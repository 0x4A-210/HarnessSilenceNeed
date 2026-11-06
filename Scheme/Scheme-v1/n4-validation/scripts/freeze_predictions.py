#!/usr/bin/env python3
"""Freeze task-4 predictions before any label reveal or evaluation."""

from __future__ import annotations

import hashlib
import json
import datetime as dt
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRED = ROOT / "predictions"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    output = PRED / "prediction_freeze_manifest.json"
    if output.exists():
        raise SystemExit("refusing to overwrite frozen predictions")
    records = {}
    for method in ("gap_only", "evolution_aware"):
        prediction = PRED / f"{method}.jsonl"
        pairs = PRED / f"{method}_input_output_pairs.jsonl"
        run_path = PRED / f"run_manifest_{method}.json"
        run = json.loads(run_path.read_text(encoding="utf-8"))
        rows = [json.loads(line) for line in prediction.read_text(encoding="utf-8").splitlines() if line]
        pair_rows = [json.loads(line) for line in pairs.read_text(encoding="utf-8").splitlines() if line]
        ids = [row["case_id"] for row in rows]
        if len(rows) != 40 or len(set(ids)) != 40 or set(ids) != {f"C{i:03d}" for i in range(1, 41)}:
            raise SystemExit(f"bad case set for {method}")
        if len(pair_rows) != 40 or any(row["model_output"] is None or row["exit_code"] != 0 or row["error"] for row in pair_rows):
            raise SystemExit(f"invalid input/output pair for {method}")
        if run["status"] != "complete" or run["valid_predictions"] != 40 or run["failed_predictions"] != 0:
            raise SystemExit(f"incomplete run manifest for {method}")
        for pair in pair_rows:
            case_id = pair["case_id"]
            frozen_case = (ROOT / "frozen-inputs" / f"{case_id}.md").read_text(encoding="utf-8")
            if frozen_case not in pair["model_input"]:
                raise SystemExit(f"frozen case not embedded verbatim: {method}/{case_id}")
        records[method] = {
            "prediction_sha256": sha256(prediction.read_bytes()),
            "input_output_pairs_sha256": sha256(pairs.read_bytes()),
            "run_manifest_sha256": sha256(run_path.read_bytes()),
            "case_count": 40, "valid_count": 40, "failed_count": 0, "retry_count": 0,
            "started_at": run["started_at"], "finished_at": run["finished_at"],
            "prompt_sha256": run["prompt_sha256"], "schema_sha256": run["schema_sha256"],
            "model": run["model"], "reasoning_effort": run["reasoning_effort"],
            "ground_truth_files_read": run["ground_truth_files_read"],
        }
    manifest = {
        "status": "FROZEN_BEFORE_LABEL_REVEAL",
        "frozen_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "methods": records,
        "case_count_per_method": 40, "total_one_shot_predictions": 80,
        "all_cases_embed_frozen_input_verbatim": True, "labels_read_by_runner": False,
        "evaluation_files_present_at_freeze": False,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
