# Ground truth: C029

- Actual label: positive
- Criterion: VP3
- Mechanism: new_parser_entry_point
- Affected function/API/state: ares_parse_uri_reply
- Counterfactual evidence: S1 adds the URI reply parser; H0 invokes the pre-existing reply parsers but not URI, while H1 adds ares_parse_uri_reply and cleanup.
