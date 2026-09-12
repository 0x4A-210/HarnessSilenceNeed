# Ground-truth audit

## Counterfactual verification

All 80 frozen cases were classified before model prediction using S0+H0,
S1+H0, and S1+H1. The original strata satisfy the expected build/runtime
patterns:

- 20 frozen silent positives: all six build/runtime fields PASS.
- 10 VP1 positives: S0+H0 PASS/PASS, S1+H0 build FAIL, S1+H1 PASS/PASS.
- 50 negatives: all six build/runtime fields PASS.

Wuffs targets were compiled directly from historical trees with parent H0
overlaid onto S1 and executed on deterministic inputs. Mbed TLS cases used the
historical in-tree build and target. Solidity used three component probes: real
historical `EVMVersion.h` plus the exact H0/H1 version vector; real historical
`YulString.h` plus exact reset-call presence; and real historical
`OptimiserSettings.h` plus exact optimizer-mode call presence. Commands,
diagnostics, exit codes, and observations are retained in the detailed CSVs.

N223 is a new-target case, so its H0 counterfactual is portfolio-level. A
pre-existing GIF target builds/runs at both S0 and S1; the new JSON target
builds/runs at S1+H1. This construction was technically successful but its
label was later invalidated on evolution-attribution grounds.

## Coverage and reachability

Changed-code coverage uses GCC 13/gcov and only S1 added/modified lines that
gcov recognizes as executable in either H0 or H1. Wuffs measurements use one
fixed 128-input corpus. N128 uses the real production header in a component
coverage probe. Coverage was numeric for 15/20 originally frozen silent cases
and 14/17 valid silent cases. The three valid `NOT_MEASURED` cases are N071,
N116, and N132; their labels use dynamic state/configuration observations, not
estimated coverage.

Coverage is not treated as the only admissible evidence. N202 and N216 have no
coverage delta but objective early-return/oracle evidence; N228 and N250 have
semantic-domain/configuration evidence. Every unmeasured value is explicitly
`NOT_MEASURED`.

## Original frozen taxonomy

| Type | Frozen | Valid after invalidation |
|---|---:|---:|
| VP2 | 1 | 1 |
| VP3 | 6 | 4 |
| VP4 | 11 | 10 |
| VP5 | 2 | 2 |
| VP1 | 10 | 10 |

N071 is retained as a boundary-case VP4: the observable repository IDs
accumulate in S0+H0 and S1+H0, but the reset API, reset callbacks, and dialect
cache invalidation protocol are introduced only by S1; H0 cannot exercise that
new reset/rebuild transition, while H1 does. This interpretation and the
component-level nature of its evidence should be retained in any sensitivity
analysis.

## Post-freeze invalidations

The original label files were not edited. After predictions were frozen and
labels revealed, complete manual re-audit found three serious label defects:

- N223 / C015: the JSON decoder gap predates the source change; newly exposed
  size constants do not objectively aggravate it.
- N231 / C017: the CBOR decoder gap likewise predates the source change.
- N234 / C044: old quirk identifiers remain aliases for the S1 numeric modes,
  and H1's removal of a selector did not establish recovery; measured changed
  coverage actually fell 32/42 to 27/42.

They are recorded as `INVALID`, never converted to negatives, and omitted from
valid main metrics. Original 80-label results remain under the
`results/frozen_label_*` prefix. Because invalidation occurred only after
prediction, it is an experimental-integrity failure, not merely a change in
sample size.
