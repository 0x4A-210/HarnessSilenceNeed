#!/usr/bin/env python3
"""Build and validate the 105-case blind feasibility-pilot dataset."""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import random
import re
import subprocess
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve()
OUT = HERE.parents[1]
ROOT = OUT.parent
PHASE1 = ROOT / "FSE2026-harness-degradation"
PROJECTS = PHASE1 / "sources" / "projects"
OSS_FUZZ = PHASE1 / "sources" / "oss-fuzz"
CONFIG = OUT / "config" / "selections.json"

SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".wuffs"}
EXCLUDED_PARTS = {
    "test", "tests", "testing", "regression_testing", "doc", "docs",
    "example", "examples", "benchmark", "benchmarks", "fuzz", "fuzzer",
    "fuzzing",
}

REPO_HARNESS_PATHS = {
    "brotli": ["c/fuzz/decode_fuzzer.c"],
    "c-ares": ["test/ares-test-fuzz.c", "test/ares-test-fuzz-name.c"],
    "h2o": ["fuzz/driver.cc", "fuzz/driver_url.cc"],
    "jansson": ["test/ossfuzz/json_load_dump_fuzzer.cc"],
    "leptonica": [
        "prog/fuzzing/leptfuzz.h",
        "prog/fuzzing/pix3_fuzzer.cc",
        "prog/fuzzing/barcode_fuzzer.cc",
    ],
    "libplist": ["fuzz/bplist_fuzzer.cc", "fuzz/xplist_fuzzer.cc"],
    "libspng": ["tests/spng_read_fuzzer.cc"],
    "meshoptimizer": ["tools/codecfuzz.cpp"],
    "tidy-html5": [],
    "wuffs": ["fuzz/c/std/gif_fuzzer.c", "fuzz/c/std/zlib_fuzzer.c"],
}

OSS_HARNESS_PATHS = {
    "tidy-html5": [
        "tidy_fuzzer.c",
        "tidy_general_fuzzer.c",
        "tidy_parse_string_fuzzer.c",
        "tidy_parse_file_fuzzer.c",
        "tidy_xml_fuzzer.c",
        "tidy_config_fuzzer.c",
    ]
}

LANGUAGE = {
    ".c": "c", ".h": "c", ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp",
    ".hh": "cpp", ".hpp": "cpp", ".wuffs": "text",
}


def run(cmd: list[str], *, stdin: str | None = None, check: bool = True) -> str:
    result = subprocess.run(
        cmd,
        input=stdin,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(cmd)}\n{result.stderr}")
    return result.stdout


def git(repo: Path, *args: str, check: bool = True, stdin: str | None = None) -> str:
    return run(["git", "-C", str(repo), *args], stdin=stdin, check=check)


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def resolve(repo: Path, value: str) -> str:
    return git(repo, "rev-parse", f"{value}^{{commit}}").strip()


