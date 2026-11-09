from __future__ import annotations
from copy import deepcopy
import json
from scheme_v8.budget import Budget
from scheme_v8.util import digest
from scheme_v8.util import write_json
from scheme_v8.llm.evidence_locations import LOCATION
from scheme_v8.llm.evidence_locations import LOCATION_RULES
from scheme_v8.llm.evidence_locations import location_schema
from scheme_v8.llm.evidence_locations import set_pointer
from scheme_v8.llm.obligation_packets import encode_prompt
from scheme_v8.llm.schema import TEXT
from scheme_v8.llm.schema import arr
from scheme_v8.llm.schema import obj
from scheme_v8.llm.schema import validate_schema
from scheme_v8.llm.attribution.maintenance import SCHEMA
from scheme_v8.llm.attribution.maintenance import verify_balanced
from scheme_v8.llm.attribution.retrieval import MAINT_PROMPT
from scheme_v8.llm.attribution.retrieval import TIME_PROMPT
from scheme_v8.llm.attribution.retrieval import TIME_SCHEMA
from scheme_v8.llm.attribution.retrieval import PER_CANDIDATE_PROMPT
from scheme_v8.llm.attribution.retrieval import PER_CANDIDATE_SCHEMA
from scheme_v8.llm.attribution.temporal import verify_independent
BATCH_RULES = '\nThis request is one explicit scope batch. Review all selected_change_ids and\nthe target foundations visible here. Catalog metadata is navigation only; do\nnot invent unread source. A missing decisive dependency must be requested by\nsymbol/path. Do not call an omitted batch globally satisfied. Compare source\nrequirements to the same OLD harness. Retain the existing necessary-maintenance\nstandard, including preexisting blockers. Split different obligations; do not\nmix alternative blockers into one before/after comparison. If focus_candidate\nis supplied, assess ONLY that candidate, preserve its ID, and do not introduce\nunrelated candidates. It is a hypothesis, not a trusted conclusion. Check both\nsupporting and refuting evidence and alternatives.\n'
REPAIR_SCHEMA = obj({'repairs': arr(obj({'pointer': TEXT, 'replacement': LOCATION}))})
REPAIR_PROMPT = 'Repair ONLY the listed invalid citation locations. The claim\ntext and verdict are frozen and must not be rewritten. Return one replacement\nfor each repairable pointer, none for valid references. Select the source that\nactually supports the frozen claim; do not change roles merely to bypass a\ncheck. Dependencies require a specific relationship to a primary contract.\nIf no supplied evidence supports the citation, leave that pointer unrepaired.\n' + LOCATION_RULES

def protocol_hashes():
    return {k: digest(v.encode()) for k, v in {'maintenance_prompt': MAINT_PROMPT + BATCH_RULES + LOCATION_RULES, 'temporal_prompt': TIME_PROMPT + BATCH_RULES + LOCATION_RULES, 'candidate_prompt': PER_CANDIDATE_PROMPT + LOCATION_RULES, 'repair_prompt': REPAIR_PROMPT, 'schemas': json.dumps([location_schema(SCHEMA), location_schema(TIME_SCHEMA), location_schema(PER_CANDIDATE_SCHEMA), REPAIR_SCHEMA], sort_keys=True)}.items()}

def validate_answer(raw, store, request, packet, temporal):
    answer, citations, errors, ledger = store.materialize(raw, request['evidence'])
    vp = {**packet, 'selected_change_ids': request['selected_change_ids'], 'obligation_batch_mode': True, 'total_change_groups': len(request['selected_change_ids']), 'omitted_change_group_count': 0, 'evidence': packet['evidence'] + citations}
    if temporal:
        checked = verify_independent({k: answer[k] for k in ('summary', 'coverage_complete', 'coverage_evidence', 'claims', 'missing_information')}, vp)
    else:
        checked = verify_balanced(answer, vp)
    return (answer, checked, vp, errors, ledger)

def claim_status(checked, candidate_id, temporal):
    if temporal:
        return next((c['status'] for c in checked['claims'] if c['claim_id'] == candidate_id), 'unknown')
    return 'needs_update' if any((b['id'] == candidate_id for b in checked['accepted'])) else 'unknown'

