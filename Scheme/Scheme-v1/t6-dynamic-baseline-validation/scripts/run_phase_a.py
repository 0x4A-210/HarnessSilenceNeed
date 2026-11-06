#!/usr/bin/env python3
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import shutil
import tempfile
import traceback
from pathlib import Path

from build_versions import build_snapshot, extract_snapshot
from collect_coverage import collect
from common import (ROOT, SYNTHETIC_SEEDS, read_csv, sha256_bytes, sha256_file,
                    utc_now, write_json)
from run_corpus_replay import run_corpus_replay
from run_fuzz_budget import run_budget


def copy_corpus(case: dict[str, str], s0_source: Path, destination: Path) -> dict:
    manifests = [r for r in read_csv(ROOT / "dataset" / "corpus_manifest.csv")
                 if r["case_id"] == case["case_id"]]
    rows = []
    for manifest in manifests:
        target = manifest["fuzz_target"]
        target_dir = destination / target
        target_dir.mkdir(parents=True, exist_ok=True)
        hashes = []
        if manifest["corpus_source"] == "S0_PROJECT_HISTORICAL_TEST_DATA":
            for index, rel in enumerate(x for x in manifest["source_paths"].split(";") if x):
                source = s0_source / rel
                data = source.read_bytes()
                name = f"{index:05d}_{hashlib.sha256(rel.encode()).hexdigest()[:12]}"
                (target_dir / name).write_bytes(data)
                hashes.append((name, sha256_bytes(data), len(data), rel))
        else:
            for name, data in SYNTHETIC_SEEDS.items():
                (target_dir / name).write_bytes(data)
                hashes.append((name, sha256_bytes(data), len(data), "FIXED"))
        payload = json.dumps(hashes, separators=(",", ":")).encode()
        rows.append({"target": target, "source": manifest["corpus_source"],
                     "files": len(hashes), "bytes": sum(x[2] for x in hashes),
                     "actual_sha256": sha256_bytes(payload)})
    result = {"case_id": case["case_id"], "s0_commit": case["s0_commit"],
              "created_at": utc_now(), "targets": rows}
    write_json(ROOT / "raw" / "corpus" / f"{case['case_id']}.json", result)
    return result


def expected_outputs(case: dict[str, str], config: dict) -> list[Path]:
    paths = []
    for version in ("s0", "s1"):
        for budget in config["budget_policy"]["budgets"]:
            for repeat in range(1, budget["repeats"] + 1):
                paths.append(ROOT / "raw" / "coverage" / case["case_id"] / version /
                             f"{budget['name']}_r{repeat}.json.gz")
    return paths


def process_case(case: dict[str, str], config: dict, resume: bool) -> dict:
    if resume and all(p.exists() for p in expected_outputs(case, config)):
        return {"case_id": case["case_id"], "status": "SKIPPED_COMPLETE"}
    result = {"case_id": case["case_id"], "project": case["project"],
              "started_at": utc_now(), "versions": {}}
    try:
        with tempfile.TemporaryDirectory(prefix=f"t6-{case['case_id']}-", dir="/tmp") as tmp:
            tmp_path = Path(tmp)
            sources = {"s0": tmp_path / "source-s0", "s1": tmp_path / "source-s1"}
            checkouts = {
                "s0": extract_snapshot(case["project"], case["s0_commit"], sources["s0"]),
                "s1": extract_snapshot(case["project"], case["s1_commit"], sources["s1"]),
            }
            corpus_root = tmp_path / "base-corpus"
            copy_corpus(case, sources["s0"], corpus_root)
            for version in ("s0", "s1"):
                out_dir = tmp_path / f"out-{version}"
                work_dir = tmp_path / f"work-{version}"
                build = build_snapshot(case["case_id"], case["project"], version,
                                       sources[version], out_dir, work_dir)
                build["checkout_time_seconds"] = checkouts[version]["checkout_time_seconds"]
                write_json(ROOT / "raw" / "timings" /
                           f"{case['case_id']}_{version}_build.json", build)
                version_result = {"build": build, "runs": []}
                result["versions"][version] = version_result
                if build["status"] != "PASS":
                    continue
                for budget in config["budget_policy"]["budgets"]:
                    for repeat in range(1, int(budget["repeats"]) + 1):
                        run_root = tmp_path / "runs" / version / budget["name"] / f"r{repeat}"
                        if int(budget["seconds"]) == 0:
                            run_result = run_corpus_replay(case, version, out_dir,
                                                          corpus_root, run_root)
                        else:
                            run_result = run_budget(
                                case, version, out_dir, corpus_root, run_root,
                                budget_name=budget["name"],
                                budget_seconds=int(budget["seconds"]), repeat=repeat,
                            )
                        coverage = collect(case, version, out_dir, run_root,
                                           budget["name"], repeat, run_result)
                        version_result["runs"].append({
                            "budget": budget["name"], "repeat": repeat,
                            "run_status": run_result.get("status"),
                            "coverage_status": coverage.get("status"),
                        })
        statuses = [v["build"]["status"] for v in result["versions"].values()]
        result["status"] = "PASS" if statuses == ["PASS", "PASS"] else "PARTIAL_OR_UNAVAILABLE"
    except Exception as exc:
        result["status"] = "DYNAMIC_UNAVAILABLE"
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["traceback"] = traceback.format_exc()
    result["finished_at"] = utc_now()
    write_json(ROOT / "raw" / "case_manifests" / f"{case['case_id']}.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--case", action="append", default=[])
    args = parser.parse_args()
    config_path = ROOT / "experiment_config.json"
    if not config_path.exists():
        raise SystemExit("experiment_config.json must be frozen first")
    config = json.loads(config_path.read_text())
    cases = read_csv(ROOT / "dataset" / "cases.csv")
    if args.case:
        cases = [c for c in cases if c["case_id"] in set(args.case)]
    if any(c["case_id"] == "T5028" for c in cases):
        raise SystemExit("invalidated T5028 must not be executed")
    manifest_path = ROOT / "raw" / "formal_run_manifest.json"
    if manifest_path.exists() and not args.resume:
        raise SystemExit("formal run manifest exists; use --resume explicitly")
    manifest = {
        "status": "RUNNING", "started_at": utc_now(),
        "experiment_config_sha256": sha256_file(config_path),
        "case_count": len(cases), "workers": args.workers,
        "pilot_outputs_included": False, "case_results": [],
    }
    write_json(manifest_path, manifest)
    completed = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process_case, case, config, args.resume): case
                   for case in cases}
        for future in concurrent.futures.as_completed(futures):
            case = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {"case_id": case["case_id"], "status": "DYNAMIC_UNAVAILABLE",
                          "error": f"worker escaped: {exc}"}
            manifest["case_results"].append(result)
            completed += 1
            print(json.dumps({"completed": completed, "total": len(cases),
                              "case_id": case["case_id"],
                              "status": result["status"]}), flush=True)
            write_json(manifest_path, manifest)
    manifest["status"] = "COMPLETE"
    manifest["finished_at"] = utc_now()
    manifest["case_results"] = sorted(manifest["case_results"],
                                      key=lambda x: x["case_id"])
    write_json(manifest_path, manifest)


if __name__ == "__main__":
    main()
