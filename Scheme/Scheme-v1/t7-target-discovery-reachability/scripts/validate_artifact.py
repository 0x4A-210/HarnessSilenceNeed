#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from common import ROOT, read_csv, sha256_file, utc_now, write_json


REQUIRED = [
    "README.md", "NEXT_STEP_TARGET_DISCOVERY_REACHABILITY.md",
    "dataset/cases.csv", "dataset/gt_targets.csv", "dataset/preparation_manifest.json",
    "frozen-experiment-config.json", "protocol/m1_rules_v1.md",
    "scripts/extract_diff_targets.py", "scripts/rank_targets.py", "scripts/build_callgraph.py",
    "scripts/static_reachability.py", "scripts/dynamic_reachability.py", "scripts/evaluate.py",
    "results/target_recall.csv", "results/target_recall_summary.csv",
    "results/exact_target_oracle.csv", "results/diff_reachability_top1.csv",
    "results/diff_reachability_top3.csv", "results/diff_reachability_top5.csv",
    "results/delta_aware.csv", "results/applicability.csv", "results/latency.csv",
    "results/latency_summary.csv", "results/comparison.csv", "results/kill_gate.csv",
    "results/dynamic_supplement.csv", "results/protocol_conformance.csv",
    "reports/target_discovery_results.md", "reports/reachability_results.md",
    "reports/non_function_cases.md", "reports/error_analysis.md",
    "reports/reviewer_kill_test.md", "reports/go_no_go.md",
]


def add(checks: list[dict], name: str, passed: bool, detail: str) -> None:
    checks.append({"check": name, "passed": bool(passed), "detail": detail})


