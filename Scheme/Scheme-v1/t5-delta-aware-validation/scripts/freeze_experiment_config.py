#!/usr/bin/env python3
"""Freeze prompts, schemas, inputs, and model parameters before prediction."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "frozen-experiment-config.json"
MODEL = "gpt-5.6-sol"
EFFORT = "high"


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if OUTPUT.exists():
        raise SystemExit("refusing to overwrite frozen experiment config")
    predictions = ROOT / "predictions"
    if predictions.exists() and any(predictions.iterdir()):
        raise SystemExit("predictions already exist")
    inputs = json.loads((ROOT / "frozen-inputs" / "manifest.json").read_text(encoding="utf-8"))
    truth = json.loads((ROOT / "frozen-ground-truth" / "manifest.json").read_text(encoding="utf-8"))
    if inputs["status"] != "FROZEN" or truth["status"] != "FROZEN":
        raise SystemExit("ground truth and inputs must both be frozen")
    files = {
        "gap_only_prompt": ROOT / "prompts" / "gap_only.md",
        "gap_only_schema": ROOT / "prompts" / "gap_only_schema.json",
        "direct_evolution_aware_prompt": ROOT / "prompts" / "direct_evolution_aware.md",
        "direct_evolution_aware_schema": ROOT / "prompts" / "direct_evolution_aware_schema.json",
        "delta_aware_prompt": ROOT / "prompts" / "delta_aware.md",
        "delta_aware_schema": ROOT / "prompts" / "delta_aware_schema.json",
    }
    codex = shutil.which("codex")
    if not codex:
        raise SystemExit("codex executable not found")
    version = subprocess.run([codex, "--version"], capture_output=True, text=True, check=True).stdout.strip()
    frozen_at = now()
    value = {
        "status": "FROZEN", "config_frozen_at": frozen_at,
        "model": MODEL, "model_version": "service alias; exact backend revision not exposed by CLI",
        "reasoning_effort": EFFORT, "temperature": None, "max_tokens": None,
        "concurrency": 4, "timeout_seconds": 900, "retries": 0, "one_shot": True,
        "codex_cli_version_at_freeze": version,
        "system_prompt": "Codex built-in system prompt; isolated with --ignore-user-config --ignore-rules",
        "protocol": "one fresh ephemeral process per case and method; unique empty read-only working directory; runner reads only one fixed prompt/schema and one frozen input",
        "methods": {
            "gap_only": {"prompt": "prompts/gap_only.md", "schema": "prompts/gap_only_schema.json"},
            "direct_evolution_aware": {"prompt": "prompts/direct_evolution_aware.md", "schema": "prompts/direct_evolution_aware_schema.json"},
            "delta_aware": {"prompt": "prompts/delta_aware.md", "schema": "prompts/delta_aware_schema.json"},
        },
        "file_sha256": {str(path.relative_to(ROOT)): digest(path) for path in files.values()},
        "prompt_provenance": {
            "gap_only": "byte-identical Task-4 baseline prompt/schema; no Task-5 tuning",
            "direct_evolution_aware": "byte-identical Task-4 direct baseline prompt/schema; no Task-5 tuning",
            "delta_aware": "byte-identical delta_aware_v2.md that passed the 36-case development gate; frozen before blind prediction",
        },
        "development_gate_metrics_sha256": digest(ROOT / "development-set" / "runs" / "v2" / "metrics.json"),
        "dataset_hash": truth["dataset_hash"], "ground_truth_hash": truth["ground_truth_hash"],
        "input_hash": inputs["input_hash"], "context_selection_version": inputs["context_selection_version"],
        "ordering": {
            "ground_truth_frozen_at": truth["frozen_at"], "input_frozen_at": inputs["frozen_at"],
            "config_frozen_at": frozen_at, "prediction_started_at": None,
        },
    }
    OUTPUT.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "FROZEN", "config_frozen_at": frozen_at,
                      "config_sha256": digest(OUTPUT), "model": MODEL, "effort": EFFORT}))


if __name__ == "__main__":
    main()
