# False-positive and corrected-FP analysis

On the 39 valid cases, Delta-Aware has no maintenance false positive. Direct
Evolution-Aware has six N4 false positives; Delta-Aware corrects all six and
introduces no paired N4 regression (McNemar exact p = 0.03125).

| Case | Project | Direct failure | Primary class | Delta-Aware result |
|---|---|---|---|---|
| T5004 | meshoptimizer | Treated a new internal degenerate-face grouping condition inside the already-omitted `meshopt_generateNormals` API as a new input obligation. | E4 delta error | YES/YES/UNCHANGED, maintenance NO |
| T5013 | c-ares | Treated moved lock boundaries inside already-omitted `ares_reinit` as an aggravated Harness lifecycle gap. | E4 delta error | YES/YES/UNCHANGED, maintenance NO |
| T5015 | libspng | Treated replacement of `compress2` with internal `deflate` state as a new caller configuration even though no caller-visible route/control changed. | E4 delta error | YES/YES/UNCHANGED, maintenance NO |
| T5026 | libplist | Treated a pass-by-reference repair in `array_fill` as a newly induced call obligation for the pre-existing omitted C++ Array API. | E4 delta error | YES/YES/UNCHANGED, maintenance NO |
| T5034 | libplist | Treated the same pass-by-reference repair in `dictionary_fill` as aggravating the omitted C++ Dictionary API. | E4 delta error | Maintenance NO, but NONE rather than UNCHANGED |
| T5037 | c-ares | Treated new internal AF_UNSPEC retry-state logic inside already-omitted `ares_getaddrinfo` as a new H0 state protocol. | E4 delta error | YES/YES/UNCHANGED, maintenance NO |

T5034 is the one valid Delta attribution error. Delta-Aware selected the
file-local helper `dictionary_fill` as the principal unit instead of preserving
the mechanically anchored public `Dictionary::Dictionary` exposure scope. It
therefore returned NO/NO/NONE. This is primarily E1 (impact-scope error), with
downstream E2/E3 errors. Its final maintenance decision remained correct, but
it failed the required N4 target pattern.

T5028 is excluded, not counted as a model FP: both Direct and Delta-Aware
recognized its actual caller-visible stride expansion. The defect was in the
frozen N4 label, and the case was invalidated without relabeling.
