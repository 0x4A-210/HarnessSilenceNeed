#!/usr/bin/env python3
"""Run three-way native build/runtime probes for selected Wuffs candidates."""

from __future__ import annotations

import argparse
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


def git_bytes(*args: str, check: bool = True) -> bytes:
    completed = subprocess.run(["git", "-C", str(REPO), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and completed.returncode:
        raise RuntimeError(completed.stderr.decode(errors="replace"))
    return completed.stdout


def extract(commit: str, destination: Path) -> None:
    archive = subprocess.Popen(["git", "-C", str(REPO), "archive", commit], stdout=subprocess.PIPE)
    assert archive.stdout is not None
    with tarfile.open(fileobj=archive.stdout, mode="r|") as handle:
        handle.extractall(destination, filter="data")
    if archive.wait() != 0:
        raise RuntimeError(f"git archive failed for {commit}")


def overlay_h0(tree: Path, parent: str, harness_paths: list[str]) -> None:
    for relative in harness_paths:
        target = tree / relative
        value = git_bytes("show", f"{parent}:{relative}", check=False)
        exists = subprocess.run(
            ["git", "-C", str(REPO), "cat-file", "-e", f"{parent}:{relative}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ).returncode == 0
        if exists:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(value)
        elif target.exists():
            target.unlink()


def run_one(case_id: str, candidate_id: str, commit: str, parent: str,
            harness_paths: list[str], side: str, tree_commit: str, use_h0: bool) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with tempfile.TemporaryDirectory(prefix=f"silent-wuffs-{candidate_id}-{side}-") as temp:
        tree = Path(temp)
        extract(tree_commit, tree)
        if use_h0:
            overlay_h0(tree, parent, harness_paths)
        selected = [path for path in harness_paths if (tree / path).is_file() and "fuzzer" in Path(path).name.lower()]
        if not selected:
            rows.append({
                "case_id": case_id, "candidate_id": candidate_id, "side": side,
                "harness_file": "", "build": "NOT_APPLICABLE", "runtime": "NOT_APPLICABLE",
                "compile_command": "", "compile_exit_code": "", "runtime_exit_code": "",
                "diagnostic": "no pre-existing changed fuzzer translation unit",
            })
            return rows
        for index, relative in enumerate(selected):
            source = tree / relative
            compiler = shutil.which("g++" if source.suffix in {".cc", ".cpp", ".cxx"} else "gcc")
            assert compiler
            executable = tree / f".probe-{index}"
            standard = "-std=gnu++17" if compiler.endswith("g++") else "-std=gnu11"
            command = [compiler, standard, "-O0", "-g0", "-DWUFFS_CONFIG__FUZZLIB_MAIN", str(source), "-o", str(executable)]
            try:
                compiled = subprocess.run(command, cwd=tree, text=True, stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE, timeout=180)
                build = "PASS" if compiled.returncode == 0 else "FAIL"
                diagnostic = (compiled.stdout + compiled.stderr)[-12000:]
            except subprocess.TimeoutExpired as exc:
                compiled = None
                build = "TIMEOUT"
                diagnostic = ((exc.stdout or "") + (exc.stderr or ""))[-12000:]
            runtime = "NOT_RUN"
            runtime_code = ""
            if build == "PASS":
                sample = tree / ".probe-input"
                sample.write_bytes(b"{}\n")
                try:
                    executed = subprocess.run([str(executable), str(sample)], cwd=tree, stdout=subprocess.PIPE,
                                              stderr=subprocess.PIPE, timeout=15)
                    runtime_code = str(executed.returncode)
                    runtime = "PASS" if executed.returncode == 0 else "FAIL"
                    diagnostic += "\nRUNTIME:\n" + (executed.stdout + executed.stderr).decode(errors="replace")[-4000:]
                except subprocess.TimeoutExpired as exc:
                    runtime = "TIMEOUT"
                    diagnostic += "\nRUNTIME TIMEOUT:\n" + ((exc.stdout or b"") + (exc.stderr or b"")).decode(errors="replace")[-4000:]
            rows.append({
                "case_id": case_id, "candidate_id": candidate_id, "side": side,
                "harness_file": relative, "build": build, "runtime": runtime,
                "compile_command": " ".join(command),
                "compile_exit_code": "" if compiled is None else str(compiled.returncode),
                "runtime_exit_code": runtime_code, "diagnostic": diagnostic,
            })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate_ids", nargs="+")
    parser.add_argument("--case-prefix", default="W")
    parser.add_argument("--output", type=Path, default=GROUND / "wuffs_probe_details.csv")
    args = parser.parse_args()
    csv.field_size_limit(sys.maxsize)
    candidates = {
        row["candidate_id"]: row for row in csv.DictReader((DATA / "new_candidates.csv").open(encoding="utf-8", newline=""))
    }
    rows: list[dict[str, str]] = []
    for number, candidate_id in enumerate(args.candidate_ids, 1):
        candidate = candidates[candidate_id]
        if candidate["project"] != "wuffs":
            raise SystemExit(f"not Wuffs: {candidate_id}")
        harness_paths = json.loads(candidate["harness_files_changed"])
        case_id = f"{args.case_prefix}{number:03d}"
        for side, tree_commit, use_h0 in (
            ("S0_H0", candidate["parent"], False),
            ("S1_H0", candidate["commit"], True),
            ("S1_H1", candidate["commit"], False),
        ):
            print(candidate_id, side, flush=True)
            rows.extend(run_one(case_id, candidate_id, candidate["commit"], candidate["parent"],
                                harness_paths, side, tree_commit, use_h0))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["case_id", "candidate_id", "side", "harness_file", "build", "runtime",
              "compile_command", "compile_exit_code", "runtime_exit_code", "diagnostic"]
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
    print(json.dumps({"rows": len(rows), "output": str(args.output)}))


if __name__ == "__main__":
    main()
