from scheme_v8.llm.attribution.scope import verify_closure
from scheme_v8.llm.attribution.missing_context import choose_scope_requests
from scheme_v8.evaluation.metrics import maintenance_resolution

def _packet():
    return {'selected_change_ids': ['g0001'], 'prior_raw_verdict': 'unknown', 'evidence': [{'evidence_id': 'd', 'kind': 'diff', 'text': 'changed source behavior applies to parse(input);'}, {'evidence_id': 'h', 'kind': 'harness', 'text': 'parse(fuzz_bytes); if (error) return 0;'}]}

def _answer():
    quote_d = {'evidence_id': 'd', 'quote': 'changed source behavior applies to parse(input);'}
    quote_h = {'evidence_id': 'h', 'quote': 'parse(fuzz_bytes); if (error) return 0;'}
    return {'summary': 'The old target covers the change.', 'all_relevant_changes_assessed': True, 'assessments': [{'change_id': 'g0001', 'status': 'covered', 'reason': 'The old harness calls the changed parser with unrestricted fuzz bytes.', 'source_evidence': [quote_d], 'harness_evidence': [quote_h]}], 'foundation': {name: {'status': 'pass', 'reason': "The old target's supplied entry and build route supports this foundation.", 'evidence': [quote_h]} for name in ('build', 'input', 'lifecycle', 'control_flow')}, 'prior_alarm_resolution': '', 'missing_information': []}

def test_not_applicable_requires_grounding_and_unresolved_cannot_pass():
    response = _answer()
    response['foundation']['build'].update(status='not_applicable', reason='', evidence=[])
    assert verify_closure(response, _packet())['verdict'] == 'unknown'
    response = _answer()
    response['missing_information'] = ['Effective macro setting is absent']
    assert verify_closure(response, _packet())['verdict'] == 'unknown'
    response = _answer()
    response['assessments'].append(response['assessments'][0].copy())
    assert verify_closure(response, _packet())['verdict'] == 'unknown'

def test_missing_camel_case_contracts_take_priority_over_repeated_known_facts():
    missing = ['Missing xmlFuzzReadString and XMLDocument::~XMLDocument destruction.', 'Need xmlFuzzReadString and MY_CONFIG_FLAG.']
    reasons = ['known_entry calls known_entry and known_entry']
    assert choose_scope_requests(missing, reasons, 3) == ['xmlFuzzReadString', 'XMLDocument', 'MY_CONFIG_FLAG']

def test_unknown_negative_is_not_confirmed_and_false_satisfied_is_visible():
    rows = [{'truth': truth, 'maintenance_verdict': verdict} for truth, verdict in [('negative', 'unknown'), ('negative', 'satisfied_in_scope'), ('positive', 'satisfied_in_scope'), ('positive', 'needs_update')]]
    metrics = maintenance_resolution(rows)
    assert metrics['negative_confirmation_rate'] == 0.5
    assert metrics['satisfied_precision'] == 0.5
    assert metrics['strict_decision_accuracy'] == 0.5
    assert metrics['decided_rate'] == 0.75
