#!/usr/bin/env python3
"""Evaluate a development prompt version and apply the task-5 stage gate."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "development-set"
VERSION = os.environ.get("DELTA_DEV_VERSION", "v1")


def pct(k: int, n: int) -> float:
    return 100.0 * k / n


def main() -> None:
    run = DEV / "runs" / VERSION
    expected = {r["prior_case_id"]: r for r in csv.DictReader(
        (DEV / "cases.csv").open(encoding="utf-8", newline=""))}
    pred = {r["case_id"]: r for r in
            (json.loads(line) for line in (run / "predictions.jsonl").read_text().splitlines() if line)}
    if set(pred) != set(expected):
        raise SystemExit("prediction/case mismatch")
    outcomes = []
    for case_id, gt in expected.items():
        p = pred[case_id]
        exp_before = gt["expected_gap_before"] == "YES"
        exp_after = gt["expected_gap_after"] == "YES"
        exp_maint = gt["maintenance_needed"] == "YES"
        derived = p["explicit_failure"] or p["delta_attribution"] in {"NEW", "AGGRAVATED"}
        outcomes.append({
            "development_id": gt["development_id"], "case_id": case_id, "case_type": gt["case_type"],
            "expected_gap_before": str(exp_before).lower(), "predicted_gap_before": str(p["gap_before"]["exists"]).lower(),
            "gap_before_correct": str(p["gap_before"]["exists"] == exp_before).lower(),
            "expected_gap_after": str(exp_after).lower(), "predicted_gap_after": str(p["gap_after"]["exists"]).lower(),
            "gap_after_correct": str(p["gap_after"]["exists"] == exp_after).lower(),
            "expected_delta": gt["expected_delta"], "predicted_delta": p["delta_attribution"],
            "delta_correct": str(p["delta_attribution"] == gt["expected_delta"]).lower(),
            "expected_maintenance": str(exp_maint).lower(), "predicted_maintenance_emitted": str(p["maintenance_needed"]).lower(),
            "predicted_maintenance_derived": str(derived).lower(),
            "output_consistent": str(p["maintenance_needed"] == derived).lower(),
            "maintenance_correct": str(derived == exp_maint).lower(), "confidence": p["confidence"],
            "reason": p["reason"],
        })
    with (run / "outcomes.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(outcomes[0])); writer.writeheader(); writer.writerows(outcomes)
    n4 = [r for r in outcomes if r["case_type"] == "N4_EXISTING_GAP"]
    pos = [r for r in outcomes if r["case_type"] == "COMMIT_INDUCED_POSITIVE"]
    metrics = {
        "prompt_version": VERSION, "valid_n4": len(n4), "valid_positive": len(pos),
        "n4_gap_before_accuracy": sum(r["gap_before_correct"] == "true" for r in n4) / len(n4),
        "n4_gap_after_accuracy": sum(r["gap_after_correct"] == "true" for r in n4) / len(n4),
        "n4_delta_accuracy": sum(r["delta_correct"] == "true" for r in n4) / len(n4),
        "n4_target_pattern_accuracy": sum(r["predicted_gap_before"] == "true" and
                                           r["predicted_gap_after"] == "true" and
                                           r["predicted_delta"] == "UNCHANGED" and
                                           r["predicted_maintenance_derived"] == "false" for r in n4) / len(n4),
        "n4_fpr": sum(r["predicted_maintenance_derived"] == "true" for r in n4) / len(n4),
        "positive_gap_before_accuracy": sum(r["gap_before_correct"] == "true" for r in pos) / len(pos),
        "positive_gap_after_accuracy": sum(r["gap_after_correct"] == "true" for r in pos) / len(pos),
        "positive_delta_accuracy": sum(r["delta_correct"] == "true" for r in pos) / len(pos),
        "positive_new_or_aggravated_recall": sum(r["predicted_delta"] in {"NEW", "AGGRAVATED"} for r in pos) / len(pos),
        "positive_recall": sum(r["predicted_maintenance_derived"] == "true" for r in pos) / len(pos),
        "output_consistency": sum(r["output_consistent"] == "true" for r in outcomes) / len(outcomes),
    }
    metrics["development_gate_pass"] = (
        metrics["n4_gap_before_accuracy"] >= 0.80 and metrics["n4_gap_after_accuracy"] >= 0.80 and
        metrics["n4_delta_accuracy"] >= 0.75 and metrics["positive_new_or_aggravated_recall"] >= 0.75 and
        metrics["n4_fpr"] <= 0.15 and metrics["positive_recall"] >= 0.75
    )
    metrics["blind_test_permitted"] = metrics["development_gate_pass"] and metrics["n4_fpr"] <= 0.20
    (run / "metrics.json").write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n")
    print(json.dumps(metrics, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
