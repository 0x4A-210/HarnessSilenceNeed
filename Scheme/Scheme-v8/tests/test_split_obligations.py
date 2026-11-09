from copy import deepcopy
import json
import pytest
from scheme_v8.util import PROJECT_ROOT, load_config
from scheme_v8.llm.schema import validate_schema
from scheme_v8.llm.evidence_locations import location_schema
from scheme_v8.llm.attribution import policy as split_policy
from scheme_v8.llm.attribution.head import aggregate
from scheme_v8.llm.attribution.maintenance import SCHEMA
from scheme_v8.llm.attribution.retrieval import TIME_SCHEMA
from scheme_v8.llm.attribution.pipeline import analyze_ledger, LedgerHead
from test_obligation_ledger import store_fixture, gate_fixture
from test_obligation_batches import loc

def coverage_gate(source, harness):
    gate = gate_fixture(source, harness)
    gate.update(obligation_class='target_coverage', scope_basis='target_api_or_format_contract', trigger_basis='supported_behavior_blocked_by_target', effect='blocked_target_coverage', coverage_witness={'supported_behavior': 'Decode a supported framed variant.', 'required_setup': 'Enable the variant in the decoder context.', 'actual_target_setup': 'The target always uses the default context.', 'blocked_behavior': 'The variant is rejected before its payload is decoded.', 'equivalent_routes': 'Input bytes cannot change the context flag; no helper sets it.'})
    return gate

def check_gate(gate, store):
    validate_schema(gate, location_schema(split_policy.GATE_SCHEMA))
    return split_policy.verify_gate(gate, store, {'evidence': [store.view(u) for u in store.units]}, 'one')

def test_supported_behavior_can_be_blocked_without_current_harness_trigger():
    store, source, harness = store_fixture()
    gate = coverage_gate(source, harness)
    result = check_gate(gate, store)
    assert result['decision'] == 'keep'
    assert result['answer']['effect'] == 'blocked_target_coverage'
    gate['obligation_class'] = 'execution_compatibility'
    assert check_gate(gate, store)['decision'] == 'uncertain'

@pytest.mark.parametrize('field,value', [('scope_basis', 'unrelated_library_capability'), ('scope_basis', 'unknown'), ('trigger_basis', 'impossible_library_state'), ('effect', 'optional_coverage'), ('effect', 'invalid_existing_assertion'), ('obligation_class', 'unknown')])
def test_coverage_category_does_not_bypass_scope_or_necessity(field, value):
    store, source, harness = store_fixture()
    gate = coverage_gate(source, harness)
    gate[field] = value
    assert check_gate(gate, store)['decision'] == 'uncertain'

def test_missing_evidence_or_witness_does_not_create_positive_or_negative():
    store, source, harness = store_fixture()
    gate = coverage_gate(source, harness)
    gate['coverage_witness']['equivalent_routes'] = ''
    assert check_gate(gate, store)['decision'] == 'uncertain'
    gate = coverage_gate(source, harness)
    gate['alternatives_ruled_out']['status'] = 'unknown'
    assert check_gate(gate, store)['decision'] == 'uncertain'
    gate['decision'] = 'dismiss'
    assert check_gate(gate, store)['decision'] == 'uncertain'
    gate['alternatives_ruled_out'].update(status='refuted', reason='The supplied helper already selects the same supported mode.')
    assert check_gate(gate, store)['decision'] == 'dismiss'
    assert aggregate(False, [{'status': 'dismissed'}], False) == 'unknown'
    assert aggregate(False, [{'status': 'dismissed'}], True) == 'satisfied_in_scope'

def test_classification_does_not_weaken_source_location_checks():
    store, source, harness = store_fixture()
    gate = coverage_gate(source, harness)
    gate['source_evidence'] = [loc('not_supplied')]
    assert check_gate(gate, store)['decision'] == 'uncertain'

def test_execution_compatibility_keeps_the_actual_execution_proof():
    store, source, harness = store_fixture()
    gate = coverage_gate(source, harness)
    gate.update(obligation_class='execution_compatibility', scope_basis='target_execution_contract', trigger_basis='current_target_execution', effect='invalid_execution')
    gate['coverage_witness'] = {k: '' for k in gate['coverage_witness']}
    assert check_gate(gate, store)['decision'] == 'keep'

@pytest.mark.parametrize('temporal', [False, True])
def test_focused_response_binds_only_program_owned_metadata(temporal):
    schema = location_schema(TIME_SCHEMA if temporal else SCHEMA)
    focused = split_policy.focused_schema(schema, temporal)
    key = 'claims' if temporal else 'blockers'
    id_field = 'claim_id' if temporal else 'id'
    assert key not in focused['properties']
    assert id_field not in focused['properties']['assessment']['properties']
    candidate = {id_field: 'frozen-operation', 'change_ids': ['g2', 'g4']}
    raw = {'assessment': {'requirement': 'Keep this exact semantic assessment', 'missing_information': ['Unresolved default']}}
    bound = split_policy.bind_assessment(raw, candidate, temporal)
    assert bound[key][0] == {**raw['assessment'], **candidate}
    assert 'assessment' in raw
    assert 'change_ids' in schema['properties'][key]['items']['properties']

