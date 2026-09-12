#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

from common import ROOT, sha256_file, utc_now, write_json

TIME_FIELDS = {
    "User time (seconds)": "user_seconds",
    "System time (seconds)": "system_seconds",
    "Maximum resident set size (kbytes)": "peak_kbytes",
}


def parse_time(path: Path) -> dict:
    result = {"user_seconds": None, "system_seconds": None, "peak_kbytes": None}
    if not path.exists():
        return result
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        for prefix, key in TIME_FIELDS.items():
            if line.startswith(prefix + ":"):
                try:
                    result[key] = float(line.split(":", 1)[1].strip())
                except ValueError:
                    pass
    return result


def run_budget(case: dict[str, str], version: str, out_dir: Path,
               base_corpus: Path, run_root: Path, *, budget_name: str,
               budget_seconds: int, repeat: int) -> dict:
    targets = [x for x in case["h0_fuzz_targets"].split(";") if x]
    available = [t for t in targets if (out_dir / t).is_file()]
    if not available:
        return {"status": "DYNAMIC_UNAVAILABLE", "targets": []}
    per_target = 0 if budget_seconds == 0 else max(1, budget_seconds // len(available))
    details = []
    profile_dir = run_root / "profiles"
    profile_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    for index, target in enumerate(available):
        corpus = run_root / "corpus" / target
        shutil.copytree(base_corpus / target, corpus)
        artifact_dir = run_root / "artifacts" / target
        artifact_dir.mkdir(parents=True, exist_ok=True)
        log_base = ROOT / "raw" / "logs" / "runs" / case["case_id"] / version
        log_base.mkdir(parents=True, exist_ok=True)
        stem = f"{budget_name}_r{repeat}_{target}"
        stdout_path = log_base / f"{stem}.stdout.log"
        stderr_path = log_base / f"{stem}.stderr.log"
        time_path = run_root / f"{stem}.time"
        profile_pattern = profile_dir / f"{target}_%m_%p.profraw"
        args = [
            "/usr/bin/time", "-v", "-o", str(time_path), str(out_dir / target),
            f"-seed={1337 + repeat}", "-timeout=10", "-rss_limit_mb=2048",
            "-print_final_stats=1", f"-artifact_prefix={artifact_dir}/",
        ]
        if budget_seconds == 0:
            args.append("-runs=0")
        else:
            args.append(f"-max_total_time={per_target}")
        args.append(str(corpus))
        env = os.environ.copy()
        env["LLVM_PROFILE_FILE"] = str(profile_pattern)
        target_started = time.perf_counter()
        timed_out = False
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            try:
                proc = subprocess.run(args, env=env, stdout=stdout, stderr=stderr,
                                      timeout=max(60, per_target + 45))
                exit_code = proc.returncode
            except subprocess.TimeoutExpired:
                timed_out = True
                exit_code = 124
        timing = parse_time(time_path)
        cpu = None
        if timing["user_seconds"] is not None and timing["system_seconds"] is not None:
            cpu = timing["user_seconds"] + timing["system_seconds"]
        details.append({
            "target": target, "allocated_seconds": per_target,
            "wall_seconds": time.perf_counter() - target_started,
            "cpu_seconds": cpu,
            "peak_memory_mb": (timing["peak_kbytes"] / 1024
                               if timing["peak_kbytes"] is not None else None),
            "exit_code": exit_code, "timed_out": timed_out,
            "stdout": str(stdout_path.relative_to(ROOT)),
            "stderr": str(stderr_path.relative_to(ROOT)),
            "final_corpus_count": sum(1 for p in corpus.iterdir() if p.is_file()),
            "artifact_count": sum(1 for p in artifact_dir.iterdir() if p.is_file()),
        })
    profiles = sorted(profile_dir.glob("*.profraw"))
    status = "PASS"
    if any(x["timed_out"] for x in details):
        status = "TIMEOUT"
    elif any(x["exit_code"] != 0 for x in details):
        status = "NONDETERMINISTIC"
    if not profiles:
        status = "COVERAGE_UNAVAILABLE"
    result = {
        "case_id": case["case_id"], "project": case["project"],
        "version": version, "budget": budget_name,
        "budget_seconds": budget_seconds, "repeat": repeat,
        "started_at": utc_now(), "wall_seconds": time.perf_counter() - started,
        "cpu_seconds": sum(x["cpu_seconds"] or 0 for x in details),
        "peak_memory_mb": max((x["peak_memory_mb"] or 0 for x in details), default=0),
        "status": status, "targets": details,
        "profile_count": len(profiles),
        "profile_sha256": {p.name: sha256_file(p) for p in profiles},
    }
    timing_out = ROOT / "raw" / "timings" / case["case_id"] / version
    write_json(timing_out / f"{budget_name}_r{repeat}.json", result)
    return result


if __name__ == "__main__":
    raise SystemExit("This module is called by run_phase_a.py.")
