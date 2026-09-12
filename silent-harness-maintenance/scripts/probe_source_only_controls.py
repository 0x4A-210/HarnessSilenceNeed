#!/usr/bin/env python3
"""Run literal S0+H0, S1+H0 and S1+H1 probes for negative controls."""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
WORKSPACE = ROOT.parent
REPO = WORKSPACE / "FSE2026-harness-degradation" / "sources" / "projects" / "wuffs"
DATA = ROOT / "data"
GROUND = ROOT / "ground-truth"


def git_bytes(*args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(REPO), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace"))
    return result.stdout


def extract(revision: str, destination: Path) -> None:
    archive = subprocess.Popen(["git", "-C", str(REPO), "archive", revision], stdout=subprocess.PIPE)
    assert archive.stdout is not None
    with tarfile.open(fileobj=archive.stdout, mode="r|") as handle:
        handle.extractall(destination, filter="data")
    if archive.wait() != 0:
        raise RuntimeError(f"git archive failed for {revision}")


def run_side(row: dict[str, str], side: str, revision: str, overlay_h0: bool) -> dict[str, str]:
    with tempfile.TemporaryDirectory(prefix=f"silent-control-{row['control_id']}-{side}-") as temporary:
        tree = Path(temporary)
        extract(revision, tree)
        harness = row["harness_file"]
        if overlay_h0:
            target = tree / harness
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(git_bytes("show", f"{row['parent']}:{harness}"))
        source = tree / harness
        compiler = shutil.which("g++" if source.suffix in {".cc", ".cpp", ".cxx"} else "gcc")
        if compiler is None:
            raise RuntimeError("native compiler unavailable")
        executable = tree / ".probe"
        standard = "-std=gnu++17" if compiler.endswith("g++") else "-std=gnu11"
        command = [compiler, standard, "-O0", "-g0", "-DWUFFS_CONFIG__FUZZLIB_MAIN",
                   str(source), "-o", str(executable)]
        started = __import__("time").monotonic()
        try:
            built = subprocess.run(command, cwd=tree, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   timeout=240)
            build = "PASS" if built.returncode == 0 else "FAIL"
            diagnostic = (built.stdout + built.stderr).decode(errors="replace")[-12000:]
            build_code = str(built.returncode)
        except subprocess.TimeoutExpired as exc:
            build = "TIMEOUT"; build_code = "124"
            diagnostic = ((exc.stdout or b"") + (exc.stderr or b"")).decode(errors="replace")[-12000:]
        runtime = "NOT_RUN"; runtime_code = ""
        if build == "PASS":
            sample = tree / ".probe-input"
            sample.write_bytes(b"{}\n")
            try:
                ran = subprocess.run([str(executable), str(sample)], cwd=tree,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
                runtime_code = str(ran.returncode)
                runtime = "PASS" if ran.returncode == 0 else "FAIL"
                diagnostic += "\nRUNTIME:\n" + (ran.stdout + ran.stderr).decode(errors="replace")[-4000:]
            except subprocess.TimeoutExpired as exc:
                runtime = "TIMEOUT"; runtime_code = "124"
                diagnostic += "\nRUNTIME TIMEOUT:\n" + ((exc.stdout or b"") + (exc.stderr or b"")).decode(errors="replace")[-4000:]
        return {
            "control_id": row["control_id"], "side": side, "harness_file": harness,
            "build": build, "runtime": runtime, "build_exit_code": build_code,
            "runtime_exit_code": runtime_code, "duration_seconds": f"{__import__('time').monotonic()-started:.3f}",
            "command": " ".join(command), "diagnostic": diagnostic,
        }


def main() -> None:
    controls = list(csv.DictReader((DATA / "source_only_negative_controls.csv").open(encoding="utf-8")))
    output: list[dict[str, str]] = []
    for row in controls:
        for side, revision, overlay in (
            ("S0_H0", row["parent"], False),
            ("S1_H0", row["commit"], True),
            ("S1_H1", row["commit"], False),
        ):
            print(row["control_id"], side, flush=True)
            output.append(run_side(row, side, revision, overlay))
    path = GROUND / "source_only_control_probe_details.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output[0]))
        writer.writeheader(); writer.writerows(output)
    failures = [row for row in output if row["build"] != "PASS" or row["runtime"] != "PASS"]
    print(json.dumps({"rows": len(output), "failures": len(failures), "output": str(path)}))


if __name__ == "__main__":
    main()
