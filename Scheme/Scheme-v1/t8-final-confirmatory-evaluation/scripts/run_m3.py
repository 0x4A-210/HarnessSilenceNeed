#!/usr/bin/env python3
"""Run byte-identical Task-7 M3 rules on Task-8 cases, without GT access."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import sys
import time
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
M3 = ROOT / "deterministic-baseline"
T7 = ROOT.parent / "t7-target-discovery-reachability"
T7_SCRIPTS = T7 / "scripts"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def bootstrap_modules():
    sys.path.insert(0, str(T7_SCRIPTS))
    import common as t7_common
    t7_common.ROOT = M3
    t7_common.WORKSPACE = ROOT.parent
    t7_common.PROJECTS = M3 / "project-repos"
    from discover_case import discover
    return t7_common, discover


def main() -> None:
    config_path = ROOT / "frozen-experiment-config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config["status"] != "FROZEN_BEFORE_PREDICTION":
        raise SystemExit("experiment is not frozen")
    for relative, expected in config["m3_diff_derived_reachability"]["file_sha256"].items():
        path = ROOT.parent / relative if relative.startswith("t7-") else ROOT / relative
        if digest(path) != expected:
            raise SystemExit(f"M3 frozen hash mismatch: {relative}")
    output = M3 / "target-discovery"
    manifest_path = M3 / "run_manifest.json"
    if output.exists() or manifest_path.exists():
        raise SystemExit("refusing to rerun frozen M3")
    t7_common, discover = bootstrap_modules()
    cases = t7_common.read_csv(M3 / "dataset" / "cases.csv")
    output.mkdir(parents=True)
    started_at = t7_common.utc_now()

    def run_one(case: dict[str, str]) -> dict:
        start = time.perf_counter()
        try:
            result = discover(case)
            write_json(output / f"{case['case_id']}.json", result)
            return {"case_id": case["case_id"], "status": "PASS", "seconds": time.perf_counter() - start}
        except Exception as exc:
            error = {
                "case_id": case["case_id"], "status": "ERROR", "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(), "seconds": time.perf_counter() - start,
            }
            write_json(output / f"{case['case_id']}.error.json", error)
            return error

    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=config["m3_diff_derived_reachability"]["concurrency"]) as pool:
        futures = [pool.submit(run_one, case) for case in cases]
        for future in concurrent.futures.as_completed(futures):
            row = future.result()
            rows.append(row)
            print(f"{len(rows):03d}/104 {row['case_id']} {row['status']} {row['seconds']:.2f}s", flush=True)
    rows.sort(key=lambda row: row["case_id"])
    manifest = {
        "status": "COMPLETE" if all(row["status"] == "PASS" for row in rows) else "COMPLETE_WITH_FAILURES",
        "started_at": started_at, "finished_at": t7_common.utc_now(), "case_count": len(cases),
        "success_count": sum(row["status"] == "PASS" for row in rows),
        "failure_count": sum(row["status"] != "PASS" for row in rows),
        "ground_truth_files_read": False, "uses_h1": False, "uses_llm": False,
        "rule_version": config["m3_diff_derived_reachability"]["rule_version"],
        "known_frozen_defects": config["m3_diff_derived_reachability"]["known_frozen_defects"],
        "records": rows,
    }
    write_json(manifest_path, manifest)
    print(json.dumps({key: manifest[key] for key in ("status", "case_count", "success_count", "failure_count")}, sort_keys=True))


if __name__ == "__main__":
    main()
