#!/usr/bin/env python3
"""Materialize the eight independent hold-out cases with the frozen pilot rules."""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import random
from pathlib import Path


HERE = Path(__file__).resolve()
HOLDOUT = HERE.parents[1]
PRETEST = HOLDOUT.parent
ROOT = PRETEST.parent
PHASE1 = ROOT / "FSE2026-harness-degradation"
CONFIG = HOLDOUT / "config" / "selection.json"
BASE_PATH = PRETEST / "scripts" / "build_dataset.py"
PROMPT = PRETEST / "prompts" / "fixed_prompt.md"


def load_base():
    spec = importlib.util.spec_from_file_location("frozen_build_dataset", BASE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import frozen generator: {BASE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def main() -> None:
    if (HOLDOUT / "results" / "run_manifest.json").exists():
        raise SystemExit("Refusing to rebuild: formal hold-out results already exist and bind the frozen case hashes.")

    base = load_base()
    selection = json.loads(CONFIG.read_text(encoding="utf-8"))
    evidence_rows = json.loads(
        (PHASE1 / "evidence" / "positive_event_evidence.json").read_text(encoding="utf-8")
    )
    evidence = {(x["project"], x["commit_id"]): x for x in evidence_rows}
    phase1_withheld = {
        (x["project"], x["commit_id"])
        for x in csv.DictReader(
            (PRETEST / "data" / "withheld_positive_cases.csv").open(encoding="utf-8", newline="")
        )
    }
    records: list[dict] = []
    for configured in selection["events"]:
        item = dict(configured)
        repo = base.PROJECTS / item["project"]
        item["commit"] = base.resolve(repo, item["commit"])
        key = (item["project"], item["commit"])
        if key not in phase1_withheld or key not in evidence:
            raise RuntimeError(f"event is not in the frozen eight-case hold-out: {key}")
        ev = evidence[key]
        item.update({
            "parent": ev["previous_commit"],
            "commit_time": ev["commit_time"],
            "artifact_classification": ev["artifact_classification"],
            "artifact_cause": ev["artifact_cause"],
            "harness_id": ev["harness_id"],
            "metric_before": ev["metrics"]["metric_before"],
            "metric_after": ev["metrics"]["metric_after"],
            "artifact_evidence": ev["artifact_evidence"],
        })
        records.append(item)

    if len(records) != 8 or {(x["project"], x["commit"]) for x in records} != phase1_withheld:
        raise RuntimeError("hold-out selection must equal the eight frozen phase-1 events")

    random.Random(selection["shuffle_seed"]).shuffle(records)
    for offset, item in enumerate(records):
        item["case_id"] = f"C{selection['case_id_start'] + offset:03d}"

    oss_history = base.load_oss_history()
    fixed = PROMPT.read_text(encoding="utf-8").rstrip()
    cases_dir = HOLDOUT / "cases"
    inputs_dir = HOLDOUT / "inputs"
    cases_dir.mkdir(parents=True, exist_ok=True)
    inputs_dir.mkdir(parents=True, exist_ok=True)
    for old in list(cases_dir.glob("C*.md")) + list(inputs_dir.glob("C*.txt")):
        old.unlink()

    mapping_rows: list[dict] = []
    materialization_rows: list[dict] = []
    for item in records:
        project = item["project"]
        repo = base.PROJECTS / project
        parent = item["parent"]
        commit = item["commit"]
        source_time = base.parse_iso(item["commit_time"])
        all_paths = base.changed_paths(repo, parent, commit)

        # The frozen task excludes fuzz/harness changes from Source Change. The base
        # classifier already excludes fuzz directory components; the explicit H0 list
        # also catches names such as tools/codecfuzz.cpp.
        known_harness = set(base.REPO_HARNESS_PATHS[project])
        excluded_harness = [p for p in all_paths if p in known_harness]
        production = [
            p for p in all_paths
            if base.is_production_source(p) and p not in known_harness
        ]
        preferred = [p for p in item.get("diff_paths", []) if p in production]
        diff_paths = preferred or production
        if diff_paths:
            diff_value = base.git(
                repo, "diff", "--no-ext-diff", "--unified=6", parent, commit,
                "--", *diff_paths,
            )
            diff_value = "\n".join(
                line for line in diff_value.splitlines() if not line.startswith("index ")
            ) + "\n"
            diff_value, excerpted = base.excerpt_diff(
                diff_value, item.get("mechanism_keywords", [])
            )
        else:
            diff_value, excerpted = "", False

        harness, harness_evidence, oss_rev = base.harness_sections(
            project, parent, source_time, oss_history
        )
        case_text = base.make_case(
            item["case_id"], harness, production, diff_value, excerpted
        )
        case_path = cases_dir / f"{item['case_id']}.md"
        base.write_text(case_path, case_text)
        exact_input = (
            fixed
            + "\n\n--- BEGIN ANONYMOUS CASE ---\n\n"
            + case_text
            + "\n--- END ANONYMOUS CASE ---\n"
        )
        input_path = inputs_dir / f"{item['case_id']}.txt"
        base.write_text(input_path, exact_input)
        case_sha = sha256_text(case_text)
        input_sha = sha256_text(exact_input)

        mapping_rows.append({
            "case_id": item["case_id"],
            "actual_label": "positive",
            "project": project,
            "commit_id": commit,
            "previous_commit": parent,
            "commit_time": item["commit_time"],
            "harness_id": item["harness_id"],
            "artifact_classification": item["artifact_classification"],
            "artifact_cause": item["artifact_cause"],
            "degradation_metric_before": item["metric_before"],
            "degradation_metric_after": item["metric_after"],
            "artifact_evidence": item["artifact_evidence"],
            "case_sha256": case_sha,
            "input_sha256": input_sha,
        })
        materialization_rows.append({
            "case_id": item["case_id"],
            "source_diff_paths": ";".join(diff_paths),
            "production_source_paths": ";".join(production),
            "excluded_harness_paths": ";".join(excluded_harness),
            "source_diff_empty": str(not diff_paths).lower(),
            "diff_excerpted": str(excerpted).lower(),
            "h0_evidence": ";".join(harness_evidence),
            "oss_fuzz_revision": oss_rev,
            "case_sha256": case_sha,
            "input_sha256": input_sha,
        })

    mapping_rows.sort(key=lambda x: x["case_id"])
    materialization_rows.sort(key=lambda x: x["case_id"])
    write_csv(HOLDOUT / "data" / "case_mapping.csv", mapping_rows, [
        "case_id", "actual_label", "project", "commit_id", "previous_commit",
        "commit_time", "harness_id", "artifact_classification", "artifact_cause",
        "degradation_metric_before", "degradation_metric_after", "artifact_evidence",
        "case_sha256", "input_sha256",
    ])
    write_csv(HOLDOUT / "data" / "case_materialization.csv", materialization_rows, [
        "case_id", "source_diff_paths", "production_source_paths",
        "excluded_harness_paths", "source_diff_empty", "diff_excerpted",
        "h0_evidence", "oss_fuzz_revision", "case_sha256", "input_sha256",
    ])
    base.write_text(HOLDOUT / "data" / "dataset_manifest.json", json.dumps({
        "status": "frozen_before_prediction",
        "cases": len(records),
        "case_ids": [x["case_id"] for x in mapping_rows],
        "shuffle_seed": selection["shuffle_seed"],
        "case_id_start": selection["case_id_start"],
        "fixed_prompt_sha256": hashlib.sha256(PROMPT.read_bytes()).hexdigest(),
        "generator_sha256": hashlib.sha256(BASE_PATH.read_bytes()).hexdigest(),
        "holdout_builder_sha256": hashlib.sha256(HERE.read_bytes()).hexdigest(),
        "selection_sha256": hashlib.sha256(CONFIG.read_bytes()).hexdigest(),
        "cases": [
            {
                "case_id": x["case_id"],
                "case_sha256": x["case_sha256"],
                "input_sha256": x["input_sha256"],
            }
            for x in mapping_rows
        ],
    }, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "cases": len(records),
        "case_ids": [x["case_id"] for x in mapping_rows],
        "empty_source_diff_cases": [
            x["case_id"] for x in materialization_rows if x["source_diff_empty"] == "true"
        ],
        "excerpted_cases": [
            x["case_id"] for x in materialization_rows if x["diff_excerpted"] == "true"
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
