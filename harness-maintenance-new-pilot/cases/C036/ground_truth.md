# Ground truth: C036

- Actual label: positive
- Criterion: VP1
- Mechanism: api_signature_change
- Affected function/API/state: meshopt_buildMeshletsSplit
- Counterfactual evidence: S1 adds a fill-weight argument; each H0 call has the old arity and H1 supplies 0.f.
