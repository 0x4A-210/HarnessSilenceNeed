from copy import deepcopy
import json
from pathlib import Path
from scheme_v8.context.reader import load_case
from scheme_v8.util import digest
from scheme_v8.util import write_json
from scheme_v8.llm.evidence_locations import EvidenceStore
from scheme_v8.llm.evidence_locations import LOCATION_RULES
from scheme_v8.llm.evidence_locations import location_schema
from scheme_v8.llm.obligation_packets import encode_prompt
from scheme_v8.llm.obligation_packets import plan_packets
from scheme_v8.llm.obligation_ledger import FACT_SCHEMA
from scheme_v8.llm.obligation_ledger import FACT_PROMPT
from scheme_v8.llm.obligation_ledger import REGISTRY_SCHEMA
from scheme_v8.llm.obligation_ledger import REGISTRY_PROMPT
from scheme_v8.llm.obligation_ledger import check_registry
from scheme_v8.llm.obligation_ledger import verified_facts
from scheme_v8.llm.obligation_ledger import dossier
from scheme_v8.llm.obligation_ledger import focused_ids
from scheme_v8.llm.backends import make_client
from scheme_v8.llm.attribution.head import Head
from scheme_v8.llm.attribution.head import aggregate
from scheme_v8.llm.attribution.head import claim_status
from scheme_v8.llm.attribution.head import validate_answer
from scheme_v8.llm.attribution.retrieval import initial_packet
from scheme_v8.llm.attribution.retrieval import expand
from scheme_v8.llm.attribution.retrieval import retrieval_requests
from scheme_v8.llm.attribution.paired_source import pair_packet
from scheme_v8.llm.attribution.combine import combine
from scheme_v8.llm.attribution.necessity_proof import POLICY
from scheme_v8.llm.attribution.necessity_proof import GATE_SCHEMA
from scheme_v8.llm.attribution.necessity_proof import GATE_PROMPT
from scheme_v8.llm.attribution.necessity_proof import verify_gate
from scheme_v8.llm.attribution.patch_alignment import align_patch
from scheme_v8.llm.attribution import policy as split_policy
LEDGER_RULES = "\nThis request may join grounded facts extracted from separate complete-function\nreads. All cited original text is supplied again. Validate the facts, consider\ncounterevidence, and compare both versions in THIS joined assessment. A catalog\nentry alone is not evidence. Ask only for decisive facts still missing after\nconsidering the joined evidence, not for the contents of an unrelated batch.\nIf focus_candidate is present, assess exactly its frozen ID, change IDs and\nidentity predicate. Do not introduce other blockers into that comparison.\nContext-only continuations never certify or veto the whole sample's coverage.\n"

def protocol_hashes(config=None):
    from scheme_v8.llm.attribution.head import protocol_hashes as base_hashes
    values = {**base_hashes(), **{k: digest(v.encode()) for k, v in {'ledger_rules': LEDGER_RULES + POLICY, 'fact_prompt': FACT_PROMPT, 'registry_prompt': REGISTRY_PROMPT, 'necessity_prompt': GATE_PROMPT, 'ledger_schemas': json.dumps([FACT_SCHEMA, REGISTRY_SCHEMA, GATE_SCHEMA], sort_keys=True)}.items()}}
    if (config or {}).get('llm', {}).get('obligation_policy') == 'split_coverage_compatibility':
        values.update({k: digest(v.encode()) for k, v in {'necessity_prompt': split_policy.GATE_PROMPT, 'split_policy': split_policy.POLICY, 'maintenance_ledger_rules': split_policy.ledger_rules(False), 'temporal_ledger_rules': split_policy.ledger_rules(True), 'split_gate_schema': json.dumps(split_policy.GATE_SCHEMA, sort_keys=True), 'focused_protocol': 'single assessment; IDs and primary change set bound by program'}.items()})
    return values

