from scheme_v8.llm.schema import validate_schema
from scheme_v8.llm.verify import verify_quotes
from scheme_v8.llm.attribution.schema import ATTRIBUTION_SCHEMA

def _grounded(quotes, blocks, kind, change_ids):
    if not quotes:
        return False
    valid, kinds, _ = verify_quotes(quotes, blocks, {kind})
    located = any((blocks.get(q['evidence_id'], {}).get('location') for q in quotes))
    if located:
        primary = [q for q in quotes if blocks.get(q['evidence_id'], {}).get('citation_role') == 'primary']
        dependencies_ok = all((blocks.get(q['evidence_id'], {}).get('citation_role') == 'primary' or (blocks.get(q['evidence_id'], {}).get('citation_role') == 'dependency' and len(blocks[q['evidence_id']].get('dependency_reason', '').strip()) >= 16) for q in quotes))
        if not primary or not dependencies_ok:
            return False
        quotes = primary
    return valid and kinds == {kind} and all((blocks[q['evidence_id']].get('change_id') in change_ids or bool(set(blocks[q['evidence_id']].get('change_ids', [])).intersection(change_ids)) or blocks[q['evidence_id']].get('invariant_source') is True for q in quotes))

def verify_attribution(response, claims, blocks):
    validate_schema(response, ATTRIBUTION_SCHEMA)
    expected = {claim['claim_id']: claim for claim in claims}
    ids = [item['claim_id'] for item in response['claims']]
    if len(ids) != len(set(ids)) or set(ids) != set(expected):
        return {'status': 'unknown', 'introduced_by_this_change': None, 'errors': ['incomplete_or_duplicate_claims'], 'claims': []}
    results, errors = ([], [])
    for item in response['claims']:
        claim_id = item['claim_id']
        ids_for_claim = set(expected[claim_id]['change_ids'])
        before, after = (item['before'], item['after'])
        issue = None
        if item['necessary'] == 'unknown':
            issue = 'necessity_not_established'
        elif len(item['necessity_reason'].strip()) < 20 or len(item['comparison_reason'].strip()) < 32:
            issue = 'insufficient_causal_explanation'
        elif not _grounded(before['source_evidence'], blocks, 'before_source', ids_for_claim):
            issue = 'missing_verified_before_source_quote'
        elif not _grounded(after['source_evidence'], blocks, 'after_source', ids_for_claim):
            issue = 'missing_verified_after_source_quote'
        else:
            target_ok, target_kinds, _ = verify_quotes(item['harness_evidence'], blocks, {'harness'})
            if not target_ok or target_kinds != {'harness'}:
                issue = 'missing_old_harness_quote'
            elif item['necessary'] == 'yes' and (not all((side['requirement'].strip() and len(side['reason'].strip()) >= 16 for side in (before, after)))):
                issue = 'incomplete_paired_assessment'
            elif item['necessary'] == 'yes' and any((side['applicability'] == 'not_applicable' and side['harness_status'] != 'not_applicable' or (side['applicability'] == 'required' and side['harness_status'] == 'not_applicable') for side in (before, after))):
                issue = 'inconsistent_applicability_and_status'
        status = 'not_necessary' if issue is None and item['necessary'] == 'no' else 'unknown'
        if issue is None and item['necessary'] == 'yes' and (after['applicability'] == 'required') and (after['harness_status'] == 'unsat'):
            if (before['applicability'] == 'not_applicable' and before['harness_status'] == 'not_applicable' or (before['applicability'] == 'required' and before['harness_status'] == 'sat')) and item['same_blocker'] != 'yes':
                status = 'introduced'
            elif before['applicability'] == 'required' and before['harness_status'] == 'unsat' and (item['same_blocker'] == 'yes'):
                status = 'preexisting'
        if issue:
            errors.append(claim_id + ':' + issue)
        results.append({'claim_id': claim_id, 'status': status, 'necessary': item['necessary'], 'before': before, 'after': after, 'same_blocker': item['same_blocker'], 'reason': item['comparison_reason'], 'error': issue, 'missing_information': item['missing_information']})
    classifications = {item['status'] for item in results if item['status'] != 'not_necessary'}
    overall = classifications.pop() if len(classifications) == 1 else 'unknown'
    return {'status': overall, 'introduced_by_this_change': True if overall == 'introduced' else False if overall == 'preexisting' else None, 'errors': errors, 'claims': results}
