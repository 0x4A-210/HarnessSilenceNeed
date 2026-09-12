#!/usr/bin/env python3
"""M0 oracle: exact GT target is intentionally allowed only in this evaluator."""
from __future__ import annotations

import argparse
import shutil
import tempfile
import time
from pathlib import Path

from build_callgraph import build_graph, catalogue, reachability_for_symbol
from common import ROOT, Timer, git_paths, is_production, materialize_snapshot, peak_rss_kib, read_csv, write_json
from static_reachability import attribute


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    case = next(row for row in read_csv(ROOT / "dataset" / "cases.csv") if row["case_id"] == args.case_id)
    gt = next(row for row in read_csv(ROOT / "dataset" / "gt_targets.csv") if row["case_id"] == args.case_id)
    started = time.perf_counter()
    if gt["exact_target_type"] != "FUNCTION_TARGET":
        write_json(args.output, {
            "case_id": args.case_id, "project": case["project"], "label": gt["label"],
            "target": gt["exact_target_config"] or gt["exact_target_state"],
            "target_type": gt["exact_target_type"], "expected_delta": gt["expected_delta"],
            "reachable_before": "NOT_APPLICABLE", "reachable_after": "NOT_APPLICABLE",
            "predicted_delta": "NOT_APPLICABLE", "maintenance_needed": "NOT_APPLICABLE",
            "applicable": False, "oracle_assisted": True,
            "reason": "exact target is non-function; function reachability cannot represent it",
            "total_time_seconds": time.perf_counter() - started, "peak_memory_kib": peak_rss_kib(),
        })
        return
    target = gt["exact_target_function"] or gt["exact_target_api"]
    with tempfile.TemporaryDirectory(prefix=f"t7-m0-{args.case_id}-") as temp:
        root0, root1 = Path(temp) / "s0", Path(temp) / "s1_with_h0"
        paths0 = git_paths(case["project"], case["s0_commit"])
        paths1 = git_paths(case["project"], case["s1_commit"])
        prod0 = [path for path in paths0 if is_production(path)]
        prod1 = [path for path in paths1 if is_production(path)]
        wanted_h0 = [x for x in case["h0_harness_paths"].split(";") if x]
        h0 = [path for path in wanted_h0 if path in set(paths0)]
        with Timer() as extraction:
            materialize_snapshot(case["project"], case["s0_commit"], sorted(set(prod0 + h0)), root0)
            materialize_snapshot(case["project"], case["s1_commit"], prod1, root1)
            for path in h0:
                destination = root1 / path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(root0 / path, destination)
            cat0 = catalogue(root0, sorted(set(prod0 + h0)), set(h0))
            cat1 = catalogue(root1, sorted(set(prod1 + h0)), set(h0))
        with Timer() as graph_time:
            graph0 = build_graph(root0, cat0["definitions"])
            graph1 = build_graph(root1, cat1["definitions"])
        with Timer() as reach_time:
            before = reachability_for_symbol(graph0, target)
            after = reachability_for_symbol(graph1, target)
            attribution = attribute(before["status"], after["status"],
                                    is_new=before["status"] == "NOT_PRESENT", exposure_changed=False)
        write_json(args.output, {
            "case_id": args.case_id, "project": case["project"], "label": gt["label"],
            "target": target, "target_type": gt["exact_target_type"],
            "expected_delta": gt["expected_delta"],
            "reachable_before": before["status"], "reachable_after": after["status"],
            "path_before": before.get("path", []), "path_after": after.get("path", []),
            "unresolved_indirect_calls_before": before.get("unresolved_indirect_calls", []),
            "unresolved_indirect_calls_after": after.get("unresolved_indirect_calls", []),
            "predicted_delta": attribution["delta"],
            "maintenance_needed": attribution["candidate_maintenance"],
            "applicable": attribution["candidate_maintenance"] in {"YES", "NO"},
            "oracle_assisted": True, "reason": attribution["attribution_reason"],
            "candidate_extraction_time_seconds": extraction.seconds,
            "callgraph_build_time_seconds": graph_time.seconds,
            "reachability_time_seconds": reach_time.seconds,
            "total_time_seconds": time.perf_counter() - started,
            "peak_memory_kib": peak_rss_kib(),
        })


if __name__ == "__main__":
    main()
