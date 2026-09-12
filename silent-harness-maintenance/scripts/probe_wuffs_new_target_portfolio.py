#!/usr/bin/env python3
"""Portfolio-level counterfactual probe for Wuffs candidate N223.

N223 introduces a brand-new JSON target, so the target translation unit has no
H0 counterpart.  The counterfactual H0 is therefore the pre-commit OSS-Fuzz
portfolio.  This probe builds and runs an unchanged pre-existing GIF target on
S0 and S1, then builds/runs the newly added JSON H1 target on S1.
"""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
WORKSPACE = ROOT.parent
REPO = WORKSPACE / "FSE2026-harness-degradation" / "sources" / "projects" / "wuffs"
DATA = ROOT / "data"
GROUND = ROOT / "ground-truth"
CANDIDATE = "N223"


def extract(revision: str, destination: Path) -> None:
    archive = subprocess.Popen(["git", "-C", str(REPO), "archive", revision], stdout=subprocess.PIPE)
    assert archive.stdout is not None
    with tarfile.open(fileobj=archive.stdout, mode="r|") as handle:
        handle.extractall(destination, filter="data")
    if archive.wait():
        raise RuntimeError("git archive failed")


def run(side: str, source_revision: str, harness: str) -> dict[str, str]:
    with tempfile.TemporaryDirectory(prefix=f"wuffs-portfolio-{side}-") as temporary:
        tree = Path(temporary)
        extract(source_revision, tree)
        source = tree / harness
        compiler = shutil.which("g++" if source.suffix == ".cc" else "gcc") or "gcc"
        standard = "-std=gnu++17" if compiler.endswith("g++") else "-std=gnu11"
        executable = tree / ".probe"
        command = [compiler, standard, "-O0", "-DWUFFS_CONFIG__FUZZLIB_MAIN", str(source), "-o", str(executable)]
        built = subprocess.run(command, cwd=tree, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        build = "PASS" if built.returncode == 0 else "FAIL"
        runtime = "NOT_RUN"
        runtime_code = ""
        diagnostic = (built.stdout + built.stderr).decode(errors="replace")[-12000:]
        if build == "PASS":
            sample = tree / ".input"
            sample.write_bytes(b"{}\n")
            ran = subprocess.run([str(executable), str(sample)], cwd=tree, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, timeout=30)
            runtime = "PASS" if ran.returncode == 0 else "FAIL"
            runtime_code = str(ran.returncode)
            diagnostic += "\nRUNTIME:\n" + (ran.stdout + ran.stderr).decode(errors="replace")[-4000:]
        return {
            "candidate_id": CANDIDATE,
            "side": side,
            "source_revision": source_revision,
            "harness_file": harness,
            "build": build,
            "runtime": runtime,
            "build_exit_code": str(built.returncode),
            "runtime_exit_code": runtime_code,
            "command": " ".join(command),
            "diagnostic": diagnostic,
            "scope": "pre-existing OSS-Fuzz portfolio target for H0; new JSON target for H1",
        }


def main() -> None:
    csv.field_size_limit(sys.maxsize)
    row = next(r for r in csv.DictReader((DATA / "new_candidates.csv").open()) if r["candidate_id"] == CANDIDATE)
    rows = [
        run("S0_H0", row["parent"], "fuzz/c/std/gif_fuzzer.c"),
        run("S1_H0", row["commit"], "fuzz/c/std/gif_fuzzer.c"),
        run("S1_H1", row["commit"], "fuzz/c/std/json_fuzzer.c"),
    ]
    output = GROUND / "wuffs_new_target_portfolio_probe_details.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
