# Task 6 — Dynamic baseline validation

This directory contains the Phase-A diagnostic kill test specified by
[`../task-6.md`](../task-6.md).  It compares the unchanged, frozen Task-5
Delta-Aware prediction with build and coverage baselines on the same 39 valid
cases: 20 silent positives and 19 N4 existing gaps from c-ares, libplist,
libspng, and meshoptimizer.  Invalidated case T5028 is absent.

## Result

The decision is **MAJOR WEAKENING**, not CONTINUE.  Target-conditioned
Function Reachability matches Delta-Aware on evaluable cases with corpus replay
alone (100% Silent Recall, 0% N4 FPR; median 18.548 s), but evaluates only
35/39 cases and has 85% intent-to-test Recall versus Delta-Aware's 100%.
Ordinary Overall Coverage Delta remains weak (16.67% Recall), and Changed-Code
Coverage trades 61.11% Recall for 50% N4 FPR.  See
`reports/go_no_go.md` and `reports/reviewer_kill_test.md` for the qualified
decision.  Phase B was not run because the protocol gates it on CONTINUE.

## Freeze and independence

`experiment_config.json` was frozen before the first formal dynamic
execution.  It records the dataset hash, all preregistered rules, image IDs,
compiler and runtime settings, corpus policy, budgets, and SHA-256 values for
the Task-5 predictions and every collection/evaluation input.  Dynamic
collection code does not read the case label.  Ground truth is opened only by
the evaluation stage.  Task-5 Delta-Aware outputs are reused byte-for-byte;
there is no new model call.

The formal minimum resource-bounded schedule is corpus replay, 1 minute,
5 minutes, and 15 minutes per snapshot across the complete H0 target set.
The 5-minute budget has three independent repeats; the other budgets have one.
The optional 30-minute budget was preregistered as not run because of resource
limits.  S0 and S1 always start from the same corpus copied from S0.  No
post-commit corpus is used.

## Methods

- Build-Only: explicit S1 build/link/corpus-runtime failure after a valid S0.
- S1 Overall Coverage: line, branch, and function coverage; only complete
  post-hoc threshold curves are reported, never a deployable threshold.
- Overall Coverage Delta: preregistered decline greater than 1 percentage
  point in any production-code coverage dimension.
- Changed-Code Coverage: preregistered `<10%` changed executable-line coverage
  or `0%` mapped changed-function reachability.
- Function Reachability: temporal reachability of the selected changed target,
  explicitly distinguishing new gaps from gaps already present in S0.
- H1 Oracle: unavailable because Task 5 identified no provenance-audited H1;
  none is synthesized.
- Delta-Aware: frozen Task-5 one-shot result.

Coverage uses Clang 22 source-based instrumentation and libFuzzer in the
pinned OSS-Fuzz project images.  Totals include project production C/C++
sources and headers, excluding test, fuzz, tool, example, generated, and build
paths.

## Reproduction order

The artifact was executed in this order:

```text
python3 scripts/prepare_phase_a.py
python3 scripts/extract_changed_code.py
python3 scripts/extract_target_anchors.py
python3 scripts/freeze_experiment.py
python3 scripts/run_phase_a.py --workers 8
python3 scripts/evaluate_dynamic_baselines.py
python3 scripts/summarize_phase_a.py
```

The first four commands must not be rerun as a way to alter the frozen formal
run.  Raw failures are retained.  The post-freeze summarizer only audits and
aggregates already produced measurements; it cannot change a prediction rule.

## Artifact map

- `dataset/`: exact 39 cases, S0-only corpus manifest, changed-code lines, and
  target anchors.
- `scripts/`: preparation, frozen build/run/coverage/evaluation pipeline, and
  post-freeze reporting audit.
- `raw/coverage/`: compact gzip JSON with production totals, file segments,
  per-function counters, binary hashes, and run metadata.
- `raw/timings/` and `raw/logs/`: build, fuzz/corpus, coverage, stdout, and
  stderr evidence, including failures.
- `results/`: per-case signals, classifications, threshold sweep, repeatability,
  cost, execution audit, and hashes.
- `reports/`: result narrative, cost analysis, failure/case analysis, the 15
  required reviewer answers, and the Phase-A gate decision.

The authoritative conclusion is in `reports/go_no_go.md`; Phase A is a reused
diagnostic set and cannot by itself establish an independent confirmatory
claim.
