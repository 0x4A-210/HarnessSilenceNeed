#!/usr/bin/env python3
"""Supplement frozen M1 Top-5 candidates with existing Task-6 corpus coverage."""
from __future__ import annotations

import gzip
import json

from common import ROOT, T6, normalize_symbol, read_csv, write_csv


def match_name(candidate: str, observed: str) -> bool:
    candidate = normalize_symbol(candidate).split("::")[-1]
    observed = normalize_symbol(observed).split("::")[-1]
    return candidate == observed


def main() -> None:
    rows = []
    for case in read_csv(ROOT / "dataset" / "cases.csv"):
        discovery = json.loads((ROOT / "target-discovery" / f'{case["case_id"]}.json').read_text())
        for version in ("s0", "s1"):
            coverage_path = T6 / "raw" / "coverage" / case["case_id"] / version / "corpus_r1.json.gz"
            coverage = None
            if coverage_path.is_file():
                with gzip.open(coverage_path, "rt", encoding="utf-8") as handle:
                    coverage = json.load(handle)
            for candidate in discovery["top_5"]:
                observed = [] if not coverage else [fn for fn in coverage.get("functions", [])
                                                    if match_name(candidate["target"], fn.get("name", ""))]
                rows.append({
                    "case_id": case["case_id"], "project": case["project"], "version": version,
                    "rank": candidate["rank"], "target": candidate["target"],
                    "target_type": candidate["target_type"],
                    "coverage_artifact": str(coverage_path.relative_to(ROOT.parent)) if coverage_path.is_file() else "",
                    "coverage_status": coverage.get("status", "") if coverage else "MISSING",
                    "mapped_function_count": len(observed),
                    "dynamic_reached": any(int(fn.get("count", 0)) > 0 for fn in observed),
                    "max_execution_count": max([int(fn.get("count", 0)) for fn in observed] or [0]),
                    "influenced_primary_m1_decision": False,
                })
    fields = ["case_id", "project", "version", "rank", "target", "target_type",
              "coverage_artifact", "coverage_status", "mapped_function_count", "dynamic_reached",
              "max_execution_count", "influenced_primary_m1_decision"]
    write_csv(ROOT / "results" / "dynamic_supplement.csv", rows, fields)
    summary = []
    for version in ("s0", "s1"):
        selected = [row for row in rows if row["version"] == version]
        available = [row for row in selected if row["coverage_status"] != "MISSING"]
        summary.append({
            "version": version, "candidate_rows": len(selected),
            "coverage_available_rows": len(available),
            "mapped_candidate_rows": sum(row["mapped_function_count"] > 0 for row in available),
            "dynamically_reached_rows": sum(row["dynamic_reached"] for row in available),
            "primary_decisions_changed": 0,
        })
    write_csv(ROOT / "results" / "dynamic_supplement_summary.csv", summary,
              ["version", "candidate_rows", "coverage_available_rows", "mapped_candidate_rows",
               "dynamically_reached_rows", "primary_decisions_changed"])


if __name__ == "__main__":
    main()
