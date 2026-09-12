#!/usr/bin/env python3
"""Mine and deterministically sample source+harness co-evolution commits.

The complete path-level universe is retained for audit.  The registered pilot
uses at most 50 candidates: every hit from the smaller repositories first,
then the highest static-linkage-scoring Wuffs hits to fill the quota.  No
ground-truth or LLM prediction is consulted by this selection.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from collections import Counter
from pathlib import Path, PurePosixPath


PROJECTS = (
    "c-ares", "libplist", "libspng", "tidy-html5", "brotli",
    "leptonica", "meshoptimizer", "wuffs", "jansson", "h2o",
)
SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".inc", ".wuffs"}
NON_PRODUCTION_PARTS = {
    "test", "tests", "testing", "fuzz", "fuzzing", "fuzzers",
    "doc", "docs", "example", "examples", "bench", "benchmark",
    "benchmarks", "third_party", "vendor",
}
HARNESS_PARTS = {"fuzz", "fuzzing", "fuzzers", "ossfuzz", "oss-fuzz"}
PATHSPECS = (
    ":(icase,glob)**/*fuzz*.c", ":(icase,glob)**/*fuzz*.cc",
    ":(icase,glob)**/*fuzz*.cpp", ":(icase,glob)**/*fuzz*.cxx",
    ":(icase,glob)**/fuzz/**/*.h", ":(icase,glob)**/fuzzing/**/*.h",
)
TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")
STOP_TOKENS = {
    "const", "static", "return", "struct", "size_t", "uint32_t",
    "uint64_t", "include", "define", "ifdef", "endif", "while",
    "else", "void", "data", "size", "input", "output", "status",
    "result", "decoder", "encoder", "context", "buffer", "fuzzer",
    "LLVMFuzzerTestOneInput",
}
API_PROTOCOL_CUES = (
    " arg", "args", "argument", "status", "workbuf", "work_buffer",
    "initialize", "version", "decode_frame", "decode_config", "io_buffer",
    "pixel_buffer", " type", " order", " return", " remove", " split",
    " redo", "set_quirk", "transform_io",
)
NON_SEMANTIC_CUES = (
    "relicense", "spelling", "inclusive", "format c", "comment", "license",
    "header", "flags consistently", "single file",
)


def git(repo: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if check and result.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed in {repo}: {result.stderr}")
    return result.stdout


def is_harness(path: str) -> bool:
    value = path.lower()
    posix = PurePosixPath(value)
    if posix.suffix not in SOURCE_SUFFIXES:
        return False
    return (
        "fuzz" in posix.name
        or "fuzzer" in posix.name
        or any(part in HARNESS_PARTS for part in posix.parts)
    )


def is_production(path: str) -> bool:
    value = path.lower()
    posix = PurePosixPath(value)
    if posix.suffix not in SOURCE_SUFFIXES or is_harness(path):
        return False
    if any(part in NON_PRODUCTION_PARTS for part in posix.parts):
        return False
    # h2o vendors several complete projects under deps/.  Those are not h2o
    # production-source/harness co-evolution events for this experiment.
    return not (posix.parts and posix.parts[0] == "deps")


def analyze_patch(patch: str, sources: set[str], harnesses: set[str]) -> dict[str, object]:
    """Collect line counts and added tokens in one pass over one Git diff."""
    result: dict[str, object] = {
        "source_tokens": Counter(), "harness_tokens": Counter(),
        "source_added": 0, "source_deleted": 0,
        "harness_added": 0, "harness_deleted": 0,
    }
    current = ""
    for line in patch.splitlines():
        if line.startswith("diff --git a/"):
            match = re.match(r"diff --git a/(.*?) b/(.*)", line)
            current = match.group(2) if match else ""
            continue
        group = "source" if current in sources else "harness" if current in harnesses else ""
        if not group:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            result[f"{group}_added"] = int(result[f"{group}_added"]) + 1
            tokens = result[f"{group}_tokens"]
            assert isinstance(tokens, Counter)
            for token in TOKEN_RE.findall(line[1:]):
                if token not in STOP_TOKENS and not token.isupper():
                    tokens[token] += 1
        elif line.startswith("-") and not line.startswith("---"):
            result[f"{group}_deleted"] = int(result[f"{group}_deleted"]) + 1
    return result


def mine(project_root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for project in PROJECTS:
        repo = project_root / project
        if not (repo / ".git").exists():
            raise FileNotFoundError(f"missing Git repository: {repo}")
        touched = set(git(repo, "log", "--all", "--format=%H", "--", *PATHSPECS).split())
        for commit in touched:
            metadata = git(repo, "show", "-s", "--format=%P%x1f%aI%x1f%s", commit).rstrip().split("\x1f", 2)
            if len(metadata) != 3 or not metadata[0].split():
                continue
            parent = metadata[0].split()[0]
            timestamp, message = metadata[1:]
            changed = [x for x in git(repo, "diff", "--name-only", parent, commit).splitlines() if x]
            harnesses = sorted(x for x in changed if is_harness(x))
            sources = sorted(x for x in changed if is_production(x))
            if not harnesses or not sources:
                continue
            patch = git(repo, "diff", "--no-ext-diff", "--unified=0", parent, commit, "--", *sources, *harnesses)
            analysis = analyze_patch(patch, set(sources), set(harnesses))
            source_tokens = analysis["source_tokens"]
            harness_tokens = analysis["harness_tokens"]
            assert isinstance(source_tokens, Counter) and isinstance(harness_tokens, Counter)
            overlap = sorted(set(source_tokens) & set(harness_tokens))
            source_add, source_del = int(analysis["source_added"]), int(analysis["source_deleted"])
            harness_add, harness_del = int(analysis["harness_added"]), int(analysis["harness_deleted"])
            message_lower = message.lower()
            score = min(len(overlap), 12) * 3
            score += 4 if "fuzz" in message_lower else 0
            score += 2 if any(word in message_lower for word in ("add", "support", "new", "implement", "expose")) else 0
            score += 1 if harness_add + harness_del >= 3 else 0
            score -= 8 if any(word in message_lower for word in ("format", "clang-format", "rename", "typo", "cleanup")) else 0
            cue_text = " " + message_lower
            protocol_score = sum(2 for cue in API_PROTOCOL_CUES if cue in cue_text)
            protocol_score -= sum(5 for cue in NON_SEMANTIC_CUES if cue in cue_text)
            protocol_score += 1 if harness_add + harness_del >= 2 else 0
            rows.append({
                "project": project,
                "commit_id": commit,
                "parent_commit": parent,
                "timestamp": timestamp,
                "source_files_changed": json.dumps(sources, separators=(",", ":")),
                "harness_files_changed": json.dumps(harnesses, separators=(",", ":")),
                "commit_message": message,
                "source_added": source_add,
                "source_deleted": source_del,
                "harness_added": harness_add,
                "harness_deleted": harness_del,
                "shared_added_identifiers": json.dumps(overlap[:30], separators=(",", ":")),
                "static_linkage_score": score,
                "protocol_cue_score": protocol_score,
            })
    return sorted(rows, key=lambda x: (str(x["project"]), str(x["timestamp"]), str(x["commit_id"])))


def sample(rows: list[dict[str, object]], limit: int) -> list[dict[str, object]]:
    non_wuffs = [row for row in rows if row["project"] != "wuffs"]
    wuffs = [row for row in rows if row["project"] == "wuffs"]
    # The Wuffs history dominates the raw universe.  Prioritize likely API or
    # call-protocol co-evolution using message cues only; this is candidate
    # screening, not a ground-truth label, and occurs before blind prediction.
    wuffs.sort(key=lambda x: (-int(x["protocol_cue_score"]), -int(x["static_linkage_score"]), str(x["timestamp"]), str(x["commit_id"])))
    selected = non_wuffs[:limit]
    if len(selected) < limit:
        selected.extend(wuffs[:limit - len(selected)])
    selected.sort(key=lambda x: (str(x["project"]), str(x["timestamp"]), str(x["commit_id"])))
    return selected


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else ["project", "commit_id"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    rows = mine(args.project_root.resolve())
    selected = sample(rows, args.limit)
    write_csv(args.output_dir / "co_evolution_universe.csv", rows)
    write_csv(args.output_dir / "co_evolution_candidates.csv", selected)
    print(json.dumps({
        "universe": len(rows),
        "selected": len(selected),
        "universe_by_project": dict(Counter(str(x["project"]) for x in rows)),
        "selected_by_project": dict(Counter(str(x["project"]) for x in selected)),
    }, indent=2))


if __name__ == "__main__":
    main()
