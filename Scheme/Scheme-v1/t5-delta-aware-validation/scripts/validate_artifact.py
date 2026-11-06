#!/usr/bin/env python3
"""Read-only integrity checks followed by a Task-5 validation report."""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_time(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    checks: list[tuple[str, bool, str]] = []

    def check(name: str, condition: bool, detail: str) -> None:
        checks.append((name, condition, detail))

    gt = load_json(ROOT / "frozen-ground-truth" / "manifest.json")
    inputs = load_json(ROOT / "frozen-inputs" / "manifest.json")
    config = load_json(ROOT / "frozen-experiment-config.json")
    prediction_freeze = load_json(ROOT / "predictions" / "prediction_freeze_manifest.json")
    post = load_json(ROOT / "frozen-ground-truth" / "post_freeze_audit_manifest.json")
    labels_path = ROOT / "frozen-ground-truth" / "labels.csv"
    evidence_path = ROOT / "frozen-ground-truth" / "evidence.csv"
    labels = list(csv.DictReader(labels_path.open(encoding="utf-8", newline="")))
    evidence = list(csv.DictReader(evidence_path.open(encoding="utf-8", newline="")))
    invalid = list(csv.DictReader((ROOT / "frozen-ground-truth" / "invalidations.csv").open(encoding="utf-8", newline="")))

    check("ground truth status", gt["status"] == "FROZEN", gt["status"])
    check("40 immutable labels", len(labels) == 40 and len(evidence) == 40, f"labels={len(labels)}, evidence={len(evidence)}")
    check("ground-truth file hashes", digest(labels_path) == gt["labels_sha256"] and digest(evidence_path) == gt["evidence_sha256"],
          f"labels={digest(labels_path)}, evidence={digest(evidence_path)}")
    combined = hashlib.sha256(labels_path.read_bytes() + evidence_path.read_bytes()).hexdigest()
    check("ground-truth composite hash", combined == gt["ground_truth_hash"], combined)
    check("post-freeze labels unchanged", post["labels_sha256_unchanged"] == digest(labels_path), digest(labels_path))
    check("invalidation without relabel", len(invalid) == 1 and invalid[0]["case_id"] == "T5028" and
          invalid[0]["status"] == "INVALIDATE" and invalid[0]["relabelled"] == "false" and post["relabels"] == 0,
          f"invalidations={len(invalid)}, relabels={post['relabels']}")

    input_cases = inputs["case_inputs"]
    case_hashes_ok = all(digest(ROOT / row["input_path"]) == row["sha256"] for row in input_cases)
    composite = "".join(f"{row['case_id']}:{row['sha256']}\n" for row in input_cases).encode()
    check("40 frozen input hashes", len(input_cases) == 40 and case_hashes_ok, f"cases={len(input_cases)}")
    check("input composite hash", hashlib.sha256(composite).hexdigest() == inputs["input_hash"], inputs["input_hash"])
    leakage_ok = True
    commit_by_case = {row["case_id"]: row["commit_id"] for row in labels}
    for row in input_cases:
        text = (ROOT / row["input_path"]).read_text(encoding="utf-8")
        leakage_ok &= commit_by_case[row["case_id"]] not in text
        leakage_ok &= "expected_gap_before" not in text and "semantic_audit" not in text
        leakage_ok &= "## Existing harness H0" in text and "## Complete S0 -> S1 production-source diff" in text
    check("anonymous input template", leakage_ok, "no case commit IDs or oracle field names; required H0/diff sections present")

    prompt_hashes_ok = all(digest(ROOT / path) == expected for path, expected in config["file_sha256"].items())
    check("frozen prompt/schema hashes", prompt_hashes_ok, f"files={len(config['file_sha256'])}")
    check("baseline prompt provenance",
          digest(ROOT / "prompts" / "gap_only.md") == digest(ROOT.parents[0] / "n4-validation" / "prompts" / "gap_only_prompt.md") and
          digest(ROOT / "prompts" / "direct_evolution_aware.md") == digest(ROOT.parents[0] / "n4-validation" / "prompts" / "evolution_aware_prompt.md"),
          "Gap-Only and Direct are byte-identical to Task-4 prompts")
    check("Delta prompt provenance", digest(ROOT / "prompts" / "delta_aware.md") == digest(ROOT / "prompts" / "delta_aware_v2.md"),
          digest(ROOT / "prompts" / "delta_aware.md"))

    methods = ["gap_only", "direct_evolution_aware", "delta_aware"]
    prediction_ok = True; pair_ok = True; runner_blind = True; total_predictions = 0
    for method in methods:
        manifest = load_json(ROOT / "predictions" / f"run_manifest_{method}.json")
        pred = ROOT / "predictions" / f"{method}.jsonl"
        pairs = ROOT / "predictions" / f"{method}_input_output_pairs.jsonl"
        prediction_ok &= manifest["status"] == "complete" and manifest["valid_predictions"] == 40 and manifest["failed_predictions"] == 0
        prediction_ok &= digest(pred) == manifest["prediction_sha256"]
        pair_ok &= digest(pairs) == manifest["input_output_pairs_sha256"]
        pred_rows = [json.loads(line) for line in pred.read_text(encoding="utf-8").splitlines() if line]
        pair_rows = [json.loads(line) for line in pairs.read_text(encoding="utf-8").splitlines() if line]
        total_predictions += len(pred_rows)
        pair_ok &= len(pair_rows) == 40 and len({row["case_id"] for row in pair_rows}) == 40
        runner_blind &= manifest["ground_truth_files_read"] is False and manifest["retries"] == 0
        for row in pair_rows:
            pair_ok &= hashlib.sha256(row["model_input"].encode()).hexdigest() == row["input_sha256"]
    check("three complete prediction streams", prediction_ok and total_predictions == 120,
          f"valid predictions={total_predictions}, failures=0")
    check("full model I/O hashes", pair_ok, "40 input/output pairs per method")
    check("runner blindness and zero retries", runner_blind, "all manifests ground_truth_files_read=false, retries=0")
    freeze_files_ok = all(digest(ROOT / path) == expected for path, expected in prediction_freeze["file_sha256"].items())
    check("prediction-freeze hashes", freeze_files_ok, f"files={len(prediction_freeze['file_sha256'])}")

    chronological = (
        parse_time(gt["frozen_at"]) < parse_time(inputs["frozen_at"])
        < parse_time(config["config_frozen_at"]) < parse_time(prediction_freeze["first_prediction_started_at"])
        < parse_time(prediction_freeze["frozen_at"]) < parse_time(post["audit_completed_at"])
    )
    check("freeze chronology", chronological,
          f"GT {gt['frozen_at']} < input {inputs['frozen_at']} < config {config['config_frozen_at']} < prediction {prediction_freeze['first_prediction_started_at']}")

    selected = list(csv.DictReader((ROOT / "new-data" / "audit.csv").open(encoding="utf-8", newline="")))
    excluded = {row["commit_id"] for row in csv.DictReader((ROOT / "new-data" / "excluded.csv").open(encoding="utf-8", newline=""))}
    check("selected commit independence", len(selected) == 40 and len({row["commit_id"] for row in selected}) == 40 and
          not ({row["commit_id"] for row in selected} & excluded), "40 unique selected SHAs; zero exact overlap with prior exclusions")
    check("no Harness changes", all(row["changed_harness_file_count"] == "0" and row["h0_target_occurrences"] == "0" for row in selected),
          "40/40 changed_harness_file_count=0 and complete-H0 target count=0")

    summary = load_json(ROOT / "results" / "summary.json")
    check("evaluation denominator", summary["valid_cases"] == 39 and summary["valid_n4"] == 19 and summary["valid_positive"] == 20,
          f"valid={summary['valid_cases']}, N4={summary['valid_n4']}, positive={summary['valid_positive']}")
    check("reported decision", summary["decision"] == "MODERATE GO", summary["decision"])

    failed = [name for name, passed, _ in checks if not passed]
    report = {
        "status": "PASS" if not failed else "FAIL", "checks": len(checks), "passed": len(checks) - len(failed),
        "failed": failed, "validated_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    (ROOT / "reports" / "validation.json").write_text(
        json.dumps({**report, "details": [{"check": name, "passed": passed, "detail": detail} for name, passed, detail in checks]},
                   indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = ["# Artifact validation", "", f"Status: **{report['status']}** ({report['passed']}/{report['checks']} checks passed).", "",
             "| Check | Result | Detail |", "|---|---|---|"]
    for name, passed, detail in checks:
        lines.append(f"| {name} | {'PASS' if passed else 'FAIL'} | {detail.replace('|', '/')} |")
    lines.extend(["", "Validation is hash-based and does not rerun the one-shot model predictions.", ""])
    (ROOT / "reports" / "artifact_validation.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
