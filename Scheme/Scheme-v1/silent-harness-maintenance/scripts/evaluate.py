#!/usr/bin/env python3
"""Reveal the frozen labels and compute all preregistered metrics."""

from __future__ import annotations

import csv
import json
import math
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GT = ROOT / "frozen-ground-truth"
PRED = ROOT / "predictions"
RESULTS = ROOT / "results"
RESULTS.mkdir(parents=True, exist_ok=True)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str] | None = None) -> None:
    if not rows and not fields:
        raise ValueError(path)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def div(a: int, b: int) -> float | None:
    return a / b if b else None


def fmt(value: float | None) -> str:
    return "NOT_ESTIMABLE" if value is None else f"{value:.6f}"


def confusion(rows: list[dict[str, object]]) -> dict[str, object]:
    counts = Counter(str(r["outcome"]) for r in rows)
    tp, fp, fn, tn = (counts[x] for x in ("TP", "FP", "FN", "TN"))
    precision = div(tp, tp + fp); recall = div(tp, tp + fn)
    specificity = div(tn, tn + fp); fpr = div(fp, fp + tn)
    f1 = None if precision is None or recall is None or precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {
        "n": len(rows), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": fmt(precision), "recall": fmt(recall), "f1": fmt(f1),
        "fpr": fmt(fpr), "specificity": fmt(specificity),
    }


if not (PRED / "prediction_freeze_manifest.json").exists():
    raise SystemExit("Predictions must be frozen before label reveal")
labels = {r["case_id"]: r for r in read_csv(GT / "labels.csv")}
build = {r["case_id"]: r for r in read_csv(PRED / "build_only.csv")}
gap = {str(r["case_id"]): r for r in read_jsonl(PRED / "gap_only.jsonl")}
evo = {str(r["case_id"]): r for r in read_jsonl(PRED / "evolution_aware.jsonl")}
if not all(len(x) == 80 and set(x) == set(labels) for x in (build, gap, evo)):
    raise SystemExit("Prediction/label case set mismatch")

baselines = {
    "Build-Only": {case: build[case]["maintenance_needed"] == "YES" for case in labels},
    "Gap-Only": {case: bool(gap[case]["gap_exists"]) for case in labels},
    "Evolution-Aware": {case: bool(evo[case]["maintenance_needed"]) for case in labels},
}

case_rows = []
for case_id, label in sorted(labels.items()):
    actual = label["label"] != "VERIFIED_NEGATIVE"
    row: dict[str, object] = {
        **label,
        "actual_maintenance_needed": "YES" if actual else "NO",
        "negative_stratum": "SOURCE_ONLY" if label["internal_id"].startswith("S") else ("COEVOLUTION_HARD" if not actual else ""),
    }
    for name, predictions in baselines.items():
        pred = predictions[case_id]
        outcome = "TP" if actual and pred else "FN" if actual else "FP" if pred else "TN"
        prefix = name.lower().replace("-", "_")
        row[f"{prefix}_prediction"] = "YES" if pred else "NO"
        row[f"{prefix}_outcome"] = outcome
    row["gap_only_reason"] = gap[case_id]["reason"]
    row["gap_only_evidence"] = json.dumps(gap[case_id]["evidence"], ensure_ascii=False)
    row["evolution_gap_exists"] = evo[case_id]["gap_exists"]
    row["evolution_commit_induced"] = evo[case_id]["commit_induced"]
    row["evolution_confidence"] = evo[case_id]["confidence"]
    row["evolution_reason"] = evo[case_id]["reason"]
    row["evolution_evidence"] = json.dumps(evo[case_id]["evidence"], ensure_ascii=False)
    case_rows.append(row)
write_csv(RESULTS / "case_outcomes.csv", case_rows)

overall_rows = []
silent_rows = []
explicit_rows = []
hard_rows = []
comparison = []
for baseline, predictions in baselines.items():
    evaluated = []
    for case_id, label in labels.items():
        actual = label["label"] != "VERIFIED_NEGATIVE"
        pred = predictions[case_id]
        outcome = "TP" if actual and pred else "FN" if actual else "FP" if pred else "TN"
        evaluated.append({"case_id": case_id, "outcome": outcome})
    metrics = confusion(evaluated)
    overall_rows.append({"baseline": baseline, **metrics})

    def positive_stratum(label_name: str) -> list[dict[str, object]]:
        selected = []
        for case_id, label in labels.items():
            if label["label"] not in {label_name, "VERIFIED_NEGATIVE"}:
                continue
            actual = label["label"] == label_name
            pred = predictions[case_id]
            outcome = "TP" if actual and pred else "FN" if actual else "FP" if pred else "TN"
            selected.append({"case_id": case_id, "outcome": outcome})
        return selected

    sm = confusion(positive_stratum("VERIFIED_SILENT_POSITIVE"))
    ex = confusion(positive_stratum("VERIFIED_EXPLICIT_POSITIVE"))
    silent_rows.append({"baseline": baseline, **sm})
    explicit_rows.append({"baseline": baseline, **ex})
    hard_neg = []
    for case_id, label in labels.items():
        if label["label"] == "VERIFIED_NEGATIVE" and label["internal_id"].startswith("N"):
            pred = predictions[case_id]
            hard_neg.append({"case_id": case_id, "outcome": "FP" if pred else "TN"})
    hm = confusion(hard_neg)
    hard_rows.append({"baseline": baseline, **hm})
    comparison.append({
        "baseline": baseline, "explicit_recall": ex["recall"], "silent_recall": sm["recall"],
        "overall_precision": metrics["precision"], "negative_fpr": metrics["fpr"],
        "hard_negative_fpr": hm["fpr"], "tp": metrics["tp"], "fp": metrics["fp"],
        "fn": metrics["fn"], "tn": metrics["tn"],
    })

