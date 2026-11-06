#!/usr/bin/env python3
from __future__ import annotations

from common import ROOT, T5, T6, read_csv, sha256_file, utc_now, write_csv, write_json


def main() -> None:
    source_cases = read_csv(T6 / "dataset" / "cases.csv")
    evidence = {row["case_id"]: row for row in read_csv(T5 / "frozen-ground-truth" / "evidence.csv")}
    anchors = {(row["case_id"], row["version"]): row
               for row in read_csv(T6 / "dataset" / "target_anchors.csv")}
    cases = []
    gt = []
    for source in source_cases:
        case_id = source["case_id"]
        ev = evidence[case_id]
        cases.append({
            "case_id": case_id,
            "project": source["project"],
            "s0_commit": source["s0_commit"],
            "s1_commit": source["s1_commit"],
            "commit_time": source["commit_time"],
            "h0_harness_paths": ev["h0_harness_paths"],
            "phase": "A_DIAGNOSTIC_KILL_TEST",
        })
        target = source["target_symbol"]
        kind = anchors[(case_id, "s1")]["target_kind"]
        target_type = "FUNCTION_TARGET" if kind == "FUNCTION" else "NON_FUNCTION_CONFIG"
        gt.append({
            "case_id": case_id,
            "project": source["project"],
            "label": source["label"],
            "exact_target_type": target_type,
            "exact_target_function": target if kind == "FUNCTION" else "",
            "exact_target_api": target if kind == "FUNCTION" else "",
            "exact_target_config": target if kind != "FUNCTION" else "",
            "exact_target_state": "",
            "expected_delta": source["expected_delta"],
            "impact_scope": source["impact_scope"],
            "evidence_type": ev["evidence_type"],
            "semantic_audit": ev["semantic_audit"],
        })
    case_fields = ["case_id", "project", "s0_commit", "s1_commit", "commit_time",
                   "h0_harness_paths", "phase"]
    gt_fields = ["case_id", "project", "label", "exact_target_type",
                 "exact_target_function", "exact_target_api", "exact_target_config",
                 "exact_target_state", "expected_delta", "impact_scope", "evidence_type",
                 "semantic_audit"]
    write_csv(ROOT / "dataset" / "cases.csv", cases, case_fields)
    write_csv(ROOT / "dataset" / "gt_targets.csv", gt, gt_fields)
    write_json(ROOT / "dataset" / "preparation_manifest.json", {
        "prepared_at": utc_now(),
        "case_count": len(cases),
        "positive_count": sum(row["label"] == "POSITIVE" for row in gt),
        "n4_count": sum(row["label"] == "N4" for row in gt),
        "function_target_count": sum(row["exact_target_type"] == "FUNCTION_TARGET" for row in gt),
        "non_function_target_count": sum(row["exact_target_type"] != "FUNCTION_TARGET" for row in gt),
        "m1_cases_columns": case_fields,
        "m1_cases_contains_ground_truth": False,
        "source_case_sha256": sha256_file(T6 / "dataset" / "cases.csv"),
        "source_gt_sha256": sha256_file(T5 / "frozen-ground-truth" / "evidence.csv"),
        "status": "PREPARED_BEFORE_M1_EXECUTION",
    })


if __name__ == "__main__":
    main()
