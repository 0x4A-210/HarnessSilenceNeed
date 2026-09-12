# Feasibility results

## Bottom line

The audited 60-case subset shows a strong signal for evolution attribution,
but this run is **NO-GO as a confirmatory pilot** because its ground truth was
not stable before prediction. The numerical result should be treated as a
post-hoc sensitivity analysis, not as an unbiased estimate to publish or scale.

## Dataset and counterfactual validation

Ten requested repositories were searched. The miner found 119 path-level
source+harness hits in six repositories: Wuffs 80, Leptonica 13, c-ares 10,
libspng 8, Brotli 4, and meshoptimizer 4. h2o, Jansson, libplist, and tidy-html5
had no eligible in-repository co-evolution hit under the fixed harness-path
rules. A deterministic stratified screen retained 50; one Wuffs hit changed
only examples, a benchmark, and harnesses, leaving **49 eligible candidates**.

The semantic screen over the 50 path hits produced 30 RELATED, 13 UNRELATED,
and 7 UNCERTAIN records after audit (the ineligible hit is recorded among the
UNRELATED rows). **20 candidates are Verified Positive**, across five projects:
Wuffs 9, meshoptimizer 4, libspng 3, c-ares 3, and Leptonica 1.

The maintenance mechanisms group cleanly:

- 15 VP1 build/API incompatibilities: signature/arity changes, symbol or status
  type changes, state-layout changes, work-buffer protocols, and include-path
  moves. Every one has the three-way compile pattern S0+H0=PASS,
  S1+H0=FAIL, S1+H1=PASS.
- 2 VP3 new parser entry points: `ares_parse_uri_reply` and the new
  `ares_set_servers_csv` URI/configuration path, directly exposed only by H1.
- 3 VP4 configuration/state changes: meshoptimizer's version 0xe→1, Wuffs'
  swapped initializer arguments, and libspng's new ancillary CRC-discard state.

Changed-line dynamic coverage was not measured because there was no uniform
historical instrumented build plus matching corpus. `coverage_results.csv`
records this as `NOT_MEASURED`; static identifier exposure is reported
separately and is not called coverage.

## Blind prediction results

The initial frozen labels were 24 positive/40 negative (64 cases). Those raw
results are preserved because they were the labels in force at prediction time:

| Baseline | TP | FP | FN | TN | Precision | Recall | F1 | FPR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Gap-Only, initial | 23 | 29 | 1 | 11 | 44.23% | 95.83% | 60.53% | 72.50% |
| Evolution-Aware, initial | 20 | 3 | 4 | 37 | 86.96% | 83.33% | 85.11% | 7.50% |

The mandatory three-way audit then produced a stable 20-positive/40-negative
subset. Its sensitivity-analysis results are:

| Baseline | TP | FP | FN | TN | Precision | Recall | F1 | FPR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Gap-Only, audited | 20 | 28 | 0 | 12 | 41.67% | 100.00% | 58.82% | 70.00% |
| Evolution-Aware, audited | 19 | 1 | 1 | 39 | 95.00% | 95.00% | 95.00% | 2.50% |

Evolution attribution reduced FP from 28 to 1: 27 fewer false positives, a
**96.43% reduction**, while recall fell by 5 percentage points (100%→95%).

## Answers required by TEST.md

1. **How many co-evolution candidates?** 119 raw hits; 50 screened; 49 eligible
   Source+Harness candidates after the production-source audit.
2. **How many Verified Positive?** 20.
3. **Main mechanisms?** API/build incompatibility (15), new entry exposure (2),
   and configuration/state adequacy (3).
4. **Gap-Only TP/FP/FN/TN?** 20/28/0/12 on the audited stable subset.
5. **Evolution-Aware TP/FP/FN/TN?** 19/1/1/39 on that subset.
6. **Did attribution reduce FP?** Yes: 28→1, down 96.43%, at a 5-point recall
   cost.
7. **Were existing gaps still mistaken for current maintenance?** Yes, once:
   C040. H0 already failed at S0, but the model attributed a new S1 declaration
   failure to this commit.
8. **Easiest needs?** Typed API name/arity/status/layout changes and explicit
   new parser/configuration entry points. They produced concrete diff evidence.
9. **Hardest needs?** Source-layout/include-path moves. One of two was missed;
   the other was classified correctly for a causally wrong reason.
10. **Did the run meet Go/No-Go?** The audited numbers meet STRONG GO thresholds,
    and 18/19 TP reasons were correct with 19/19 evidence grounded. Nevertheless
    the formal answer is **NO-GO**, because 3 labels were changed and 4 cases
    excluded only after the predictions; the preregistered ground-truth
    stability condition failed.
