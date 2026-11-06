# Ground truth: C002

- Actual label: positive
- Criterion: VP4
- Mechanism: configuration_value_change
- Affected function/API/state: meshopt_encodeVertexVersion
- Counterfactual evidence: S1 changes the new vertex-codec version from 0xe to 1; H0 continues selecting 0xe and H1 selects 1 for the same fuzz-controlled branch.
