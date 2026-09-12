# Ground truth: C050

- Actual label: positive
- Criterion: VP4
- Mechanism: new_configuration_behavior
- Affected function/API/state: SPNG_CRC_DISCARD ancillary CRC action
- Counterfactual evidence: S1 makes ancillary CRC discard a default behavior and adds undo paths; H0 always forces SPNG_CRC_USE, while H1 makes DISCARD fuzzer-selectable.