def aggregate(temporal, obligations, scope_complete):
    states = [o['status'] for o in obligations if o['status'] != 'dismissed']
    if temporal:
        if 'introduced' in states:
            return 'introduced'
        if states and all((s == 'preexisting' for s in states)):
            return 'preexisting'
        return 'no_gap' if not states and scope_complete else 'unknown'
    if 'needs_update' in states:
        return 'needs_update'
    return 'satisfied_in_scope' if not states and scope_complete else 'unknown'

class Head:

    def __init__(self, case, output, config, temporal, client_factory):
        self.case, self.output, self.config, self.temporal = (case, output, config, temporal)
        output.mkdir(parents=True)
        self.budget = Budget(config['whole_budget'])
        self.client = client_factory(config['llm'], self.budget)
        self.limit = config['llm'].get('request_max_chars', 950000)
        if not 10000 <= self.limit < 1048576:
            raise ValueError('request_max_chars must leave room below the observed call limit')
        self.pack_limit = min(config['llm'].get('request_pack_chars', 750000), self.limit - 10000)
        self.errors, self.missing, self.audit = ([], [], [])
        self.citation_events, self.final_citation_errors = ([], [])
        self.instructions = (TIME_PROMPT if temporal else MAINT_PROMPT) + BATCH_RULES + LOCATION_RULES
        self.schema = location_schema(TIME_SCHEMA if temporal else SCHEMA)

    def infer(self, instructions, request, schema, folder):
        prompt = encode_prompt(instructions, request)
        if len(prompt) > self.limit:
            raise ValueError(f'local_transport_guard:{len(prompt)}>{self.limit}')
        write_json(folder / 'request.json', request)
        raw = self.client.infer(prompt, schema, folder / 'llm')
        validate_schema(raw, schema)
        write_json(folder / 'response.json', raw)
        return raw

    def repair(self, raw, store, request, folder):
        frozen = deepcopy(raw)
        _, _, errors, _ = store.materialize(frozen, request['evidence'])
        initial = deepcopy(errors)
        if errors:
            context = {}
            for error in errors:
                parts = error['pointer'].split('/')
                if len(parts) > 2 and parts[1] in ('claims', 'blockers', 'decisions', 'facts'):
                    context['/'.join(parts[:3])] = frozen[parts[1]][int(parts[2])]
                elif len(parts) > 1 and isinstance(frozen.get(parts[1]), dict):
                    context['/' + parts[1]] = frozen[parts[1]]
                else:
                    context['scope'] = frozen.get('scope', {k: v for k, v in frozen.items() if not isinstance(v, (list, dict))})
            repair_request = {**request, 'citation_errors': errors, 'frozen_context': context}
            if len(encode_prompt(REPAIR_PROMPT, repair_request)) <= self.limit:
                try:
                    fixed = self.infer(REPAIR_PROMPT, repair_request, REPAIR_SCHEMA, folder / 'citation_repair')
                    allowed = {e['pointer'] for e in errors}
                    seen = set()
                    for repair in fixed['repairs']:
                        pointer = repair['pointer']
                        if pointer not in allowed or pointer in seen:
                            raise ValueError('repair_modified_unrequested_or_duplicate_field:' + pointer)
                        seen.add(pointer)
                    for repair in fixed['repairs']:
                        set_pointer(frozen, repair['pointer'], repair['replacement'])
                except (ValueError, OSError, RuntimeError) as exc:
                    self.errors.append('citation_repair:' + str(exc))
            else:
                self.errors.append('citation_repair_requires_focused_task')
        _, _, remaining, _ = store.materialize(frozen, request['evidence'])
        event = {'stage': str(folder.relative_to(self.output)), 'initial': initial, 'remaining': remaining}
        self.citation_events.append(event)
        write_json(folder / 'citation_repair_audit.json', event)
        write_json(folder / 'resolved_response.json', frozen)
        return frozen

    def review(self, store, packet, request, folder):
        raw = self.infer(self.instructions, request, self.schema, folder)
        raw = self.repair(raw, store, request, folder)
        answer, checked, vp, errors, ledger = validate_answer(raw, store, request, packet, self.temporal)
        write_json(folder / 'citations.json', ledger)
        write_json(folder / 'verification.json', {'checked': checked, 'citation_errors': errors})
        return {'raw': raw, 'answer': answer, 'checked': checked, 'packet': vp, 'request': request, 'citation_errors': errors, 'folder': folder}
