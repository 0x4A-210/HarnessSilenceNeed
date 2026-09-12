#!/usr/bin/env python3
"""Execute frozen Task-6 M0/M1/M2 infrastructure on S0+H0 and S1+H0."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DYNAMIC = ROOT / "dynamic-baseline"
T6 = ROOT.parent / "t6-dynamic-baseline-validation"
T6_SCRIPTS = T6 / "scripts"
REPOS = ROOT / "deterministic-baseline" / "project-repos"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bootstrap_modules():
    sys.path.insert(0, str(T6_SCRIPTS))
    import common as common6
    common6.ROOT = DYNAMIC
    common6.WORKSPACE = ROOT.parent
    common6.PROJECTS = REPOS
    import build_versions
    build_versions.ROOT = DYNAMIC
    build_versions.ORIGINAL_PROJECTS = REPOS
    build_versions.ADAPTER = T6_SCRIPTS / "oss_fuzz_build_adapter.sh"
    import run_fuzz_budget
    import collect_coverage
    return common6, build_versions, run_fuzz_budget, collect_coverage


def overlay_h0(case: dict[str, str], source: Path) -> list[dict[str, str]]:
    records = []
    repo = REPOS / case["project"]
    for relative in filter(None, case["h0_harness_paths"].split(";")):
        result = subprocess.run(
            ["git", "-C", str(repo), "show", f"{case['s0_commit']}:{relative}"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        if result.returncode:
            raise RuntimeError(f"cannot materialize H0 {relative}: {result.stderr.decode(errors='replace')[-500:]}")
        target = source / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(result.stdout)
        records.append({"path": relative, "sha256": hashlib.sha256(result.stdout).hexdigest()})
    return records


def make_corpus(common6, case: dict[str, str], root: Path) -> dict:
    rows = []
    for target in filter(None, case["h0_fuzz_targets"].split(";")):
        directory = root / target
        directory.mkdir(parents=True)
        for name, data in common6.SYNTHETIC_SEEDS.items():
            (directory / name).write_bytes(data)
        rows.append({"target": target, "seed_count": len(common6.SYNTHETIC_SEEDS),
                     "source": "TASK6_FIXED_SYNTHETIC_FALLBACK"})
    return {"targets": rows, "post_commit_data_used": False}


def main() -> None:
    config = json.loads((ROOT / "frozen-experiment-config.json").read_text(encoding="utf-8"))
    method = config["dynamic_baselines"]
    for relative, expected in method["file_sha256"].items():
        path = ROOT.parent / relative if relative.startswith("t6-") else ROOT / relative
        if digest(path) != expected:
            raise SystemExit(f"dynamic frozen hash mismatch: {relative}")
    manifest_path = DYNAMIC / "run_manifest.json"
    if manifest_path.exists() or (DYNAMIC / "raw").exists():
        raise SystemExit("refusing to rerun dynamic baselines")
    common6, builds, run_fuzz, coverage = bootstrap_modules()
    cases = common6.read_csv(DYNAMIC / "dataset" / "cases.csv")
    started_at = common6.utc_now()

    def process(case: dict[str, str]) -> dict:
        start = time.perf_counter()
        if case["adapter_supported"] != "true":
            return {
                "case_id": case["case_id"], "project": case["project"],
                "status": "NOT_APPLICABLE_NO_FROZEN_ADAPTER", "versions": {},
                "seconds": time.perf_counter() - start,
            }
        record = {"case_id": case["case_id"], "project": case["project"],
                  "status": "RUNNING", "versions": {}, "h0_overlay": []}
        try:
            with tempfile.TemporaryDirectory(prefix=f"t8-dyn-{case['case_id']}-", dir="/tmp") as temp:
                temp_path = Path(temp)
                sources = {key: temp_path / f"source-{key}" for key in ("s0", "s1")}
                checkout = {
                    "s0": builds.extract_snapshot(case["project"], case["s0_commit"], sources["s0"]),
                    "s1": builds.extract_snapshot(case["project"], case["s1_commit"], sources["s1"]),
                }
                record["h0_overlay"] = overlay_h0(case, sources["s1"])
                corpus_root = temp_path / "corpus"
                record["corpus"] = make_corpus(common6, case, corpus_root)
                for version in ("s0", "s1"):
                    out_dir = temp_path / f"out-{version}"
                    work_dir = temp_path / f"work-{version}"
                    build = builds.build_snapshot(case["case_id"], case["project"], version,
                                                  sources[version], out_dir, work_dir)
                    build["checkout_time_seconds"] = checkout[version]["checkout_time_seconds"]
                    common6.write_json(DYNAMIC / "raw" / "timings" /
                                       f"{case['case_id']}_{version}_build.json", build)
                    version_record = {"build": build, "run": None, "coverage": None}
                    record["versions"][version] = version_record
                    if build["status"] != "PASS":
                        continue
                    run_root = temp_path / "runs" / version / "corpus" / "r1"
                    run = run_fuzz.run_budget(case, version, out_dir, corpus_root, run_root,
                                              budget_name="corpus", budget_seconds=0, repeat=1)
                    measured = coverage.collect(case, version, out_dir, run_root,
                                                "corpus", 1, run)
                    version_record["run"] = {k: run.get(k) for k in ("status", "wall_seconds", "cpu_seconds", "peak_memory_mb")}
                    version_record["coverage"] = {k: measured.get(k) for k in ("status", "run_status", "totals")}
                record["status"] = "PASS" if all(
                    record["versions"].get(v, {}).get("build", {}).get("status") == "PASS"
                    for v in ("s0", "s1")) else "PARTIAL_OR_BUILD_UNAVAILABLE"
        except Exception as exc:
            record["status"] = "DYNAMIC_UNAVAILABLE"
            record["error"] = f"{type(exc).__name__}: {exc}"
            record["traceback"] = traceback.format_exc()
        record["seconds"] = time.perf_counter() - start
        common6.write_json(DYNAMIC / "raw" / "case_manifests" / f"{case['case_id']}.json", record)
        return record

    unsupported = [process(case) for case in cases if case["adapter_supported"] != "true"]
    supported = [case for case in cases if case["adapter_supported"] == "true"]
    records = list(unsupported)
    with concurrent.futures.ThreadPoolExecutor(max_workers=method["worker_concurrency"]) as pool:
        futures = [pool.submit(process, case) for case in supported]
        for future in concurrent.futures.as_completed(futures):
            row = future.result(); records.append(row)
            print(f"{len(records):03d}/104 {row['case_id']} {row['status']} {row['seconds']:.1f}s", flush=True)
    records.sort(key=lambda row: row["case_id"])
    manifest = {
        "status": "COMPLETE", "started_at": started_at, "finished_at": common6.utc_now(),
        "case_count": 104, "frozen_adapter_applicable": len(supported),
        "pass_count": sum(row["status"] == "PASS" for row in records),
        "unavailable_or_partial_count": sum(row["status"] != "PASS" for row in records),
        "ground_truth_files_read": False, "h1_used": False,
        "counterfactual": "S1 production tree with selected parent H0 paths overlaid",
        "budget": "corpus replay only", "records": records,
    }
    common6.write_json(manifest_path, manifest)
    print(json.dumps({key: manifest[key] for key in ("status", "case_count", "frozen_adapter_applicable", "pass_count", "unavailable_or_partial_count")}, sort_keys=True))


if __name__ == "__main__":
    main()
