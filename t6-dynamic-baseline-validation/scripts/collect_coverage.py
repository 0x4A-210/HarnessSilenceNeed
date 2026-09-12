#!/usr/bin/env python3
from __future__ import annotations

import gzip
import json
import subprocess
import time
from pathlib import Path

from common import ROOT, sha256_file, write_json

EXCLUDED_PARTS = {"test", "tests", "fuzz", "fuzzer", "tools", "tool",
                  "example", "examples", "demo", "demos", "build"}


def production_relative(filename: str, project: str) -> str | None:
    prefix = f"/src/{project}/"
    if not filename.startswith(prefix):
        return None
    rel = filename[len(prefix):]
    parts = {p.lower() for p in Path(rel).parts}
    if parts & EXCLUDED_PARTS:
        return None
    if not rel.lower().endswith((".c", ".cc", ".cpp", ".cxx", ".h", ".hpp")):
        return None
    return rel


def aggregate(files: list[dict], key: str) -> dict:
    count = sum(int(f["summary"].get(key, {}).get("count", 0)) for f in files)
    covered = sum(int(f["summary"].get(key, {}).get("covered", 0)) for f in files)
    return {"count": count, "covered": covered,
            "percent": (100.0 * covered / count if count else None)}


def collect(case: dict[str, str], version: str, out_dir: Path, run_root: Path,
            budget_name: str, repeat: int, run_result: dict) -> dict:
    profile_dir = run_root / "profiles"
    binaries = [x for x in case["h0_fuzz_targets"].split(";")
                if (out_dir / x).is_file()]
    output_path = ROOT / "raw" / "coverage" / case["case_id"] / version / f"{budget_name}_r{repeat}.json.gz"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not list(profile_dir.glob("*.profraw")) or not binaries:
        compact = {"case_id": case["case_id"], "version": version,
                   "budget": budget_name, "repeat": repeat,
                   "status": "COVERAGE_UNAVAILABLE", "run": run_result}
        with gzip.open(output_path, "wt", encoding="utf-8") as f:
            json.dump(compact, f, sort_keys=True)
        return compact

    objects = " ".join(f"-object=/out/{x}" for x in binaries[1:])
    command = (
        "llvm-profdata merge -sparse /profiles/*.profraw -o /profiles/merged.profdata "
        f"&& llvm-cov export -instr-profile=/profiles/merged.profdata /out/{binaries[0]} "
        f"{objects} > /profiles/export.json"
    )
    started = time.perf_counter()
    proc = subprocess.run([
        "docker", "run", "--rm", "--cpus=1", "--memory=2g",
        "-v", f"{out_dir}:/out:ro", "-v", f"{profile_dir}:/profiles",
        f"gcr.io/oss-fuzz/{case['project']}", "/bin/bash", "-lc", command,
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    collection_seconds = time.perf_counter() - started
    export = profile_dir / "export.json"
    if proc.returncode or not export.exists():
        compact = {"case_id": case["case_id"], "version": version,
                   "budget": budget_name, "repeat": repeat,
                   "status": "COVERAGE_UNAVAILABLE", "run": run_result,
                   "coverage_error": proc.stderr[-4000:]}
    else:
        data = json.loads(export.read_text())["data"][0]
        production_files = []
        file_rows = []
        for item in data.get("files", []):
            rel = production_relative(item["filename"], case["project"])
            if rel is None:
                continue
            production_files.append(item)
            file_rows.append({"path": rel, "summary": item["summary"],
                              "segments": item.get("segments", [])})
        functions = []
        for function in data.get("functions", []):
            rels = [production_relative(x, case["project"])
                    for x in function.get("filenames", [])]
            if not any(x is not None for x in rels):
                continue
            functions.append({
                "name": function["name"], "count": function.get("count", 0),
                "filenames": rels, "regions": function.get("regions", []),
            })
        compact = {
            "case_id": case["case_id"], "project": case["project"],
            "version": version, "budget": budget_name, "repeat": repeat,
            "status": "PASS", "run_status": run_result.get("status"),
            "collection_wall_seconds": collection_seconds,
            "binaries": binaries,
            "binary_sha256": {x: sha256_file(out_dir / x) for x in binaries},
            "totals": {k: aggregate(production_files, k)
                       for k in ("lines", "branches", "functions")},
            "files": file_rows, "functions": functions,
            "run": run_result,
        }
    with gzip.open(output_path, "wt", encoding="utf-8") as f:
        json.dump(compact, f, sort_keys=True, separators=(",", ":"))
    return compact


if __name__ == "__main__":
    raise SystemExit("This module is called by run_phase_a.py.")
