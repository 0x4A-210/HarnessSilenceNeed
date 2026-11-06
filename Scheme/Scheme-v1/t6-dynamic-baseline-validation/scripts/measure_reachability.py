#!/usr/bin/env python3
from __future__ import annotations

import gzip
import json
from collections import defaultdict
from pathlib import Path

from common import ROOT, read_csv, write_csv


def load_raw(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def parse_anchors(value: str) -> list[tuple[str, int]]:
    result = []
    for entry in filter(None, value.split(";")):
        path, line = entry.rsplit(":", 1)
        result.append((path, int(line)))
    return result


def target_reached(raw: dict, anchors: list[tuple[str, int]], symbol: str) -> tuple[bool, int, str]:
    matched = []
    short = symbol.split("::")[-1].replace("operator=", "")
    for function in raw.get("functions", []):
        hit = False
        for region in function.get("regions", []):
            if len(region) < 6:
                continue
            start, _sc, end, _ec, _count, file_id = region[:6]
            names = function.get("filenames", [])
            if isinstance(file_id, int) and file_id < len(names):
                path = names[file_id]
                if any(path == anchor_path and int(start) <= line <= int(end)
                       for anchor_path, line in anchors):
                    hit = True
                    break
        if not hit and short and short in function.get("name", ""):
            hit = True
        if hit:
            matched.append(function)
    reached = any(int(x.get("count", 0)) > 0 for x in matched)
    return reached, len(matched), ";".join(sorted({x["name"] for x in matched}))


def main() -> None:
    cases = {r["case_id"]: r for r in read_csv(ROOT / "dataset" / "cases.csv")}
    anchors = {(r["case_id"], r["version"]): r
               for r in read_csv(ROOT / "dataset" / "target_anchors.csv")}
    raw_index = {}
    for path in sorted((ROOT / "raw" / "coverage").glob("*/*/*.json.gz")):
        raw = load_raw(path)
        raw_index[(raw["case_id"], raw["version"], raw["budget"], int(raw["repeat"]))] = raw
    out = []
    keys = sorted({(case, budget, repeat) for case, _version, budget, repeat in raw_index})
    for case_id, budget, repeat in keys:
        case = cases[case_id]
        values = {}
        status = "PASS"
        for version in ("s0", "s1"):
            anchor = anchors[(case_id, version)]
            raw = raw_index.get((case_id, version, budget, repeat))
            present = anchor["present"] == "true"
            if anchor["target_kind"] != "FUNCTION":
                values[version] = (present, None, 0, "")
            elif raw is None or raw.get("status") != "PASS":
                values[version] = (present, None, 0, "")
                status = "COVERAGE_UNAVAILABLE"
            else:
                reached, mapped, names = target_reached(
                    raw, parse_anchors(anchor["anchors"]), case["target_symbol"])
                values[version] = (present, reached, mapped, names)
        s0_present, s0_reached, s0_mapped, s0_names = values["s0"]
        s1_present, s1_reached, s1_mapped, s1_names = values["s1"]
        if anchors[(case_id, "s1")]["target_kind"] != "FUNCTION":
            prediction = "ABSTAIN"
            status = "NOT_APPLICABLE_NON_FUNCTION_TARGET"
        elif status != "PASS":
            prediction = "ABSTAIN"
        elif (not s0_present and s1_present and s1_reached is False) or (
                s0_reached is True and s1_reached is False):
            prediction = "YES"
        elif s0_present and s1_present and s0_reached is False and s1_reached is False:
            prediction = "NO"
        else:
            prediction = "NO"
        out.append({
            "case_id": case_id, "project": case["project"], "budget": budget,
            "repeat": repeat, "target_symbol": case["target_symbol"],
            "target_kind": anchors[(case_id, "s1")]["target_kind"],
            "s0_present": str(s0_present).lower(), "s1_present": str(s1_present).lower(),
            "s0_reached": "NA" if s0_reached is None else str(s0_reached).lower(),
            "s1_reached": "NA" if s1_reached is None else str(s1_reached).lower(),
            "s0_mapped_functions": s0_mapped, "s1_mapped_functions": s1_mapped,
            "s0_function_names": s0_names, "s1_function_names": s1_names,
            "status": status, "maintenance_prediction": prediction,
            "rule": "new-unreached or reached-to-unreached = YES; existing-unreached both = NO",
        })
    fields = ["case_id", "project", "budget", "repeat", "target_symbol",
              "target_kind", "s0_present", "s1_present", "s0_reached", "s1_reached",
              "s0_mapped_functions", "s1_mapped_functions", "s0_function_names",
              "s1_function_names", "status", "maintenance_prediction", "rule"]
    write_csv(ROOT / "results" / "reachability.csv", out, fields)


if __name__ == "__main__":
    main()
