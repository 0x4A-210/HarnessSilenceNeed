You are evaluating whether a source commit creates a fuzz-harness maintenance
need. Use only the anonymous case supplied below. Do not use tools, files, the
network, commit messages, developer harness changes, future behavior, or
outside knowledge.

First decide whether S1 + H0 has a material harness gap involving an entry
point, API protocol, state, configuration, input semantics, or attack surface.
Then compare S0 + H0 with S1 + H0 and decide whether this commit introduced or
materially aggravated that gap. A historical gap alone is not maintenance for
this commit. Refactoring, validation, error handling, and internal optimization
do not require maintenance when H0 still reaches the changed behavior with
adequate state and input control.

Set maintenance_needed to true only when gap_exists is true AND commit_induced
is YES. Return exactly one JSON object matching the required schema and ground
every claim in concrete identifiers visible in the case.
