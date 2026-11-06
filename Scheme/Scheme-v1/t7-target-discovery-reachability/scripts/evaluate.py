#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from common import ROOT, T5, percentile, read_csv, sha256_file, symbol_matches, utc_now, write_csv, write_json


def pct(numerator: int, denominator: int) -> str:
    return "NA" if denominator == 0 else f"{100 * numerator / denominator:.6f}"


def truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes"}


def prediction_expected(label: str) -> str:
    return "YES" if label == "POSITIVE" else "NO"


def verify_m1_freeze() -> dict:
    path = ROOT / "target-discovery" / "prediction_freeze_manifest.json"
    frozen = json.loads(path.read_text(encoding="utf-8"))
    mismatches = []
    for name, expected in frozen["per_file_sha256"].items():
        actual = sha256_file(ROOT / "target-discovery" / name)
        if actual != expected:
            mismatches.append({"file": name, "expected": expected, "actual": actual})
    if mismatches:
        raise SystemExit(f"M1 output changed after freeze: {mismatches}")
    return frozen


def metric_row(method: str, target_info: str, records: list[dict], attribution_correct: int,
               attribution_denominator: int, attribution_representable_denominator: int) -> dict:
    applicable = [row for row in records if row["evaluation_prediction"] in {"YES", "NO"}]
    positives = [row for row in records if row["label"] == "POSITIVE"]
    n4 = [row for row in records if row["label"] == "N4"]
    applicable_pos = [row for row in applicable if row["label"] == "POSITIVE"]
    applicable_n4 = [row for row in applicable if row["label"] == "N4"]
    tp = sum(row["evaluation_prediction"] == "YES" for row in positives)
    fp = sum(row["evaluation_prediction"] == "YES" for row in n4)
    cc_tp = sum(row["evaluation_prediction"] == "YES" for row in applicable_pos)
    cc_fp = sum(row["evaluation_prediction"] == "YES" for row in applicable_n4)
    return {
        "method": method, "target_info": target_info,
        "total_cases": len(records), "evaluable_cases": len(applicable),
        "applicability_percent": pct(len(applicable), len(records)),
        "complete_case_positive_denominator": len(applicable_pos),
        "complete_case_true_positive": cc_tp,
        "complete_case_positive_recall_percent": pct(cc_tp, len(applicable_pos)),
        "complete_case_n4_denominator": len(applicable_n4),
        "complete_case_false_positive": cc_fp,
        "complete_case_n4_fpr_percent": pct(cc_fp, len(applicable_n4)),
        "itt_positive_denominator": len(positives), "itt_true_positive": tp,
        "itt_positive_recall_percent": pct(tp, len(positives)),
        "itt_n4_denominator": len(n4), "itt_false_positive": fp,
        "itt_n4_fpr_percent": pct(fp, len(n4)),
        "strict_attribution_correct": attribution_correct,
        "strict_attribution_denominator": attribution_denominator,
        "strict_attribution_accuracy_percent": pct(attribution_correct, attribution_denominator),
        "representable_attribution_denominator": attribution_representable_denominator,
        "representable_attribution_accuracy_percent": pct(
            attribution_correct, attribution_representable_denominator),
        "abstain_or_not_applicable": len(records) - len(applicable),
    }


