# False-negative analysis

Delta-Aware has zero maintenance false negatives on 20 valid positives.

Direct Evolution-Aware misses two positives:

| Case | Project | Direct judgment | Primary class | Delta-Aware |
|---|---|---|---|---|
| T5022 | libplist | Collapsed new `plist_mem_free` into the older uncovered export/free subsystem and rejected the new identity as non-material. | E1 impact identity/materiality | NO/YES/NEW, maintenance YES |
| T5024 | meshoptimizer | Rejected newly exported `meshopt_generateTangentsMikkT` because its initial implementation is a no-op stub. | E1 impact identity/materiality | NO/YES/NEW, maintenance YES |

These cases expose the boundary of the static oracle. The ground truth treats
new public entry exposure as an objective new gap even when the initial body is
small; Direct adds a separate current-behavior materiality test. T5024 is
therefore a deliberately hard, low-complexity positive, not evidence of
dynamic bug-finding capability.

Gap-Only also misses T5024 and T5033. For T5033 it argues that H0 can already
obtain arbitrary TTL state by parsing and writing DNS records, so the tiny new
`ares_dns_rr_set_ttl` direct entry is not material. Delta-Aware instead follows
the frozen identity rule: the public setter is absent in S0 and unexposed in
S1, hence NEW.
