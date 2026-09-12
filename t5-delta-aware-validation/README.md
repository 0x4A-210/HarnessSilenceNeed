# Task 5 — Delta-Aware validation

## Outcome

The defensible result is **MODERATE GO**, not STRONG GO. On the valid blind
set, Delta-Aware reaches 20/20 positive recall, 0/19 N4 false positives,
38/39 exact delta attribution, and 18/19 complete N4 target patterns. It
eliminates all six valid Direct Evolution-Aware N4 false positives without a
paired regression.

STRONG GO is withheld because the immutable post-freeze audit invalidated one
N4 case, leaving 19 rather than the required 20 valid N4 cases. The invalid
case was not relabeled or replaced.

| Method | Positive recall | N4 FPR | Attribution accuracy | Classification accuracy |
|---|---:|---:|---:|---:|
| Gap-Only | 18/20 (90.00%) | 19/19 (100.00%) | N/A | 18/39 (46.15%) |
| Direct Evolution-Aware | 18/20 (90.00%) | 6/19 (31.58%) | 31/39 (79.49%) | 31/39 (79.49%) |
| Delta-Aware | 20/20 (100.00%) | 0/19 (0.00%) | 38/39 (97.44%) | 39/39 (100.00%) |

Delta-Aware diagnostics:

- GapBefore accuracy: 38/39 (97.44%); on N4, 18/19 (94.74%).
- GapAfter accuracy: 38/39 (97.44%).
- Exact delta attribution: 38/39 (97.44%).
- N4 target pattern `YES/YES/UNCHANGED/NO`: 18/19 (94.74%).
- Output/decision-rule consistency: 39/39 (100%).
- Direct -> Delta paired N4 change: 6 corrected, 0 worsened;
  McNemar exact p = 0.03125.

Wilson 95% intervals remain wide at this sample size: Delta positive recall
20/20 is [83.89%, 100%], and Delta N4 FPR 0/19 is [0%, 16.82%].

## Development gate

The prior 16 valid N4 plus 20 positives were used only for prompt development.
The first Delta-Aware prompt failed the gate (N4 FPR 18.75%, delta accuracy
68.75%). The frozen v2 passed it (N4 FPR 0%, all Before/After/delta/recall
metrics 100%). No development case contributes to the blind metrics.

The original Direct errors were dominated by impact-scope failure (7/16). Its
7/16 = 43.75% N4 FPR came specifically from three GapBefore errors and four
delta/internal-growth errors. Only 2/16 Direct outputs exhibited the complete
target attribution pattern even though additional cases happened to make the
right final maintenance decision.

## Blind dataset and integrity

The frozen blind design has 40 unique commits: 20 N4 and 20 positives across
c-ares, libplist, libspng, and meshoptimizer, 10 per project (25% maximum
frozen share). Every commit is a single-parent ancestor of the archived local
HEAD, has no Harness change, and is absent from a conservative set of 1,053
prior SHAs. The broad miner retained 6,994 new candidates and recorded 135
excluded project/commit rows.

The objective oracle is static entry exposure/API protocol: complete H0 has no
literal target exposure; positive target identities are absent in S0 and
present in S1; N4 identities exist on both sides; and every semantic diff is
manually audited. This experiment does not claim dynamic coverage or runtime
bug-finding evidence.

Freeze order:

1. Ground Truth — `2026-09-10T10:34:05.846810Z`
2. Anonymous inputs — `2026-09-10T10:36:47.600835Z`
3. Prompts/model configuration — `2026-09-10T10:40:59.002606Z`
4. First prediction — `2026-09-10T10:42:00.066947Z`
5. All 120 predictions frozen — `2026-09-10T11:01:22.474133Z`

Integrity identifiers:

- Dataset: `d041e28db6d6cef4ef187f0bf4304ccf044ced60f36e8d5ab0d2a2497b50fb43`
- Ground Truth: `6b5513fa02af4313e1d2ee1e9fc68f61a0d236d8a1a87bc842cf2a283f759683`
- Inputs: `7c55fd860e9cee127087de9ae65a89c87e95dd4dfcf14900bdcf0b7a0aa4caf8`

