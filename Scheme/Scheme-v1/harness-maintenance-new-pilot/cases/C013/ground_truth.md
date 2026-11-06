# Audited ground truth: C013

- Initial label: positive
- Audited label: negative
- Audit status: RELABEL
- Evidence: S0+H0, S1+H0, and S1+H1 all compile. H0 supplies the required valid size/version constants, so the new status result is deterministically OK; H1 adds defensive handling but does not restore lost fuzz reach.
