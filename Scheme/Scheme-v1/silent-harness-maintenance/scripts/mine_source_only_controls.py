#!/usr/bin/env python3
"""Materialize the pre-audited Wuffs source-only negative-control stratum.

These controls supplement (and never replace) the source+harness co-evolution
candidate pool.  Selection was completed before blind prediction.  Every
selected revision is independent of all earlier development/prompt cases, has
production-source changes, has no fuzz-harness change, and retains an
appropriate pre-existing harness byte-for-byte.  The semantic strata are
restricted to refactoring/comment/naming changes or bounds/compiler-cleanup
changes for which the old harness still exercises the same public entry path.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath


HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
WORKSPACE = ROOT.parent
REPO = WORKSPACE / "FSE2026-harness-degradation" / "sources" / "projects" / "wuffs"
DATA = ROOT / "data"
SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".inc", ".wuffs"}
HARNESS_PARTS = {"fuzz", "fuzzing", "fuzzers", "ossfuzz", "oss-fuzz"}
NON_PRODUCTION_PARTS = {
    "test", "tests", "testing", "fuzz", "fuzzing", "fuzzers", "doc", "docs",
    "example", "examples", "bench", "benchmark", "benchmarks", "third_party",
    "vendor", "deps",
}


# prefix, stable harness, negative taxonomy, audit rationale
CONTROL_SPECS = (
    ("0fe5509f1b7e", "fuzz/c/std/json_fuzzer.cc", "N3", "NULL-plus-zero avoidance changes slice implementation safety; the public slice/decoder input protocol is unchanged."),
    ("3fce6225c9b4", "fuzz/c/std/webp_fuzzer.c", "N1", "VP8 reconstruction changes are comments only; generated executable decoder statements are unchanged."),
    ("214b63c275ad", "fuzz/c/std/webp_fuzzer.c", "N1", "Private VP8 helper/file rename preserves the decoder entry path and call graph."),
    ("18488a3bd0f0", "fuzz/c/std/bzip2_fuzzer.c", "N1", "Private CLAMP/CLIP table renames preserve values and the decode path."),
    ("0ce35fefdeb1", "fuzz/c/std/webp_fuzzer.c", "N3", "A cast avoids a sign-conversion warning; input semantics and VP8 decoder state are unchanged."),
    ("2560db99aa19", "fuzz/c/std/json_fuzzer.cc", "N3", "C++ warning cleanup in the STB compatibility layer does not change the Wuffs decoder protocol."),
    ("56ee4b5e7f47", "fuzz/c/std/pixel_swizzler_fuzzer.c", "N1", "The image dimension limit change is documentation-only."),
    ("721e5743988a", "fuzz/c/std/pixel_swizzler_fuzzer.c", "N3", "Equivalent preprocessor spelling avoids a compiler warning; pixel configuration semantics are unchanged."),
    ("ce1f59e9ce97", "fuzz/c/std/json_fuzzer.cc", "N1", "Token constants are mechanically reformatted without value changes."),
    ("7a57e2b600f2", "fuzz/c/std/json_fuzzer.cc", "N1", "A redundant internal CPU-family macro is removed; public feature dispatch remains unchanged."),
    ("d8c3deb02824", "fuzz/c/std/json_fuzzer.cc", "N1", "Unused auxiliary DynIOBuffer allocation bookkeeping is removed outside the C fuzz entry path."),
    ("00a01abc4ee2", "fuzz/c/std/json_fuzzer.cc", "N3", "Pointer-end calculations avoid NULL plus zero while retaining slice lengths and public calls."),
    ("3bad76cd2c4f", "fuzz/c/std/pixel_swizzler_fuzzer.c", "N3", "A tautological-limit comparison is made compiler-clean; accepted pixel dimensions do not change."),
    ("f1a9d3449417", "fuzz/c/std/pixel_swizzler_fuzzer.c", "N3", "Explicit conversion cleanup preserves pixel-swizzler inputs and dispatch."),
    ("da40cdf29ff7", "fuzz/c/std/pixel_swizzler_fuzzer.c", "N1", "Pixel-format constants are reformatted with identical numeric values."),
    ("be1b1b564c33", "fuzz/c/std/json_fuzzer.cc", "N1", "Generated local pointer declarations are whitespace-reformatted only."),
    ("992fd9622a32", "fuzz/c/std/json_fuzzer.cc", "N5", "A private XZ bit-vector getter is renamed consistently; it does not alter the JSON harness target or its protocol."),
    ("d40b7fbd7e6a", "fuzz/c/std/png_fuzzer.c", "N1", "An unused internal PNG status constant is removed; no decoder behavior or requirement changes."),
    ("988af1c03c6a", "fuzz/c/std/json_fuzzer.cc", "N3", "Float-conversion signedness cleanup preserves the callable conversion behavior."),
    ("190f24903126", "fuzz/c/std/jpeg_fuzzer.c", "N1", "The JPEG horizontal-rule change is comment-only."),
    ("ad7fda33dd5f", "fuzz/c/std/json_fuzzer.cc", "N3", "Auxiliary constant-comparison warning cleanup leaves parser entry and input protocol unchanged."),
    ("99b8c1cb9e69", "fuzz/c/std/bzip2_fuzzer.c", "N1", "The Bzip2 quirk edit adds a comment only; decoder behavior and configuration are unchanged."),
    ("836a87886148", "fuzz/c/std/pixel_swizzler_fuzzer.c", "N1", "Unused pixel-conversion length locals are removed without changing conversion calls."),
    ("3dbfb00c42ba", "fuzz/c/std/jpeg_fuzzer.c", "N1", "The AVX2 upsampling change adds a compiler-explorer comment only."),
    ("bfc7fc2f458f", "fuzz/c/std/jpeg_fuzzer.c", "N1", "The JPEG AVX2 change adds a GCC explanatory comment only."),
    ("2687d1daafd1", "fuzz/c/std/jpeg_fuzzer.c", "N3", "Integer constants are rewritten to avoid pedantic overflow diagnostics; the same upsampling route remains exposed."),
    ("724aec33dfae", "fuzz/c/std/json_fuzzer.cc", "N1", "Generated pointer-to-array expressions lose redundant parentheses only."),
    ("04344db3748c", "fuzz/c/std/pixel_swizzler_fuzzer.c", "N1", "Generator marker comments and the corresponding patch rule are removed; runtime conversion semantics are unchanged."),
    ("f43246e3bbd2", "fuzz/c/std/cbor_fuzzer.c", "N1", "The CBOR source change corrects a BEGIN/END comment typo only."),
    ("5336b511e03b", "fuzz/c/std/json_fuzzer.cc", "N5", "XXHash SIMD documentation changes are outside the JSON harness target and contain no executable change."),
    ("255516bc210a", "fuzz/c/std/jpeg_fuzzer.c", "N1", "The JPEG Huffman-LUT edits add and clarify comments without changing statements."),
    ("1acd74482a5c", "fuzz/c/std/jpeg_fuzzer.c", "N1", "The JPEG EXTEND edits are comments only."),
    ("48fa7182f413", "fuzz/c/std/jpeg_fuzzer.c", "N1", "The JPEG UNZIG edits are comments only."),
)


def git(*args: str, check: bool = True) -> str:
    result = subprocess.run(["git", "-C", str(REPO), *args], text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout


def is_harness(path: str) -> bool:
    posix = PurePosixPath(path.lower())
    return posix.suffix in SOURCE_SUFFIXES and (
        "fuzz" in posix.name or "fuzzer" in posix.name or any(part in HARNESS_PARTS for part in posix.parts)
    )


def is_production(path: str) -> bool:
    posix = PurePosixPath(path.lower())
    return (posix.suffix in SOURCE_SUFFIXES and not is_harness(path)
            and not any(part in NON_PRODUCTION_PARTS for part in posix.parts))


def blob(revision: str, path: str) -> bytes:
    return subprocess.run(["git", "-C", str(REPO), "show", f"{revision}:{path}"],
                          stdout=subprocess.PIPE, check=True).stdout


def main() -> None:
    csv.field_size_limit(sys.maxsize)
    exclusions = {
        row["commit_id"] for row in csv.DictReader((DATA / "prior_commit_exclusions.csv").open(encoding="utf-8"))
        if row["project"] == "wuffs"
    }
    coevolution = {
        row["commit"] for row in csv.DictReader((DATA / "new_candidates.csv").open(encoding="utf-8"))
        if row["project"] == "wuffs"
    }
    rows: list[dict[str, object]] = []
    for index, (prefix, harness, negative_type, rationale) in enumerate(CONTROL_SPECS, 1):
        commit = git("rev-parse", f"{prefix}^{{commit}}").strip()
        parent = git("rev-parse", f"{commit}^1").strip()
        if commit in exclusions or commit in coevolution:
            raise SystemExit(f"control is not independent: {commit}")
        changed = [line for line in git("diff", "--name-only", parent, commit).splitlines() if line]
        harness_changes = sorted(path for path in changed if is_harness(path))
        sources = sorted(path for path in changed if is_production(path))
        if not sources or harness_changes:
            raise SystemExit(f"not source-only: {commit} sources={sources} harness={harness_changes}")
        if blob(parent, harness) != blob(commit, harness):
            raise SystemExit(f"harness not byte-identical: {commit}:{harness}")
        added = deleted = 0
        for line in git("diff", "--numstat", parent, commit, "--", *sources).splitlines():
            a, d, _ = line.split("\t", 2)
            if a == "-" or d == "-":
                raise SystemExit(f"binary production change: {commit}")
            added += int(a); deleted += int(d)
        rows.append({
            "control_id": f"S{index:03d}", "project": "wuffs", "commit": commit,
            "parent": parent, "timestamp": git("show", "-s", "--format=%aI", commit).strip(),
            "source_files_changed": json.dumps(sources, separators=(",", ":")),
            "harness_file": harness, "harness_files_changed": "[]",
            "commit_message": git("show", "-s", "--format=%s", commit).strip(),
            "changed_loc_source": added + deleted, "negative_type": negative_type,
            "audit_rationale": rationale, "selection_stratum": "SOURCE_ONLY_NEGATIVE_CONTROL",
            "h0_h1_blob_identical": "YES",
        })
    path = DATA / "source_only_negative_controls.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    print(json.dumps({"controls": len(rows), "output": str(path)}, indent=2))


if __name__ == "__main__":
    main()
