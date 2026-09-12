#!/usr/bin/env python3
from __future__ import annotations

import gzip
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from common import ROOT, T5, read_csv, write_csv, write_json
from measure_changed_coverage import main as measure_changed
from measure_reachability import main as measure_reachability


def load_raw(path: Path) -> dict:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def fnum(value):
    if value in (None, "", "NA"):
        return None
    return float(value)


def prediction_metrics(rows: list[dict], labels: dict[str, str]) -> dict:
    by_case = {r["case_id"]: r["prediction"] for r in rows}
    tp = fn = fp = tn = 0
    abstain_pos = abstain_neg = 0
    for case_id, label in labels.items():
        pred = by_case.get(case_id, "ABSTAIN")
        if pred == "ABSTAIN":
            if label == "POSITIVE": abstain_pos += 1
            else: abstain_neg += 1
        elif label == "POSITIVE" and pred == "YES": tp += 1
        elif label == "POSITIVE": fn += 1
        elif pred == "YES": fp += 1
        else: tn += 1
    recall = tp / (tp + fn) if tp + fn else None
    fpr = fp / (fp + tn) if fp + tn else None
    precision = tp / (tp + fp) if tp + fp else None
    f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None
    return {
        "TP": tp, "FN": fn, "FP": fp, "TN": tn,
        "positive_evaluable": tp + fn, "n4_evaluable": fp + tn,
        "abstain_positive": abstain_pos, "abstain_n4": abstain_neg,
        "positive_recall_percent": None if recall is None else 100 * recall,
        "silent_recall_percent": None if recall is None else 100 * recall,
        "n4_fpr_percent": None if fpr is None else 100 * fpr,
        "overall_fpr_percent": None if fpr is None else 100 * fpr,
        "precision_percent": None if precision is None else 100 * precision,
        "f1_percent": None if f1 is None else 100 * f1,
        "intent_to_test_recall_percent": 100 * tp / 20,
        "execution_success_percent": 100 * (tp + fn + fp + tn) / 39,
    }


def oracle_low_threshold(signals: dict[str, float], labels: dict[str, str]) -> tuple[float, list[dict], dict]:
    values = sorted(set(signals.values()))
    thresholds = [values[0] - 1e-9] + [(a + b) / 2 for a, b in zip(values, values[1:])] + [values[-1] + 1e-9]
    best = None
    for threshold in thresholds:
        rows = [{"case_id": c, "prediction": "YES" if value < threshold else "NO"}
                for c, value in signals.items()]
        metric = prediction_metrics(rows, labels)
        score = (metric["f1_percent"] or -1, -(metric["n4_fpr_percent"] or 0),
                 metric["positive_recall_percent"] or -1)
        if best is None or score > best[0]:
            best = (score, threshold, rows, metric)
    assert best is not None
    return best[1], best[2], best[3]


def median_rows(rows: list[dict], numeric: list[str], prediction_field: str) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["case_id"]].append(row)
    out = []
    for case_id, items in grouped.items():
        row = {"case_id": case_id}
        for field in numeric:
            vals = [fnum(x.get(field)) for x in items]
            vals = [x for x in vals if x is not None]
            row[field] = statistics.median(vals) if vals else None
        votes = [x.get(prediction_field, "ABSTAIN") for x in items]
        non_abstain = [x for x in votes if x != "ABSTAIN"]
        row["prediction"] = Counter(non_abstain).most_common(1)[0][0] if non_abstain else "ABSTAIN"
        out.append(row)
    return out


