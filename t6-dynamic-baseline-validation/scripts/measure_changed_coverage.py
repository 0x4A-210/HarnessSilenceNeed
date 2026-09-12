#!/usr/bin/env python3
from __future__ import annotations

import gzip
import json
from collections import defaultdict
from pathlib import Path

from common import ROOT, read_csv, write_csv


def expand(spec: str) -> set[int]:
    values = set()
    for part in filter(None, spec.split(";")):
        if "-" in part:
            start, end = map(int, part.split("-", 1))
            values.update(range(start, end + 1))
        else:
            values.add(int(part))
    return values


def load_raw(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def compute_for_raw(raw: dict, changed: dict[str, set[int]]) -> dict:
    executable: set[tuple[str, int]] = set()
    covered: set[tuple[str, int]] = set()
    changed_functions: dict[tuple[str, str], bool] = {}
    for function in raw.get("functions", []):
        function_changed = False
        for region in function.get("regions", []):
            if len(region) < 6:
                continue
            start, _sc, end, _ec, count, file_id = region[:6]
            names = function.get("filenames", [])
            if not isinstance(file_id, int) or file_id >= len(names):
                continue
            path = names[file_id]
            if path is None or path not in changed:
                continue
            overlap = changed[path].intersection(range(int(start), int(end) + 1))
            if not overlap:
                continue
            function_changed = True
            for line in overlap:
                executable.add((path, line))
                if int(count) > 0:
                    covered.add((path, line))
        if function_changed:
            files = ";".join(x or "" for x in function.get("filenames", []))
            key = (function["name"], files)
            changed_functions[key] = changed_functions.get(key, False) or int(function.get("count", 0)) > 0
    return {
        "changed_executable_lines": len(executable),
        "changed_covered_lines": len(covered),
        "changed_line_coverage_percent": (100 * len(covered) / len(executable)
                                            if executable else None),
        "changed_functions": len(changed_functions),
        "changed_functions_reached": sum(changed_functions.values()),
        "changed_function_coverage_percent": (
            100 * sum(changed_functions.values()) / len(changed_functions)
            if changed_functions else None),
        "changed_function_names": ";".join(sorted(k[0] for k in changed_functions)),
    }


def main() -> None:
    change_rows = read_csv(ROOT / "dataset" / "changed_code.csv")
    by_case: dict[str, dict[str, set[int]]] = defaultdict(dict)
    for row in change_rows:
        by_case[row["case_id"]][row["path"]] = expand(row["s1_added_or_modified_lines"])
    out = []
    for path in sorted((ROOT / "raw" / "coverage").glob("*/s1/*.json.gz")):
        raw = load_raw(path)
        case_id = raw["case_id"]
        metrics = compute_for_raw(raw, by_case[case_id]) if raw.get("status") == "PASS" else {
            "changed_executable_lines": None, "changed_covered_lines": None,
            "changed_line_coverage_percent": None, "changed_functions": None,
            "changed_functions_reached": None,
            "changed_function_coverage_percent": None, "changed_function_names": "",
        }
        line_low = (metrics["changed_executable_lines"] or 0) > 0 and (
            metrics["changed_line_coverage_percent"] is not None and
            metrics["changed_line_coverage_percent"] < 10.0)
        function_zero = (metrics["changed_functions"] or 0) > 0 and (
            metrics["changed_function_coverage_percent"] == 0.0)
        out.append({
            "case_id": case_id, "project": raw.get("project"),
            "budget": raw["budget"], "repeat": raw["repeat"],
            "status": raw.get("status"), **metrics,
            "c1_low_changed_line_coverage": str(line_low).lower(),
            "c2_zero_changed_function_reachability": str(function_zero).lower(),
            "maintenance_prediction": ("YES" if line_low or function_zero else "NO")
                                      if raw.get("status") == "PASS" else "ABSTAIN",
            "rule": "changed executable line coverage <10% OR changed-function reachability =0%",
        })
    fields = ["case_id", "project", "budget", "repeat", "status",
              "changed_executable_lines", "changed_covered_lines",
              "changed_line_coverage_percent", "changed_functions",
              "changed_functions_reached", "changed_function_coverage_percent",
              "changed_function_names", "c1_low_changed_line_coverage",
              "c2_zero_changed_function_reachability", "maintenance_prediction", "rule"]
    write_csv(ROOT / "results" / "changed_code_coverage.csv", out, fields)


if __name__ == "__main__":
    main()
