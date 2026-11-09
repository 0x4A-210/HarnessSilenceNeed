from scheme_v8.llm.attribution.maintenance import verify_balanced
from test_scope_closure import _answer, _packet

def packet():
    return {**_packet(), 'omitted_change_group_count': 0, 'truncated_change_ids': [], 'harness_complete_files': {'input/harness/fuzz.c': True}}

def answer():
    return {'scope': _answer(), 'blockers': [], 'assumptions': [], 'requested_symbols': [], 'requested_paths': []}

def blocker():
    p = packet()
    return {'id': 'b1', 'change_ids': ['g0001'], 'kind': 'input', 'necessary': True, 'established': True, 'requirement': 'The API requires an extent within the provided allocation.', 'target_route': 'The target passes fuzz bytes and a length into the changed parser.', 'failure_condition': 'The target-provided extent exceeds the actual input allocation.', 'alternative_paths': 'The complete old target uses the same invalid extent on every call.', 'source_evidence': [{'evidence_id': 'd', 'quote': p['evidence'][0]['text']}], 'harness_evidence': [{'evidence_id': 'h', 'quote': p['evidence'][1]['text']}], 'missing_information': []}

def test_concrete_blocker_is_not_vetoed_by_unrelated_missing_scope():
    a, p = (answer(), packet())
    a['blockers'] = [blocker()]
    a['scope']['missing_information'] = ['Unrelated build group remains unresolved']
    p['omitted_change_group_count'] = 1
    assert verify_balanced(a, p)['verdict'] == 'needs_update'

def test_unknown_scope_or_truncated_diff_cannot_certify_negative():
    p = packet()
    assert verify_balanced(answer(), p)['verdict'] == 'satisfied_in_scope'
    p['truncated_change_ids'] = ['g0001']
    assert verify_balanced(answer(), p)['verdict'] == 'unknown'

def test_hypothetical_and_ungrounded_blockers_do_not_create_alerts_or_normality():
    a = answer()
    a['blockers'] = [blocker()]
    a['blockers'][0]['missing_information'] = ['Actual input extent unknown']
    assert verify_balanced(a, packet())['verdict'] == 'unknown'
    a['blockers'][0]['missing_information'] = []
    a['blockers'][0]['harness_evidence'][0]['quote'] = 'invented call'
    assert verify_balanced(a, packet())['verdict'] == 'unknown'

def test_paired_source_quotes_need_current_side_and_can_keep_before_context():
    p, a = (packet(), answer())
    p['evidence'] += [{'evidence_id': 'before', 'kind': 'before_source', 'text': 'old supported behavior was enabled'}, {'evidence_id': 'after', 'kind': 'after_source', 'text': 'new supported behavior requires an option'}]
    b = blocker()
    b['source_evidence'] = [{'evidence_id': 'before', 'quote': 'old supported behavior was enabled'}, {'evidence_id': 'after', 'quote': 'new supported behavior requires an option'}]
    a['blockers'] = [b]
    assert verify_balanced(a, p)['verdict'] == 'needs_update'
    b['source_evidence'] = b['source_evidence'][:1]
    assert verify_balanced(a, p)['verdict'] == 'unknown'

def test_preexisting_foundation_blocker_does_not_need_fabricated_diff_anchor():
    p, a = (packet(), answer())
    b = blocker()
    b.update(kind='call', change_ids=[])
    a['blockers'] = [b]
    assert verify_balanced(a, p)['verdict'] == 'unknown'
    a['scope']['foundation']['control_flow'].update(status='blocked', evidence=b['harness_evidence'])
    assert verify_balanced(a, p)['verdict'] == 'needs_update'
    a['scope']['foundation']['control_flow']['evidence'] = []
    assert verify_balanced(a, p)['verdict'] == 'unknown'
