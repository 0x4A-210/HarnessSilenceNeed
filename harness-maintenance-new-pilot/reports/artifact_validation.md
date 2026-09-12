# Automated artifact validation

**Overall status: PASS**

- Passed checks: 53
- Failed checks: 0

## Passed

- required artifact files exist: 24/24
- TEST.md is the exact frozen task specification
- raw path-level hits: 119 (expected 119)
- screened candidates: 50 (expected 50)
- eligible candidates: 49 (expected 49)
- semantic screen rows: 50 (expected 50)
- initial positives: 24 (expected 24)
- initial negatives: 40 (expected 40)
- audited positives: 20 (expected 20)
- audited negatives: 40 (expected 40)
- ground-truth audit rows: 64 (expected 64)
- canonical coverage rows: 20 (expected 20)
- canonical reachability rows: 20 (expected 20)
- semantic label distribution: Counter({'RELATED': 30, 'UNRELATED': 13, 'UNCERTAIN': 7})
- Verified Positive criteria: Counter({'VP1': 15, 'VP4': 3, 'VP3': 2})
- positive project distribution: Counter({'wuffs': 9, 'meshoptimizer': 4, 'libspng': 3, 'c-ares': 3, 'leptonica': 1})
- audited evaluation project count: 10
- audited evaluation unique commit count: 60
- eligible co-evolution project count: 6
- initial label partition is complete and disjoint
- audited label partition is complete and disjoint
- three relabelled cases are explicit
- four excluded cases are explicit
- positive CSV matches audit ledger
- negative CSV matches audit ledger
- 64 anonymous case directories
- 50 candidate directories
- case materialization: 64/64 complete
- frozen blind-input hashes: 64/64
- blind-input leakage marker scan: none
- gap_only predictions: 64 unique complete cases
- gap_only exact input/output pairs: 64 unique complete cases
- gap_only input/output reconstruction: 64/64 exact
- gap_only one-shot run completion: 64 valid, 0 failed
- gap_only frozen model parameters
- gap_only prompt/schema hashes
- evolution_aware predictions: 64 unique complete cases
- evolution_aware exact input/output pairs: 64 unique complete cases
- evolution_aware input/output reconstruction: 64/64 exact
- evolution_aware one-shot run completion: 64 valid, 0 failed
- evolution_aware frozen model parameters
- evolution_aware prompt/schema hashes
- Evolution-Aware final-decision invariant: 64/64
- recomputed initial gap-only confusion matrix: {'TP': 23, 'FP': 29, 'FN': 1, 'TN': 11}
- recomputed initial evolution-aware confusion matrix: {'TP': 20, 'FP': 3, 'FN': 4, 'TN': 37}
- recomputed audited gap-only confusion matrix: {'TP': 20, 'FP': 28, 'FN': 0, 'TN': 12}
- recomputed audited evolution-aware confusion matrix: {'TP': 19, 'FP': 1, 'FN': 1, 'TN': 39}
- coverage table is honest and aligned: 20/20 explicitly NOT_MEASURED
- static exposure is not mislabeled as dynamic reachability
- VP1 three-way compile evidence: 15/15
- full Git commit identifiers: all commit and parent IDs are 40 hex characters
- commits resolve in local Git clones: 68/68 unique project/commit pairs
- CSV parent commits match Git first parents: 68/68

## Failed

- None.

## Interpretation notes

- Dynamic changed-code coverage was not measured; the artifact does not substitute the static exposure proxy.
- The audited 60-case scores are post-hoc sensitivity results because 7/64 labels changed or were excluded after prediction.
- Formal decision remains NO-GO despite passing the numerical gates.
