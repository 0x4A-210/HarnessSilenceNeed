# False-negative analysis

Evolution-Aware has three FN among 17 valid silent positives. Gap-Only has two.

| Case | Commit candidate | Type | Why Evolution-Aware missed it |
|---|---|---|---|
| C002 | N216 | VP5 | It saw the new `not_enough_data` check as already reachable and observable, but missed that H1 moves the dirty-rectangle invariant oracle before status handling so the newly changed error state is validated. |
| C037 | N207 | VP2 | It concluded H0's image-config-derived exact-width buffer remained behaviorally adequate and dismissed direct exposure of the newly implemented `decoder.workbuf_len`; measured changed-code coverage was 1/4 vs 4/4. |
| C038 | N185 | VP3 | It correctly recognized H0's manual aggregate construction as behavior-equivalent, but the frozen definition counts direct exposure of the new public reader/writer helpers; measured coverage was 0/20 vs 20/20. |

The C037 and C038 errors expose a real definition boundary: a model optimized
for “material behavior” may reject convenience/public-API exposure cases even
when the frozen taxonomy labels any new public entry not reached by H0 as a
maintenance need. Their evidence is grounded; their final attribution differs
from the frozen rule.

C002 is the clearest semantic FN. It requires connecting a production
error-path change to an oracle whose placement relative to status handling
determines whether the post-error state is checked. This is cross-statement
state/oracle reasoning rather than missing context.

Three additional frozen-label FN (C015/N223, C017/N231, C044/N234) are not
counted: full post-freeze re-audit marked their ground truth `INVALID`. In all
three, the model's rejection helped expose the ground-truth defect; treating
them as model errors would be misleading.