def main() -> None:
    cases = read_csv(ROOT / "dataset" / "cases.csv")
    labels = {r["case_id"]: r["label"] for r in cases}
    raw_index = {}
    overall_rows = []
    for path in sorted((ROOT / "raw" / "coverage").glob("*/*/*.json.gz")):
        raw = load_raw(path)
        key = (raw["case_id"], raw["version"], raw["budget"], int(raw["repeat"]))
        raw_index[key] = raw
        totals = raw.get("totals", {})
        overall_rows.append({
            "case_id": raw["case_id"], "project": raw.get("project"),
            "version": raw["version"], "budget": raw["budget"],
            "repeat": raw["repeat"], "status": raw.get("status"),
            "line_count": totals.get("lines", {}).get("count"),
            "line_covered": totals.get("lines", {}).get("covered"),
            "line_coverage_percent": totals.get("lines", {}).get("percent"),
            "branch_count": totals.get("branches", {}).get("count"),
            "branch_covered": totals.get("branches", {}).get("covered"),
            "branch_coverage_percent": totals.get("branches", {}).get("percent"),
            "function_count": totals.get("functions", {}).get("count"),
            "function_covered": totals.get("functions", {}).get("covered"),
            "function_coverage_percent": totals.get("functions", {}).get("percent"),
        })
    write_csv(ROOT / "results" / "overall_coverage.csv", overall_rows,
              list(overall_rows[0]) if overall_rows else ["case_id"])

    overall_index = {(r["case_id"], r["version"], r["budget"], int(r["repeat"])): r
                     for r in overall_rows}
    delta_rows = []
    keys = sorted({(c, b, rep) for c, _v, b, rep in overall_index})
    for case_id, budget, repeat in keys:
        s0 = overall_index.get((case_id, "s0", budget, repeat))
        s1 = overall_index.get((case_id, "s1", budget, repeat))
        available = s0 and s1 and s0["status"] == "PASS" and s1["status"] == "PASS"
        row = {"case_id": case_id, "project": next(c["project"] for c in cases if c["case_id"] == case_id),
               "budget": budget, "repeat": repeat,
               "status": "PASS" if available else "COVERAGE_UNAVAILABLE"}
        declines = []
        for metric in ("line", "branch", "function"):
            before = fnum(s0[f"{metric}_coverage_percent"]) if available else None
            after = fnum(s1[f"{metric}_coverage_percent"]) if available else None
            row[f"s0_{metric}_coverage_percent"] = before
            row[f"s1_{metric}_coverage_percent"] = after
            row[f"delta_{metric}_coverage_pp"] = after - before if before is not None and after is not None else None
            if row[f"delta_{metric}_coverage_pp"] is not None:
                declines.append(row[f"delta_{metric}_coverage_pp"] < -1.0)
        row["maintenance_prediction"] = ("YES" if any(declines) else "NO") if available else "ABSTAIN"
        row["rule"] = "any line/branch/function production coverage delta < -1.0 percentage point"
        delta_rows.append(row)
    write_csv(ROOT / "results" / "coverage_delta.csv", delta_rows,
              list(delta_rows[0]) if delta_rows else ["case_id"])

    measure_changed()
    measure_reachability()
    changed = read_csv(ROOT / "results" / "changed_code_coverage.csv")
    reachability = read_csv(ROOT / "results" / "reachability.csv")

    build_rows = []
    failures = []
    for case in cases:
        builds = {}
        for version in ("s0", "s1"):
            path = ROOT / "raw" / "timings" / f"{case['case_id']}_{version}_build.json"
            builds[version] = json.loads(path.read_text()) if path.exists() else None
            if builds[version] is None or builds[version].get("status") != "PASS":
                failures.append({"case_id": case["case_id"], "project": case["project"],
                                 "version": version, "stage": "build", "budget": "NA",
                                 "repeat": "NA", "failure_type": "BUILD_UNAVAILABLE",
                                 "detail": "missing result" if builds[version] is None else builds[version].get("status")})
        s0_ok = builds["s0"] is not None and builds["s0"].get("status") == "PASS"
        s1_ok = builds["s1"] is not None and builds["s1"].get("status") == "PASS"
        s1_corpus = raw_index.get((case["case_id"], "s1", "corpus", 1))
        runtime_ok = s1_corpus is not None and s1_corpus.get("run_status") == "PASS"
        if not s0_ok:
            pred, status = "ABSTAIN", "BUILD_UNAVAILABLE"
        elif not s1_ok or not runtime_ok:
            pred, status = "YES", "S1_H0_EXPLICIT_FAILURE"
        else:
            pred, status = "NO", "PASS"
        build_rows.append({"case_id": case["case_id"], "project": case["project"],
                           "s0_build": str(s0_ok).lower(), "s1_build": str(s1_ok).lower(),
                           "s1_corpus_runtime": str(runtime_ok).lower(), "status": status,
                           "maintenance_prediction": pred})
    write_csv(ROOT / "results" / "build_only.csv", build_rows, list(build_rows[0]))

    for raw in raw_index.values():
        if raw.get("run_status") != "PASS":
            failures.append({"case_id": raw["case_id"], "project": raw.get("project"),
                             "version": raw["version"], "stage": "dynamic_run",
                             "budget": raw["budget"], "repeat": raw["repeat"],
                             "failure_type": raw.get("run_status"), "detail": "see raw logs"})
        if raw.get("status") != "PASS":
            failures.append({"case_id": raw["case_id"], "project": raw.get("project"),
                             "version": raw["version"], "stage": "coverage",
                             "budget": raw["budget"], "repeat": raw["repeat"],
                             "failure_type": "COVERAGE_UNAVAILABLE", "detail": raw.get("coverage_error", "")})
    failure_fields = ["case_id", "project", "version", "stage", "budget", "repeat", "failure_type", "detail"]
    write_csv(ROOT / "results" / "execution_failures.csv", failures, failure_fields)

    metric_rows = []
    method_predictions = []
    def add_metrics(method: str, budget: str, repeat: str, predictions: list[dict], oracle=False, rule=""):
        metric = prediction_metrics(predictions, labels)
        metric_rows.append({"method": method, "budget": budget, "repeat": repeat,
                            "oracle_post_hoc": str(oracle).lower(), "rule": rule, **metric})
        for item in predictions:
            method_predictions.append({"case_id": item["case_id"], "method": method,
                                       "budget": budget, "repeat": repeat,
                                       "prediction": item["prediction"],
                                       "label": labels[item["case_id"]],
                                       "correct": str((item["prediction"] == "YES") ==
                                                      (labels[item["case_id"]] == "POSITIVE")).lower()
                                                  if item["prediction"] != "ABSTAIN" else "NA"})

    add_metrics("Build-Only", "corpus", "1",
                [{"case_id": r["case_id"], "prediction": r["maintenance_prediction"]} for r in build_rows],
                rule="S0 success followed by S1 build/link/corpus-runtime failure")

    budget_repeats = sorted({(r["budget"], str(r["repeat"])) for r in delta_rows},
                            key=lambda x: ({"corpus":0,"1m":1,"5m":2,"15m":3}.get(x[0],9), int(x[1])))
    for budget, repeat in budget_repeats:
        dr = [r for r in delta_rows if r["budget"] == budget and str(r["repeat"]) == repeat]
        add_metrics("Overall Coverage Delta", budget, repeat,
                    [{"case_id": r["case_id"], "prediction": r["maintenance_prediction"]} for r in dr],
                    rule="any production coverage dimension declines >1pp")
        cr = [r for r in changed if r["budget"] == budget and str(r["repeat"]) == repeat]
        add_metrics("Changed-Code Coverage", budget, repeat,
                    [{"case_id": r["case_id"], "prediction": r["maintenance_prediction"]} for r in cr],
                    rule="changed line <10% or changed function =0%")
        rr = [r for r in reachability if r["budget"] == budget and str(r["repeat"]) == repeat]
        add_metrics("Function Reachability", budget, repeat,
                    [{"case_id": r["case_id"], "prediction": r["maintenance_prediction"]} for r in rr],
                    rule="temporal target reachability")
        s1r = [r for r in overall_rows if r["version"] == "s1" and r["budget"] == budget
               and str(r["repeat"]) == repeat and r["status"] == "PASS"
               and fnum(r["line_coverage_percent"]) is not None]
        signals = {r["case_id"]: fnum(r["line_coverage_percent"]) for r in s1r}
        if signals:
            threshold, preds, _metric = oracle_low_threshold(signals, labels)
            add_metrics("S1 Overall Coverage (oracle)", budget, repeat, preds, oracle=True,
                        rule=f"post-hoc low-line-coverage threshold={threshold:.9g}")

    # Reused Task-5 Delta-Aware output; no inference is performed here.
    outcomes = read_csv(T5 / "results" / "case_outcomes.csv")
    delta_predictions = [{"case_id": r["case_id"],
                          "prediction": "YES" if r["delta_maintenance_derived"] == "true" else "NO"}
                         for r in outcomes if r["case_id"] in labels]
    add_metrics("Delta-Aware", "static", "1", delta_predictions,
                rule="reused frozen Task-5 prediction")

    write_csv(ROOT / "results" / "classification_metrics.csv", metric_rows,
              list(metric_rows[0]))
    write_csv(ROOT / "results" / "case_predictions.csv", method_predictions,
              list(method_predictions[0]))

    # Runtime cost by case/budget/repeat. Build/checkouts are charged to every
    # end-to-end dynamic strategy because both snapshots are required.
    cost_rows = []
    for case in cases:
        builds = []
        for version in ("s0", "s1"):
            path = ROOT / "raw" / "timings" / f"{case['case_id']}_{version}_build.json"
            if path.exists(): builds.append(json.loads(path.read_text()))
        for budget, repeat in budget_repeats:
            raws = [raw_index.get((case["case_id"], v, budget, int(repeat))) for v in ("s0", "s1")]
            raws = [x for x in raws if x]
            fuzz_wall = sum(float(x.get("run", {}).get("wall_seconds", 0)) for x in raws)
            coverage_wall = sum(float(x.get("collection_wall_seconds", 0)) for x in raws)
            cpu = sum(float(x.get("run", {}).get("cpu_seconds", 0)) for x in raws)
            build_wall = sum(float(x.get("build_wall_seconds", 0)) for x in builds)
            checkout_wall = sum(float(x.get("checkout_time_seconds", 0)) for x in builds)
            build_cpu = sum(float(x.get("build_cpu_seconds") or 0) for x in builds)
            peak = max([float(x.get("run", {}).get("peak_memory_mb", 0)) for x in raws] or [0])
            cost_rows.append({"case_id": case["case_id"], "project": case["project"],
                              "budget": budget, "repeat": repeat,
                              "checkout_time_seconds": checkout_wall,
                              "build_time_seconds": build_wall,
                              "instrumentation_time_seconds": build_wall,
                              "corpus_or_fuzz_time_seconds": fuzz_wall,
                              "coverage_collection_time_seconds": coverage_wall,
                              "total_wall_clock_seconds": checkout_wall + build_wall + fuzz_wall + coverage_wall,
                              "cpu_seconds": build_cpu + cpu,
                              "peak_memory_mb_fuzz_only": peak,
                              "build_peak_memory": "UNAVAILABLE_DOCKER_LIMIT_4096MB",
                              "status": "PASS" if len(raws) == 2 and all(x.get("status") == "PASS" for x in raws) else "DYNAMIC_UNAVAILABLE"})
    write_csv(ROOT / "results" / "runtime_cost.csv", cost_rows, list(cost_rows[0]))

    # Compact budget comparison uses repeat 1; 5m variability remains available
    # as three separate rows in classification_metrics.csv.
    budget_rows = []
    dynamic_methods = {"Overall Coverage Delta", "Changed-Code Coverage", "Function Reachability"}
    for budget in ("corpus", "1m", "5m", "15m"):
        candidates = [r for r in metric_rows if r["method"] in dynamic_methods and
                      r["budget"] == budget and r["repeat"] == "1"]
        if not candidates: continue
        best = max(candidates, key=lambda r: ((r["f1_percent"] or -1),
                                             -(r["n4_fpr_percent"] or 100)))
        times = [float(r["total_wall_clock_seconds"]) for r in cost_rows
                 if r["budget"] == budget and r["repeat"] == "1" and r["status"] == "PASS"]
        budget_rows.append({"budget": budget, "best_dynamic_method": best["method"],
                            "silent_recall_percent": best["silent_recall_percent"],
                            "n4_fpr_percent": best["n4_fpr_percent"],
                            "median_time_seconds": statistics.median(times) if times else None,
                            "execution_success_percent": best["execution_success_percent"]})
    write_csv(ROOT / "results" / "budget_comparison.csv", budget_rows,
              list(budget_rows[0]) if budget_rows else ["budget"])

    summary = {"evaluated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
               "cases": 39, "positives": 20, "n4": 19,
               "dynamic_failures": len(failures),
               "metric_rows": len(metric_rows)}
    write_json(ROOT / "results" / "evaluation_summary.json", summary)


if __name__ == "__main__":
    main()
