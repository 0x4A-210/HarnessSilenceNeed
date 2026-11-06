# Audited ground truth: C030

- Initial label: positive
- Audited label: negative
- Audit status: RELABEL
- Evidence: S0+H0 and S1+H0 both fail on the same missing spng_ctx_new(int flags) argument. The source diff only introduces an equivalent typedef; H1 repairs an already-existing harness build failure.
