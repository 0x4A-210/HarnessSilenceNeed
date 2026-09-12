# Go / No-Go decision

## Verdict: NO-GO for a definitive unbiased main experiment

The prediction signal itself is encouraging and reaches the numeric MODERATE
GO band:

- valid silent positives: 17 (threshold >=15);
- Evolution-Aware silent recall: 82.35% (threshold >=60%);
- Evolution-Aware FPR: 0% (threshold <=10%);
- Gap-Only to Evolution-Aware FP reduction: 100%;
- all 14 valid silent TP passed the manual reason/evidence/attribution audit.

It is not STRONG GO because the valid silent-positive count is 17 rather than
20, even though recall, FPR, attribution, and explanation thresholds otherwise
pass.

More importantly, `task-3.md` defines any unstable ground-truth freeze as a
NO-GO condition. Three of 20 frozen silent labels were found invalid only after
prediction freeze. They were not relabeled and original metrics remain intact,
but their existence means this run cannot serve as the claimed final unbiased
main evaluation. The absence of any frozen N4 existing-gap negative prevents a
formal answer to a central failure-mode question, and 89.6% of valid cases come
from one project.

Therefore:

- **Model feasibility signal:** MODERATE GO.
- **This artifact as a final unbiased experiment:** NO-GO.

A subsequent final test would need a newly frozen replacement set with at
least three independently verified silent positives, an explicit N4
existing-gap negative stratum, and broader project representation. The current
predictions must not be reused to tune those replacement cases or prompts.
