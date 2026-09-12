# Target discovery results

M1 v1 extracted candidates only from the production S0→S1 diff, ranked them
with the frozen transparent score, and did not receive GT targets. All metrics
below were computed after the 39 JSON outputs were frozen.

| Scope | n | Top-1 | Top-3 | Top-5 |
|---|---:|---:|---:|---:|
| All targets | 39 | 20 (51.28%) | 28 (71.79%) | 29 (74.36%) |
| Function/API | 38 | 19 (50.00%) | 27 (71.05%) | 28 (73.68%) |
| Positive function/API | 19 | 11 (57.89%) | 16 (84.21%) | 17 (89.47%) |
| N4 function/API | 19 | 8 (42.11%) | 11 (57.89%) | 11 (57.89%) |
| State/config/non-function | 1 | 1 (100%) | 1 (100%) | 1 (100%) |

There are no state-only targets, so state-only recall is undefined rather than
zero. The only non-function target, T5035 `SPNG_ENCODE_TO_BUFFER`, is rank 1.
Discovery success does not make function reachability applicable to it.

Top-5 misses ten exact targets:

- Positive: T5009 `ares_search_dnsrec`; T5030 `plist_string_val_compare`.
- N4: T5004 `meshopt_generateNormals`, T5007 `spng_encode_image`, T5015
  `spng_set_text`, T5018/T5026 `Array::Array`, T5029/T5037
  `ares_getaddrinfo`, and T5034 `Dictionary::Dictionary`.

The positive target misses at T5009 and T5030 still produce YES because sibling
new functions are selected. Those are classification TPs but strict attribution
failures—exactly why target recall must be reported separately from final recall.

The N4 target-pattern accuracy is 8/19 (42.11%) at Top-1 and 11/19 (57.89%) at
Top-3/5. Every automatically found N4 exact target received the correct
existing-unreachable-both/UNCHANGED/NO pattern; the loss comes from target misses,
not the before/after rule on a found exact target.

The frozen scorer has a disclosed type-guard deviation: several function-only
bonuses also applied to macros/enums. Formal rankings are retained unchanged;
see `results/protocol_conformance.csv`.
