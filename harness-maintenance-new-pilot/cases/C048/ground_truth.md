# Ground truth: C048

- Actual label: positive
- Criterion: VP4
- Mechanism: argument_order_protocol
- Affected function/API/state: check_wuffs_version
- Counterfactual evidence: S1 swaps receiver-size and version arguments; H0 keeps the old order, while H1 supplies sizeof(dec) before WUFFS_VERSION for both targets.
