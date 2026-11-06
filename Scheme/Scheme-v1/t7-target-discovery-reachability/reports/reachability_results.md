# Reachability and classification results

## M0 oracle upper bound

Source-level exact-target reachability is evaluable for all 38 function targets.
It obtains 19/19 positive recall and 0/19 N4 FPs, with 38/38 correct function
delta attributions. T5035 is a configuration target and is explicitly
NOT_APPLICABLE. Consequently, M0 ITT positive recall is 19/20 = 95%, while its
complete-case recall is 100%.

This M0 is the Task-7 static oracle and is distinct from Task 6's build-dependent
dynamic exact-target baseline. It uses GT target information and is not deployable.

## M1 automatic pipeline

| Mode | Complete-case recall | ITT recall | N4 FPR | Applicability | Strict attribution (function targets) |
|---|---:|---:|---:|---:|---:|
| Top-1 | 16/17 (94.12%) | 16/20 (80%) | 1/19 (5.26%) | 36/39 (92.31%) | 19/38 (50.00%) |
| Top-3 | 19/19 (100%) | 19/20 (95%) | 2/19 (10.53%) | 38/39 (97.44%) | 27/38 (71.05%) |
| Top-5 | 19/19 (100%) | 19/20 (95%) | 2/19 (10.53%) | 38/39 (97.44%) | 28/38 (73.68%) |

Top-3/5 trade target coverage for false alarms. Their N4 FPs are T5029 and
T5037. Top-1 has only T5029 as FP, but misses three function-positive decisions
and cannot represent the configuration positive.

Across the 104 Top-5 candidate slots, the before/after status pairs are:

- 42 NOT_PRESENT → STATIC_UNREACHABLE;
- 36 STATIC_UNREACHABLE → STATIC_UNREACHABLE;
- 17 non-function NOT_APPLICABLE pairs;
- 5 STATIC_REACHABLE → STATIC_REACHABLE;
- 4 NOT_PRESENT → STATIC_REACHABLE.

No selected candidate was promoted to UNKNOWN by the address-taken heuristic.
Unresolved external call tokens were retained in 87 candidate records, so the
absence of UNKNOWN must not be interpreted as a sound whole-program proof. The
lexical graph intentionally over-approximates ambiguous same-name direct calls
and under-approximates complex function-pointer dispatch.

## Dynamic supplement

Existing Task-6 corpus artifacts supplied 192 of 208 candidate-version rows.
Fifty-four rows mapped a symbol and eight observations had a positive execution
count (3 in S0, 5 in S1). The supplement changed zero primary decisions, by
design; it was generated only after M1 outputs were frozen.

## Latency

M1 median/p90 total case time is 0.955/1.402 seconds; Delta-Aware's frozen
inference duration is 27.889/39.627 seconds. M1 median/p90 peak RSS is
23,552/28,702 KiB. Delta-Aware process memory, tokens, and monetary cost were
not exposed by the Task-5 CLI artifacts and are reported as NOT_EXPOSED rather
than estimated.
