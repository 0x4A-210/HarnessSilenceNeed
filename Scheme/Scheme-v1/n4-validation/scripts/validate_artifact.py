#!/usr/bin/env python3
"""Fail-closed integrity validation for the completed task-4 artifact."""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, message: str, checks: list[str]) -> None:
    if not condition:
        raise SystemExit(f"VALIDATION FAILED: {message}")
    checks.append(message)


def rows(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8", newline="")))


def main() -> None:
    checks: list[str] = []
    required = [
        "data/n4_candidates.csv", "data/positive_candidates.csv", "data/matched_pairs.csv",
        "data/excluded_cases.csv", "data/independence_audit.csv",
        "ground-truth/n4_audit.csv", "ground-truth/positive_audit.csv",
        "frozen-ground-truth/labels.csv", "frozen-ground-truth/manifest.json",
        "frozen-ground-truth/invalidations.csv", "frozen-inputs/manifest.json",
        "prompts/gap_only_prompt.md", "prompts/evolution_aware_prompt.md",
        "predictions/gap_only.jsonl", "predictions/evolution_aware.jsonl",
        "predictions/prediction_freeze_manifest.json", "results/metrics.csv",
        "results/n4_metrics.csv", "results/attribution_metrics.csv",
        "results/confusion_matrix.csv", "results/matched_pair_results.csv",
        "results/frozen_label_sensitivity.csv", "results/summary.json",
        "reports/dataset_construction.md", "reports/ground_truth_audit.md",
        "reports/blind_test_results.md", "reports/false_positive_analysis.md",
        "reports/false_negative_analysis.md", "reports/go_no_go.md",
    ]
    require(all((ROOT / p).is_file() for p in required), "all required artifact files exist", checks)

    n4, pos = rows(ROOT / "data/n4_candidates.csv"), rows(ROOT / "data/positive_candidates.csv")
    require(len(n4) == 20 and len(pos) == 20, "candidate selection is exactly 20 N4 + 20 positive", checks)
    require(len({r["commit"] for r in n4 + pos}) == 40, "all 40 selected commits are unique", checks)
    independence = rows(ROOT / "data/independence_audit.csv")
    require(len(independence) == 40 and all(r["prior_data_overlap"] == "false" for r in independence),
            "all selected commits pass prior-data overlap audit", checks)

    n4_audit, pos_audit = rows(ROOT / "ground-truth/n4_audit.csv"), rows(ROOT / "ground-truth/positive_audit.csv")
    require(len(n4_audit) == 20 and len(pos_audit) == 20 and
            all(r["audit_status"] == "VALID" and r["build_pair_pass"] == "true" for r in n4_audit + pos_audit),
            "all 40 pre-freeze audits and S0/S1 build-run pairs passed", checks)

    gt_manifest = json.loads((ROOT / "frozen-ground-truth/manifest.json").read_text())
    label_path = ROOT / "frozen-ground-truth/labels.csv"
    require(sha256(label_path.read_bytes()) == gt_manifest["labels_file_sha256"],
            "frozen labels still match their pre-prediction hash", checks)
    labels = rows(label_path)
    require(len(labels) == 40 and {r["case_id"] for r in labels} == {f"C{i:03d}" for i in range(1, 41)},
            "neutral label mapping contains C001-C040 exactly once", checks)

    input_manifest = json.loads((ROOT / "frozen-inputs/manifest.json").read_text())
    input_files = sorted((ROOT / "frozen-inputs").glob("C[0-9][0-9][0-9].md"))
    require(len(input_files) == 40, "exactly 40 frozen blind inputs exist", checks)
    listed = {r["case_id"]: r["sha256"] for r in input_manifest["files"]}
    require(all(sha256(p.read_bytes()) == listed[p.stem] for p in input_files),
            "every frozen input matches its manifest hash", checks)
    leak = re.compile(r"N4_EXISTING_GAP|COMMIT_INDUCED_POSITIVE|ground[- ]truth|audit_status|frozen_label")
    require(not any(leak.search(p.read_text(encoding="utf-8")) for p in input_files),
            "blind inputs contain no label or ground-truth marker", checks)

    config = json.loads((ROOT / "frozen-experiment-config.json").read_text())
    require(config["model"] == "gpt-5.6-sol" and config["reasoning_effort"] == "high" and
            config["retries"] == 0 and config["dataset_hash"] == gt_manifest["dataset_hash"],
            "frozen model/config and dataset hash are internally consistent", checks)
    require(all(sha256((ROOT / path).read_bytes()) == digest for path, digest in config["prompt_files"].items()),
            "all prompt/schema files match frozen hashes", checks)

    pred_freeze = json.loads((ROOT / "predictions/prediction_freeze_manifest.json").read_text())
    require(pred_freeze["status"] == "FROZEN_BEFORE_LABEL_REVEAL" and
            pred_freeze["total_one_shot_predictions"] == 80, "80 predictions froze before label reveal", checks)
    for method in ("gap_only", "evolution_aware"):
        info = pred_freeze["methods"][method]
        require(sha256((ROOT / f"predictions/{method}.jsonl").read_bytes()) == info["prediction_sha256"] and
                sha256((ROOT / f"predictions/{method}_input_output_pairs.jsonl").read_bytes()) == info["input_output_pairs_sha256"],
                f"{method} predictions and input/output pairs match frozen hashes", checks)
        run = json.loads((ROOT / f"predictions/run_manifest_{method}.json").read_text())
        require(run["status"] == "complete" and run["valid_predictions"] == 40 and
                run["failed_predictions"] == 0 and len(run["attempts"]) == 40 and
                all(a["exit_code"] == 0 and a["valid_prediction"] for a in run["attempts"]),
                f"{method} has 40 successful one-shot attempts and zero failures", checks)

    invalid = rows(ROOT / "frozen-ground-truth/invalidations.csv")
    require(len(invalid) == 4 and all(r["post_freeze_status"] == "INVALIDATE" and
                                      not r["replacement_label"] and r["included_in_main_results"] == "false" for r in invalid),
            "four post-freeze errors are invalidated without relabel/replacement", checks)
    summary = json.loads((ROOT / "results/summary.json").read_text())
    require(summary["valid_n4"] == 16 and summary["valid_positive"] == 20 and
            summary["gap_only_n4_fp"] == 16 and summary["evolution_n4_fp"] == 7 and
            abs(summary["fp_reduction"] - 0.5625) < 1e-12 and summary["go_no_go"] == "NO-GO",
            "reported core metrics and NO-GO decision are internally consistent", checks)
    sensitivity = rows(ROOT / "results/frozen_label_sensitivity.csv")
    require(len(sensitivity) == 2 and sensitivity[1]["n4_fp"] == "11" and
            sensitivity[1]["n4_fpr_percent"] == "55.000000",
            "all-40 frozen-label sensitivity is present and reports 11/20 evolution FP", checks)
    outcomes = rows(ROOT / "results/case_outcomes.csv")
    require(len(outcomes) == 40 and all(r["evolution_output_consistent"] == "true" for r in outcomes),
            "all 40 emitted Evolution-Aware outputs obey the final conjunction rule", checks)

    critical = sorted(p for p in ROOT.rglob("*") if p.is_file() and
                      p.relative_to(ROOT).as_posix() not in {"artifact_manifest.json", "reports/artifact_validation.md"} and
                      "__pycache__" not in p.parts)
    artifact_manifest = {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "status": "VALID", "file_count": len(critical),
        "files": {p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()) for p in critical},
    }
    (ROOT / "artifact_manifest.json").write_text(json.dumps(artifact_manifest, indent=2, sort_keys=True) + "\n")
    report = "# Artifact Validation\n\nStatus: **PASS**\n\n" + "\n".join(f"- PASS — {x}" for x in checks) + "\n"
    report += f"\nManifest records {len(critical)} files.\n"
    (ROOT / "reports/artifact_validation.md").write_text(report, encoding="utf-8")
    print(json.dumps({"status": "PASS", "checks": len(checks), "manifest_files": len(critical)}, indent=2))


if __name__ == "__main__":
    main()
