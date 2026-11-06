# Development N4 failure taxonomy

The 16 valid Task-4 N4 cases are development data only. Every case has the
expected pattern `GapBefore=YES`, `GapAfter=YES`, `Delta=UNCHANGED`, and
`Maintenance=NO`.

## Direct-method diagnosis

| Primary outcome | Count | Cases | Meaning |
|---|---:|---|---|
| E1 — impact-scope error | 7 | N4002, N4006, N4015, N4016, N4018, N4019, N4020 | The model switched to an already-covered ordinary path or rejected the selected historical API gap. Final maintenance happened to be correct, but evolution attribution was not demonstrated. |
| E2 — GapBefore error | 3 | N4004, N4007, N4011 | The historical gap was treated as newly induced. |
| E4 — delta/internal-growth error | 4 | N4005, N4008, N4010, N4014 | New internal code, state, or optimization inside an already-omitted API was treated as aggravating the Harness obligation. |
| Fully correct target pattern | 2 | N4001, N4009 | The reason explicitly established an existing gap and `commit_induced=NO`. |

The largest diagnostic category is E1 (7/16, 43.75%). The observed Direct
N4 false positives, however, are exactly the three E2 cases plus four E4
cases: 7/16 = 43.75%. The seven E1 cases returned the right final maintenance
decision for the wrong or incomplete attribution path, which is why final
classification alone overstated method quality.

## Why explicit Before/After was needed

The Direct schema had only an S1 gap and a direct `commit_induced` judgment.
It therefore allowed the model to:

- find a historical omission and immediately associate it with new internal code;
- compare different API/subsystem scopes before and after;
- return `maintenance=false` after denying the real historical gap; and
- call internal implementation growth `AGGRAVATED` without identifying a new caller action.

Delta-Aware makes those shortcuts observable by fixing one identity scope,
requiring separate S0/H0 and S1/H0 evidence, and applying an explicit truth
table.

The detailed evidence for every case is under
`development-set/analysis/N4*.md`.
