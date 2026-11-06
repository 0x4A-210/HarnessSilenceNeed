# M1 deterministic rule freeze (v1)

Frozen before the 39-case formal M1 run. M1 receives only the row from
`dataset/cases.csv`, the two production snapshots/diff, and the S0 harness files
listed in that row. It does not receive a label, exact target, H1, harness diff,
coverage-selected target, or an LLM output.

## Extraction

- Production files are C/C++ sources and headers, excluding path components for
  tests, fuzzers, tools, examples, builds, generated code, and vendors.
- Functions whose S1 ctags extent intersects an added/changed production line
  are candidates (new or modified).
- Changed public header declarations also select a corresponding definition.
- Changed macros/enums/enumerators are retained as explicit non-function
  candidates. They are not coerced into functions.
- Universal Ctags supplies deterministic symbols/extents. Qualified names are
  normalized only for whitespace/operator spelling.

## Ranking

- +3 new public/exported function.
- +3 semantic identifier token: parser/decoder/encoder/reader/writer, protocol,
  query/queue, input processing, serialization, filtering, or mesh optimization.
- +2 changed public API.
- +2 new function directly called from a changed caller.
- +2 enum/state/config/macro candidate or handler.
- +1 modified function in a fuzz-relevant source path.
- +1 modified function already statically reachable from H0.
- -2 static/internal helper.
- -2 test-only helper (normally removed by production filtering).
- -2 obvious logging/formatting utility.
- Tie break: score descending, function before non-function, public before
  non-public, then source path, line, and symbol lexicographically.

## Static graph and attribution

- The graph is a conservative lexical direct-call graph. Nodes are ctags
  definitions. Calls are identifier tokens followed by `(`; ambiguous same-name
  definitions all receive an edge.
- Entry nodes are `LLVMFuzzerTestOneInput` definitions in unchanged H0. The same
  S0 harness source is combined with S0 and S1 production code respectively.
- A direct path is `STATIC_REACHABLE`; an existing symbol without a path is
  `STATIC_UNREACHABLE`. Address-taken evidence in reachable code without a direct
  path is `UNKNOWN` and is never silently treated as unreachable.
- New/absent-before plus unreachable-after is NEW/YES. Reachable-before to
  unreachable-after is AGGRAVATED/YES. Existing unreachable on both sides is
  UNCHANGED/NO unless both a public declaration and its signature changed.
  Reachable on both sides is NONE/NO. Uncertainty is ABSTAIN.
- For Top-k, any function candidate with YES yields YES; otherwise any function
  uncertainty yields ABSTAIN; otherwise function candidates yield NO. A set with
  no function candidate is NOT_APPLICABLE.

The pre-freeze smoke tests T5001/T5002 only checked execution mechanics. One
generic tokenization defect (`read` matching `thread`) was corrected before this
freeze. Pilot artifacts are excluded from all formal evaluation.
