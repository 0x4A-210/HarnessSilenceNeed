# Blind-test results

## Main comparison

The table below uses the 77 valid cases after excluding, not relabeling, three
post-freeze invalid cases. The untouched original 80-label result follows it.

| Baseline | Explicit recall | Silent recall | Negative FPR | Hard-negative FPR |
|---|---:|---:|---:|---:|
| Build-Only | 10/10 (100%) | 0/17 (0%) | 0/50 (0%) | 0/17 (0%) |
| Gap-Only | 10/10 (100%) | 15/17 (88.24%) | 22/50 (44%) | 4/17 (23.53%) |
| Evolution-Aware | 10/10 (100%) | 14/17 (82.35%) | 0/50 (0%) | 0/17 (0%) |

For all valid positives combined, Evolution-Aware has TP=24, FP=0, FN=3,
TN=50, precision=100%, recall=88.89%, and F1=94.12%. Gap-Only has TP=25,
FP=22, FN=2, TN=28, precision=53.19%, recall=92.59%, and F1=67.57%.

Evolution attribution reduces Gap-Only FP by `(22-0)/22 = 100%`; silent recall
drops by `88.24%-82.35% = 5.88` percentage points.

On the untouched 80-label freeze, Evolution-Aware silent recall was 14/20
(70%) and Gap-Only was 17/20 (85%); FPRs remained 0/50 and 22/50. These values
are preserved because all three later-invalidated cases were frozen silent
positives and Evolution-Aware rejected them.

## Answers to the 15 required questions

1. **How many new candidates were mined?** 250 independent source+harness
   co-evolution candidates, from 300 pre-exclusion path hits. Separately, 33
   source-only negative controls were mined.
2. **How many became Verified Silent Positive?** 20 were frozen as silent
   positives; post-freeze audit invalidated 3, leaving 17 valid.
3. **VP2/VP3/VP4/VP5 counts?** Frozen: 1/6/11/2. Valid: 1/4/10/2.
4. **How many VP1?** 10, all valid.
5. **Was ground truth completely frozen before prediction?** Yes. GT was frozen
   at 04:23:58Z; prediction began at 04:30:45Z.
6. **Did any relabel occur after prediction?** No relabel. Three cases were
   marked `INVALID` after reveal, exactly as the protocol requires. This still
   means the GT freeze was not stable.
7. **Build-Only Explicit/Silent performance?** 100% explicit recall (10/10),
   0% silent recall (0/17 valid; also 0/20 frozen).
8. **Gap-Only Silent Recall and FPR?** Valid set: 88.24% and 44%. Frozen-label
   set: 85% and 44%.
9. **Evolution-Aware Silent Recall and FPR?** Valid set: 82.35% and 0%.
   Frozen-label set: 70% and 0%.
10. **How much did attribution reduce FP?** 100% (22 to 0), with a valid-set
    silent-recall cost of 5.88 percentage points.
11. **Did Existing Gap FP clearly decrease?** Formally not estimable: the frozen
    negative stratum contains zero N4 cases. As a post-hoc diagnostic only,
    Evolution-Aware rejected both N223 and N231 that were invalidated as
    existing gaps, whereas Gap-Only flagged both.
12. **Which silent type was easiest?** VP4: 10/10 valid cases for
    Evolution-Aware. VP3 was 3/4, VP5 1/2, VP2 0/1.
13. **Which was hardest?** VP2 (0/1), followed by VP5 (1/2). With such small
    denominators this is descriptive, not a stable ranking.
14. **What caused FN?** The three valid Evolution-Aware FN are: an error-path
    state/oracle ordering change (N216), a new decoder sizing API dismissed as
    behavior-equivalent (N207), and new reader/writer helpers dismissed as
    convenience wrappers (N185). Inputs contained complete source diffs and H0,
    so these are primarily materiality/semantic-attribution failures, not
    obvious context truncation. No FN is principally a dynamic-performance case.
15. **STRONG GO, MODERATE GO, or NO-GO?** Quantitatively the valid-set model
    result reaches MODERATE GO and exceeds its recall/FPR thresholds. The
    experiment as a definitive unbiased main test is nevertheless **NO-GO**:
    three GT cases were invalidated after prediction freeze, directly meeting
    the protocol's “ground truth cannot be stably frozen” condition. It also
    cannot answer the preregistered N4 Existing Gap test and is heavily Wuffs
    dominated.

## One-shot execution facts

Both LLM baselines produced 80/80 schema-valid outputs, with zero timeout,
failure, or retry. Each call used a fresh ephemeral Codex process in an empty
read-only directory, model `gpt-5.6-sol`, reasoning effort `high`, concurrency
4, timeout 900 seconds, and service-default temperature/max-token settings
(the CLI exposes neither). Exact model inputs and outputs are preserved in the
two `*_input_output_pairs.jsonl` files.
