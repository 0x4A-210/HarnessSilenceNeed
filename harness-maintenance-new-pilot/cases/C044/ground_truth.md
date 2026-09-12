# Ground truth: C044

- Actual label: positive
- Criterion: VP1
- Mechanism: work_buffer_protocol
- Affected function/API/state: decode_io_writer
- Counterfactual evidence: S1 adds a required work-buffer argument; H0 omits it and H1 allocates and passes a correctly sized slice.
