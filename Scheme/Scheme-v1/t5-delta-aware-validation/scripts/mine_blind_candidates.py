#!/usr/bin/env python3
"""Mine commit-level candidates while conservatively excluding all prior pools.

This script is deterministic and read-only with respect to the source repositories.
It intentionally emits a broad audit pool; semantic labeling happens separately.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "t5-delta-aware-validation" / "new-data"
REPOS = ROOT / "FSE2026-harness-degradation" / "sources" / "projects"
PROJECTS = ["c-ares", "jansson", "leptonica", "libplist", "libspng", "meshoptimizer"]
SHA_RE = re.compile(r"\b[0-9a-f]{40}\b")
CODE_RE = re.compile(r"\.(?:c|cc|cpp|cxx|h|hh|hpp)$", re.I)
# Project layouts vary (``test/ares-fuzz.c``, ``tools/codecfuzz.cpp``,
# ``prog/fuzzing/...``), so a path-level ``fuzz`` marker is the stable rule.
HARNESS_RE = re.compile(r"fuzz", re.I)
NON_PRODUCTION_RE = re.compile(
    r"(?:^|/)(?:test|tests|testing|example|examples|demo|demos|bench|benchmark|benchmarks|doc|docs)(?:/|$)",
    re.I,
)

# These are the only prior directories that can contain case/candidate identities.
# Raw source repositories and Task-5 outputs are deliberately not searched.
EXCLUSION_ROOTS = [
    ROOT / "harness-maintenance-new-pilot" / "data",
    ROOT / "harness-maintenance-new-pilot" / "results",
    ROOT / "pre-test" / "data",
    ROOT / "pre-test" / "holdout" / "data",
    ROOT / "n4-validation" / "data",
    ROOT / "n4-validation" / "frozen-ground-truth",
    ROOT / "silent-harness-maintenance" / "data",
    ROOT / "silent-harness-maintenance" / "frozen-ground-truth",
    ROOT / "t5-delta-aware-validation" / "development-set",
    ROOT / "FSE2026-harness-degradation" / "config",
    ROOT / "FSE2026-harness-degradation" / "evidence",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prior_shas() -> tuple[set[str], dict[str, set[str]]]:
    found: dict[str, set[str]] = {}
    for directory in EXCLUSION_ROOTS:
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".csv", ".json", ".jsonl", ".md", ".txt"}:
                continue
            values = set(SHA_RE.findall(path.read_text(encoding="utf-8", errors="ignore")))
            for value in values:
                found.setdefault(value, set()).add(str(path.relative_to(ROOT)))
    return set(found), found


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], encoding="utf-8", errors="replace"
    )


def changed_commits(repo: Path) -> list[dict[str, object]]:
    raw = git(repo, "log", "--all", "--no-merges", "--format=@@@%H%x09%P%x09%ct%x09%cs%x09%s", "--name-only")
    commits: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for line in raw.splitlines() + ["@@@END\t\t\t\t"]:
        if line.startswith("@@@"):
            if current is not None:
                commits.append(current)
            parts = line[3:].split("\t", 4)
            if parts[0] == "END":
                current = None
            else:
                current = {
                    "commit_id": parts[0], "parents": parts[1], "commit_epoch": parts[2],
                    "commit_date": parts[3], "subject": parts[4], "paths": [],
                }
        elif current is not None and line.strip():
            current["paths"].append(line.strip())
    return commits


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    excluded, provenance = prior_shas()
    candidates: list[dict[str, object]] = []
    exclusion_rows: list[dict[str, str]] = []
    for project in PROJECTS:
        repo = REPOS / project
        for item in changed_commits(repo):
            paths = list(item.pop("paths"))
            code = [path for path in paths if CODE_RE.search(path)]
            harness = [path for path in code if HARNESS_RE.search(path)]
            production = [
                path for path in code
                if path not in harness and not NON_PRODUCTION_RE.search(path)
            ]
            if not production:
                continue
            commit_id = str(item["commit_id"])
            if commit_id in excluded:
                exclusion_rows.append({
                    "project": project, "commit_id": commit_id,
                    "reason": "exact SHA present in a prior case or candidate artifact",
                    "prior_files": ";".join(sorted(provenance[commit_id])),
                })
                continue
            parent_count = len(str(item["parents"]).split())
            candidates.append({
                "project": project, **item, "parent_count": parent_count,
                "touches_harness": bool(harness), "harness_paths": ";".join(harness),
                "production_paths": ";".join(production), "all_changed_paths": ";".join(paths),
                "candidate_class": "cochange" if harness else "source_only",
                "audit_status": "UNAUDITED",
            })
    candidates.sort(key=lambda row: (str(row["project"]), -int(str(row["commit_epoch"]))))
    fields = [
        "project", "commit_id", "parents", "parent_count", "commit_epoch", "commit_date", "subject",
        "candidate_class", "touches_harness", "harness_paths", "production_paths", "all_changed_paths",
        "audit_status",
    ]
    with (OUT / "candidates.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(candidates)
    with (OUT / "excluded.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["project", "commit_id", "reason", "prior_files"])
        writer.writeheader(); writer.writerows(sorted(exclusion_rows, key=lambda row: (row["project"], row["commit_id"])))
    manifest = {
        "projects": PROJECTS, "candidate_count": len(candidates), "excluded_exact_sha_count": len(exclusion_rows),
        "unique_prior_sha_count": len(excluded),
        "candidate_sha256": sha256(OUT / "candidates.csv"),
        "excluded_sha256": sha256(OUT / "excluded.csv"),
        "note": "Broad deterministic mining output; UNAUDITED rows are not ground truth.",
    }
    (OUT / "mining_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, ensure_ascii=False))


if __name__ == "__main__":
    main()
