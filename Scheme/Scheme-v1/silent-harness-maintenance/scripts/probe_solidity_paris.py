#!/usr/bin/env python3
"""Component-level three-way probes for Solidity EVM-version candidates.

The historical full Solidity/OSS-Fuzz toolchain is not available in this
workspace.  This probe compiles the real EVMVersion.h from S0/S1 together with
the exact s_evmVersions initializer extracted from H0/H1.  A minimal local
boost/operators.hpp compatibility header supplies only the two empty CRTP base
classes needed by EVMVersion; no production or harness behavior is mocked.
"""

from __future__ import annotations

import csv
import json
import re
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
SPECS = (("N116", "paris"), ("N132", "prague"))


def git_bytes(*args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(REPO), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace"))
    return result.stdout


def vector_initializer(revision: str) -> str:
    text = git_bytes("show", f"{revision}:test/tools/fuzzer_common.cpp").decode()
    match = re.search(r"static (?:std::)?vector<EVMVersion> s_evmVersions\s*=\s*\{(.*?)\};", text, re.S)
    if not match:
        raise RuntimeError(f"s_evmVersions initializer absent at {revision}")
    body = match.group(1)
    calls = re.findall(r"EVMVersion::[A-Za-z_][A-Za-z0-9_]*\(\)", body)
    if not calls:
        raise RuntimeError(f"no EVMVersion calls at {revision}")
    return ",\n    ".join(calls)


def probe(candidate_id: str, version_name: str, side: str,
          source_revision: str, harness_revision: str) -> dict[str, str]:
    with tempfile.TemporaryDirectory(prefix=f"solidity-{version_name}-{side}-") as temporary:
        tree = Path(temporary)
        header = tree / "liblangutil" / "EVMVersion.h"
        header.parent.mkdir(parents=True)
        header.write_bytes(git_bytes("show", f"{source_revision}:liblangutil/EVMVersion.h"))
        boost = tree / "boost" / "operators.hpp"
        boost.parent.mkdir(parents=True)
        boost.write_text(
            "#pragma once\nnamespace boost {\n"
            "template<class T> struct less_than_comparable {\n"
            " friend bool operator>(T const& a, T const& b) { return b < a; }\n"
            " friend bool operator<=(T const& a, T const& b) { return !(b < a); }\n"
            " friend bool operator>=(T const& a, T const& b) { return !(a < b); }\n"
            "};\n"
            "template<class T> struct equality_comparable {\n"
            " friend bool operator!=(T const& a, T const& b) { return !(a == b); }\n"
            "};\n}\n", encoding="utf-8")
        initializer = vector_initializer(harness_revision)
        driver = tree / "probe.cpp"
        driver.write_text(
            "#include <cstdint>\n#include <iostream>\n#include <vector>\n"
            "#include <liblangutil/EVMVersion.h>\n"
            "using solidity::langutil::EVMVersion;\n"
            "static std::vector<EVMVersion> s_evmVersions = {\n    " + initializer + "\n};\n"
            "int main() {\n"
            "  bool vector_has_target = false;\n"
            f"  for (auto const& v : s_evmVersions) vector_has_target |= (v.name() == \"{version_name}\");\n"
            f"  bool source_has_target = EVMVersion::fromString(\"{version_name}\").has_value();\n"
            "  std::cout << \"vector_size=\" << s_evmVersions.size()"
            " << \" vector_has_target=\" << vector_has_target"
            " << \" source_has_target=\" << source_has_target << \"\\n\";\n"
            "  return 0;\n}\n", encoding="utf-8")
        executable = tree / "probe"
        command = [shutil.which("g++") or "g++", "-std=gnu++17", "-O0", "-I", str(tree),
                   str(driver), "-o", str(executable)]
        started = time.monotonic()
        built = subprocess.run(command, cwd=tree, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
        build = "PASS" if built.returncode == 0 else "FAIL"
        runtime = "NOT_RUN"; runtime_code = ""; runtime_output = ""
        if build == "PASS":
            ran = subprocess.run([str(executable)], cwd=tree, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, timeout=30)
            runtime = "PASS" if ran.returncode == 0 else "FAIL"
            runtime_code = str(ran.returncode)
            runtime_output = (ran.stdout + ran.stderr).decode(errors="replace")
        return {
            "candidate_id": candidate_id, "target_version": version_name, "side": side,
            "source_revision": source_revision, "harness_revision": harness_revision,
            "build": build, "runtime": runtime, "build_exit_code": str(built.returncode),
            "runtime_exit_code": runtime_code, "runtime_observation": runtime_output.strip(),
            "duration_seconds": f"{time.monotonic()-started:.3f}", "command": " ".join(command),
            "diagnostic": (built.stdout + built.stderr).decode(errors="replace")[-12000:],
            "scope": "real EVMVersion.h plus exact historical s_evmVersions initializer; component probe",
        }


def main() -> None:
    csv.field_size_limit(sys.maxsize)
    candidates = {row["candidate_id"]: row for row in csv.DictReader((DATA / "new_candidates.csv").open(encoding="utf-8"))}
    output = []
    for candidate_id, version_name in SPECS:
        row = candidates[candidate_id]
        output.extend([
            probe(candidate_id, version_name, "S0_H0", row["parent"], row["parent"]),
            probe(candidate_id, version_name, "S1_H0", row["commit"], row["parent"]),
            probe(candidate_id, version_name, "S1_H1", row["commit"], row["commit"]),
        ])
    path = GROUND / "solidity_version_probe_details.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output[0]))
        writer.writeheader(); writer.writerows(output)
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
