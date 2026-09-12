# Dynamic baseline results

## Outcome

Phase A gives **MAJOR WEAKENING**, not CONTINUE, for Delta-Aware as a
standalone method.  The preregistered Function Reachability baseline matches
Delta-Aware's complete-case Silent Recall and N4 FPR with corpus replay alone,
at lower measured median latency.  It does not match Delta-Aware under an
intent-to-test treatment of abstentions, so this is not an unconditional KILL.

This is a diagnostic result on the reused Task-5 set, not an independent
confirmatory claim.  In accordance with the gate in `task-6.md`, Phase B was
not run after the MAJOR WEAKENING decision.

## Experiment scope

- 39 valid Task-5 cases: 20 silent positives and 19 N4 existing gaps.
- Four projects: c-ares (10), libplist (10), libspng (10), meshoptimizer (9).
- T5028 is excluded because Task 5 invalidated it; it was not replaced.
- Budgets per S0/S1 snapshot: corpus replay, 1 minute, 5 minutes, and
  15 minutes over the complete H0 target set.  Five minutes was repeated three
  times.  The optional 30-minute budget was frozen as resource-bound/not run.
- 36 cases executed completely; three historical libplist cases were
  BUILD_UNAVAILABLE in both snapshots.
- 432/432 generated run/coverage records are PASS.
- Delta-Aware is the original frozen Task-5 one-shot output: no prompt edit,
  inference rerun, or answer selection.

## Primary classification result

Dynamic rows below use the lowest budget, corpus replay.  Recall and FPR are
complete-case quantities under the preregistered failure policy; ITT Recall
keeps all 20 positives in the denominator.  All negative cases are N4, so
Overall FPR equals N4 FPR.

| Method | Silent Recall | N4 / Overall FPR | Precision | F1 | ITT Recall | Median wall time | Dynamic |
|---|---:|---:|---:|---:|---:|---:|---|
| Build-Only | 0/18 (0.00%) | 0/18 (0.00%) | N/A | N/A | 0/20 (0.00%) | 18.548 s | Yes |
| Overall Coverage Delta | 3/18 (16.67%) | 0/18 (0.00%) | 100.00% | 28.57% | 3/20 (15.00%) | 18.548 s | Yes |
| Changed-Code Coverage | 11/18 (61.11%) | 9/18 (50.00%) | 55.00% | 57.89% | 11/20 (55.00%) | 18.548 s | Yes |
| Function Reachability | 17/17 (100.00%) | 0/18 (0.00%) | 100.00% | 100.00% | 17/20 (85.00%) | 18.548 s | Yes |
| Delta-Aware | 20/20 (100.00%) | 0/19 (0.00%) | 100.00% | 100.00% | 20/20 (100.00%) | 27.889 s | No |

Function Reachability evaluates 35/39 cases (89.74%): 17 positives and 18
N4.  Its four abstentions are two positive build failures (T5030, T5038), one
N4 build failure (T5034), and the non-function configuration target T5035.
The underlying dynamic build/run success is 36/39 (92.31%).

## Budget curve

Function Reachability is the best dynamic method at every measured budget.
The 5-minute row uses the majority prediction over all three repeats.

| Budget | Silent Recall | N4 FPR | ITT Recall | Signal evaluability | Median wall time |
|---|---:|---:|---:|---:|---:|
| Corpus only | 17/17 (100.00%) | 0/18 (0.00%) | 85.00% | 35/39 (89.74%) | 18.548 s |
| 1 minute | 17/17 (100.00%) | 0/18 (0.00%) | 85.00% | 35/39 (89.74%) | 136.637 s |
| 5 minutes | 17/17 (100.00%) | 0/18 (0.00%) | 85.00% | 35/39 (89.74%) | 588.662 s |
| 15 minutes | 17/17 (100.00%) | 0/18 (0.00%) | 85.00% | 35/39 (89.74%) | 1718.793 s |
| 30 minutes | N/A | N/A | N/A | N/A | NOT RUN — preregistered resource limit |

Longer fuzzing adds no classification value.  Every one of the 35 evaluable
function targets has `s1_reached=false` at every budget/repeat, and every
existing N4 target also has `s0_reached=false`.  Function Reachability therefore
separates this set through temporal source presence: positive targets are NEW
(absent in S0, present and unreached in S1), while N4 targets are UNCHANGED
(present and unreached on both sides).  Dynamic execution confirms the gap but
does not discover a reached target.

This is a material limitation as well as the kill-test result.  The baseline
is conditioned on the case's exact audited `target_symbol`; it is more
optimistic than a production system that must derive and prioritize the full
changed-function set automatically.  It also mirrors the NEW-versus-UNCHANGED
ground-truth construction.  The perfect complete-case score must not be
generalized beyond this diagnostic set.

## Absolute and delta overall coverage

Absolute S1 overall coverage has no usable cross-project threshold.  Even the
post-hoc F1-maximizing threshold for line, branch, and function coverage at
every budget predicts every executable case positive: 100% recall, 100% N4
FPR, and 66.67% F1.  Low-coverage-positive ROC AUC is near chance.  At corpus
replay it is 0.505 (line), 0.474 (branch), and 0.499 (function); at 5-minute
repeat 1 it is 0.488, 0.498, and 0.498.  These are explicitly oracle/post-hoc
statistics, not deployment results.

The preregistered overall-delta rule detects only T5003, T5006, and T5017:
3/18 executable positives.  It misses 15 executable silent positives.  Its
5-minute repeats have stable 16.67% recall but N4 FPR values 0%, 5.56%, and
0%; T5036 is the single stochastic false positive in repeat 2.  Majority vote
returns 0% FPR.

## Changed-code coverage

The changed-code rule improves recall to 11/18 but is not sufficient: it misses
seven executable positives and reports nine of 18 executable N4 cases as
maintenance needs.  Its 5-minute results are identical in all three repeats
(61.11% recall, 50.00% FPR; population standard deviation 0 for both).  Low
coverage of changed code identifies a gap but cannot attribute whether the
current commit created it, which is exactly why the N4 false-positive rate is
high.

Changed-branch coverage was not promoted to a separate decision feature: the
frozen implementation could map added/modified source lines and functions
reliably, but not branch identities across revisions without adding an
unfrozen heuristic.

## H1 oracle

Task 5 did not identify any provenance-audited H1 harness update for these
cases.  B4 is therefore unavailable for all 39 cases.  No H1 was synthesized,
and no later harness, degradation result, or oracle coverage was exposed to
Delta-Aware or the primary dynamic baselines.

## Direct answers relative to degradation monitoring

1. Degradation-style overall coverage delta identifies 3/18 executable silent
   needs (16.67%; 15.00% ITT) at every aggregated budget.
2. Changed-Code Coverage is not enough: 61.11% complete-case recall comes with
   50.00% N4 FPR.
3. Fifteen executable positives have no >1pp overall coverage decline at the
   5-minute majority result, yet frozen Delta-Aware returns YES for all of
   them.
4. T5036 shows a coverage decline without a current-commit maintenance need in
   one 5-minute repeat; its line/function deltas are -2.527pp/-1.914pp, while
   repeats 1 and 3 are exactly 0pp.
5. Target-conditioned Function Reachability reaches matching complete-case
   accuracy with corpus replay alone; ordinary overall and changed-code
   coverage never approach Delta-Aware even at 15 minutes.

Machine-readable evidence is in `results/method_summary.csv`,
`results/classification_metrics.csv`, `results/repeatability_5m.csv`,
`results/s1_overall_threshold_sweep.csv`, and `results/case_analysis.csv`.
