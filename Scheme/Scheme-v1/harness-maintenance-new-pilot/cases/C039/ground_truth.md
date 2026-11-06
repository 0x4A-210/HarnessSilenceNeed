# Ground truth: C039

- Actual label: positive
- Criterion: VP1
- Mechanism: api_symbol_rename
- Affected function/API/state: meshopt_buildMeshletsSplit -> meshopt_buildMeshletsSpatial
- Counterfactual evidence: S1 removes/renames the entry point used by H0; H1 changes all six calls to meshopt_buildMeshletsSpatial.