Each method used `gpt-5.6-sol`, reasoning effort `high`, temperature and max
tokens unset, concurrency 4, 900-second timeout, and zero retries. Every
case/method used a fresh ephemeral process in a unique empty read-only working
directory. All three runs produced 40/40 schema-valid outputs. The runners did
not read Ground Truth. Full input/output pairs are retained under
`predictions/*_input_output_pairs.jsonl`.

## Post-freeze audit

T5028 was frozen as N4 but actually changes
`meshopt_generateTangents`' public `vertex_uvs_stride` lower bound from 12 to
8. That is a new caller-supplied input-layout obligation and therefore
AGGRAVATED. In accordance with the frozen protocol, `labels.csv` was not
edited: T5028 is recorded as `INVALIDATE`, with no replacement and zero
relabels. Metrics exclude it.

The only valid Delta attribution miss is T5034. Delta-Aware scoped the change
to the file-local `dictionary_fill` helper and returned NO/NO/NONE, instead of
preserving the public `Dictionary::Dictionary` exposure scope and returning
YES/YES/UNCHANGED. Final maintenance was still correctly NO.

## Required questions

1. **Where did the 16 development N4 errors occur?** Primarily impact-scope
   selection: E1 accounts for 7/16. There were also 3 E2 GapBefore and 4 E4
   delta/internal-growth failures; only 2 cases had the full target pattern.
2. **Why was Direct N4 FPR 43.75%?** It had no explicit S0 gap decision, so it
   directly attributed three historical gaps and four internal-only changes
   to the commit: 7/16 false positives.
3. **Did Delta improve GapBefore?** Yes. Blind N4 GapBefore is 18/19 = 94.74%.
   Direct has no explicit GapBefore field and correctly denied induction on
   only 13/19 valid N4 cases.
4. **Did it improve UNCHANGED attribution?** Yes: 18/19 = 94.74%, versus
   Direct's 13/19 correct `commit_induced=NO` N4 attributions.
5. **N4 target-pattern accuracy?** 18/19 = 94.74%.
6. **Is Delta N4 FPR below Direct?** Yes: 0/19 versus 6/19 (31.58%).
7. **Was positive recall retained?** Yes, and improved: 20/20 versus Direct's
   18/20.
8. **Were cross-scope/existing-gap misattributions reduced?** Yes. Six valid
   Direct N4 false positives became correct Delta maintenance decisions; no
   valid paired N4 case worsened.
9. **How many blind-test projects?** Four.
10. **Largest project share?** 25% in the frozen 40-case design; 25.64% among
    the 39 valid cases after one meshoptimizer invalidation.
11. **Was Ground Truth frozen before prediction?** Yes, about eight minutes
    before the first prediction, with immutable hashes.
12. **Any relabel after prediction?** No. There was one explicit invalidation
    and no replacement.
13. **Final criterion?** MODERATE GO. Performance clears the STRONG thresholds,
    but valid N4 count is 19, below the STRONG sample floor of 20.

## Artifact map

- `development-set/analysis/`: all 36 development case diagnoses.
- `development-set/runs/`: complete v1/v2 development I/O and metrics.
- `prompts/`: frozen Gap-Only, Direct, and Delta-Aware prompts/schemas.
- `new-data/`: broad candidates, conservative exclusions, selected audit.
- `frozen-ground-truth/`: immutable labels/evidence/manifests and invalidation.
- `frozen-inputs/`: 40 exact anonymous model inputs and hashes.
- `predictions/`: 120 predictions, full model I/O, logs, and run manifests.
- `results/`: per-case outcomes, metrics, paired comparison, and error analyses.
- `reports/`: development diagnosis, dataset construction, and validation.

Reproducible orchestration scripts are under `scripts/`. The model calls are
one-shot and the runners intentionally refuse to overwrite existing results.
