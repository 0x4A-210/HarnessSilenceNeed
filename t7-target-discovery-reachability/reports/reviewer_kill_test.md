# Reviewer kill-test answers

1. **Exact-target Reachability performance?** On 38 function targets: 19/19
   positive recall, 0/19 N4 FP, and 38/38 correct delta attribution. One config
   target is NOT_APPLICABLE, so ITT positive recall is 19/20 = 95% and overall
   applicability is 38/39 = 97.44%. This is an oracle-assisted M0.

2. **Automatic Target Discovery Top-1/3/5 recall?** Across all 39 targets:
   20/39 = 51.28%, 28/39 = 71.79%, 29/39 = 74.36%. For function/API targets:
   19/38 = 50.00%, 27/38 = 71.05%, 28/38 = 73.68%.

3. **How much does automated Reachability decline?** Versus M0's 100%
   complete-case function recall/0% FPR, M1 Top-1 is 94.12%/5.26%; Top-3/5 are
   100%/10.53%. Strict representable-target attribution falls from 100% to
   50.00%/71.05%/73.68%.

4. **Does N4 FPR remain near zero?** No. It is 5.26% at Top-1 and 10.53% at
   Top-3/5, versus 0% for M0 and M2.

5. **Which FPs come from wrong target discovery?** T5029 selects new helper
   `numeric_service_to_port`; T5037 Top-3/5 includes new helper `ai_has_ipv4`.
   The GT unit in both is the existing omitted `ares_getaddrinfo` surface.

6. **Which FNs come from target miss?** Top-1 function FNs T5011, T5017, and
   T5019 are target-selection misses. Top-3/5 have no target-miss function FN;
   their sole FN is non-function T5035. Top-5 misses positive exact targets
   T5009/T5030 but sibling candidates make their final class YES.

7. **Which case cannot function reachability express?** T5035,
   `SPNG_ENCODE_TO_BUFFER`, a compile/runtime option/configuration obligation.

8. **M1 ITT recall?** Top-1 16/20 = 80%; Top-3 and Top-5 19/20 = 95%.

9. **Applicability?** Top-1 36/39 = 92.31%; Top-3/5 38/39 = 97.44%.

10. **Median latency versus Delta-Aware?** M1 0.955 s versus M2 27.889 s;
    p90 is 1.402 s versus 39.627 s. M1 is about 29.2× faster by medians.

11. **Does it satisfy KILL?** No mode does. Top-1 fails recall, FPR, and
    applicability. Top-3/5 fail the N4-FPR requirement (10.53% > 5%).

12. **Where is Delta-Aware's independent value?** In selecting the principal
    semantic impact scope rather than any new changed helper, and in expressing
    non-function/configuration obligations. Once the exact function is known,
    deterministic reachability is already sufficient on this set.

13. **Continue pure Delta-Aware?** Retain Delta-Aware as the primary hypothesis
    for the next independent validation, but do not claim a final pure detector
    from this development-contaminated diagnostic set. Keep M1 as a mandatory
    baseline.

14. **Switch to Hybrid now?** No. Task 7 allows Hybrid only for MAJOR WEAKENING;
    the registered outcome is CONTINUE. A hybrid can be pre-registered later if
    independent data show complementary failures.

15. **Build a larger independent dataset?** Yes. Freeze sampling, target GT,
    rules, and evaluation before predictions; include more config/state and
    indirect-dispatch cases. This is necessary because all 39 cases were already
    part of method development.

Protocol caveat: the frozen scorer accidentally applies three function-only
bonuses to some non-function candidates. The outputs were not retuned after GT.
This affects Top-1 cleanliness but not the non-KILL conclusion, because the
decisive Top-3/5 FPs are function candidates.