def parse_iso(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def is_production_source(path: str) -> bool:
    p = Path(path)
    if p.suffix.lower() not in SOURCE_SUFFIXES:
        return False
    lower_parts = {x.lower() for x in p.parts}
    if lower_parts & EXCLUDED_PARTS:
        return False
    if "third_party" in lower_parts or "vendor" in lower_parts or "deps" in lower_parts:
        return False
    if path.startswith("release/c/"):
        return False
    return True


def changed_paths(repo: Path, parent: str, commit: str) -> list[str]:
    return [
        line for line in git(repo, "diff", "--name-only", parent, commit).splitlines()
        if line
    ]


def numstat(repo: Path, parent: str, commit: str, paths: list[str]) -> tuple[int, int]:
    if not paths:
        return 0, 0
    added = deleted = 0
    for line in git(repo, "diff", "--numstat", parent, commit, "--", *paths).splitlines():
        bits = line.split("\t")
        if len(bits) == 3 and bits[0].isdigit() and bits[1].isdigit():
            added += int(bits[0])
            deleted += int(bits[1])
    return added, deleted


def git_file(repo: Path, rev: str, path: str) -> str | None:
    value = git(repo, "show", f"{rev}:{path}", check=False)
    if not value:
        return None
    return value


def excerpt_source(value: str, limit: int = 28_000) -> str:
    if len(value) <= limit:
        return value.rstrip()
    lines = value.splitlines()
    head = lines[:80]
    tail = lines[-180:]
    return "\n".join(head + ["/* ... middle omitted from this harness listing ... */"] + tail)


def excerpt_diff(value: str, keywords: list[str], limit: int = 58_000) -> tuple[str, bool]:
    if len(value) <= limit:
        return value.rstrip(), False
    lines = value.splitlines()
    keep: set[int] = set()
    keyword_re = re.compile("|".join(re.escape(x) for x in keywords), re.I) if keywords else None
    for i, line in enumerate(lines):
        if line.startswith("diff --git") or line.startswith("--- ") or line.startswith("+++ ") or line.startswith("@@"):
            keep.update(range(max(0, i - 1), min(len(lines), i + 3)))
        if keyword_re and keyword_re.search(line):
            keep.update(range(max(0, i - 18), min(len(lines), i + 24)))
    # Ensure broad coverage even when no explicit keyword appears.
    keep.update(range(min(140, len(lines))))
    keep.update(range(max(0, len(lines) - 180), len(lines)))
    selected: list[str] = []
    previous = -2
    used = 0
    for i in sorted(keep):
        line = lines[i]
        extra = len(line) + 1
        if used + extra > limit:
            break
        if i != previous + 1:
            selected.append("... [unselected diff lines omitted] ...")
            used += 39
        selected.append(line)
        used += extra
        previous = i
    return "\n".join(selected).rstrip(), True


def fence(path: str, value: str) -> str:
    language = LANGUAGE.get(Path(path).suffix.lower(), "text")
    return f"### `{path}`\n\n~~~~{language}\n{value.rstrip()}\n~~~~"


def load_oss_history() -> list[tuple[str, dt.datetime]]:
    history = []
    for line in git(OSS_FUZZ, "log", "--format=%H%x1f%cI").splitlines():
        bits = line.split("\x1f")
        if len(bits) == 2:
            history.append((bits[0], parse_iso(bits[1])))
    return history


def oss_revision_before(history: list[tuple[str, dt.datetime]], when: dt.datetime) -> str:
    for commit, timestamp in history:
        if timestamp <= when:
            return commit
    raise RuntimeError(f"no OSS-Fuzz revision before {when.isoformat()}")


def harness_sections(project: str, parent: str, source_time: dt.datetime,
                     oss_history: list[tuple[str, dt.datetime]]) -> tuple[str, list[str], str]:
    repo = PROJECTS / project
    sections: list[str] = []
    evidence_paths: list[str] = []
    for path in REPO_HARNESS_PATHS[project]:
        value = git_file(repo, parent, path)
        if value is not None:
            sections.append(fence(path, excerpt_source(value)))
            evidence_paths.append(f"project:{parent}:{path}")

    oss_rev = oss_revision_before(oss_history, source_time)
    build_path = f"projects/{project}/build.sh"
    build = git_file(OSS_FUZZ, oss_rev, build_path)
    if build is None:
        raise RuntimeError(f"missing historical OSS-Fuzz build file {project} at {oss_rev}")
    sections.append(fence(f"historical OSS-Fuzz:{build_path}", excerpt_source(build, 18_000)))
    evidence_paths.append(f"oss-fuzz:{oss_rev}:{build_path}")

    for name in OSS_HARNESS_PATHS.get(project, []):
        path = f"projects/{project}/{name}"
        value = git_file(OSS_FUZZ, oss_rev, path)
        if value is not None:
            sections.append(fence(f"historical OSS-Fuzz:{path}", excerpt_source(value)))
            evidence_paths.append(f"oss-fuzz:{oss_rev}:{path}")

    if not sections:
        raise RuntimeError(f"no H0 material found for {project} at {parent}")
    return "\n\n".join(sections), evidence_paths, oss_rev


def make_case(case_id: str, harness: str, paths: list[str], diff_text: str,
              excerpted: bool) -> str:
    clipping = (
        "The complete production-source file list is shown below. The diff is a deterministic, "
        "keyword-centered excerpt because the complete diff exceeded 58,000 characters."
        if excerpted else
        "The complete diff for the production-source files listed below is included."
    )
    path_lines = "\n".join(f"- `{p}`" for p in paths)
    return f"""# Case ID

{case_id}

## Existing Fuzz Harness H0

The following target source and OSS-Fuzz build wiring are from before the source commit.

{harness}

## Source Change (S0 -> S1)

Tests, documentation, commit messages, generated snapshots, and any fuzz-harness changes are excluded. {clipping}

{path_lines}

~~~~diff
{diff_text}
~~~~

## Relevant Code Context

No post-commit harness, future commit, coverage result, issue outcome, or vulnerability information is provided. The pre-change harness and source diff above are the available evidence.

## Question

Based only on the source-code evolution and the existing fuzz harness:

Does this commit introduce a fuzz-harness maintenance need?

A maintenance need exists when the source-code change introduces or modifies functionality, entry points, API usage requirements, state/configuration requirements, or input constraints such that the existing harness is no longer adequate for testing the changed functionality.

Return one structured decision using the fixed experiment prompt.
"""


def main() -> None:
    selection = json.loads(CONFIG.read_text(encoding="utf-8"))
    universe_rows = list(csv.DictReader((PHASE1 / "data/processed/commit_universe.csv").open(encoding="utf-8", newline="")))
    universe = {(x["project"], x["commit_id"]): x for x in universe_rows}
    evidence_rows = json.loads((PHASE1 / "evidence/positive_event_evidence.json").read_text(encoding="utf-8"))
    evidence = {(x["project"], x["commit_id"]): x for x in evidence_rows}
    known_positive = {x["commit_id"] for x in evidence_rows}
    repo_urls = {
        x["project"]: x["repo_url"].removesuffix(".git")
        for x in csv.DictReader((PHASE1 / "config/selected_projects.csv").open(encoding="utf-8", newline=""))
    }
    records: list[dict] = []

    for item in selection["positive"]:
        project = item["project"]
        commit = resolve(PROJECTS / project, item["commit"])
        ev = evidence[(project, commit)]
        item = dict(item)
        item.update({
            "commit": commit,
            "parent": ev["previous_commit"],
            "commit_time": ev["commit_time"],
            "actual_label": "positive",
            "negative_type": "",
            "artifact_evidence": ev["artifact_evidence"],
            "metric_before": ev["metrics"]["metric_before"],
            "metric_after": ev["metrics"]["metric_after"],
        })
        records.append(item)

    for project, groups in selection["negative"].items():
        for negative_type, prefixes in groups.items():
            for prefix in prefixes:
                commit = resolve(PROJECTS / project, prefix)
                if commit in known_positive:
                    raise RuntimeError(f"known positive selected as negative: {project} {commit}")
                key = (project, commit)
                if key not in universe:
                    raise RuntimeError(f"negative outside phase-1 universe: {project} {commit}")
                parent_line = git(PROJECTS / project, "show", "-s", "--format=%P", commit).strip()
                if len(parent_line.split()) != 1:
                    raise RuntimeError(f"negative is not a single-parent commit: {project} {commit}")
                parent = parent_line
                commit_time = universe[key]["commit_time"]
                if universe[key]["previous_commit"] != parent:
                    raise RuntimeError(f"phase-1 parent mismatch: {project} {commit}")
                all_paths = changed_paths(PROJECTS / project, parent, commit)
                prod_paths = [p for p in all_paths if is_production_source(p)]
                if not prod_paths:
                    raise RuntimeError(f"negative has no production source path: {project} {commit}")
                fuzz_changes = [p for p in all_paths if re.search(r"fuzz|harness", p, re.I)]
                if fuzz_changes:
                    raise RuntimeError(f"negative changes fuzz/harness files: {project} {commit}: {fuzz_changes}")
                records.append({
                    "project": project,
                    "commit": commit,
                    "parent": parent,
                    "commit_time": commit_time,
                    "actual_label": "negative",
                    "negative_type": negative_type,
                    "degradation_type": "none_known",
                    "maintenance_need_type": "none",
                    "affected_function": "",
                    "affected_file": "; ".join(prod_paths),
                    "reason_for_selection": {
                        "easy": "Localized production-source correction or portability change; manual review found no new entry point, call protocol, state, configuration, or input-generation requirement.",
                        "matched": "Substantive production implementation change near the project's degradation-era anchor; H0 retains the same high-level invocation and manual review found no newly introduced harness requirement.",
                        "hard": "A refactor, validation, state, or API-adjacent change that looks maintenance-sensitive, but the changed behavior remains behind H0's existing entry path or does not alter its calling/setup requirements.",
                    }[negative_type],
                    "mechanism_keywords": [],
                    "diff_paths": [],
                    "artifact_evidence": "",
                    "metric_before": "",
                    "metric_after": "",
                })

    if len(records) != 105:
        raise RuntimeError(f"expected 105 records, found {len(records)}")
    if Counter(x["actual_label"] for x in records) != {"negative": 100, "positive": 5}:
        raise RuntimeError("class counts are not 5 positive / 100 negative")
    neg_counts = Counter((x["project"], x["negative_type"]) for x in records if x["actual_label"] == "negative")
    expected = {"easy": 2, "matched": 6, "hard": 2}
    for project in selection["negative"]:
        actual = {kind: neg_counts[(project, kind)] for kind in expected}
        if actual != expected:
            raise RuntimeError(f"negative strata mismatch for {project}: {actual}")

    rng = random.Random(selection["shuffle_seed"])
    rng.shuffle(records)
    for index, item in enumerate(records, 1):
        item["case_id"] = f"C{index:03d}"

    oss_history = load_oss_history()
    cases_dir = OUT / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    for old in cases_dir.glob("C*.md"):
        old.unlink()

    mapping_rows: list[dict] = []
    positive_rows: list[dict] = []
    negative_rows: list[dict] = []
    materialization_rows: list[dict] = []

    for item in records:
        project = item["project"]
        repo = PROJECTS / project
        parent = item["parent"]
        commit = item["commit"]
        source_time = parse_iso(item["commit_time"])
        all_paths = changed_paths(repo, parent, commit)
        production = [p for p in all_paths if is_production_source(p)]
        preferred = [p for p in item.get("diff_paths", []) if p in all_paths]
        diff_paths = preferred or production
        if not diff_paths:
            raise RuntimeError(f"no source diff material for {project} {commit}")
        diff_value = git(repo, "diff", "--no-ext-diff", "--unified=6", parent, commit, "--", *diff_paths)
        # Blob IDs are not decision evidence and make anonymous cases easier to look up.
        diff_value = "\n".join(
            line for line in diff_value.splitlines() if not line.startswith("index ")
        ) + "\n"
        diff_value, excerpted = excerpt_diff(diff_value, item.get("mechanism_keywords", []))
        harness, harness_evidence, oss_rev = harness_sections(project, parent, source_time, oss_history)
        case_text = make_case(item["case_id"], harness, production, diff_value, excerpted)
        case_path = cases_dir / f"{item['case_id']}.md"
        write_text(case_path, case_text)
        case_sha = hashlib.sha256(case_text.encode()).hexdigest()
        added, deleted = numstat(repo, parent, commit, production)
        commit_url = f"{repo_urls[project]}/commit/{commit}"
        mapping_rows.append({
            "case_id": item["case_id"],
            "actual_label": item["actual_label"],
            "project": project,
            "commit_id": commit,
            "previous_commit": parent,
            "commit_time": item["commit_time"],
            "negative_type": item["negative_type"],
            "maintenance_need_type": item["maintenance_need_type"],
            "shuffle_seed": selection["shuffle_seed"],
            "case_sha256": case_sha,
        })
        common = {
            "case_id": item["case_id"],
            "project": project,
            "commit_id": commit,
            "previous_commit": parent,
            "commit_time": item["commit_time"],
            "changed_source_loc": added + deleted,
            "files_changed": len(production),
            "affected_file": item["affected_file"],
            "reason_for_selection": item["reason_for_selection"],
            "evidence": commit_url,
        }
        if item["actual_label"] == "positive":
            positive_rows.append({
                **common,
                "degradation_type": item["degradation_type"],
                "maintenance_need_type": item["maintenance_need_type"],
                "affected_function": item["affected_function"],
                "artifact_evidence": item["artifact_evidence"],
                "degradation_metric_before": item["metric_before"],
                "degradation_metric_after": item["metric_after"],
            })
        else:
            negative_rows.append({**common, "negative_type": item["negative_type"]})
        materialization_rows.append({
            "case_id": item["case_id"],
            "source_diff_paths": ";".join(diff_paths),
            "production_source_paths": ";".join(production),
            "diff_excerpted": str(excerpted).lower(),
            "h0_evidence": ";".join(harness_evidence),
            "oss_fuzz_revision": oss_rev,
            "case_sha256": case_sha,
        })

    mapping_rows.sort(key=lambda x: x["case_id"])
    positive_rows.sort(key=lambda x: x["case_id"])
    negative_rows.sort(key=lambda x: x["case_id"])
    materialization_rows.sort(key=lambda x: x["case_id"])
    write_csv(OUT / "data/case_mapping.csv", mapping_rows, [
        "case_id", "actual_label", "project", "commit_id", "previous_commit",
        "commit_time", "negative_type", "maintenance_need_type", "shuffle_seed", "case_sha256",
    ])
    write_csv(OUT / "data/selected_positive_cases.csv", positive_rows, [
        "case_id", "project", "commit_id", "previous_commit", "commit_time",
        "degradation_type", "maintenance_need_type", "affected_function", "affected_file",
        "changed_source_loc", "files_changed", "reason_for_selection", "evidence",
        "artifact_evidence", "degradation_metric_before", "degradation_metric_after",
    ])
    write_csv(OUT / "data/selected_negative_cases.csv", negative_rows, [
        "case_id", "project", "commit_id", "previous_commit", "commit_time", "negative_type",
        "affected_file", "changed_source_loc", "files_changed", "reason_for_selection", "evidence",
    ])
    write_csv(OUT / "data/case_materialization.csv", materialization_rows, [
        "case_id", "source_diff_paths", "production_source_paths", "diff_excerpted",
        "h0_evidence", "oss_fuzz_revision", "case_sha256",
    ])

    print(json.dumps({
        "cases": len(records),
        "positive": 5,
        "negative": 100,
        "projects": len(selection["negative"]),
        "negative_strata": Counter(x["negative_type"] for x in records if x["actual_label"] == "negative"),
        "shuffle_seed": selection["shuffle_seed"],
    }, indent=2, default=dict))


if __name__ == "__main__":
    main()
