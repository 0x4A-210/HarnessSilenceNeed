#!/usr/bin/env python3
"""Validate the frozen blind run and materialize its de-blinded evaluation."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve()
OUT = HERE.parents[1]
MAPPING = OUT / "data" / "case_mapping.csv"
PREDICTIONS = OUT / "results" / "llm_predictions.jsonl"
MANIFEST = OUT / "results" / "run_manifest.json"
AUDIT = OUT / "config" / "reasoning_audit.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def rate(numerator: int, denominator: int) -> str:
    return f"{numerator / denominator:.4f}" if denominator else ""


def main() -> None:
    mapping_rows = read_csv(MAPPING)
    prediction_rows = [
        json.loads(line)
        for line in PREDICTIONS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    audit_doc = json.loads(AUDIT.read_text(encoding="utf-8"))
    annotations = audit_doc["annotations"]

    if len(mapping_rows) != 105 or len(prediction_rows) != 105:
        raise RuntimeError(
            f"expected 105 mapping and prediction rows; got {len(mapping_rows)} and {len(prediction_rows)}"
        )
    mapping = {row["case_id"]: row for row in mapping_rows}
    predictions = {row["case_id"]: row for row in prediction_rows}
    if len(mapping) != 105 or len(predictions) != 105 or set(mapping) != set(predictions):
        raise RuntimeError("case IDs are missing, duplicated, or inconsistent")
    if manifest.get("status") != "complete" or manifest.get("valid_predictions") != 105:
        raise RuntimeError("blind-run manifest is not a clean 105-case completion")
    attempts = manifest.get("attempts", [])
    if len(attempts) != 105 or len({x["case_id"] for x in attempts}) != 105:
        raise RuntimeError("one-attempt invariant failed")
    if any(x.get("exit_code") != 0 or not x.get("valid_prediction") for x in attempts):
        raise RuntimeError("one or more blind invocations failed")

    outcomes: list[dict] = []
    confusion = Counter()
    stratum = Counter()
    project = Counter()
    for case_id in sorted(mapping):
        m = mapping[case_id]
        p = predictions[case_id]
        actual_positive = m["actual_label"] == "positive"
        predicted_positive = p["maintenance_needed"]
        if not isinstance(predicted_positive, bool):
            raise RuntimeError(f"non-boolean decision for {case_id}")
        outcome = (
            "TP" if actual_positive and predicted_positive else
            "FN" if actual_positive else
            "FP" if predicted_positive else
            "TN"
        )
        confusion[outcome] += 1
        if not actual_positive:
            stratum[(m["negative_type"], outcome)] += 1
        project[(m["project"], outcome)] += 1
        outcomes.append({
            "case_id": case_id,
            "project": m["project"],
            "commit_id": m["commit_id"],
            "actual_label": m["actual_label"],
            "negative_type": m["negative_type"],
            "predicted_label": "YES" if predicted_positive else "NO",
            "confidence": p["confidence"],
            "outcome": outcome,
            "reason": p["reason"],
        })

    tp, fp, fn, tn = (confusion[x] for x in ("TP", "FP", "FN", "TN"))
    required_audit = {
        row["case_id"] for row in outcomes
        if row["actual_label"] == "positive" or row["outcome"] in {"FP", "FN"}
    }
    if set(annotations) != required_audit:
        missing = sorted(required_audit - set(annotations))
        extra = sorted(set(annotations) - required_audit)
        raise RuntimeError(f"audit coverage mismatch; missing={missing}, extra={extra}")

    audit_rows = []
    for case_id in sorted(required_audit):
        outcome = next(row for row in outcomes if row["case_id"] == case_id)
        note = annotations[case_id]
        expected_correct = int(outcome["outcome"] in {"TP", "TN"})
        if note["decision_correct"] != expected_correct:
            raise RuntimeError(f"decision_correct inconsistent for {case_id}")
        audit_rows.append({
            "case_id": case_id,
            "project": outcome["project"],
            "actual_label": outcome["actual_label"],
            "predicted_label": outcome["predicted_label"],
            "outcome": outcome["outcome"],
            "decision_correct": note["decision_correct"],
            "reason_correct": note["reason_correct"],
            "evidence_grounded": note["evidence_grounded"],
            "fp_category": note["fp_category"],
            "label_ambiguity": note["label_ambiguity"],
            "audit_note": note["audit_note"],
        })

    hard_fp = stratum[("hard", "FP")]
    matched_fp = stratum[("matched", "FP")]
    easy_fp = stratum[("easy", "FP")]
    tp_reason_correct = sum(
        row["reason_correct"] for row in audit_rows if row["outcome"] == "TP"
    )
    tp_evidence_grounded = sum(
        row["evidence_grounded"] for row in audit_rows if row["outcome"] == "TP"
    )

    if tp >= 4 and fp <= 5 and tp_reason_correct >= 3 and tp_evidence_grounded >= 3:
        gate = "STRONG GO"
    elif tp >= 3 and fp <= 10:
        gate = "MODERATE GO"
    else:
        gate = "NO-GO"

    write_csv(OUT / "results" / "confusion_matrix.csv", [
        {"predicted": "YES", "actual_positive": tp, "actual_negative": fp},
        {"predicted": "NO", "actual_positive": fn, "actual_negative": tn},
    ], ["predicted", "actual_positive", "actual_negative"])

    write_csv(OUT / "results" / "case_outcomes.csv", outcomes, [
        "case_id", "project", "commit_id", "actual_label", "negative_type",
        "predicted_label", "confidence", "outcome", "reason",
    ])

    write_csv(OUT / "results" / "reasoning_quality.csv", audit_rows, [
        "case_id", "project", "actual_label", "predicted_label", "outcome",
        "decision_correct", "reason_correct", "evidence_grounded", "fp_category",
        "label_ambiguity", "audit_note",
    ])

    summary_rows = [
        {"metric": "projects", "value": 10, "denominator": "", "rate": "", "note": "all selected projects represented"},
        {"metric": "total_cases", "value": 105, "denominator": "", "rate": "", "note": "one prediction per case"},
        {"metric": "actual_positive", "value": 5, "denominator": "", "rate": "", "note": "selected from 13 confirmed events"},
        {"metric": "actual_negative", "value": 100, "denominator": "", "rate": "", "note": "20 easy, 60 matched, 20 hard"},
        {"metric": "TP", "value": tp, "denominator": 5, "rate": rate(tp, 5), "note": "primary positive-detection count"},
        {"metric": "FN", "value": fn, "denominator": 5, "rate": rate(fn, 5), "note": ""},
        {"metric": "FP", "value": fp, "denominator": 100, "rate": rate(fp, 100), "note": "primary false-alarm count"},
        {"metric": "TN", "value": tn, "denominator": 100, "rate": rate(tn, 100), "note": ""},
        {"metric": "FP_easy", "value": easy_fp, "denominator": 20, "rate": rate(easy_fp, 20), "note": ""},
        {"metric": "FP_matched", "value": matched_fp, "denominator": 60, "rate": rate(matched_fp, 60), "note": ""},
        {"metric": "FP_hard", "value": hard_fp, "denominator": 20, "rate": rate(hard_fp, 20), "note": "primary hard-negative count"},
        {"metric": "predicted_YES", "value": tp + fp, "denominator": 105, "rate": rate(tp + fp, 105), "note": ""},
        {"metric": "TP_reason_correct", "value": tp_reason_correct, "denominator": tp, "rate": rate(tp_reason_correct, tp), "note": "post-run semantic audit"},
        {"metric": "TP_evidence_grounded", "value": tp_evidence_grounded, "denominator": tp, "rate": rate(tp_evidence_grounded, tp), "note": "post-run semantic audit"},
        {"metric": "pre_registered_gate", "value": gate, "denominator": "", "rate": "", "note": "Strong requires TP>=4 and FP<=5; Moderate requires TP>=3 and FP<=10"},
    ]
    write_csv(OUT / "results" / "summary.csv", summary_rows, [
        "metric", "value", "denominator", "rate", "note",
    ])

    print(json.dumps({
        "TP": tp,
        "FP": fp,
        "FN": fn,
        "TN": tn,
        "FP_easy": easy_fp,
        "FP_matched": matched_fp,
        "FP_hard": hard_fp,
        "TP_reason_correct": tp_reason_correct,
        "TP_evidence_grounded": tp_evidence_grounded,
        "gate": gate,
    }, indent=2))


if __name__ == "__main__":
    main()
