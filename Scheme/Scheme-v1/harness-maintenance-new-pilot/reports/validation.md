# Artifact and protocol validation

## Execution

- Candidate mining used first-parent diffs from the ten local Git clones.
- Initial materialization froze 64 anonymous inputs with seed 20260909.
- Gap-Only: 64 valid outputs, 0 failed, 0 retried.
- Evolution-Aware: 64 valid outputs, 0 failed, 0 retried.
- Both used Codex CLI 0.145.0, `gpt-5.6-sol`, high reasoning, concurrency 4,
  a unique empty temporary working directory, read-only sandbox, ignored user
  configuration/rules, and one ephemeral process per case.
- The two manifests record command templates, hashes, timestamps, duration, and
  exit status. Exact model inputs and outputs are retained in paired JSONL.

## Leakage checks

The runner reads only `cases/C*/blind_input.md`, the fixed baseline prompt, and
its JSON schema. A scan of all inputs found none of these ground-truth markers:
`verified positive`, `actual label`, `counterfactual status`, `commit_message`,
`harness diff`, `H1/`, or `developer harness`. Commit messages, H1, harness
diffs, labels, coverage/counterfactual results, and predictions from the other
baseline are absent.

## Counterfactual evidence

For all 15 final VP1 cases, the host translation-unit probe with minimally
materialized generated headers produced:

`S0 + H0 = PASS; S1 + H0 = FAIL; S1 + H1 = PASS`.

Two VP3 and three VP4 cases use direct entry/configuration evidence recorded in
the case ground truth and reachability table. All 20 final positives have H0,
H1, source diff, harness diff, metadata, blind input, and ground truth.

Dynamic changed-code coverage was not available uniformly and is explicitly
recorded as `NOT_MEASURED`; no static proxy is presented as dynamic coverage.

## Ground-truth audit and protocol deviation

The initial counterfactual check compared only S1+H0 with S1+H1. The later
three-way probe showed why S0+H0 is mandatory: C030 and C040 already failed at
S0. Combined with one no-production-source case and three unresolved label
polarities, 7/64 initial labels were changed or excluded after predictions.

The artifact preserves both views:

- `*_initial.csv`: labels and metrics in force at prediction time.
- canonical CSVs: audited 20-positive/40-negative stable subset.
- `ground_truth_audit.csv`: every change/exclusion and its evidence.

Because this deviation can bias the audited scores, the formal decision is
NO-GO even though the sensitivity-analysis metrics pass STRONG GO thresholds.
