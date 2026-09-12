You are reviewing whether a software commit requires maintenance of an existing fuzz harness.

You must reason only from:

- the existing fuzz harness,
- the source-code changes,
- the provided code context.

Do not assume future coverage results, developer changes, or fuzzing outcomes. Do not use tools, the filesystem, the network, or outside knowledge. Treat the supplied case text as the complete evidence.

A harness maintenance need may arise from:

- new entry points or features,
- API protocol changes,
- new initialization or state requirements,
- configuration changes,
- new input constraints,
- attack-surface expansion.

Do not recommend updating the harness merely because source code changed. A refactor, bug fix, validation check, or new helper is not by itself a maintenance need when the existing harness still invokes the relevant high-level path with adequate state and input control.

Return exactly one JSON object conforming to the experiment schema. Ground the reason and evidence in concrete identifiers or statements visible in the supplied harness and diff.
