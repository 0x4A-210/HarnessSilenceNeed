from scheme_v8.budget import Budget
from scheme_v8.context.reader import Reader, load_case
from scheme_v8.llm.whole_functions import WholeFunctionBuilder, unit_errors
from scheme_v8.llm.attribution.retrieval import initial_packet
from scheme_v8.llm.attribution.paired_source import pair_packet

def builder(root, limit=200000):
    b = WholeFunctionBuilder(Reader(load_case(root), Budget({'max_lines': 10000})), {})
    b.limit = limit
    return b

def test_full_function_keeps_middle_and_reuses_overlapping_requests(make_input):
    code = 'int feature() {\n' + '  int x=0;\n' * 750 + '  MIDDLE_CONDITION();\n' + '  x++;\n' * 750 + '  return x;\n}\n'
    b = builder(make_input('int feature(){return 0;}\n', code))
    b.symbol('feature', 'return_contract', 'check whole function')
    records = list(b.units.values())
    assert len(records) == 1 and records[0]['complete']
    assert records[0]['end'] > 1500
    evidence_count = len(b.blocks)
    b.snippet('input/source/lib.c', 700, 800, 'overlapping call-site request')
    assert len(b.blocks) == evidence_count
    p = b.enrich_packet({})
    assert not unit_errors(p)
    assert 'MIDDLE_CONDITION();' in ''.join((e['text'] for e in p['evidence']))
    p['evidence'] = p['evidence'][:-1]
    assert unit_errors(p)

def test_unit_that_does_not_fit_is_pending_without_head_tail_partial(make_input):
    code = 'int feature() {\n' + '  do_something();\n' * 1000 + '}\n'
    b = builder(make_input('', code), 1000)
    b.symbol('feature', 'return_contract', 'read body')
    assert not b.blocks
    assert any((not u['complete'] for u in b.units.values()))
    assert unit_errors(b.enrich_packet({}))
    b.limit = 100000
    b.symbol('feature', 'return_contract', 'retry complete body')
    assert not unit_errors(b.enrich_packet({}))

def test_changed_function_preimage_keeps_middle_and_correct_side(make_input):
    before = 'int feature() {\n' + '  int x=0;\n' * 650 + '  old_requirement();\n' + '  x++;\n' * 400 + '}\n'
    after = before.replace('old_requirement', 'new_requirement')
    root = make_input(before, after)
    case = load_case(root)
    p, b = initial_packet(case, {'llm': {'balanced_packet_chars': 200000}}, Budget({'max_lines': 10000}))
    paired = pair_packet(b, p)
    assert not paired['preimage_errors']
    old = ''.join((e['text'] for e in paired['evidence'] if e['kind'] == 'before_source' and '-whole-' in e['evidence_id']))
    new = ''.join((e['text'] for e in paired['evidence'] if e['kind'] == 'after_source' and '-whole-' in e['evidence_id']))
    assert 'old_requirement();' in old and 'new_requirement();' not in old
    assert 'new_requirement();' in new and 'old_requirement();' not in new
    assert old.count('x++;') == 400

def test_qualified_operator_returns_whole_body(make_input):
    code = 'struct Value {\n bool operator==(const Value &x) const {\n' + '  check();\n' * 700 + '  return value == x.value;\n }\n};\n'
    b = builder(make_input('', code, filename='lib.hpp'))
    b.symbol('Value::operator==', 'return_contract', 'check actual equality')
    assert any((u['unit_kind'] == 'function' and u['end'] - u['start'] > 700 and u['complete'] for u in b.units.values()))
    assert not unit_errors(b.enrich_packet({}))

def test_added_function_absence_is_verified_in_preimage_file(make_input):
    root = make_input('int feature(){return 1;}\n', 'int feature(){return 1;}\nint new_api(){return 2;}\n')
    from scheme_v8.llm.diff_pages import install_pages
    b = builder(root)
    p = install_pages(b)
    b.symbol('new_api', 'return_contract', 'new function contract')
    p = b.enrich_packet(p)
    paired = pair_packet(b, p)
    assert not paired['preimage_errors']
    assert any(('no function definition named new_api' in e['text'] for e in paired['evidence'] if e['kind'] == 'before_source'))
