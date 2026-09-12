#!/usr/bin/env python3
"""Run deterministic target discovery for one case; this module never opens GT files."""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import time
from pathlib import Path

from build_callgraph import build_graph, catalogue, ctags_version, reachability_for_symbol
from common import (ROOT, Timer, git_paths, is_production, materialize_snapshot,
                    normalize_symbol, peak_rss_kib, read_csv, utc_now, write_json)
from extract_diff_targets import intersects, production_diff
from rank_targets import rank_candidates
from static_reachability import aggregate, attribute


ALLOWED_CASE_FIELDS = {
    "case_id", "project", "s0_commit", "s1_commit", "commit_time",
    "h0_harness_paths", "phase",
}


def _headers(tags: list[dict]) -> set[str]:
    return {tag["canonical"] for tag in tags
            if Path(tag["path"]).suffix.lower() in {".h", ".hh", ".hpp", ".hxx"}
            and tag["kind"] in {"prototype", "function", "method"}}


def _same_symbol(a: str, b: str) -> bool:
    a = normalize_symbol(a)
    b = normalize_symbol(b)
    return a == b or a.endswith("::" + b) or b.endswith("::" + a)


def _definition_exists(definitions: list[dict], symbol: str) -> bool:
    return any(_same_symbol(item["canonical"], symbol) for item in definitions)


def _signatures(definitions: list[dict], symbol: str) -> set[str]:
    return {item["signature"] for item in definitions if _same_symbol(item["canonical"], symbol)}


def _merge_candidate(store: dict[str, dict], item: dict) -> None:
    key = normalize_symbol(item["target"])
    if key not in store:
        store[key] = item
        return
    old = store[key]
    old["reason"] = sorted(set(old["reason"] + item["reason"]))
    old["is_public"] = old["is_public"] or item["is_public"]
    old["file_scope"] = old["file_scope"] and item["file_scope"]
    old["public_declaration_changed"] = (
        old.get("public_declaration_changed", False)
        or item.get("public_declaration_changed", False)
    )
    if item.get("line", 10**9) < old.get("line", 10**9):
        old["source"] = item["source"]
        old["line"] = item["line"]
        old["end"] = item["end"]


def _extract_candidates(diff: dict, s0_catalogue: dict, s1_catalogue: dict) -> list[dict]:
    old_defs = s0_catalogue["definitions"]
    new_defs = s1_catalogue["definitions"]
    old_public = _headers(s0_catalogue["tags"])
    new_public = _headers(s1_catalogue["tags"])
    store: dict[str, dict] = {}
    changed_function_symbols = set()

    for node in new_defs:
        changed_lines = diff["changed_lines_s1"].get(node["path"], [])
        if not changed_lines or not intersects(changed_lines, node["line"], node["end"]):
            continue
        symbol = node["canonical"]
        exists = _definition_exists(old_defs, symbol)
        is_public = (not node["file_scope"] or node["canonical"] in new_public
                     or node["name"] in {x.split("::")[-1] for x in new_public})
        item = {
            "target": symbol,
            "target_type": "function",
            "candidate_kind": "modified_function" if exists else "new_function",
            "source": node["path"],
            "line": node["line"],
            "end": node["end"],
            "reason": ["modified_function_body" if exists else "newly_added_function"],
            "is_new": not exists,
            "is_modified": exists,
            "is_public": is_public,
            "file_scope": node["file_scope"],
            "test_only": False,
            "state_config_handler": any(token in symbol.lower() for token in ("state", "mode", "config")),
            "public_declaration_changed": False,
            "signature_changed": exists and _signatures(old_defs, symbol) != _signatures(new_defs, symbol),
            "definition_node_ids": [node["id"]],
        }
        _merge_candidate(store, item)
        changed_function_symbols.add(normalize_symbol(symbol))

    # A changed public declaration can identify an implementation whose body itself was untouched.
    for tag in s1_catalogue["tags"]:
        suffix = Path(tag["path"]).suffix.lower()
        changed_lines = diff["changed_lines_s1"].get(tag["path"], [])
        if suffix not in {".h", ".hh", ".hpp", ".hxx"} or tag["kind"] not in {"prototype", "function", "method"}:
            continue
        if not changed_lines or not intersects(changed_lines, tag["line"], tag["end"]):
            continue
        matching_defs = [node for node in new_defs if _same_symbol(node["canonical"], tag["canonical"])]
        exemplar = matching_defs[0] if matching_defs else tag
        exists = _definition_exists(old_defs, tag["canonical"])
        item = {
            "target": exemplar["canonical"],
            "target_type": "function",
            "candidate_kind": "modified_public_api" if exists else "new_public_api",
            "source": exemplar["path"],
            "line": exemplar["line"],
            "end": exemplar["end"],
            "reason": ["changed_public_api_declaration"],
            "is_new": not exists,
            "is_modified": exists,
            "is_public": True,
            "file_scope": False,
            "test_only": False,
            "state_config_handler": any(token in tag["canonical"].lower() for token in ("state", "mode", "config")),
            "public_declaration_changed": True,
            "signature_changed": exists and _signatures(old_defs, tag["canonical"]) != _signatures(new_defs, tag["canonical"]),
            "definition_node_ids": [node["id"] for node in matching_defs],
        }
        _merge_candidate(store, item)
        changed_function_symbols.add(normalize_symbol(exemplar["canonical"]))

    old_nonfunctions = {normalize_symbol(tag["canonical"]) for tag in s0_catalogue["tags"]
                        if tag["kind"] in {"macro", "enumerator", "enum"}}
    for tag in s1_catalogue["tags"]:
        if tag["kind"] not in {"macro", "enumerator", "enum"}:
            continue
        lines = diff["changed_lines_s1"].get(tag["path"], [])
        if not lines or not intersects(lines, tag["line"], tag["end"]):
            continue
        symbol = tag["canonical"]
        is_new = normalize_symbol(symbol) not in old_nonfunctions
        _merge_candidate(store, {
            "target": symbol,
            "target_type": "non_function",
            "candidate_kind": "new_enum_state_config_macro" if is_new else "modified_enum_state_config_macro",
            "source": tag["path"],
            "line": tag["line"],
            "end": tag["end"],
            "reason": ["new_or_modified_enum_state_config_macro"],
            "is_new": is_new,
            "is_modified": not is_new,
            "is_public": Path(tag["path"]).suffix.lower() in {".h", ".hh", ".hpp", ".hxx"},
            "file_scope": False,
            "test_only": False,
            "state_config_handler": True,
            "public_declaration_changed": False,
            "signature_changed": False,
            "definition_node_ids": [],
        })
    return list(store.values())


