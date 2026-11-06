#!/usr/bin/env python3
"""De-blind and report the frozen eight-positive hold-out run."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve()
HOLDOUT = HERE.parents[1]
MAPPING = HOLDOUT / "data" / "case_mapping.csv"
PREDICTIONS = HOLDOUT / "results" / "llm_predictions.jsonl"
MANIFEST = HOLDOUT / "results" / "run_manifest.json"
AUDIT = HOLDOUT / "config" / "reasoning_audit.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    mapping_rows = read_csv(MAPPING)
    mapping = {x["case_id"]: x for x in mapping_rows}
    predictions_list = [
        json.loads(x) for x in PREDICTIONS.read_text(encoding="utf-8").splitlines()
        if x.strip()
    ]
    predictions = {x["case_id"]: x for x in predictions_list}
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    audit_doc = json.loads(AUDIT.read_text(encoding="utf-8"))
    annotations = audit_doc["annotations"]
    expected_ids = {f"C{x:03d}" for x in range(106, 114)}

    if set(mapping) != expected_ids or set(predictions) != expected_ids:
        raise RuntimeError("hold-out mapping or prediction IDs differ from C106..C113")
    if len(mapping_rows) != 8 or len(mapping) != 8:
        raise RuntimeError("hold-out mapping must have eight unique rows")
    if set(annotations) != expected_ids:
        raise RuntimeError("all eight hold-out cases must be audited")
    if manifest.get("status") != "complete" or manifest.get("valid_predictions") != 8:
        raise RuntimeError("hold-out manifest is not a clean eight-case completion")
    attempts = manifest.get("attempts", [])
    if len(attempts) != 8 or len({x["case_id"] for x in attempts}) != 8:
        raise RuntimeError("hold-out one-attempt invariant failed")
    if any(x.get("exit_code") != 0 or not x.get("valid_prediction") for x in attempts):
        raise RuntimeError("one or more hold-out invocations failed")

    outcomes: list[dict] = []
    audit_rows: list[dict] = []
    pair_rows: list[dict] = []
    report_sections: list[str] = []
    tp = fn = 0
    for case_id in sorted(expected_ids):
        m, p, a = mapping[case_id], predictions[case_id], annotations[case_id]
        decision = p["maintenance_needed"]
        if not isinstance(decision, bool):
            raise RuntimeError(f"decision is not boolean: {case_id}")
        outcome = "TP" if decision else "FN"
        tp += int(decision)
        fn += int(not decision)
        input_path = HOLDOUT / "inputs" / f"{case_id}.txt"
        raw_path = HOLDOUT / "results" / "raw" / f"{case_id}.json"
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        if raw != p:
            raise RuntimeError(f"raw and JSONL output differ: {case_id}")
        if sha256(input_path) != m["input_sha256"]:
            raise RuntimeError(f"input hash changed: {case_id}")

        outcome_row = {
            "case_id": case_id,
            "project": m["project"],
            "commit_id": m["commit_id"],
            "commit_time": m["commit_time"],
            "actual_label": "positive",
            "predicted_label": "YES" if decision else "NO",
            "outcome": outcome,
            "confidence": p["confidence"],
            "input_file": f"inputs/{case_id}.txt",
            "input_sha256": m["input_sha256"],
            "output_file": f"results/raw/{case_id}.json",
            "reason": p["reason"],
        }
        outcomes.append(outcome_row)
        audit_rows.append({
            "case_id": case_id,
            "project": m["project"],
            "predicted_label": outcome_row["predicted_label"],
            "outcome": outcome,
            "strict_decision_correct": int(decision),
            "strict_reason_correct": a["strict_reason_correct"],
            "evidence_grounded": a["evidence_grounded"],
            "decision_defensible_from_allowed_input": a["decision_defensible_from_allowed_input"],
            "positive_mechanism_observability": a["positive_mechanism_observability"],
            "miss_category": a["miss_category"],
            "ground_truth_mechanism": a["ground_truth_mechanism"],
            "audit_note": a["audit_note"],
        })
        exact_input = input_path.read_text(encoding="utf-8")
        pair_rows.append({
            "case_id": case_id,
            "input_sha256": m["input_sha256"],
            "exact_input": exact_input,
            "exact_output": p,
        })
        report_sections.append(f"""## {case_id}: {m['project']}