write_csv(RESULTS / "overall_metrics.csv", overall_rows)
write_csv(RESULTS / "silent_positive_metrics.csv", silent_rows)
write_csv(RESULTS / "explicit_positive_metrics.csv", explicit_rows)
write_csv(RESULTS / "hard_negative_metrics.csv", hard_rows)
write_csv(RESULTS / "baseline_comparison.csv", comparison)

taxonomy_rows = []
for baseline, predictions in baselines.items():
    for positive_type in ("VP1", "VP2", "VP3", "VP4", "VP5"):
        cases = [case for case, label in labels.items() if label["positive_type"] == positive_type]
        tp = sum(predictions[case] for case in cases)
        taxonomy_rows.append({"baseline": baseline, "positive_type": positive_type,
                              "n": len(cases), "tp": tp, "fn": len(cases) - tp,
                              "recall": fmt(div(tp, len(cases)))})
write_csv(RESULTS / "taxonomy_metrics.csv", taxonomy_rows)

project_rows = []
for baseline, predictions in baselines.items():
    for project in sorted({x["project"] for x in labels.values()}):
        cases = [case for case, label in labels.items() if label["project"] == project]
        evaluated = []
        for case in cases:
            actual = labels[case]["label"] != "VERIFIED_NEGATIVE"
            pred = predictions[case]
            evaluated.append({"outcome": "TP" if actual and pred else "FN" if actual else "FP" if pred else "TN"})
        project_rows.append({"baseline": baseline, "project": project, **confusion(evaluated)})
write_csv(RESULTS / "project_metrics.csv", project_rows)

gap_fp = next(r["fp"] for r in overall_rows if r["baseline"] == "Gap-Only")
evo_fp = next(r["fp"] for r in overall_rows if r["baseline"] == "Evolution-Aware")
gap_silent = float(next(r["recall"] for r in silent_rows if r["baseline"] == "Gap-Only"))
evo_silent = float(next(r["recall"] for r in silent_rows if r["baseline"] == "Evolution-Aware"))
fp_reduction = div(int(gap_fp) - int(evo_fp), int(gap_fp))

existing_cases = [case for case, label in labels.items() if label["negative_type"] == "N4"]
existing_rows = []
for baseline, predictions in baselines.items():
    fp = sum(predictions[case] for case in existing_cases)
    existing_rows.append({"baseline": baseline, "existing_gap_n": len(existing_cases),
                          "existing_gap_fp": fp, "existing_gap_fpr": fmt(div(fp, len(existing_cases)))})
write_csv(RESULTS / "existing_gap_metrics.csv", existing_rows)

# Freeze the exact audit sampling set now: all Evolution-Aware silent TP, all
# Evolution-Aware FP/FN, and seed-fixed 10 TN.  Manual judgments are added by a
# separate script without altering predictions or labels.
evo_outcome = {r["case_id"]: r["evolution_aware_outcome"] for r in case_rows}
silent_tp = [case for case, label in labels.items() if label["label"] == "VERIFIED_SILENT_POSITIVE" and evo_outcome[case] == "TP"]
all_fp = [case for case in labels if evo_outcome[case] == "FP"]
all_fn = [case for case in labels if evo_outcome[case] == "FN"]
tns = sorted(case for case in labels if evo_outcome[case] == "TN")
sample_tn = sorted(random.Random(20260910).sample(tns, min(10, len(tns))))
queue = []
for case in sorted(set(silent_tp + all_fp + all_fn + sample_tn)):
    categories = []
    if case in silent_tp: categories.append("ALL_SILENT_TP")
    if case in all_fp: categories.append("ALL_FP")
    if case in all_fn: categories.append("ALL_FN")
    if case in sample_tn: categories.append("RANDOM_TN")
    label = labels[case]; prediction = evo[case]
    queue.append({
        "case_id": case, "internal_id": label["internal_id"], "audit_categories": ";".join(categories),
        "ground_truth_label": label["label"], "positive_type": label["positive_type"],
        "evidence_summary": label["evidence_summary"], "prediction": json.dumps(prediction, ensure_ascii=False),
    })
write_csv(RESULTS / "reasoning_audit_queue.csv", queue)

summary = {
    "labels_revealed_at": datetime.now(timezone.utc).isoformat(),
    "counts": dict(Counter(x["label"] for x in labels.values())),
    "overall": {r["baseline"]: r for r in overall_rows},
    "silent": {r["baseline"]: r for r in silent_rows},
    "explicit": {r["baseline"]: r for r in explicit_rows},
    "hard_negative": {r["baseline"]: r for r in hard_rows},
    "fp_reduction_gap_to_evolution": fmt(fp_reduction),
    "silent_recall_drop_gap_to_evolution": fmt(gap_silent - evo_silent),
    "existing_gap_negative_count": len(existing_cases),
    "reasoning_audit_queue_count": len(queue),
    "reasoning_audit_sample": {"all_silent_tp": len(silent_tp), "all_fp": len(all_fp),
                               "all_fn": len(all_fn), "random_tn": len(sample_tn)},
}
(RESULTS / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2, sort_keys=True))
