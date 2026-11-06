# Task 7 — Automatic Target Discovery + Reachability Kill Test

Status: **complete, outcome = CONTINUE (not KILL; not MAJOR WEAKENING).**

This is a diagnostic kill test on the 39 previously audited Task-5/Task-6
cases: 20 commit-induced positives and 19 N4 existing gaps from four projects
(c-ares 10, libplist 10, libspng 10, meshoptimizer 9). It is not an independent
unbiased main experiment because these cases participated in method development.

## Headline comparison

| Method | Positive recall, complete-case | Positive recall, ITT | N4 FPR | Applicability | Strict attribution, representable cases |
|---|---:|---:|---:|---:|---:|
| M0 Exact-Target Reachability (oracle) | 19/19 = 100% | 19/20 = 95% | 0/19 = 0% | 38/39 = 97.44% | 38/38 = 100% |
| M1 Top-1 | 16/17 = 94.12% | 16/20 = 80% | 1/19 = 5.26% | 36/39 = 92.31% | 19/38 = 50% |
| M1 Top-3 | 19/19 = 100% | 19/20 = 95% | 2/19 = 10.53% | 38/39 = 97.44% | 27/38 = 71.05% |
| M1 Top-5 | 19/19 = 100% | 19/20 = 95% | 2/19 = 10.53% | 38/39 = 97.44% | 28/38 = 73.68% |
| M2 Delta-Aware v2 (frozen reuse) | 20/20 = 100% | 20/20 = 100% | 0/19 = 0% | 39/39 = 100% | 38/39 = 97.44% |

M1 automatic exact-target recall over all 39 cases is 51.28% / 71.79% /
74.36% at Top-1/3/5. On the 38 function/API targets it is 50.00% / 71.05% /
73.68%. The single configuration target is found at rank 1, but correctly remains
not applicable to function reachability.

The best M1 median case latency is 0.955 s versus 27.889 s for the frozen
Delta-Aware inference (p90 1.402 s versus 39.627 s). Speed is not enough to pass
the gate: Top-3/5 meet recall, applicability, latency, and complexity conditions,
but their 10.53% N4 FPR exceeds the allowed 5%. Top-1 also fails recall and
applicability. See [go_no_go.md](reports/go_no_go.md).

## Isolation and freeze order

1. `dataset/cases.csv` was constructed without label or target columns;
   `dataset/gt_targets.csv` was stored separately.
2. The v1 rules and executable M1 inputs were frozen at
   `2026-09-11T08:46:40.966910Z`.
3. All 39 cases ran in separate processes, 39/39 succeeded.
4. The 39 outputs were frozen at `2026-09-11T08:47:34.432064Z`, aggregate
   SHA-256 `a338a01a4ddce42a45a97acc26e2129013b60ed58d7605056bbfc2bf569dfe56`.
5. Only then did evaluation read Ground Truth and run M0.

The access claim is supported by schema and source/path audit, not by an
OS-level syscall trace. Each formal JSON records the permitted input and false
use flags.

## Important frozen-protocol caveat

Post-freeze conformance review found that three intended function-only scoring
clauses lack a `target_type == function` guard in the frozen implementation.
Thus 21 non-function candidates in nine cases received at least one extra point;
14 appeared in a Top-5. The primary v1 results were **not** changed or rerun after
GT reveal. This especially affects Top-1 ordering in T5011, T5019, and T5035.
It cannot turn the result into KILL: the Top-3/5 FPs T5029 and T5037 arise from
function candidates and still violate the FPR gate. Full disclosure is in
`results/protocol_conformance.csv`.

## Artifact map

- Frozen inputs/rules: `frozen-experiment-config.json`, `protocol/m1_rules_v1.md`
- Isolated data: `dataset/cases.csv`, `dataset/gt_targets.csv`
- Per-case M1 evidence: `target-discovery/T5001.json` … `T5040.json` (T5028 excluded)
- Core metrics: `results/comparison.csv`, `results/target_recall_summary.csv`,
  `results/kill_gate.csv`, `results/latency_summary.csv`
- Case-level results: `results/diff_reachability_top{1,3,5}.csv`,
  `results/exact_target_oracle.csv`, `results/delta_aware.csv`
- Supplement and audits: `results/dynamic_supplement.csv`,
  `results/protocol_conformance.csv`, `results/validation.json`
- Reviewer answers: `reports/reviewer_kill_test.md`

## Reproduction

The preserved primary outputs should not be overwritten. A fresh semantic
reproduction can be sent to another directory:

```bash
python3 t7-target-discovery-reachability/scripts/run_discovery.py \
  --jobs 4 \
  --output-dir /tmp/t7-m1-reproduction \
  --manifest /tmp/t7-m1-reproduction-manifest.json
```

Timestamps, latency, and memory naturally differ; candidate/order/reachability
fields should be compared. To verify the preserved artifact and regenerate
post-freeze tables without changing M1:

```bash
python3 t7-target-discovery-reachability/scripts/dynamic_reachability.py
python3 t7-target-discovery-reachability/scripts/evaluate.py
python3 t7-target-discovery-reachability/scripts/validate_artifact.py
```
