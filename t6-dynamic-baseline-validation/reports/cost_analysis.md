# Cost analysis

## Per-case dynamic cost

The table uses successful cases only.  Each end-to-end row charges both S0 and
S1 checkout/build because temporal baselines require both snapshots.  Build
time includes configure and instrumentation; instrumentation is not added a
second time.  Five-minute component medians pool all three repeats.

| Budget | Checkout | Instrumented build | Corpus/fuzz | Coverage collection | Total wall | CPU | Successful cases/runs |
|---|---:|---:|---:|---:|---:|---:|---:|
| Corpus | 0.452 s | 14.092 s | 0.394 s | 1.527 s | 18.548 s | 10.905 s | 36/36 |
| 1 minute | 0.452 s | 14.092 s | 118.063 s | 1.413 s | 136.637 s | 136.330 s | 36/36 |
| 5 minutes | 0.452 s | 14.092 s | 569.805 s | 1.422 s | 588.790 s | 617.330 s | 108/108 repeats |
| 15 minutes | 0.452 s | 14.092 s | 1696.654 s | 1.405 s | 1718.793 s | 1817.300 s | 36/36 |

The 5-minute classification table uses the per-case median cost before taking
the cross-case median (588.662 s), while the component table takes the median
over all 108 successful repeat rows (588.790 s).  No performance conclusion
depends on this 0.128-second aggregation difference.

Peak fuzz-process RSS medians are 27.0 MiB (corpus), 27.47 MiB (1 minute),
28.02 MiB (5 minutes), and 27.43 MiB (15 minutes).  Build peak memory is not
available from the frozen adapter; builds ran under a 4096 MiB Docker limit.
Coverage-collection CPU is also unavailable, so measured CPU is a lower bound.

## Delta-Aware comparison

Frozen Delta-Aware median model-call latency over the 39 valid cases is
27.889 s.  Target-conditioned Function Reachability has the following measured
wall differences:

| Dynamic budget | Dynamic median | Difference vs Delta | Ratio to Delta |
|---|---:|---:|---:|
| Corpus | 18.548 s | -9.341 s | 0.665x |
| 1 minute | 136.637 s | +108.748 s | 4.899x |
| 5 minutes | 588.662 s | +560.773 s | 21.107x |
| 15 minutes | 1718.793 s | +1690.904 s | 61.630x |

Corpus replay is therefore not slower in measured per-case wall time on this
artifact.  This comparison is not a complete economic accounting: Task 5 did
not separately time Delta input preparation, this task did not separately time
changed-code/target-anchor preparation, and remote model CPU is unavailable.
The exact CPU-cost difference cannot be computed.  The observed dynamic corpus
CPU median is 10.905 s; Delta-Aware's remote CPU is N/A.

## Formal-run resource consumption

- Calendar duration: 18,917.347 s = 5 h 15 min 17.347 s with up to 8 workers.
- Measured build plus fuzz/corpus CPU: 135,524.790 s = 37.646 CPU-hours.
- Fuzz/corpus CPU alone: 134,672.700 s.
- Build CPU, counted once per 78 attempts: 852.090 s.
- Serial sum of fuzz/corpus wall time: 126,901.933 s.
- Serial sum of build wall time: 751.673 s.

These full-run totals include all budgets and repeats and are not the cost of
one deployment strategy.  Corpus-only is the relevant low-budget comparator.

## Availability cost

Three of 39 cases (7.69%) are build-pair unavailable; equivalently, six of 78
snapshot build attempts fail.  All are old libplist revisions.  The project
library itself builds, but the frozen adapter searches only for
`libplist-2.0.a`, while those revisions emit `libplist.a`; fuzz-target linking
therefore stops.  These failures were not repaired or rerun after seeing the
result.

For the remaining 36 cases, all 432 run and coverage records pass.  A separate
TemporaryDirectory cleanup permission exception affects the orchestration
manifest after measurement but does not remove or invalidate the 36 complete
measurements.  `results/execution_audit.csv` preserves both statuses.

Detailed data are in `results/runtime_cost.csv` and
`results/cost_summary.json`.
