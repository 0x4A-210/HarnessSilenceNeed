from __future__ import annotations
from scheme_v8.llm.schema import QUOTES
from scheme_v8.llm.schema import TEXT
from scheme_v8.llm.schema import arr
from scheme_v8.llm.schema import obj
from scheme_v8.llm.schema import validate_schema
from scheme_v8.llm.verify import verify_quotes
GROUP = obj({'change_id': TEXT, 'status': {'type': 'string', 'enum': ['covered', 'not_target_relevant', 'blocked', 'unknown']}, 'reason': TEXT, 'source_evidence': QUOTES, 'harness_evidence': QUOTES})
FOUNDATION = obj({'status': {'type': 'string', 'enum': ['pass', 'not_applicable', 'blocked', 'unknown']}, 'reason': TEXT, 'evidence': QUOTES})
SCHEMA = obj({'summary': TEXT, 'all_relevant_changes_assessed': {'type': 'boolean'}, 'assessments': arr(GROUP), 'foundation': obj({k: FOUNDATION for k in ('build', 'input', 'lifecycle', 'control_flow')}), 'prior_alarm_resolution': TEXT, 'missing_information': arr(TEXT)})

def verify_closure(answer, packet):
    validate_schema(answer, SCHEMA)
    selected = packet['selected_change_ids']
    errors = []
    ids = [item['change_id'] for item in answer['assessments']]
    if len(ids) != len(set(ids)) or set(ids) != set(selected):
        errors.append('missing_duplicate_or_extra_change_assessment')
    blocks = {e['evidence_id']: e for e in packet['evidence']}
    group_results = []
    for item in answer['assessments']:
        status = item['status']
        item_errors = []
        if status in ('covered', 'not_target_relevant'):
            if len(item['reason'].strip()) < 32:
                item_errors.append('short_reason')
            source_ok, _, source_issues = verify_quotes(item['source_evidence'], blocks, {'source', 'diff'})
            harness_ok, _, harness_issues = verify_quotes(item['harness_evidence'], blocks, {'harness'})
            if not source_ok:
                item_errors.extend(('source:' + issue for issue in source_issues))
            if not harness_ok:
                item_errors.extend(('harness:' + issue for issue in harness_issues))
        if item_errors:
            errors.extend((item['change_id'] + ':' + issue for issue in item_errors))
            status = 'unknown'
        group_results.append({'change_id': item['change_id'], 'status': status, 'reason': item['reason'], 'errors': item_errors})
    foundation = {}
    for name, item in answer['foundation'].items():
        status = item['status']
        item_errors = []
        if status in ('pass', 'not_applicable'):
            if len(item['reason'].strip()) < 32:
                item_errors.append('short_reason')
            valid, kinds, issues = verify_quotes(item['evidence'], blocks)
            if not valid or not kinds:
                item_errors.extend(issues or ['missing_evidence'])
            if name == 'build' and status == 'pass' and ('harness' not in kinds):
                item_errors.append('build_without_target_evidence')
        if item_errors:
            errors.extend((name + ':' + issue for issue in item_errors))
            status = 'unknown'
        foundation[name] = {'status': status, 'reason': item['reason'], 'errors': item_errors}
    if packet['prior_raw_verdict'] == 'needs_update' and len(answer['prior_alarm_resolution'].strip()) < 32:
        errors.append('prior_alert_not_resolved')
    complete = not errors and (not answer['missing_information']) and answer['all_relevant_changes_assessed'] and all((x['status'] in ('covered', 'not_target_relevant') for x in group_results)) and all((x['status'] in ('pass', 'not_applicable') for x in foundation.values()))
    return {'verdict': 'satisfied_in_scope' if complete else 'unknown', 'coverage_complete': complete, 'group_results': group_results, 'foundation': foundation, 'errors': errors, 'missing_information': answer['missing_information'], 'semantic_proof': False}
