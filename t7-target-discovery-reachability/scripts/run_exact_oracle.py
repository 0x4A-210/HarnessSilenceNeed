#!/usr/bin/env python3
from __future__ import annotations

import concurrent.futures
import json
import subprocess
import sys
from pathlib import Path

from common import ROOT, read_csv, utc_now, write_csv, write_json


def one(case_id: str) -> dict:
    output = ROOT / "exact-target-oracle" / f"{case_id}.json"
    completed = subprocess.run([
        sys.executable, str(ROOT / "scripts" / "exact_oracle_case.py"),
        "--case-id", case_id, "--output", str(output),
    ], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return {"case_id": case_id, "exit_code": completed.returncode,
            "stderr": completed.stderr[-3000:], "output": str(output)}


def main() -> None:
    ids = [row["case_id"] for row in read_csv(ROOT / "dataset" / "cases.csv")]
    (ROOT / "exact-target-oracle").mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        attempts = list(pool.map(one, ids))
    failures = [row for row in attempts if row["exit_code"] != 0]
    write_json(ROOT / "results" / "m0_run_manifest.json", {
        "finished_at": utc_now(), "case_count": len(ids), "oracle_assisted": True,
        "success_count": len(ids) - len(failures), "failures": failures,
    })
    if failures:
        raise SystemExit(1)
    records = [json.loads((ROOT / "exact-target-oracle" / f"{case_id}.json").read_text()) for case_id in ids]
    fields = [
        "case_id", "project", "label", "target", "target_type", "expected_delta",
        "reachable_before", "reachable_after", "predicted_delta", "maintenance_needed",
        "applicable", "oracle_assisted", "reason", "candidate_extraction_time_seconds",
        "callgraph_build_time_seconds", "reachability_time_seconds", "total_time_seconds",
        "peak_memory_kib",
    ]
    write_csv(ROOT / "results" / "exact_target_oracle.csv", records, fields)


if __name__ == "__main__":
    main()
