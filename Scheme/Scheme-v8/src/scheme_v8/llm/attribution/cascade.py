"""Cascade engine: one conversation per sample, 2-4 model turns.

Round 0 (program): build the evidence packet once for both decisions.
Round 1 (new session): spec + evidence; discover candidate obligations with
         J1 premises and a J4 scope assessment.
Round 2 (fork of round 1 when the backend supports it, else resume): batched
         review of EVERY candidate (necessity gate) plus scope audit; carries
         evidence retrieved for round-1 requests and round-1 citation errors.
Extra   (at most llm.cascade_extra_rounds): when the maintenance verdict is
         unknown and the review requested facts, retrieve them and review again.
Round 3 (only after needs_update): timing of the kept obligations; sends only
         the before/after source of their change groups.

Every turn after the first sends only new instructions and new evidence. All
program-side checks of the dual engine are reused: citation materialization,
the five-premise gate verifier, scope closure and side-fact timing derivation.
"""
from __future__ import annotations

import json
from copy import deepcopy

from scheme_v8.context.reader import load_case
from scheme_v8.budget import Budget
from scheme_v8.util import digest, write_json
from scheme_v8.llm.backends import QuotaExhausted, make_client
from scheme_v8.llm.evidence_locations import EvidenceStore, LOCATION, LOCATION_RULES, location_schema, set_pointer
from scheme_v8.llm.obligation_packets import encode_prompt, plan_packets
from scheme_v8.llm.schema import BOOL, TEXT, arr, nullable, obj, validate_schema
from scheme_v8.llm.attribution.head import REPAIR_PROMPT, REPAIR_SCHEMA, validate_answer
from scheme_v8.llm.attribution.maintenance import BLOCKER, SCHEMA as MAINT_SCHEMA
from scheme_v8.llm.attribution.retrieval import MAINT_PROMPT, expand, initial_packet
from scheme_v8.llm.attribution.scope import SCHEMA as SCOPE_SCHEMA, verify_closure
from scheme_v8.llm.attribution.temporal import INDEPENDENT_SCHEMA, PROMPT as TIME_BASE
from scheme_v8.llm.attribution.policy import GATE_PROTOCOL, GATE_SCHEMA, POLICY, verify_gate
from scheme_v8.llm.attribution.paired_source import pair_packet
from scheme_v8.llm.attribution.patch_alignment import align_patch
from scheme_v8.llm.attribution.combine import combine_cascade
from scheme_v8.llm.attribution.spec import render

SESSION_NOTE = """
CONVERSATION PROTOCOL: this review is one conversation. Later turns may add
evidence, a candidate review or before-version source. Evidence from any earlier
turn stays valid and citable by its unit_id. Keep every free-text reason concise
(at most about 80 words); cite instead of restating code.
"""
TASK_CONTEXT = """TASK CONTEXT: this is a static code-review task in software maintenance. A fuzz
harness is a test program, like a unit test, that feeds generated inputs to a
library. The question is only whether that test program must be updated after a
library change so that it keeps building, running and covering the library's
supported behavior. No exploit, attack or vulnerability research is requested;
the inputs are the project's own source code, build files and test code.

"""
DISCOVER = TASK_CONTEXT + MAINT_PROMPT + LOCATION_RULES + POLICY + SESSION_NOTE + render('PROT-FACTS')
PART = 'EVIDENCE PART {i}/{n} of this review. Retain it; do not analyze yet. Return received=true.'
PART_SCHEMA = obj({'received': BOOL})
REVIEW = """REVIEW TURN. Independently audit EVERY candidate in `candidates`; each is a
hypothesis from the discovery turn, not a trusted conclusion. Return exactly one
decision per candidate_id.
""" + GATE_PROTOCOL + """
Then audit the whole scope again (J4): assess every selected change ID and the
four foundations with evidence, challenge both dismissals (J6) and retained
gaps (J1). Out-of-scope items (D7) are not obligations. New evidence contains
contracts retrieved for earlier requests (`evidence`); `citation_errors` lists earlier
citations the program could not verify; cite valid locations instead. Request
exact symbols or paths only for decisive missing facts (E3).
If the evidence establishes a distinct obligation that is NOT among `candidates`
(for example one that only became visible with the new evidence), report it in
`new_candidates` with the same fields as a discovery blocker and mark its change
group as blocked in the scope audit. It is reviewed in a separate turn; do not
add a decision for it here.
"""
TIMING = """TIMING TURN. Do not search for new obligations in this turn. Assess exactly
the frozen obligations in `obligations_to_time`: use each candidate_id as
claim_id and keep its change_ids. `evidence` holds the
reconstructed before_source and after_source units for their change groups;
harness units from earlier turns remain citable. Necessity of these obligations
is already established by the review: set necessary="yes" and assess timing only
(T1, T2); do not re-decide whether the obligation is required.
Units of files this change did
not modify are delivered as identical before/after pairs (invariant); cite them
on both sides when the obligation rests on unchanged code or build files.
Follow these rules:
""" + TIME_BASE
DECISION = deepcopy(GATE_SCHEMA)
REVIEW_SCHEMA = obj({'decisions': arr(DECISION), 'new_candidates': arr(BLOCKER), 'scope': SCOPE_SCHEMA,
                     'requested_symbols': arr(TEXT), 'requested_paths': arr(TEXT)})
