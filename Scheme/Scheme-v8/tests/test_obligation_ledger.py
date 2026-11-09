from copy import deepcopy
import json
import pytest
from scheme_v8.source_text import source_lines
from scheme_v8.util import PROJECT_ROOT, load_config
from scheme_v8.llm.evidence_locations import EvidenceStore
from scheme_v8.llm.obligation_ledger import check_registry, verified_facts, dossier, focused_ids
from scheme_v8.llm.obligation_packets import encode_prompt
from scheme_v8.llm.attribution.preimage import parse_file_patches, reverse_file
from scheme_v8.llm.attribution.patch_alignment import align_patch
from scheme_v8.llm.attribution.necessity_proof import verify_gate
from scheme_v8.llm.attribution.pipeline import LedgerHead, analyze_ledger
from test_obligation_batches import page, loc

def store_fixture():
    store = EvidenceStore({'evidence': [page('int operation() { return caller_helper(); }\n', kind='source', uid='source', change_ids=['g1']), page('int harness() { return operation(); }\n', kind='harness', uid='harness')]})
    source, harness = list(store.units)
    return (store, source, harness)

def gate_fixture(source, harness):
    proof = {'status': 'established', 'reason': 'The supplied source and target establish this concrete prerequisite.', 'evidence': [loc(source), loc(harness)]}
    return {'candidate_id': 'one', 'decision': 'keep', 'effect': 'invalid_execution', 'reason': 'Concrete target prerequisite fails in the supplied configuration.', 'finite_witness': 'A finite ordinary target call reaches this concrete invalid operation.', **{k: deepcopy(proof) for k in ('scope_contract', 'feasible_trigger', 'observable_consequence', 'alternatives_ruled_out', 'identity_preserved')}, 'source_evidence': [loc(source)], 'harness_evidence': [loc(harness)], 'missing_information': [], 'requested_symbols': [], 'requested_paths': []}

@pytest.mark.parametrize('effect', ['optional_coverage', 'speculative', 'unclear'])
def test_optional_or_speculative_gap_cannot_pass_keep(effect):
    store, source, harness = store_fixture()
    raw = gate_fixture(source, harness)
    raw['effect'] = effect
    result = verify_gate(raw, store, {'evidence': [store.view(u) for u in store.units]}, 'one')
    assert result['decision'] == 'uncertain'

@pytest.mark.parametrize('field', ['scope_contract', 'feasible_trigger', 'observable_consequence', 'alternatives_ruled_out', 'identity_preserved'])
def test_each_missing_necessity_premise_prevents_alarm(field):
    store, source, harness = store_fixture()
    raw = gate_fixture(source, harness)
    raw[field]['status'] = 'unknown'
    assert verify_gate(raw, store, {'evidence': [store.view(u) for u in store.units]}, 'one')['decision'] == 'uncertain'

def test_grounded_keep_and_refutation_are_distinct_from_absence_of_evidence():
    store, source, harness = store_fixture()
    raw = gate_fixture(source, harness)
    request = {'evidence': [store.view(u) for u in store.units]}
    assert verify_gate(raw, store, request, 'one')['decision'] == 'keep'
    raw['decision'] = 'dismiss'
    assert verify_gate(raw, store, request, 'one')['decision'] == 'uncertain'
    raw['scope_contract']['status'] = 'refuted'
    assert verify_gate(raw, store, request, 'one')['decision'] == 'dismiss'
    raw['candidate_id'] = 'substitute'
    assert verify_gate(raw, store, request, 'one')['decision'] == 'uncertain'

def test_joined_dossier_supplies_originals_from_both_continuations():
    store = EvidenceStore({'evidence': [page('before_condition();\n', kind='before_source', uid='p', change_ids=['g1']), page('after_condition();\n', kind='after_source', uid='p', change_ids=['g1']), page('old_harness_call();\n', kind='harness', uid='h')]})
    records = [{'evidence': [loc(uid)]} for uid in store.units]
    request = dossier(store, {'selected_change_ids': ['g1']}, 'instructions', 10000, records)
    assert {v['kind'] for v in request['evidence']} == {'before_source', 'after_source', 'harness'}
    assert not store.materialize({'records': records}, request['evidence'])[2]
    assert len(encode_prompt('instructions', request)) <= 10000

