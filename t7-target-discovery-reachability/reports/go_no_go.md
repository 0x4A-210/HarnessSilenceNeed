# Kill-test decision

Decision: **CONTINUE**. The experiment does **not** KILL Delta-Aware and does not
meet the Task-7 definition of MAJOR WEAKENING. Therefore the optional Hybrid
branch was not run.

| Gate | Top-1 | Top-3 | Top-5 |
|---|---:|---:|---:|
| ITT recall ≥ 95% | 80% — fail | 95% — pass | 95% — pass |
| N4 FPR ≤ 5% | 5.26% — fail | 10.53% — fail | 10.53% — fail |
| Applicability ≥ 95% | 92.31% — fail | 97.44% — pass | 97.44% — pass |
| Median latency ≤ 27.889 s | 0.955 s — pass | pass | pass |
| Complexity reasonable | pass | pass | pass |
| All KILL conditions | **fail** | **fail** | **fail** |

The failure is substantively about commit impact scope and target selection.
When the exact function is supplied, the static reachability/attribution engine
is perfect on 38/38 representable cases. Automatic Top-5 exact-target recall is
only 29/39 overall and 28/38 for functions; broader selection recovers final
positive recall by accepting sibling targets, but creates the T5029/T5037 N4
false alarms and much lower strict attribution.

Delta-Aware's observed independent value in this diagnostic set is therefore
semantic selection of the principal comparison unit, plus handling a
configuration obligation. It is not evidence that its reachability reasoning is
intrinsically superior, nor is it a final unbiased performance estimate.

The disclosed non-function scoring deviation makes the formal Top-1 estimate
less clean. It does not rescue any KILL mode: Top-3/5 fail because of two
function-candidate FPs unaffected by that deviation. The correct next step is a
larger independently sampled and pre-registered dataset retaining M0, M1, and M2;
not post-GT retuning on these 39 cases.
