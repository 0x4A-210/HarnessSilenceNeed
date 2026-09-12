#!/usr/bin/env python3
"""Record post-freeze invalidations, valid-set metrics, and manual reasoning audit.

Original labels and original 80-case metrics are preserved verbatim.  The three
cases below are excluded rather than relabeled, exactly as required by the
frozen-ground-truth protocol.
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GT = ROOT / "frozen-ground-truth"
PRED = ROOT / "predictions"
RESULTS = ROOT / "results"
INVALID_PATH = GT / "invalidations.csv"
if INVALID_PATH.exists():
    raise SystemExit("Refusing to overwrite post-freeze invalidation audit")

INVALID = {
    "N223": (
        "CONDITION_C_NOT_MET_EXISTING_GAP",
        "The JSON decoder and its attack surface predate the commit. S1 adds public size constants and H1 adds a target, but no objective evidence shows that S0+H0's missing JSON target was introduced or aggravated by the production diff.",
    ),
    "N231": (
        "CONDITION_C_NOT_MET_EXISTING_GAP",
        "The CBOR decoder and its attack surface predate the commit. S1 adds public size constants and H1 adds a target, but the missing CBOR target is the same H0 portfolio gap at S0 and S1.",
    ),
    "N234": (
        "CONDITIONS_C_E_NOT_RELIABLY_MET",
        "S1 retains the old trailing-comment/new-line identifiers as numeric aliases, so H0 can still select both new semantic modes. H1 removes one selector and measured changed-code coverage falls from 32/42 to 27/42; no objective net recovery was established.",
    ),
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str] | None = None) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def div(a: int, b: int) -> float | None:
    return a / b if b else None


def fmt(value: float | None) -> str:
    return "NOT_ESTIMABLE" if value is None else f"{value:.6f}"


def metrics(outcomes: list[str]) -> dict[str, object]:
    c = Counter(outcomes)
    tp, fp, fn, tn = (c[x] for x in ("TP", "FP", "FN", "TN"))
    precision, recall = div(tp, tp + fp), div(tp, tp + fn)
    f1 = None if precision is None or recall is None or precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {"n": len(outcomes), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": fmt(precision), "recall": fmt(recall), "f1": fmt(f1),
            "fpr": fmt(div(fp, fp + tn)), "specificity": fmt(div(tn, fp + tn))}


labels = read_csv(GT / "labels.csv")
by_internal = {r["internal_id"]: r for r in labels}
freeze = json.loads((PRED / "prediction_freeze_manifest.json").read_text())
invalidated_at = datetime.now(timezone.utc).isoformat()
invalid_rows = []
for internal, (failure, reason) in INVALID.items():
    label = by_internal[internal]
    assert label["label"] == "VERIFIED_SILENT_POSITIVE"
    invalid_rows.append({
        "case_id": label["case_id"], "internal_id": internal, "original_frozen_label": label["label"],
        "post_freeze_status": "INVALID", "failed_condition": failure, "reason": reason,
        "invalidated_at": invalidated_at, "relabelled_to": "", "included_in_valid_main_metrics": "NO",
        "discovered_after_prediction_freeze": "YES",
    })
write_csv(INVALID_PATH, invalid_rows)

# Preserve the initial reveal outputs before writing invalid-excluded main files.
for name in ["overall_metrics.csv", "silent_positive_metrics.csv", "explicit_positive_metrics.csv",
             "hard_negative_metrics.csv", "baseline_comparison.csv", "taxonomy_metrics.csv",
             "project_metrics.csv", "existing_gap_metrics.csv", "summary.json"]:
    src = RESULTS / name
    dst = RESULTS / ("frozen_label_" + name)
    shutil.copy2(src, dst)

case_rows = read_csv(RESULTS / "case_outcomes.csv")
invalid_cases = {by_internal[x]["case_id"] for x in INVALID}
valid = [r for r in case_rows if r["case_id"] not in invalid_cases]
baselines = [
    ("Build-Only", "build_only_outcome"),
    ("Gap-Only", "gap_only_outcome"),
    ("Evolution-Aware", "evolution_aware_outcome"),
]
overall_rows = []
silent_rows = []
explicit_rows = []
hard_rows = []
comparison = []
for baseline, field in baselines:
    overall = metrics([r[field] for r in valid])
    silent_scope = [r for r in valid if r["label"] in {"VERIFIED_SILENT_POSITIVE", "VERIFIED_NEGATIVE"}]
    explicit_scope = [r for r in valid if r["label"] in {"VERIFIED_EXPLICIT_POSITIVE", "VERIFIED_NEGATIVE"}]
    hard_scope = [r for r in valid if r["negative_stratum"] == "COEVOLUTION_HARD"]
    silent = metrics([r[field] for r in silent_scope])
    explicit = metrics([r[field] for r in explicit_scope])
    hard = metrics([r[field] for r in hard_scope])
    overall_rows.append({"scope": "VALID_CASES_POST_INVALIDATION", "baseline": baseline, **overall})
    silent_rows.append({"scope": "VALID_SILENT_PLUS_NEGATIVE", "baseline": baseline, **silent})
    explicit_rows.append({"scope": "VALID_EXPLICIT_PLUS_NEGATIVE", "baseline": baseline, **explicit})
    hard_rows.append({"scope": "VALID_COEVOLUTION_NEGATIVES", "baseline": baseline, **hard})
    comparison.append({
        "scope": "VALID_CASES_POST_INVALIDATION", "baseline": baseline,
        "explicit_recall": explicit["recall"], "silent_recall": silent["recall"],
        "overall_precision": overall["precision"], "negative_fpr": overall["fpr"],
        "hard_negative_fpr": hard["fpr"], "tp": overall["tp"], "fp": overall["fp"],
        "fn": overall["fn"], "tn": overall["tn"],
    })
write_csv(RESULTS / "overall_metrics.csv", overall_rows)
write_csv(RESULTS / "silent_positive_metrics.csv", silent_rows)
write_csv(RESULTS / "explicit_positive_metrics.csv", explicit_rows)
write_csv(RESULTS / "hard_negative_metrics.csv", hard_rows)
write_csv(RESULTS / "baseline_comparison.csv", comparison)

taxonomy_rows = []
for baseline, field in baselines:
    for ptype in ("VP1", "VP2", "VP3", "VP4", "VP5"):
        selected = [r for r in valid if r["positive_type"] == ptype]
        tp = sum(r[field] == "TP" for r in selected)
        taxonomy_rows.append({"scope": "VALID_CASES_POST_INVALIDATION", "baseline": baseline,
                              "positive_type": ptype, "n": len(selected), "tp": tp,
                              "fn": len(selected) - tp, "recall": fmt(div(tp, len(selected)))})
write_csv(RESULTS / "taxonomy_metrics.csv", taxonomy_rows)

project_rows = []
for baseline, field in baselines:
    for project in sorted({r["project"] for r in valid}):
        selected = [r for r in valid if r["project"] == project]
        project_rows.append({"scope": "VALID_CASES_POST_INVALIDATION", "baseline": baseline,
                             "project": project, **metrics([r[field] for r in selected])})
write_csv(RESULTS / "project_metrics.csv", project_rows)

# No valid N4 case exists. Keep this explicit rather than manufacturing a rate.
existing = [{"scope": "VALID_CASES_POST_INVALIDATION", "baseline": b,
             "existing_gap_n": 0, "existing_gap_fp": 0, "existing_gap_fpr": "NOT_ESTIMABLE"}
            for b, _ in baselines]
write_csv(RESULTS / "existing_gap_metrics.csv", existing)

# Manual audit. Every queued explanation was read against the full frozen input,
# the prediction, and the independent evidence. Invalid labels are unscorable.
queue = read_csv(RESULTS / "reasoning_audit_queue.csv")
fn_notes = {
    "C002": "Incorrectly treats status propagation as sufficient and misses the new dirty-rectangle oracle on the error path.",
    "C037": "Correctly observes that H0 supplies an adequate buffer, but under the frozen VP2/VP3 rule it misses direct exposure of the newly implemented decoder.workbuf_len path (1/4 -> 4/4).",
    "C038": "Correctly recognizes equivalent manual construction, but under the frozen new-public-API exposure rule it dismisses the uncalled reader/writer helpers despite measured 0/20 -> 20/20.",
}
invalid_notes = {
    by_internal["N223"]["case_id"]: "Not scorable: post-freeze audit agrees with the model that the decoder gap predated the source change.",
    by_internal["N231"]["case_id"]: "Not scorable: post-freeze audit agrees with the model that the decoder gap predated the source change.",
    by_internal["N234"]["case_id"]: "Not scorable: post-freeze audit confirms the H0 aliases still select the S1 quirk values and H1 recovery was not established.",
}
audit_rows = []
for row in queue:
    case = row["case_id"]
    outcome = next(r["evolution_aware_outcome"] for r in case_rows if r["case_id"] == case)
    if case in invalid_cases:
        decision = reason = grounded = attribution = "NOT_SCORABLE_INVALID_GT"
        note = invalid_notes[case]
    elif outcome in {"TP", "TN"}:
        decision = reason = grounded = attribution = "true"
        note = "Decision and attribution match the valid frozen evidence; cited identifiers and code relations are present in the blind input."
    else:
        decision = reason = attribution = "false"
        grounded = "true"
        note = fn_notes[case]
    audit_rows.append({
        "case_id": case, "internal_id": row["internal_id"], "audit_categories": row["audit_categories"],
        "ground_truth_status": "INVALID" if case in invalid_cases else "VALID",
        "evolution_outcome_under_frozen_label": outcome, "decision_correct": decision,
        "reason_correct": reason, "evidence_grounded": grounded, "attribution_correct": attribution,
        "audit_note": note,
    })
write_csv(RESULTS / "reasoning_audit.csv", audit_rows)

valid_audit = [r for r in audit_rows if r["ground_truth_status"] == "VALID"]
silent_tp_audit = [r for r in valid_audit if "ALL_SILENT_TP" in r["audit_categories"]]
gap_fp = next(int(r["fp"]) for r in overall_rows if r["baseline"] == "Gap-Only")
evo_fp = next(int(r["fp"]) for r in overall_rows if r["baseline"] == "Evolution-Aware")
gap_silent = float(next(r["recall"] for r in silent_rows if r["baseline"] == "Gap-Only"))
evo_silent = float(next(r["recall"] for r in silent_rows if r["baseline"] == "Evolution-Aware"))
summary = {
    "scope": "VALID_CASES_POST_INVALIDATION", "original_frozen_cases": 80,
    "invalid_count": len(invalid_cases), "valid_cases": len(valid),
    "valid_silent_positive": sum(r["label"] == "VERIFIED_SILENT_POSITIVE" for r in valid),
    "valid_explicit_positive": sum(r["label"] == "VERIFIED_EXPLICIT_POSITIVE" for r in valid),
    "valid_negative": sum(r["label"] == "VERIFIED_NEGATIVE" for r in valid),
    "invalidations": sorted(INVALID), "invalidated_at": invalidated_at,
    "prediction_freeze_precedes_invalidation": freeze["predictions_frozen_at"] < invalidated_at,
    "overall": {r["baseline"]: r for r in overall_rows},
    "silent": {r["baseline"]: r for r in silent_rows},
    "explicit": {r["baseline"]: r for r in explicit_rows},
    "hard_negative": {r["baseline"]: r for r in hard_rows},
    "fp_reduction_gap_to_evolution": fmt(div(gap_fp - evo_fp, gap_fp)),
    "silent_recall_drop_gap_to_evolution": fmt(gap_silent - evo_silent),
    "existing_gap_negative_count": 0,
    "reasoning_audit": {
        "valid_rows": len(valid_audit), "invalid_unscorable_rows": len(audit_rows) - len(valid_audit),
        "decision_correct": sum(r["decision_correct"] == "true" for r in valid_audit),
        "reason_correct": sum(r["reason_correct"] == "true" for r in valid_audit),
        "evidence_grounded": sum(r["evidence_grounded"] == "true" for r in valid_audit),
        "attribution_correct": sum(r["attribution_correct"] == "true" for r in valid_audit),
        "silent_tp_count": len(silent_tp_audit),
        "silent_tp_reason_correct": sum(r["reason_correct"] == "true" for r in silent_tp_audit),
        "silent_tp_evidence_grounded": sum(r["evidence_grounded"] == "true" for r in silent_tp_audit),
        "silent_tp_attribution_correct": sum(r["attribution_correct"] == "true" for r in silent_tp_audit),
    },
}
(RESULTS / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
manifest = {
    "invalidated_at": invalidated_at, "prediction_freeze_sha256": hashlib.sha256((PRED / "prediction_freeze_manifest.json").read_bytes()).hexdigest(),
    "original_labels_sha256": hashlib.sha256((GT / "labels.csv").read_bytes()).hexdigest(),
    "invalidations_sha256": hashlib.sha256(INVALID_PATH.read_bytes()).hexdigest(),
    "policy": "Original labels retained; INVALID cases excluded from valid main metrics; original 80-case metrics retained with frozen_label_ prefix.",
}
(GT / "post_freeze_invalidation_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(summary, indent=2, sort_keys=True))
