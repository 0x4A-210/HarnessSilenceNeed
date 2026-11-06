#!/usr/bin/env python3
"""Run isolated three-way native build/runtime probes for Mbed TLS candidates.

The historical in-tree standalone fuzz Makefile links a small ``onefile``
driver, so these probes exercise the actual harness translation unit and its
library, not a reconstructed mock.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path


HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
WORKSPACE = ROOT.parent
REPO = WORKSPACE / "FSE2026-harness-degradation" / "sources" / "projects" / "mbedtls"
DATA = ROOT / "data"


def git_bytes(*args: str, check: bool = True) -> bytes:
    result = subprocess.run(["git", "-C", str(REPO), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace"))
    return result.stdout


def extract(commit: str, destination: Path) -> None:
    archive = subprocess.Popen(["git", "-C", str(REPO), "archive", commit], stdout=subprocess.PIPE)
    assert archive.stdout is not None
    with tarfile.open(fileobj=archive.stdout, mode="r|") as handle:
        handle.extractall(destination, filter="data")
    if archive.wait() != 0:
        raise RuntimeError(f"git archive failed for {commit}")


def overlay_h0(tree: Path, parent: str, paths: list[str]) -> None:
    for relative in paths:
        target = tree / relative
        exists = subprocess.run(
            ["git", "-C", str(REPO), "cat-file", "-e", f"{parent}:{relative}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
        if exists:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(git_bytes("show", f"{parent}:{relative}"))
        elif target.exists():
            target.unlink()


def choose_target(tree: Path, harness_paths: list[str]) -> str:
    fuzz_sources = [
        Path(path).stem for path in harness_paths
        if path.startswith("programs/fuzz/fuzz_") and path.endswith(".c") and (tree / path).is_file()
    ]
    if fuzz_sources:
        return sorted(fuzz_sources)[0]
    for fallback in ("fuzz_server", "fuzz_client", "fuzz_x509crt"):
        if (tree / "programs" / "fuzz" / f"{fallback}.c").is_file():
            return fallback
    return ""


def probe_side(candidate_id: str, side: str, revision: str, parent: str,
               harness_paths: list[str], use_h0: bool) -> dict[str, str]:
    with tempfile.TemporaryDirectory(prefix=f"silent-mbedtls-{candidate_id}-{side}-") as temporary:
        tree = Path(temporary)
        extract(revision, tree)
        if use_h0:
            overlay_h0(tree, parent, harness_paths)
        target = choose_target(tree, harness_paths)
        if not target or not (tree / "programs" / "fuzz" / "Makefile").is_file():
            return {
                "candidate_id": candidate_id, "side": side, "target": target,
                "build": "NOT_APPLICABLE", "runtime": "NOT_APPLICABLE",
                "build_exit_code": "", "runtime_exit_code": "",
                "duration_seconds": "0", "command": "", "diagnostic": "standalone fuzz Makefile/target unavailable",
            }
        prerequisite_command = ["make", "-j4", "mbedtls_test"]
        command = ["make", "-C", "programs/fuzz", "-j4", target]
        started = time.monotonic()
        try:
            prerequisite = subprocess.run(
                prerequisite_command, cwd=tree, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600
            )
            if prerequisite.returncode == 0:
                built = subprocess.run(command, cwd=tree, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       timeout=600)
                combined_output = prerequisite.stdout + built.stdout
            else:
                built = prerequisite
                combined_output = prerequisite.stdout
            build, diagnostic = ("PASS" if built.returncode == 0 else "FAIL"), built.stdout.decode(errors="replace")[-16000:]
            diagnostic = combined_output.decode(errors="replace")[-16000:]
        except subprocess.TimeoutExpired as exc:
            built = None
            build, diagnostic = "TIMEOUT", (exc.stdout or b"").decode(errors="replace")[-16000:]
        runtime, runtime_code = "NOT_RUN", ""
        executable = tree / "programs" / "fuzz" / target
        if build == "PASS":
            sample = tree / ".probe-input"
            sample.write_bytes(b"\x00{}\n")
            try:
                ran = subprocess.run([str(executable), str(sample)], cwd=tree, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, timeout=30)
                runtime_code = str(ran.returncode)
                runtime = "PASS" if ran.returncode == 0 else "FAIL"
                diagnostic += "\nRUNTIME:\n" + ran.stdout.decode(errors="replace")[-4000:]
            except subprocess.TimeoutExpired as exc:
                runtime = "TIMEOUT"
                diagnostic += "\nRUNTIME TIMEOUT:\n" + (exc.stdout or b"").decode(errors="replace")[-4000:]
        return {
            "candidate_id": candidate_id, "side": side, "target": target,
            "build": build, "runtime": runtime,
            "build_exit_code": "" if built is None else str(built.returncode),
            "runtime_exit_code": runtime_code,
            "duration_seconds": f"{time.monotonic() - started:.3f}",
            "command": " ".join(prerequisite_command) + " ; " + " ".join(command), "diagnostic": diagnostic,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate_ids", nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    csv.field_size_limit(sys.maxsize)
    candidates = {
        row["candidate_id"]: row
        for row in csv.DictReader((DATA / "new_candidates.csv").open(encoding="utf-8", newline=""))
    }
    rows: list[dict[str, str]] = []
    for candidate_id in args.candidate_ids:
        item = candidates[candidate_id]
        if item["project"] != "mbedtls":
            raise SystemExit(f"not Mbed TLS: {candidate_id}")
        paths = json.loads(item["harness_files_changed"])
        for side, revision, h0 in (
            ("S0_H0", item["parent"], False),
            ("S1_H0", item["commit"], True),
            ("S1_H1", item["commit"], False),
        ):
            print(candidate_id, side, flush=True)
            rows.append(probe_side(candidate_id, side, revision, item["parent"], paths, h0))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["candidate_id", "side", "target", "build", "runtime", "build_exit_code",
              "runtime_exit_code", "duration_seconds", "command", "diagnostic"]
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"rows": len(rows), "output": str(args.output)}))


if __name__ == "__main__":
    main()
