#!/usr/bin/env python3
"""Mine independent source+harness co-evolution commits from local Git clones.

The miner excludes every commit exposed by the FSE degradation replication,
the pre-test/holdout experiments, and the complete development pilot.  It uses
batched Git plumbing so the complete history can be audited efficiently.
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath


HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
WORKSPACE = ROOT.parent
PROJECT_ROOT = WORKSPACE / "FSE2026-harness-degradation" / "sources" / "projects"
DATA = ROOT / "data"

PROJECTS = (
    "brotli", "c-ares", "h2o", "jansson", "leptonica", "libplist",
    "libspng", "mbedtls", "meshoptimizer", "proj4", "selinux", "solidity",
    "tidy-html5", "tpm2-tss", "trafficserver", "wuffs",
)
SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".inc", ".wuffs"}
HARNESS_PARTS = {"fuzz", "fuzzing", "fuzzers", "ossfuzz", "oss-fuzz"}
NON_PRODUCTION_PARTS = {
    "test", "tests", "testing", "fuzz", "fuzzing", "fuzzers", "doc", "docs",
    "example", "examples", "bench", "benchmark", "benchmarks", "third_party",
    "vendor", "deps",
}
PATHSPECS = (
    ":(icase,glob)**/*fuzz*.c", ":(icase,glob)**/*fuzz*.cc",
    ":(icase,glob)**/*fuzz*.cpp", ":(icase,glob)**/*fuzz*.cxx",
    ":(icase,glob)**/fuzz/**/*.h", ":(icase,glob)**/fuzzing/**/*.h",
)
TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")
STOP_TOKENS = {
    "const", "static", "return", "struct", "class", "size_t", "uint32_t", "uint64_t",
    "include", "define", "ifdef", "endif", "while", "else", "void", "data", "size",
    "input", "output", "status", "result", "decoder", "encoder", "context", "buffer",
    "fuzzer", "LLVMFuzzerTestOneInput", "true", "false",
}

EXCLUSION_FILES = (
    ("pre-test-development", WORKSPACE / "pre-test" / "data" / "case_mapping.csv"),
    ("pre-test-holdout", WORKSPACE / "pre-test" / "holdout" / "data" / "case_mapping.csv"),
    ("fse-positive-event", WORKSPACE / "FSE2026-harness-degradation" / "config" / "positive_events.csv"),
    ("maintenance-pilot-candidates", WORKSPACE / "harness-maintenance-new-pilot" / "data" / "co_evolution_candidates_initial.csv"),
    ("maintenance-pilot-positive", WORKSPACE / "harness-maintenance-new-pilot" / "data" / "verified_positive_cases_initial.csv"),
    ("maintenance-pilot-negative", WORKSPACE / "harness-maintenance-new-pilot" / "data" / "verified_negative_cases_initial.csv"),
)


def git(repo: Path, *args: str, stdin: str | None = None) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args], input=stdin, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if completed.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed in {repo}: {completed.stderr}")
    return completed.stdout


def is_harness(path: str) -> bool:
    posix = PurePosixPath(path.lower())
    return posix.suffix in SOURCE_SUFFIXES and (
        "fuzz" in posix.name or "fuzzer" in posix.name or any(part in HARNESS_PARTS for part in posix.parts)
    )


def is_production(path: str) -> bool:
    posix = PurePosixPath(path.lower())
    return (posix.suffix in SOURCE_SUFFIXES and not is_harness(path)
            and not any(part in NON_PRODUCTION_PARTS for part in posix.parts))


def read_exclusions() -> tuple[set[tuple[str, str]], list[dict[str, str]]]:
    sources: dict[tuple[str, str], set[str]] = defaultdict(set)
    for source_name, path in EXCLUSION_FILES:
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                commit = row.get("commit_id") or row.get("commit")
                project = row.get("project")
                if project and commit:
                    sources[(project, commit)].add(source_name)
    rows = [
        {"project": project, "commit_id": commit, "exclusion_sources": ";".join(sorted(values))}
        for (project, commit), values in sorted(sources.items())
    ]
    return set(sources), rows


def touched_records(repo: Path) -> list[tuple[list[str], list[str]]]:
    hashes = sorted(set(git(repo, "log", "--all", "--no-merges", "--format=%H", "--", *PATHSPECS).split()))
    if not hashes:
        return []
    output = git(
        repo, "diff-tree", "--stdin", "-r", "--name-only", "--no-renames",
        "--format=@@%H%x1f%P%x1f%aI%x1f%s", stdin="\n".join(hashes) + "\n",
    )
    records: list[tuple[list[str], list[str]]] = []
    metadata: list[str] | None = None
    paths: list[str] = []
    for line in output.splitlines():
        if line.startswith("@@"):
            if metadata is not None:
                records.append((metadata, paths))
            metadata, paths = line[2:].split("\x1f", 3), []
        elif line and metadata is not None:
            paths.append(line)
    if metadata is not None:
        records.append((metadata, paths))
    return records


def patch_features(repo: Path, parent: str, commit: str, sources: list[str], harnesses: list[str]) -> dict[str, object]:
    patch = git(repo, "diff", "--no-ext-diff", "--no-renames", "--unified=0", parent, commit, "--", *sources, *harnesses)
    current = ""
    source_added = source_deleted = harness_added = harness_deleted = 0
    source_tokens: Counter[str] = Counter()
    harness_tokens: Counter[str] = Counter()
    new_functions: set[str] = set()
    for line in patch.splitlines():
        if line.startswith("diff --git a/"):
            match = re.match(r"diff --git a/(.*?) b/(.*)", line)
            current = match.group(2) if match else ""
            continue
        group = "source" if current in sources else "harness" if current in harnesses else ""
        if not group:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            if group == "source":
                source_added += 1
                # Deliberately use a bounded, linear parser here. Some generated
                # C/C++ source lines are extremely long and make a permissive
                # declaration regex catastrophically backtrack.
                declaration = line[1:].strip()
                if len(declaration) <= 1000 and "(" in declaration and ";" not in declaration:
                    prefix = declaration.split("(", 1)[0].rstrip()
                    name = prefix.split()[-1].lstrip("*&") if prefix.split() else ""
                    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_:]*", name):
                        new_functions.add(name)
                target = source_tokens
            else:
                harness_added += 1
                target = harness_tokens
            target.update(token for token in TOKEN_RE.findall(line[1:]) if token not in STOP_TOKENS)
        elif line.startswith("-") and not line.startswith("---"):
            if group == "source":
                source_deleted += 1
            else:
                harness_deleted += 1
    shared = sorted(set(source_tokens) & set(harness_tokens))
    new_function_exposure = sorted(name for name in new_functions if name in harness_tokens)
    return {
        "changed_loc_source": source_added + source_deleted,
        "changed_loc_harness": harness_added + harness_deleted,
        "source_added": source_added,
        "source_deleted": source_deleted,
        "harness_added": harness_added,
        "harness_deleted": harness_deleted,
        "shared_changed_identifiers": json.dumps(shared[:50], separators=(",", ":")),
        "detected_new_functions": json.dumps(sorted(new_functions), separators=(",", ":")),
        "new_functions_exposed_by_h1": json.dumps(new_function_exposure, separators=(",", ":")),
        "static_relation_score": min(len(shared), 20) * 3 + min(len(new_function_exposure), 5) * 8,
    }


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = fields or list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    excluded, exclusion_rows = read_exclusions()
    candidates: list[dict[str, object]] = []
    path_hits = 0
    for project in PROJECTS:
        repo = PROJECT_ROOT / project
        for metadata, paths in touched_records(repo):
            commit, parents, timestamp, message = metadata
            parent_parts = parents.split()
            if not parent_parts:
                continue
            harnesses = sorted(path for path in paths if is_harness(path))
            sources = sorted(path for path in paths if is_production(path))
            if not harnesses or not sources:
                continue
            path_hits += 1
            if (project, commit) in excluded:
                continue
            parent = parent_parts[0]
            features = patch_features(repo, parent, commit, sources, harnesses)
            candidates.append({
                "candidate_id": "",
                "project": project,
                "commit": commit,
                "parent": parent,
                "timestamp": timestamp,
                "source_files_changed": json.dumps(sources, separators=(",", ":")),
                "harness_files_changed": json.dumps(harnesses, separators=(",", ":")),
                "commit_message": message,
                **features,
            })
        print(f"{project}: {sum(row['project'] == project for row in candidates)} independent candidates", flush=True)
    candidates.sort(key=lambda row: (str(row["project"]), str(row["timestamp"]), str(row["commit"])))
    for index, row in enumerate(candidates, 1):
        row["candidate_id"] = f"N{index:03d}"
    write_csv(DATA / "new_candidates.csv", candidates)
    write_csv(DATA / "prior_commit_exclusions.csv", exclusion_rows,
              ["project", "commit_id", "exclusion_sources"])
    manifest = {
        "projects_searched": list(PROJECTS),
        "project_count": len(PROJECTS),
        "path_level_coevolution_hits_before_exclusion": path_hits,
        "prior_unique_commits_excluded": len(excluded),
        "independent_candidate_count": len(candidates),
        "candidates_by_project": dict(Counter(str(row["project"]) for row in candidates)),
        "exclusion_files": [str(path.relative_to(WORKSPACE)) for _, path in EXCLUSION_FILES],
        "selection_uses_labels_or_predictions": False,
    }
    (DATA / "mining_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