TIME_SCHEMA = INDEPENDENT_SCHEMA
SECTIONS = {'part': PART_SCHEMA, 'discover': location_schema(MAINT_SCHEMA),
            'review': location_schema(REVIEW_SCHEMA), 'timing': location_schema(TIME_SCHEMA),
            'repair': REPAIR_SCHEMA}
# One schema for every turn of a conversation. A backend may place the output
# schema ahead of the messages (Claude CLI sends it as a tool definition), so a
# per-turn schema would invalidate the cached conversation prefix.
# Each section is `object | null`, so the format itself admits at most one answer.
SESSION_SCHEMA = obj({'turn': {'type': 'string', 'enum': list(SECTIONS)},
                      **{name: nullable(schema) for name, schema in SECTIONS.items()}})
REPAIR = ('CITATION REPAIR TURN. `citation_errors` lists citation locations in your previous answer '
          'in this conversation that the program could not verify; `pointer` addresses them in that answer. '
          + REPAIR_PROMPT)
CORRECTION = ('OUTPUT CORRECTION. Your previous output in this conversation did not follow the output '
              'protocol: {problem}. Re-send the same answer for that turn: set turn="{name}", fill the "{name}" '
              'object and set every other section to null. Do not change its content.\n')
TURN_NOTE = ('OUTPUT: set turn="{name}", fill the "{name}" object, and set every other section to null.\n')


def cascade_protocol_hashes(config=None):
    texts = {'cascade_correction': CORRECTION, 'cascade_discover': DISCOVER, 'cascade_review': REVIEW, 'cascade_timing': TIMING, 'cascade_part': PART, 'cascade_repair': REPAIR,
             'cascade_turn_note': TURN_NOTE, 'cascade_schema': json.dumps(SESSION_SCHEMA, sort_keys=True)}
    return {k: digest(v.encode()) for k, v in texts.items()}


def to_candidates(blockers, start, origin):
    return [{'candidate_id': f'c{start + i + 1}', 'source_id': b['id'], 'origin': origin, 'kind': b['kind'],
             'change_ids': list(b['change_ids']), 'requirement': b['requirement'],
             'target_route': b['target_route'], 'failure_condition': b['failure_condition'],
             'alternative_paths': b['alternative_paths'], 'discovery_necessary': b['necessary'],
             'discovery_established': b['established']} for i, b in enumerate(blockers)]