def test_join_refuses_to_drop_cited_originals_when_too_large():
    store = EvidenceStore({'evidence': [page('long_contract_statement();\n' * 1000, kind='source')]})
    uid = next(iter(store.units))
    with pytest.raises(ValueError, match='joined_proof_exceeds'):
        dossier(store, {'selected_change_ids': []}, 'proof', 1500, {'evidence': [loc(uid, 1, 1000)]})

def test_absence_fact_requires_whole_unit_read_not_catalog_entry():
    store = EvidenceStore({'evidence': [page('known_call();\nother_call();\n', kind='source')]})
    uid = next(iter(store.units))
    fact = {'topic': 'alternative', 'statement': 'No alternate route in this function.', 'evidence': [loc(uid)], 'absence_claim': True, 'audited_unit_ids': [uid]}
    raw = {'facts': [fact]}
    assert verified_facts(raw, store, {'evidence': [store.view(uid)]})[0]
    assert not verified_facts(raw, store, {'evidence': [store.view(uid, 1, 1)]})[0]

@pytest.mark.parametrize('members', [['a'], ['a', 'a', 'b'], ['a', 'b', 'invented']])
def test_registry_cannot_drop_duplicate_or_invent_candidates(members):
    raw = {'groups': [{'member_ids': members, **{k: 'same predicate' for k in ('operation', 'condition', 'capability', 'consequence', 'equivalence_reason')}}]}
    with pytest.raises(ValueError, match='partition'):
        check_registry(raw, {'a': {}, 'b': {}})

def test_dependency_closure_recomputes_second_level_and_counterpart():
    store = EvidenceStore({'evidence': [page('int root() { return helper(); }\n', uid='root', kind='after_source', change_ids=['g1']), page('int helper() { return config_gate(); }\n', uid='helper', kind='after_source'), page('int config_gate() { return 0; }\n', uid='gate', kind='after_source'), page('int config_gate() { return 1; }\n', uid='gate', kind='before_source')]})
    for u in store.units.values():
        u['name'] = {'root': 'root', 'helper': 'helper', 'gate': 'config_gate'}[u['original_unit_id']]
    assert set(focused_ids(store, {'change_ids': ['g1']})) == set(store.units)

def test_source_coordinates_and_quotes_preserve_formfeed():
    content = 'header\n\x0c\nint target(){ return 2; }\n'
    assert len(source_lines(content)) == 3
    assert ''.join(source_lines(content, keepends=True)) == content
    store = EvidenceStore({'evidence': [page(content, kind='source')]})
    uid = next(iter(store.units))
    quote, _ = store.resolve(loc(uid, 3, 3), [store.view(uid)])
    assert quote['quote'] == 'int target(){ return 2; }\n'

def patch_fixture():
    diff = 'diff --git a/a.c b/a.c\n--- a/a.c\n+++ b/a.c\n@@ -2,3 +2,3 @@\n context();\n-old_call();\n+new_call();\n tail();\n'
    return parse_file_patches(diff)['a.c']

def test_formfeed_reverse_patch_uses_diff_line_coordinates():
    patch = patch_fixture()
    post = '\x0c\ncontext();\nnew_call();\ntail();\n'
    assert reverse_file(post, patch) == '\x0c\ncontext();\nold_call();\ntail();\n'

def test_unambiguous_relocation_roundtrips_and_keeps_untouched_content():
    patch = patch_fixture()
    post = 'header\nextra\ncontext();\nnew_call();\ntail();\n'
    aligned, audit = align_patch(post, patch)
    assert audit['forward_roundtrip_verified']
    assert reverse_file(post, aligned) == post.replace('new_call', 'old_call')
    assert patch.hunks[0].new_start == 2

