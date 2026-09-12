#!/usr/bin/env python3
"""Read-only integrity and completeness validator for the task-3 artifact."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
csv.field_size_limit(sys.maxsize)
errors: list[str] = []
checks = 0


def check(condition: bool, message: str) -> None:
    global checks
    checks += 1
    if not condition:
        errors.append(message)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


required = [
    "README.md", "NEXT_STEP.md", "data/new_candidates.csv", "data/candidate_audit.csv", "data/excluded_cases.csv",
    "ground-truth/build_runtime_validation.csv", "ground-truth/changed_code_coverage.csv",
    "ground-truth/reachability_validation.csv", "ground-truth/state_config_validation.csv",
    "frozen-ground-truth/labels.csv", "frozen-ground-truth/silent_positive.csv",
    "frozen-ground-truth/explicit_positive.csv", "frozen-ground-truth/negative.csv",
    "frozen-ground-truth/audit_manifest.json", "frozen-ground-truth/invalidations.csv",
    "frozen-ground-truth/post_freeze_invalidation_manifest.json", "frozen-inputs/input_manifest.json",
    "prompts/gap_only_prompt.md", "prompts/evolution_aware_prompt.md", "frozen-experiment-config.json",
    "predictions/build_only.csv", "predictions/gap_only.jsonl", "predictions/evolution_aware.jsonl",
    "predictions/gap_only_input_output_pairs.jsonl", "predictions/evolution_aware_input_output_pairs.jsonl",
    "predictions/prediction_freeze_manifest.json", "results/overall_metrics.csv",
    "results/silent_positive_metrics.csv", "results/explicit_positive_metrics.csv",
    "results/hard_negative_metrics.csv", "results/reasoning_audit.csv", "results/baseline_comparison.csv",
    "reports/dataset_construction.md", "reports/ground_truth_audit.md", "reports/blind_test_results.md",
    "reports/false_positive_analysis.md", "reports/false_negative_analysis.md", "reports/go_no_go.md",
]
for relative in required:
    check((ROOT / relative).is_file(), f"missing {relative}")
if errors:
    raise SystemExit("\n".join(errors))

gtm = json.loads((ROOT / "frozen-ground-truth/audit_manifest.json").read_text())
im = json.loads((ROOT / "frozen-inputs/input_manifest.json").read_text())
cfg = json.loads((ROOT / "frozen-experiment-config.json").read_text())
pf = json.loads((ROOT / "predictions/prediction_freeze_manifest.json").read_text())
for relative, expected in gtm["files"].items():
    check(digest(ROOT / relative) == expected, f"ground-truth hash changed: {relative}")
for relative, expected in gtm["validation_evidence"].items():
    check(digest(ROOT / relative) == expected, f"validation evidence hash changed: {relative}")
for item in im["cases"]:
    path = ROOT / "frozen-inputs" / item["file"]
    check(digest(path) == item["sha256"], f"input hash changed: {item['case_id']}")
for relative, expected in cfg["prompt_files"].items():
    check(digest(ROOT / relative) == expected, f"prompt hash changed: {relative}")
for relative, expected in pf["files"].items():
    check(digest(ROOT / relative) == expected, f"prediction hash changed: {relative}")

times = [gtm["ground_truth_frozen_at"], im["input_frozen_at"], cfg["config_frozen_at"],
         pf["gap_only_started_at"], pf["gap_only_finished_at"], pf["evolution_aware_started_at"],
         pf["evolution_aware_finished_at"], pf["predictions_frozen_at"]]
parsed = [datetime.fromisoformat(x.replace("Z", "+00:00")) for x in times]
check(parsed == sorted(parsed), "freeze/run timestamps are not strictly ordered")
check(gtm["dataset_hash"] == im["dataset_hash"] == cfg["dataset_hash"] == pf["dataset_hash"], "dataset hash mismatch")
check(im["input_hash"] == cfg["input_hash"] == pf["input_hash"], "input hash mismatch")

labels = rows(ROOT / "frozen-ground-truth/labels.csv")
counts = Counter(x["label"] for x in labels)
check(len(labels) == 80 and len({x["case_id"] for x in labels}) == 80, "labels are not 80 unique cases")
check(len({x["commit"] for x in labels}) == 80, "commits are not unique")
check(counts == {"VERIFIED_SILENT_POSITIVE": 20, "VERIFIED_EXPLICIT_POSITIVE": 10, "VERIFIED_NEGATIVE": 50}, "frozen strata mismatch")
check(len(rows(ROOT / "data/new_candidates.csv")) == 250, "raw candidate count mismatch")
for name in ["build_runtime_validation.csv", "changed_code_coverage.csv", "reachability_validation.csv"]:
    check(len(rows(ROOT / "ground-truth" / name)) == 80, f"row count mismatch: {name}")
check(len(rows(ROOT / "ground-truth/state_config_validation.csv")) == 20, "state/config row count mismatch")

build = {x["case_id"]: x for x in rows(ROOT / "ground-truth/build_runtime_validation.csv")}
for label in labels:
    b = build[label["case_id"]]
    six = [b[k] for k in ("s0_h0_build", "s0_h0_runtime", "s1_h0_build", "s1_h0_runtime", "s1_h1_build", "s1_h1_runtime")]
    if label["label"] in {"VERIFIED_SILENT_POSITIVE", "VERIFIED_NEGATIVE"}:
        check(six == ["PASS"] * 6, f"non-VP1 three-way failure: {label['case_id']}")
    else:
        check(b["s0_h0_build"] == "PASS" and b["s1_h0_build"] == "FAIL" and b["s1_h1_build"] == "PASS", f"VP1 pattern failure: {label['case_id']}")

expected_cases = {x["case_id"] for x in labels}
for baseline in ("gap_only", "evolution_aware"):
    predictions = [json.loads(line) for line in (ROOT / f"predictions/{baseline}.jsonl").read_text().splitlines() if line]
    pairs = [json.loads(line) for line in (ROOT / f"predictions/{baseline}_input_output_pairs.jsonl").read_text().splitlines() if line]
    check(len(predictions) == len(pairs) == 80, f"prediction count mismatch: {baseline}")
    check({str(x["case_id"]) for x in predictions} == expected_cases, f"prediction case mismatch: {baseline}")
    prompt = (ROOT / f"prompts/{baseline}_prompt.md").read_text().rstrip()
    for pair in pairs:
        case = (ROOT / "frozen-inputs" / f"{pair['case_id']}.md").read_text()
        expected = prompt + "\n\n--- BEGIN ANONYMOUS CASE ---\n\n" + case + "\n--- END ANONYMOUS CASE ---\n"
        check(pair["model_input"] == expected, f"stored model input mismatch: {baseline}/{pair['case_id']}")
        check(pair["model_output"] is not None and pair["exit_code"] == 0 and not pair["error"], f"invalid one-shot call: {baseline}/{pair['case_id']}")

invalid = rows(ROOT / "frozen-ground-truth/invalidations.csv")
check(len(invalid) == 3 and {x["internal_id"] for x in invalid} == {"N223", "N231", "N234"}, "invalidation set mismatch")
check(all(not x["relabelled_to"] and x["included_in_valid_main_metrics"] == "NO" for x in invalid), "an invalid case was relabeled/included")
summary = json.loads((ROOT / "results/summary.json").read_text())
check((summary["valid_cases"], summary["valid_silent_positive"], summary["valid_explicit_positive"], summary["valid_negative"]) == (77, 17, 10, 50), "valid counts mismatch")
check(summary["silent"]["Evolution-Aware"]["recall"] == "0.823529", "Evolution silent recall mismatch")
check(summary["overall"]["Evolution-Aware"]["fpr"] == "0.000000", "Evolution FPR mismatch")
check(summary["fp_reduction_gap_to_evolution"] == "1.000000", "FP reduction mismatch")
check(len(rows(ROOT / "results/reasoning_audit.csv")) == 30, "reasoning audit size mismatch")

print(json.dumps({"status": "PASS", "checks": checks, "errors": 0,
                  "frozen_cases": 80, "valid_cases": 77,
                  "dataset_hash": gtm["dataset_hash"], "input_hash": im["input_hash"]}, indent=2))
