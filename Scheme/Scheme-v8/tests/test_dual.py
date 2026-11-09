from copy import deepcopy
from scheme_v8.evaluation.metrics import three_matrices, three_metrics
from scheme_v8.llm.attribution.combine import combine
from scheme_v8.llm.attribution.temporal import verify_independent
from scheme_v8.llm.attribution.paths import _resolve_path

def _row(truth, origin, maintenance, timing, kind='api', visibility='explicit'):
    temporal_alarm = timing in ('introduced', 'preexisting')
    joint_alarm = maintenance or temporal_alarm
    return {'truth': truth, 'truth_introduced_by_this_change': origin, 'maintenance_alarm': maintenance, 'temporal_status': timing, 'joint_alarm': joint_alarm, 'joint_origin': timing if temporal_alarm else 'unknown' if maintenance else 'not_applicable', 'degradation_type': kind, 'need_visibility': visibility}

def test_independent_timing_can_rescue_maintenance_no_alarm():
    result = combine({'verdict': 'unknown'}, {'status': 'introduced'})
    assert result == {'maintenance_alarm': False, 'temporal_gap_alarm': True, 'joint_alarm': True, 'joint_origin': 'introduced'}
    satisfied = combine({'verdict': 'satisfied_in_scope'}, {'status': 'introduced'})
    assert satisfied['temporal_gap_alarm'] and (not satisfied['joint_alarm'])
    assert satisfied['joint_origin'] == 'not_applicable'

def test_missing_helper_path_resolves_within_allowlist():
    files = {'input/source/tests/fuzz/zstd_helpers.h': {}, 'input/source/lib/zstd.h': {}, 'input/harness/build.sh': {}}
    assert _resolve_path('tests/fuzz/zstd_helpers.h', files) == 'input/source/tests/fuzz/zstd_helpers.h'
    assert _resolve_path('not_exported.h', files) is None

def test_three_metrics_keep_time_truth_separate_from_negative_samples():
    rows = [_row('positive', True, False, 'introduced'), _row('positive', False, True, 'unknown'), _row('negative', None, False, 'unknown'), _row('negative', None, False, 'introduced')]
    result = three_metrics(rows)
    assert result['maintenance']['tp'] == 1
    assert result['maintenance']['fp'] == 0
    assert result['temporal']['accuracy'] == 0.5
    assert result['temporal']['false_positive_rate'] == 0
    assert result['temporal']['unresolved_preexisting'] == 1
    assert result['temporal']['false_gap_alarms_on_negatives'] == 1
    assert result['joint']['tp'] == 1
    assert result['joint']['fp'] == 1
    assert result['joint']['fn'] == 1
    tables = three_matrices(rows)
    assert tables['temporal']['api']['阳-显-本次']['correct'] == 1
    assert tables['joint']['合计']['阴-显']['false_alarms'] == 1

def test_independent_verifier_requires_side_specific_quotes():
    from test_attribution import _response
    claim = deepcopy(_response()['claims'][0])
    claim['change_ids'] = ['g0001']
    packet = {'selected_change_ids': ['g0001'], 'evidence': [{'evidence_id': 'before-g0001', 'kind': 'before_source', 'change_id': 'g0001', 'text': 'if (flags & 1) return 0;'}, {'evidence_id': 'after-g0001', 'kind': 'after_source', 'change_id': 'g0001', 'text': 'if (flags & 2) return 0;'}, {'evidence_id': 'h', 'kind': 'harness', 'text': 'target_function(1); return 0;'}]}
    answer = {'summary': 'independent', 'coverage_complete': False, 'coverage_evidence': [], 'claims': [claim], 'missing_information': []}
    assert verify_independent(answer, packet)['status'] == 'introduced'
    answer['claims'][0]['before']['source_evidence'][0]['evidence_id'] = 'after-g0001'
    assert verify_independent(answer, packet)['status'] == 'unknown'
