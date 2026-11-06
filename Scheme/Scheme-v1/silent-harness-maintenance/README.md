# Silent Harness Maintenance — task-3 artifact

This directory contains the independent 80-case experiment requested by
`task-3.md`. Candidate mining, three-way ground-truth audit, ground-truth
freeze, blind-input freeze, prompt/config freeze, one-shot prediction, label
reveal, and evaluation are timestamped and hashed.

## Result in one paragraph

The original frozen dataset had 3 projects, 80 unique commits, and 30 positive
commits (20 silent plus 10 explicit). Post-freeze review invalidated—not
relabeled—3 silent cases, leaving the validity-cleaned set at 3 projects, 77
unique commits, and 27 positives (17 silent plus 10 explicit). On the valid set,
Evolution-Aware achieved 14/17 silent recall (82.35%) and 0/50 FPR; Gap-Only
achieved 15/17 (88.24%) and 22/50 FPR (44%). Evolution attribution therefore
removed 100% of Gap-Only false positives at a 5.88 percentage-point silent
recall cost. These model numbers are Moderate-GO-level, but the experiment's
formal verdict is **NO-GO for use as a definitive unbiased main result** because
three labels had to be invalidated after prediction freeze and the frozen
negative stratum contained no N4 existing-gap case.

## Integrity chain

- Ground truth frozen: `2026-09-10T04:23:58.852330Z`
- Blind inputs frozen: `2026-09-10T04:28:12.719205Z`
- Prompt/model config frozen: `2026-09-10T04:28:13.806610Z`
- Gap-Only run: `04:30:45Z–04:40:56Z`
- Evolution-Aware run: `04:41:13Z–04:50:53Z`
- Predictions frozen: `2026-09-10T04:51:49.857025Z`
- Labels first joined: `2026-09-10T04:54:07.469815Z`
- Post-freeze invalidations recorded: `2026-09-10T05:01:23.265707Z`
- Dataset hash: `0a3a0ddc052fa60f7647820f51846aae1740144ce08a42c14cf691679aaa4b4e`
- Blind-input hash: `07c4d0baf8ee5dd77d4c931a2de4819c44c2099ff816ea2e0654661940637809`

## Where to look

- Final answers to all 15 questions: `reports/blind_test_results.md`
- Verdict: `reports/go_no_go.md`
- Frozen labels and invalidations: `frozen-ground-truth/`
- Exact anonymous model inputs: `frozen-inputs/C001.md` … `C080.md`
- Exact input/output pairs: `predictions/*_input_output_pairs.jsonl`
- Per-case joined outcomes: `results/case_outcomes.csv`
- Valid-set metrics: `results/baseline_comparison.csv`
- Untouched original 80-label metrics: `results/frozen_label_*.csv`
- Build/runtime, coverage, reachability, and state evidence: `ground-truth/`
- Complete audited source/H1 patches: `raw-evidence/audited-diffs/`

`NOT_MEASURED` is used wherever reliable dynamic coverage was unavailable; no
estimate is substituted. Solidity validation is component-level against exact
historical production headers and exact historical harness decisions, not a
claim of a full historical OSS-Fuzz image build.
