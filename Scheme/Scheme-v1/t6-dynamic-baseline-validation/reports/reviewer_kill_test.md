# Reviewer kill test

All classification fractions below distinguish complete-case results from
intent-to-test (ITT) results.  Dynamic failures remain in the 39-case ITT
denominator and are never silently dropped.

## Required answers

1. **Is S1+H0 overall coverage alone sufficient?** No.  With lower absolute
   coverage treated as positive, ROC AUC stays near 0.5.  Even the post-hoc
   F1-best threshold predicts all 36 executable cases YES: 100% recall, 100%
   N4 FPR, 66.67% F1.  There is no deployable threshold.

2. **Is S0+H0 to S1+H0 overall coverage delta sufficient?** No.  The
   preregistered >1pp decline rule has only 3/18 = 16.67% complete-case Silent
   Recall (15% ITT), although its 5-minute majority N4 FPR is 0/18.

3. **Is Changed-Code Coverage sufficient?** No.  It detects 11/18 = 61.11% of
   executable positives but falsely flags 9/18 = 50.00% of executable N4.
   It detects gaps without reliably attributing them to the commit.

4. **Is Function Reachability sufficient?** On this target-conditioned Phase-A
   set, yes for evaluable function cases: 17/17 positives and 18/18 N4 are
   correct.  It is not sufficient as a complete operational detector: ITT
   Recall is 17/20 = 85%, four cases abstain, and the exact target symbol is an
   audited case input.  No target is dynamically reached, so temporal source
   presence supplies the separation.

5. **Which dynamic baseline performs best?** Function Reachability, with 100%
   complete-case recall, 0% N4 FPR, 100% precision/F1, and 89.74% signal
   evaluability.

6. **How does the best dynamic baseline perform at 1/5/15/30 minutes?** It is
   unchanged: 17/17 recall and 0/18 FPR at 1, 5, and 15 minutes.  Median wall
   times are 136.637 s, 588.662 s, and 1718.793 s.  Corpus replay already has
   the same classification at 18.548 s.  Thirty minutes was preregistered as
   NOT RUN because the protocol permits the resource-bounded minimum schedule.

7. **Silent Recall gap versus Delta-Aware?** Zero percentage points on
   complete cases (100% versus 100%), but -15 percentage points on ITT Recall
   (85% versus 100%) because Delta-Aware covers all three positive abstentions.

8. **N4 FPR gap versus Delta-Aware?** Zero percentage points among evaluable
   N4 (0/18 versus 0/19).  Function Reachability abstains on T5034; it does not
   earn a true negative for that case.

9. **Median latency gap?** At the earliest matching point, corpus-only Function
   Reachability is 18.548 s versus 27.889 s for the frozen Delta model call:
   9.341 s faster (0.665x).  At 1/5/15 minutes it is respectively 108.748 s,
   560.773 s, and 1690.904 s slower.  Input/target preparation was not timed
   comparably, so these are measured pipeline/model-call differences.

10. **CPU-cost gap?** The exact gap is unavailable because Delta-Aware runs on
    a remote model and its CPU consumption was not exposed.  Dynamic corpus
    replay has median measured CPU 10.905 s per successful case.  The complete
    multi-budget formal run consumed at least 135,524.790 measured CPU-seconds.

11. **How many cases cannot execute reliably?** Three of 39 (7.69%) are
    BUILD_UNAVAILABLE in both snapshots: T5030, T5034, and T5038.  Function
    Reachability additionally abstains on non-function target T5035, so that
    signal is evaluable for 35/39 cases.  All 432 records for the other 36 cases
    pass run and coverage collection.

12. **Do real needs exist when coverage looks normal?** Yes.  Fifteen of 18
    executable positives have no >1pp overall decline at the 5-minute majority
    result.  T5001 and T5035 are concrete examples; Delta-Aware says YES for
    all 15.

13. **Does coverage ever decline without a maintenance need?** Yes.  T5036 is
    N4 but crosses the decline threshold in 5-minute repeat 2
    (-2.527pp line, -1.914pp function), then has exactly 0pp deltas in repeats
    1 and 3.

14. **Standalone detector or dynamic-validation trigger?** The Phase-A evidence
    does not support Delta-Aware as the primary standalone detector.  If kept,
    it is better positioned as a prefilter/fallback around dynamic temporal
    validation, especially for build-unavailable and non-function cases.  The
    corpus baseline is lower-latency here, although historical-build operations
    remain more complex than a model call.

15. **Does this experiment support continuing the current idea?** No, not in
    its current standalone-paper positioning.  The decision is MAJOR
    WEAKENING.  Complete-case accuracy and low-budget cost satisfy the
    kill-test performance branch; incomplete ITT coverage and the optimistic
    exact-target conditioning prevent an unconditional KILL.  Under the task's
    gate, Phase B is therefore not executed.  Only a narrowed hybrid/fallback
    claim would merit a separately designed future study.

## Decision sensitivity

The result is intentionally reported both ways.  Treating abstentions as
excluded yields the preregistered 100%/0% and triggers MAJOR WEAKENING.
Treating all abstentions as misses yields 85% ITT Recall and would not meet the
`Delta-Aware - 5pp` recall line.  The experiment did not redefine its primary
failure policy after seeing this difference; both numbers are retained so a
reviewer can apply a different operational tolerance.
