# Ground truth: C061

- Actual label: positive
- Criterion: VP1
- Mechanism: api_signature_change
- Affected function/API/state: meshopt_encodeVertexBufferLevel
- Counterfactual evidence: S1 adds a version argument; H0 uses the old arity and H1 supplies -1 to both calls.
