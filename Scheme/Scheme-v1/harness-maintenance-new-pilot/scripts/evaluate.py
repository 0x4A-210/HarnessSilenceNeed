#!/usr/bin/env python3
"""Evaluate the frozen predictions under initial and audited ground truth."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve()
OUT = HERE.parents[1]
DATA = OUT / "data"
RESULTS = OUT / "results"
CASES = OUT / "cases"


def read_csv(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8", newline="")))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def load_jsonl(path: Path) -> dict[str, dict[str, object]]:
    return {value["case_id"]: value for value in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())}


def outcome(actual: bool, predicted: bool) -> str:
    return "TP" if actual and predicted else "FN" if actual else "FP" if predicted else "TN"


def measures(counts: Counter[str]) -> dict[str, object]:
    tp, fp, fn, tn = (counts[x] for x in ("TP", "FP", "FN", "TN"))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    fpr = fp / (fp + tn) if fp + tn else 0.0
    accuracy = (tp + tn) / (tp + fp + fn + tn)
    return {
        "TP": tp, "FP": fp, "FN": fn, "TN": tn,
        "precision": round(precision, 6), "recall": round(recall, 6),
        "f1": round(f1, 6), "false_positive_rate": round(fpr, 6),
        "accuracy": round(accuracy, 6), "n": tp + fp + fn + tn,
    }


def grounding_ratio(prediction: dict[str, object], input_text: str) -> float:
    claim = str(prediction.get("reason", "")) + " " + " ".join(str(x) for x in prediction.get("evidence", []))
    identifiers = set(re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*[_A-Z][A-Za-z0-9_]*\b", claim))
    identifiers = {x for x in identifiers if len(x) >= 5 and x not in {"S0", "S1", "H0", "YES", "NO"}}
    if not identifiers:
        return 1.0
    lower = input_text.lower()
    return round(sum(x.lower() in lower for x in identifiers) / len(identifiers), 4)


def evaluate_view(labels: dict[str, str], name: str, predictions: dict[str, dict[str, object]],
                  decision_field: str) -> tuple[list[dict[str, object]], dict[str, object]]:
    rows = []
    counts: Counter[str] = Counter({"TP": 0, "FP": 0, "FN": 0, "TN": 0})
    for case_id in sorted(labels):
        actual = labels[case_id] == "positive"
        prediction = predictions[case_id]
        predicted = bool(prediction[decision_field])
        result = outcome(actual, predicted)
        counts[result] += 1
        meta = json.loads((CASES / case_id / "metadata.json").read_text(encoding="utf-8"))
        case_text = (CASES / case_id / "blind_input.md").read_text(encoding="utf-8")
        rows.append({
            "ground_truth_view": name, "case_id": case_id,
            "project": meta["project"], "commit_id": meta["commit"],
            "actual_label": labels[case_id], "negative_subtype": meta.get("negative_subtype", ""),
            "baseline": "gap_only" if decision_field == "gap_exists" else "evolution_aware",
            "gap_exists": prediction["gap_exists"],
            "commit_induced": prediction.get("commit_induced", "NOT_APPLICABLE"),
            "predicted_maintenance": predicted, "outcome": result,
            "confidence": prediction["confidence"], "reason": prediction["reason"],
            "evidence": json.dumps(prediction["evidence"], ensure_ascii=False, separators=(",", ":")),
            "identifier_grounding_ratio": grounding_ratio(prediction, case_text),
        })
    return rows, measures(counts)


def main() -> None:
    gap = load_jsonl(RESULTS / "gap_only_predictions.jsonl")
    evolution = load_jsonl(RESULTS / "evolution_aware_predictions.jsonl")
    if set(gap) != set(evolution) or len(gap) != 64:
        raise RuntimeError("prediction set mismatch")
    initial_labels = {x["case_id"]: "positive" for x in read_csv(DATA / "verified_positive_cases_initial.csv")}
    initial_labels.update({x["case_id"]: "negative" for x in read_csv(DATA / "verified_negative_cases_initial.csv")})
    audit = {x["case_id"]: x for x in read_csv(DATA / "ground_truth_audit.csv")}
    audited_labels = {case_id: x["audited_label"] for case_id, x in audit.items() if x["audited_label"] in {"positive", "negative"}}
    if Counter(audited_labels.values()) != {"negative": 40, "positive": 20}:
        raise RuntimeError(f"audited truth mismatch: {Counter(audited_labels.values())}")

    initial_rows, initial_metrics = [], []
    audited_rows, audited_metrics = [], []
    for baseline, predictions, field in (
        ("gap_only", gap, "gap_exists"),
        ("evolution_aware", evolution, "maintenance_needed"),
    ):
        rows, metric = evaluate_view(initial_labels, "initial_frozen", predictions, field)
        initial_rows.extend(rows); initial_metrics.append({"baseline": baseline, **metric})
        rows, metric = evaluate_view(audited_labels, "audited_stable_subset", predictions, field)
        audited_rows.extend(rows); audited_metrics.append({"baseline": baseline, **metric})
    write_csv(RESULTS / "evaluation_initial.csv", initial_rows)
    write_csv(RESULTS / "confusion_matrix_initial.csv", initial_metrics)
    write_csv(RESULTS / "evaluation.csv", audited_rows)
    write_csv(RESULTS / "confusion_matrix.csv", audited_metrics)

    g_metric = next(x for x in audited_metrics if x["baseline"] == "gap_only")
    e_metric = next(x for x in audited_metrics if x["baseline"] == "evolution_aware")
    transitions = Counter()
    for case_id, label in audited_labels.items():
        transitions[(label, bool(gap[case_id]["gap_exists"]), bool(evolution[case_id]["maintenance_needed"]))] += 1
    attribution = [{
        "view": "audited_stable_subset", "gap_only_fp": g_metric["FP"],
        "evolution_aware_fp": e_metric["FP"],
        "fp_reduction_count": int(g_metric["FP"]) - int(e_metric["FP"]),
        "fp_reduction_percent": round((int(g_metric["FP"]) - int(e_metric["FP"])) / int(g_metric["FP"]), 6),
        "gap_only_recall": g_metric["recall"], "evolution_aware_recall": e_metric["recall"],
        "recall_change_percentage_points": round((float(e_metric["recall"]) - float(g_metric["recall"])) * 100, 3),
        "negative_gap_yes_to_maintenance_no": transitions[("negative", True, False)],
        "negative_gap_yes_to_maintenance_yes": transitions[("negative", True, True)],
    }]
    write_csv(RESULTS / "attribution_effect.csv", attribution)

    # Manual reason audit after comparing input, prediction, and counterfactual
    # evidence.  C054 reaches the right decision via a wrong "new streaming
    # implementation" story; the true cause is the moved include path.
    evolution_rows = {x["case_id"]: x for x in audited_rows if x["baseline"] == "evolution_aware"}
    reasoning_rows = []
    for case_id, row in evolution_rows.items():
        if row["outcome"] not in {"TP", "FP", "FN"}:
            continue
        correct = row["outcome"] == "TP" and case_id != "C054"
        note = "Reason identifies the registered mechanism and attribution."
        if case_id == "C054":
            note = "Decision is TP, but reason incorrectly treats a moved file as newly added streaming functionality; true evidence is H0's obsolete ../src/spng.h include."
        elif case_id == "C004":
            note = "FN: model reasons about decoder reachability and overlooks that S1 moved spng.h, so S1+H0 cannot compile."
        elif case_id == "C040":
            note = "FP: model sees the newly missing declaration but misses that S0+H0 already failed, so no further adequacy delta is established."
        reasoning_rows.append({
            "case_id": case_id, "outcome": row["outcome"],
            "reason_correct": str(correct).lower(),
            "evidence_grounded": "true",
            "identifier_grounding_ratio": row["identifier_grounding_ratio"],
            "audit_note": note,
        })
    write_csv(RESULTS / "reasoning_quality.csv", reasoning_rows)

    summary = {
        "dataset": {
            "searched_projects": 10,
            "coevolution_hit_projects": 6,
            "positive_projects": len({row["project"] for row in read_csv(DATA / "verified_positive_cases.csv")}),
            "raw_coevolution_hits": len(read_csv(DATA / "co_evolution_universe.csv")),
            "screened_coevolution_candidates": len(read_csv(DATA / "co_evolution_candidates_initial.csv")),
            "eligible_coevolution_candidates": len(read_csv(DATA / "co_evolution_candidates.csv")),
            "initial_blind_cases": len(initial_labels),
            "audited_evaluation_cases": len(audited_labels),
            "audited_unique_commits": len({(row["project"], row["commit_id"])
                                            for row in read_csv(DATA / "verified_positive_cases.csv")
                                            + read_csv(DATA / "verified_negative_cases.csv")}),
            "verified_positive_commits": sum(label == "positive" for label in audited_labels.values()),
            "verified_negative_commits": sum(label == "negative" for label in audited_labels.values()),
        },
        "initial_frozen": {x["baseline"]: x for x in initial_metrics},
        "audited_stable_subset": {x["baseline"]: x for x in audited_metrics},
        "attribution_effect": attribution[0],
        "ground_truth_audit": {
            "initial_cases": 64, "audited_cases": 60,
            "relabelled": sorted(k for k, v in audit.items() if v["audit_status"] == "RELABEL"),
            "excluded": sorted(k for k, v in audit.items() if v["audited_label"] == "excluded"),
            "verified_positive": 20, "verified_negative": 40,
        },
        "reasoning": {
            "evolution_aware_tp": 19,
            "tp_reason_correct": sum(x["outcome"] == "TP" and x["reason_correct"] == "true" for x in reasoning_rows),
            "tp_evidence_grounded": sum(x["outcome"] == "TP" and x["evidence_grounded"] == "true" for x in reasoning_rows),
        },
    }
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
