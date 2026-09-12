#!/usr/bin/env python3
"""Fail-closed consistency checks for the completed Task-6 artifact."""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    errors: list[str] = []
    checks: list[str] = []

    config = json.loads((ROOT / "experiment_config.json").read_text())
    manifest = json.loads((ROOT / "raw" / "formal_run_manifest.json").read_text())
    cases = read_csv(ROOT / "dataset" / "cases.csv")
    case_ids = {row["case_id"] for row in cases}
    if len(cases) != 39 or len(case_ids) != 39:
        errors.append(f"case count/uniqueness is {len(cases)}/{len(case_ids)}, expected 39/39")
    if "T5028" in case_ids:
        errors.append("invalidated T5028 is present")
    labels = {name: sum(row["label"] == name for row in cases) for name in ("POSITIVE", "N4")}
    if labels != {"POSITIVE": 20, "N4": 19}:
        errors.append(f"label counts are {labels}")
    checks.append("39 unique cases; 20 silent positives, 19 N4; T5028 excluded")

    if manifest.get("status") != "COMPLETE" or manifest.get("case_count") != 39:
        errors.append(f"formal run manifest is {manifest.get('status')}/{manifest.get('case_count')}")
    checks.append("formal run manifest COMPLETE")

    hash_bad = []
    for relative, expected in config["frozen_file_sha256"].items():
        path = WORKSPACE / relative
        actual = digest(path) if path.exists() else None
        if actual != expected:
            hash_bad.append(relative)
    if hash_bad:
        errors.append(f"frozen hash mismatches: {hash_bad}")
    checks.append(f"{len(config['frozen_file_sha256'])} frozen SHA-256 checks")

    corpus = read_csv(ROOT / "dataset" / "corpus_manifest.csv")
    s0_by_case = {row["case_id"]: row["s0_commit"] for row in cases}
    for row in corpus:
        if row["source_commit"] != s0_by_case[row["case_id"]]:
            errors.append(f"post-S0 corpus commit in {row['case_id']}/{row['fuzz_target']}")
        if row["post_commit_data_used"] != "false":
            errors.append(f"post-commit corpus flagged in {row['case_id']}/{row['fuzz_target']}")
    checks.append(f"{len(corpus)} corpus rows use each case's S0 commit")

    build_status = {}
    raw_total = raw_pass = 0
    for case in cases:
        case_id = case["case_id"]
        versions = []
        for version in ("s0", "s1"):
            path = ROOT / "raw" / "timings" / f"{case_id}_{version}_build.json"
            if not path.exists():
                versions.append("MISSING")
            else:
                versions.append(json.loads(path.read_text()).get("status", "MISSING"))
        build_status[case_id] = versions
        raw_paths = sorted((ROOT / "raw" / "coverage" / case_id).glob("*/*.json.gz"))
        expected = 12 if versions == ["PASS", "PASS"] else 0
        if len(raw_paths) != expected:
            errors.append(f"{case_id}: {len(raw_paths)} coverage files, expected {expected}")
        for path in raw_paths:
            raw_total += 1
            try:
                with gzip.open(path, "rt", encoding="utf-8") as handle:
                    value = json.load(handle)
            except Exception as exc:
                errors.append(f"{path.relative_to(ROOT)} unreadable: {exc}")
                continue
            if value.get("status") == "PASS" and value.get("run_status") == "PASS":
                raw_pass += 1
            else:
                errors.append(f"{path.relative_to(ROOT)} status {value.get('run_status')}/{value.get('status')}")
    checks.append(f"{raw_pass}/{raw_total} gzip coverage records have run=PASS and coverage=PASS")

    required_results = [
        "build_only.csv", "overall_coverage.csv", "coverage_delta.csv",
        "changed_code_coverage.csv", "reachability.csv", "budget_comparison.csv",
        "runtime_cost.csv", "classification_metrics.csv", "execution_failures.csv",
        "case_predictions.csv", "method_summary.csv", "repeatability_5m.csv",
        "execution_audit.csv", "case_analysis.csv", "s1_overall_threshold_sweep.csv",
        "s1_overall_oracle_summary.csv", "s1_overall_auc.csv", "h1_oracle.csv", "cost_summary.json",
        "frozen_integrity_audit.json", "post_freeze_reporting_manifest.json",
        "postprocess_summary.json",
    ]
    missing_results = [name for name in required_results if not (ROOT / "results" / name).is_file()]
    if missing_results:
        errors.append(f"missing result files: {missing_results}")
    checks.append(f"{len(required_results) - len(missing_results)}/{len(required_results)} required result files")

    summary_path = ROOT / "results" / "method_summary.csv"
    if summary_path.exists():
        rows = read_csv(summary_path)
        for row in rows:
            classified = sum(int(row[field]) for field in ("TP", "FN", "FP", "TN",
                                                              "abstain_positive", "abstain_n4"))
            if classified != 39:
                errors.append(f"metric denominator {classified} for {row['method']}/{row['budget']}")
        delta = [row for row in rows if row["method"] == "Delta-Aware"]
        if len(delta) != 1 or [int(delta[0][field]) for field in ("TP", "FN", "FP", "TN")] != [20, 0, 0, 19]:
            errors.append("frozen Delta-Aware metric is not 20/0/0/19")
        checks.append("all method summaries account for 39 cases; Delta-Aware is 20/0/0/19")

    report_names = [
        "dynamic_baseline_results.md", "cost_analysis.md", "coverage_failure_cases.md",
        "reviewer_kill_test.md", "go_no_go.md",
    ]
    missing_reports = [name for name in report_names if not (ROOT / "reports" / name).is_file()]
    if missing_reports:
        errors.append(f"missing reports: {missing_reports}")
    checks.append(f"{len(report_names) - len(missing_reports)}/{len(report_names)} required reports")

    status = "PASS" if not errors else "FAIL"
    value = {"status": status, "checks": checks, "errors": errors,
             "raw_coverage_records": raw_total, "raw_coverage_pass": raw_pass,
             "build_pair_pass_cases": sum(value == ["PASS", "PASS"] for value in build_status.values()),
             "build_pair_unavailable_cases": sum(value != ["PASS", "PASS"] for value in build_status.values())}
    (ROOT / "results" / "validation.json").write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# Artifact validation", "", f"Final status: **{status}**.", "", "## Checks", ""]
    lines.extend(f"- {item}" for item in checks)
    lines.extend(["", "## Errors", ""])
    lines.extend(f"- {item}" for item in errors or ["None."])
    (ROOT / "reports" / "artifact_validation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if errors:
        raise SystemExit("artifact validation failed; see results/validation.json")


if __name__ == "__main__":
    main()
