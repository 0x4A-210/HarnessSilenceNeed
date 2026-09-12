#!/usr/bin/env python3
"""Component-level three-way state probe for Solidity candidate N071.

The driver compiles the real historical libyul/YulString.h.  For each side it
injects the exact reset statement only when that statement exists in the real
historical strictasm_diff_ossfuzz.cpp harness.  Two simulated fuzz iterations
then expose repository ID reuse (H1) versus cross-iteration accumulation (H0).
"""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
WORKSPACE = ROOT.parent
REPO = WORKSPACE / "FSE2026-harness-degradation" / "sources" / "projects" / "solidity"
DATA = ROOT / "data"
GROUND = ROOT / "ground-truth"
CANDIDATE_ID = "N071"
HARNESS = "test/tools/ossfuzz/strictasm_diff_ossfuzz.cpp"


def git_bytes(*args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(REPO), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace"))
    return result.stdout


def probe(side: str, source_revision: str, harness_revision: str) -> dict[str, str]:
    harness_text = git_bytes("show", f"{harness_revision}:{HARNESS}").decode(errors="replace")
    reset_statement = "YulStringRepository::reset();"
    has_reset = reset_statement in harness_text
    with tempfile.TemporaryDirectory(prefix=f"solidity-reset-{side}-") as temporary:
        tree = Path(temporary)
        header = tree / "libyul" / "YulString.h"
        header.parent.mkdir(parents=True)
        header.write_bytes(git_bytes("show", f"{source_revision}:libyul/YulString.h"))
        boost = tree / "boost" / "noncopyable.hpp"
        boost.parent.mkdir(parents=True)
        boost.write_text(
            "#pragma once\nnamespace boost { class noncopyable { protected: noncopyable() = default; "
            "~noncopyable() = default; noncopyable(noncopyable const&) = delete; "
            "noncopyable& operator=(noncopyable const&) = delete; }; }\n", encoding="utf-8")
        driver = tree / "probe.cpp"
        reset_line = f"  {reset_statement}\n" if has_reset else ""
        driver.write_text(
            "#include <cstdint>\n#include <iostream>\n#include <libyul/YulString.h>\n"
            "using yul::YulStringRepository;\n"
            "static void fuzz_iteration(char const* value) {\n" + reset_line +
            "  auto h = YulStringRepository::instance().stringToHandle(value);\n"
            "  std::cout << h.id << \" \";\n"
            "}\nint main() { fuzz_iteration(\"alpha\"); fuzz_iteration(\"beta\"); std::cout << \"\\n\"; }\n",
            encoding="utf-8")
        executable = tree / "probe"
        command = [shutil.which("g++") or "g++", "-std=gnu++17", "-O0", "-I", str(tree),
                   str(driver), "-o", str(executable)]
        started = time.monotonic()
        built = subprocess.run(command, cwd=tree, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        build = "PASS" if built.returncode == 0 else "FAIL"
        runtime = "NOT_RUN"; runtime_code = ""; observation = ""
        if build == "PASS":
            ran = subprocess.run([str(executable)], cwd=tree, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, timeout=30)
            runtime = "PASS" if ran.returncode == 0 else "FAIL"
            runtime_code = str(ran.returncode)
            observation = (ran.stdout + ran.stderr).decode(errors="replace").strip()
        return {
            "candidate_id": CANDIDATE_ID, "side": side, "source_revision": source_revision,
            "harness_revision": harness_revision, "harness_file": HARNESS,
            "historical_harness_contains_reset": "YES" if has_reset else "NO",
            "build": build, "runtime": runtime, "build_exit_code": str(built.returncode),
            "runtime_exit_code": runtime_code, "runtime_observation_iteration_ids": observation,
            "duration_seconds": f"{time.monotonic()-started:.3f}", "command": " ".join(command),
            "diagnostic": (built.stdout + built.stderr).decode(errors="replace")[-12000:],
            "scope": "real YulString.h plus reset statement presence from historical OSS-Fuzz harness; component state probe",
        }


def main() -> None:
    csv.field_size_limit(sys.maxsize)
    candidates = {row["candidate_id"]: row for row in csv.DictReader((DATA / "new_candidates.csv").open(encoding="utf-8"))}
    row = candidates[CANDIDATE_ID]
    rows = [
        probe("S0_H0", row["parent"], row["parent"]),
        probe("S1_H0", row["commit"], row["parent"]),
        probe("S1_H1", row["commit"], row["commit"]),
    ]
    path = GROUND / "solidity_reset_state_probe_details.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
