# Ground truth: C037

- Actual label: positive
- Criterion: VP1
- Mechanism: state_object_protocol_redesign
- Affected function/API/state: image_config; pixel_buffer; frame_config
- Counterfactual evidence: S1 replaces the image-buffer/config protocol with pixel_config, pixel_buffer, and frame_config; H0 uses removed fields/functions and H1 adopts the new state sequence.
