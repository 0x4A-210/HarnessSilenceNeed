# Evolution-Induced Harness Maintenance Pilot

This is the executable artifact and complete result package for `../task-2.md`.
Maintenance is the conjunction of a material harness gap and evidence that the
current source commit introduced or aggravated it.

## Outcome

- Ten repositories searched; 119 raw path-level hits.
- 50 stratified candidates screened; 49 survived production-source eligibility.
- Audited evaluation: 60 unique commits from all ten repositories, comprising
  20 verified positives and 40 verified negatives; positives come from five.
- Gap-Only: TP=20, FP=28, FN=0, TN=12.
- Evolution-Aware: TP=19, FP=1, FN=1, TN=39.
- Formal decision: **NO-GO for a confirmatory/scaled experiment**, because the
  mandatory three-way audit occurred after prediction and changed/excluded 7 of
  the original 64 labels. The audited numerical result is a promising but
  post-hoc sensitivity analysis.

## Blindness

Every frozen input contains only H0 and the S0-to-S1 production diff. H1,
harness diffs, commit messages, counterfactual outcomes, labels, prior model
outputs, and future evidence were not sent to either predictor. Each baseline
used one fresh ephemeral process per case, with no retries:

- model: `gpt-5.6-sol`
- reasoning effort: `high`
- concurrency: 4
- timeout: 900 seconds

The exact input and output for every invocation is retained in
`results/*_input_output_pairs.jsonl`; manifests record hashes and timings.

## Reproduction order

From the workspace root:

```sh
python3 harness-maintenance-new-pilot/scripts/mine_coevolution_commits.py \
  --project-root FSE2026-harness-degradation/sources/projects \
  --output-dir harness-maintenance-new-pilot/data --limit 50
python3 harness-maintenance-new-pilot/scripts/prepare_cases.py
python3 harness-maintenance-new-pilot/scripts/measure_reachability.py
python3 harness-maintenance-new-pilot/scripts/measure_changed_coverage.py
python3 harness-maintenance-new-pilot/scripts/build_counterfactual.py
python3 harness-maintenance-new-pilot/scripts/run_gap_only.py
python3 harness-maintenance-new-pilot/scripts/run_evolution_aware.py
python3 harness-maintenance-new-pilot/scripts/audit_ground_truth.py
python3 harness-maintenance-new-pilot/scripts/evaluate.py
python3 harness-maintenance-new-pilot/scripts/summarize_counterfactual.py
python3 harness-maintenance-new-pilot/scripts/validate_artifact.py
```

The runners and most result-producing scripts intentionally refuse to
overwrite one-shot artifacts. The `*_initial.csv` files preserve the labels and
metrics as they existed before the post-run audit.

Dynamic changed-line coverage is explicitly `NOT_MEASURED`: uniform historical
instrumented builds and corpora were unavailable. Fifteen positives instead
have the registered VP1 three-way compile pattern (PASS/FAIL/PASS), two use
direct new-entry exposure (VP3), and three use direct configuration/state
evidence (VP4). Static identifier exposure is never presented as coverage.

Run `scripts/validate_artifact.py` after reproduction to independently
reconstruct both confusion matrices, verify all frozen input/output pairs and
hashes, resolve commit IDs in the local Git clones, scan blind inputs for
leakage markers, and validate the three-way VP1 evidence. Its generated report
is `reports/artifact_validation.md`.
