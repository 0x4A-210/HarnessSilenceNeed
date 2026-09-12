#!/usr/bin/env python3
"""Mine previously unused Wuffs public-API commits for matched N4 validation.

The unit emitted here is a (commit, public function) pair. A positive signal is
a newly introduced public function. An N4 signal is a meaningfully modified
public function with the same signature on both sides. Both signals require no
direct reference from the parent fuzz harness portfolio and no internal Wuffs
call, making direct API exposure the objectively missing gap.
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path, PurePosixPath

HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
WORKSPACE = ROOT.parent
REPO = WORKSPACE / "FSE2026-harness-degradation" / "sources" / "projects" / "wuffs"
DATA = ROOT / "data"

EXCLUSION_CSVS = [
    WORKSPACE / "silent-harness-maintenance" / "data" / "new_candidates.csv",
    WORKSPACE / "silent-harness-maintenance" / "data" / "source_only_negative_controls.csv",
    WORKSPACE / "silent-harness-maintenance" / "data" / "prior_commit_exclusions.csv",
    WORKSPACE / "pre-test" / "data" / "case_mapping.csv",
    WORKSPACE / "pre-test" / "holdout" / "data" / "case_mapping.csv",
]
FUNC_RE = re.compile(r"^\s*pub\s+func\s+([A-Za-z_][A-Za-z0-9_.]*)[!?]?\s*\(", re.M)
TRIVIAL_MESSAGE = re.compile(r"\b(comment|doc|readme|spelling|typo|format|rename|relicense|license|spdx)\b", re.I)
INTERFACE_NAMES = {
    "decode_frame", "decode_frame_config", "decode_image_config", "decode_tokens",
    "transform_io", "initialize", "workbuf_len", "set_quirk", "set_report_metadata",
}


def git(*args: str, check: bool = True) -> str:
    result = subprocess.run(["git", "-C", str(REPO), *args], text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and result.returncode:
        raise RuntimeError(result.stderr)
    return result.stdout


def read_exclusions() -> set[str]:
    result: set[str] = set()
    csv.field_size_limit(sys.maxsize)
    for path in EXCLUSION_CSVS:
        if not path.exists():
            continue
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("project") not in (None, "", "wuffs"):
                    continue
                value = row.get("commit") or row.get("commit_id")
                if value:
                    result.add(value)
    return result


def source_files(commit: str) -> tuple[list[str], list[str]]:
    paths = git("diff-tree", "--no-commit-id", "--name-only", "-r", "--no-renames", commit).splitlines()
    sources = sorted(p for p in paths if p.startswith("std/") and p.endswith(".wuffs"))
    harnesses = sorted(p for p in paths if "fuzz" in p.lower() and PurePosixPath(p).suffix in {".c", ".cc", ".cpp"})
    return sources, harnesses


def parse_functions(text: str) -> dict[str, tuple[int, int, str]]:
    lines = text.splitlines()
    starts = []
    for number, line in enumerate(lines, 1):
        match = re.match(r"\s*pub\s+func\s+([A-Za-z_][A-Za-z0-9_.]*)[!?]?\s*\(", line)
        if match:
            starts.append((number, match.group(1), re.sub(r"\s+", " ", line.strip())))
    result = {}
    for index, (start, name, signature) in enumerate(starts):
        end = (starts[index + 1][0] - 1) if index + 1 < len(starts) else len(lines)
        result[name] = (start, end, signature)
    return result


def changed_new_lines(parent: str, commit: str, path: str) -> tuple[set[int], int, int]:
    patch = git("diff", "--unified=0", parent, commit, "--", path)
    current = 0
    changed: set[int] = set()
    semantic_added = semantic_deleted = 0
    for line in patch.splitlines():
        match = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
        if match:
            current = int(match.group(1))
            continue
        if line.startswith("+") and not line.startswith("+++"):
            body = line[1:].strip()
            if body and not body.startswith("//"):
                changed.add(current); semantic_added += 1
            current += 1
        elif line.startswith("-") and not line.startswith("---"):
            body = line[1:].strip()
            if body and not body.startswith("//"):
                semantic_deleted += 1
        elif current and not line.startswith("\\"):
            current += 1
    return changed, semantic_added, semantic_deleted


def direct_reference_count(revision: str, simple: str) -> int:
    # Search source language and fuzz harnesses. Definitions are counted and
    # subtracted by the caller; generated snapshots are deliberately excluded.
    output = git("grep", "-n", "-E", rf"(^|[^A-Za-z0-9_]){re.escape(simple)}([!?]?[[:space:]]*\\(|[^A-Za-z0-9_])",
                 revision, "--", "std/*.wuffs", "std/**/*.wuffs", "fuzz/*.c", "fuzz/**/*.c", "fuzz/**/*.cc", check=False)
    return len([line for line in output.splitlines() if line])


def fuzz_reference_count(revision: str, simple: str) -> int:
    output = git("grep", "-n", "-E", rf"{re.escape(simple)}", revision, "--", "fuzz/*.c", "fuzz/**/*.c", "fuzz/**/*.cc", check=False)
    return len([line for line in output.splitlines() if line])


def main() -> None:
    excluded = read_exclusions()
    # The 2022+ window is large enough for the requested strata and avoids
    # needlessly traversing early experimental history. This cutoff is fixed
    # before candidate labels or predictions are selected.
    commits = git("rev-list", "--all", "--no-merges", "--since=2022-01-01", "--", "std").splitlines()
    rows = []
    seen_commits = 0
    for commit in commits:
        if commit in excluded:
            continue
        parents = git("show", "-s", "--format=%P", commit).split()
        if len(parents) != 1:
            continue
        parent = parents[0]
        sources, harnesses = source_files(commit)
        if not sources or harnesses:
            continue
        message = git("show", "-s", "--format=%s", commit).strip()
        if TRIVIAL_MESSAGE.search(message):
            continue
        timestamp = git("show", "-s", "--format=%aI", commit).strip()
        seen_commits += 1
        for path in sources:
            old = git("show", f"{parent}:{path}", check=False)
            new = git("show", f"{commit}:{path}", check=False)
            if not new:
                continue
            old_funcs, new_funcs = parse_functions(old), parse_functions(new)
            changed, added_loc, deleted_loc = changed_new_lines(parent, commit, path)
            for name, (start, end, signature) in new_funcs.items():
                simple = name.rsplit(".", 1)[-1]
                if simple in INTERFACE_NAMES or not any(start <= line <= end for line in changed):
                    continue
                old_entry = old_funcs.get(name)
                signal = ""
                if old_entry is None:
                    signal = "COMMIT_INDUCED_POSITIVE_SIGNAL"
                elif old_entry[2] == signature:
                    signal = "N4_EXISTING_GAP_SIGNAL"
                if not signal:
                    continue
                fuzz_refs_s0 = fuzz_reference_count(parent, simple)
                fuzz_refs_s1 = fuzz_reference_count(commit, simple)
                # A public function definition itself is normally one source
                # reference; more references imply an internal caller.
                refs_s0 = direct_reference_count(parent, simple)
                refs_s1 = direct_reference_count(commit, simple)
                internal_calls_s0 = max(0, refs_s0 - (1 if old_entry else 0))
                internal_calls_s1 = max(0, refs_s1 - 1)
                if fuzz_refs_s0 or fuzz_refs_s1 or internal_calls_s0 or internal_calls_s1:
                    continue
                rows.append({
                    "raw_id": "", "project": "wuffs", "commit": commit, "parent": parent,
                    "timestamp": timestamp, "commit_message": message, "source_file": path,
                    "target_function": name, "simple_name": simple, "signal": signal,
                    "signature_s0": old_entry[2] if old_entry else "ABSENT",
                    "signature_s1": signature, "fuzz_refs_s0": fuzz_refs_s0,
                    "fuzz_refs_s1": fuzz_refs_s1, "internal_calls_s0": internal_calls_s0,
                    "internal_calls_s1": internal_calls_s1,
                    "semantic_added_loc_file": added_loc, "semantic_deleted_loc_file": deleted_loc,
                    "source_files_changed": json.dumps(sources, separators=(",", ":")),
                })
    # Prefer one target per commit, with smaller meaningful patches first.
    rows.sort(key=lambda r: (r["signal"], int(r["semantic_added_loc_file"]) + int(r["semantic_deleted_loc_file"]), r["timestamp"], r["commit"], r["target_function"]))
    selected = []
    used = set()
    for row in rows:
        if row["commit"] in used:
            continue
        used.add(row["commit"]); selected.append(row)
    selected.sort(key=lambda r: (r["timestamp"], r["commit"]))
    for index, row in enumerate(selected, 1):
        row["raw_id"] = f"R{index:04d}"
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / "raw_candidates.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(selected[0]) if selected else ["raw_id"])
        writer.writeheader(); writer.writerows(selected)
    counts = defaultdict(int)
    for row in selected:
        counts[row["signal"]] += 1
    manifest = {"excluded_commit_count": len(excluded), "source_only_commits_screened": seen_commits,
                "raw_function_candidates": len(rows), "unique_commit_candidates": len(selected),
                "counts": dict(counts), "selection_uses_predictions": False}
    (DATA / "mining_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
