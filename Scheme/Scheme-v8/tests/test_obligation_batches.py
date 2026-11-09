from copy import deepcopy
import pytest
from scheme_v8.llm.evidence_locations import EvidenceStore, location_schema
from scheme_v8.llm.obligation_packets import plan_packets, encode_prompt, intervals_complete
from scheme_v8.llm.attribution.verify import _grounded
from scheme_v8.llm.attribution.head import Head, aggregate
from scheme_v8.llm.schema import QUOTES, validate_schema
from scheme_v8.util import digest

def page(text, part=0, start=1, kind='harness', uid='file', **extra):
    return {'evidence_id': f'{kind}-{uid}-{part}', 'kind': kind, 'path': 'input/harness/fuzz.c' if kind == 'harness' else 'input/source/lib.c', 'text': text, 'unit_id': uid, 'part': part, 'start': start, 'end': start + len(text.splitlines()) - 1, 'sha256': digest(text.encode()), **extra}

def loc(uid, a=1, b=1, **extra):
    return {'unit_id': uid, 'start_line': a, 'end_line': b, 'role': 'primary', 'dependency_reason': '', **extra}

def test_cross_page_citation_extracts_original_text_and_hash():
    store = EvidenceStore({'evidence': [page('if (success()) {\n', start=250), page('  release();\n  goto cleanup;\n}\n', part=1, start=251)]})
    uid = next(iter(store.units))
    views = [store.view(uid, 250, 250), store.view(uid, 251, 253)]
    quote, block = store.resolve(loc(uid, 250, 253), views)
    assert quote['quote'] == 'if (success()) {\n  release();\n  goto cleanup;\n}\n'
    assert block['location']['quote_sha256'] == digest(quote['quote'].encode())
    with pytest.raises(ValueError, match='unprovided_lines'):
        store.resolve(loc(uid, 250, 253), views[:1])

@pytest.mark.parametrize('bad', [loc('missing'), loc('placeholder', 0), loc('placeholder', True), loc('placeholder', 2, 1)])
def test_invalid_addresses_are_rejected(bad):
    store = EvidenceStore({'evidence': [page('target_call();\n')]})
    uid = next(iter(store.units))
    if bad['unit_id'] == 'placeholder':
        bad['unit_id'] = uid
    with pytest.raises(ValueError):
        store.resolve(bad, [store.view(uid)])

def test_modified_content_cannot_reuse_old_hash():
    store = EvidenceStore({'evidence': [page('target_call();\n')]})
    uid = next(iter(store.units))
    view = store.view(uid)
    store.units[uid]['text'] = 'different_call();\n'
    with pytest.raises(ValueError, match='hash_mismatch'):
        store.resolve(loc(uid), [view])

def test_cross_version_citation_reports_pointer_and_actual_side():
    store = EvidenceStore({'evidence': [page('old_contract();\n', kind='before_source', change_ids=['g1'])]})
    uid = next(iter(store.units))
    raw = {'claims': [{'change_ids': ['g1'], 'after': {'source_evidence': [loc(uid)]}}]}
    result, _, errors, _ = store.materialize(raw, [store.view(uid)])
    assert errors[0]['pointer'] == '/claims/0/after/source_evidence/0'
    assert 'expected=after_source:actual=before_source' in errors[0]['reason']
    assert result['claims'][0]['after']['source_evidence'][0]['evidence_id'].startswith('INVALID:')

def test_cross_change_dependency_requires_grounded_primary_contract():
    store = EvidenceStore({'evidence': [page('release_pending_comment();\n', kind='before_source', uid='primary', change_ids=['g2']), page('produce_parser_error();\n', kind='before_source', uid='dependency', change_ids=['g1'])]})
    a, b = list(store.units)
    views = [store.view(a), store.view(b)]
    qa, ba = store.resolve(loc(a), views)
    qb, bb = store.resolve(loc(b, role='dependency', dependency_reason='The error producer reaches the cleanup contract through the same parser.'), views)
    blocks = {ba['evidence_id']: ba, bb['evidence_id']: bb}
    assert _grounded([qa, qb], blocks, 'before_source', {'g2'})
    assert not _grounded([qb], blocks, 'before_source', {'g2'})
    bb['citation_role'] = 'primary'
    assert not _grounded([qa, qb], blocks, 'before_source', {'g2'})