class LedgerHead(Head):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.split = True
        self.policy = split_policy.POLICY
        self.gate_prompt = split_policy.GATE_PROMPT
        self.gate_schema = split_policy.GATE_SCHEMA
        self.gate_verifier = split_policy.verify_gate
        self.instructions += self.policy + split_policy.ledger_rules(self.temporal)
        self.facts, self.gates, self.registry_audit = ([], [], [])
        self.retrieval_answers = []
        self.review_cache = {}

    def review(self, store, packet, request, folder):
        if not request.get('focus_candidate'):
            return super().review(store, packet, request, folder)
        raw = self.infer(self.instructions, request, split_policy.focused_schema(self.schema, self.temporal), folder)
        raw = split_policy.bind_assessment(raw, request['focus_candidate'], self.temporal)
        write_json(folder / 'bound_response.json', raw)
        raw = self.repair(raw, store, request, folder)
        answer, checked, vp, errors, ledger = validate_answer(raw, store, request, packet, self.temporal)
        write_json(folder / 'citations.json', ledger)
        write_json(folder / 'verification.json', {'checked': checked, 'citation_errors': errors})
        return {'raw': raw, 'answer': answer, 'checked': checked, 'packet': vp, 'request': request, 'citation_errors': errors, 'folder': folder}

    def remember(self, answer):
        self.retrieval_answers.append(answer)
        self.missing.extend(answer.get('missing_information', []))
        self.missing.extend(answer.get('scope', {}).get('missing_information', []))
        for item in answer.get('claims', []) + answer.get('blockers', []):
            self.missing.extend(item.get('missing_information', []))

    def facts_for(self, store, request, folder):
        instructions = FACT_PROMPT + self.policy + LOCATION_RULES
        raw = self.infer(instructions, request, location_schema(FACT_SCHEMA), folder)
        raw = self.repair(raw, store, request, folder)
        facts, errors = verified_facts(raw, store, request)
        self.final_citation_errors.extend(errors)
        self.missing.extend(raw['missing_information'])
        self.remember(raw)
        write_json(folder / 'verified_facts.json', {'facts': facts, 'errors': errors})
        return facts

    def candidates(self, readings):
        result = {}
        for reading in readings:
            for item in reading['raw']['claims' if self.temporal else 'blockers']:
                requirement = item['after']['requirement'] if self.temporal else item['requirement']
                key = digest(json.dumps([sorted(item['change_ids']), requirement], sort_keys=True).encode())[:20]
                if key not in result:
                    result[key] = {'item': item, 'reading': reading}
        return result

    def normalize(self, candidates, folder):
        simplified = {k: {'candidate_id': k, 'candidate': v['item']} for k, v in candidates.items()}
        if len(candidates) > 1:
            request = {'candidates': list(simplified.values())}
            try:
                raw = self.infer(REGISTRY_PROMPT, request, REGISTRY_SCHEMA, folder)
                groups = check_registry(raw, candidates)
                self.registry_audit.append({'folder': str(folder), 'groups': groups})
                return groups
            except (ValueError, OSError, RuntimeError) as exc:
                self.errors.append('registry:' + str(exc))
        return [{'member_ids': [k], 'operation': v['item'].get('target_route', ''), 'condition': v['item'].get('failure_condition', ''), 'capability': v['item'].get('requirement', v['item'].get('after', {}).get('requirement', '')), 'consequence': v['item'].get('comparison_reason', v['item'].get('requirement', '')), 'equivalence_reason': 'Singleton; no semantic merge assumed.'} for k, v in candidates.items()]

    def assess(self, store, packet, group, candidates, folder):
        members = [candidates[k] for k in group['member_ids']]
        item = deepcopy(members[0]['item'])
        cid = 'o-' + digest(json.dumps(group['member_ids'], sort_keys=True).encode())[:16]
        id_field = 'claim_id' if self.temporal else 'id'
        item[id_field] = cid
        item['change_ids'] = sorted({g for m in members for g in m['item']['change_ids']})
        identity = {k: group[k] for k in ('operation', 'condition', 'capability', 'consequence')}
        extra = {'focus_candidate': item, 'frozen_identity': identity, 'equivalent_hypotheses': [m['item'] for m in members]}
        chosen = sorted({uid for m in members for uid in focused_ids(store, m['item'])})
        batches = plan_packets(store, packet, self.instructions, self.pack_limit, chosen, extra)
        facts = []
        if len(batches) == 1:
            joined = batches[0]
        else:
            fact_instructions = FACT_PROMPT + self.policy + LOCATION_RULES
            batches = plan_packets(store, packet, fact_instructions, self.pack_limit, chosen, extra)
            for i, request in enumerate(batches):
                facts.extend(self.facts_for(store, request, folder / f'facts-{i}'))
            joined = dossier(store, packet, self.instructions, self.pack_limit, [facts, [m['item'] for m in members]], {**extra, 'joined_facts': facts, 'continuations_read': len(batches)}, chosen)
        reading = self.review(store, packet, joined, folder / 'assessment')
        raw_items = reading['raw']['claims' if self.temporal else 'blockers']
        if len(raw_items) != 1 or raw_items[0][id_field] != cid:
            raise ValueError('focused_assessment_must_return_exactly_the_frozen_obligation')
        assessed = raw_items[0]
        if set(assessed['change_ids']) != set(item['change_ids']):
            raise ValueError('focused_assessment_changed_change_identity')
        state = claim_status(reading['checked'], cid, self.temporal)
        self.remember(reading['answer'])
        self.final_citation_errors.extend(reading['citation_errors'])
        gate_instructions = self.gate_prompt + LOCATION_RULES
        gate_request = {**joined, 'candidate_id': cid, 'assessment': assessed, 'module': 'temporal' if self.temporal else 'maintenance'}
        if len(encode_prompt(gate_instructions, gate_request)) > self.pack_limit:
            gate_request = dossier(store, packet, gate_instructions, self.pack_limit, [facts, item, assessed], {**extra, 'candidate_id': cid, 'assessment': assessed, 'joined_facts': facts, 'module': 'temporal' if self.temporal else 'maintenance'}, chosen)
        schema = location_schema(self.gate_schema)
        schema = deepcopy(schema)
        schema['properties'].pop('candidate_id')
        schema['required'].remove('candidate_id')
        raw_gate = self.infer(gate_instructions, gate_request, schema, folder / 'necessity')
        raw_gate = {'candidate_id': cid, **raw_gate}
        write_json(folder / 'necessity/bound_response.json', raw_gate)
        raw_gate = self.repair(raw_gate, store, gate_request, folder / 'necessity')
        checked = self.gate_verifier(raw_gate, store, gate_request, cid)
        self.gates.append({'candidate_id': cid, **checked})
        self.errors.extend(checked['errors'])
        self.final_citation_errors.extend(checked['citation_errors'])
        self.remember(raw_gate)
        self.missing.extend(raw_gate['missing_information'])
        write_json(folder / 'necessity/verification.json', checked)
        decision = checked['decision']
        state = 'dismissed' if decision == 'dismiss' else state if decision == 'keep' else 'unknown'
        if state == 'not_necessary':
            state = 'unknown'
        record = {'obligation_key': cid, 'candidate_id': cid, 'identity': identity, 'member_ids': group['member_ids'], 'requirement': item.get('requirement', item.get('after', {}).get('requirement')), 'change_ids': item['change_ids'], 'status': state, 'necessity': decision, 'joined_continuations': len(batches), 'assessment': assessed, 'necessity_evidence': raw_gate}
        record['obligation_class'] = raw_gate['obligation_class']
        write_json(folder / 'result.json', record)
        self.facts.extend(facts)
        return (record, reading)

    def retrieve_once(self, packet, builder):
        """Consolidate missing facts before one retrieval; avoid repeated expansion."""
        symbols, paths, missing = ([], [], list(self.missing))
        for answer in self.retrieval_answers:
            requests = retrieval_requests(answer, None, self.temporal)
            symbols.extend(requests['requested_symbols'])
            paths.extend(requests['requested_paths'])
            missing.extend(requests['missing_information'])
        symbols = list(dict.fromkeys(symbols))
        keep_paths = []
        from scheme_v8.llm.attribution.maintenance import _resolve_path
        from scheme_v8.llm.whole_functions import CODE
        for name in dict.fromkeys(paths):
            path = _resolve_path(name, builder.reader.case.manifest['files'])
            if path and symbols and (Path(path).suffix.lower() in CODE):
                size = builder.reader.case.manifest['files'][path].get('size', 0)
                if size > 100000:
                    continue
            keep_paths.append(name)
        combined = {'requested_symbols': symbols, 'requested_paths': keep_paths, 'missing_information': list(dict.fromkeys(missing)), 'claims': [], 'scope': {'missing_information': list(dict.fromkeys(missing))}, 'blockers': []}
        return expand(packet, builder, combined, None, self.temporal)

    def execute(self):
        packet, builder = initial_packet(self.case, self.config, self.budget)
        records, previous_candidates = ([], {})
        max_rounds = self.config['llm'].get('whole_review_rounds', 3)
        status, complete = ('unknown', False)
        for rd in range(max_rounds):
            self.missing, self.final_citation_errors, self.retrieval_answers = ([], [], [])
            self.facts = []
            current = pair_packet(builder, packet, patch_resolver=align_patch) if self.temporal else packet
            store = EvidenceStore(current)
            store.save(self.output / 'evidence_store')
            round_dir = self.output / f'round-{rd}'
            write_json(round_dir / 'packet.json', current)
            requests = plan_packets(store, current, self.instructions, self.pack_limit)
            scans, failed = ([], False)
            for i, request in enumerate(requests):
                try:
                    if not request['selected_change_ids']:
                        self.facts.extend(self.facts_for(store, request, round_dir / f'context-{i}'))
                        continue
                    cache_key = digest(encode_prompt(self.instructions, request).encode())
                    if cache_key in self.review_cache:
                        scan = self.review_cache[cache_key]
                        write_json(round_dir / f'scan-{i}/reuse.json', {'same_run_identical_request': str(scan['folder'])})
                    else:
                        scan = self.review(store, current, request, round_dir / f'scan-{i}')
                        self.review_cache[cache_key] = scan
                    scans.append(scan)
                    self.remember(scan['answer'])
                    self.final_citation_errors.extend(scan['citation_errors'])
                except (ValueError, OSError, RuntimeError) as exc:
                    failed = True
                    self.errors.append('scan:' + str(exc))
                    write_json(round_dir / f'scan-{i}/failure.json', {'error': str(exc)})
            self.audit.append({'round': rd, 'scan_batches': len(requests), 'units': len(store.units), 'all_units_scheduled': True, 'chars': [len(encode_prompt(self.instructions, r)) for r in requests]})
            candidates = {**previous_candidates, **self.candidates(scans)}
            records, assessed_readings = ([], [])
            groups = self.normalize(candidates, round_dir / 'registry')
            for i, group in enumerate(groups):
                try:
                    record, reading = self.assess(store, current, group, candidates, round_dir / f'obligation-{i}')
                    records.append(record)
                    assessed_readings.append(reading)
                except (ValueError, OSError, RuntimeError) as exc:
                    self.errors.append('obligation:' + str(exc))
                    records.append({'status': 'unknown', 'member_ids': group['member_ids'], 'error': str(exc)})
            complete = False
            preliminary = aggregate(self.temporal, records, False)
            if preliminary not in ('needs_update', 'introduced') and scans:
                try:
                    evidence_records = [s['raw'] for s in scans] + self.facts + records
                    audit_request = dossier(store, current, self.instructions, self.pack_limit, evidence_records, {'joined_facts': self.facts, 'obligation_audit': records, 'task': 'Audit EVERY change and target foundation using the joined evidence (J4). Challenge both dismissals (J6) and retained old gaps (J1). Identify any distinct missed obligation of either class (D4, D5); out-of-scope items (D7) are not obligations. Return ordinary scope and candidates; do not trust prior conclusions.'}, store.units)
                    audit = self.review(store, current, audit_request, round_dir / 'scope_audit')
                    self.remember(audit['answer'])
                    self.final_citation_errors.extend(audit['citation_errors'])
                    checked = audit['checked']
                    complete = checked['status'] == 'no_gap' if self.temporal else checked['scope']['coverage_complete']
                    complete &= not audit['citation_errors'] and (not failed)
                    complete &= not current.get('pending_units') and (not current.get('preimage_errors'))
                    complete &= current.get('diff_coverage_complete', False)
                    added = {k: v for k, v in self.candidates([audit]).items() if k not in candidates}
                    if added:
                        all_candidates = {**candidates, **added}
                        regrouped = self.normalize(all_candidates, round_dir / 'audit_registry')
                        refreshed = []
                        for i, group in enumerate(regrouped):
                            if any((k in added for k in group['member_ids'])):
                                record, reading = self.assess(store, current, group, all_candidates, round_dir / f'audit_obligation-{i}')
                                refreshed.append(record)
                                assessed_readings.append(reading)
                            else:
                                members = set(group['member_ids'])
                                refreshed.extend((r for r in records if members & set(r.get('member_ids', []))))
                        records, candidates = (refreshed, all_candidates)
                except (ValueError, OSError, RuntimeError) as exc:
                    self.errors.append('scope_audit:' + str(exc))
                    complete = False
                    if self.temporal:
                        records.append({'status': 'unknown', 'obligation_key': 'failed_scope_audit'})
            if failed:
                records.append({'status': 'unknown', 'obligation_key': 'failed_scope_batch'})
            status = aggregate(self.temporal, records, complete)
            write_json(round_dir / 'obligation_ledger.json', {'obligations': records, 'scope_complete': bool(complete), 'status': status, 'context_facts': self.facts})
            if status != 'unknown' or rd + 1 == max_rounds or failed:
                break
            previous_candidates = candidates
            before = set(builder.blocks)
            packet = self.retrieve_once(packet, builder)
            if set(builder.blocks) == before:
                break
        result = {'status': status if self.temporal else 'not_requested', 'verdict': status if not self.temporal else 'not_requested', 'rounds': rd + 1, 'errors': list(dict.fromkeys(self.errors)), 'missing_information': list(dict.fromkeys(self.missing)), 'obligations': records, 'scope_complete': bool(complete), 'cost': self.budget.snapshot(), 'model_calls': self.client.calls, 'transport_batches': self.audit, 'citation_events': self.citation_events, 'final_citation_errors': self.final_citation_errors, 'preimage_errors': current.get('preimage_errors', []), 'retrieval_issues': builder.issues, 'function_units': len(builder.units), 'pending_units': sum((not u['complete'] for u in builder.units.values())), 'registry': self.registry_audit}
        write_json(self.output / 'final_packet.json', current)
        write_json(self.output / 'verification.json', result)
        return result