class Cascade:

    def __init__(self, case, output, config, client_factory=make_client):
        self.case, self.output, self.config = (case, output, config)
        self.llm = config['llm']
        output.mkdir(parents=True)
        self.budget = Budget(config['whole_budget'])
        self.client = client_factory(self.llm, self.budget)
        self.limit = min(self.llm.get('request_pack_chars', 750000), self.llm.get('request_max_chars', 950000) - 10000)
        self.errors, self.rounds, self.delivered = ([], [], {})
        self.turn = 0

    # -- transport -------------------------------------------------------
    def call(self, instructions, payload, section, label, session=None, fork=False):
        self.turn += 1
        folder = self.output / f'turn-{self.turn:02d}-{label}'
        prompt = encode_prompt(TURN_NOTE.format(name=section) + instructions, payload)
        if len(prompt) > self.llm.get('request_max_chars', 950000):
            raise ValueError(f'local_transport_guard:{len(prompt)}')
        write_json(folder / 'request.json', payload)
        envelope = self.client.infer(prompt, SESSION_SCHEMA, folder / 'llm', session=session, fork=fork, persist=True)
        if envelope['turn'] != section or envelope[section] is None:
            # One correction turn in the same conversation; the answer itself is not re-derived.
            problem = f'turn="{envelope["turn"]}" and "{section}" is {"null" if envelope[section] is None else "filled"}'
            write_json(folder / 'envelope_mismatch.json', {'problem': problem, 'envelope': envelope})
            fixed = encode_prompt(CORRECTION.format(problem=problem, name=section), {'evidence': []})
            envelope = self.client.infer(fixed, SESSION_SCHEMA, folder / 'llm-correction',
                                         session=self.client.last_session, persist=True)
            if envelope['turn'] != section or envelope[section] is None:
                raise ValueError(f'session_envelope_mismatch:{section}:{envelope["turn"]}')
        # Sections other than the requested one are ignored even if filled.
        raw = envelope[section]
        validate_schema(raw, SECTIONS[section])
        write_json(folder / 'response.json', raw)
        self.rounds.append({'turn': self.turn, 'label': label, 'session_in': session, 'fork': fork,
                            'session_out': self.client.last_session, 'prompt_chars': len(prompt)})
        return raw, folder

    def send(self, instructions, store, packet, unit_ids, task, section, label, session=None, fork=False):
        """Deliver undelivered units (split into parts if needed); the last turn carries the task."""
        unit_ids = [u for u in unit_ids if u not in self.delivered]
        if unit_ids:
            parts = plan_packets(store, packet, instructions, self.limit, unit_ids, task)
        else:
            parts = [{**{k: packet[k] for k in ('target', 'sample_id') if k in packet}, **task, 'evidence': []}]
        for i, part in enumerate(parts):
            final = i == len(parts) - 1
            payload = dict(part) if final else {k: v for k, v in part.items() if k not in task}
            if self.turn:
                # The catalog and inventory were sent in the first turn of this conversation.
                payload.pop('evidence_catalog', None)
                payload.pop('source_root_inventory', None)
                payload.pop('program_facts', None)
            if final:
                payload['selected_change_ids'] = packet['selected_change_ids']
                text = instructions if len(parts) == 1 else f'FINAL PART {len(parts)}/{len(parts)} of this request.\n' + instructions
                raw, folder = self.call(text, payload, section, label, session, fork)
            else:
                raw, folder = self.call(PART.format(i=i + 1, n=len(parts)), payload, 'part', f'{label}-part{i + 1}', session, fork)
                session, fork = (self.client.last_session, False)
            for view in part['evidence']:
                self.delivered.setdefault(view['unit_id'], []).append(view)
        return raw, folder

    def repair_citations(self, raw, store, delivered, folder, label):
        """One light turn in the same conversation: only failed citation locations
        are replaced; decisions, statuses and reasons stay frozen."""
        _, _, errors, _ = store.materialize(raw, delivered)
        audit = {'initial': errors, 'applied': [], 'rejected': [], 'remaining': errors}
        if errors and self.llm.get('cascade_citation_repair', True):
            pointers = {e['pointer'] for e in errors}
            listed = [{'pointer': e['pointer'], 'cited': e['location'], 'reason': e['reason']} for e in errors]
            try:
                fixed, _ = self.call(REPAIR, {'citation_errors': listed, 'evidence': []}, 'repair', f'{label}-repair',
                                     self.client.last_session)
                patched, seen = (deepcopy(raw), set())
                for item in fixed['repairs']:
                    pointer = item['pointer']
                    if pointer not in pointers or pointer in seen:
                        audit['rejected'].append({'pointer': pointer, 'reason': 'not_requested_or_duplicate'})
                        continue
                    seen.add(pointer)
                    try:
                        set_pointer(patched, pointer, item['replacement'])
                        audit['applied'].append(pointer)
                    except (KeyError, IndexError, ValueError, TypeError) as exc:
                        audit['rejected'].append({'pointer': pointer, 'reason': 'bad_pointer:' + str(exc)})
                raw = patched
                _, _, audit['remaining'], _ = store.materialize(raw, delivered)
            except (ValueError, OSError, RuntimeError) as exc:
                if isinstance(exc, QuotaExhausted):
                    raise
                self.errors.append(f'{label}_citation_repair:' + str(exc))
        write_json(folder / 'citation_repair.json', audit)
        write_json(folder / 'resolved_response.json', raw)
        return raw

    def views(self):
        return [v for views in self.delivered.values() for v in views]

    # -- rounds ----------------------------------------------------------
    def discover(self, packet, store):
        raw, folder = self.send(DISCOVER, store, packet, list(store.units), {}, 'discover', 'discover')
        request = {'selected_change_ids': packet['selected_change_ids'], 'evidence': self.views()}
        answer, checked, vp, errors, ledger = validate_answer(raw, store, request, packet, False)
        write_json(folder / 'verification.json', {'checked': checked, 'citation_errors': errors})
        return raw, to_candidates(raw['blockers'], 0, 'discover'), errors

    def review(self, packet, store, candidates, citation_errors, session, fork, label):
        new_ids = [u for u in store.units if u not in self.delivered]
        task = {'candidates': candidates, 'citation_errors': [{'pointer': e['pointer'], 'reason': e['reason']} for e in citation_errors]}
        raw, folder = self.send(REVIEW, store, packet, new_ids, task, 'review', label, session, fork)
        delivered = self.views()
        raw = self.repair_citations(raw, store, delivered, folder, label)
        by_id = {d['candidate_id']: d for d in raw['decisions']}
        decisions = []
        for c in candidates:
            d = by_id.get(c['candidate_id'])
            if d is None:
                decisions.append({'candidate_id': c['candidate_id'], 'decision': 'uncertain', 'errors': ['decision_missing']})
                continue
            checked = verify_gate(d, store, {'evidence': delivered}, c['candidate_id'])
            decisions.append({'candidate_id': c['candidate_id'], 'decision': checked['decision'], 'errors': checked['errors'],
                              'obligation_class': checked.get('obligation_class'), 'citation_errors': checked['citation_errors'],
                              'cited_paths': sorted({x['path'] for x in checked.get('citations', []) if x.get('path')})})
        answer, citations, scope_errors, _ = store.materialize({'scope': raw['scope']}, delivered)
        vp = {**packet, 'selected_change_ids': packet['selected_change_ids'], 'evidence': packet['evidence'] + citations,
              'prior_raw_verdict': 'unknown'}
        closure = verify_closure(answer['scope'], vp)
        complete = (closure['coverage_complete'] and not scope_errors and packet.get('diff_coverage_complete', False)
                    and not packet.get('pending_units'))
        write_json(folder / 'verification.json', {'decisions': decisions, 'closure': closure, 'scope_citation_errors': scope_errors,
                                                  'scope_complete': complete})
        return raw, decisions, complete

    def timing(self, packet, builder, kept, session, cited_paths=()):
        paired = pair_packet(builder, packet, patch_resolver=align_patch)
        pstore = EvidenceStore(paired)
        pstore.save(self.output / 'paired_store')
        anchors = {g for c in kept for g in c['change_ids']}
        if not anchors or any(not c['change_ids'] for c in kept):
            anchors = set(packet['selected_change_ids'])
        units = [u for u, unit in pstore.units.items()
                 if unit['kind'] in ('before_source', 'after_source') and set(unit['change_ids']) & anchors]
        # Files the kept obligations rest on but this change did not touch (build files,
        # unchanged callers, ...) are delivered as before/after pairs too; unchanged
        # units are marked invariant and are identical on both sides (T1).
        units += [u for u, unit in pstore.units.items()
                  if unit['kind'] in ('before_source', 'after_source') and unit['path'] in set(cited_paths) and u not in units]
        units += [u for u, unit in pstore.units.items() if unit['kind'] == 'harness']
        frozen = [{'candidate_id': c['candidate_id'], 'change_ids': c['change_ids'] or sorted(anchors),
                   'requirement': c['requirement'], 'target_route': c['target_route'],
                   'failure_condition': c['failure_condition'], 'obligation_class': c.get('obligation_class')} for c in kept]
        selected = sorted(anchors)
        timing_packet = {**paired, 'selected_change_ids': selected}
        raw, folder = self.send(TIMING, pstore, timing_packet, units, {'obligations_to_time': frozen},
                                'timing', 'timing', session)
        delivered = [v for v in self.views() if v['unit_id'] in pstore.units]
        raw = self.repair_citations(raw, pstore, delivered, folder, 'timing')
        wanted = {c['candidate_id'] for c in frozen}
        raw = {**raw, 'claims': [c for c in raw['claims'] if c['claim_id'] in wanted]}
        answer, checked, vp, errors, _ = validate_answer(raw, pstore, {'selected_change_ids': selected, 'evidence': delivered}, timing_packet, True)
        returned = {c['claim_id'] for c in raw['claims']}
        # Necessity is frozen by the review: a timing answer that declares a kept
        # obligation unnecessary is unresolved timing, never no_gap.
        states = [('unknown' if c['status'] == 'not_necessary' else c['status']) for c in checked['claims']]
        if returned != wanted or not states:
            status = 'unknown'
        elif 'introduced' in states:
            status = 'introduced'
        elif all(s == 'preexisting' for s in states):
            status = 'preexisting'
        else:
            status = 'unknown'
        checked = {**checked, 'cascade_status': status, 'necessity_frozen': True}
        write_json(folder / 'verification.json', {'checked': checked, 'citation_errors': errors, 'missing_claims': sorted(wanted - returned),
                                                  'preimage_errors': paired.get('preimage_errors', [])})
        return status, checked

    # -- driver ----------------------------------------------------------
    def execute(self):
        packet, builder = initial_packet(self.case, self.config, self.budget)
        store = EvidenceStore(packet)
        store.save(self.output / 'evidence_store')
        raw1, candidates, cite_errors = self.discover(packet, store)
        main = self.client.last_session
        fork = self.llm.get('cascade_review', 'fork') == 'fork' and self.client.provider == 'claude_cli'
        if raw1['requested_symbols'] or raw1['requested_paths'] or raw1['scope']['missing_information'] or any(b['missing_information'] for b in raw1['blockers']):
            packet = expand(packet, builder, raw1, None, False)
            store = EvidenceStore(packet)
        raw2, decisions, complete = self.review(packet, store, candidates, cite_errors, main, fork, 'review')
        session = self.client.last_session
        # Obligations first seen during review (e.g. after retrieval filled a
        # discovery gap) get their own necessity review in a further turn.
        for rnd in range(self.llm.get('cascade_new_candidate_rounds', 1)):
            new = to_candidates(raw2['new_candidates'], len(candidates), f'review-{rnd + 1}')
            if not new:
                break
            candidates = candidates + new
            raw2, more, complete = self.review(packet, store, new, [], session, False, f'review-new{rnd + 1}')
            session = self.client.last_session
            decisions = decisions + more
        for extra in range(self.llm.get('cascade_extra_rounds', 1)):
            verdict = self.verdict(decisions, complete)
            wants = raw2['requested_symbols'] or raw2['requested_paths'] or raw2['scope']['missing_information'] or any(d['missing_information'] for d in raw2['decisions'])
            if verdict != 'unknown' or not wants:
                break
            follow = {'scope': raw2['scope'], 'blockers': [{'missing_information': d['missing_information']} for d in raw2['decisions']],
                      'requested_symbols': raw2['requested_symbols'] + [s for d in raw2['decisions'] for s in d['requested_symbols']],
                      'requested_paths': raw2['requested_paths'] + [p for d in raw2['decisions'] for p in d['requested_paths']]}
            before = set(store.units)
            packet = expand(packet, builder, follow, None, False)
            store = EvidenceStore(packet)
            if set(store.units) <= before:
                break
            open_ids = {d['candidate_id'] for d in decisions if d['decision'] == 'uncertain'}
            again = [c for c in candidates if c['candidate_id'] in open_ids]
            raw2, redo, complete = self.review(packet, store, again, [], session, False, f'review-extra{extra + 1}')
            session = self.client.last_session
            redone = {d['candidate_id']: d for d in redo}
            decisions = [redone.get(d['candidate_id'], d) for d in decisions]
        # Candidates proposed in the last review turn were never reviewed: they
        # cannot establish a gap, but they do block an affirmative negative.
        for c in to_candidates(raw2['new_candidates'], len(candidates), 'unreviewed'):
            candidates.append(c)
            decisions.append({'candidate_id': c['candidate_id'], 'decision': 'uncertain', 'errors': ['new_candidate_not_reviewed']})
        verdict = self.verdict(decisions, complete)
        timing, timing_checked = ('not_applicable', None)
        if verdict == 'needs_update':
            kept_ids = {d['candidate_id'] for d in decisions if d['decision'] == 'keep'}
            classes = {d['candidate_id']: d.get('obligation_class') for d in decisions}
            kept = [{**c, 'obligation_class': classes.get(c['candidate_id'])} for c in candidates if c['candidate_id'] in kept_ids]
            cited = sorted({p for d in decisions if d['candidate_id'] in kept_ids for p in d.get('cited_paths', [])})
            timing, timing_checked = self.timing(packet, builder, kept, session, cited)
        return {'verdict': verdict, 'status': timing, 'candidates': candidates, 'decisions': decisions,
                'scope_complete': complete, 'timing': timing_checked}

    @staticmethod
    def verdict(decisions, complete):
        states = [d['decision'] for d in decisions]
        if 'keep' in states:
            return 'needs_update'
        return 'satisfied_in_scope' if complete and 'uncertain' not in states else 'unknown'

    def cost(self):
        usage = [c.get('usage') or {} for c in self.client.calls]
        total = lambda key: sum((u.get(key) or 0) for u in usage)
        return {**self.budget.snapshot(), 'llm_calls': len(self.client.calls), 'model_seconds': round(sum(c.get('seconds', 0) for c in self.client.calls), 3),
                'input_tokens_uncached': total('input_tokens'), 'input_tokens_cached': total('cached_input_tokens'),
                'input_tokens_cache_write': total('cache_write_input_tokens'), 'output_tokens': total('output_tokens'),
                'input_tokens_total': total('input_tokens') + total('cached_input_tokens') + total('cache_write_input_tokens')}