def test_wrong_id_relocation_is_unique_and_side_specific():
    store = EvidenceStore({'evidence': [page('unrelated_function();\n', uid='wrong', kind='before_source'), page('scrub_message(pkt, env);\n', uid='right', kind='before_source'), page('scrub_message(pkt, env);\n', uid='right', kind='after_source')]})
    found = store.locate_legacy({'evidence_id': 'before_source-wrong-0', 'quote': 'scrub_message(pkt, env);'}, 'before_source')
    assert store.units[found['unit_id']]['original_unit_id'] == 'right'
    assert store.units[found['unit_id']]['kind'] == 'before_source'

def test_lossless_large_unit_partition_respects_serialized_cap():
    code = 'int body() {\n' + '    meaningful_call(12345);\n' * 9000 + '}\n'
    store = EvidenceStore({'evidence': [page(code, kind='before_source', change_ids=['g1']), page(code.replace('12345', '54321'), kind='after_source', change_ids=['g1']), page('harness_entry();\n')]})
    instructions = 'Only the supplied evidence.' * 20
    batches = plan_packets(store, {'target': 'test', 'selected_change_ids': ['g1']}, instructions, max_chars=15000)
    assert len(batches) > 2
    assert all((len(encode_prompt(instructions, b)) <= 15000 for b in batches))
    views = [v for b in batches for v in b['evidence']]
    assert all((intervals_complete(views, u) for u in store.units.values()))

def test_no_truncation_when_seventeen_units_are_scheduled():
    store = EvidenceStore({'evidence': [page('contract_%d();\n' % i, uid=str(i), kind='source', change_ids=[f'g{i}']) for i in range(17)]})
    batches = plan_packets(store, {'selected_change_ids': [f'g{i}' for i in range(17)]}, 'review', max_chars=10000)
    assert {v['unit_id'] for b in batches for v in b['evidence']} == set(store.units)

def test_dependency_explanation_and_integer_types_are_enforced():
    store = EvidenceStore({'evidence': [page('contract_call();\n')]})
    uid = next(iter(store.units))
    with pytest.raises(ValueError, match='missing_dependency'):
        store.resolve(loc(uid, role='dependency'), [store.view(uid)])
    with pytest.raises(ValueError, match='integer'):
        validate_schema([loc(uid, 1.5)], location_schema(QUOTES))

def test_unresolved_new_candidate_prevents_preexisting_but_not_verified_introduced():
    assert aggregate(True, [{'status': 'preexisting'}, {'status': 'unknown'}], False) == 'unknown'
    assert aggregate(True, [{'status': 'introduced'}, {'status': 'unknown'}], False) == 'introduced'
    assert aggregate(False, [], False) == 'unknown'
    assert aggregate(False, [], True) == 'satisfied_in_scope'

def test_citation_repair_cannot_rewrite_valid_fields(tmp_path):
    store = EvidenceStore({'evidence': [page('contract_call();\n')]})
    uid = next(iter(store.units))
    raw = {'claims': [{'claim_id': 'frozen', 'harness_evidence': [loc('wrong'), loc(uid)]}]}
    original = deepcopy(raw)

    class Client:

        def __init__(self, *args):
            self.calls = []

        def infer(self, prompt, schema, output):
            return {'repairs': [{'pointer': '/claims/0/harness_evidence/0', 'replacement': loc(uid)}]}
    h = Head(None, tmp_path / 'head', {'whole_budget': {}, 'llm': {}}, True, Client)
    repaired = h.repair(raw, store, {'evidence': [store.view(uid)]}, tmp_path / 'head/stage')
    assert raw == original
    assert repaired['claims'][0]['claim_id'] == 'frozen'
    assert repaired['claims'][0]['harness_evidence'][1] == raw['claims'][0]['harness_evidence'][1]
    assert not store.materialize(repaired, [store.view(uid)])[2]
