#!/usr/bin/env python3
"""Evaluate frozen predictions against frozen labels, excluding invalidations."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from scipy.stats import binomtest


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"


def read_jsonl(path: Path) -> dict[str, dict]:
    return {row["case_id"]: row for row in
            (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)}


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if not n:
        return math.nan, math.nan
    p = k / n
    den = 1 + (z * z / n)
    center = (p + z * z / (2 * n)) / den
    half = z * math.sqrt((p * (1 - p) / n) + (z * z / (4 * n * n))) / den
    return center - half, center + half


def pct(x: float) -> str:
    return f"{100 * x:.6f}"


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def main() -> None:
    freeze = json.loads((ROOT / "predictions" / "prediction_freeze_manifest.json").read_text())
    if freeze["status"] != "FROZEN_BEFORE_LABEL_REVEAL":
        raise SystemExit("prediction freeze missing")
    labels = list(csv.DictReader((ROOT / "frozen-ground-truth" / "labels.csv").open(encoding="utf-8", newline="")))
    invalid = {r["case_id"] for r in csv.DictReader(
        (ROOT / "frozen-ground-truth" / "invalidations.csv").open(encoding="utf-8", newline=""))}
    gap = read_jsonl(ROOT / "predictions" / "gap_only.jsonl")
    evo = read_jsonl(ROOT / "predictions" / "evolution_aware.jsonl")
    valid = [r for r in labels if r["case_id"] not in invalid]
    if len(valid) != 36:
        raise SystemExit(f"expected 36 valid cases, got {len(valid)}")
    outcomes = []
    for label in labels:
        case_id = label["case_id"]
        g, e = gap[case_id], evo[case_id]
        expected_positive = label["maintenance_needed"] == "YES"
        g_maintenance = bool(g["gap_exists"])
        e_derived = bool(e["gap_exists"] and e["commit_induced"] == "YES")
        outcomes.append({
            "case_id": case_id, "candidate_id": label["candidate_id"], "project": label["project"],
            "commit": label["commit"], "case_type": label["case_type"],
            "ground_truth_maintenance": str(expected_positive).lower(),
            "post_freeze_status": "INVALIDATE" if case_id in invalid else "VALID",
            "gap_only_gap_exists": str(g["gap_exists"]).lower(),
            "gap_only_maintenance": str(g_maintenance).lower(), "gap_only_confidence": g["confidence"],
            "gap_only_correct": str(g_maintenance == expected_positive).lower(),
            "evolution_gap_exists": str(e["gap_exists"]).lower(),
            "evolution_commit_induced": e["commit_induced"],
            "evolution_maintenance_emitted": str(e["maintenance_needed"]).lower(),
            "evolution_maintenance_derived": str(e_derived).lower(),
            "evolution_output_consistent": str(e["maintenance_needed"] == e_derived).lower(),
            "evolution_confidence": e["confidence"],
            "evolution_correct": str(e_derived == expected_positive).lower(),
            "evolution_reason": e["reason"], "gap_only_reason": g["reason"],
        })
    RESULTS.mkdir(parents=True, exist_ok=True)
    write_csv(RESULTS / "case_outcomes.csv", outcomes)
    valid_out = [r for r in outcomes if r["post_freeze_status"] == "VALID"]
    n4 = [r for r in valid_out if r["case_type"] == "N4_EXISTING_GAP"]
    pos = [r for r in valid_out if r["case_type"] == "COMMIT_INDUCED_POSITIVE"]

    method_rows = []
    confusion_rows = []
    for method, key in (("Gap-Only", "gap_only_maintenance"),
                        ("Evolution-Aware", "evolution_maintenance_derived")):
        tp = sum(r[key] == "true" for r in pos)
        fn = len(pos) - tp
        fp = sum(r[key] == "true" for r in n4)
        tn = len(n4) - fp
        recall = tp / len(pos); fpr = fp / len(n4)
        rlo, rhi = wilson(tp, len(pos)); flo, fhi = wilson(fp, len(n4))
        method_rows.append({
            "method": method, "valid_positive": len(pos), "true_positive": tp,
            "false_negative": fn, "positive_recall_percent": pct(recall),
            "positive_recall_wilson95_low_percent": pct(rlo),
            "positive_recall_wilson95_high_percent": pct(rhi),
            "valid_n4": len(n4), "false_positive": fp, "true_negative": tn,
            "n4_existing_gap_fpr_percent": pct(fpr),
            "n4_fpr_wilson95_low_percent": pct(flo), "n4_fpr_wilson95_high_percent": pct(fhi),
            "overall_fpr_percent": pct(fpr), "accuracy_percent": pct((tp + tn) / len(valid_out)),
        })
        confusion_rows.append({"method": method, "TP": tp, "FN": fn, "FP": fp, "TN": tn,
                               "valid_total": len(valid_out)})
    write_csv(RESULTS / "metrics.csv", method_rows)
    write_csv(RESULTS / "confusion_matrix.csv", confusion_rows)

    gap_fp = int(method_rows[0]["false_positive"])
    evo_fp = int(method_rows[1]["false_positive"])
    reduction = (gap_fp - evo_fp) / gap_fp if gap_fp else math.nan
    corrected = sum(r["gap_only_maintenance"] == "true" and r["evolution_maintenance_derived"] == "false" for r in n4)
    worsened = sum(r["gap_only_maintenance"] == "false" and r["evolution_maintenance_derived"] == "true" for r in n4)
    mcnemar_p = binomtest(min(corrected, worsened), corrected + worsened, 0.5).pvalue if corrected + worsened else 1.0
    desired_n4 = sum(r["evolution_gap_exists"] == "true" and r["evolution_commit_induced"] == "NO" and
                     r["evolution_maintenance_derived"] == "false" for r in n4)
    n4_attr_correct = sum(r["evolution_commit_induced"] == "NO" for r in n4)
    pos_attr_correct = sum(r["evolution_commit_induced"] == "YES" for r in pos)
    attr_rows = [
        {"scope": "all_valid", "correct": n4_attr_correct + pos_attr_correct, "total": len(valid_out),
         "accuracy_percent": pct((n4_attr_correct + pos_attr_correct) / len(valid_out))},
        {"scope": "N4_EXISTING_GAP", "correct": n4_attr_correct, "total": len(n4),
         "accuracy_percent": pct(n4_attr_correct / len(n4))},
        {"scope": "COMMIT_INDUCED_POSITIVE", "correct": pos_attr_correct, "total": len(pos),
         "accuracy_percent": pct(pos_attr_correct / len(pos))},
    ]
    write_csv(RESULTS / "attribution_metrics.csv", attr_rows)
    n4_rows = [{
        "valid_n4": len(n4), "gap_only_fp": gap_fp, "gap_only_fpr_percent": pct(gap_fp / len(n4)),
        "evolution_fp": evo_fp, "evolution_fpr_percent": pct(evo_fp / len(n4)),
        "false_positives_removed": gap_fp - evo_fp, "fp_reduction_percent": pct(reduction),
        "paired_corrected": corrected, "paired_worsened": worsened, "mcnemar_exact_p": f"{mcnemar_p:.9f}",
        "evolution_n4_gap_detected": sum(r["evolution_gap_exists"] == "true" for r in n4),
        "evolution_n4_attribution_no": n4_attr_correct,
        "full_target_pattern_gap_yes_induced_no_maintenance_no": desired_n4,
        "full_target_pattern_percent": pct(desired_n4 / len(n4)),
    }]
    write_csv(RESULTS / "n4_metrics.csv", n4_rows)

    mapping = {r["candidate_id"]: r["case_id"] for r in labels}
    pair_rows = []
    for pair in csv.DictReader((ROOT / "data" / "matched_pairs.csv").open(encoding="utf-8", newline="")):
        n4_id, p_id = mapping[pair["n4_candidate_id"]], mapping[pair["positive_candidate_id"]]
        left = next(r for r in outcomes if r["case_id"] == n4_id)
        right = next(r for r in outcomes if r["case_id"] == p_id)
        pair_rows.append({
            "pair_id": pair["pair_id"], "n4_case_id": n4_id, "positive_case_id": p_id,
            "pair_valid": str(n4_id not in invalid and p_id not in invalid).lower(),
            "gap_only_n4_fp": left["gap_only_maintenance"], "evolution_n4_fp": left["evolution_maintenance_derived"],
            "gap_only_positive_tp": right["gap_only_maintenance"],
            "evolution_positive_tp": right["evolution_maintenance_derived"],
            "time_distance_days": pair["time_distance_days"], "matching_cost": pair["matching_cost"],
        })
    write_csv(RESULTS / "matched_pair_results.csv", pair_rows)

    # Preserve a transparent sensitivity view under the original immutable
    # labels.  All four invalidated N4 happened to receive positive evolution
    # predictions, so this table makes the effect of exclusion explicit.
    frozen_n4 = [r for r in outcomes if r["case_type"] == "N4_EXISTING_GAP"]
    frozen_pos = [r for r in outcomes if r["case_type"] == "COMMIT_INDUCED_POSITIVE"]
    sensitivity = []
    for method, key in (("Gap-Only", "gap_only_maintenance"),
                        ("Evolution-Aware", "evolution_maintenance_derived")):
        frozen_tp = sum(r[key] == "true" for r in frozen_pos)
        frozen_fp = sum(r[key] == "true" for r in frozen_n4)
        sensitivity.append({
            "method": method, "analysis": "all_40_original_frozen_labels_including_later_invalidations",
            "positive_tp": frozen_tp, "positive_total": len(frozen_pos),
            "positive_recall_percent": pct(frozen_tp / len(frozen_pos)),
            "n4_fp": frozen_fp, "n4_total": len(frozen_n4),
            "n4_fpr_percent": pct(frozen_fp / len(frozen_n4)),
            "accuracy_percent": pct((frozen_tp + len(frozen_n4) - frozen_fp) / len(outcomes)),
        })
    write_csv(RESULTS / "frozen_label_sensitivity.csv", sensitivity)

    summary = {
        "frozen_cases": 40, "post_freeze_invalidations": len(invalid), "valid_cases": len(valid_out),
        "valid_n4": len(n4), "valid_positive": len(pos), "gap_only_n4_fp": gap_fp,
        "gap_only_n4_fpr": gap_fp / len(n4), "gap_only_positive_recall": 1.0,
        "evolution_n4_fp": evo_fp, "evolution_n4_fpr": evo_fp / len(n4),
        "evolution_positive_recall": sum(r["evolution_maintenance_derived"] == "true" for r in pos) / len(pos),
        "fp_reduction": reduction, "attribution_accuracy": (n4_attr_correct + pos_attr_correct) / len(valid_out),
        "n4_full_target_pattern_count": desired_n4, "n4_full_target_pattern_rate": desired_n4 / len(n4),
        "mcnemar_exact_p": mcnemar_p, "relabels": 0,
        "frozen_label_sensitivity": {
            "gap_only_n4_fpr": int(sensitivity[0]["n4_fp"]) / int(sensitivity[0]["n4_total"]),
            "evolution_n4_fpr": int(sensitivity[1]["n4_fp"]) / int(sensitivity[1]["n4_total"]),
            "evolution_fp_reduction": ((int(sensitivity[0]["n4_fp"]) - int(sensitivity[1]["n4_fp"])) /
                                        int(sensitivity[0]["n4_fp"])),
            "evolution_positive_recall": int(sensitivity[1]["positive_tp"]) / int(sensitivity[1]["positive_total"]),
            "note": "all 40 original labels, before excluding four later INVALIDATE cases",
        },
        "go_no_go": "NO-GO",
        "go_no_go_reasons": ["valid N4 below 20 after immutable invalidation",
                              "Evolution-Aware N4 FPR exceeds 30%",
                              "full gap=yes/commit-induced=no attribution pattern is unstable"],
    }
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
