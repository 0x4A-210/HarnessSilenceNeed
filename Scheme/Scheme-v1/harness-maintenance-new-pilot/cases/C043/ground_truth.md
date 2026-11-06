# Ground truth: C043

- Actual label: positive
- Criterion: VP1
- Mechanism: work_buffer_protocol
- Affected function/API/state: wuffs_gif__decoder__decode_frame
- Counterfactual evidence: S1 adds a work-buffer argument to decode_frame; H0 omits it and H1 supplies an empty slice.
