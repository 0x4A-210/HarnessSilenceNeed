# Audited ground truth: C040

- Initial label: positive
- Audited label: negative
- Audit status: RELABEL
- Evidence: S0+H0 already fails because including common.h as C++ defines uninitialized const arrays. S1+H0 adds a missing-declaration error, but adequacy was already at build failure; H1 repairs the historical build gap rather than a measurable S0-to-S1 loss.
