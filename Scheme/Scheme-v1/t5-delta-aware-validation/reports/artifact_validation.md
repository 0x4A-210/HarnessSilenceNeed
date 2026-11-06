# Artifact validation

Status: **PASS** (21/21 checks passed).

| Check | Result | Detail |
|---|---|---|
| ground truth status | PASS | FROZEN |
| 40 immutable labels | PASS | labels=40, evidence=40 |
| ground-truth file hashes | PASS | labels=d19dc6a25c98ed6acadcc2e0a43809f0f7ad3eb18dbcef83f6c78c1380862bbb, evidence=de88d09a4ec123748f3c0f07036331443b7ba5028ba37b166e68d481fc6235a3 |
| ground-truth composite hash | PASS | 6b5513fa02af4313e1d2ee1e9fc68f61a0d236d8a1a87bc842cf2a283f759683 |
| post-freeze labels unchanged | PASS | d19dc6a25c98ed6acadcc2e0a43809f0f7ad3eb18dbcef83f6c78c1380862bbb |
| invalidation without relabel | PASS | invalidations=1, relabels=0 |
| 40 frozen input hashes | PASS | cases=40 |
| input composite hash | PASS | 7c55fd860e9cee127087de9ae65a89c87e95dd4dfcf14900bdcf0b7a0aa4caf8 |
| anonymous input template | PASS | no case commit IDs or oracle field names; required H0/diff sections present |
| frozen prompt/schema hashes | PASS | files=6 |
| baseline prompt provenance | PASS | Gap-Only and Direct are byte-identical to Task-4 prompts |
| Delta prompt provenance | PASS | 726dc2fc1e0682e81a2dd84ae173e0c9413d3fffd570aadd1331333e7549e187 |
| three complete prediction streams | PASS | valid predictions=120, failures=0 |
| full model I/O hashes | PASS | 40 input/output pairs per method |
| runner blindness and zero retries | PASS | all manifests ground_truth_files_read=false, retries=0 |
| prediction-freeze hashes | PASS | files=9 |
| freeze chronology | PASS | GT 2026-09-10T10:34:05.846810Z < input 2026-09-10T10:36:47.600835Z < config 2026-09-10T10:40:59.002606Z < prediction 2026-09-10T10:42:00.066947Z |
| selected commit independence | PASS | 40 unique selected SHAs; zero exact overlap with prior exclusions |
| no Harness changes | PASS | 40/40 changed_harness_file_count=0 and complete-H0 target count=0 |
| evaluation denominator | PASS | valid=39, N4=19, positive=20 |
| reported decision | PASS | MODERATE GO |

Validation is hash-based and does not rerun the one-shot model predictions.