def discover(case: dict) -> dict:
    if set(case) != ALLOWED_CASE_FIELDS:
        raise RuntimeError(f"M1 case schema violation: {sorted(set(case) - ALLOWED_CASE_FIELDS)}")
    total_started = time.perf_counter()
    case_id = case["case_id"]
    project = case["project"]
    h0_requested = [item for item in case["h0_harness_paths"].split(";") if item]
    timing = {}
    with Timer() as timer:
        diff = production_diff(project, case["s0_commit"], case["s1_commit"])
    timing["diff_parse_time_seconds"] = timer.seconds

    with tempfile.TemporaryDirectory(prefix=f"t7-{case_id}-") as temp:
        temp_path = Path(temp)
        root0 = temp_path / "s0"
        root1 = temp_path / "s1_with_h0"
        with Timer() as timer:
            paths0_all = git_paths(project, case["s0_commit"])
            paths1_all = git_paths(project, case["s1_commit"])
            prod0 = [path for path in paths0_all if is_production(path)]
            prod1 = [path for path in paths1_all if is_production(path)]
            h0 = [path for path in h0_requested if path in set(paths0_all)]
            materialize_snapshot(project, case["s0_commit"], sorted(set(prod0 + h0)), root0)
            materialize_snapshot(project, case["s1_commit"], prod1, root1)
            for path in h0:
                target = root1 / path
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(root0 / path, target)
            cat0 = catalogue(root0, sorted(set(prod0 + h0)), set(h0))
            cat1 = catalogue(root1, sorted(set(prod1 + h0)), set(h0))
            candidates = _extract_candidates(diff, cat0, cat1)
        timing["candidate_extraction_time_seconds"] = timer.seconds

        with Timer() as timer:
            graph0 = build_graph(root0, cat0["definitions"])
            graph1 = build_graph(root1, cat1["definitions"])
        timing["callgraph_build_time_seconds"] = timer.seconds

        # T4 connection: a changed candidate directly calls a newly added candidate.
        candidate_symbols = {normalize_symbol(item["target"]): item for item in candidates}
        changed_nodes = set()
        for item in candidates:
            if item["target_type"] == "function" and item["is_modified"]:
                changed_nodes.update(node_id for node_id, node in graph1["nodes"].items()
                                     if _same_symbol(node["canonical"], item["target"]))
        called_from_changed = set()
        for node_id in changed_nodes:
            for target_id in graph1["edges"].get(node_id, []):
                called_from_changed.add(normalize_symbol(graph1["nodes"][target_id]["canonical"]))

        with Timer() as timer:
            attributed = []
            for item in candidates:
                item = dict(item)
                item["connected_changed_caller"] = item["is_new"] and any(
                    _same_symbol(item["target"], called) for called in called_from_changed)
                if item["target_type"] == "non_function":
                    item.update({
                        "reachable_before": "NOT_APPLICABLE",
                        "reachable_after": "NOT_APPLICABLE",
                        "path_before": [], "path_after": [],
                        "unresolved_indirect_calls_before": [],
                        "unresolved_indirect_calls_after": [],
                        "delta": "NOT_APPLICABLE",
                        "candidate_maintenance": "ABSTAIN",
                        "attribution_reason": "non-function candidate cannot be represented by function reachability",
                    })
                else:
                    before = reachability_for_symbol(graph0, item["target"])
                    after = reachability_for_symbol(graph1, item["target"])
                    item.update({
                        "reachable_before": before["status"],
                        "reachable_after": after["status"],
                        "path_before": before.get("path", []),
                        "path_after": after.get("path", []),
                        "unresolved_indirect_calls_before": before.get("unresolved_indirect_calls", []),
                        "unresolved_indirect_calls_after": after.get("unresolved_indirect_calls", []),
                        "indirect_evidence_before": before.get("indirect_evidence_callers", []),
                        "indirect_evidence_after": after.get("indirect_evidence_callers", []),
                    })
                    item.update(attribute(
                        before["status"], after["status"], is_new=item["is_new"],
                        exposure_changed=bool(item["signature_changed"] and item["public_declaration_changed"]),
                    ))
                attributed.append(item)
            ranked = rank_candidates(attributed)
        timing["reachability_time_seconds"] = timer.seconds

        decisions = {f"top{k}": aggregate(ranked, k) for k in (1, 3, 5)}
        timing["total_time_seconds"] = time.perf_counter() - total_started
        timing["peak_memory_kib"] = peak_rss_kib()
        return {
            "schema_version": "t7-m1-v1",
            "case_id": case_id,
            "project": project,
            "s0_commit": case["s0_commit"],
            "s1_commit": case["s1_commit"],
            "h0_harness_paths_requested": h0_requested,
            "h0_harness_paths_materialized": h0,
            "method": "M1_DIFF_DERIVED_REACHABILITY_V1",
            "uses_ground_truth_target": False,
            "uses_llm": False,
            "uses_h1_or_harness_diff": False,
            "created_at": utc_now(),
            "tool": ctags_version(),
            "diff_summary": {
                "production_files_s0": diff["production_files_s0"],
                "production_files_s1": diff["production_files_s1"],
                "changed_line_count_s0": sum(map(len, diff["changed_lines_s0"].values())),
                "changed_line_count_s1": sum(map(len, diff["changed_lines_s1"].values())),
                "raw_diff_bytes": diff["raw_diff_bytes"],
            },
            "catalogue_summary": {
                "s0_function_definitions": len(cat0["definitions"]),
                "s1_function_definitions": len(cat1["definitions"]),
                "s0_tags": len(cat0["tags"]), "s1_tags": len(cat1["tags"]),
                "s0_ctags_exit_code": cat0.get("ctags_exit_code"),
                "s1_ctags_exit_code": cat1.get("ctags_exit_code"),
                "s0_parse_errors": cat0["parse_errors"], "s1_parse_errors": cat1["parse_errors"],
            },
            "callgraph_summary": {
                "s0_nodes": len(graph0["nodes"]), "s1_nodes": len(graph1["nodes"]),
                "s0_edges": sum(map(len, graph0["edges"].values())),
                "s1_edges": sum(map(len, graph1["edges"].values())),
                "s0_entry_nodes": [graph0["nodes"][x]["canonical"] for x in graph0["entry_nodes"]],
                "s1_entry_nodes": [graph1["nodes"][x]["canonical"] for x in graph1["entry_nodes"]],
                "s0_reachable_nodes": len(graph0["reachable_nodes"]),
                "s1_reachable_nodes": len(graph1["reachable_nodes"]),
            },
            "candidate_count": len(ranked),
            "candidates": ranked,
            "top_1": ranked[:1], "top_3": ranked[:3], "top_5": ranked[:5],
            "decisions": decisions,
            "timing": timing,
            "access_audit": {
                "allowed_input": "dataset/cases.csv (one row)",
                "forbidden_inputs_opened": [],
                "ground_truth_target_opened": False,
                "label_opened": False,
                "h1_opened": False,
            },
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [row for row in read_csv(ROOT / "dataset" / "cases.csv") if row["case_id"] == args.case_id]
    if len(rows) != 1:
        raise SystemExit(f"expected one case row for {args.case_id}, got {len(rows)}")
    write_json(args.output, discover(rows[0]))


if __name__ == "__main__":
    main()