def test_maintenance_and_timing_instructions_keep_distinct_responsibilities(tmp_path):

    class Client:

        def __init__(self, *args):
            self.calls = []
    config = {'whole_budget': {}, 'llm': {'obligation_policy': 'split_coverage_compatibility'}}
    m = LedgerHead(None, tmp_path / 'm', config, False, Client)
    t = LedgerHead(None, tmp_path / 't', config, True, Client)
    assert 'Do not require occurrence timing or before-side proof for maintenance' in m.instructions
    assert 'Compare the same frozen behavior on both source versions' in t.instructions
    assert 'compare both versions in THIS joined assessment' not in m.instructions

def test_split_pipeline_retains_grounded_coverage_with_bound_ids(make_input, tmp_path):
    from test_balanced import answer, blocker
    from test_attribution import _response
    root = make_input('int feature(){return 1;}\n', 'int feature(){return 2;}\n')
    config = load_config(PROJECT_ROOT / 'configs/default.yaml')
    config['llm']['whole_review_rounds'] = 1
    gates = []

    class Client:

        def __init__(self, *args):
            self.calls = []

        def infer(self, prompt, schema, output):
            p = json.loads(prompt.split('PACKET:\n')[1])

            def ref(kind):
                u = next((v for v in p['evidence'] if v['kind'] == kind and v['line_origin'] == 'file'))
                return loc(u['unit_id'], u['provided_start'], u['provided_end'])
            if 'decision' in schema['properties']:
                temporal = p['module'] == 'temporal'
                s, h = (ref('after_source' if temporal else 'source'), ref('harness'))
                g = coverage_gate(s['unit_id'], h['unit_id'])
                g.pop('candidate_id')
                for key in ('scope_contract', 'feasible_trigger', 'observable_consequence', 'alternatives_ruled_out', 'identity_preserved'):
                    g[key]['evidence'] = [s, h]
                g['source_evidence'], g['harness_evidence'] = ([s], [h])
                gates.append(temporal)
                return g
            temporal = 'claims' in schema['properties'] or 'summary' in schema['properties']
            if temporal:
                c = deepcopy(p.get('focus_candidate', _response()['claims'][0]))
                c['change_ids'] = p['selected_change_ids']
                c['before']['source_evidence'] = [ref('before_source')]
                c['after']['source_evidence'] = [ref('after_source')]
                c['harness_evidence'] = [ref('harness')]
                a = {'summary': 'Paired coverage', 'coverage_complete': False, 'coverage_evidence': [], 'claims': [c], 'missing_information': [], 'requested_symbols': [], 'requested_paths': []}
            else:
                a = answer()
                c = deepcopy(p.get('focus_candidate', blocker()))
                c.update(change_ids=p['selected_change_ids'], source_evidence=[ref('source')], harness_evidence=[ref('harness')])
                a['blockers'] = [c]
                a['scope'].update(all_relevant_changes_assessed=False, assessments=[])
                for v in a['scope']['foundation'].values():
                    v.update(status='unknown', evidence=[])
            if 'assessment' in schema['properties']:
                c = a.pop('claims' if temporal else 'blockers')[0]
                c.pop('claim_id' if temporal else 'id')
                c.pop('change_ids')
                a['assessment'] = c
            return a
    result = analyze_ledger(root, tmp_path / 'run', config, Client)
    assert result['maintenance_verdict'] == 'needs_update', result['whole_function_heads']['maintenance']
    assert result['attribution_status'] == 'introduced', result['whole_function_heads']['temporal']
    assert gates == [False, True]
    assert result['obligation_policy'] == 'split_coverage_compatibility'
    for head in result['whole_function_heads'].values():
        assert head['obligations'][0]['obligation_class'] == 'target_coverage'

@pytest.mark.parametrize('complete', [False, True])
def test_split_negative_still_requires_affirmative_scope_and_foundations(make_input, tmp_path, complete):
    from test_balanced import answer
    root = make_input('int feature(){return 1;}\n', 'int feature(){return 2;}\n')
    config = load_config(PROJECT_ROOT / 'configs/default.yaml')
    config['llm']['whole_review_rounds'] = 1

    class Client:

        def __init__(self, *args):
            self.calls = []

        def infer(self, prompt, schema, output):
            p = json.loads(prompt.split('PACKET:\n')[1])

            def refs(kind):
                return [loc(v['unit_id'], v['provided_start'], v['provided_end']) for v in p['evidence'] if v['kind'] == kind]
            if 'claims' in schema['properties']:
                return {'summary': 'All selected behavior already has a natural-input route.', 'coverage_complete': complete, 'coverage_evidence': refs('before_source') + refs('after_source') + refs('harness'), 'claims': [], 'missing_information': [] if complete else ['Unknown relevant default'], 'requested_symbols': [], 'requested_paths': []}
            a = answer()
            a['scope'].update(all_relevant_changes_assessed=complete, assessments=[{'change_id': cid, 'status': 'covered' if complete else 'unknown', 'reason': 'The primary target call and natural inputs reach the supported changed behavior.', 'source_evidence': refs('source'), 'harness_evidence': refs('harness')} for cid in p['selected_change_ids']], missing_information=[] if complete else ['Unknown relevant default'])
            for v in a['scope']['foundation'].values():
                v.update(status='pass' if complete else 'unknown', evidence=refs('source') + refs('harness'))
            return a
    result = analyze_ledger(root, tmp_path / 'run', config, Client)
    assert result['maintenance_verdict'] == ('satisfied_in_scope' if complete else 'unknown'), result
    assert result['attribution_status'] == ('no_gap' if complete else 'unknown'), result
