from __future__ import annotations
from pathlib import Path
from scheme_v8.llm.schema import QUOTES
from scheme_v8.llm.schema import TEXT
from scheme_v8.llm.schema import arr
from scheme_v8.llm.schema import obj
from scheme_v8.llm.schema import validate_schema
from scheme_v8.llm.verify import verify_quotes
from scheme_v8.llm.attribution.schema import CLAIM
from scheme_v8.llm.attribution.verify import verify_attribution
INDEPENDENT_CLAIM = obj({**CLAIM['properties'], 'change_ids': arr(TEXT)})
INDEPENDENT_SCHEMA = obj({'summary': TEXT, 'coverage_complete': {'type': 'boolean'}, 'coverage_evidence': QUOTES, 'claims': arr(INDEPENDENT_CLAIM), 'missing_information': arr(TEXT)})
PROMPT = (Path(__file__).parent / 'prompts/independent.txt').read_text(encoding='utf-8')

def verify_independent(response, packet):
    validate_schema(response, INDEPENDENT_SCHEMA)
    selected = set(packet['selected_change_ids'])
    claims = response['claims']
    ids = [c['claim_id'] for c in claims]
    if len(claims) > 10 and (not packet.get('obligation_batch_mode', False)) or len(ids) != len(set(ids)) or any((not c['change_ids'] or not set(c['change_ids']).issubset(selected) for c in claims)):
        return {'status': 'unknown', 'gap': None, 'introduced_by_this_change': None, 'claims': [], 'errors': ['invalid_independent_claims']}
    blocks = {e['evidence_id']: e for e in packet['evidence']}
    expected = [{'claim_id': c['claim_id'], 'change_ids': c['change_ids']} for c in claims]
    plain = {'summary': response['summary'], 'claims': [{k: v for k, v in c.items() if k != 'change_ids'} for c in claims]}
    checked = verify_attribution(plain, expected, blocks)
    statuses = [c['status'] for c in checked['claims']]
    errors = list(checked['errors'])
    if 'introduced' in statuses:
        status = 'introduced'
    elif 'preexisting' in statuses and all((s in ('preexisting', 'not_necessary') for s in statuses)):
        status = 'preexisting'
    elif all((s == 'not_necessary' for s in statuses)) and response['coverage_complete']:
        valid, kinds, issues = verify_quotes(response['coverage_evidence'], blocks, {'before_source', 'after_source', 'harness'})
        if valid and kinds == {'before_source', 'after_source', 'harness'}:
            status = 'no_gap'
        else:
            status = 'unknown'
            errors.extend(('coverage:' + issue for issue in issues or ['incomplete_side_or_harness_quotes']))
    else:
        status = 'unknown'
    return {'status': status, 'gap': status in ('introduced', 'preexisting') if status != 'unknown' else None, 'introduced_by_this_change': True if status == 'introduced' else False if status == 'preexisting' else None, 'claims': checked['claims'], 'errors': errors, 'missing_information': response['missing_information']}
