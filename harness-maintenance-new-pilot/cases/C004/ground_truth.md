# Ground truth: C004

- Actual label: positive
- Criterion: VP1
- Mechanism: source_layout_build_protocol
- Affected function/API/state: spng/spng.h include path
- Counterfactual evidence: S1 moves the installed header under spng/, invalidating H0's ../spng.h include; H1 changes it to ../spng/spng.h.
