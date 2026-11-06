# Ground truth: C023

- Actual label: positive
- Criterion: VP1
- Mechanism: state_layout_change
- Affected function/API/state: wuffs_base__io_buffer data/meta
- Counterfactual evidence: S1 splits io_buffer fields into data and meta; H0 initializes/accesses removed flat fields and H1 constructs/accesses the nested layout.
