# Reachability raw evidence

Function-reachability decisions are derived deterministically from the
per-function counters and source regions retained in
`../coverage/<case>/<version>/<budget>_r<repeat>.json.gz`, together with the
pre-execution source anchors in `../../dataset/target_anchors.csv`.

No separate runtime trace was collected and no H1 result was synthesized.
The normalized derivation is written to `../../results/reachability.csv` by
`../../scripts/measure_reachability.py`.