def main() -> None:
    output_freeze = verify_m1_freeze()
    cases = read_csv(ROOT / "dataset" / "cases.csv")
    gt_rows = read_csv(ROOT / "dataset" / "gt_targets.csv")
    gt = {row["case_id"]: row for row in gt_rows}
    discoveries = {row["case_id"]: json.loads(
        (ROOT / "target-discovery" / f'{row["case_id"]}.json').read_text(encoding="utf-8")) for row in cases}

    dataset_summary = []
    for project in sorted({row["project"] for row in cases}):
        selected = [row for row in cases if row["project"] == project]
        dataset_summary.append({
            "project": project, "cases": len(selected),
            "unique_s1_commits": len({row["s1_commit"] for row in selected}),
            "positive": sum(gt[row["case_id"]]["label"] == "POSITIVE" for row in selected),
            "n4": sum(gt[row["case_id"]]["label"] == "N4" for row in selected),
        })
    dataset_summary.append({
        "project": "TOTAL", "cases": len(cases),
        "unique_s1_commits": len({row["s1_commit"] for row in cases}),
        "positive": sum(row["label"] == "POSITIVE" for row in gt_rows),
        "n4": sum(row["label"] == "N4" for row in gt_rows),
    })
    write_csv(ROOT / "results" / "dataset_summary.csv", dataset_summary,
              ["project", "cases", "unique_s1_commits", "positive", "n4"])

    recall_rows = []
    diff_records: dict[int, list[dict]] = {1: [], 3: [], 5: []}
    n4_pattern_rows = []
    errors = []
    for case in cases:
        case_id = case["case_id"]
        answer = gt[case_id]
        discovery = discoveries[case_id]
        target = (answer["exact_target_function"] or answer["exact_target_api"]
                  or answer["exact_target_config"] or answer["exact_target_state"])
        hit_candidate = {}
        recall = {
            "case_id": case_id, "project": case["project"], "label": answer["label"],
            "exact_target_type": answer["exact_target_type"], "exact_target": target,
            "candidate_count": discovery["candidate_count"],
        }
        for k in (1, 3, 5):
            matching = next((candidate for candidate in discovery["candidates"][:k]
                             if symbol_matches(candidate["target"], target)), None)
            hit_candidate[k] = matching
            recall[f"top{k}_hit"] = bool(matching)
            recall[f"top{k}_rank"] = matching["rank"] if matching else ""
        recall_rows.append(recall)

        if not hit_candidate[5]:
            errors.append({
                "case_id": case_id, "project": case["project"], "label": answer["label"],
                "mode": "Top-5", "error_category": "E1_TARGET_MISS",
                "exact_target": target,
                "selected_targets": ";".join(x["target"] for x in discovery["top_5"]),
                "detail": "exact target absent from automatic Top-5",
            })
        if answer["exact_target_type"] != "FUNCTION_TARGET":
            errors.append({
                "case_id": case_id, "project": case["project"], "label": answer["label"],
                "mode": "all", "error_category": "E5_NON_FUNCTION_TARGET",
                "exact_target": target,
                "selected_targets": ";".join(x["target"] for x in discovery["top_5"]),
                "detail": "target discovered as non-function but function reachability is not applicable",
            })
        if any(candidate["reachable_before"] == "UNKNOWN" or candidate["reachable_after"] == "UNKNOWN"
               for candidate in discovery["top_5"] if candidate["target_type"] == "function"):
            errors.append({
                "case_id": case_id, "project": case["project"], "label": answer["label"],
                "mode": "Top-5", "error_category": "E6_INDIRECT_CALL",
                "exact_target": target,
                "selected_targets": ";".join(x["target"] for x in discovery["top_5"]),
                "detail": "at least one selected function has address-taken/indirect uncertainty",
            })

        for k in (1, 3, 5):
            aggregate = discovery["decisions"][f"top{k}"]
            raw_prediction = aggregate["maintenance_needed"]
            # Function-only baseline cannot become applicable to a known config target by
            # choosing an unrelated changed function. This correction happens only in evaluation.
            effective = ("NOT_APPLICABLE" if answer["exact_target_type"] != "FUNCTION_TARGET"
                         else raw_prediction)
            matching = hit_candidate[k]
            attribution_ok = bool(
                answer["exact_target_type"] == "FUNCTION_TARGET" and matching
                and matching["delta"] == answer["expected_delta"]
                and matching["candidate_maintenance"] == prediction_expected(answer["label"])
            )
            record = {
                "case_id": case_id, "project": case["project"], "label": answer["label"],
                "expected_maintenance": prediction_expected(answer["label"]),
                "exact_target_type": answer["exact_target_type"], "exact_target": target,
                "target_hit": bool(matching), "target_rank": matching["rank"] if matching else "",
                "selected_targets": ";".join(aggregate["selected_targets"]),
                "raw_aggregate_prediction": raw_prediction,
                "evaluation_prediction": effective,
                "applicable": effective in {"YES", "NO"},
                "classification_correct": effective == prediction_expected(answer["label"]),
                "expected_delta": answer["expected_delta"],
                "target_candidate_delta": matching["delta"] if matching else "TARGET_MISSED",
                "strict_attribution_correct": attribution_ok,
            }
            diff_records[k].append(record)
            if answer["label"] == "N4":
                pattern_ok = bool(matching and matching["reachable_before"] != "NOT_PRESENT"
                                  and matching["reachable_after"] != "NOT_PRESENT"
                                  and matching["delta"] == "UNCHANGED"
                                  and matching["candidate_maintenance"] == "NO")
                n4_pattern_rows.append({
                    "case_id": case_id, "project": case["project"], "mode": f"Top-{k}",
                    "exact_target": target, "target_hit": bool(matching),
                    "reachable_before": matching["reachable_before"] if matching else "TARGET_MISSED",
                    "reachable_after": matching["reachable_after"] if matching else "TARGET_MISSED",
                    "candidate_delta": matching["delta"] if matching else "TARGET_MISSED",
                    "target_pattern_correct": pattern_ok,
                })

    recall_fields = ["case_id", "project", "label", "exact_target_type", "exact_target",
                     "candidate_count", "top1_hit", "top1_rank", "top3_hit", "top3_rank",
                     "top5_hit", "top5_rank"]
    write_csv(ROOT / "results" / "target_recall.csv", recall_rows, recall_fields)
    scopes = [
        ("ALL", lambda row: True),
        ("FUNCTION_API", lambda row: row["exact_target_type"] == "FUNCTION_TARGET"),
        ("STATE_CONFIG", lambda row: row["exact_target_type"] in {"NON_FUNCTION_CONFIG", "NON_FUNCTION_STATE"}),
        ("NON_FUNCTION", lambda row: row["exact_target_type"] != "FUNCTION_TARGET"),
        ("POSITIVE_FUNCTION_API", lambda row: row["label"] == "POSITIVE" and row["exact_target_type"] == "FUNCTION_TARGET"),
        ("N4_FUNCTION_API", lambda row: row["label"] == "N4" and row["exact_target_type"] == "FUNCTION_TARGET"),
    ]
    recall_summary = []
    for scope, predicate in scopes:
        selected = [row for row in recall_rows if predicate(row)]
        for k in (1, 3, 5):
            hits = sum(truthy(str(row[f"top{k}_hit"])) for row in selected)
            recall_summary.append({"scope": scope, "top_k": k, "hits": hits,
                                   "total": len(selected), "recall_percent": pct(hits, len(selected))})
    write_csv(ROOT / "results" / "target_recall_summary.csv", recall_summary,
              ["scope", "top_k", "hits", "total", "recall_percent"])

    diff_fields = ["case_id", "project", "label", "expected_maintenance", "exact_target_type",
                   "exact_target", "target_hit", "target_rank", "selected_targets",
                   "raw_aggregate_prediction", "evaluation_prediction", "applicable",
                   "classification_correct", "expected_delta", "target_candidate_delta",
                   "strict_attribution_correct"]
    for k in (1, 3, 5):
        write_csv(ROOT / "results" / f"diff_reachability_top{k}.csv", diff_records[k], diff_fields)
    write_csv(ROOT / "results" / "n4_target_pattern.csv", n4_pattern_rows,
              ["case_id", "project", "mode", "exact_target", "target_hit", "reachable_before",
               "reachable_after", "candidate_delta", "target_pattern_correct"])

    # Reuse frozen M2 predictions and their original measured durations; no rerun.
    outcomes = {row["case_id"]: row for row in read_csv(T5 / "results" / "case_outcomes.csv")}
    manifest = json.loads((T5 / "predictions" / "run_manifest_delta_aware.json").read_text())
    duration = {row["case_id"]: row["duration_seconds"] for row in manifest["attempts"]}
    delta_records = []
    for case in cases:
        source = outcomes[case["case_id"]]
        predicted = "YES" if truthy(source["delta_maintenance_derived"]) else "NO"
        delta_records.append({
            "case_id": case["case_id"], "project": case["project"], "label": gt[case["case_id"]]["label"],
            "maintenance_prediction": predicted,
            "evaluation_prediction": predicted, "applicable": True,
            "classification_correct": truthy(source["delta_correct"]),
            "delta_attribution": source["delta_attribution"],
            "attribution_correct": truthy(source["delta_attribution_correct"]),
            "duration_seconds": duration[case["case_id"]],
            "model": manifest["model"], "reasoning_effort": manifest["reasoning_effort"],
            "reused_frozen_prediction": True,
        })
    write_csv(ROOT / "results" / "delta_aware.csv", delta_records,
              ["case_id", "project", "label", "maintenance_prediction", "evaluation_prediction",
               "applicable", "classification_correct", "delta_attribution", "attribution_correct",
               "duration_seconds", "model", "reasoning_effort", "reused_frozen_prediction"])

    m0_source = read_csv(ROOT / "results" / "exact_target_oracle.csv")
    m0_records = [{**row, "evaluation_prediction": row["maintenance_needed"]} for row in m0_source]
    metrics = []
    m0_attr = sum(row["applicable"] == "True" and row["predicted_delta"] == row["expected_delta"]
                  for row in m0_source)
    metrics.append(metric_row("M0 Exact-Target Reachability (ORACLE)", "GT exact target",
                              m0_records, m0_attr, len(m0_source),
                              sum(row["target_type"] == "FUNCTION_TARGET" for row in m0_source)))
    for k in (1, 3, 5):
        attr = sum(row["strict_attribution_correct"] for row in diff_records[k])
        metrics.append(metric_row(f"M1 Diff-Derived Reachability Top-{k}", "automatic production diff",
                                  diff_records[k], attr, len(diff_records[k]),
                                  sum(row["exact_target_type"] == "FUNCTION_TARGET" for row in diff_records[k])))
    metrics.append(metric_row("M2 Delta-Aware v2", "semantic; frozen LLM", delta_records,
                              sum(row["attribution_correct"] for row in delta_records), len(delta_records),
                              len(delta_records)))
    metric_fields = list(metrics[0])
    write_csv(ROOT / "results" / "comparison.csv", metrics, metric_fields)
    write_csv(ROOT / "results" / "applicability.csv", [{
        "method": row["method"], "evaluable_cases": row["evaluable_cases"],
        "total_cases": row["total_cases"], "applicability_percent": row["applicability_percent"],
        "abstain_or_not_applicable": row["abstain_or_not_applicable"],
    } for row in metrics], ["method", "evaluable_cases", "total_cases", "applicability_percent",
                            "abstain_or_not_applicable"])

    latency_rows = []
    for case in cases:
        discovery = discoveries[case["case_id"]]
        timing = discovery["timing"]
        latency_rows.append({
            "case_id": case["case_id"], "project": case["project"], "method": "M1 Diff-Derived Reachability",
            "diff_parse_time_seconds": timing["diff_parse_time_seconds"],
            "candidate_extraction_time_seconds": timing["candidate_extraction_time_seconds"],
            "callgraph_build_time_seconds": timing["callgraph_build_time_seconds"],
            "reachability_time_seconds": timing["reachability_time_seconds"],
            "input_prep_time_seconds": "NA", "inference_time_seconds": "NA",
            "total_time_seconds": timing["total_time_seconds"],
            "peak_memory_kib": timing["peak_memory_kib"], "input_tokens": "NOT_EXPOSED",
            "output_tokens": "NOT_EXPOSED", "cost_usd": "NOT_EXPOSED",
        })
        d = next(row for row in delta_records if row["case_id"] == case["case_id"])
        latency_rows.append({
            "case_id": case["case_id"], "project": case["project"], "method": "M2 Delta-Aware v2",
            "diff_parse_time_seconds": "NA", "candidate_extraction_time_seconds": "NA",
            "callgraph_build_time_seconds": "NA", "reachability_time_seconds": "NA",
            "input_prep_time_seconds": "NOT_SEPARATELY_INSTRUMENTED",
            "inference_time_seconds": d["duration_seconds"], "total_time_seconds": d["duration_seconds"],
            "peak_memory_kib": "NOT_EXPOSED", "input_tokens": "NOT_EXPOSED",
            "output_tokens": "NOT_EXPOSED", "cost_usd": "NOT_EXPOSED",
        })
    latency_fields = list(latency_rows[0])
    write_csv(ROOT / "results" / "latency.csv", latency_rows, latency_fields)
    latency_summary = []
    for method in ("M1 Diff-Derived Reachability", "M2 Delta-Aware v2"):
        values = [float(row["total_time_seconds"]) for row in latency_rows if row["method"] == method]
        memories = [float(row["peak_memory_kib"]) for row in latency_rows
                    if row["method"] == method and str(row["peak_memory_kib"]).replace(".", "", 1).isdigit()]
        latency_summary.append({
            "method": method, "cases": len(values), "median_total_seconds": f"{percentile(values, .5):.6f}",
            "p90_total_seconds": f"{percentile(values, .9):.6f}",
            "median_peak_memory_kib": (f"{percentile(memories, .5):.1f}" if memories else "NOT_EXPOSED"),
            "p90_peak_memory_kib": (f"{percentile(memories, .9):.1f}" if memories else "NOT_EXPOSED"),
        })
    write_csv(ROOT / "results" / "latency_summary.csv", latency_summary,
              ["method", "cases", "median_total_seconds", "p90_total_seconds",
               "median_peak_memory_kib", "p90_peak_memory_kib"])

    # Add outcome-linked error categories after all decisions are known.
    for k in (1, 3, 5):
        for row in diff_records[k]:
            if row["label"] == "N4" and row["evaluation_prediction"] == "YES":
                errors.append({
                    "case_id": row["case_id"], "project": row["project"], "label": row["label"],
                    "mode": f"Top-{k}", "error_category": "E2_TARGET_OVERGENERATION",
                    "exact_target": row["exact_target"], "selected_targets": row["selected_targets"],
                    "detail": "newly inferred selected target caused an N4 false positive",
                })
            if row["label"] == "POSITIVE" and row["evaluation_prediction"] != "YES":
                category = "E5_NON_FUNCTION_TARGET" if row["exact_target_type"] != "FUNCTION_TARGET" else (
                    "E1_TARGET_MISS" if not row["target_hit"] else "E4_EXISTING_GAP_ATTRIBUTION")
                errors.append({
                    "case_id": row["case_id"], "project": row["project"], "label": row["label"],
                    "mode": f"Top-{k}", "error_category": category,
                    "exact_target": row["exact_target"], "selected_targets": row["selected_targets"],
                    "detail": f'positive prediction was {row["evaluation_prediction"]}',
                })
    error_fields = ["case_id", "project", "label", "mode", "error_category",
                    "exact_target", "selected_targets", "detail"]
    write_csv(ROOT / "results" / "error_analysis.csv", errors, error_fields)

    delta_metric = metrics[-1]
    delta_latency = next(row for row in latency_summary if row["method"] == "M2 Delta-Aware v2")
    m1_latency = next(row for row in latency_summary if row["method"] == "M1 Diff-Derived Reachability")
    gate_rows = []
    for k, metric in zip((1, 3, 5), metrics[1:4]):
        recall_pass = float(metric["itt_positive_recall_percent"]) >= float(delta_metric["itt_positive_recall_percent"]) - 5
        fpr_pass = float(metric["itt_n4_fpr_percent"]) <= float(delta_metric["itt_n4_fpr_percent"]) + 5
        applicability_pass = float(metric["applicability_percent"]) >= 95
        latency_pass = float(m1_latency["median_total_seconds"]) <= float(delta_latency["median_total_seconds"])
        complexity_pass = True
        all_pass = all((recall_pass, fpr_pass, applicability_pass, latency_pass, complexity_pass))
        gate_rows.append({
            "mode": f"Top-{k}",
            "itt_recall_percent": metric["itt_positive_recall_percent"],
            "required_recall_percent": f'{float(delta_metric["itt_positive_recall_percent"]) - 5:.6f}',
            "recall_pass": recall_pass,
            "n4_fpr_percent": metric["itt_n4_fpr_percent"],
            "maximum_fpr_percent": f'{float(delta_metric["itt_n4_fpr_percent"]) + 5:.6f}',
            "fpr_pass": fpr_pass,
            "applicability_percent": metric["applicability_percent"],
            "applicability_pass": applicability_pass,
            "m1_median_latency_seconds": m1_latency["median_total_seconds"],
            "delta_median_latency_seconds": delta_latency["median_total_seconds"],
            "latency_pass": latency_pass, "complexity_reasonable": complexity_pass,
            "all_kill_conditions_pass": all_pass,
            "gate_outcome": "KILL" if all_pass else "CONTINUE",
        })
    write_csv(ROOT / "results" / "kill_gate.csv", gate_rows, list(gate_rows[0]))

    n4_summary = []
    for k in (1, 3, 5):
        selected = [row for row in n4_pattern_rows if row["mode"] == f"Top-{k}"]
        correct = sum(row["target_pattern_correct"] for row in selected)
        n4_summary.append({"mode": f"Top-{k}", "correct": correct, "total": len(selected),
                           "accuracy_percent": pct(correct, len(selected))})
    write_csv(ROOT / "results" / "n4_target_pattern_summary.csv", n4_summary,
              ["mode", "correct", "total", "accuracy_percent"])

    write_json(ROOT / "results" / "evaluation_summary.json", {
        "evaluated_at": utc_now(), "case_count": len(cases),
        "positive_count": sum(row["label"] == "POSITIVE" for row in gt_rows),
        "n4_count": sum(row["label"] == "N4" for row in gt_rows),
        "m1_output_frozen_at": output_freeze["frozen_at"],
        "m1_output_aggregate_sha256": output_freeze["aggregate_sha256"],
        "m1_outputs_unchanged_at_evaluation": True,
        "methods": metrics, "target_recall": recall_summary,
        "n4_target_pattern": n4_summary, "latency": latency_summary,
        "kill_gate": gate_rows,
        "overall_decision": "KILL" if any(row["all_kill_conditions_pass"] for row in gate_rows) else "CONTINUE",
        "hybrid_executed": False,
        "hybrid_reason": "Task 7 permits Hybrid only for MAJOR WEAKENING; observed gate maps to CONTINUE.",
    })


if __name__ == "__main__":
    main()