def test_preimage_rejects_semantic_difference_and_ambiguous_relocation():
    patch = patch_fixture()
    with pytest.raises(ValueError):
        align_patch('header\nextra\ncontext();\nwrong_call();\ntail();\n', patch)
    with pytest.raises(ValueError, match='not_unique'):
        align_patch('header\nextra\n' + 'context();\nnew_call();\ntail();\n' * 2, patch)

def test_two_heads_unknown_remains_unknown_and_no_cross_head_disclosure(make_input, tmp_path):
    from test_balanced import answer
    root = make_input('int feature(){return 1;}\n', 'int feature(){return 2;}\n')
    config = load_config(PROJECT_ROOT / 'configs/default.yaml')
    config['llm']['whole_review_rounds'] = 1

    class Client:

        def __init__(self, *args):
            self.calls = []

        def infer(self, prompt, schema, output):
            p = json.loads(prompt.split('PACKET:\n')[1])
            if 'claims' in schema['properties']:
                assert 'PRIVATE_MAINTENANCE' not in prompt
                return {'summary': 'unknown', 'coverage_complete': False, 'coverage_evidence': [], 'claims': [], 'missing_information': [], 'requested_symbols': [], 'requested_paths': []}
            a = answer()
            a['scope'].update(summary='PRIVATE_MAINTENANCE', all_relevant_changes_assessed=False, assessments=[{'change_id': g, 'status': 'unknown', 'reason': 'Need source', 'source_evidence': [], 'harness_evidence': []} for g in p['selected_change_ids']])
            for v in a['scope']['foundation'].values():
                v.update(status='unknown', evidence=[])
            return a
    result = analyze_ledger(root, tmp_path / 'run', config, Client)
    assert result['maintenance_verdict'] == result['attribution_status'] == 'unknown'
    assert not result['detection_reused'] and (not result['temporal_reused'])

def test_cached_reader_still_enforces_allowlist(make_input, monkeypatch):
    from scheme_v8.context.reader import Reader, load_case, InputViolation
    from scheme_v8.budget import Budget
    root = make_input('int feature(){return 1;}\n', 'int feature(){return 2;}\n')
    reader = Reader(load_case(root), Budget())
    name = next((p for p in reader.case.manifest['files'] if p.startswith('input/source/')))
    data = reader.index(name)
    monkeypatch.setattr(reader, 'path', lambda _: pytest.fail('Cached bytes should not traverse files again'))
    assert reader.index(name) == data
    with pytest.raises(InputViolation):
        reader.index('outside/secret')

@pytest.mark.parametrize('field', ['facts', 'scope_contract', 'source_evidence'])
def test_repair_receives_exact_frozen_fact_or_gate_claim(field, tmp_path):
    store, source, harness = store_fixture()
    context = 'This exact statement must accompany the failed citation location.'
    if field == 'facts':
        raw = {'facts': [{'statement': context, 'evidence': [loc('missing')]}]}
        pointer, lookup = ('/facts/0/evidence/0', '/facts/0')
    elif field == 'scope_contract':
        raw = {'scope_contract': {'status': 'established', 'reason': context, 'evidence': [loc('missing')]}}
        pointer, lookup = ('/scope_contract/evidence/0', '/scope_contract')
    else:
        raw = {'candidate_id': 'frozen-one', 'reason': context, 'source_evidence': [loc('missing')]}
        pointer, lookup = ('/source_evidence/0', 'scope')
    original = deepcopy(raw)

    class Client:

        def __init__(self, *args):
            self.calls = []

        def infer(self, prompt, schema, output):
            p = json.loads(prompt.split('PACKET:\n')[1])
            assert context in json.dumps(p['frozen_context'][lookup])
            return {'repairs': [{'pointer': pointer, 'replacement': loc(source)}]}
    head = LedgerHead(None, tmp_path / 'head', {'whole_budget': {}, 'llm': {}}, False, Client)
    repaired = head.repair(raw, store, {'evidence': [store.view(source), store.view(harness)]}, tmp_path / 'head/repair')
    assert raw == original
    assert not store.materialize(repaired, [store.view(source), store.view(harness)])[2]
