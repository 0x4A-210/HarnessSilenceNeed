# Development positive attribution analysis

All 20 Task-4 positive cases are development-only and have the frozen target
pattern `GapBefore=NO`, `GapAfter=YES`, `Delta=NEW`, and `Maintenance=YES`.
The prior Direct method retained all 20 positives, but this did not test its
ability to distinguish `NEW` from an older sibling gap.

## Delta-Aware development behavior

| Version | GapBefore | GapAfter | Exact NEW | Maintenance recall |
|---|---:|---:|---:|---:|
| v1 | 18/20 (90%) | 20/20 (100%) | 18/20 (90%) | 20/20 (100%) |
| v2 frozen | 20/20 (100%) | 20/20 (100%) | 20/20 (100%) | 20/20 (100%) |

In v1, P006 (`hasher.checksum_u64`) and P018
(`QUIRK_JUST_RAW_THUMBHASH`) were incorrectly labeled `AGGRAVATED`. In both
cases the new declaration/configuration was absent in S0, but the model mixed
it with an older sibling subsystem omitted by H0. The smallest v2 change made
the mechanically selected declaration/configuration the principal identity:
when that identity is absent in S0 and introduced in S1, its own GapBefore is
false. It also forbids an automatically supplied internal argument from being
treated as a new H0 obligation.

This tuning used all development labels and is not evidence of
generalization. The v2 prompt was frozen before the new multi-project blind
cases were materialized or predicted.

Detailed per-case analyses are under `development-set/analysis/P*.md`.