def analyze_ledger(input_root, output, config, client_factory=make_client):
    case = load_case(input_root)
    output.mkdir(parents=True, exist_ok=False)
    heads = {}
    for name, temporal in (('maintenance', False), ('temporal', True)):
        head = LedgerHead(case, output / name, config, temporal, client_factory)
        try:
            heads[name] = head.execute()
        except (ValueError, OSError, RuntimeError) as exc:
            heads[name] = {'status': 'unknown', 'verdict': 'unknown', 'errors': [str(exc)], 'missing_information': [], 'cost': head.budget.snapshot(), 'model_calls': head.client.calls, 'citation_events': head.citation_events, 'transport_batches': head.audit}
            write_json(output / name / 'verification.json', heads[name])
    maintenance, timing = (heads['maintenance']['verdict'], heads['temporal']['status'])
    result = {'prediction_schema': '20.0', 'engine': 'obligation_ledger_dual', 'sample_id': case.sample_id, 'input_hash': case.manifest['input_hash'], 'target': case.target, 'analysis_scope': 'change_related', 'function_reading': 'whole', 'protocol_hashes': protocol_hashes(config), 'verdict': maintenance, 'maintenance_verdict': maintenance, 'attribution_status': timing, 'introduced_by_this_change': True if timing == 'introduced' else False if timing == 'preexisting' else None, 'temporal_gap': timing in ('introduced', 'preexisting') if timing != 'unknown' else None, 'analysis_complete': maintenance != 'unknown', 'llm_used': True, 'dynamic_used': False, 'detection_reused': False, 'temporal_reused': False, 'whole_function_heads': heads, 'maintenance_cost': heads['maintenance']['cost'], 'temporal_cost': heads['temporal']['cost'], 'missing_information': heads['maintenance']['missing_information'], **combine({'verdict': maintenance}, {'status': timing})}
    if config['llm'].get('obligation_policy') == 'split_coverage_compatibility':
        result.update(prediction_schema='21.0', obligation_policy='split_coverage_compatibility')
    write_json(output / 'prediction.json', result)
    (output / 'report.md').write_text(f'# {case.sample_id}\n\n维护：{maintenance}\n\n归因：{timing}\n\n两个模块独立推理；逐义务身份、跨批次事实、原文引用及必要性检查见各模块目录。\n', encoding='utf-8')
    return result
