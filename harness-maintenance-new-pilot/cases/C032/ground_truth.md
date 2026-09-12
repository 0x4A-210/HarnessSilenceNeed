# Ground truth: C032

- Actual label: positive
- Criterion: VP1
- Mechanism: status_representation_change
- Affected function/API/state: wuffs_base__status const-char-pointer protocol
- Counterfactual evidence: S1 changes status from a struct to const char*; H0 accesses .code and H1 tests/returns the pointer.
