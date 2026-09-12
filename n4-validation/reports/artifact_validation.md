# Artifact Validation

Status: **PASS**

- PASS — all required artifact files exist
- PASS — candidate selection is exactly 20 N4 + 20 positive
- PASS — all 40 selected commits are unique
- PASS — all selected commits pass prior-data overlap audit
- PASS — all 40 pre-freeze audits and S0/S1 build-run pairs passed
- PASS — frozen labels still match their pre-prediction hash
- PASS — neutral label mapping contains C001-C040 exactly once
- PASS — exactly 40 frozen blind inputs exist
- PASS — every frozen input matches its manifest hash
- PASS — blind inputs contain no label or ground-truth marker
- PASS — frozen model/config and dataset hash are internally consistent
- PASS — all prompt/schema files match frozen hashes
- PASS — 80 predictions froze before label reveal
- PASS — gap_only predictions and input/output pairs match frozen hashes
- PASS — gap_only has 40 successful one-shot attempts and zero failures
- PASS — evolution_aware predictions and input/output pairs match frozen hashes
- PASS — evolution_aware has 40 successful one-shot attempts and zero failures
- PASS — four post-freeze errors are invalidated without relabel/replacement
- PASS — reported core metrics and NO-GO decision are internally consistent
- PASS — all-40 frozen-label sensitivity is present and reports 11/20 evolution FP
- PASS — all 40 emitted Evolution-Aware outputs obey the final conjunction rule

Manifest records 701 files.
