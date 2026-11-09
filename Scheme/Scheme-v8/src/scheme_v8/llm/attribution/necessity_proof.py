from scheme_v8.llm.schema import TEXT
from scheme_v8.llm.schema import QUOTES
from scheme_v8.llm.schema import arr
from scheme_v8.llm.schema import obj
from scheme_v8.llm.verify import verify_quotes
from scheme_v8.llm.attribution.spec import POLICY as SPEC_POLICY
from scheme_v8.llm.attribution.spec import render
POLICY = SPEC_POLICY
CHECK = obj({'status': {'type': 'string', 'enum': ['established', 'refuted', 'unknown']}, 'reason': TEXT, 'evidence': QUOTES})
GATE_SCHEMA = obj({'candidate_id': TEXT, 'decision': {'type': 'string', 'enum': ['keep', 'dismiss', 'uncertain']}, 'effect': {'type': 'string', 'enum': ['invalid_execution', 'invalid_existing_assertion', 'lost_supported_behavior', 'build_blocker', 'optional_coverage', 'speculative', 'unclear']}, 'reason': TEXT, 'finite_witness': TEXT, 'scope_contract': CHECK, 'feasible_trigger': CHECK, 'observable_consequence': CHECK, 'alternatives_ruled_out': CHECK, 'identity_preserved': CHECK, 'source_evidence': QUOTES, 'harness_evidence': QUOTES, 'missing_information': arr(TEXT), 'requested_symbols': arr(TEXT), 'requested_paths': arr(TEXT)})
GATE_PROMPT = 'Independently audit ONLY the supplied frozen obligation.\n' + render('PROT-HYP', 'E1') + POLICY + '\nReturn the five checks of J1 (scope_contract, feasible_trigger, observable_consequence, alternatives_ruled_out, identity_preserved), each with a specific reason and exact evidence. keep requires all five established; dismiss requires a grounded refutation (J6); otherwise uncertain.\n'

def verify_gate(raw, store, request, candidate_id):
    answer, cites, errors, ledger = store.materialize(raw, request['evidence'])
    blocks = {b['evidence_id']: b for b in cites}
    issues = [e['reason'] for e in errors]
    if answer['candidate_id'] != candidate_id:
        issues.append('gate_candidate_identity_changed')
    checks = [answer[k] for k in ('scope_contract', 'feasible_trigger', 'observable_consequence', 'alternatives_ruled_out', 'identity_preserved')]
    grounded = []
    for check in checks:
        valid, _, _ = verify_quotes(check['evidence'], blocks)
        grounded.append(valid and len(check['reason'].strip()) >= 24)
    source_ok, _, _ = verify_quotes(answer['source_evidence'], blocks, {'source', 'diff', 'before_source', 'after_source'})
    harness_ok, _, _ = verify_quotes(answer['harness_evidence'], blocks, {'harness'})
    decision = answer['decision']
    if decision == 'keep' and (not (all(grounded) and all((c['status'] == 'established' for c in checks)) and source_ok and harness_ok and (not answer['missing_information']) and (answer['effect'] in {'invalid_execution', 'invalid_existing_assertion', 'lost_supported_behavior', 'build_blocker'}) and (len(answer['finite_witness'].strip()) >= 32))):
        decision = 'uncertain'
        issues.append('necessary_maintenance_premises_not_established')
    if decision == 'dismiss' and (not (source_ok and harness_ok and any((c['status'] == 'refuted' and ok for c, ok in zip(checks[:4], grounded[:4]))))):
        decision = 'uncertain'
        issues.append('dismissal_has_no_grounded_refutation')
    if answer['candidate_id'] != candidate_id or answer['identity_preserved']['status'] != 'established' or (not grounded[-1]) or errors:
        decision = 'uncertain'
    return {'decision': decision, 'errors': issues, 'answer': answer, 'citation_errors': errors, 'citations': ledger}
