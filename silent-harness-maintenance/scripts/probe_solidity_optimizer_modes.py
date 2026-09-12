#!/usr/bin/env python3
"""Three-way component probe for Solidity candidate N128.

The probe compiles the exact historical OptimiserSettings.h.  The driver takes
its branch choice from the exact historical strictasm_diff_ossfuzz.cpp: only a
harness revision containing the real removeInvalidCharacters call exercises
the new sequence-cleaning entry.  This keeps the probe small enough to build
without the historical full Solidity toolchain while retaining the production
implementation and the relevant harness decision.
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
CANDIDATE_ID = "N128"
HEADER = "libsolidity/interface/OptimiserSettings.h"
HARNESS = "test/tools/ossfuzz/strictasm_diff_ossfuzz.cpp"


def git_bytes(*args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(REPO), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace"))
    return result.stdout


def probe(side: str, source_revision: str, harness_revision: str) -> dict[str, str]:
    harness_text = git_bytes("show", f"{harness_revision}:{HARNESS}").decode(errors="replace")
    h1_entry = "OptimiserSettings::removeInvalidCharacters(fuzzedSequence)"
    calls_new_entry = h1_entry in harness_text
    with tempfile.TemporaryDirectory(prefix=f"solidity-opt-modes-{side}-") as temporary:
        tree = Path(temporary)
        header = tree / HEADER
        header.parent.mkdir(parents=True)
        header.write_bytes(git_bytes("show", f"{source_revision}:{HEADER}"))
        exceptions = tree / "liblangutil" / "Exceptions.h"
        exceptions.parent.mkdir(parents=True)
        exceptions.write_text(
            "#pragma once\n#include <cassert>\n#include <cstdlib>\n"
            "namespace solidity::util { [[noreturn]] inline void unreachable() { std::abort(); } }\n",
            encoding="utf-8",
        )
        driver = tree / "probe.cpp"
        action = (
            '  std::string fuzzedSequence = "f!l?c:[u]";\n'
            "  auto cleaned = OptimiserSettings::removeInvalidCharacters(fuzzedSequence);\n"
            '  std::cout << "mode=sequence cleaned=" << cleaned << "\\n";\n'
            if calls_new_entry else
            '  auto sequence = OptimiserSettings::randomYulOptimiserSequence(9);\n'
            '  std::cout << "mode=legacy sequence_size=" << sequence.size() << "\\n";\n'
        )
        driver.write_text(
            "#include <iostream>\n#include <string>\n"
            "#include <libsolidity/interface/OptimiserSettings.h>\n"
            "using solidity::frontend::OptimiserSettings;\n"
            "int main() {\n" + action + "  return 0;\n}\n",
            encoding="utf-8",
        )
        executable = tree / "probe"
        command = [
            shutil.which("g++") or "g++", "-std=gnu++17", "-O0", "--coverage",
            "-I", str(tree), str(driver), "-o", str(executable),
        ]
        started = time.monotonic()
        built = subprocess.run(command, cwd=tree, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        build = "PASS" if built.returncode == 0 else "FAIL"
        runtime = "NOT_RUN"
        runtime_code = ""
        observation = ""
        helper_covered_lines = "NOT_APPLICABLE" if source_revision != candidates_row()["commit"] else "0"
        if build == "PASS":
            ran = subprocess.run([str(executable)], cwd=tree, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            runtime = "PASS" if ran.returncode == 0 else "FAIL"
            runtime_code = str(ran.returncode)
            observation = (ran.stdout + ran.stderr).decode(errors="replace").strip()
            if source_revision == candidates_row()["commit"]:
                gcov = subprocess.run(
                    [shutil.which("gcov") or "gcov", "-b", "-c", "-o", str(tree), str(driver)],
                    cwd=tree, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
                )
                gcov_files = list(tree.glob("*OptimiserSettings.h.gcov"))
                covered = 0
                if gcov.returncode == 0 and gcov_files:
                    in_helper = False
                    depth = 0
                    for line in gcov_files[0].read_text(errors="replace").splitlines():
                        parts = line.split(":", 2)
                        if len(parts) != 3:
                            continue
                        count, _, source = parts
                        if "static std::string removeInvalidCharacters" in source:
                            in_helper = True
                        if in_helper:
                            stripped = source.strip()
                            if stripped and not stripped.startswith(("//", "/*", "*")) and count.strip() not in ("-", "#####", "====="):
                                try:
                                    if int(count.strip()) > 0:
                                        covered += 1
                                except ValueError:
                                    pass
                            depth += source.count("{") - source.count("}")
                            if depth == 0 and "}" in source:
                                in_helper = False
                    helper_covered_lines = str(covered)
        return {
            "candidate_id": CANDIDATE_ID,
            "side": side,
            "source_revision": source_revision,
            "harness_revision": harness_revision,
            "harness_file": HARNESS,
            "historical_harness_calls_new_entry": "YES" if calls_new_entry else "NO",
            "build": build,
            "runtime": runtime,
            "build_exit_code": str(built.returncode),
            "runtime_exit_code": runtime_code,
            "runtime_observation": observation,
            "new_helper_covered_executable_lines": helper_covered_lines,
            "duration_seconds": f"{time.monotonic()-started:.3f}",
            "command": " ".join(command),
            "diagnostic": (built.stdout + built.stderr).decode(errors="replace")[-12000:],
            "scope": "real OptimiserSettings.h plus call presence from historical OSS-Fuzz harness; component mode probe",
        }


_CANDIDATE_CACHE: dict[str, str] | None = None


def candidates_row() -> dict[str, str]:
    global _CANDIDATE_CACHE
    if _CANDIDATE_CACHE is None:
        csv.field_size_limit(sys.maxsize)
        rows = csv.DictReader((DATA / "new_candidates.csv").open(encoding="utf-8"))
        _CANDIDATE_CACHE = next(row for row in rows if row["candidate_id"] == CANDIDATE_ID)
    return _CANDIDATE_CACHE


def main() -> None:
    row = candidates_row()
    rows = [
        probe("S0_H0", row["parent"], row["parent"]),
        probe("S1_H0", row["commit"], row["parent"]),
        probe("S1_H1", row["commit"], row["commit"]),
    ]
    path = GROUND / "solidity_optimizer_modes_probe_details.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
