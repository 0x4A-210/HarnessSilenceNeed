# Ground truth: C035

- Actual label: positive
- Criterion: VP3
- Mechanism: new_parser_entry_point
- Affected function/API/state: ares_set_servers_csv
- Counterfactual evidence: S1 adds URI parsing/writing behind ares_set_servers_csv; H0 only creates a DNS query name, while H1 initializes a channel and directly fuzzes the new CSV/URI entry path.
