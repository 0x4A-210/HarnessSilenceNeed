#!/usr/bin/env python3
"""Repeated-invocation three-way probe for Mbed TLS candidate N009.

The actual historical fuzz_server.c and libraries are built.  Only the
repository's onefile test driver is instrumented to invoke the fuzzer twice in
one process and print both return values, matching persistent fuzzing state.
"""

from __future__ import annotations

import csv
import json
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
GROUND = ROOT / "ground-truth"
CANDIDATE_ID = "N009"


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


def overlay_h0(tree: Path, parent: str, harnesses: list[str]) -> None:
    for relative in harnesses:
        target = tree / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(git_bytes("show", f"{parent}:{relative}"))


def instrument_driver(tree: Path) -> None:
    path = tree / "programs" / "fuzz" / "onefile.c"
    value = path.read_text(encoding="utf-8")
    old = "    LLVMFuzzerTestOneInput(Data, Size);\n    free(Data);"
    new = (
        "    int first_return = LLVMFuzzerTestOneInput(Data, Size);\n"
        "    int second_return = LLVMFuzzerTestOneInput(Data, Size);\n"
        "    fprintf(stderr, \"REPEATED_RETURNS=%d,%d\\n\", first_return, second_return);\n"
        "    free(Data);"
    )
    if old not in value:
        raise RuntimeError("onefile invocation marker not found")
    path.write_text(value.replace(old, new, 1), encoding="utf-8")


def probe(side: str, revision: str, parent: str, harnesses: list[str], use_h0: bool) -> dict[str, str]:
    with tempfile.TemporaryDirectory(prefix=f"mbedtls-repeat-{side}-") as temporary:
        tree = Path(temporary)
        extract(revision, tree)
        if use_h0:
            overlay_h0(tree, parent, harnesses)
        instrument_driver(tree)
        prerequisite = ["make", "-j4", "mbedtls_test"]
        target = ["make", "-C", "programs/fuzz", "-j4", "fuzz_server"]
        started = time.monotonic()
        pre = subprocess.run(prerequisite, cwd=tree, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, timeout=600)
        if pre.returncode == 0:
            built = subprocess.run(target, cwd=tree, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, timeout=600)
            build_log = pre.stdout + built.stdout
        else:
            built = pre; build_log = pre.stdout
        build = "PASS" if built.returncode == 0 else "FAIL"
        runtime = "NOT_RUN"; runtime_code = ""; observation = ""
        if build == "PASS":
            sample = tree / ".probe-input"
            sample.write_bytes(b"\x00{}\n")
            ran = subprocess.run([str(tree / "programs/fuzz/fuzz_server"), str(sample)], cwd=tree,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
            runtime = "PASS" if ran.returncode == 0 else "FAIL"
            runtime_code = str(ran.returncode)
            observation = ran.stdout.decode(errors="replace")[-8000:]
        return {
            "candidate_id": CANDIDATE_ID, "side": side, "build": build, "runtime": runtime,
            "build_exit_code": str(built.returncode), "runtime_exit_code": runtime_code,
            "runtime_observation": observation, "duration_seconds": f"{time.monotonic()-started:.3f}",
            "command": " ".join(prerequisite) + " ; " + " ".join(target),
            "diagnostic": build_log.decode(errors="replace")[-16000:],
            "scope": "actual fuzz_server and Mbed TLS libraries; onefile wrapper invokes twice in-process",
        }


def main() -> None:
    csv.field_size_limit(sys.maxsize)
    candidates = {row["candidate_id"]: row for row in csv.DictReader((DATA / "new_candidates.csv").open(encoding="utf-8"))}
    row = candidates[CANDIDATE_ID]; harnesses = json.loads(row["harness_files_changed"])
    rows = [
        probe("S0_H0", row["parent"], row["parent"], harnesses, False),
        probe("S1_H0", row["commit"], row["parent"], harnesses, True),
        probe("S1_H1", row["commit"], row["parent"], harnesses, False),
    ]
    path = GROUND / "mbedtls_repeated_state_probe_details.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
