#!/usr/bin/env python3
from __future__ import annotations

import subprocess

from build_callgraph import ctags_version
from common import ROOT, read_csv, sha256_file, utc_now, write_json


FROZEN_FILES = [
    "dataset/cases.csv",
    "protocol/m1_rules_v1.md",
    "scripts/common.py",
    "scripts/extract_diff_targets.py",
    "scripts/build_callgraph.py",
    "scripts/rank_targets.py",
    "scripts/static_reachability.py",
    "scripts/discover_case.py",
    "scripts/run_discovery.py",
]


def main() -> None:
    cases = read_csv(ROOT / "dataset" / "cases.csv")
    write_json(ROOT / "frozen-experiment-config.json", {
        "schema_version": "t7-freeze-v1",
        "frozen_at": utc_now(),
        "phase": "A_DIAGNOSTIC_KILL_TEST",
        "case_count": len(cases),
        "case_ids": [row["case_id"] for row in cases],
        "m1_allowed_case_columns": list(cases[0]) if cases else [],
        "m1_forbidden_information": [
            "ground_truth_target", "label", "H1", "harness_diff",
            "coverage_oracle", "LLM_prediction",
        ],
        "m1_llm_calls": 0,
        "m1_rule_version": "v1",
        "tool_versions": {
            "ctags": ctags_version(),
            "python": subprocess.run(["python3", "--version"], check=True,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True).stdout.strip(),
        },
        "frozen_file_sha256": {name: sha256_file(ROOT / name) for name in FROZEN_FILES},
        "ground_truth_file_intentionally_excluded_from_m1_freeze": "dataset/gt_targets.csv",
        "pilot_cases": ["T5001", "T5002"],
        "pilot_use": "mechanical smoke testing only; excluded from formal outputs",
        "post_freeze_rule_changes_allowed": False,
    })


if __name__ == "__main__":
    main()
