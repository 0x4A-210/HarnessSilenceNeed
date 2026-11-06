# Ground truth: C054

- Actual label: positive
- Criterion: VP1
- Mechanism: source_layout_build_protocol
- Affected function/API/state: spng.h include path
- Counterfactual evidence: S1 moves production code out of src/, invalidating H0's ../src/spng.h include; H1 changes the include to ../spng.h.
