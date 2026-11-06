#!/usr/bin/env python3
"""Post-freeze reporting and integrity audit for the Task-6 Phase-A run.

This script does not collect coverage and does not alter any preregistered rule.
It aggregates the frozen evaluator's per-repeat predictions, separates a known
TemporaryDirectory cleanup exception from measurement failures, and records
artifact hashes.  Run it only after run_phase_a.py and
evaluate_dynamic_baselines.py have completed.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
BUDGET_ORDER = {"corpus": 0, "1m": 1, "5m": 2, "15m": 3, "30m": 4, "static": 5}
DYNAMIC_METHODS = {
    "Overall Coverage Delta",
    "Changed-Code Coverage",
    "Function Reachability",
    "S1 Overall Coverage (oracle)",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def metrics(predictions: dict[str, str], labels: dict[str, str]) -> dict:
    tp = fn = fp = tn = abstain_pos = abstain_n4 = 0
    for case_id, label in labels.items():
        prediction = predictions.get(case_id, "ABSTAIN")
        if prediction == "ABSTAIN":
            if label == "POSITIVE":
                abstain_pos += 1
            else:
                abstain_n4 += 1
        elif label == "POSITIVE" and prediction == "YES":
            tp += 1
        elif label == "POSITIVE":
            fn += 1
        elif prediction == "YES":
            fp += 1
        else:
            tn += 1
    recall = tp / (tp + fn) if tp + fn else None
    fpr = fp / (fp + tn) if fp + tn else None
    precision = tp / (tp + fp) if tp + fp else None
    f1 = (2 * precision * recall / (precision + recall)
          if precision is not None and recall is not None and precision + recall else None)
    return {
        "TP": tp,
        "FN": fn,
        "FP": fp,
        "TN": tn,
        "positive_evaluable": tp + fn,
        "n4_evaluable": fp + tn,
        "abstain_positive": abstain_pos,
        "abstain_n4": abstain_n4,
        "silent_recall_percent": None if recall is None else 100 * recall,
        "n4_fpr_percent": None if fpr is None else 100 * fpr,
        "precision_percent": None if precision is None else 100 * precision,
        "f1_percent": None if f1 is None else 100 * f1,
        "intent_to_test_recall_percent": 100 * tp / sum(x == "POSITIVE" for x in labels.values()),
        "execution_success_percent": 100 * (tp + fn + fp + tn) / len(labels),
    }


def majority(values: list[str]) -> str:
    usable = [value for value in values if value != "ABSTAIN"]
    if not usable:
        return "ABSTAIN"
    counts = Counter(usable)
    if counts["YES"] == counts["NO"]:
        return "ABSTAIN"
    return counts.most_common(1)[0][0]


def aggregate_predictions(rows: list[dict[str, str]], method: str,
                          budget: str) -> dict[str, str]:
    selected = [row for row in rows if row["method"] == method and row["budget"] == budget]
    grouped: dict[str, list[str]] = defaultdict(list)
    for row in selected:
        grouped[row["case_id"]].append(row["prediction"])
    return {case_id: majority(values) for case_id, values in grouped.items()}


def cleanup_audit(cases: list[dict[str, str]]) -> list[dict]:
    rows = []
    for case in cases:
        case_id = case["case_id"]
        manifest_path = ROOT / "raw" / "case_manifests" / f"{case_id}.json"
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
        builds = {}
        for version in ("s0", "s1"):
            path = ROOT / "raw" / "timings" / f"{case_id}_{version}_build.json"
            builds[version] = json.loads(path.read_text()).get("status") if path.exists() else "MISSING"
        raw_paths = sorted((ROOT / "raw" / "coverage" / case_id).glob("*/*.json.gz"))
        coverage_pass = 0
        run_pass = 0
        for path in raw_paths:
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                raw = json.load(handle)
            coverage_pass += raw.get("status") == "PASS"
            run_pass += raw.get("run_status") == "PASS"
        error = manifest.get("error", "")
        cleanup_only = (
            len(raw_paths) == 12
            and coverage_pass == 12
            and run_pass == 12
            and builds == {"s0": "PASS", "s1": "PASS"}
            and error.startswith("PermissionError:")
            and "/tmp/t6-" in error
        )
        if cleanup_only or (
            len(raw_paths) == 12 and coverage_pass == 12 and run_pass == 12
            and builds == {"s0": "PASS", "s1": "PASS"}
        ):
            measurement_status = "PASS"
        elif "BUILD_UNAVAILABLE" in builds.values():
            measurement_status = "BUILD_UNAVAILABLE"
        elif raw_paths:
            measurement_status = "PARTIAL_DYNAMIC_UNAVAILABLE"
        else:
            measurement_status = "DYNAMIC_UNAVAILABLE"
        rows.append({
            "case_id": case_id,
            "project": case["project"],
            "label": case["label"],
            "manifest_status": manifest.get("status", "MISSING"),
            "measurement_status": measurement_status,
            "cleanup_only_exception": str(cleanup_only).lower(),
            "s0_build_status": builds["s0"],
            "s1_build_status": builds["s1"],
            "coverage_files": len(raw_paths),
            "expected_coverage_files": 12,
            "coverage_pass": coverage_pass,
            "run_pass": run_pass,
            "error": error,
        })
    fields = [
        "case_id", "project", "label", "manifest_status", "measurement_status",
        "cleanup_only_exception", "s0_build_status", "s1_build_status",
        "coverage_files", "expected_coverage_files", "coverage_pass", "run_pass", "error",
    ]
    write_csv(ROOT / "results" / "execution_audit.csv", rows, fields)
    return rows


def h1_unavailability(cases: list[dict[str, str]]) -> list[dict]:
    rows = [{
        "case_id": case["case_id"],
        "project": case["project"],
        "h1_status": case["h1_status"],
        "changed_line_coverage_s1_h1": "NA",
        "changed_function_coverage_s1_h1": "NA",
        "new_function_reachability_s1_h1": "NA",
        "reason": "Task-5 identified no provenance-audited H1; H1 was not synthesized",
    } for case in cases]
    fields = ["case_id", "project", "h1_status", "changed_line_coverage_s1_h1",
              "changed_function_coverage_s1_h1", "new_function_reachability_s1_h1", "reason"]
    write_csv(ROOT / "results" / "h1_oracle.csv", rows, fields)
    return rows


def integrity_audit(config: dict) -> dict:
    checks = []
    for relative, expected in config["frozen_file_sha256"].items():
        path = WORKSPACE / relative
        actual = sha256(path) if path.exists() else None
        checks.append({
            "path": relative,
            "expected_sha256": expected,
            "actual_sha256": actual,
            "match": actual == expected,
        })
    result = {
        "audited_at": now(),
        "status": "PASS" if all(row["match"] for row in checks) else "FAIL",
        "matched": sum(row["match"] for row in checks),
        "total": len(checks),
        "checks": checks,
    }
    write_json(ROOT / "results" / "frozen_integrity_audit.json", result)
    return result


def reporting_manifest(integrity: dict) -> dict:
    paths = [
        ROOT / "scripts" / "summarize_phase_a.py",
        ROOT / "scripts" / "validate_artifact.py",
        ROOT / "README.md",
        ROOT / "raw" / "reachability" / "README.md",
    ]
    value = {
        "created_at": now(),
        "stage": "POST_FREEZE_REPORTING_ONLY",
        "can_change_dynamic_measurements": False,
        "can_change_preregistered_predictions": False,
        "frozen_integrity_status_at_reporting": integrity["status"],
        "files": [{"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}
                  for path in paths if path.exists()],
    }
    write_json(ROOT / "results" / "post_freeze_reporting_manifest.json", value)
    return value


def latency_for_budget(cost_rows: list[dict[str, str]], budget: str) -> tuple[float | None, float | None]:
    grouped_wall: dict[str, list[float]] = defaultdict(list)
    grouped_cpu: dict[str, list[float]] = defaultdict(list)
    for row in cost_rows:
        if row["budget"] != budget or row["status"] != "PASS":
            continue
        grouped_wall[row["case_id"]].append(float(row["total_wall_clock_seconds"]))
        grouped_cpu[row["case_id"]].append(float(row["cpu_seconds"]))
    wall = [statistics.median(values) for values in grouped_wall.values()]
    cpu = [statistics.median(values) for values in grouped_cpu.values()]
    return (statistics.median(wall) if wall else None,
            statistics.median(cpu) if cpu else None)


def delta_latency() -> float:
    manifest = json.loads((WORKSPACE / "t5-delta-aware-validation" / "predictions" /
                           "run_manifest_delta_aware.json").read_text())
    values = [float(row["duration_seconds"]) for row in manifest["attempts"]
              if row.get("valid_prediction") and row["case_id"] != "T5028"]
    return statistics.median(values)


def method_summary(cases: list[dict[str, str]], prediction_rows: list[dict[str, str]],
                   cost_rows: list[dict[str, str]]) -> list[dict]:
    labels = {row["case_id"]: row["label"] for row in cases}
    specs = [
        ("Build-Only", "corpus", "single preregistered result"),
        ("Overall Coverage Delta", "corpus", "repeat 1"),
        ("Changed-Code Coverage", "corpus", "repeat 1"),
        ("Function Reachability", "corpus", "repeat 1"),
        ("Overall Coverage Delta", "1m", "repeat 1"),
        ("Changed-Code Coverage", "1m", "repeat 1"),
        ("Function Reachability", "1m", "repeat 1"),
        ("Overall Coverage Delta", "5m", "majority of repeats 1/2/3"),
        ("Changed-Code Coverage", "5m", "majority of repeats 1/2/3"),
        ("Function Reachability", "5m", "majority of repeats 1/2/3"),
        ("Overall Coverage Delta", "15m", "repeat 1"),
        ("Changed-Code Coverage", "15m", "repeat 1"),
        ("Function Reachability", "15m", "repeat 1"),
        ("Delta-Aware", "static", "frozen Task-5 one-shot"),
    ]
    output = []
    for method, budget, aggregation in specs:
        predictions = aggregate_predictions(prediction_rows, method, budget)
        result = metrics(predictions, labels)
        if method == "Delta-Aware":
            wall, cpu = delta_latency(), None
            dynamic = "false"
        else:
            wall, cpu = latency_for_budget(cost_rows, budget)
            dynamic = "true"
        output.append({
            "method": method,
            "budget": budget,
            "aggregation": aggregation,
            **result,
            "median_wall_clock_seconds": wall,
            "median_cpu_seconds": cpu,
            "dynamic_execution": dynamic,
        })
    fields = [
        "method", "budget", "aggregation", "TP", "FN", "FP", "TN",
        "positive_evaluable", "n4_evaluable", "abstain_positive", "abstain_n4",
        "silent_recall_percent", "n4_fpr_percent", "precision_percent", "f1_percent",
        "intent_to_test_recall_percent", "execution_success_percent",
        "median_wall_clock_seconds", "median_cpu_seconds", "dynamic_execution",
    ]
    write_csv(ROOT / "results" / "method_summary.csv", output, fields)
    return output


def repeatability(metric_rows: list[dict[str, str]]) -> list[dict]:
    methods = ["Overall Coverage Delta", "Changed-Code Coverage", "Function Reachability",
               "S1 Overall Coverage (oracle)"]
    measures = ["silent_recall_percent", "n4_fpr_percent", "precision_percent",
                "f1_percent", "execution_success_percent"]
    output = []
    for method in methods:
        rows = [row for row in metric_rows
                if row["method"] == method and row["budget"] == "5m"]
        rows.sort(key=lambda row: int(row["repeat"]))
        for row in rows:
            output.append({
                "method": method,
                "budget": "5m",
                "statistic": f"repeat_{row['repeat']}",
                **{measure: row[measure] for measure in measures},
            })
        for statistic in ("mean", "median", "std_population", "min", "max"):
            aggregate = {}
            for measure in measures:
                values = [float(row[measure]) for row in rows if row[measure] not in ("", "None")]
                if not values:
                    aggregate[measure] = None
                elif statistic == "mean":
                    aggregate[measure] = statistics.mean(values)
                elif statistic == "median":
                    aggregate[measure] = statistics.median(values)
                elif statistic == "std_population":
                    aggregate[measure] = statistics.pstdev(values)
                elif statistic == "min":
                    aggregate[measure] = min(values)
                else:
                    aggregate[measure] = max(values)
            output.append({"method": method, "budget": "5m", "statistic": statistic,
                           **aggregate})
    fields = ["method", "budget", "statistic", *measures]
    write_csv(ROOT / "results" / "repeatability_5m.csv", output, fields)
    return output


def s1_threshold_sweep(cases: list[dict[str, str]]) -> tuple[list[dict], list[dict]]:
    """Emit complete post-hoc ROC/PR points for absolute S1 coverage.

    The direction is frozen to "lower coverage predicts YES".  These rows are
    diagnostic oracle upper bounds and are never copied into the deployable
    method table.
    """
    labels = {row["case_id"]: row["label"] for row in cases}
    overall = read_csv(ROOT / "results" / "overall_coverage.csv")
    curve_rows = []
    best_rows = []
    keys = sorted(
        {(row["budget"], row["repeat"]) for row in overall if row["version"] == "s1"},
        key=lambda item: (BUDGET_ORDER.get(item[0], 99), int(item[1])),
    )
    for budget, repeat in keys:
        selected = [row for row in overall if row["version"] == "s1"
                    and row["budget"] == budget and row["repeat"] == repeat
                    and row["status"] == "PASS"]
        for dimension in ("line", "branch", "function"):
            field = f"{dimension}_coverage_percent"
            signals = {row["case_id"]: float(row[field]) for row in selected
                       if row[field] not in ("", "NA", "None")}
            values = sorted(set(signals.values()))
            if not values:
                continue
            thresholds = [values[0] - 1e-9]
            thresholds.extend((left + right) / 2 for left, right in zip(values, values[1:]))
            thresholds.append(values[-1] + 1e-9)
            dimension_rows = []
            for index, threshold in enumerate(thresholds):
                predictions = {case_id: "YES" if value < threshold else "NO"
                               for case_id, value in signals.items()}
                result = metrics(predictions, labels)
                tpr = result["silent_recall_percent"]
                fpr = result["n4_fpr_percent"]
                row = {
                    "budget": budget,
                    "repeat": repeat,
                    "dimension": dimension,
                    "threshold_index": index,
                    "low_coverage_yes_threshold": threshold,
                    "oracle_post_hoc": "true",
                    **result,
                    "roc_tpr_percent": tpr,
                    "roc_fpr_percent": fpr,
                }
                curve_rows.append(row)
                dimension_rows.append(row)
            best = max(
                dimension_rows,
                key=lambda row: (
                    -1 if row["f1_percent"] is None else row["f1_percent"],
                    0 if row["n4_fpr_percent"] is None else -row["n4_fpr_percent"],
                    -1 if row["silent_recall_percent"] is None else row["silent_recall_percent"],
                ),
            )
            best_rows.append({key: value for key, value in best.items()
                              if key not in {"threshold_index", "roc_tpr_percent", "roc_fpr_percent"}})
    curve_fields = [
        "budget", "repeat", "dimension", "threshold_index", "low_coverage_yes_threshold",
        "oracle_post_hoc", "TP", "FN", "FP", "TN", "positive_evaluable", "n4_evaluable",
        "abstain_positive", "abstain_n4", "silent_recall_percent", "n4_fpr_percent",
        "precision_percent", "f1_percent", "intent_to_test_recall_percent",
        "execution_success_percent", "roc_tpr_percent", "roc_fpr_percent",
    ]
    best_fields = [field for field in curve_fields
                   if field not in {"threshold_index", "roc_tpr_percent", "roc_fpr_percent"}]
    write_csv(ROOT / "results" / "s1_overall_threshold_sweep.csv", curve_rows, curve_fields)
    write_csv(ROOT / "results" / "s1_overall_oracle_summary.csv", best_rows, best_fields)
    return curve_rows, best_rows


def s1_auc(cases: list[dict[str, str]]) -> list[dict]:
    labels = {row["case_id"]: row["label"] for row in cases}
    overall = read_csv(ROOT / "results" / "overall_coverage.csv")
    keys = sorted(
        {(row["budget"], row["repeat"]) for row in overall if row["version"] == "s1"},
        key=lambda item: (BUDGET_ORDER.get(item[0], 99), int(item[1])),
    )
    output = []
    for budget, repeat in keys:
        selected = [row for row in overall if row["version"] == "s1"
                    and row["budget"] == budget and row["repeat"] == repeat
                    and row["status"] == "PASS"]
        for dimension in ("line", "branch", "function"):
            field = f"{dimension}_coverage_percent"
            # A larger score means more likely positive; the frozen direction
            # for absolute coverage is therefore minus the coverage value.
            positives = [-float(row[field]) for row in selected
                         if labels[row["case_id"]] == "POSITIVE" and row[field] != ""]
            negatives = [-float(row[field]) for row in selected
                         if labels[row["case_id"]] == "N4" and row[field] != ""]
            wins = sum((positive > negative) + 0.5 * (positive == negative)
                       for positive in positives for negative in negatives)
            auc = wins / (len(positives) * len(negatives)) if positives and negatives else None
            output.append({
                "budget": budget,
                "repeat": repeat,
                "dimension": dimension,
                "direction": "lower_coverage_predicts_positive",
                "positive_evaluable": len(positives),
                "n4_evaluable": len(negatives),
                "roc_auc": auc,
                "oracle_post_hoc": "true",
            })
    fields = ["budget", "repeat", "dimension", "direction", "positive_evaluable",
              "n4_evaluable", "roc_auc", "oracle_post_hoc"]
    write_csv(ROOT / "results" / "s1_overall_auc.csv", output, fields)
    return output


def case_analysis(cases: list[dict[str, str]], prediction_rows: list[dict[str, str]]) -> list[dict]:
    methods = ["Overall Coverage Delta", "Changed-Code Coverage", "Function Reachability"]
    indexed = {(method, budget): aggregate_predictions(prediction_rows, method, budget)
               for method in methods for budget in ("corpus", "1m", "5m", "15m")}
    output = []
    for case in cases:
        case_id = case["case_id"]
        row = {
            "case_id": case_id,
            "project": case["project"],
            "label": case["label"],
            "positive_subtype": case["positive_subtype"],
            "impact_scope": case["impact_scope"],
            "expected_delta": case["expected_delta"],
        }
        for budget in ("corpus", "1m", "5m", "15m"):
            for method in methods:
                key = method.lower().replace("-", "_").replace(" ", "_")
                row[f"{key}_{budget}"] = indexed[(method, budget)].get(case_id, "ABSTAIN")
        output.append(row)
    fields = list(output[0]) if output else ["case_id"]
    write_csv(ROOT / "results" / "case_analysis.csv", output, fields)
    return output


def cost_summary(cost_rows: list[dict[str, str]], run_manifest: dict) -> dict:
    components = [
        "checkout_time_seconds",
        "build_time_seconds",
        "corpus_or_fuzz_time_seconds",
        "coverage_collection_time_seconds",
        "total_wall_clock_seconds",
        "cpu_seconds",
        "peak_memory_mb_fuzz_only",
    ]
    by_budget = []
    for budget in ("corpus", "1m", "5m", "15m"):
        rows = [row for row in cost_rows if row["budget"] == budget]
        passed = [row for row in rows if row["status"] == "PASS"]
        entry = {
            "budget": budget,
            "records": len(rows),
            "pass_records": len(passed),
            "unavailable_records": len(rows) - len(passed),
        }
        for component in components:
            values = [float(row[component]) for row in passed if row[component] not in ("", "NA")]
            entry[f"median_{component}"] = statistics.median(values) if values else None
            entry[f"mean_{component}"] = statistics.mean(values) if values else None
        by_budget.append(entry)

    run_timing_files = sorted((ROOT / "raw" / "timings").glob("*/*/*.json"))
    build_timing_files = sorted((ROOT / "raw" / "timings").glob("*_build.json"))
    run_cpu = 0.0
    run_wall = 0.0
    for path in run_timing_files:
        value = json.loads(path.read_text())
        run_cpu += float(value.get("cpu_seconds") or 0)
        run_wall += float(value.get("wall_seconds") or 0)
    build_cpu = 0.0
    build_wall = 0.0
    checkout_wall = 0.0
    for path in build_timing_files:
        value = json.loads(path.read_text())
        build_cpu += float(value.get("build_cpu_seconds") or 0)
        build_wall += float(value.get("build_wall_seconds") or 0)
        checkout_wall += float(value.get("checkout_time_seconds") or 0)

    started = datetime.fromisoformat(run_manifest["started_at"].replace("Z", "+00:00"))
    finished = datetime.fromisoformat(run_manifest["finished_at"].replace("Z", "+00:00"))
    value = {
        "generated_at": now(),
        "budget_component_summary": by_budget,
        "actual_formal_run": {
            "calendar_wall_seconds": (finished - started).total_seconds(),
            "calendar_parallel_workers": run_manifest["workers"],
            "successful_run_timing_records": len(run_timing_files),
            "build_attempts": len(build_timing_files),
            "build_cpu_seconds_once": build_cpu,
            "build_wall_seconds_serial_sum": build_wall,
            "checkout_wall_seconds_serial_sum": checkout_wall,
            "fuzz_or_corpus_cpu_seconds": run_cpu,
            "fuzz_or_corpus_wall_seconds_serial_sum": run_wall,
            "measured_cpu_seconds_total": build_cpu + run_cpu,
            "coverage_collection_cpu_seconds": "UNAVAILABLE",
        },
        "component_accounting": {
            "configure_time": "included in build_time; adapter does not expose it separately",
            "instrumentation_time": "same instrumented build operation, not an additional cost",
            "coverage_collection_cpu": "not exposed by the frozen collector",
            "build_peak_memory": "unavailable; Docker build memory limit was 4096 MB",
        },
    }
    write_json(ROOT / "results" / "cost_summary.json", value)
    return value


def artifact_manifest() -> dict:
    included = []
    for path in (ROOT / "README.md", ROOT / "NEXT_STEP_DYNAMIC_BASELINE.md",
                 ROOT / "experiment_config.json", ROOT / "raw" / "formal_run_manifest.json"):
        if path.exists():
            included.append({
                "path": str(path.relative_to(ROOT)),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            })
    for base in (ROOT / "dataset", ROOT / "scripts", ROOT / "results", ROOT / "reports"):
        if not base.exists():
            continue
        for path in sorted(x for x in base.rglob("*")
                           if x.is_file() and "__pycache__" not in x.parts):
            if path.name == "artifact_manifest.json":
                continue
            included.append({
                "path": str(path.relative_to(ROOT)),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            })
    raw_counts = {}
    for name in ("coverage", "timings", "logs", "corpus", "case_manifests", "reachability"):
        base = ROOT / "raw" / name
        paths = sorted(path for path in base.rglob("*") if path.is_file()) if base.exists() else []
        digest = hashlib.sha256()
        total_bytes = 0
        for path in paths:
            relative = str(path.relative_to(ROOT)).encode()
            digest.update(relative)
            digest.update(b"\0")
            total_bytes += path.stat().st_size
            with path.open("rb") as handle:
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
            digest.update(b"\0")
        raw_counts[name] = {
            "files": len(paths),
            "bytes": total_bytes,
            "composite_sha256": digest.hexdigest(),
        }
    value = {
        "generated_at": now(),
        "scope": "Phase A diagnostic kill test",
        "metadata_files": included,
        "raw_file_counts": raw_counts,
    }
    write_json(ROOT / "artifact_manifest.json", value)
    return value


def main() -> None:
    config = json.loads((ROOT / "experiment_config.json").read_text())
    run_manifest = json.loads((ROOT / "raw" / "formal_run_manifest.json").read_text())
    if run_manifest.get("status") != "COMPLETE":
        raise SystemExit("formal Phase-A run is not COMPLETE")
    required = [
        ROOT / "results" / "classification_metrics.csv",
        ROOT / "results" / "case_predictions.csv",
        ROOT / "results" / "runtime_cost.csv",
    ]
    if not all(path.exists() for path in required):
        raise SystemExit("run evaluate_dynamic_baselines.py first")
    cases = read_csv(ROOT / "dataset" / "cases.csv")
    predictions = read_csv(ROOT / "results" / "case_predictions.csv")
    metric_rows = read_csv(ROOT / "results" / "classification_metrics.csv")
    cost_rows = read_csv(ROOT / "results" / "runtime_cost.csv")
    audit = cleanup_audit(cases)
    h1_rows = h1_unavailability(cases)
    integrity = integrity_audit(config)
    reporting_manifest(integrity)
    summaries = method_summary(cases, predictions, cost_rows)
    repeats = repeatability(metric_rows)
    sweep, sweep_best = s1_threshold_sweep(cases)
    auc_rows = s1_auc(cases)
    analyses = case_analysis(cases, predictions)
    costs = cost_summary(cost_rows, run_manifest)
    artifact_manifest()
    write_json(ROOT / "results" / "postprocess_summary.json", {
        "generated_at": now(),
        "integrity_status": integrity["status"],
        "measurement_pass_cases": sum(row["measurement_status"] == "PASS" for row in audit),
        "measurement_unavailable_cases": sum(row["measurement_status"] != "PASS" for row in audit),
        "h1_unavailable_cases": len(h1_rows),
        "method_summary_rows": len(summaries),
        "repeatability_rows": len(repeats),
        "s1_oracle_threshold_points": len(sweep),
        "s1_oracle_summary_rows": len(sweep_best),
        "s1_auc_rows": len(auc_rows),
        "case_analysis_rows": len(analyses),
        "formal_run_measured_cpu_seconds": costs["actual_formal_run"]["measured_cpu_seconds_total"],
        "notes": [
            "5m deployable summaries use majority vote across all three preregistered repeats.",
            "Oracle S1 threshold rows remain post-hoc and are excluded from deployable method_summary.csv.",
            "Cleanup-only exceptions do not convert complete PASS measurements into execution failures.",
        ],
    })


if __name__ == "__main__":
    main()
