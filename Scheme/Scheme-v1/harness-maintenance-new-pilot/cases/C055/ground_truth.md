# Ground truth: C055

- Actual label: positive
- Criterion: VP1
- Mechanism: api_signature_change
- Affected function/API/state: fpixCopy; dpixCopy
- Counterfactual evidence: S1 removes the destination argument from fpixCopy/dpixCopy; H0 supplies two arguments throughout, while H1 updates those calls to the one-argument protocol.
