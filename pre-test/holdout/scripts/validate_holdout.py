#!/usr/bin/env python3
"""Validate blindness, immutability, one-shot execution, and outputs."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import re
from pathlib import Path


HERE = Path(__file__).resolve()
HOLDOUT = HERE.parents[1]
PRETEST = HOLDOUT.parent
PROMPT = PRETEST / "prompts" / "fixed_prompt.md"
SCHEMA = PRETEST / "prompts" / "prediction_schema.json"
BASE_GENERATOR = PRETEST / "scripts" / "build_dataset.py"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(value: bool, message: str, failures: list[str]) -> None:
    if not value:
        failures.append(message)


def load_base():
    spec = importlib.util.spec_from_file_location("frozen_build_dataset", BASE_GENERATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import base generator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    failures: list[str] = []
    base = load_base()
    mapping_rows = rows(HOLDOUT / "data" / "case_mapping.csv")
    mapping = {x["case_id"]: x for x in mapping_rows}
    materialization = {
        x["case_id"]: x for x in rows(HOLDOUT / "data" / "case_materialization.csv")
    }
    dataset_manifest = json.loads(
        (HOLDOUT / "data" / "dataset_manifest.json").read_text(encoding="utf-8")
    )
    run_manifest = json.loads(
        (HOLDOUT / "results" / "run_manifest.json").read_text(encoding="utf-8")
    )
    pilot_manifest = json.loads(
        (PRETEST / "results" / "run_manifest.json").read_text(encoding="utf-8")
    )
    predictions_list = [
        json.loads(x)
        for x in (HOLDOUT / "results" / "llm_predictions.jsonl").read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]
    predictions = {x["case_id"]: x for x in predictions_list}
    expected_ids = {f"C{x:03d}" for x in range(106, 114)}
    case_files = sorted((HOLDOUT / "cases").glob("C*.md"))
    input_files = sorted((HOLDOUT / "inputs").glob("C*.txt"))
    raw_json = sorted((HOLDOUT / "results" / "raw").glob("C*.json"))
    raw_stdout = sorted((HOLDOUT / "results" / "raw").glob("C*.stdout.log"))
    raw_stderr = sorted((HOLDOUT / "results" / "raw").glob("C*.stderr.log"))

    check(len(mapping_rows) == len(mapping) == 8, "mapping must contain eight unique rows", failures)
    check(set(mapping) == expected_ids, "mapping IDs must be C106..C113", failures)
    check(len(case_files) == len(input_files) == 8, "case/input file counts differ", failures)
    check({x.stem for x in case_files} == {x.stem for x in input_files} == expected_ids, "case/input IDs differ", failures)
    check(len(predictions_list) == len(predictions) == 8 and set(predictions) == expected_ids, "prediction IDs differ", failures)
    check(len(raw_json) == len(raw_stdout) == len(raw_stderr) == 8, "raw result triplets differ", failures)

    manifest_cases = {x["case_id"]: x for x in dataset_manifest["cases"]}
    run_cases = {x["case_id"]: x for x in run_manifest["cases"]}
    fixed = PROMPT.read_text(encoding="utf-8").rstrip()
    previous = rows(PRETEST / "data" / "selected_positive_cases.csv")
    previous_commits = {x["commit_id"] for x in previous} | {x["previous_commit"] for x in previous}
    previous_case_ids = {x["case_id"] for x in previous}
    forbidden_cues = [
        "actual_label", "degradation_metric_before", "degradation_metric_after",
        "MODERATE GO", "False Positive Analysis", "scope-expansion bias",
        "TP_reason_correct", "clusterfuzz-testcase", "CVE-",
    ]
    for case_id in sorted(expected_ids):
        case_path = HOLDOUT / "cases" / f"{case_id}.md"
        input_path = HOLDOUT / "inputs" / f"{case_id}.txt"
        case = case_path.read_text(encoding="utf-8")
        exact_input = input_path.read_text(encoding="utf-8")
        m = mapping[case_id]
        expected_input = (
            fixed + "\n\n--- BEGIN ANONYMOUS CASE ---\n\n" + case
            + "\n--- END ANONYMOUS CASE ---\n"
        )
        check(exact_input == expected_input, f"exact input composition differs: {case_id}", failures)
        check(sha256(case_path) == m["case_sha256"] == manifest_cases[case_id]["case_sha256"], f"case hash differs: {case_id}", failures)
        check(sha256(input_path) == m["input_sha256"] == manifest_cases[case_id]["input_sha256"] == run_cases[case_id]["input_sha256"], f"input hash differs: {case_id}", failures)
        check(m["commit_id"] not in exact_input and m["previous_commit"] not in exact_input, f"hold-out commit ID leaked: {case_id}", failures)
        check(not re.search(r"(?m)^index [0-9a-f]+\.\.[0-9a-f]+", exact_input), f"git blob IDs leaked: {case_id}", failures)
        lowered = exact_input.lower()
        for cue in forbidden_cues:
            check(cue.lower() not in lowered, f"forbidden cue {cue!r}: {case_id}", failures)
        for value in previous_commits | previous_case_ids:
            check(value not in exact_input, f"pilot positive identifier leaked: {case_id}", failures)
        diff_paths = set(filter(None, materialization[case_id]["source_diff_paths"].split(";")))
        known_harness = set(base.REPO_HARNESS_PATHS[m["project"]])
        check(not (diff_paths & known_harness), f"post-H0 harness diff included: {case_id}", failures)
        check(not any({x.lower() for x in Path(path).parts} & {"fuzz", "fuzzer", "fuzzing"} for path in diff_paths), f"fuzz directory diff included: {case_id}", failures)

        raw = json.loads((HOLDOUT / "results" / "raw" / f"{case_id}.json").read_text(encoding="utf-8"))
        check(raw == predictions[case_id], f"raw/JSONL output differs: {case_id}", failures)

    check(dataset_manifest["fixed_prompt_sha256"] == sha256(PROMPT), "dataset prompt hash differs", failures)
    check(dataset_manifest["generator_sha256"] == sha256(BASE_GENERATOR), "base generator changed after freeze", failures)
    check(dataset_manifest["selection_sha256"] == sha256(HOLDOUT / "config" / "selection.json"), "selection changed after freeze", failures)
    check(run_manifest.get("status") == "complete", "run status is not complete", failures)
    check(run_manifest.get("valid_predictions") == 8 and run_manifest.get("failed_predictions") == 0, "run success counts differ", failures)
    attempts = run_manifest.get("attempts", [])
    check(len(attempts) == 8 and len({x["case_id"] for x in attempts}) == 8, "not exactly one attempt per case", failures)
    check(all(x.get("exit_code") == 0 and x.get("valid_prediction") for x in attempts), "an attempt failed", failures)

    for key in (
        "model", "reasoning_effort", "codex_version", "concurrency", "timeout_seconds",
        "fixed_prompt_sha256", "schema_sha256",
    ):
        check(run_manifest.get(key) == pilot_manifest.get(key), f"pilot parameter changed: {key}", failures)

    schema_fields = {
        "case_id", "maintenance_needed", "confidence", "change_types",
        "affected_functions", "reason", "evidence", "recommended_action",
    }
    for case_id, p in predictions.items():
        check(set(p) == schema_fields, f"schema fields differ: {case_id}", failures)
        check(isinstance(p.get("maintenance_needed"), bool), f"decision is not boolean: {case_id}", failures)
        check(isinstance(p.get("confidence"), int) and 0 <= p.get("confidence", -1) <= 100, f"confidence invalid: {case_id}", failures)

    tool_markers = ("exec_command", "web.run", "tool call", "mcp__")
    for path in raw_stderr:
        content = path.read_text(encoding="utf-8", errors="replace")
        tail = content.split("--- END ANONYMOUS CASE ---", 1)[-1]
        suspicious = [
            line for line in tail.splitlines()
            if line.strip().lower().startswith(tool_markers)
        ]
        check(not suspicious, f"possible predictor tool call: {path.stem}", failures)

    pairs = [
        json.loads(x)
        for x in (HOLDOUT / "results" / "input_output_pairs.jsonl").read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]
    check(len(pairs) == 8 and {x["case_id"] for x in pairs} == expected_ids, "input/output pair rows differ", failures)
    for pair in pairs:
        case_id = pair["case_id"]
        check(pair["exact_input"] == (HOLDOUT / "inputs" / f"{case_id}.txt").read_text(encoding="utf-8"), f"embedded input differs: {case_id}", failures)
        check(pair["exact_output"] == predictions[case_id], f"embedded output differs: {case_id}", failures)

    summary = {x["metric"]: x["value"] for x in rows(HOLDOUT / "results" / "summary.csv")}
    check(summary.get("TP") == "3" and summary.get("FN") == "5", "summary result differs", failures)
    result = {
        "status": "PASS" if not failures else "FAIL",
        "checks": {
            "holdout_cases": len(mapping),
            "exact_inputs": len(input_files),
            "predictions": len(predictions),
            "attempts": len(attempts),
            "technical_failures": run_manifest.get("failed_predictions"),
            "TP": int(summary.get("TP", -1)),
            "FN": int(summary.get("FN", -1)),
        },
        "failures": failures,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
