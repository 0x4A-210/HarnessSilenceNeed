# Candidate ground truth: P012

- Semantic label: RELATED
- Counterfactual status: PASS_VERIFIED_POSITIVE
- Verified maintenance positive: true
- Rationale: S1 adds URI parsing/writing behind ares_set_servers_csv; H0 only creates a DNS query name, while H1 initializes a channel and directly fuzzes the new CSV/URI entry path.
