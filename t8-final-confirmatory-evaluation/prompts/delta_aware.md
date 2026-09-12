You are evaluating whether one production-source commit creates a fuzz-harness
maintenance need. Use only the anonymous case below. Do not use tools, files,
the network, commit messages, developer harness changes, future behavior, or
outside knowledge.

Follow this order exactly and preserve one principal comparison scope:

1. Identify the smallest fuzz-relevant semantic unit introduced or changed by
   the diff. Use the mechanically supplied S0/S1 declaration context as the
   identity anchor when it belongs to the change. Do not combine it with an
   older sibling API, another module, or a general project-wide omission.
2. For that exact unit and exposure obligation, decide Gap(S0,H0).
3. For the identical unit and exposure obligation, decide Gap(S1,H0).
4. Compare the caller-visible harness obligations, not the amount of internal
   implementation.
5. Derive NEW, AGGRAVATED, UNCHANGED, REMOVED, or NONE and apply the fixed
   maintenance rule.

Identity rules:

- If the anchored public declaration/configuration/module is absent in S0 and
  introduced in S1, then its own GapBefore is false. Do not turn it into an
  AGGRAVATED old gap merely because H0 also omitted a related module in S0.
- If the same public declaration exists in S0 and S1 and unchanged H0 omits
  that callable/configuration/lifecycle path on both sides, its exposure gap is
  true before and after. A formerly constant/no-op getter or lifecycle method
  is still the same callable surface; new behavior inside it does not create a
  new call obligation. This comparison is UNCHANGED unless the commit changes
  how H0 must reach or control the API.
- If H0 already reaches the new behavior through an existing one-hop caller
  that supplies a new internal argument/configuration automatically, that
  internal caller-to-callee protocol is not a new H0 obligation. It cannot make
  an already-omitted direct-API gap AGGRAVATED.

A concrete new harness obligation means H0 itself must add an entry/call,
caller-supplied value or buffer, call-order transition, runtime/compile-time
configuration, or special input construction that was unnecessary in S0. More
LOC, new internal state, a replacement algorithm, validation/error handling,
CPU fast path, or state reset inside an existing omitted API is not sufficient.
Do not infer aggravation because a whole subsystem is omitted on both sides.

Use separate evidence and this default truth table:

- before=false, after=true  -> NEW
- before=true,  after=true  -> UNCHANGED
- before=true,  after=false -> REMOVED
- before=false, after=false -> NONE

AGGRAVATED is allowed only with concrete S0-versus-S1 evidence of a new H0
action or reduced same-scope reachability/control. Set maintenance_needed=true
only if explicit_failure=true or the delta is NEW/AGGRAVATED. Return exactly
one JSON object matching the schema, with separate S0 and S1 evidence.
