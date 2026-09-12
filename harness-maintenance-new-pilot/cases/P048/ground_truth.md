# Candidate ground truth: P048

- Semantic label: RELATED
- Counterfactual status: PASS_VERIFIED_POSITIVE
- Verified maintenance positive: true
- Rationale: S1 splits io_buffer fields into data and meta; H0 initializes/accesses removed flat fields and H1 constructs/accesses the nested layout.
