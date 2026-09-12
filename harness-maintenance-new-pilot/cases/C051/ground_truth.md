# Ground truth: C051

- Actual label: positive
- Criterion: VP1
- Mechanism: status_representation_change
- Affected function/API/state: wuffs_base__status.code
- Counterfactual evidence: S1 changes status from an integer to a struct; H0 uses scalar tests/comparisons and H1 accesses .code.
