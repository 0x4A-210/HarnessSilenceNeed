#!/usr/bin/env python3
"""Freeze all one-shot streams before any evaluator opens labels."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from common import ROOT, utc_now, write_json


METHODS = ["gap_only", "direct_evolution_aware", "delta_aware"]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    output = ROOT / "predictions" / "prediction_freeze_manifest.json"
    if output.exists():
        raise SystemExit("refusing to overwrite prediction freeze")
    config_path = ROOT / "frozen-experiment-config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    files = {}; starts = []; finishes = []; valid = failed = 0
    for method in METHODS:
        manifest_path = ROOT / "predictions" / f"run_manifest_{method}.json"
        prediction_path = ROOT / "predictions" / f"{method}.jsonl"
        pairs_path = ROOT / "predictions" / f"{method}_input_output_pairs.jsonl"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["status"] not in {"COMPLETE", "COMPLETE_WITH_FAILURES"} or manifest["attempt_count"] != 104:
            raise SystemExit(f"incomplete method: {method}")
        if manifest["ground_truth_files_read"] or manifest["h1_or_harness_diff_read"] or manifest["retries"] != 0:
            raise SystemExit(f"blindness/one-shot invariant failed: {method}")
        if manifest["dataset_hash"] != config["dataset_hash"] or manifest["input_hash"] != config["input_hash"]:
            raise SystemExit(f"frozen hash mismatch: {method}")
        starts.append(manifest["started_at"]); finishes.append(manifest["finished_at"])
        valid += manifest["valid_predictions"]; failed += manifest["failed_predictions"]
        for path in (manifest_path, prediction_path, pairs_path):
            files[str(path.relative_to(ROOT))] = digest(path)
    frozen_at = utc_now()
    value = {
        "status": "FROZEN_BEFORE_LABEL_REVEAL", "frozen_at": frozen_at,
        "methods": METHODS, "attempts_per_method": 104, "total_independent_attempts": 312,
        "valid_predictions": valid, "failed_predictions_retained": failed, "retries": 0,
        "ground_truth_files_read_by_runners": False, "h1_read_by_runners": False,
        "dataset_hash": config["dataset_hash"], "ground_truth_hash_reference": config["ground_truth_hash"],
        "input_hash": config["input_hash"], "config_sha256": digest(config_path),
        "first_prediction_started_at": min(starts), "last_prediction_finished_at": max(finishes),
        "file_sha256": files,
        "ordering": {
            "ground_truth_frozen_at": config["ordering"]["ground_truth_frozen_at"],
            "input_frozen_at": config["ordering"]["input_frozen_at"],
            "experiment_config_frozen_at": config["frozen_at"],
            "prediction_started_at": min(starts), "predictions_frozen_at": frozen_at,
            "label_reveal_evaluation_started_at": None,
        },
    }
    write_json(output, value)
    print(json.dumps({"status": value["status"], "valid": valid, "failed": failed,
                      "manifest_sha256": digest(output)}, sort_keys=True))


if __name__ == "__main__":
    main()
