# Dataset construction

## Mining and independence

The miner searched 16 local OSS-Fuzz C/C++ project histories. It found 300
source-plus-harness path-level co-evolution hits before exclusion and removed
all commits present in the earlier 60-case development set, the original 13
degradation events, pre-test/holdout material, and prompt/rule-development
candidate files (162 unique excluded commits). The remaining independent pool
contains 250 candidates from 7 projects:

| Project | Raw candidates |
|---|---:|
| mbedtls | 38 |
| proj4 | 9 |
| selinux | 8 |
| solidity | 105 |
| tpm2-tss | 12 |
| trafficserver | 9 |
| wuffs | 69 |
| **Total** | **250** |

An additional 33 independent Wuffs source-only negative controls were mined by
a separate fixed rule. They all have a byte-identical H0/H1 harness blob and
passed S0+H0, S1+H0, and S1+H1 native build/run checks. One initially selected
control was removed before freeze because an unrelated pre-existing API
inconsistency broke all three builds; it is recorded in `data/excluded_cases.csv`.

## Frozen strata

The original randomly assigned 80-case freeze contained:

| Stratum | Cases |
|---|---:|
| Silent positive | 20 |
| Explicit VP1 | 10 |
| Negative—source/harness co-evolution | 17 |
| Negative—source-only control | 33 |
| **Total** | **80** |

Its project distribution was Wuffs 72, Solidity 4, and Mbed TLS 4. Every case
used a unique commit. Case IDs were assigned by `random.Random(20260910)` before
blind inputs were generated.

The post-freeze audit marked N223, N231, and N234 `INVALID` without assigning
replacement labels. The valid analysis set therefore contains 77 commits:
Wuffs 69, Solidity 4, Mbed TLS 4; 17 silent positives, 10 VP1, and 50 negatives.

## Selection and context rules

The ground-truth candidate selection used no predictions. Blind input creation
used one uniform rule:

1. Include the complete parent-revision H0 file for every changed harness path
   that exists at the parent.
2. If no changed target path exists at H0 (new-target case), include the
   lexicographically first pre-existing non-fuzzlib fuzzer and explicitly record
   the absent path.
3. Include the complete production diff for every audited source path using
   `git diff --full-index --function-context`, without truncation.
4. Include no H1, harness diff, commit message, dynamic evidence, label, or
   case-specific supplementary context.

The 80 frozen files total 4,384,023 bytes; the smallest is 5,858 bytes and the
largest 302,642 bytes. Their aggregate hash is in
`frozen-inputs/input_manifest.json`.

## Important representativeness limitations

- The valid set is 89.6% Wuffs (69/77), so project-specific structure may
  inflate both detection and attribution performance.
- All 17 hard negatives are co-evolution cases, but none has the frozen N4
  existing-gap label; the 33 additional negatives are source-only controls.
- Solidity cases use exact-history component probes due unavailable historical
  full toolchains. They are not full OSS-Fuzz container reproductions.
- Mining found a broad 7-project pool, but reproducible counterfactual evidence
  narrowed the final set to 3 projects.
