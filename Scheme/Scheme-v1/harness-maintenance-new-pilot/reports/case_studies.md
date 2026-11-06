# Case studies

## True positives

### C002 — meshoptimizer version protocol

- Source evolution: encoder version 0xe becomes version 1 and S1 rejects values
  greater than 1.
- H0: selects 0xe for four of five level choices.
- Gap/attribution: most S1 executions assert or reject before round-trip work;
  the same value was valid in S0.
- Counterfactual: H1 changes 0xe to 1.
- Prediction: both baselines YES; Evolution-Aware explicitly compared the old
  and new assertions.
- Root cause: correct configuration-value and shallow-execution reasoning.

### C007 — Wuffs status type removal

- Source evolution: codec-specific status typedefs are removed for the base
  status type.
- H0: declares `wuffs_gif__status` and `wuffs_zlib__status`.
- Gap/attribution: S0+H0 compiles; S1+H0 does not.
- Counterfactual: H1 uses `wuffs_base__status`; S1+H1 compiles.
- Prediction: Evolution-Aware YES, with the exact removed identifiers.
- Root cause: correct typed API-compatibility reasoning.

### C010 — c-ares symbol-family rename

- Source evolution: internal buffer symbols change from `ares__buf_*` to
  `ares_buf_*`.
- H0: directly uses the old header, type, and functions.
- Gap/attribution: three-way compile is PASS/FAIL/PASS.
- Counterfactual: H1 replaces the entire used symbol family.
- Prediction: Evolution-Aware YES at 99 confidence.
- Root cause: exact symbol mapping made attribution easy.

### C029 — c-ares URI reply parser

- Source evolution: adds `ares_parse_uri_reply` and URI record parsing.
- H0: invokes the other reply parsers but has no URI call.
- Gap/attribution: the new entry did not exist at S0 and is directly unreachable
  from H0.
- Counterfactual: H1 adds the parser call and cleanup.
- Prediction: Evolution-Aware YES with correct allocation/length/error paths.
- Root cause: correct new-entry exposure reasoning.

### C050 — libspng ancillary CRC-discard state

- Source evolution: ancillary CRC discard becomes default and introduces
  text/sPLT rollback paths.
- H0: always overrides both CRC actions with `SPNG_CRC_USE`.
- Gap/attribution: H0 suppresses the S1-only configuration/state behavior.
- Counterfactual: H1 makes `SPNG_CRC_DISCARD` fuzz-selectable.
- Prediction: Evolution-Aware YES and identifies `text_undo`/`splt_undo`.
- Root cause: correct configuration-controlled reachability reasoning.

### C054 — correct decision, wrong reason

- Source evolution: production files move out of `src/`.
- H0: still includes `../src/spng.h`.
- Counterfactual: PASS/FAIL/PASS after H1 uses `../spng.h`.
- Prediction: YES, but says a new streaming implementation is uncovered.
- Root cause: Git represented a move as file addition/deletion; the model found
  grounded identifiers but drew the wrong causal story. Counted TP, failed the
  reason-correct audit.

## False positives

### C005 — existing barcode gap (Gap-Only FP)

- Source evolution: adds error checking around an existing crossing-distance
  computation; concurrent H1 changes the image input format.
- H0/gap: no barcode-crossing NUMA path, but that absence predates S1.
- Prediction: Gap-Only YES; Evolution-Aware NO.
- Root cause: Gap-Only correctly sees incompleteness but cannot attribute it.

### C031 — historical harness API misuse (Gap-Only FP)

- Source evolution: documentation is corrected to describe an existing integer
  status return.
- H0/gap: historically treats that status as a `PIX*` and destroys it.
- Prediction: Gap-Only YES; Evolution-Aware NO.
- Root cause: attribution recognizes that the implementation/protocol did not
  change in this commit.

### C040 — historical build failure (both-baseline FP)

- Source evolution: removes private declarations from `common.h`.
- H0/gap: S1 adds a missing declaration, but S0+H0 already fails because the C
  header defines uninitialized const arrays in a C++ unit.
- Counterfactual: S0+H0=FAIL, S1+H0=FAIL, S1+H1=PASS.
- Prediction: both YES.
- Root cause: Evolution-Aware noticed only the new diagnostic and failed to
  reason about the pre-existing zero-adequacy state.

### C059 — historical Jansson deep-copy gap (Gap-Only FP)

- Source evolution: internal expression/refactor changes in copy/dump logic.
- H0/gap: parser/serializer H0 does not construct circular graphs or directly
  call deep-copy paths, but this was already true in S0.
- Prediction: Gap-Only YES; Evolution-Aware NO.
- Root cause: successful historical-gap attribution.

### C064 — historical libplist writer gap (Gap-Only FP)

- Source evolution: changes existing real-number size estimation/formatting.
- H0/gap: parser-only targets do not invoke the writer path; that gap predates
  the commit.
- Prediction: Gap-Only YES; Evolution-Aware NO.
- Root cause: successful distinction between current incompleteness and current
  maintenance need.

## All false negatives

### C004 — libspng header relocation

- Source evolution: moves `spng.h` to `spng/spng.h`.
- H0: includes the old `../spng.h` path.
- Gap/attribution: build failure is introduced exactly at S1.
- Counterfactual: S0+H0=PASS, S1+H0=FAIL, S1+H1=PASS.
- Prediction: Gap-Only YES for an unrelated metadata-gap story;
  Evolution-Aware NO.
- Root cause: the large move diff distracted from the build/include protocol.
