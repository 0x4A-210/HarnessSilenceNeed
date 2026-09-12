# False-negative analysis

Gap-Only had no FN on the audited stable subset. Evolution-Aware had one: C004,
libspng commit `c21b8299781e512ed485cefc02ab617ef0c97fe7`.

The commit moves `spng.h` under `spng/`. H0 still includes `../spng.h`, giving
the verified three-way pattern S0+H0=PASS, S1+H0=FAIL, S1+H1=PASS after H1
changes the include to `../spng/spng.h`.

The source diff represented the move as a very large deleted/added file. The
model focused on decoder and metadata reachability in the apparent added
implementation, concluded H0 already reached those paths, and overlooked the
include-path/build protocol. This is a context-representation failure, not a
failure to understand an explicit arity or symbol change.

The related C054 move was a TP, but its reason was also causally wrong: it called
streaming functionality newly introduced instead of citing H0's obsolete
`../src/spng.h` include. Source-layout moves are therefore the hardest observed
mechanism even when the final Boolean decision is right.