- Commit: `{m['commit_id']}`
- Label / prediction: Positive / **{outcome_row['predicted_label']} ({outcome})**
- Confidence: {p['confidence']}
- Exact GPT input: [`inputs/{case_id}.txt`](../inputs/{case_id}.txt) (`sha256:{m['input_sha256']}`)
- Exact raw output: [`results/raw/{case_id}.json`](../results/raw/{case_id}.json)
- Positive mechanism observability: `{a['positive_mechanism_observability']}`
- Post-run audit: {a['audit_note']}

Exact JSON returned by GPT:

```json
{json.dumps(p, ensure_ascii=False, indent=2)}
```
""")

    write_csv(HOLDOUT / "results" / "case_results.csv", outcomes, [
        "case_id", "project", "commit_id", "commit_time", "actual_label",
        "predicted_label", "outcome", "confidence", "input_file", "input_sha256",
        "output_file", "reason",
    ])
    write_csv(HOLDOUT / "results" / "reasoning_quality.csv", audit_rows, [
        "case_id", "project", "predicted_label", "outcome", "strict_decision_correct",
        "strict_reason_correct", "evidence_grounded", "decision_defensible_from_allowed_input",
        "positive_mechanism_observability", "miss_category", "ground_truth_mechanism", "audit_note",
    ])
    write_csv(HOLDOUT / "results" / "confusion_matrix.csv", [
        {"predicted": "YES", "actual_positive": tp, "actual_negative": "N/A"},
        {"predicted": "NO", "actual_positive": fn, "actual_negative": "N/A"},
    ], ["predicted", "actual_positive", "actual_negative"])
    write_csv(HOLDOUT / "results" / "summary.csv", [
        {"metric": "holdout_positive_cases", "value": 8, "denominator": "", "rate": "", "note": "all eight phase-1 held-out confirmed degradation events"},
        {"metric": "TP", "value": tp, "denominator": 8, "rate": f"{tp / 8:.4f}", "note": "strict match to historical positive label"},
        {"metric": "FN", "value": fn, "denominator": 8, "rate": f"{fn / 8:.4f}", "note": "strict match to historical positive label"},
        {"metric": "holdout_positive_detection", "value": tp, "denominator": 8, "rate": f"{tp / 8:.4f}", "note": "do not interpret as a population recall estimate"},
        {"metric": "pilot_plus_holdout_TP", "value": 5 + tp, "denominator": 13, "rate": f"{(5 + tp) / 13:.4f}", "note": "descriptive combination of two differently selected batches"},
        {"metric": "technical_failures", "value": 0, "denominator": 8, "rate": "0.0000", "note": "no retry"},
    ], ["metric", "value", "denominator", "rate", "note"])

    with (HOLDOUT / "results" / "input_output_pairs.jsonl").open(
        "w", encoding="utf-8", newline="\n"
    ) as handle:
        for row in pair_rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    sections_text = "\n".join(report_sections)
    report = f"""# Eight-case Hold-out: Exact Inputs and Outputs

All eight outputs were produced once with the frozen prompt, schema, model, and parameters. GPT saw only the exact linked input file for that case; it did not receive this mapping, any degradation result, H1/harness diff, pilot answer, or error analysis.

Strict result against the phase-1 confirmed-positive labels: **{tp}/8 YES (TP), {fn}/8 NO (FN)**.

The complete input is not abbreviated in this report: each link points to the byte-for-byte UTF-8 text piped to `codex exec`, including the fixed prompt, anonymous case, and boundary markers. The same eight input/output pairs are also embedded in machine-readable `results/input_output_pairs.jsonl`.

{sections_text}
"""
    write_text(HOLDOUT / "reports" / "case_by_case.md", report)
    print(json.dumps({
        "holdout_cases": 8,
        "TP": tp,
        "FN": fn,
        "detection": f"{tp}/8",
        "combined_descriptive": f"{5 + tp}/13",
    }, indent=2))


if __name__ == "__main__":
    main()
