#!/usr/bin/env python3
"""Materialize and freeze the 40 anonymous Task-5 blind inputs."""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
T5 = ROOT / "t5-delta-aware-validation"
AUDIT = T5 / "new-data" / "audit.csv"
GT_MANIFEST = T5 / "frozen-ground-truth" / "manifest.json"
GT_EVIDENCE = T5 / "frozen-ground-truth" / "evidence.csv"
REPOS = ROOT / "FSE2026-harness-degradation" / "sources" / "projects"
OUT = T5 / "frozen-inputs"
CODE_RE = re.compile(r"\.(?:c|cc|cpp|cxx|h|hh|hpp)$", re.I)
HARNESS_RE = re.compile(r"fuzz", re.I)
CONTEXT_RADIUS = 24


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], encoding="utf-8", errors="replace"
    )


def file_at(repo: Path, revision: str, path: str) -> str:
    return git(repo, "show", f"{revision}:{path}")


def tree_paths(repo: Path, revision: str) -> list[str]:
    return git(repo, "ls-tree", "-r", "--name-only", revision).splitlines()


def context(repo: Path, revision: str, paths: list[str], target: str) -> str:
    for path in paths:
        try:
            lines = file_at(repo, revision, path).splitlines()
        except subprocess.CalledProcessError:
            continue
        for index, line in enumerate(lines):
            if target in line:
                start, end = max(0, index - CONTEXT_RADIUS), min(len(lines), index + CONTEXT_RADIUS + 1)
                body = "\n".join(f"{number + 1:06d}: {lines[number]}" for number in range(start, end))
                return f"Path: `{path}`; lines {start + 1}-{end}\n\n~~~~text\n{body}\n~~~~"
    return "~~~~text\n<no matching declaration in the selected production files>\n~~~~"


def main() -> None:
    if OUT.exists():
        raise SystemExit("refusing to overwrite frozen inputs")
    gt = json.loads(GT_MANIFEST.read_text(encoding="utf-8"))
    if gt.get("status") != "FROZEN" or gt.get("case_count") != 40:
        raise SystemExit("ground truth must be frozen first")
    rows = list(csv.DictReader(AUDIT.open(encoding="utf-8", newline="")))
    evidence = {
        row["case_id"]: row
        for row in csv.DictReader(GT_EVIDENCE.open(encoding="utf-8", newline=""))
    }
    if len(rows) != 40 or any(row["audit_status"] != "VALID" for row in rows):
        raise SystemExit("expected 40 valid audited cases")
    OUT.mkdir(parents=True)
    case_meta: list[dict[str, object]] = []
    for row in rows:
        repo = REPOS / row["project"]
        parent, commit = row["previous_commit"], row["commit_id"]
        harness_paths = sorted(
            path for path in tree_paths(repo, parent)
            if CODE_RE.search(path) and HARNESS_RE.search(path)
        )
        production_paths = evidence[row["case_id"]]["changed_production_paths"].split(";")
        harness_sections = []
        for path in harness_paths:
            harness_sections.append(f"### H0 path: `{path}`\n\n~~~~cpp\n{file_at(repo, parent, path).rstrip()}\n~~~~")
        # -W expands each hunk to its enclosing C/C++ function. No changed
        # production path or hunk is omitted.
        diff = git(
            repo, "diff", "--no-ext-diff", "--no-color", "--function-context",
            parent, commit, "--", *production_paths,
        ).rstrip()
        s0_context = context(repo, parent, production_paths, row["target_symbol"])
        s1_context = context(repo, commit, production_paths, row["target_symbol"])
        content = (
            "# Anonymous fuzz-harness case\n\n"
            "## Case ID\n\n"
            f"{row['case_id']}\n\n"
            "## Existing harness H0\n\n"
            "Every project-owned C/C++ path containing `fuzz` at the pre-change snapshot is shown below. "
            "Framework and build-script scaffolding are not expanded.\n\n"
            + "\n\n".join(harness_sections)
            + "\n\n## Complete S0 -> S1 production-source diff\n\n"
            "All changed C/C++ production paths and all hunks are included. Function-context mode expands "
            "changed C/C++ function bodies; tests, examples, documentation, build files, and Harness files "
            "are excluded by the frozen rule.\n\n"
            f"~~~~diff\n{diff}\n~~~~\n\n"
            "## Uniform selected declaration context\n\n"
            "The same mechanical rule is used for every case: in lexicographic changed-production-path "
            f"order, show +/-{CONTEXT_RADIUS} lines around the first literal identity match in each snapshot.\n\n"
            "### S0\n\n" + s0_context + "\n\n"
            "### S1\n\n" + s1_context + "\n"
        )
        path = OUT / f"{row['case_id']}.md"
        path.write_text(content, encoding="utf-8", newline="\n")
        case_meta.append({
            "case_id": row["case_id"], "input_path": str(path.relative_to(T5)),
            "sha256": sha(path.read_bytes()), "bytes": path.stat().st_size,
            "h0_file_count": len(harness_paths), "production_path_count": len(production_paths),
        })
    frozen_at = now()
    composite = "".join(f"{item['case_id']}:{item['sha256']}\n" for item in case_meta).encode()
    manifest = {
        "status": "FROZEN", "frozen_at": frozen_at, "case_count": len(case_meta),
        "dataset_hash": gt["dataset_hash"], "ground_truth_hash": gt["ground_truth_hash"],
        "ground_truth_frozen_at": gt["frozen_at"], "input_hash": sha(composite),
        "context_selection_version": "complete-H0-fuzz-paths+complete-production-function-context-diff+literal-identity-radius24-v1",
        "context_rule": {
            "H0": "all pre-change C/C++ repository paths whose path contains the literal fuzz (case-insensitive)",
            "production_diff": "all changed C/C++ non-fuzz paths outside test/example/demo/bench/doc directories; git --function-context; no hunk truncation",
            "supplement": "first literal audited identity match, lexicographic changed-production-path order, plus/minus 24 lines, for S0 and S1",
        },
        "prohibited_material_injected": [],
        "case_inputs": case_meta,
        "ordering": {
            "ground_truth_frozen_at": gt["frozen_at"], "input_frozen_at": frozen_at,
            "prediction_started_at": None,
        },
    }
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "status": "FROZEN", "case_count": len(case_meta), "input_hash": manifest["input_hash"],
        "min_bytes": min(item["bytes"] for item in case_meta),
        "max_bytes": max(item["bytes"] for item in case_meta),
    }))


if __name__ == "__main__":
    main()
