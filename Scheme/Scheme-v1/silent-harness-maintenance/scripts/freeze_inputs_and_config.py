#!/usr/bin/env python3
"""Freeze anonymous H0/source-diff inputs, prompts, and model parameters."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
WORKSPACE = ROOT.parent
PROJECT_ROOT = WORKSPACE / "FSE2026-harness-degradation" / "sources" / "projects"
DATA = ROOT / "data"
FROZEN_GT = ROOT / "frozen-ground-truth"
INPUTS = ROOT / "frozen-inputs"
PROMPTS = ROOT / "prompts"
CONFIG = ROOT / "frozen-experiment-config.json"
CONTEXT_VERSION = "complete-source-diff+function-context-and-complete-H0-v1"


def read_csv(path: Path) -> list[dict[str, str]]:
    csv.field_size_limit(sys.maxsize)
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def git_bytes(repo: Path, *args: str, check: bool = True) -> bytes:
    result = subprocess.run(["git", "-C", str(repo), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace"))
    return result.stdout


def exists(repo: Path, revision: str, path: str) -> bool:
    return subprocess.run(["git", "-C", str(repo), "cat-file", "-e", f"{revision}:{path}"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def fallback_harness(repo: Path, parent: str) -> str:
    paths = git_bytes(repo, "ls-tree", "-r", "--name-only", parent).decode(errors="replace").splitlines()
    options = sorted(p for p in paths if "fuzz" in p.lower() and Path(p).suffix.lower() in {".c", ".cc", ".cpp", ".cxx"}
                     and "fuzzer" in Path(p).name.lower())
    if not options:
        raise RuntimeError(f"no pre-existing fuzzer at {parent}")
    # Prefer a real target over a shared fuzz library.
    targets = [p for p in options if "fuzzlib" not in p.lower()]
    return (targets or options)[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    gt_manifest_path = FROZEN_GT / "audit_manifest.json"
    if not gt_manifest_path.exists():
        raise SystemExit("Ground truth must be frozen first")
    if (INPUTS / "input_manifest.json").exists() and not args.force:
        raise SystemExit("Refusing to overwrite frozen blind inputs")
    if CONFIG.exists() and not args.force:
        raise SystemExit("Refusing to overwrite frozen experiment config")

    gt_manifest = json.loads(gt_manifest_path.read_text(encoding="utf-8"))
    labels = read_csv(FROZEN_GT / "labels.csv")
    candidates = {r["candidate_id"]: r for r in read_csv(DATA / "new_candidates.csv")}
    controls = {r["control_id"]: r for r in read_csv(DATA / "source_only_negative_controls.csv")}
    INPUTS.mkdir(parents=True, exist_ok=True)
    entries = []
    for label in labels:
        case_id = label["case_id"]
        internal = label["internal_id"]
        item = candidates.get(internal) or controls[internal]
        repo = PROJECT_ROOT / item["project"]
        parent, commit = item["parent"], item["commit"]
        source_paths = json.loads(item["source_files_changed"])
        harness_paths = json.loads(item.get("harness_files_changed", "[]"))
        if internal in controls:
            harness_paths = [item["harness_file"]]
        present = [p for p in harness_paths if exists(repo, parent, p)]
        absent = [p for p in harness_paths if p not in present]
        fallback = ""
        if not present:
            fallback = fallback_harness(repo, parent)
            present = [fallback]

        chunks = [
            "# Anonymous Fuzz-Harness Maintenance Case\n\n",
            "Case ID\n\n",
            f"{case_id}\n\n",
            "## Evidence boundary\n\n",
            "The material below contains only the complete existing harness H0 and the complete production source diff from S0 to S1. "
            "No developer-updated harness, commit message, build result, coverage result, reachability result, or label is supplied.\n\n",
            "## Existing Harness H0\n\n",
        ]
        for path in present:
            content = git_bytes(repo, "show", f"{parent}:{path}").decode(errors="replace")
            chunks.extend([f"### `{path}`\n\n", "```text\n", content, "\n```\n\n"])
        for path in absent:
            chunks.append(f"### `{path}`\n\nThis path does not exist in H0.\n\n")
        if fallback:
            chunks.append("The displayed fallback file is the lexicographically first pre-existing real fuzzer target, selected by the frozen rule because no changed target path exists in H0.\n\n")
        source_diff = git_bytes(
            repo, "diff", "--no-ext-diff", "--no-renames", "--full-index", "--function-context",
            parent, commit, "--", *source_paths,
        ).decode(errors="replace")
        chunks.extend([
            "## Complete production source diff S0 -> S1\n\n",
            "The fixed `--function-context` rule includes the complete diff and expanded changed-function bodies where Git recognizes them.\n\n",
            "```diff\n", source_diff, "\n```\n",
        ])
        content = "".join(chunks)
        # Leak checks target labels/results and developer-side harness text, not
        # identifiers that naturally occur in production code.
        forbidden = ["VERIFIED_SILENT_POSITIVE", "VERIFIED_EXPLICIT_POSITIVE", "VERIFIED_NEGATIVE",
                     "changed_coverage_h0", "reachability_h1", "S1_H1"]
        hit = [token for token in forbidden if token in content]
        if hit:
            raise RuntimeError(f"forbidden blind-input token in {case_id}: {hit}")
        path = INPUTS / f"{case_id}.md"
        path.write_text(content, encoding="utf-8")
        entries.append({
            "case_id": case_id, "file": path.name, "sha256": sha256_file(path),
            "bytes": path.stat().st_size, "h0_files": present,
            "h0_absent_changed_paths": absent, "fallback_h0_file": fallback,
        })

    canonical = "".join(f"{x['case_id']}:{x['sha256']}\n" for x in entries).encode()
    input_hash = sha256_bytes(canonical)
    prompt_files = [
        PROMPTS / "gap_only_prompt.md", PROMPTS / "evolution_aware_prompt.md",
        PROMPTS / "gap_only_schema.json", PROMPTS / "evolution_aware_schema.json",
    ]
    input_frozen_at = datetime.now(timezone.utc).isoformat()
    input_manifest = {
        "input_frozen_at": input_frozen_at,
        "ground_truth_frozen_at": gt_manifest["ground_truth_frozen_at"],
        "ground_truth_precedes_input_freeze": gt_manifest["ground_truth_frozen_at"] < input_frozen_at,
        "dataset_hash": gt_manifest["dataset_hash"], "input_hash": input_hash,
        "case_count": len(entries), "context_selection_version": CONTEXT_VERSION,
        "context_selection_rule": {
            "source": "all audited production paths; git diff --full-index --function-context; no truncation",
            "harness": "complete parent-revision contents of every changed harness path that exists in H0",
            "new_target_fallback": "if none exists, include the lexicographically first pre-existing non-fuzzlib fuzzer target and record absent paths",
            "extra_context": "none",
        },
        "forbidden_material": ["H1", "harness diff", "ground truth", "dynamic validation", "commit message", "future behavior"],
        "cases": entries,
    }
    (INPUTS / "input_manifest.json").write_text(json.dumps(input_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    prompt_hash = sha256_bytes("".join(f"{p.name}:{sha256_file(p)}\n" for p in prompt_files).encode())
    codex = shutil.which("codex")
    codex_version = subprocess.run([codex, "--version"], text=True, capture_output=True, check=True).stdout.strip() if codex else "NOT_FOUND"
    config_frozen_at = datetime.now(timezone.utc).isoformat()
    config = {
        "config_frozen_at": config_frozen_at,
        "ordering": {
            "ground_truth_frozen_at": gt_manifest["ground_truth_frozen_at"],
            "input_frozen_at": input_frozen_at,
            "prompt_and_model_config_frozen_at": config_frozen_at,
            "prediction_started_at": None,
        },
        "dataset_hash": gt_manifest["dataset_hash"], "input_hash": input_hash,
        "prompt_hash": prompt_hash,
        "prompt_files": {p.relative_to(ROOT).as_posix(): sha256_file(p) for p in prompt_files},
        "build_only_rule": "YES iff S1+H0 build FAIL or S1+H0 runtime FAIL; otherwise NO",
        "model": "gpt-5.6-sol", "model_version": "service alias; exact backend revision not exposed by CLI",
        "system_prompt": "Codex built-in system prompt; isolated with --ignore-user-config --ignore-rules",
        "reasoning_effort": "high", "temperature": None, "max_tokens": None,
        "unset_parameter_note": "Codex CLI does not expose temperature or max output tokens; service defaults are frozen by leaving both unset.",
        "context_selection_version": CONTEXT_VERSION, "concurrency": 4, "timeout_seconds": 900,
        "one_shot": True, "retries": 0, "codex_cli_version_at_freeze": codex_version,
        "protocol": "one fresh ephemeral process per case and baseline; read-only empty working directory; input is fixed prompt plus one frozen case",
    }
    CONFIG.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "case_count": len(entries), "input_hash": input_hash, "prompt_hash": prompt_hash,
        "min_bytes": min(x["bytes"] for x in entries), "max_bytes": max(x["bytes"] for x in entries),
        "total_bytes": sum(x["bytes"] for x in entries), "config_frozen_at": config_frozen_at,
    }, indent=2))


if __name__ == "__main__":
    main()
