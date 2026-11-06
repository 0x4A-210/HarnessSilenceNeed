#!/usr/bin/env python3
"""Freeze all three prediction streams before labels are opened by evaluation."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
METHODS = ["gap_only", "direct_evolution_aware", "delta_aware"]
OUTPUT = ROOT / "predictions" / "prediction_freeze_manifest.json"


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise SystemExit("refusing to overwrite frozen predictions")
    config = json.loads((ROOT / "frozen-experiment-config.json").read_text(encoding="utf-8"))
    files: dict[str, str] = {}
    starts: list[str] = []
    finishes: list[str] = []
    for method in METHODS:
        manifest_path = ROOT / "predictions" / f"run_manifest_{method}.json"
        prediction_path = ROOT / "predictions" / f"{method}.jsonl"
        pairs_path = ROOT / "predictions" / f"{method}_input_output_pairs.jsonl"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["status"] != "complete" or manifest["valid_predictions"] != 40 or manifest["failed_predictions"] != 0:
            raise SystemExit(f"incomplete method: {method}")
        if manifest["ground_truth_files_read"] is not False or manifest["retries"] != 0:
            raise SystemExit(f"blindness invariant failed: {method}")
        if manifest["dataset_hash"] != config["dataset_hash"] or manifest["input_hash"] != config["input_hash"]:
            raise SystemExit(f"frozen hash mismatch: {method}")
        starts.append(manifest["started_at"]); finishes.append(manifest["finished_at"])
        for path in (manifest_path, prediction_path, pairs_path):
            files[str(path.relative_to(ROOT))] = digest(path)
    frozen_at = now()
    value = {
        "status": "FROZEN_BEFORE_LABEL_REVEAL", "frozen_at": frozen_at,
        "methods": METHODS, "prediction_count_per_method": 40, "failed_predictions": 0,
        "total_independent_predictions": 120, "retries": 0, "ground_truth_files_read_by_runners": False,
        "dataset_hash": config["dataset_hash"], "ground_truth_hash_reference": config["ground_truth_hash"],
        "input_hash": config["input_hash"], "config_sha256": digest(ROOT / "frozen-experiment-config.json"),
        "first_prediction_started_at": min(starts), "last_prediction_finished_at": max(finishes),
        "file_sha256": files,
        "ordering": {
            **config["ordering"], "prediction_started_at": min(starts),
            "predictions_frozen_at": frozen_at, "label_reveal_evaluation_started_at": None,
        },
    }
    OUTPUT.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": value["status"], "frozen_at": frozen_at,
                      "total_independent_predictions": 120, "manifest_sha256": digest(OUTPUT)}))


if __name__ == "__main__":
    main()
