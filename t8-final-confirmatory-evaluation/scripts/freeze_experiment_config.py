#!/usr/bin/env python3
"""Freeze every Task-8 method and artifact hash before formal prediction."""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
from pathlib import Path

from common import ROOT, sha256_file, utc_now, write_json


WORKSPACE = ROOT.parent
OUTPUT = ROOT / "frozen-experiment-config.json"


def composite(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(ROOT)).encode()); digest.update(b"\0")
        digest.update(path.read_bytes()); digest.update(b"\0")
    return digest.hexdigest()


def path_hashes(paths: list[Path]) -> dict[str, str]:
    output = {}
    for path in paths:
        try:
            name = str(path.relative_to(ROOT))
        except ValueError:
            name = str(path.relative_to(WORKSPACE))
        output[name] = sha256_file(path)
    return output


def main() -> None:
    if OUTPUT.exists():
        raise SystemExit("refusing to overwrite frozen experiment config")
    if (ROOT / "predictions").exists() and any((ROOT / "predictions").rglob("*")):
        raise SystemExit("prediction artifacts exist before config freeze")
    gt = json.loads((ROOT / "frozen-ground-truth" / "audit_manifest.json").read_text(encoding="utf-8"))
    inputs = json.loads((ROOT / "frozen-inputs" / "manifest.json").read_text(encoding="utf-8"))
    if gt["status"] != "FROZEN_BEFORE_ANY_PREDICTION" or inputs["status"] != "FROZEN":
        raise SystemExit("ground truth and blind inputs must be frozen")
    if gt["dataset_hash"] != inputs["dataset_hash"] or gt["ground_truth_hash"] != inputs["ground_truth_hash"]:
        raise SystemExit("freeze chain hash mismatch")

    prompt_files = [ROOT / "prompts" / name for name in (
        "gap_only.md", "gap_only_schema.json", "direct_evolution_aware.md",
        "direct_evolution_aware_schema.json", "delta_aware.md", "delta_aware_schema.json",
    )]
    m3_files = [
        ROOT / "deterministic-baseline" / "dataset" / "cases.csv", ROOT / "scripts" / "run_m3.py",
        WORKSPACE / "t7-target-discovery-reachability" / "protocol" / "m1_rules_v1.md",
        *[WORKSPACE / "t7-target-discovery-reachability" / "scripts" / name for name in (
            "common.py", "build_callgraph.py", "extract_diff_targets.py", "rank_targets.py",
            "static_reachability.py", "discover_case.py",
        )],
    ]
    dynamic_files = [
        ROOT / "dynamic-baseline" / "dataset" / "cases.csv",
        ROOT / "dynamic-baseline" / "dataset" / "changed_code.csv",
        ROOT / "dynamic-baseline" / "dataset" / "corpus_manifest.csv",
        ROOT / "scripts" / "run_dynamic.py",
        *[WORKSPACE / "t6-dynamic-baseline-validation" / "scripts" / name for name in (
            "common.py", "oss_fuzz_build_adapter.sh", "build_versions.py",
            "run_fuzz_budget.py", "collect_coverage.py",
        )],
    ]
    general_files = prompt_files + [ROOT / "scripts" / "run_blind.py", ROOT / "scripts" / "freeze_predictions.py"]
    all_hashes = path_hashes(general_files)
    all_hashes.update(path_hashes(m3_files)); all_hashes.update(path_hashes(dynamic_files))
    frozen_at = utc_now()
    config = {
        "status": "FROZEN_BEFORE_PREDICTION", "frozen_at": frozen_at,
        "dataset_hash": gt["dataset_hash"], "ground_truth_hash": gt["ground_truth_hash"],
        "input_hash": inputs["input_hash"], "prompt_hash": composite(prompt_files),
        "case_count": 104, "model": "gpt-5.6-sol",
        "model_version": "service alias; exact backend revision not exposed by CLI",
        "reasoning_effort": "high", "temperature": None, "max_tokens": None,
        "one_shot": True, "retries": 0, "concurrency": 4, "timeout_seconds": 900,
        "codex_cli_version_at_freeze": subprocess.check_output(["codex", "--version"], text=True).strip(),
        "system_prompt": "Codex built-in system prompt; isolated with --ignore-user-config --ignore-rules",
        "llm_protocol": "one fresh ephemeral process per case and method; unique empty read-only working directory; runner reads only one frozen prompt/schema and one frozen anonymous input",
        "llm_methods": {
            "gap_only": {"method": "A1/M-gap", "prompt": "prompts/gap_only.md", "schema": "prompts/gap_only_schema.json"},
            "direct_evolution_aware": {"method": "M4/A2", "prompt": "prompts/direct_evolution_aware.md", "schema": "prompts/direct_evolution_aware_schema.json"},
            "delta_aware": {"method": "M5/A3 Delta-Aware v2", "prompt": "prompts/delta_aware.md", "schema": "prompts/delta_aware_schema.json"},
        },
        "prompt_provenance": {
            "gap_only": "byte-identical Task-5 frozen baseline",
            "direct_evolution_aware": "byte-identical Task-5 frozen direct baseline",
            "delta_aware": "byte-identical Task-5 Delta-Aware v2",
        },
        "context_selection_version": inputs["context_selection_version"],
        "context_protocol_deviation": inputs["protocol_deviation"],
        "dynamic_baselines": {
            "methods": ["M0_BUILD_ONLY", "M1_OVERALL_COVERAGE_DELTA", "M2_CHANGED_CODE_COVERAGE"],
            "rule_version": "byte-identical Task-6 thresholds and build adapter; Task-8 counterfactual H0 overlay",
            "build_only_rule": "YES only when S0+H0 builds/runs and S1+H0 fails build, link, or corpus sanity; S0 infrastructure failure is ABSTAIN",
            "overall_coverage_rule": "YES if any production line/branch/function coverage percentage declines by more than 1.0 percentage point",
            "changed_code_rule": "YES if S1 executable changed-line coverage is <10%, or mapped changed-function reachability is 0%",
            "coverage_scope": "project production C/C++ files only; tests/fuzz/examples/build/generated excluded",
            "corpus": "five fixed Task-6 synthetic fallback byte strings; identical for S0 and S1; no post-commit data",
            "budget": "corpus replay only", "worker_concurrency": 8,
            "applicability_known_before_prediction": "32/104 cases have one of four already-frozen Task-6 project adapters; all other cases retained as NOT_APPLICABLE",
            "supported_projects": ["c-ares", "libplist", "libspng", "meshoptimizer"],
            "image_ids": {
                "c-ares": "sha256:4af5d560841e302242a22f4486b01cb26801072fd91de5a51a1a291a9954844c",
                "libplist": "sha256:cf4c75d74086bdc9db5fc17145d4ee07ec4f65e62773abff47b19e30ef768184",
                "libspng": "sha256:e9c4485da51e29da397987fc0720da345b8f76da964c1fef64fd5757c67c9b01",
                "meshoptimizer": "sha256:4e45a36808f0d23b443cf4c47d54dadead817d4857006741e2016fcdc7f93888",
            },
            "file_sha256": path_hashes(dynamic_files),
        },
        "m3_diff_derived_reachability": {
            "rule_version": "Task-7 M1 deterministic v1 byte-identical rules",
            "top_k": [1, 3, 5], "concurrency": 4, "uses_ground_truth_target": False,
            "uses_h1": False, "uses_llm": False,
            "known_frozen_defects": [
                "rank_targets.py v1 applies new_public_exported, fuzz_semantic_name, and changed_public_api scoring clauses to non-function candidates; preserved without repair for confirmatory reuse"
            ],
            "file_sha256": path_hashes(m3_files),
        },
        "m6_hybrid": "NOT_IMPLEMENTED_BEFORE_FREEZE_AND_EXCLUDED",
        "frozen_file_sha256": all_hashes,
        "environment": {
            "python": platform.python_version(), "platform": platform.platform(),
            "ctags": subprocess.check_output(["ctags", "--version"], text=True).splitlines()[0],
            "docker_server": subprocess.check_output(
                ["docker", "version", "--format", "{{.Server.Version}} {{.Server.Os}}/{{.Server.Arch}}"], text=True
            ).strip(),
        },
        "ordering": {
            "ground_truth_frozen_at": gt["frozen_at"], "input_frozen_at": inputs["frozen_at"],
            "experiment_config_frozen_at": frozen_at, "prediction_started_at": None,
        },
        "post_freeze_tuning_allowed": False,
    }
    write_json(OUTPUT, config)
    print(json.dumps({
        "status": config["status"], "frozen_at": frozen_at, "dataset_hash": config["dataset_hash"],
        "ground_truth_hash": config["ground_truth_hash"], "input_hash": config["input_hash"],
        "prompt_hash": config["prompt_hash"], "frozen_file_count": len(all_hashes),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
