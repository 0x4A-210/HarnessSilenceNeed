# Ground truth: C025

- Actual label: positive
- Criterion: VP1
- Mechanism: argument_order_protocol
- Affected function/API/state: wuffs_gif__decoder__decode_frame
- Counterfactual evidence: S1 reorders decode_frame arguments; H0 retains the old typed ordering and H1 moves blend/disposal arguments before the reader/work buffer.
