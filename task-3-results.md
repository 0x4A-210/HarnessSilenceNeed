# Task 3 result

Complete artifact: [`silent-harness-maintenance/`](silent-harness-maintenance/)

Primary report: [`silent-harness-maintenance/reports/blind_test_results.md`](silent-harness-maintenance/reports/blind_test_results.md)

Verdict: **NO-GO as a definitive unbiased main experiment**, although the
valid-set model result is quantitatively MODERATE-GO-level.

| Scope | Projects | Unique commits | Positive commits | Silent | VP1 | Negative |
|---|---:|---:|---:|---:|---:|---:|
| Original frozen set | 3 | 80 | 30 | 20 | 10 | 50 |
| Valid after 3 INVALID exclusions | 3 | 77 | 27 | 17 | 10 | 50 |

| Baseline | Explicit recall | Silent recall | FPR |
|---|---:|---:|---:|
| Build-Only | 100% | 0% | 0% |
| Gap-Only | 100% | 88.24% | 44% |
| Evolution-Aware | 100% | 82.35% | 0% |

The three post-freeze invalid cases are recorded without relabeling in
`silent-harness-maintenance/frozen-ground-truth/invalidations.csv`. Original
80-label metrics remain in `results/frozen_label_*`; validity-cleaned metrics
are the unprefixed result files. The artifact passes 566/566 integrity checks.
