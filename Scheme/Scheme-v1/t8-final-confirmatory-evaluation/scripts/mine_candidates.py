#!/usr/bin/env python3
"""Mine path-level candidate pools before any Task-8 labels or predictions exist."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from common import ROOT, REPOS, SPLITS, WORKSPACE, git, is_harness, is_production, sha256_file, utc_now, write_csv, write_json


PRIOR_SOURCES = [
    "FSE2026-harness-degradation/config/positive_events.csv",
    "harness-maintenance-new-pilot/data/co_evolution_candidates_initial.csv",
    "harness-maintenance-new-pilot/data/co_evolution_semantic_labels_initial.csv",
    "harness-maintenance-new-pilot/data/verified_positive_cases_initial.csv",
    "harness-maintenance-new-pilot/data/verified_negative_cases_initial.csv",
    "pre-test/data/case_mapping.csv",
    "pre-test/holdout/data/case_mapping.csv",
    "silent-harness-maintenance/data/candidate_audit.csv",
    "silent-harness-maintenance/data/excluded_cases.csv",
    "silent-harness-maintenance/data/source_only_negative_controls.csv",
    "silent-harness-maintenance/frozen-ground-truth/labels.csv",
    "n4-validation/data/raw_candidates.csv",
    "n4-validation/data/n4_candidates.csv",
    "n4-validation/data/positive_candidates.csv",
    "n4-validation/data/excluded_cases.csv",
    "n4-validation/frozen-ground-truth/labels.csv",
    "t5-delta-aware-validation/development-set/cases.csv",
    "t5-delta-aware-validation/new-data/audit.csv",
    "t5-delta-aware-validation/new-data/selection_spec.csv",
    "t5-delta-aware-validation/new-data/excluded.csv",
    "t5-delta-aware-validation/frozen-ground-truth/evidence.csv",
    "t6-dynamic-baseline-validation/dataset/cases.csv",
    "t7-target-discovery-reachability/dataset/cases.csv",
]
SHA = re.compile(r"^[0-9a-f]{40}$")
POSITIVE_CUES = ("add", "support", "new", "expose", "api", "parser", "decode", "encode",
                 "fuzz", "option", "config", "state", "protocol", "reader", "writer")
NOISY_CUES = ("format", "clang-format", "typo", "spelling", "license", "reformat", "merge branch")


def prior_commits() -> tuple[set[str], list[dict]]:
    import csv, sys
    csv.field_size_limit(sys.maxsize)
    provenance: dict[str, set[str]] = defaultdict(set)
    for relative in PRIOR_SOURCES:
        path = WORKSPACE / relative
        if not path.is_file():
            continue
        with path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
            for row in csv.DictReader(handle):
                for key in ("commit", "commit_id", "s0_commit", "s1_commit", "parent", "parent_commit", "previous_commit"):
                    value = (row.get(key) or "").lower().strip()
                    if SHA.fullmatch(value):
                        provenance[value].add(relative)
    rows = [{"commit": commit, "prior_sources": ";".join(sorted(sources))}
            for commit, sources in sorted(provenance.items())]
    return set(provenance), rows


def history(project: str) -> list[dict]:
    # Default-branch history only; remote feature branches are outside the sampling frame.
    raw = git(project, "log", "HEAD", "--no-merges",
              "--format=@@%H%x1f%P%x1f%aI%x1f%s", "--name-only").stdout
    rows = []
    meta = None; paths: list[str] = []
    for line in raw.splitlines() + ["@@END\x1f\x1f\x1f"]:
        if line.startswith("@@"):
            if meta:
                production = sorted(path for path in paths if is_production(path))
                harness = sorted(path for path in paths if is_harness(path))
                parents = meta[1].split()
                if production and len(parents) == 1:
                    subject_lower = meta[3].lower()
                    score = sum(2 for cue in POSITIVE_CUES if cue in subject_lower)
                    score -= sum(5 for cue in NOISY_CUES if cue in subject_lower)
                    score += 3 if harness else 0
                    score -= max(0, len(production) + len(harness) - 8)
                    rows.append({
                        "project": project, "split": SPLITS[project], "commit": meta[0],
                        "parent": parents[0], "timestamp": meta[2], "subject": meta[3],
                        "candidate_class": "COEVOLUTION" if harness else "SOURCE_ONLY",
                        "production_paths": ";".join(production), "harness_paths_changed": ";".join(harness),
                        "production_file_count": len(production), "harness_file_count": len(harness),
                        "path_rank_score": score,
                    })
            meta = line[2:].split("\x1f", 3); paths = []
        elif line.strip():
            paths.append(line.strip())
    return rows


def main() -> None:
    excluded, exclusion_rows = prior_commits()
    all_rows = []
    repo_rows = []
    for project in REPOS:
        records = history(project)
        for row in records:
            row["prior_case_excluded"] = row["commit"] in excluded or row["parent"] in excluded
        all_rows.extend(records)
        repo_rows.append({
            "project": project, "split": SPLITS[project], "remote": git(project, "remote", "get-url", "origin").stdout.strip(),
            "head": git(project, "rev-parse", "HEAD").stdout.strip(),
            "head_time": git(project, "show", "-s", "--format=%cI", "HEAD").stdout.strip(),
            "history_commit_count": git(project, "rev-list", "--all", "--count").stdout.strip(),
            "production_candidates": len(records),
            "coevolution_candidates": sum(row["candidate_class"] == "COEVOLUTION" for row in records),
            "eligible_after_prior_exclusion": sum(not row["prior_case_excluded"] for row in records),
        })
    fields = ["project", "split", "commit", "parent", "timestamp", "subject", "candidate_class",
              "production_paths", "harness_paths_changed", "production_file_count", "harness_file_count",
              "path_rank_score", "prior_case_excluded"]
    write_csv(ROOT / "mining" / "candidate_universe.csv", all_rows, fields)
    eligible = [row for row in all_rows if not row["prior_case_excluded"]]
    pool = []
    for project in REPOS:
        co = sorted((row for row in eligible if row["project"] == project and row["candidate_class"] == "COEVOLUTION"),
                    key=lambda row: (-int(row["path_rank_score"]), row["production_file_count"], row["timestamp"], row["commit"]))[:60]
        source = sorted((row for row in eligible if row["project"] == project and row["candidate_class"] == "SOURCE_ONLY"
                         and int(row["production_file_count"]) <= 8),
                        key=lambda row: (-int(row["path_rank_score"]), row["production_file_count"],
                                         -datetime.fromisoformat(row["timestamp"]).timestamp(), row["commit"]))[:160]
        pool.extend(co + source)
    write_csv(ROOT / "mining" / "audit_pool.csv", pool, fields)
    write_csv(ROOT / "mining" / "prior_case_exclusions.csv", exclusion_rows, ["commit", "prior_sources"])
    write_csv(ROOT / "mining" / "repository_provenance.csv", repo_rows,
              ["project", "split", "remote", "head", "head_time", "history_commit_count",
               "production_candidates", "coevolution_candidates", "eligible_after_prior_exclusion"])
    write_json(ROOT / "mining" / "mining_manifest.json", {
        "mined_at": utc_now(), "selection_used_labels": False, "selection_used_predictions": False,
        "projects": list(REPOS), "project_count": len(REPOS),
        "seen_projects": sum(split == "SEEN_PROJECT" for split in SPLITS.values()),
        "unseen_projects": sum(split == "UNSEEN_PROJECT_HOLDOUT" for split in SPLITS.values()),
        "prior_identity_source_files": PRIOR_SOURCES, "prior_commit_or_parent_count": len(excluded),
        "universe_count": len(all_rows), "eligible_count": len(eligible), "audit_pool_count": len(pool),
        "universe_by_project": dict(Counter(row["project"] for row in all_rows)),
        "coevolution_by_project": dict(Counter(row["project"] for row in eligible if row["candidate_class"] == "COEVOLUTION")),
        "audit_pool_by_project": dict(Counter(row["project"] for row in pool)),
        "candidate_universe_sha256": sha256_file(ROOT / "mining" / "candidate_universe.csv"),
        "audit_pool_sha256": sha256_file(ROOT / "mining" / "audit_pool.csv"),
    })


if __name__ == "__main__":
    main()
