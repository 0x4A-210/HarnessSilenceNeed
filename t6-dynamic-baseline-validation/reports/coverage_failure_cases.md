# Coverage and execution failure cases

## Measurement availability

The audited measurement state is 36 PASS and 3 BUILD_UNAVAILABLE.  The frozen
orchestrator's top-level manifest says DYNAMIC_UNAVAILABLE for all cases because
Docker-created root-owned temporary files raise a permission exception during
Python `TemporaryDirectory` cleanup.  That exception happens after successful
cases have written all 12 coverage records.  It is retained as an orchestration
defect, but it is not counted as a build/run/coverage failure.

For the 36 complete cases:

- 72/72 snapshot builds pass.
- 432/432 fuzz/corpus runs pass.
- 432/432 coverage exports pass and are valid gzip JSON.
- 36/36 cases have the expected six S0 and six S1 records.

## True unavailable cases

| Case | Label | Snapshots | Frozen failure | Coverage records |
|---|---|---|---|---:|
| T5030 | POSITIVE | S0 and S1 | BUILD_UNAVAILABLE | 0 |
| T5034 | N4 | S0 and S1 | BUILD_UNAVAILABLE | 0 |
| T5038 | POSITIVE | S0 and S1 | BUILD_UNAVAILABLE | 0 |

In each case, historical libplist compilation reaches `libplist.la`, but the
adapter's exact lookup for `libplist-2.0.a` returns empty because the old build
emits `libplist.a`.  The failure is a frozen adapter compatibility limitation,
not evidence of a commit-induced harness failure.  Because both snapshots
fail, Build-Only abstains rather than predicting YES.  Logs are retained under
`raw/logs/build/T503{0,4,8}_{s0,s1}.log`.

## Type A — normal overall coverage with a real silent need

At the 5-minute majority result, 15 executable positives have Overall Coverage
Delta = NO:

`T5001, T5008, T5009, T5011, T5014, T5016, T5019, T5022, T5024, T5025,
T5027, T5032, T5033, T5035, T5040`.

Examples:

- T5001 introduces `ares_queue_wait_empty`.  Line/branch/function deltas in
  repeat 1 are only -0.356pp/-0.276pp/-0.671pp, so overall monitoring says NO;
  the new target is present but unreachable, and Delta-Aware says YES.
- T5035 is a configuration obligation (`SPNG_ENCODE_TO_BUFFER`).  Its deltas
  are -0.030pp/-0.026pp/0pp.  Function Reachability correctly abstains because
  it is not a function, while Delta-Aware still returns YES.

This is direct evidence that degradation-style aggregate coverage is
insensitive to most silent maintenance needs in this set.

## Type B — coverage decline without maintenance need

T5036 is N4.  In 5-minute repeat 2 its line/function coverage falls
-2.527pp/-1.914pp, so Overall Coverage Delta emits a false YES.  In repeats 1
and 3, every line/branch/function delta is exactly 0pp and the result is NO.
Majority vote is correct, but the single false-positive repeat demonstrates
that a measured coverage decline is neither stable nor equivalent to a
current-commit maintenance need.

## Type C — existing gap

Function Reachability correctly says NO for all 18 executable N4 cases because
the audited target is already present in S0 and remains unreachable in S1.
T5005 is representative: `ares_queue_wait_empty` is present and unreached in
both snapshots.  Overall delta says NO, while Changed-Code Coverage sees 0/12
changed executable lines and 0/4 changed functions reached and incorrectly
says YES.  Nine N4 cases have this Changed-Code false-positive pattern:

`T5005, T5007, T5015, T5021, T5023, T5029, T5031, T5037, T5039`.

The changed-code metric detects an inadequacy but cannot tell whether it
predates the current commit.  Temporal attribution is the decisive feature.

## Function-reachability caution

No selected function is reached by H0 at any budget or repeat.  Five positive
and nine N4 cases also have zero mapped target functions in the instrumented
binary; their static source presence is known, while dynamic reachability is
false.  Consequently, the perfect complete-case classification is driven by
the target-conditioned S0/S1 presence distinction.  It is a valid execution of
the frozen rule, but an optimistic diagnostic upper bound rather than evidence
that fuzzing automatically discovers the relevant target.

The authoritative records are `results/execution_audit.csv`,
`results/execution_failures.csv`, `results/coverage_delta.csv`,
`results/changed_code_coverage.csv`, and `results/reachability.csv`.
