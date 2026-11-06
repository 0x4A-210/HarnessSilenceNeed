You are evaluating whether one production-source commit creates a fuzz-harness
maintenance need. Use only the anonymous case below. Do not use tools, files,
the network, commit messages, developer harness changes, future behavior, or
outside knowledge.

Follow this order exactly and keep one stable comparison scope throughout:

1. Identify the commit's fuzz-relevant impact scope from the S0-to-S1 source
   diff. Anchor it in concrete files, functions, states, configurations, input
   semantics, or entry points. Do not search the rest of the project for an
   unrelated harness omission.
2. For that same scope, decide whether S0 + H0 has a material harness gap.
3. For that identical scope, decide whether S1 + H0 has a material harness gap.
4. Identify whether the commit creates a concrete new harness obligation: a
   new entry/call, caller-supplied argument or buffer, call-order transition,
   configuration action, compile-time enablement, or input construction that
   H0 did not need in S0.
5. Derive exactly one delta: NEW, AGGRAVATED, UNCHANGED, REMOVED, or NONE.
6. Apply the fixed final rule.

A harness gap concerns exposure or controllability, not the mere existence of
changed lines. More internal code, a replacement algorithm, validation, error
handling, a CPU fast path, or implementation state is not by itself an
aggravation. If an existing public entry/API is omitted by the unchanged H0 on
both sides and its caller-facing exposure requirement is unchanged, then the
gap existed before and after: classify UNCHANGED even when the commit changes
behavior inside that entry. Conversely, a genuinely new public entry, format,
configuration, state protocol, or caller obligation that H0 cannot exercise is
NEW (or AGGRAVATED when a demonstrably weaker same-scope gap already existed).

AGGRAVATED requires concrete comparative evidence that S1 adds a harness action
or reachability/control requirement absent in S0. Do not infer AGGRAVATED only
from added LOC, a changed file, additional internal branches, or the fact that
H0 omits the whole subsystem on both sides.

Use this truth table unless concrete aggravation/removal evidence is present:

- before=false, after=true  -> NEW
- before=true,  after=true  -> UNCHANGED
- before=true,  after=false -> REMOVED
- before=false, after=false -> NONE

Set maintenance_needed=true only if explicit_failure=true or delta_attribution
is NEW or AGGRAVATED. Otherwise set it false. Return exactly one JSON object
matching the schema. Give separate S0 and S1 evidence and do not collapse the
two judgments into one narrative.
