# Development gate summary

The development set contains the 16 valid N4 and 20 positive cases inherited
from Task 4. It is explicitly excluded from final blind-test estimates.

| Metric | Required | v1 | frozen v2 |
|---|---:|---:|---:|
| N4 GapBefore accuracy | >=80% | 81.25% | 100% |
| N4 GapAfter accuracy | >=80% | 87.50% | 100% |
| N4 delta accuracy | >=75% | 68.75% | 100% |
| N4 target-pattern accuracy | diagnostic | 68.75% | 100% |
| N4 FPR | <=15% | 18.75% | 0% |
| Positive NEW/AGGRAVATED recall | >=75% | 100% | 100% |
| Positive maintenance recall | >=75% | 100% | 100% |
| Output consistency | required | 100% | 100% |

v1 failed the gate. v2 passed every threshold, so the protocol permitted the
independent blind phase. The exact metrics and all model I/O are preserved in
`development-set/runs/v1/` and `development-set/runs/v2/`.

The frozen v2 prompt differs only by explicit identity preservation and
caller-visible-obligation rules derived from the documented development
failures. `prompts/delta_aware.md` is byte-identical to
`prompts/delta_aware_v2.md` (SHA-256
`726dc2fc1e0682e81a2dd84ae173e0c9413d3fffd570aadd1331333e7549e187`).
