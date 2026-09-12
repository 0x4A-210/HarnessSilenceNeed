#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import platform
import subprocess

from common import (OSS_FUZZ, ROOT, T5, composite_hash, sha256_file, utc_now,
                    write_json)


def output(cmd: list[str]) -> str:
    return subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE).stdout.strip()


def main() -> None:
    config_path = ROOT / "experiment_config.json"
    if config_path.exists():
        raise SystemExit("refusing to overwrite frozen experiment_config.json")

    frozen_files = [
        ROOT / "dataset" / "cases.csv",
        ROOT / "dataset" / "corpus_manifest.csv",
        ROOT / "dataset" / "changed_code.csv",
        ROOT / "dataset" / "target_anchors.csv",
        ROOT.parent / "task-6.md",
        T5 / "frozen-ground-truth" / "labels.csv",
        T5 / "frozen-ground-truth" / "evidence.csv",
        T5 / "frozen-ground-truth" / "invalidations.csv",
        T5 / "predictions" / "delta_aware.jsonl",
        T5 / "predictions" / "run_manifest_delta_aware.json",
        T5 / "frozen-experiment-config.json",
    ]
    frozen_files.extend(sorted((ROOT / "scripts").glob("*.py")))
    frozen_files.extend(sorted((ROOT / "scripts").glob("*.sh")))
    image_data = {}
    for project in ("c-ares", "libplist", "libspng", "meshoptimizer"):
        raw = output(["docker", "image", "inspect", f"gcr.io/oss-fuzz/{project}"])
        info = json.loads(raw)[0]
        image_data[project] = {
            "image_id": info["Id"],
            "repo_digests": info.get("RepoDigests", []),
        }

    config = {
        "status": "FROZEN_BEFORE_FORMAL_DYNAMIC_EXECUTION",
        "frozen_at": utc_now(),
        "phase": "A_DIAGNOSTIC_KILL_TEST",
        "phase_a_cases": 39,
        "phase_b_gate": "RUN_ONLY_IF_PHASE_A_DECISION_IS_CONTINUE",
        "task6_sha256": sha256_file(ROOT.parent / "task-6.md"),
        "frozen_file_sha256": {str(p.relative_to(ROOT.parent)): sha256_file(p)
                               for p in frozen_files},
        "dataset_composite_sha256": composite_hash([
            ROOT / "dataset" / "cases.csv",
            ROOT / "dataset" / "corpus_manifest.csv",
            ROOT / "dataset" / "changed_code.csv",
            ROOT / "dataset" / "target_anchors.csv",
        ]),
        "task5_delta_prediction_policy": {
            "reuse_only": True,
            "rerun": False,
            "prompt_modified": False,
            "task5_prediction_sha256": sha256_file(T5 / "predictions" / "delta_aware.jsonl"),
        },
        "dynamic_environment": {
            "oss_fuzz_commit": output(["git", "-C", str(OSS_FUZZ), "rev-parse", "HEAD"]),
            "docker_server": output(["docker", "info", "--format", "{{.ServerVersion}} {{.OSType}} {{.Architecture}}"]),
            "compiler": "clang 22.0.0git cb2f0d0a5f14c183e7182aba0f0e54a518de9e3f",
            "instrumentation": "-fprofile-instr-generate -fcoverage-mapping",
            "fuzz_engine": "libFuzzer from pinned OSS-Fuzz base-builder",
            "sanitizer": "coverage; runtime sanity uses the same binary",
            "architecture": "x86_64",
            "fuzz_process_cpus": 1,
            "memory_limit_mb": 2048,
            "per_input_timeout_seconds": 10,
            "worker_concurrency": 8,
            "build_jobs_per_worker": 3,
            "host": platform.platform(),
            "logical_cpus": os.cpu_count(),
            "project_images": image_data,
        },
        "corpus_policy": {
            "primary": "test/fuzz corpus present in S0 tree",
            "fallback": "five fixed synthetic byte strings of lengths 1,4,16,64,256",
            "post_commit_corpus_forbidden": True,
            "same_initial_corpus_for_s0_s1": True,
            "each_fuzz_run_starts_from_fresh_copy": True,
        },
        "budget_policy": {
            "unit": "seconds per snapshot across complete H0 target set",
            "target_allocation": "equal split; union all target profiles",
            "budgets": [
                {"name": "corpus", "seconds": 0, "repeats": 1},
                {"name": "1m", "seconds": 60, "repeats": 1},
                {"name": "5m", "seconds": 300, "repeats": 3},
                {"name": "15m", "seconds": 900, "repeats": 1},
            ],
            "30m": "NOT_RUN_RESOURCE_BOUND; protocol explicitly permits corpus/1m/5m/15m minimum",
            "libfuzzer_seed": "1337 + repeat index; identical for S0 and S1",
        },
        "preregistered_decision_rules": {
            "build_only": "YES only when S0+H0 builds/sanity-runs and S1+H0 fails build, link, or corpus sanity; common historical infrastructure failure is UNAVAILABLE",
            "overall_s1": "no deployable cross-project threshold; report post-hoc threshold-sweep upper bound only",
            "overall_delta": "YES if any production-only line/branch/function coverage percentage falls by more than 1.0 percentage point from S0 to S1",
            "changed_code": "YES if S1 has executable changed lines and <10% are covered, or has mapped changed functions and 0% are reached; report both components separately",
            "function_reachability": "YES for target absent in S0 and present-but-unreached in S1, or reached in S0 but unreached in S1; NO for existing target unreached in both; abstain if target presence cannot be established",
            "threshold_tuning_on_phase_a_labels": False,
            "sweeps": "explicitly ORACLE/POST_HOC upper bounds, never deployment results",
        },
        "coverage_scope": "project production C/C++ files only; test/fuzz/example/build/generated files excluded",
        "failure_policy": {
            "retain_all": True,
            "statuses": ["DYNAMIC_UNAVAILABLE", "BUILD_UNAVAILABLE", "COVERAGE_UNAVAILABLE", "NONDETERMINISTIC", "TIMEOUT"],
            "classification_complete_case": "only cases with required signal",
            "failure_rate_denominator": 39,
        },
        "h1_policy": "Task-5 has no identified H1; do not synthesize it. B4 is reported unavailable unless a provenance-audited update is found.",
    }
    write_json(config_path, config)
    print(json.dumps({"status": config["status"], "frozen_at": config["frozen_at"],
                      "dataset_hash": config["dataset_composite_sha256"]}))


if __name__ == "__main__":
    main()
