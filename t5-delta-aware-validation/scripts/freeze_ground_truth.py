#!/usr/bin/env python3
"""Validate and freeze the independent Task-5 blind-test ground truth.

The freeze is deliberately performed before blind inputs or predictions exist.
Static entry-exposure evidence is the objective oracle used for this stage.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
T5 = ROOT / "t5-delta-aware-validation"
SPEC = T5 / "new-data" / "selection_spec.csv"
CANDIDATES = T5 / "new-data" / "candidates.csv"
EXCLUDED = T5 / "new-data" / "excluded.csv"
REPOS = ROOT / "FSE2026-harness-degradation" / "sources" / "projects"
FROZEN = T5 / "frozen-ground-truth"
CODE_RE = re.compile(r"\.(?:c|cc|cpp|cxx|h|hh|hpp)$", re.I)
HARNESS_RE = re.compile(r"fuzz", re.I)
NON_PRODUCTION_RE = re.compile(
    r"(?:^|/)(?:test|tests|testing|example|examples|demo|demos|bench|benchmark|benchmarks|doc|docs)(?:/|$)",
    re.I,
)


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def git(repo: Path, *args: str, check: bool = True) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        encoding="utf-8", errors="replace", check=False,
    )
    if check and done.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed in {repo.name}: {done.stderr.strip()}")
    return done.stdout


def tree_paths(repo: Path, revision: str) -> list[str]:
    return git(repo, "ls-tree", "-r", "--name-only", revision).splitlines()


def is_harness(path: str) -> bool:
    return bool(CODE_RE.search(path) and HARNESS_RE.search(path))


def is_production(path: str) -> bool:
    return bool(CODE_RE.search(path) and not HARNESS_RE.search(path) and not NON_PRODUCTION_RE.search(path))


def file_at(repo: Path, revision: str, path: str) -> str:
    return git(repo, "show", f"{revision}:{path}")


def batch_files(repo: Path, revision: str, paths: list[str]) -> dict[str, str]:
    """Read many tree blobs through one persistent git cat-file process."""
    if not paths:
        return {}
    process = subprocess.Popen(
        ["git", "-C", str(repo), "cat-file", "--batch"], stdin=subprocess.PIPE,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    assert process.stdin is not None and process.stdout is not None
    process.stdin.write("".join(f"{revision}:{path}\n" for path in paths).encode())
    process.stdin.close()
    result: dict[str, str] = {}
    for path in paths:
        header = process.stdout.readline().decode("utf-8", errors="replace").rstrip("\n")
        parts = header.split()
        if len(parts) != 3 or parts[1] != "blob":
            raise RuntimeError(f"cat-file failed for {revision}:{path}: {header}")
        size = int(parts[2])
        data = process.stdout.read(size)
        separator = process.stdout.read(1)
        if separator != b"\n":
            raise RuntimeError(f"cat-file framing failure for {revision}:{path}")
        result[path] = data.decode("utf-8", errors="replace")
    stderr = process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
    code = process.wait()
    if code:
        raise RuntimeError(f"git cat-file failed in {repo.name}: {stderr.strip()}")
    return result


def select_matches(files: dict[str, str], paths: list[str], needle: str) -> tuple[int, list[str]]:
    count = 0
    excerpts: list[str] = []
    for path in paths:
        for line_no, line in enumerate(files.get(path, "").splitlines(), 1):
            occurrences = line.count(needle)
            if occurrences:
                count += occurrences
                if len(excerpts) < 12:
                    excerpts.append(f"{path}:{line_no}:{line.strip()}")
    return count, excerpts


def canonical_dataset(rows: list[dict[str, str]]) -> bytes:
    keys = ["case_id", "project", "commit_id", "previous_commit", "commit_time"]
    value = [{key: row[key] for key in keys} for row in rows]
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def main() -> None:
    if FROZEN.exists():
        raise SystemExit("refusing to overwrite frozen ground truth")
    spec = list(csv.DictReader(SPEC.open(encoding="utf-8", newline="")))
    candidate_ids = {row["commit_id"] for row in csv.DictReader(CANDIDATES.open(encoding="utf-8", newline=""))}
    excluded_ids = {row["commit_id"] for row in csv.DictReader(EXCLUDED.open(encoding="utf-8", newline=""))}
    if len(spec) != 40 or len({row["case_id"] for row in spec}) != 40 or len({row["commit_id"] for row in spec}) != 40:
        raise SystemExit("selection must contain 40 unique cases and 40 unique commits")
    labels = Counter(row["label"] for row in spec)
    projects = Counter(row["project"] for row in spec)
    if labels != {"N4": 20, "POSITIVE": 20}:
        raise SystemExit(f"wrong label balance: {labels}")
    if not 3 <= len(projects) <= 8 or max(projects.values()) / len(spec) > 0.40:
        raise SystemExit(f"project constraint failed: {projects}")

    audit: list[dict[str, str]] = []
    evidence_rows: list[dict[str, str]] = []
    for row in spec:
        repo = REPOS / row["project"]
        commit = git(repo, "rev-parse", row["commit_id"]).strip()
        parents = git(repo, "show", "-s", "--format=%P", commit).strip().split()
        if len(parents) != 1:
            raise SystemExit(f"{row['case_id']}: expected one parent, got {len(parents)}")
        parent = parents[0]
        if commit not in candidate_ids or commit in excluded_ids:
            raise SystemExit(f"{row['case_id']}: commit is not independent according to mining outputs")
        ancestor = subprocess.run(
            ["git", "-C", str(repo), "merge-base", "--is-ancestor", commit, "HEAD"], check=False
        ).returncode == 0
        if not ancestor:
            raise SystemExit(f"{row['case_id']}: selected commit is not an ancestor of local HEAD")
        before_tree, after_tree = tree_paths(repo, parent), tree_paths(repo, commit)
        h0_paths = sorted(path for path in before_tree if is_harness(path))
        changed = git(repo, "diff", "--name-only", parent, commit).splitlines()
        changed_harness = sorted(path for path in changed if is_harness(path))
        changed_production = sorted(path for path in changed if is_production(path))
        if not h0_paths or changed_harness or not changed_production:
            raise SystemExit(
                f"{row['case_id']}: harness={len(h0_paths)} changed_harness={changed_harness} production={changed_production}"
            )
        # The complete H0 inventory is searched. Production identity is searched
        # in every changed production file (the same deterministic set exposed
        # to the model), avoiding unrelated vendored trees and test corpora.
        s0_paths = [path for path in changed_production if path in before_tree]
        s1_paths = [path for path in changed_production if path in after_tree]
        before_files = batch_files(repo, parent, sorted(set(h0_paths + s0_paths)))
        after_files = batch_files(repo, commit, s1_paths)
        h0_count, h0_excerpt = select_matches(before_files, h0_paths, row["target_symbol"])
        s0_count, s0_excerpt = select_matches(before_files, s0_paths, row["target_symbol"])
        s1_count, s1_excerpt = select_matches(after_files, s1_paths, row["target_symbol"])
        if h0_count != 0:
            raise SystemExit(f"{row['case_id']}: target occurs {h0_count} times in complete H0")
        if row["label"] == "POSITIVE" and not (s0_count == 0 and s1_count > 0):
            raise SystemExit(f"{row['case_id']}: NEW static oracle failed ({s0_count} -> {s1_count})")
        if row["label"] == "N4" and not (s0_count > 0 and s1_count > 0):
            raise SystemExit(f"{row['case_id']}: existing-entry static oracle failed ({s0_count} -> {s1_count})")
        harness_blob = "".join(
            f"PATH:{path}\n{before_files[path]}\n" for path in h0_paths
        ).encode()
        production_diff = git(repo, "diff", "--no-ext-diff", "--unified=3", parent, commit, "--", *changed_production)
        target_in_diff = row["target_symbol"] in production_diff
        commit_time = git(repo, "show", "-s", "--format=%cI", commit).strip()
        common = {
            **row, "commit_id": commit, "previous_commit": parent, "commit_time": commit_time,
            "h0_file_count": str(len(h0_paths)), "h0_target_occurrences": str(h0_count),
            "s0_target_occurrences": str(s0_count), "s1_target_occurrences": str(s1_count),
            "changed_harness_file_count": str(len(changed_harness)),
            "target_present_in_production_diff": str(target_in_diff).lower(),
            "audit_status": "VALID",
        }
        audit.append(common)
        evidence_rows.append({
            "case_id": row["case_id"], "project": row["project"], "commit_id": commit,
            "previous_commit": parent, "commit_time": commit_time, "target_symbol": row["target_symbol"],
            "evidence_type": row["evidence_type"], "h0_harness_paths": ";".join(h0_paths),
            "h0_harness_sha256": sha_bytes(harness_blob), "h0_target_occurrences": str(h0_count),
            "s0_target_occurrences": str(s0_count), "s1_target_occurrences": str(s1_count),
            "s0_match_excerpt": " | ".join(s0_excerpt) or "ABSENT",
            "s1_match_excerpt": " | ".join(s1_excerpt),
            "changed_production_paths": ";".join(changed_production),
            "changed_harness_paths": ";".join(changed_harness) or "NONE",
            "production_diff_sha256": sha_bytes(production_diff.encode()),
            "target_present_in_production_diff": str(target_in_diff).lower(),
            "semantic_audit": row["semantic_audit"], "audit_status": "VALID",
        })

    FROZEN.mkdir(parents=True)
    audit_fields = list(audit[0])
    with (T5 / "new-data" / "audit.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=audit_fields); writer.writeheader(); writer.writerows(audit)
    label_fields = [
        "case_id", "project", "commit_id", "previous_commit", "commit_time", "label",
        "expected_gap_before", "expected_gap_after", "expected_delta", "maintenance_needed",
        "impact_scope", "audit_status",
    ]
    with (FROZEN / "labels.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=label_fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(audit)
    evidence_fields = list(evidence_rows[0])
    with (FROZEN / "evidence.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=evidence_fields); writer.writeheader(); writer.writerows(evidence_rows)
    frozen_at = now()
    manifest = {
        "status": "FROZEN", "frozen_at": frozen_at, "case_count": 40,
        "label_counts": dict(sorted(labels.items())), "project_counts": dict(sorted(projects.items())),
        "project_count": len(projects), "max_project_share": max(projects.values()) / len(spec),
        "dataset_hash": sha_bytes(canonical_dataset(audit)),
        "ground_truth_hash": sha_bytes((FROZEN / "labels.csv").read_bytes() + (FROZEN / "evidence.csv").read_bytes()),
        "labels_sha256": sha_file(FROZEN / "labels.csv"), "evidence_sha256": sha_file(FROZEN / "evidence.csv"),
        "selection_spec_sha256": sha_file(SPEC), "candidate_pool_sha256": sha_file(CANDIDATES),
        "prior_exclusions_sha256": sha_file(EXCLUDED),
        "oracle": "static public-entry exposure/protocol evidence plus complete H0 identifier inventory and manual semantic diff audit",
        "ordering": {"ground_truth_frozen_at": frozen_at, "input_frozen_at": None, "prediction_started_at": None},
        "post_freeze_policy": "No relabeling. Audit defects may only be recorded as INVALID without replacement.",
        "relabels_after_freeze": 0, "invalidations_after_freeze": 0,
    }
    (FROZEN / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
