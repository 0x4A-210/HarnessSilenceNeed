#!/usr/bin/env python3
"""Perform the pre-prediction objective audit for all selected N4/P cases."""

from __future__ import annotations

import concurrent.futures
import csv
import hashlib
import io
import json
import os
import re
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
GT = ROOT / "ground-truth"
EVIDENCE = GT / "evidence"

PRIOR_DATA = [
    WORKSPACE / "silent-harness-maintenance" / "data" / "new_candidates.csv",
    WORKSPACE / "silent-harness-maintenance" / "data" / "source_only_negative_controls.csv",
    WORKSPACE / "silent-harness-maintenance" / "data" / "prior_commit_exclusions.csv",
    WORKSPACE / "pre-test" / "data" / "case_mapping.csv",
    WORKSPACE / "pre-test" / "holdout" / "data" / "case_mapping.csv",
    WORKSPACE / "harness-maintenance-new-pilot" / "data" / "co_evolution_candidates.csv",
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_bytes(*args: str, check: bool = True) -> bytes:
    result = subprocess.run(["git", "-C", str(REPO), *args], stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    if check and result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace"))
    return result.stdout


def git(*args: str, check: bool = True) -> str:
    return git_bytes(*args, check=check).decode("utf-8", errors="replace")


def show_file(revision: str, path: str) -> str:
    return git("show", f"{revision}:{path}", check=False)


def target_matches(text: str, target: str) -> list[re.Match[str]]:
    if target.startswith("QUIRK_"):
        pattern = rf"(?m)^\s*pub\s+const\s+{re.escape(target)}\s*:"
    else:
        pattern = rf"(?m)^\s*pub\s+func\s+{re.escape(target)}[!?]?\s*\("
    return list(re.finditer(pattern, text))


def context_around(text: str, matches: list[re.Match[str]], radius: int = 24) -> str:
    if not matches:
        return "TARGET ABSENT\n"
    lines = text.splitlines()
    chunks = []
    for match in matches:
        number = text.count("\n", 0, match.start()) + 1
        lo, hi = max(1, number - radius), min(len(lines), number + radius)
        chunks.append(f"lines {lo}-{hi}\n" + "\n".join(f"{i:06d}: {lines[i - 1]}" for i in range(lo, hi + 1)))
    return "\n\n".join(chunks) + "\n"


def code_paths(revision: str, prefix: str = "fuzz/c") -> list[str]:
    paths = git("ls-tree", "-r", "--name-only", revision, "--", prefix).splitlines()
    return sorted(p for p in paths if Path(p).suffix in {".c", ".cc", ".cpp", ".h"})


def grep_portfolio(revision: str, needle: str) -> str:
    paths = code_paths(revision)
    hits = []
    for path in paths:
        text = show_file(revision, path)
        for number, line in enumerate(text.splitlines(), 1):
            if needle in line:
                hits.append(f"{revision}:{path}:{number}:{line}")
    return "\n".join(hits) + ("\n" if hits else "")


def choose_harness(revision: str, source_file: str) -> str:
    paths = code_paths(revision, "fuzz/c/std")
    available = set(paths)
    module = source_file.split("/")[1] if source_file.startswith("std/") else ""
    modules = [module]
    if module == "vp8":
        modules.append("webp")
    for name in modules:
        for suffix in (".c", ".cc", ".cpp"):
            candidate = f"fuzz/c/std/{name}_fuzzer{suffix}"
            if candidate in available:
                return candidate
    for candidate in (
        "fuzz/c/std/json_fuzzer.cc", "fuzz/c/std/json_fuzzer.c",
        "fuzz/c/std/cbor_fuzzer.c", "fuzz/c/std/gif_fuzzer.c",
        "fuzz/c/std/bmp_fuzzer.c",
    ):
        if candidate in available:
            return candidate
    raise RuntimeError(f"no stable H0 at {revision}")


def build_and_run(revision: str, harness: str) -> dict[str, object]:
    paths = ["release/c/wuffs-unsupported-snapshot.c", "fuzz/c/fuzzlib", harness]
    archive = git_bytes("archive", "--format=tar", revision, "--", *paths)
    with tempfile.TemporaryDirectory(prefix="n4-ground-truth-build-") as temp_name:
        temp = Path(temp_name)
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tf:
            tf.extractall(temp, filter="data")
        harness_path = temp / harness
        binary = temp / "h0-check"
        compiler = "g++" if harness_path.suffix in {".cc", ".cpp"} else "gcc"
        # The project's runner relies on POSIX PATH_MAX; use GNU language modes
        # just as the README's plain gcc/g++ invocation does.
        language = "gnu++11" if compiler == "g++" else "gnu99"
        command = [compiler, f"-std={language}", "-O0", "-w", "-DWUFFS_CONFIG__FUZZLIB_MAIN",
                   harness_path.name, "-o", str(binary)]
        compiled = subprocess.run(command, cwd=harness_path.parent, text=True,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        seed = temp / "seed.bin"
        seed.write_bytes(b"{}\n")
        runtime_code = None
        runtime_stdout = runtime_stderr = ""
        if compiled.returncode == 0:
            ran = subprocess.run([str(binary), str(seed)], cwd=harness_path.parent, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
            runtime_code, runtime_stdout, runtime_stderr = ran.returncode, ran.stdout, ran.stderr
        return {
            "revision": revision, "harness": harness,
            "compile_command": " ".join(command[:-2] + ["-o", "<temporary-binary>"]),
            "compile_exit_code": compiled.returncode,
            "compile_stdout": compiled.stdout, "compile_stderr": compiled.stderr,
            "runtime_exit_code": runtime_code, "runtime_stdout": runtime_stdout,
            "runtime_stderr": runtime_stderr,
            "build_runtime_pass": compiled.returncode == 0 and runtime_code == 0,
        }


def audit_one(row: dict[str, str]) -> dict[str, str]:
    candidate_id = row["candidate_id"]
    commit, parent = row["commit"], row["parent"]
    target, source_file = row["target_function"], row["source_file"]
    case_dir = EVIDENCE / candidate_id
    case_dir.mkdir(parents=True, exist_ok=True)

    s0_source, s1_source = show_file(parent, source_file), show_file(commit, source_file)
    matches_s0, matches_s1 = target_matches(s0_source, target), target_matches(s1_source, target)
    refs_s0, refs_s1 = grep_portfolio(parent, row["simple_name"]), grep_portfolio(commit, row["simple_name"])
    h0_path = choose_harness(parent, source_file)
    h0_s0, h0_s1 = show_file(parent, h0_path), show_file(commit, h0_path)
    changed_harness_code = [p for p in git("diff", "--name-only", parent, commit, "--", "fuzz/c").splitlines()
                            if Path(p).suffix in {".c", ".cc", ".cpp", ".h"}]
    production_paths = json.loads(row["production_source_files"])
    source_diff = git("diff", "--no-ext-diff", "--no-renames", "--unified=12", parent, commit, "--", *production_paths)

    expected_n4 = row["case_type"] == "N4_EXISTING_GAP"
    target_state_ok = ((len(matches_s0) >= 1 and len(matches_s1) >= 1) if expected_n4
                       else (len(matches_s0) == 0 and len(matches_s1) >= 1))
    static_gap_ok = (not refs_s0.strip()) and (not refs_s1.strip())
    h0_fixed = sha256(h0_s0.encode()) == sha256(h0_s1.encode()) and not changed_harness_code
    meaningful = int(row["production_changed_loc"]) > 0

    build_s0 = build_and_run(parent, h0_path)
    build_s1 = build_and_run(commit, h0_path)
    build_pair_pass = bool(build_s0["build_runtime_pass"] and build_s1["build_runtime_pass"])

    (case_dir / "production_source.diff").write_text(source_diff, encoding="utf-8")
    (case_dir / "target_context_s0.txt").write_text(context_around(s0_source, matches_s0), encoding="utf-8")
    (case_dir / "target_context_s1.txt").write_text(context_around(s1_source, matches_s1), encoding="utf-8")
    (case_dir / "harness_references_s0.txt").write_text(refs_s0 or "NO MATCHES\n", encoding="utf-8")
    (case_dir / "harness_references_s1.txt").write_text(refs_s1 or "NO MATCHES\n", encoding="utf-8")
    (case_dir / f"H0{Path(h0_path).suffix}").write_text(h0_s0, encoding="utf-8")
    (case_dir / "build_s0.json").write_text(json.dumps(build_s0, indent=2, sort_keys=True) + "\n")
    (case_dir / "build_s1.json").write_text(json.dumps(build_s1, indent=2, sort_keys=True) + "\n")

    valid = target_state_ok and static_gap_ok and h0_fixed and meaningful
    if expected_n4:
        evidence_summary = (
            f"{source_file}:{target} is present in both S0 and S1; the complete fuzz/c code portfolio "
            f"contains zero direct references to {row['simple_name']} on both sides; H0 code is byte-identical; "
            "the commit changes production implementation but not this API exposure requirement."
        )
        gap_s0, gap_s1, induced, maintenance = "YES", "YES", "NO", "NO"
        evidence_type = "static_call_path+unchanged_exposure+build_runtime"
    else:
        evidence_summary = (
            f"{source_file}:{target} is absent in S0 and introduced in S1; the unchanged fuzz/c portfolio "
            f"contains zero direct references to {row['simple_name']}; therefore the new public API/configuration "
            "has no H0 exposure path."
        )
        gap_s0, gap_s1, induced, maintenance = "NO", "YES", "YES", "YES"
        evidence_type = "new_symbol_unreachable+unchanged_harness+build_runtime"

    metadata = {
        "candidate_id": candidate_id, "project": row["project"], "commit": commit, "parent": parent,
        "source_file": source_file, "target": target, "case_type": row["case_type"],
        "target_definitions_s0": len(matches_s0), "target_definitions_s1": len(matches_s1),
        "portfolio_references_s0": len(refs_s0.splitlines()) if refs_s0.strip() else 0,
        "portfolio_references_s1": len(refs_s1.splitlines()) if refs_s1.strip() else 0,
        "h0_path": h0_path, "h0_sha256_s0": sha256(h0_s0.encode()), "h0_sha256_s1": sha256(h0_s1.encode()),
        "changed_harness_code": changed_harness_code, "production_source_paths": production_paths,
        "production_source_diff_sha256": sha256(source_diff.encode()), "target_state_ok": target_state_ok,
        "static_gap_ok": static_gap_ok, "h0_fixed": h0_fixed, "meaningful_production_change": meaningful,
        "build_pair_pass": build_pair_pass, "valid_by_predeclared_static_criteria": valid,
    }
    (case_dir / "audit.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    return {
        "candidate_id": candidate_id, "project": row["project"], "commit": commit, "parent": parent,
        "timestamp": row["timestamp"], "case_type": row["case_type"], "label": row["label"],
        "source_file": source_file, "target_symbol": f"{source_file}:{target}", "functional_family": row["functional_family"],
        "gap_exists_s0": gap_s0, "gap_exists_s1": gap_s1, "commit_induced": induced,
        "maintenance_needed": maintenance, "evidence_type": evidence_type,
        "evidence_summary": evidence_summary, "target_definitions_s0": str(len(matches_s0)),
        "target_definitions_s1": str(len(matches_s1)),
        "portfolio_target_refs_s0": str(len(refs_s0.splitlines()) if refs_s0.strip() else 0),
        "portfolio_target_refs_s1": str(len(refs_s1.splitlines()) if refs_s1.strip() else 0),
        "h0_path": h0_path, "h0_sha256_s0": sha256(h0_s0.encode()), "h0_sha256_s1": sha256(h0_s1.encode()),
        "h0_code_unchanged": str(h0_fixed).lower(), "production_changed_loc": row["production_changed_loc"],
        "meaningful_production_change": str(meaningful).lower(), "build_s0_pass": str(build_s0["build_runtime_pass"]).lower(),
        "build_s1_pass": str(build_s1["build_runtime_pass"]).lower(), "build_pair_pass": str(build_pair_pass).lower(),
        "audit_status": "VALID" if valid else "INVALID", "audit_before_prediction": "true",
        "evidence_directory": f"ground-truth/evidence/{candidate_id}",
    }


def prior_commits() -> tuple[set[str], list[str]]:
    result: set[str] = set()
    checked = []
    csv.field_size_limit(sys.maxsize)
    for path in PRIOR_DATA:
        if not path.exists():
            continue
        checked.append(str(path.relative_to(WORKSPACE)))
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("project") not in (None, "", "wuffs"):
                    continue
                for key in ("commit", "commit_id"):
                    if row.get(key):
                        result.add(row[key])
    return result, checked


def main() -> None:
    if any((ROOT / "predictions").glob("*.jsonl")):
        raise SystemExit("refusing to audit after predictions exist")
    csv.field_size_limit(sys.maxsize)
    rows = []
    for filename in ("n4_candidates.csv", "positive_candidates.csv"):
        with (DATA / filename).open(encoding="utf-8", newline="") as handle:
            rows.extend(csv.DictReader(handle))
    if len(rows) != 40:
        raise SystemExit(f"expected 40 candidates, got {len(rows)}")
    prior, checked = prior_commits()
    overlap = [row["commit"] for row in rows if row["commit"] in prior]
    if overlap:
        raise SystemExit(f"prior-data overlap: {overlap}")
    DATA.mkdir(parents=True, exist_ok=True)
    GT.mkdir(parents=True, exist_ok=True)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with (DATA / "independence_audit.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = ["candidate_id", "project", "commit", "prior_data_overlap", "sources_checked"]
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader()
        for row in rows:
            writer.writerow({"candidate_id": row["candidate_id"], "project": row["project"],
                             "commit": row["commit"], "prior_data_overlap": "false",
                             "sources_checked": json.dumps(checked, separators=(",", ":"))})

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(audit_one, row): row["candidate_id"] for row in rows}
        for future in concurrent.futures.as_completed(futures):
            result = future.result(); results.append(result)
            print(f"{len(results):02d}/40 {result['candidate_id']} audit={result['audit_status']} "
                  f"build={result['build_pair_pass']}", flush=True)
    results.sort(key=lambda r: r["candidate_id"])
    n4 = [r for r in results if r["case_type"] == "N4_EXISTING_GAP"]
    positive = [r for r in results if r["case_type"] == "COMMIT_INDUCED_POSITIVE"]
    fields = list(results[0])
    for path, values in ((GT / "n4_audit.csv", n4), (GT / "positive_audit.csv", positive)):
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(values)
    manifest = {
        "stage": "ground-truth-audit-before-freeze", "case_count": 40,
        "valid_n4": sum(r["audit_status"] == "VALID" for r in n4),
        "valid_positive": sum(r["audit_status"] == "VALID" for r in positive),
        "build_pair_pass_count": sum(r["build_pair_pass"] == "true" for r in results),
        "post_prediction_information_used": False, "predictions_existed_during_audit": False,
        "prior_sources_checked": checked, "prior_commit_overlap_count": 0,
    }
    (GT / "audit_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
