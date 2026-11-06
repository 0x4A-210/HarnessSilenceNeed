# Candidate ground truth: P047

- Semantic label: RELATED
- Counterfactual status: PASS_VERIFIED_POSITIVE
- Verified maintenance positive: true
- Rationale: S1 changes status from a struct to const char*; H0 accesses .code and H1 tests/returns the pointer.
