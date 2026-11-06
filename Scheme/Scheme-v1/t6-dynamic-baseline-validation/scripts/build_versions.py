#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

from common import ROOT, SOURCES, sha256_file, target_sources, utc_now, write_json

ORIGINAL_PROJECTS = SOURCES / "projects"
ADAPTER = ROOT / "scripts" / "oss_fuzz_build_adapter.sh"


def extract_snapshot(project: str, commit: str, destination: Path) -> dict:
    destination.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    archive = subprocess.Popen(
        ["git", "-C", str(ORIGINAL_PROJECTS / project), "archive", commit],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    assert archive.stdout is not None
    untar = subprocess.run(["tar", "-x", "-C", str(destination)],
                           stdin=archive.stdout, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE)
    archive.stdout.close()
    archive_stderr = archive.stderr.read().decode(errors="replace") if archive.stderr else ""
    archive_rc = archive.wait()
    elapsed = time.perf_counter() - started
    if archive_rc or untar.returncode:
        raise RuntimeError(
            f"git archive rc={archive_rc}: {archive_stderr}; "
            f"tar rc={untar.returncode}: {untar.stderr.decode(errors='replace')}"
        )
    return {"checkout_time_seconds": elapsed, "commit": commit}


def build_snapshot(case_id: str, project: str, version: str, source_dir: Path,
                   out_dir: Path, work_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    log_path = ROOT / "raw" / "logs" / "build" / f"{case_id}_{version}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "docker", "run", "--privileged", "--shm-size=2g",
        "--platform", "linux/amd64", "--cpus=3", "--memory=4g", "--rm",
        "-e", "FUZZING_ENGINE=libfuzzer", "-e", "SANITIZER=coverage",
        "-e", "ARCHITECTURE=x86_64", "-e", f"PROJECT_NAME={project}",
        "-e", "FUZZING_LANGUAGE=c++", "-e", "T6_BUILD_JOBS=3",
        "-v", f"{source_dir}:/src/{project}",
        "-v", f"{out_dir}:/out", "-v", f"{work_dir}:/work",
        "-v", f"{ADAPTER}:/src/build.sh:ro",
        f"gcr.io/oss-fuzz/{project}",
        "/bin/bash", "-lc", "time -p compile",
    ]
    started_at = utc_now()
    started = time.perf_counter()
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True)
    elapsed = time.perf_counter() - started
    log_path.write_text(proc.stdout, encoding="utf-8", errors="replace")
    binaries = sorted(
        p.name for p in out_dir.iterdir()
        if p.is_file() and os.access(p, os.X_OK) and p.name != "llvm-symbolizer"
    )
    timing_matches = re.findall(r"(?m)^(real|user|sys) ([0-9.]+)$", proc.stdout)
    shell_timing = {k: float(v) for k, v in timing_matches[-3:]}
    build_cpu = (shell_timing.get("user", 0.0) + shell_timing.get("sys", 0.0)
                 if "user" in shell_timing and "sys" in shell_timing else None)
    result = {
        "case_id": case_id, "project": project, "version": version,
        "started_at": started_at, "finished_at": utc_now(),
        "build_wall_seconds": elapsed, "build_cpu_seconds": build_cpu,
        "build_peak_memory_mb": None, "exit_code": proc.returncode,
        "status": "PASS" if proc.returncode == 0 and binaries else "BUILD_UNAVAILABLE",
        "binaries": binaries,
        "binary_sha256": {name: sha256_file(out_dir / name) for name in binaries},
        "log": str(log_path.relative_to(ROOT)),
        "adapter_sha256": sha256_file(ADAPTER),
    }
    write_json(ROOT / "raw" / "timings" / f"{case_id}_{version}_build.json", result)
    return result


if __name__ == "__main__":
    raise SystemExit("This module is called by run_phase_a.py; it is not a standalone batch runner.")
