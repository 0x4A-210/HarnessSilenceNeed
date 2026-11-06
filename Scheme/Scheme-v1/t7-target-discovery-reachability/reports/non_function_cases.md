# Non-function applicability

Ground Truth contains one non-function case and no state-only case:

| Case | Project | Label | Exact target | Discovery | Function reachability |
|---|---|---|---|---|---|
| T5035 | libspng | POSITIVE | `SPNG_ENCODE_TO_BUFFER` | Top-1 hit | NOT_APPLICABLE |

M1 correctly emits an explicit non-function candidate for the new configuration
flag instead of fabricating a function mapping. Top-3/5 also contain existing
functions such as `spng_set_option`, but evaluation does not allow these unrelated
functions to make the known configuration obligation “applicable.” Hence T5035
is an ITT miss for M0/M1 and is the only Top-3/5 positive miss.

M2 Delta-Aware handles the semantic/configuration obligation and predicts NEW /
maintenance YES. This case is direct evidence that target discovery and function
reachability applicability are different metrics.

Several function-target cases also contain changed enum/macro candidates. Their
presence is not itself an applicability failure, although the disclosed frozen
scorer type-guard deviation over-ranks some of them.
