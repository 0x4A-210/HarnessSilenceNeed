import pytest
from scheme_v8.budget import Budget, BudgetExceeded
from scheme_v8.context.reader import Reader, load_case

def test_union_of_source_ranges_and_atomic_failure():
    budget = Budget({'max_files': 2, 'max_lines': 5})
    budget.charge('source', 1, 3)
    budget.charge('source', 2, 4)
    budget.charge('harness', 1, 1)
    assert budget.snapshot()['deep_unique_lines'] == 5
    with pytest.raises(BudgetExceeded, match='line_budget'):
        budget.charge('harness', 2, 2)
    with pytest.raises(BudgetExceeded, match='file_budget'):
        budget.charge('third', 1, 1)
    assert budget.snapshot()['deep_unique_lines'] == 5

def test_depth_time_and_llm_budget():
    now = [0]
    budget = Budget({'seconds': 3, 'max_depth': 1, 'max_llm_calls': 1}, clock=lambda: now[0])
    with pytest.raises(BudgetExceeded, match='depth'):
        budget.check(2)
    budget.charge_llm(10)
    with pytest.raises(BudgetExceeded, match='llm_calls'):
        budget.charge_llm(1)
    now[0] = 3
    with pytest.raises(BudgetExceeded, match='time'):
        budget.check()

def test_cache_does_not_double_charge_index_or_lines(make_input):
    root = make_input('int a;\n', 'int b;\n')
    reader = Reader(load_case(root), Budget())
    reader.snippet('input/source/lib.c', 1, 1, 'first')
    reader.snippet('input/source/lib.c', 1, 1, 'again')
    cost = reader.budget.snapshot()
    assert cost['indexed_files'] == 1
    assert cost['deep_unique_lines'] == 1
