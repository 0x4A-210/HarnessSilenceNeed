#!/usr/bin/env python3
"""Run structural, provenance, blindness, and result-integrity checks."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve()
OUT = HERE.parents[1]
ROOT = OUT.parent
PHASE1 = ROOT / "FSE2026-harness-degradation"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def check(condition: bool, description: str, failures: list[str]) -> None:
    if not condition:
        failures.append(description)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    failures: list[str] = []
    mapping_rows = rows(OUT / "data" / "case_mapping.csv")
    positives = rows(OUT / "data" / "selected_positive_cases.csv")
    negatives = rows(OUT / "data" / "selected_negative_cases.csv")
    withheld = rows(OUT / "data" / "withheld_positive_cases.csv")
    materialization = {
        x["case_id"]: x for x in rows(OUT / "data" / "case_materialization.csv")
    }
    universe = {
        (x["project"], x["commit_id"]): x
        for x in rows(PHASE1 / "data" / "processed" / "commit_universe.csv")
    }
    confirmed = {
        (x["project"], x["commit_id"])
        for x in json.loads(
            (PHASE1 / "evidence" / "positive_event_evidence.json").read_text(encoding="utf-8")
        )
    }
    predictions = [
        json.loads(x)
        for x in (OUT / "results" / "llm_predictions.jsonl").read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]
    manifest = json.loads((OUT / "results" / "run_manifest.json").read_text(encoding="utf-8"))

    mapping = {x["case_id"]: x for x in mapping_rows}
    prediction_map = {x["case_id"]: x for x in predictions}
    case_files = sorted((OUT / "cases").glob("C*.md"))
    raw_json = sorted((OUT / "results" / "raw").glob("C*.json"))
    raw_stdout = sorted((OUT / "results" / "raw").glob("C*.stdout.log"))
    raw_stderr = sorted((OUT / "results" / "raw").glob("C*.stderr.log"))

    check(len(mapping_rows) == len(mapping) == 105, "mapping must contain 105 unique IDs", failures)
    check(len(positives) == 5, "selected positives must equal 5", failures)
    check(len(negatives) == 100, "selected negatives must equal 100", failures)
    check(len(withheld) == 8, "withheld confirmed positives must equal 8", failures)
    check(len(case_files) == 105, "there must be 105 case files", failures)
    check(len(predictions) == len(prediction_map) == 105, "there must be 105 unique predictions", failures)
    check(len(raw_json) == len(raw_stdout) == len(raw_stderr) == 105, "raw result triplets must equal 105", failures)
    check(Counter(x["actual_label"] for x in mapping_rows) == {"positive": 5, "negative": 100}, "class counts differ", failures)
    check(Counter(x["negative_type"] for x in negatives) == {"matched": 60, "easy": 20, "hard": 20}, "negative strata differ", failures)
    check(Counter(x["project"] for x in negatives) == {x: 10 for x in {
        "brotli", "c-ares", "h2o", "jansson", "leptonica", "libplist",
        "libspng", "meshoptimizer", "tidy-html5", "wuffs",
    }}, "negative project allocation is not 10 each", failures)
    check(set(mapping) == {x.stem for x in case_files} == set(prediction_map), "case ID sets differ", failures)

    selected_positive_keys = {(x["project"], x["commit_id"]) for x in positives}
    withheld_keys = {(x["project"], x["commit_id"]) for x in withheld}
    check(selected_positive_keys <= confirmed, "a selected positive is not confirmed by phase 1", failures)
    check(withheld_keys <= confirmed, "a withheld item is not confirmed by phase 1", failures)
    check(not (selected_positive_keys & withheld_keys), "selected and withheld positives overlap", failures)
    check(len(selected_positive_keys | withheld_keys) == 13, "selected plus withheld positives must cover all 13", failures)
    for item in negatives:
        key = (item["project"], item["commit_id"])
        check(key in universe, f"negative outside phase-1 universe: {key}", failures)
        check(key not in confirmed, f"confirmed event used as a negative: {key}", failures)
        if key in universe:
            check(universe[key]["previous_commit"] == item["previous_commit"], f"parent mismatch: {key}", failures)

    forbidden_literals = ["actual_label", "degradation_metric_before", "degradation_metric_after", "clusterfuzz-testcase", "CVE-"]
    manifest_cases = {x["case_id"]: x["case_sha256"] for x in manifest.get("cases", [])}
    for path in case_files:
        case_id = path.stem
        text = path.read_text(encoding="utf-8")
        item = mapping[case_id]
        digest = sha256(path)
        check(digest == item["case_sha256"], f"mapping hash mismatch: {case_id}", failures)
        check(digest == materialization[case_id]["case_sha256"], f"materialization hash mismatch: {case_id}", failures)
        check(digest == manifest_cases.get(case_id), f"run-manifest hash mismatch: {case_id}", failures)
        check(item["commit_id"] not in text, f"source commit leaked: {case_id}", failures)
        check(item["previous_commit"] not in text, f"parent commit leaked: {case_id}", failures)
        check(not re.search(r"(?m)^index [0-9a-f]+\.\.[0-9a-f]+", text), f"git blob IDs leaked: {case_id}", failures)
        lowered = text.lower()
        for literal in forbidden_literals:
            check(literal.lower() not in lowered, f"forbidden answer cue {literal!r}: {case_id}", failures)

    schema_fields = {
        "case_id", "maintenance_needed", "confidence", "change_types",
        "affected_functions", "reason", "evidence", "recommended_action",
    }
    for prediction in predictions:
        case_id = prediction.get("case_id", "<missing>")
        check(set(prediction) == schema_fields, f"prediction fields differ: {case_id}", failures)
        check(isinstance(prediction.get("maintenance_needed"), bool), f"decision not boolean: {case_id}", failures)
        check(isinstance(prediction.get("confidence"), int) and 0 <= prediction.get("confidence", -1) <= 100, f"confidence invalid: {case_id}", failures)
        check(isinstance(prediction.get("change_types"), list), f"change_types invalid: {case_id}", failures)
        check(isinstance(prediction.get("affected_functions"), list), f"affected_functions invalid: {case_id}", failures)
        check(isinstance(prediction.get("reason"), str) and bool(prediction.get("reason")), f"reason invalid: {case_id}", failures)
        check(isinstance(prediction.get("evidence"), list) and bool(prediction.get("evidence")), f"evidence invalid: {case_id}", failures)

    attempts = manifest.get("attempts", [])
    check(manifest.get("status") == "complete", "run status is not complete", failures)
    check(manifest.get("valid_predictions") == 105 and manifest.get("failed_predictions") == 0, "run success counts differ", failures)
    check(len(attempts) == 105 and len({x["case_id"] for x in attempts}) == 105, "not exactly one attempt per case", failures)
    check(all(x.get("exit_code") == 0 and x.get("valid_prediction") for x in attempts), "a run attempt failed", failures)

    # The frozen instruction prohibited tools. Codex CLI records any tool invocation after
    # the anonymous case boundary; none should appear in that region.
    tool_markers = ("exec_command", "web.run", "tool call", "mcp__")
    for path in raw_stderr:
        content = path.read_text(encoding="utf-8", errors="replace")
        tail = content.split("--- END ANONYMOUS CASE ---", 1)[-1]
        suspicious = [
            line for line in tail.splitlines()
            if line.strip().lower().startswith(tool_markers)
        ]
        check(not suspicious, f"possible predictor tool invocation: {path.stem}", failures)

    expected_summary = {
        "TP": "5", "FP": "6", "FN": "0", "TN": "94",
        "FP_easy": "0", "FP_matched": "3", "FP_hard": "3",
        "pre_registered_gate": "MODERATE GO",
    }
    summary = {x["metric"]: x["value"] for x in rows(OUT / "results" / "summary.csv")}
    for key, value in expected_summary.items():
        check(summary.get(key) == value, f"summary mismatch for {key}", failures)

    result = {
        "status": "PASS" if not failures else "FAIL",
        "checks": {
            "cases": len(case_files),
            "selected_positive": len(positives),
            "selected_negative": len(negatives),
            "withheld_positive": len(withheld),
            "predictions": len(predictions),
            "raw_attempts": len(attempts),
            "leak_and_hash_cases_checked": len(case_files),
        },
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
