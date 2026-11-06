#!/usr/bin/env python3
"""Launch every M1 case in an isolated subprocess."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import subprocess
import sys
import time
from pathlib import Path

from common import ROOT, read_csv, sha256_file, utc_now, write_json


def verify_freeze() -> dict:
    path = ROOT / "frozen-experiment-config.json"
    if not path.is_file():
        raise SystemExit("formal M1 run requires frozen-experiment-config.json")
    frozen = json.loads(path.read_text(encoding="utf-8"))
    mismatches = []
    for name, expected in frozen["frozen_file_sha256"].items():
        actual = sha256_file(ROOT / name)
        if actual != expected:
            mismatches.append({"file": name, "expected": expected, "actual": actual})
    if mismatches:
        raise SystemExit(f"frozen input/rule mismatch: {mismatches}")
    return frozen


def run_one(case_id: str, output_dir: Path) -> dict:
    output = output_dir / f"{case_id}.json"
    started = time.perf_counter()
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "discover_case.py"),
         "--case-id", case_id, "--output", str(output)],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    return {
        "case_id": case_id, "exit_code": completed.returncode,
        "orchestration_wall_seconds": time.perf_counter() - started,
        "stdout": completed.stdout[-2000:], "stderr": completed.stderr[-4000:],
        "output_exists": output.is_file(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", action="append")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "target-discovery")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--manifest", type=Path, default=ROOT / "results" / "m1_run_manifest.json")
    args = parser.parse_args()
    args.output_dir = args.output_dir.resolve()
    args.manifest = args.manifest.resolve()
    frozen = verify_freeze()
    all_ids = [row["case_id"] for row in read_csv(ROOT / "dataset" / "cases.csv")]
    case_ids = args.case_id or all_ids
    unknown = sorted(set(case_ids) - set(all_ids))
    if unknown:
        raise SystemExit(f"unknown cases: {unknown}")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        records = list(pool.map(lambda case_id: run_one(case_id, args.output_dir), case_ids))
    manifest = {
        "started_from_frozen_rules": True,
        "frozen_at": frozen["frozen_at"],
        "m1_rule_version": frozen["m1_rule_version"],
        "finished_at": utc_now(),
        "case_count": len(case_ids), "jobs": args.jobs,
        "success_count": sum(row["exit_code"] == 0 and row["output_exists"] for row in records),
        "failures": [row for row in records if row["exit_code"] != 0 or not row["output_exists"]],
        "records": records,
    }
    write_json(args.manifest, manifest)
    if manifest["failures"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
