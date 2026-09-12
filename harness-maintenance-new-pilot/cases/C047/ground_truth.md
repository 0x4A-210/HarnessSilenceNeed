# Audited ground truth: C047

- Initial label: negative
- Audited label: excluded
- Audit status: unverified_negative
- Evidence: S1 adds ares_expand_string_ex and H0 does not call it, while H1 does not expose it. This is a plausible commit-induced gap without the required H1 validation, so neither polarity is stable.