def main() -> None:
    checks = []
    missing = [name for name in REQUIRED if not (ROOT / name).is_file()]
    add(checks, "required_files", not missing, f"missing={missing}")

    cases = read_csv(ROOT / "dataset" / "cases.csv")
    gt = read_csv(ROOT / "dataset" / "gt_targets.csv")
    add(checks, "case_count", len(cases) == 39, f"observed={len(cases)} expected=39")
    add(checks, "unique_commit_count", len({row["s1_commit"] for row in cases}) == 39,
        f'observed={len({row["s1_commit"] for row in cases})} expected=39')
    projects = Counter(row["project"] for row in cases)
    add(checks, "project_distribution", projects == Counter({"c-ares": 10, "libplist": 10,
                                                               "libspng": 10, "meshoptimizer": 9}),
        f"observed={dict(projects)}")
    labels = Counter(row["label"] for row in gt)
    add(checks, "label_distribution", labels == Counter({"POSITIVE": 20, "N4": 19}),
        f"observed={dict(labels)}")
    safe_fields = ["case_id", "project", "s0_commit", "s1_commit", "commit_time",
                   "h0_harness_paths", "phase"]
    add(checks, "m1_case_schema", list(cases[0]) == safe_fields,
        f"fields={list(cases[0])}")

    config = json.loads((ROOT / "frozen-experiment-config.json").read_text())
    config_mismatch = [name for name, digest in config["frozen_file_sha256"].items()
                       if sha256_file(ROOT / name) != digest]
    add(checks, "frozen_rules_unchanged", not config_mismatch, f"mismatch={config_mismatch}")
    freeze = json.loads((ROOT / "target-discovery" / "prediction_freeze_manifest.json").read_text())
    output_mismatch = [name for name, digest in freeze["per_file_sha256"].items()
                       if sha256_file(ROOT / "target-discovery" / name) != digest]
    add(checks, "m1_outputs_unchanged", not output_mismatch, f"mismatch={output_mismatch}")
    add(checks, "freeze_order", config["frozen_at"] < freeze["frozen_at"],
        f'rules={config["frozen_at"]}; outputs={freeze["frozen_at"]}')

    outputs = []
    for case in cases:
        path = ROOT / "target-discovery" / f'{case["case_id"]}.json'
        if path.is_file():
            outputs.append(json.loads(path.read_text()))
    add(checks, "m1_output_count", len(outputs) == 39, f"observed={len(outputs)}")
    prohibited_top_keys = {"label", "exact_target", "target_symbol", "ground_truth"}
    leaked = [row["case_id"] for row in outputs if prohibited_top_keys & set(row)]
    add(checks, "m1_no_gt_fields", not leaked, f"cases={leaked}")
    bad_flags = [row["case_id"] for row in outputs
                 if row["uses_ground_truth_target"] or row["uses_llm"] or row["uses_h1_or_harness_diff"]]
    add(checks, "m1_forbidden_use_flags", not bad_flags, f"cases={bad_flags}")
    run = json.loads((ROOT / "results" / "m1_run_manifest.json").read_text())
    add(checks, "independent_process_success", run["success_count"] == 39 and not run["failures"],
        f'success={run["success_count"]}; failures={len(run["failures"])}')

    expected_rows = {
        "results/target_recall.csv": 39, "results/exact_target_oracle.csv": 39,
        "results/diff_reachability_top1.csv": 39, "results/diff_reachability_top3.csv": 39,
        "results/diff_reachability_top5.csv": 39, "results/delta_aware.csv": 39,
        "results/comparison.csv": 5,
    }
    wrong_rows = {name: len(read_csv(ROOT / name)) for name, expected in expected_rows.items()
                  if len(read_csv(ROOT / name)) != expected}
    add(checks, "result_row_counts", not wrong_rows, f"wrong={wrong_rows}")
    delta = read_csv(ROOT / "results" / "delta_aware.csv")
    add(checks, "delta_reused", len(delta) == 39 and all(row["reused_frozen_prediction"] == "True" for row in delta),
        "39 frozen M2 records expected")
    dynamic = read_csv(ROOT / "results" / "dynamic_supplement.csv")
    add(checks, "dynamic_is_supplement_only",
        bool(dynamic) and all(row["influenced_primary_m1_decision"] == "False" for row in dynamic),
        f"rows={len(dynamic)}")
    gate = read_csv(ROOT / "results" / "kill_gate.csv")
    add(checks, "kill_gate_outcome", len(gate) == 3 and all(row["gate_outcome"] == "CONTINUE" for row in gate),
        f"outcomes={[row['gate_outcome'] for row in gate]}")

    reviewer = (ROOT / "reports" / "reviewer_kill_test.md").read_text(encoding="utf-8")
    add(checks, "reviewer_answers", all(f"{number}. **" in reviewer for number in range(1, 16)),
        "expected numbered answers 1..15")
    conformance = read_csv(ROOT / "results" / "protocol_conformance.csv")
    deviations = [row for row in conformance if row["status"] == "DEVIATION"]
    add(checks, "protocol_deviation_disclosed", len(deviations) == 1 and deviations[0]["check_id"] == "D1",
        f"deviations={[row['check_id'] for row in deviations]}")

    failed = [row for row in checks if not row["passed"]]
    validation = {
        "validated_at": utc_now(), "status": ("FAIL" if failed else "PASS_WITH_DISCLOSED_PROTOCOL_DEVIATION"),
        "check_count": len(checks), "passed_count": len(checks) - len(failed),
        "failed_count": len(failed), "checks": checks,
        "known_protocol_deviation": "D1 non-function candidates received function-only score bonuses",
        "primary_outcome": "CONTINUE",
        "task_spec_sha256": sha256_file(ROOT.parent / "task-7.md"),
    }
    write_json(ROOT / "results" / "validation.json", validation)

    entries = {}
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.name == "artifact_manifest.json" or "__pycache__" in path.parts:
            continue
        relative = path.relative_to(ROOT)
        if any(part.startswith(".pilot") for part in relative.parts):
            continue
        # Exclude the accidental nested pilot-only directory from the deliverable manifest.
        if relative.parts and relative.parts[0] == ROOT.name:
            continue
        entries[str(relative)] = sha256_file(path)
    write_json(ROOT / "artifact_manifest.json", {
        "created_at": utc_now(), "file_count": len(entries), "files": entries,
        "validation_status": validation["status"],
        "m1_prediction_aggregate_sha256": freeze["aggregate_sha256"],
    })
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