def analyze_cascade(input_root, output, config, client_factory=make_client):
    case = load_case(input_root)
    output.mkdir(parents=True, exist_ok=False)
    engine = Cascade(case, output / 'cascade', config, client_factory)
    try:
        result = engine.execute()
        result['errors'] = engine.errors
    except QuotaExhausted:
        raise
    except (ValueError, OSError, RuntimeError) as exc:
        result = {'verdict': 'unknown', 'status': 'unknown', 'errors': [type(exc).__name__ + ': ' + str(exc)]}
    finally:
        engine.client.close()
    head = {**result, 'model_calls': engine.client.calls, 'rounds': engine.rounds, 'cost': engine.cost()}
    write_json(output / 'cascade' / 'verification.json', head)
    maintenance, timing = (result['verdict'], result['status'])
    prediction = {'prediction_schema': '30.0', 'engine': 'cascade_session', 'provider': config['llm'].get('provider', 'codex_cli'),
                  'model': config['llm']['model'], 'sample_id': case.sample_id, 'input_hash': case.manifest['input_hash'],
                  'target': case.target, 'analysis_scope': 'change_related', 'protocol_hashes': cascade_protocol_hashes(config),
                  'verdict': maintenance, 'maintenance_verdict': maintenance, 'attribution_status': timing,
                  'introduced_by_this_change': True if timing == 'introduced' else False if timing == 'preexisting' else None,
                  'analysis_complete': maintenance != 'unknown', 'llm_used': True, 'whole_function_heads': {'cascade': head},
                  'cost': head['cost'], 'missing_information': [], **combine_cascade(maintenance, timing)}
    write_json(output / 'prediction.json', prediction)
    (output / 'report.md').write_text(f'# {case.sample_id}\n\n维护：{maintenance}\n\n归因：{timing}\n\n'
                                      f'级联会话：{len(engine.client.calls)} 次调用；详见 cascade/。\n', encoding='utf-8')
    return prediction
