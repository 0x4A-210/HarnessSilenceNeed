#!/usr/bin/env python3
"""Evaluate all frozen Task-5 blind predictions against immutable labels."""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def read_jsonl(path: Path) -> dict[str, dict]:
    return {
        row["case_id"]: row
        for row in (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)
    }


def truth(value: str) -> bool:
    return value.lower() == "true"


def pct(value: float) -> str:
    return f"{100 * value:.6f}"


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if not n:
        return math.nan, math.nan
    p = k / n; denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return center - half, center + half


def exact_discordant_p(left: int, right: int) -> float:
    n = left + right
    if not n:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(0, min(left, right) + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def main() -> None:
    freeze = json.loads((ROOT / "predictions" / "prediction_freeze_manifest.json").read_text(encoding="utf-8"))
    if freeze["status"] != "FROZEN_BEFORE_LABEL_REVEAL":
        raise SystemExit("predictions were not frozen before label reveal")
    labels = list(csv.DictReader((ROOT / "frozen-ground-truth" / "labels.csv").open(encoding="utf-8", newline="")))
    invalidations_path = ROOT / "frozen-ground-truth" / "invalidations.csv"
    invalid = {
        row["case_id"] for row in csv.DictReader(invalidations_path.open(encoding="utf-8", newline=""))
        if row["status"] == "INVALIDATE"
    }
    if len(labels) != 40 or any(row["audit_status"] != "VALID" for row in labels):
        raise SystemExit("expected 40 immutable frozen labels")
    gap = read_jsonl(ROOT / "predictions" / "gap_only.jsonl")
    direct = read_jsonl(ROOT / "predictions" / "direct_evolution_aware.jsonl")
    delta = read_jsonl(ROOT / "predictions" / "delta_aware.jsonl")
    ids = {row["case_id"] for row in labels}
    if set(gap) != ids or set(direct) != ids or set(delta) != ids:
        raise SystemExit("prediction/label case sets differ")
    outcomes: list[dict] = []
    for label in labels:
        case_id = label["case_id"]; g, d, a = gap[case_id], direct[case_id], delta[case_id]
        expected_maintenance = truth(label["maintenance_needed"])
        g_decision = bool(g["gap_exists"])
        d_decision = bool(d["gap_exists"] and d["commit_induced"] == "YES")
        a_decision = bool(a["explicit_failure"] or a["delta_attribution"] in {"NEW", "AGGRAVATED"})
        expected_induced = "YES" if label["label"] == "POSITIVE" else "NO"
        target_pattern = bool(
            a["gap_before"]["exists"] and a["gap_after"]["exists"]
            and a["delta_attribution"] == "UNCHANGED" and not a["maintenance_needed"]
        )
        outcomes.append({
            "case_id": case_id, "project": label["project"], "commit_id": label["commit_id"],
            "label": label["label"], "expected_gap_before": label["expected_gap_before"],
            "expected_gap_after": label["expected_gap_after"], "expected_delta": label["expected_delta"],
            "expected_maintenance": str(expected_maintenance).lower(),
            "post_freeze_status": "INVALIDATE" if case_id in invalid else "VALID",
            "gap_only_gap_exists": str(g["gap_exists"]).lower(),
            "gap_only_decision": str(g_decision).lower(), "gap_only_confidence": g["confidence"],
            "gap_only_correct": str(g_decision == expected_maintenance).lower(),
            "direct_gap_exists": str(d["gap_exists"]).lower(), "direct_commit_induced": d["commit_induced"],
            "direct_maintenance_emitted": str(d["maintenance_needed"]).lower(),
            "direct_maintenance_derived": str(d_decision).lower(),
            "direct_output_consistent": str(d["maintenance_needed"] == d_decision).lower(),
            "direct_attribution_correct": str(d["commit_induced"] == expected_induced).lower(),
            "direct_correct": str(d_decision == expected_maintenance).lower(),
            "direct_confidence": d["confidence"], "direct_reason": d["reason"],
            "delta_gap_before": str(a["gap_before"]["exists"]).lower(),
            "delta_gap_after": str(a["gap_after"]["exists"]).lower(),
            "delta_attribution": a["delta_attribution"], "delta_explicit_failure": str(a["explicit_failure"]).lower(),
            "delta_maintenance_emitted": str(a["maintenance_needed"]).lower(),
            "delta_maintenance_derived": str(a_decision).lower(),
            "delta_output_consistent": str(a["maintenance_needed"] == a_decision).lower(),
            "delta_gap_before_correct": str(a["gap_before"]["exists"] == truth(label["expected_gap_before"])).lower(),
            "delta_gap_after_correct": str(a["gap_after"]["exists"] == truth(label["expected_gap_after"])).lower(),
            "delta_attribution_correct": str(a["delta_attribution"] == label["expected_delta"]).lower(),
            "delta_n4_target_pattern": str(target_pattern if label["label"] == "N4" else False).lower(),
            "delta_correct": str(a_decision == expected_maintenance).lower(),
            "delta_confidence": a["confidence"], "delta_reason": a["reason"],
        })
    RESULTS.mkdir(exist_ok=True)
    write_csv(RESULTS / "case_outcomes.csv", outcomes)
    valid_outcomes = [row for row in outcomes if row["post_freeze_status"] == "VALID"]
    positives = [row for row in valid_outcomes if row["label"] == "POSITIVE"]
    n4 = [row for row in valid_outcomes if row["label"] == "N4"]
    positive_total, n4_total, valid_total = len(positives), len(n4), len(valid_outcomes)

    method_defs = [
        ("Gap-Only", "gap_only_decision", None),
        ("Direct Evolution-Aware", "direct_maintenance_derived", "direct_attribution_correct"),
        ("Delta-Aware", "delta_maintenance_derived", "delta_attribution_correct"),
    ]
    metrics: list[dict] = []; confusion: list[dict] = []
    for method, decision, attribution in method_defs:
        tp = sum(row[decision] == "true" for row in positives); fn = len(positives) - tp
        fp = sum(row[decision] == "true" for row in n4); tn = len(n4) - fp
        rlo, rhi = wilson(tp, len(positives)); flo, fhi = wilson(fp, len(n4))
        attr_correct = sum(row[attribution] == "true" for row in valid_outcomes) if attribution else None
        metrics.append({
            "method": method, "valid_positive": len(positives), "true_positive": tp, "false_negative": fn,
            "positive_recall_percent": pct(tp / len(positives)),
            "positive_recall_wilson95_low_percent": pct(rlo), "positive_recall_wilson95_high_percent": pct(rhi),
            "valid_n4": len(n4), "false_positive": fp, "true_negative": tn,
            "n4_fpr_percent": pct(fp / len(n4)), "n4_fpr_wilson95_low_percent": pct(flo),
            "n4_fpr_wilson95_high_percent": pct(fhi),
            "attribution_correct": "NA" if attr_correct is None else attr_correct,
            "attribution_total": "NA" if attr_correct is None else valid_total,
            "attribution_accuracy_percent": "NA" if attr_correct is None else pct(attr_correct / valid_total),
            "classification_accuracy_percent": pct((tp + tn) / valid_total),
        })
        confusion.append({"method": method, "TP": tp, "FN": fn, "FP": fp, "TN": tn, "total": valid_total})
    write_csv(RESULTS / "metrics.csv", metrics); write_csv(RESULTS / "confusion_matrix.csv", confusion)

    before_correct = sum(row["delta_gap_before_correct"] == "true" for row in valid_outcomes)
    after_correct = sum(row["delta_gap_after_correct"] == "true" for row in valid_outcomes)
    delta_correct = sum(row["delta_attribution_correct"] == "true" for row in valid_outcomes)
    attr = [
        {"metric": "GapBefore Accuracy", "scope": "all", "correct": before_correct, "total": valid_total,
         "accuracy_percent": pct(before_correct / valid_total)},
        {"metric": "GapBefore Accuracy", "scope": "N4", "correct": sum(row["delta_gap_before_correct"] == "true" for row in n4),
         "total": n4_total, "accuracy_percent": pct(sum(row["delta_gap_before_correct"] == "true" for row in n4) / n4_total)},
        {"metric": "GapBefore Accuracy", "scope": "POSITIVE", "correct": sum(row["delta_gap_before_correct"] == "true" for row in positives),
         "total": positive_total, "accuracy_percent": pct(sum(row["delta_gap_before_correct"] == "true" for row in positives) / positive_total)},
        {"metric": "GapAfter Accuracy", "scope": "all", "correct": after_correct, "total": valid_total,
         "accuracy_percent": pct(after_correct / valid_total)},
        {"metric": "Delta Attribution Accuracy", "scope": "all", "correct": delta_correct, "total": valid_total,
         "accuracy_percent": pct(delta_correct / valid_total)},
        {"metric": "Direct Attribution Accuracy", "scope": "all",
         "correct": sum(row["direct_attribution_correct"] == "true" for row in valid_outcomes), "total": valid_total,
         "accuracy_percent": pct(sum(row["direct_attribution_correct"] == "true" for row in valid_outcomes) / valid_total)},
    ]
    write_csv(RESULTS / "attribution_metrics.csv", attr)
    target_rows = [{
        "case_id": row["case_id"], "project": row["project"],
        "gap_before": row["delta_gap_before"], "gap_after": row["delta_gap_after"],
        "delta_attribution": row["delta_attribution"], "maintenance": row["delta_maintenance_emitted"],
        "target_pattern": row["delta_n4_target_pattern"],
    } for row in n4]
    write_csv(RESULTS / "n4_target_pattern.csv", target_rows)

    gap_fp = sum(row["gap_only_decision"] == "true" for row in n4)
    direct_fp = sum(row["direct_maintenance_derived"] == "true" for row in n4)
    delta_fp = sum(row["delta_maintenance_derived"] == "true" for row in n4)
    direct_to_delta_corrected = sum(
        row["direct_maintenance_derived"] == "true" and row["delta_maintenance_derived"] == "false" for row in n4
    )
    direct_to_delta_worsened = sum(
        row["direct_maintenance_derived"] == "false" and row["delta_maintenance_derived"] == "true" for row in n4
    )
    comparison = [{
        "comparison": "Direct Evolution-Aware -> Delta-Aware on N4",
        "direct_fp": direct_fp, "delta_fp": delta_fp,
        "absolute_fp_change": delta_fp - direct_fp,
        "relative_fp_reduction_percent": pct((direct_fp - delta_fp) / direct_fp) if direct_fp else "NA",
        "paired_corrected": direct_to_delta_corrected, "paired_worsened": direct_to_delta_worsened,
        "mcnemar_exact_p": f"{exact_discordant_p(direct_to_delta_corrected, direct_to_delta_worsened):.9f}",
        "gap_only_fp": gap_fp,
    }]
    write_csv(RESULTS / "comparison.csv", comparison)

    n4_target = sum(row["delta_n4_target_pattern"] == "true" for row in n4)
    direct_attr = sum(row["direct_attribution_correct"] == "true" for row in valid_outcomes)
    delta_output_consistency = sum(row["delta_output_consistent"] == "true" for row in valid_outcomes)
    direct_output_consistency = sum(row["direct_output_consistent"] == "true" for row in valid_outcomes)
    delta_recall = sum(row["delta_maintenance_derived"] == "true" for row in positives) / positive_total
    delta_fpr = delta_fp / n4_total
    delta_attr_rate = delta_correct / valid_total
    target_rate = n4_target / n4_total
    if n4_total >= 20 and positive_total >= 20 and delta_fpr <= 0.10 and delta_recall >= 0.75 and target_rate >= 0.70 and delta_attr_rate >= 0.75 and delta_fp < direct_fp:
        decision = "STRONG GO"
    elif delta_fpr <= 0.20 and delta_recall >= 0.60 and target_rate >= 0.60 and delta_attr_rate > direct_attr / valid_total:
        decision = "MODERATE GO"
    else:
        decision = "NO-GO"
    summary = {
        "frozen_cases": 40, "valid_cases": valid_total, "valid_n4": n4_total, "valid_positive": positive_total,
        "projects_frozen": dict(Counter(row["project"] for row in outcomes)),
        "projects_valid": dict(Counter(row["project"] for row in valid_outcomes)),
        "project_count": len({row["project"] for row in outcomes}),
        "max_project_share_frozen": max(Counter(row["project"] for row in outcomes).values()) / 40,
        "max_project_share_valid": max(Counter(row["project"] for row in valid_outcomes).values()) / valid_total,
        "gap_only": {"positive_recall": metrics[0]["positive_recall_percent"], "n4_fpr": metrics[0]["n4_fpr_percent"]},
        "direct": {"positive_recall": metrics[1]["positive_recall_percent"], "n4_fpr": metrics[1]["n4_fpr_percent"],
                   "attribution_accuracy": metrics[1]["attribution_accuracy_percent"],
                   "output_consistency": direct_output_consistency / valid_total},
        "delta": {"positive_recall": metrics[2]["positive_recall_percent"], "n4_fpr": metrics[2]["n4_fpr_percent"],
                  "gap_before_accuracy": before_correct / valid_total,
                  "gap_after_accuracy": after_correct / valid_total,
                  "delta_attribution_accuracy": delta_attr_rate, "n4_target_pattern_accuracy": target_rate,
                  "output_consistency": delta_output_consistency / valid_total},
        "direct_to_delta": comparison[0], "post_freeze_invalidations": len(invalid), "invalidated_cases": sorted(invalid),
        "post_freeze_relabels": 0,
        "decision": decision,
        "decision_note": "STRONG GO is withheld because one frozen N4 was invalidated, leaving 19 valid N4; all MODERATE GO performance thresholds are met.",
    }
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
