# Next Experiment — Delta-Aware vs. Dynamic Coverage-Based Detection

This artifact implements the protocol supplied in
[`../task-6.md`](../task-6.md). The canonical protocol is retained unchanged
there; its SHA-256 is frozen in `experiment_config.json` before formal runs.

Phase A is a diagnostic kill test over the 39 valid Task-5 cases. Existing
Delta-Aware prompts and predictions are read-only inputs. Phase B is permitted
only if the Phase-A decision is `CONTINUE`.
