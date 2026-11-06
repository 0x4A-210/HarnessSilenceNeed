# Error analysis

## E1 — Target miss

Top-5 misses ten exact targets: two positives (T5009, T5030) and eight N4s
(T5004, T5007, T5015, T5018, T5026, T5029, T5034, T5037). T5009/T5030 are
nevertheless classified YES through sibling new functions, so they remain
strict attribution errors rather than classification FNs.

At Top-1, target misses cause the three function-positive misses T5011, T5017,
and T5019. At Top-3/5, no function-positive FN is caused by target miss; the only
positive miss is non-function T5035.

## E2 — Target overgeneration

- T5029 (all modes): `numeric_service_to_port` is inferred as a new unreachable
  helper and yields NEW/YES, while the GT unit is the unchanged omitted
  `ares_getaddrinfo` surface.
- T5037 (Top-3/5): `ai_has_ipv4` is inferred as a new unreachable helper and
  yields NEW/YES; the GT unit is again the unchanged omitted
  `ares_getaddrinfo` surface.

These two function candidates produce the 10.53% Top-3/5 N4 FPR and are not a
consequence of the non-function score-guard deviation.

## E3 — Reachability error

No disagreement was observed for an exact target found by M1 versus M0, because
both use the same static engine. This is an internal consistency result, not an
independent soundness validation. Corpus evidence is supplementary and sparse.

## E4 — Existing-gap attribution error

Zero found exact N4 targets were attributed incorrectly. N4 target-pattern
accuracy is still only 42.11%/57.89%/57.89% at Top-1/3/5 because the exact unit
was often not selected.

## E5 — Non-function target

T5035's `SPNG_ENCODE_TO_BUFFER` is discovered but cannot be expressed by
function reachability. It is retained as NOT_APPLICABLE, never silently dropped.

## E6 — Indirect call

No Top-5 candidate met the frozen address-taken condition for UNKNOWN. The
artifacts retain unresolved call-token lists; lexical analysis cannot rule out
all indirect-dispatch errors, so zero observed E6 cases is not a general claim
that these projects contain no indirect calls.
