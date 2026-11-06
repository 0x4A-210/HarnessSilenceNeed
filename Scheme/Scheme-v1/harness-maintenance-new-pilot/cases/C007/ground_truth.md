# Ground truth: C007

- Actual label: positive
- Criterion: VP1
- Mechanism: status_type_removal
- Affected function/API/state: wuffs_foo__status -> wuffs_base__status
- Counterfactual evidence: S1 removes codec-specific status types still declared by H0; H1 uses wuffs_base__status.
