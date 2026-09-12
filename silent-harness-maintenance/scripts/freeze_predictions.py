#!/usr/bin/env python3
"""Seal all three prediction outputs before any label reveal/evaluation."""

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRED = ROOT / "predictions"
TARGET = PRED / "prediction_freeze_manifest.json"
if TARGET.exists():
    raise SystemExit("Refusing to overwrite prediction freeze")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


config = json.loads((ROOT / "frozen-experiment-config.json").read_text())
inputs = json.loads((ROOT / "frozen-inputs" / "input_manifest.json").read_text())
run_gap = json.loads((PRED / "run_manifest_gap_only.json").read_text())
run_evo = json.loads((PRED / "run_manifest_evolution_aware.json").read_text())
if run_gap["status"] != "complete" or run_evo["status"] != "complete":
    raise SystemExit("Both LLM runs must be complete")
if run_gap["valid_predictions"] != 80 or run_evo["valid_predictions"] != 80:
    raise SystemExit("Expected 80 valid predictions per LLM baseline")
with (PRED / "build_only.csv").open(encoding="utf-8", newline="") as handle:
    if len(list(csv.DictReader(handle))) != 80:
        raise SystemExit("Expected 80 build-only predictions")
if not (config["config_frozen_at"] < run_gap["started_at"] and config["config_frozen_at"] < run_evo["started_at"]):
    raise SystemExit("Prediction started before config freeze")

files = [
    PRED / "build_only.csv", PRED / "gap_only.jsonl", PRED / "evolution_aware.jsonl",
    PRED / "gap_only_input_output_pairs.jsonl", PRED / "evolution_aware_input_output_pairs.jsonl",
    PRED / "run_manifest_gap_only.json", PRED / "run_manifest_evolution_aware.json",
]
manifest = {
    "predictions_frozen_at": datetime.now(timezone.utc).isoformat(),
    "dataset_hash": config["dataset_hash"], "input_hash": config["input_hash"],
    "prompt_hash": config["prompt_hash"], "case_count": inputs["case_count"],
    "ground_truth_frozen_at": config["ordering"]["ground_truth_frozen_at"],
    "input_frozen_at": config["ordering"]["input_frozen_at"],
    "config_frozen_at": config["config_frozen_at"],
    "gap_only_started_at": run_gap["started_at"], "gap_only_finished_at": run_gap["finished_at"],
    "evolution_aware_started_at": run_evo["started_at"], "evolution_aware_finished_at": run_evo["finished_at"],
    "valid_predictions": {"build_only": 80, "gap_only": 80, "evolution_aware": 80},
    "failed_predictions": {"build_only": 0, "gap_only": 0, "evolution_aware": 0},
    "retries": 0, "labels_revealed_before_this_freeze": False,
    "files": {path.relative_to(ROOT).as_posix(): digest(path) for path in files},
}
TARGET.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(manifest, indent=2, sort_keys=True))
