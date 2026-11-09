from copy import deepcopy
import json

import pytest

from scheme_v8.util import PROJECT_ROOT, load_config
from scheme_v8.llm.backends import QuotaExhausted, TransientFailure, Retrying, classify_failure
from scheme_v8.llm.attribution.cascade import analyze_cascade
from test_attribution import _response
from test_balanced import answer, blocker
from test_obligation_batches import loc
from test_split_obligations import coverage_gate


class SessionClient:
    """Fake CLI backend: remembers what each conversation has seen."""

    provider = 'claude_cli'

    def __init__(self, behaviour, provider='claude_cli'):
        self.behaviour, self.provider = (behaviour, provider)
        self.calls, self.seen, self.last_session, self.trace = ([], {}, None, [])

    def close(self):
        pass

    def infer(self, prompt, schema, output, session=None, fork=False, persist=False):
        payload = json.loads(prompt.split('PACKET:\n')[1])
        if session is None:
            sid = f's{len(self.seen) + 1}'
            self.seen[sid] = []
        elif fork:
            sid = f's{len(self.seen) + 1}'
            self.seen[sid] = list(self.seen[session])
        else:
            sid = session
        self.seen[sid] = self.seen[sid] + payload.get('evidence', [])
        self.last_session = sid
        self.calls.append({'usage': {'input_tokens': len(prompt) // 4, 'cached_input_tokens': 0, 'output_tokens': 10},
                           'seconds': 1.0, 'session_in': session, 'fork': fork})
        kind = schema_kind(prompt)
        correction = prompt.startswith('OUTPUT CORRECTION')
        self.trace.append(('correction' if correction else kind, session, fork, sid))
        if correction:
            answer = self.last_answer
        else:
            answer = self.behaviour(kind, payload, self.seen[sid])
            self.last_answer = answer
        # `drop` simulates a malformed envelope: the requested section left null.
        dropped = (not correction or getattr(self, 'stubborn', False)) and getattr(self, 'drop', {}).pop(kind, False)
        return {'turn': kind, **{k: (answer if k == kind and not dropped else None) for k in ('part', 'discover', 'review', 'timing', 'repair')}}


def schema_kind(prompt):
    return prompt.split('set turn="', 1)[1].split('"', 1)[0]


def refs(views, kind):
    return [loc(v['unit_id'], v['provided_start'], v['provided_end']) for v in views if v['kind'] == kind]


def full_gate(views):
    s, h = (refs(views, 'source')[0], refs(views, 'harness')[0])
    gate = coverage_gate(s['unit_id'], h['unit_id'])
    for key in ('scope_contract', 'feasible_trigger', 'observable_consequence', 'alternatives_ruled_out', 'identity_preserved'):
        gate[key]['evidence'] = [s, h]
    gate['source_evidence'], gate['harness_evidence'] = ([s], [h])
    return gate


def closed_scope(payload, views, complete=True):
    scope = answer()['scope']
    scope.update(all_relevant_changes_assessed=complete, missing_information=[] if complete else ['Unknown default'],
                 assessments=[{'change_id': cid, 'status': 'covered' if complete else 'unknown',
                               'reason': 'The primary target call and natural inputs reach the changed behavior.',
                               'source_evidence': refs(views, 'source'), 'harness_evidence': refs(views, 'harness')}
                              for cid in payload['selected_change_ids']])
    for v in scope['foundation'].values():
        v.update(status='pass' if complete else 'unknown', evidence=refs(views, 'source') + refs(views, 'harness'))
    return scope


def config():
    c = load_config(PROJECT_ROOT / 'configs/default.yaml')
    assert c['llm']['engine'] == 'cascade_session'
    return c


def positive_behaviour(kind, payload, views):
    if kind == 'discover':
        a = answer()
        b = deepcopy(blocker())
        b.update(change_ids=payload['selected_change_ids'], source_evidence=refs(views, 'source'), harness_evidence=refs(views, 'harness'))
        a['blockers'] = [b]
        a['scope'].update(all_relevant_changes_assessed=False, assessments=[])
        for v in a['scope']['foundation'].values():
            v.update(status='unknown', evidence=[])
        return a
    if kind == 'review':
        gate = full_gate(views)
        decisions = [{**gate, 'candidate_id': c['candidate_id']} for c in payload['candidates']]
        return {'decisions': decisions, 'new_candidates': [], 'scope': closed_scope(payload, views, False), 'requested_symbols': [], 'requested_paths': []}
    if kind == 'timing':
        claims = []
        for o in payload['obligations_to_time']:
            c = deepcopy(_response()['claims'][0])
            c.update(claim_id=o['candidate_id'], change_ids=o['change_ids'])
            c['before']['source_evidence'] = refs(views, 'before_source')[:1]
            c['after']['source_evidence'] = refs(views, 'after_source')[:1]
            c['harness_evidence'] = refs(views, 'harness')[:1]
            claims.append(c)
        return {'summary': 'Paired', 'coverage_complete': False, 'coverage_evidence': [], 'claims': claims, 'missing_information': []}
    return {'received': True}


def test_positive_uses_three_turns_one_conversation_and_derives_timing(make_input, tmp_path):
    root = make_input('int feature(){return 1;}\n', 'int feature(){return 2;}\n')
    client = SessionClient(positive_behaviour)
    result = analyze_cascade(root, tmp_path / 'run', config(), lambda *a: client)
    assert result['maintenance_verdict'] == 'needs_update', result['whole_function_heads']['cascade']
    assert result['attribution_status'] == 'introduced', result['whole_function_heads']['cascade']
    assert result['joint_alarm'] and result['joint_origin'] == 'introduced'
    kinds = [t[0] for t in client.trace]
    assert kinds == ['discover', 'review', 'timing']
    # review is a fork of the discovery conversation; timing continues the review.
    (_, s0, f0, d), (_, s1, f1, r), (_, s2, f2, _) = client.trace
    assert s0 is None and s1 == d and f1 and r != d and s2 == r and not f2
    # later turns do not resend evidence that the conversation already holds
    sent = [json.loads(p.read_text())['evidence'] for p in sorted((tmp_path / 'run/cascade').glob('turn-*/request.json'))]
    first_ids = {v['unit_id'] for v in sent[0]}
    assert not first_ids & {v['unit_id'] for v in sent[1]}
    assert all(v['kind'] in ('before_source', 'after_source') for v in sent[2])
    assert result['cost']['llm_calls'] == 3


@pytest.mark.parametrize('complete', [False, True])
def test_negative_needs_affirmative_closure_and_skips_timing(make_input, tmp_path, complete):
    root = make_input('int feature(){return 1;}\n', 'int feature(){return 2;}\n')

    def behaviour(kind, payload, views):
        if kind == 'discover':
            a = answer()
            a['scope'] = closed_scope(payload, views, complete)
            return a
        if kind == 'review':
            return {'decisions': [], 'new_candidates': [], 'scope': closed_scope(payload, views, complete), 'requested_symbols': [], 'requested_paths': []}
        raise AssertionError('timing must not run for a negative')
    cfg = config()
    cfg['llm']['cascade_extra_rounds'] = 0
    client = SessionClient(behaviour)
    result = analyze_cascade(root, tmp_path / 'run', cfg, lambda *a: client)
    assert result['maintenance_verdict'] == ('satisfied_in_scope' if complete else 'unknown')
    assert result['attribution_status'] == 'not_applicable'
    assert not result['joint_alarm']
    assert [t[0] for t in client.trace] == ['discover', 'review']


def test_dismissal_without_scope_closure_is_not_negative(make_input, tmp_path):
    root = make_input('int feature(){return 1;}\n', 'int feature(){return 2;}\n')

    def behaviour(kind, payload, views):
        if kind == 'discover':
            return positive_behaviour(kind, payload, views)
        gate = full_gate(views)
        gate.update(decision='dismiss')
        gate['alternatives_ruled_out'].update(status='refuted', reason='A delegated helper already selects the same supported mode.')
        decisions = [{**gate, 'candidate_id': c['candidate_id']} for c in payload['candidates']]
        return {'decisions': decisions, 'new_candidates': [], 'scope': closed_scope(payload, views, False), 'requested_symbols': [], 'requested_paths': []}
    cfg = config()
    cfg['llm']['cascade_extra_rounds'] = 0
    result = analyze_cascade(root, tmp_path / 'run', cfg, lambda *a: SessionClient(behaviour))
    assert result['maintenance_verdict'] == 'unknown'


def test_codex_backend_resumes_instead_of_forking(make_input, tmp_path):
    root = make_input('int feature(){return 1;}\n', 'int feature(){return 2;}\n')
    client = SessionClient(positive_behaviour, provider='codex_cli')
    analyze_cascade(root, tmp_path / 'run', config(), lambda *a: client)
    sessions = {t[3] for t in client.trace}
    assert len(sessions) == 1 and not any(t[2] for t in client.trace)


def test_quota_exhaustion_propagates_instead_of_unknown(make_input, tmp_path):
    root = make_input('int feature(){return 1;}\n', 'int feature(){return 2;}\n')

    def behaviour(kind, payload, views):
        raise QuotaExhausted('usage limit')
    with pytest.raises(QuotaExhausted):
        analyze_cascade(root, tmp_path / 'run', config(), lambda *a: SessionClient(behaviour))


def test_failure_classification_and_transient_retry(tmp_path):
    assert classify_failure("ERROR: You’ve hit your usage limit. Visit ...") is QuotaExhausted
    assert classify_failure('Connection failed: error sending request') is TransientFailure
    assert classify_failure('tls handshake eof') is TransientFailure
    assert classify_failure('schema mismatch') not in (QuotaExhausted, TransientFailure)

    class Flaky:
        config = {'transient_retries': 2}

        class budget:
            @staticmethod
            def check():
                pass

        def __init__(self):
            self.n = 0

        def infer(self, prompt, schema, output, **kw):
            self.n += 1
            if self.n < 3:
                raise TransientFailure('connection failed')
            return {'ok': True}
    import scheme_v8.llm.backends as backends
    backends.time.sleep, original = (lambda s: None, backends.time.sleep)
    try:
        assert Retrying(Flaky()).infer('p', {}, tmp_path / 'x') == {'ok': True}
    finally:
        backends.time.sleep = original


def test_every_turn_sends_the_same_output_schema(make_input, tmp_path):
    root = make_input('int feature(){return 1;}\n', 'int feature(){return 2;}\n')
    schemas = []
    client = SessionClient(positive_behaviour)
    original = client.infer

    def recording(prompt, schema, output, **kw):
        schemas.append(json.dumps(schema, sort_keys=True))
        return original(prompt, schema, output, **kw)
    client.infer = recording
    analyze_cascade(root, tmp_path / 'run', config(), lambda *a: client)
    assert len(schemas) == 3 and len(set(schemas)) == 1


def test_codex_resume_usage_is_converted_from_thread_totals():
    from scheme_v8.llm.backends import CodexCLI
    from scheme_v8.budget import Budget
    backend = CodexCLI({'model': 'm'}, Budget({}))
    try:
        first = {'input_tokens': 43716, 'cached_input_tokens': 0, 'cache_write_input_tokens': 0, 'output_tokens': 19, 'reasoning_output_tokens': 0}
        second = {'input_tokens': 87477, 'cached_input_tokens': 43520, 'cache_write_input_tokens': 0, 'output_tokens': 44, 'reasoning_output_tokens': 0}
        u1 = backend.per_turn({'raw': first}, 't')
        u2 = backend.per_turn({'raw': second}, 't')
        assert (u1['input_tokens'], u1['cached_input_tokens'], u1['output_tokens']) == (43716, 0, 19)
        assert (u2['input_tokens'], u2['cached_input_tokens'], u2['output_tokens']) == (241, 43520, 25)
    finally:
        backend.close()


def evidence_starved_behaviour(review_new_candidates):
    """Discovery finds nothing; the review proposes a new obligation."""
    def behaviour(kind, payload, views):
        if kind == 'discover':
            a = answer()
            a['scope'].update(all_relevant_changes_assessed=False, assessments=[])
            for v in a['scope']['foundation'].values():
                v.update(status='unknown', evidence=[])
            return a
        if kind == 'review':
            gate = full_gate(views)
            decisions = [{**gate, 'candidate_id': c['candidate_id']} for c in payload['candidates']]
            new = []
            if not payload['candidates'] or review_new_candidates == 'always':
                b = deepcopy(blocker())
                b.update(change_ids=payload['selected_change_ids'], source_evidence=refs(views, 'source'), harness_evidence=refs(views, 'harness'))
                new = [b]
            return {'decisions': decisions, 'new_candidates': new, 'scope': closed_scope(payload, views, False),
                    'requested_symbols': [], 'requested_paths': []}
        return positive_behaviour(kind, payload, views)
    return behaviour


def test_obligation_first_seen_in_review_is_reviewed_and_can_alarm(make_input, tmp_path):
    root = make_input('int feature(){return 1;}\n', 'int feature(){return 2;}\n')
    client = SessionClient(evidence_starved_behaviour('once'))
    result = analyze_cascade(root, tmp_path / 'run', config(), lambda *a: client)
    assert [t[0] for t in client.trace] == ['discover', 'review', 'review', 'timing']
    head = result['whole_function_heads']['cascade']
    assert [c['origin'] for c in head['candidates']] == ['review-1']
    assert result['maintenance_verdict'] == 'needs_update' and result['attribution_status'] == 'introduced'


def test_unreviewed_new_candidate_blocks_both_alarm_and_negative(make_input, tmp_path):
    root = make_input('int feature(){return 1;}\n', 'int feature(){return 2;}\n')
    cfg = config()
    cfg['llm']['cascade_new_candidate_rounds'] = 0
    cfg['llm']['cascade_extra_rounds'] = 0
    result = analyze_cascade(root, tmp_path / 'run', cfg, lambda *a: SessionClient(evidence_starved_behaviour('once')))
    head = result['whole_function_heads']['cascade']
    assert result['maintenance_verdict'] == 'unknown'
    assert head['decisions'][-1]['errors'] == ['new_candidate_not_reviewed']


def bad_citation_behaviour(repair_mode):
    """Review cites a line range outside the unit; the repair turn fixes it."""
    state = {}

    def behaviour(kind, payload, views):
        if kind == 'review':
            out = positive_behaviour(kind, payload, views)
            good = out['decisions'][0]['feasible_trigger']['evidence'][0]
            state['good'] = good
            out['decisions'][0]['feasible_trigger']['evidence'][0] = {**good, 'start_line': 900, 'end_line': 905}
            return out
        if kind == 'repair':
            errors = payload['citation_errors']
            state['errors'] = errors
            repairs = [{'pointer': e['pointer'], 'replacement': state['good']} for e in errors]
            if repair_mode == 'sneaky':
                repairs.append({'pointer': '/decisions/0/decision', 'replacement': state['good']})
            return {'repairs': repairs}
        return positive_behaviour(kind, payload, views)
    return behaviour, state


@pytest.mark.parametrize('mode', ['honest', 'sneaky'])
def test_citation_repair_replaces_only_failed_locations(make_input, tmp_path, mode):
    root = make_input('int feature(){return 1;}\n', 'int feature(){return 2;}\n')
    behaviour, state = bad_citation_behaviour(mode)
    client = SessionClient(behaviour)
    result = analyze_cascade(root, tmp_path / 'run', config(), lambda *a: client)
    kinds = [t[0] for t in client.trace]
    assert kinds == ['discover', 'review', 'repair', 'timing']
    assert [e['pointer'] for e in state['errors']] == ['/decisions/0/feasible_trigger/evidence/0']
    # repair continues the review conversation
    assert client.trace[2][1] == client.trace[1][3]
    assert result['maintenance_verdict'] == 'needs_update'
    audit = json.loads(next((tmp_path / 'run/cascade').glob('turn-02-review/citation_repair.json')).read_text())
    assert audit['applied'] == ['/decisions/0/feasible_trigger/evidence/0'] and audit['remaining'] == []
    if mode == 'sneaky':
        assert audit['rejected'][0]['pointer'] == '/decisions/0/decision'


def test_no_repair_turn_without_citation_errors(make_input, tmp_path):
    root = make_input('int feature(){return 1;}\n', 'int feature(){return 2;}\n')
    client = SessionClient(positive_behaviour)
    analyze_cascade(root, tmp_path / 'run', config(), lambda *a: client)
    assert 'repair' not in [t[0] for t in client.trace]


@pytest.mark.parametrize('stubborn', [False, True])
def test_null_requested_section_gets_one_correction_turn(make_input, tmp_path, stubborn):
    root = make_input('int feature(){return 1;}\n', 'int feature(){return 2;}\n')
    client = SessionClient(positive_behaviour)
    client.drop = {'discover': True}
    client.stubborn = stubborn
    if stubborn:
        original = client.infer

        def always_drop(prompt, schema, output, **kw):
            client.drop['discover'] = True
            return original(prompt, schema, output, **kw)
        client.infer = always_drop
    result = analyze_cascade(root, tmp_path / 'run', config(), lambda *a: client)
    kinds = [t[0] for t in client.trace]
    assert kinds[:2] == ['discover', 'correction']
    assert client.trace[1][1] == client.trace[0][3]
    if stubborn:
        assert result['maintenance_verdict'] == 'unknown'
        assert 'session_envelope_mismatch' in result['whole_function_heads']['cascade']['errors'][0]
    else:
        assert result['maintenance_verdict'] == 'needs_update' and kinds[2:] == ['review', 'timing']


def test_session_schema_admits_at_most_one_answer_per_section():
    from scheme_v8.llm.attribution.cascade import SESSION_SCHEMA
    from scheme_v8.llm.schema import validate_schema
    for name, sub in SESSION_SCHEMA['properties'].items():
        if name != 'turn':
            assert sub['anyOf'][1] == {'type': 'null'} and sub['anyOf'][0]['type'] == 'object'
    envelope = {'turn': 'part', 'part': {'received': True}, 'discover': None, 'review': None, 'timing': None, 'repair': None}
    validate_schema(envelope, SESSION_SCHEMA)
    with pytest.raises(ValueError):
        validate_schema({**envelope, 'part': [{'received': True}, {'received': True}]}, SESSION_SCHEMA)


def test_safety_filter_refusal_is_its_own_failure_type():
    from scheme_v8.llm.backends import ContentFlagged
    assert classify_failure('This content was flagged for possible cybersecurity risk. If this seems wrong') is ContentFlagged


def test_timing_receives_pairs_of_unchanged_files_cited_by_kept_obligation(make_input, tmp_path):
    harness = ('int LLVMFuzzerTestOneInput(const unsigned char *data, unsigned long size) {\n'
               '    helper();\n    feature();\n    return 0;\n}\n')
    root = make_input('int feature(){return 1;}\n', 'int feature(){return 2;}\n', harness=harness,
                      extra={'input/source/helper.c': 'int helper(void){\n    return 7;\n}\n'})

    def behaviour(kind, payload, views):
        if kind == 'review':
            out = positive_behaviour(kind, payload, views)
            helper = [v for v in views if v['kind'] == 'source' and v['path'].endswith('helper.c')]
            assert helper, 'unchanged helper must be part of the evidence'
            ref = loc(helper[0]['unit_id'], helper[0]['provided_start'], helper[0]['provided_end'])
            for d in out['decisions']:
                for key in ('scope_contract', 'feasible_trigger', 'observable_consequence', 'alternatives_ruled_out', 'identity_preserved'):
                    d[key]['evidence'].append(ref)
            return out
        return positive_behaviour(kind, payload, views)
    analyze_cascade(root, tmp_path / 'run', config(), lambda *a: SessionClient(behaviour))
    timing = json.loads(next((tmp_path / 'run/cascade').glob('turn-*-timing/request.json')).read_text())
    helper_units = [v for v in timing['evidence'] if v['path'].endswith('helper.c')]
    assert {v['kind'] for v in helper_units} == {'before_source', 'after_source'}
    assert all(v['invariant_source'] for v in helper_units)


def test_timing_cannot_turn_a_kept_obligation_into_no_gap(make_input, tmp_path):
    root = make_input('int feature(){return 1;}\n', 'int feature(){return 2;}\n')

    def behaviour(kind, payload, views):
        out = positive_behaviour(kind, payload, views)
        if kind == 'timing':
            for c in out['claims']:
                c['necessary'] = 'no'
            out['coverage_complete'] = True
            out['coverage_evidence'] = refs(views, 'before_source')[:1] + refs(views, 'after_source')[:1] + refs(views, 'harness')[:1]
        return out
    result = analyze_cascade(root, tmp_path / 'run', config(), lambda *a: SessionClient(behaviour))
    assert result['maintenance_verdict'] == 'needs_update'
    assert result['attribution_status'] == 'unknown'

