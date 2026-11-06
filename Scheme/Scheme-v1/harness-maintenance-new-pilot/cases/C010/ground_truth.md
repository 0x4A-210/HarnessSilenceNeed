# Ground truth: C010

- Actual label: positive
- Criterion: VP1
- Mechanism: api_symbol_rename
- Affected function/API/state: ares__buf_* -> ares_buf_*
- Counterfactual evidence: S1 removes the ares__ buffer symbol family used by H0; H1 replaces every affected type and call with the new ares_buf family.
