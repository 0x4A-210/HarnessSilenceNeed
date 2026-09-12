# Go / No-Go decision

**Decision: NO-GO for scaling or treating this run as confirmatory evidence.**

The audited stable subset passes every numerical gate:

| Gate | Requirement | Audited result | Status |
|---|---|---:|---|
| G1 | Verified Positive ≥20 | 20 | Pass, exactly at boundary |
| G2 | Evolution-Aware recall ≥70% | 95.0% | Pass |
| G3 | FPR ≤10%, ideal ≤5% | 2.5% | Pass, ideal |
| G4 | FP falls without large recall loss | 28→1; recall −5 pp | Pass |
| G5 | TP reasoning mostly correct/grounded | 18/19 correct; 19/19 grounded | Pass |

However, the protocol-level gate fails. The pre-run set said 24 positive and 40
negative. A mandatory S0+H0/S1+H0/S1+H1 audit performed only after both blind
runs found:

- C030 and C040 were historical H0 build gaps, not commit-induced losses.
- C013 changed an error-return protocol but did not reduce the valid H0 decode
  path; H1 was defensive rather than restorative.
- C053 contained no production/library source change and was ineligible.
- C018, C034, and C047 could not be verified as negatives: each exposed a
  plausible new/change-specific gap, but lacked an H1 counterfactual repair.

Thus 3 cases were relabelled and 4 excluded after prediction. Reporting only the
cleaned 19/1/1/39 matrix as if it had been preregistered would be post-hoc label
selection. TEST.md explicitly makes unstable ground truth a NO-GO condition.

The result still says something useful: attribution is likely the right model
decomposition, because it removed 27/28 Gap-Only false positives in the stable
subset. A new formal run should freeze three-way validation before any model
call, exclude non-production paths in mining, and reserve an untouched test
split. The prompts and model settings need not change to test that claim.
