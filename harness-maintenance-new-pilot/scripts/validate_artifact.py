#!/usr/bin/env python3
"""Validate the complete pilot artifact and emit a machine-audited report."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path


HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
WORKSPACE = ROOT.parent
DATA = ROOT / "data"
CASES = ROOT / "cases"
PROMPTS = ROOT / "prompts"
RESULTS = ROOT / "results"
REPORTS = ROOT / "reports"
PROJECTS = WORKSPACE / "FSE2026-harness-degradation" / "sources" / "projects"


class Audit:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[str] = []
        self.notes: list[str] = []

    def check(self, condition: bool, label: str, detail: str = "") -> None:
        item = label if not detail else f"{label}: {detail}"
        (self.passed if condition else self.failed).append(item)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def expected_input(baseline: str, case_id: str) -> str:
    fixed = (PROMPTS / f"{baseline}_prompt.md").read_text(encoding="utf-8").rstrip()
    case = (CASES / case_id / "blind_input.md").read_text(encoding="utf-8")
    return fixed + "\n\n--- BEGIN ANONYMOUS CASE ---\n\n" + case + "\n--- END ANONYMOUS CASE ---\n"


def confusion(labels: dict[str, bool], predictions: dict[str, dict[str, object]], field: str) -> dict[str, int]:
    counts = Counter({"TP": 0, "FP": 0, "FN": 0, "TN": 0})
    for case_id, actual in labels.items():
        predicted = bool(predictions[case_id][field])
        key = "TP" if actual and predicted else "FN" if actual else "FP" if predicted else "TN"
        counts[key] += 1
    return {key: counts[key] for key in ("TP", "FP", "FN", "TN")}


def git_commit_exists(project: str, commit: str) -> bool:
    completed = subprocess.run(
        ["git", "-C", str(PROJECTS / project), "cat-file", "-e", f"{commit}^{{commit}}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return completed.returncode == 0


def git_first_parent(project: str, commit: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(PROJECTS / project), "rev-parse", f"{commit}^1"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def validate() -> Audit:
    audit = Audit()
    required = [
        ROOT / "TEST.md", ROOT / "README.md",
        DATA / "co_evolution_candidates.csv",
        DATA / "co_evolution_semantic_labels.csv",
        DATA / "verified_positive_cases.csv",
        DATA / "verified_negative_cases.csv",
        DATA / "ground_truth_audit.csv",
        PROMPTS / "gap_only_prompt.md", PROMPTS / "evolution_aware_prompt.md",
        RESULTS / "gap_only_predictions.jsonl",
        RESULTS / "evolution_aware_predictions.jsonl",
        RESULTS / "gap_only_input_output_pairs.jsonl",
        RESULTS / "evolution_aware_input_output_pairs.jsonl",
        RESULTS / "coverage_results.csv", RESULTS / "reachability_results.csv",
        RESULTS / "evaluation.csv", RESULTS / "confusion_matrix.csv",
        RESULTS / "summary.json",
        REPORTS / "feasibility_results.md", REPORTS / "case_studies.md",
        REPORTS / "false_positive_analysis.md", REPORTS / "false_negative_analysis.md",
        REPORTS / "go_no_go.md", REPORTS / "validation.md",
    ]
    audit.check(all(path.is_file() for path in required), "required artifact files exist",
                f"{sum(path.is_file() for path in required)}/{len(required)}")
    source_test = WORKSPACE / "task-2.md"
    if source_test.exists() and (ROOT / "TEST.md").exists():
        audit.check(source_test.read_bytes() == (ROOT / "TEST.md").read_bytes(),
                    "TEST.md is the exact frozen task specification")

    universe = read_csv(DATA / "co_evolution_universe.csv")
    candidates_initial = read_csv(DATA / "co_evolution_candidates_initial.csv")
    candidates = read_csv(DATA / "co_evolution_candidates.csv")
    semantic = read_csv(DATA / "co_evolution_semantic_labels.csv")
    positives_initial = read_csv(DATA / "verified_positive_cases_initial.csv")
    negatives_initial = read_csv(DATA / "verified_negative_cases_initial.csv")
    positives = read_csv(DATA / "verified_positive_cases.csv")
    negatives = read_csv(DATA / "verified_negative_cases.csv")
    truth_audit = read_csv(DATA / "ground_truth_audit.csv")
    coverage = read_csv(RESULTS / "coverage_results.csv")
    reachability = read_csv(RESULTS / "reachability_results.csv")

    expected_counts = {
        "raw path-level hits": (len(universe), 119),
        "screened candidates": (len(candidates_initial), 50),
        "eligible candidates": (len(candidates), 49),
        "semantic screen rows": (len(semantic), 50),
        "initial positives": (len(positives_initial), 24),
        "initial negatives": (len(negatives_initial), 40),
        "audited positives": (len(positives), 20),
        "audited negatives": (len(negatives), 40),
        "ground-truth audit rows": (len(truth_audit), 64),
        "canonical coverage rows": (len(coverage), 20),
        "canonical reachability rows": (len(reachability), 20),
    }
    for label, (actual, expected) in expected_counts.items():
        audit.check(actual == expected, label, f"{actual} (expected {expected})")

    audit.check(Counter(row["semantic_label"] for row in semantic) ==
                Counter({"RELATED": 30, "UNRELATED": 13, "UNCERTAIN": 7}),
                "semantic label distribution", str(Counter(row["semantic_label"] for row in semantic)))
    audit.check(Counter(row["vp_criterion"] for row in positives) ==
                Counter({"VP1": 15, "VP3": 2, "VP4": 3}),
                "Verified Positive criteria", str(Counter(row["vp_criterion"] for row in positives)))
    audit.check(Counter(row["project"] for row in positives) ==
                Counter({"wuffs": 9, "meshoptimizer": 4, "libspng": 3, "c-ares": 3, "leptonica": 1}),
                "positive project distribution", str(Counter(row["project"] for row in positives)))
    evaluated_rows = positives + negatives
    audit.check(len({row["project"] for row in evaluated_rows}) == 10,
                "audited evaluation project count", "10")
    audit.check(len({(row["project"], row["commit_id"]) for row in evaluated_rows}) == 60,
                "audited evaluation unique commit count", "60")
    audit.check(len({row["project"] for row in candidates}) == 6,
                "eligible co-evolution project count", "6")

    initial_pos_ids = {row["case_id"] for row in positives_initial}
    initial_neg_ids = {row["case_id"] for row in negatives_initial}
    pos_ids = {row["case_id"] for row in positives}
    neg_ids = {row["case_id"] for row in negatives}
    audit_map = {row["case_id"]: row for row in truth_audit}
    expected_case_ids = {f"C{number:03d}" for number in range(1, 65)}
    audit.check(not (initial_pos_ids & initial_neg_ids) and initial_pos_ids | initial_neg_ids == expected_case_ids,
                "initial label partition is complete and disjoint")
    audit.check(not (pos_ids & neg_ids) and len(pos_ids | neg_ids) == 60,
                "audited label partition is complete and disjoint")
    audit.check({case_id for case_id, row in audit_map.items() if row["audit_status"] == "RELABEL"} ==
                {"C013", "C030", "C040"}, "three relabelled cases are explicit")
    audit.check({case_id for case_id, row in audit_map.items() if row["audited_label"] == "excluded"} ==
                {"C018", "C034", "C047", "C053"}, "four excluded cases are explicit")
    audit.check(pos_ids == {case_id for case_id, row in audit_map.items() if row["audited_label"] == "positive"},
                "positive CSV matches audit ledger")
    audit.check(neg_ids == {case_id for case_id, row in audit_map.items() if row["audited_label"] == "negative"},
                "negative CSV matches audit ledger")

    c_dirs = {path.name for path in CASES.glob("C*") if path.is_dir()}
    p_dirs = {path.name for path in CASES.glob("P*") if path.is_dir()}
    audit.check(c_dirs == expected_case_ids, "64 anonymous case directories")
    audit.check(p_dirs == {f"P{number:03d}" for number in range(1, 51)}, "50 candidate directories")
    required_case_files = ("metadata.json", "source_diff.patch", "harness_diff.patch",
                           "blind_input.md", "ground_truth.md")
    complete_cases = []
    for case_id in sorted(expected_case_ids):
        case = CASES / case_id
        if all((case / name).is_file() for name in required_case_files) and (case / "H0").is_dir() and (case / "H1").is_dir():
            complete_cases.append(case_id)
    audit.check(len(complete_cases) == 64, "case materialization", f"{len(complete_cases)}/64 complete")

    manifest = json.loads((DATA / "dataset_manifest.json").read_text(encoding="utf-8"))
    manifest_hashes = {row["case_id"]: row["blind_input_sha256"] for row in manifest["cases"]}
    matching_blind_hashes = sum(
        manifest_hashes.get(case_id) == sha256_bytes((CASES / case_id / "blind_input.md").read_bytes())
        for case_id in expected_case_ids
    )
    audit.check(matching_blind_hashes == 64, "frozen blind-input hashes", f"{matching_blind_hashes}/64")

    forbidden_patterns = {
        "H1 path": re.compile(r"(?i)(?:^|[\s`/\\])H1(?:[/\\\s`]|$)"),
        "harness diff": re.compile(r"(?i)harness[_ ]diff"),
        "ground-truth label": re.compile(r"(?i)(?:actual[_ ]label|verified[_ ]positive|verified[_ ]negative|ground[_ -]?truth)"),
        "counterfactual outcome": re.compile(r"(?i)counterfactual[_ ](?:result|status|outcome)"),
        "commit-message field": re.compile(r"(?i)commit_message"),
    }
    leaks: list[str] = []
    for case_id in sorted(expected_case_ids):
        value = (CASES / case_id / "blind_input.md").read_text(encoding="utf-8")
        for label, pattern in forbidden_patterns.items():
            if pattern.search(value):
                leaks.append(f"{case_id}:{label}")
    audit.check(not leaks, "blind-input leakage marker scan", "none" if not leaks else ", ".join(leaks[:10]))

    predictions_by_baseline: dict[str, dict[str, dict[str, object]]] = {}
    for baseline in ("gap_only", "evolution_aware"):
        prediction_rows = read_jsonl(RESULTS / f"{baseline}_predictions.jsonl")
        pair_rows = read_jsonl(RESULTS / f"{baseline}_input_output_pairs.jsonl")
        prediction_map = {str(row["case_id"]): row for row in prediction_rows}
        pair_map = {str(row["case_id"]): row for row in pair_rows}
        predictions_by_baseline[baseline] = prediction_map
        audit.check(len(prediction_rows) == 64 and set(prediction_map) == expected_case_ids,
                    f"{baseline} predictions", f"{len(prediction_rows)} unique complete cases")
        audit.check(len(pair_rows) == 64 and set(pair_map) == expected_case_ids,
                    f"{baseline} exact input/output pairs", f"{len(pair_rows)} unique complete cases")
        exact_pairs = 0
        for case_id in expected_case_ids:
            if case_id not in prediction_map or case_id not in pair_map:
                continue
            expected = expected_input(baseline, case_id)
            pair = pair_map[case_id]
            if (pair["model_input"] == expected and pair["model_output"] == prediction_map[case_id]
                    and pair["input_sha256"] == sha256_bytes(expected.encode())):
                exact_pairs += 1
        audit.check(exact_pairs == 64, f"{baseline} input/output reconstruction", f"{exact_pairs}/64 exact")
        run_manifest = json.loads((RESULTS / f"run_manifest_{baseline}.json").read_text(encoding="utf-8"))
        audit.check(run_manifest["status"] == "complete" and run_manifest["valid_predictions"] == 64
                    and run_manifest["failed_predictions"] == 0 and len(run_manifest["attempts"]) == 64,
                    f"{baseline} one-shot run completion", "64 valid, 0 failed")
        audit.check(run_manifest["model"] == "gpt-5.6-sol" and run_manifest["reasoning_effort"] == "high"
                    and run_manifest["concurrency"] == 4 and run_manifest["timeout_seconds"] == 900,
                    f"{baseline} frozen model parameters")
        audit.check(run_manifest["prompt_sha256"] == sha256_bytes((PROMPTS / f"{baseline}_prompt.md").read_bytes())
                    and run_manifest["schema_sha256"] == sha256_bytes((PROMPTS / f"{baseline}_schema.json").read_bytes()),
                    f"{baseline} prompt/schema hashes")

    evo_logic = sum(
        bool(row["maintenance_needed"]) == (bool(row["gap_exists"]) and row["commit_induced"] == "YES")
        for row in predictions_by_baseline["evolution_aware"].values()
    )
    audit.check(evo_logic == 64, "Evolution-Aware final-decision invariant", f"{evo_logic}/64")

    initial_labels = {case_id: case_id in initial_pos_ids for case_id in expected_case_ids}
    audited_labels = {case_id: case_id in pos_ids for case_id in pos_ids | neg_ids}
    computed = {
        "initial gap-only": confusion(initial_labels, predictions_by_baseline["gap_only"], "gap_exists"),
        "initial evolution-aware": confusion(initial_labels, predictions_by_baseline["evolution_aware"], "maintenance_needed"),
        "audited gap-only": confusion(audited_labels, predictions_by_baseline["gap_only"], "gap_exists"),
        "audited evolution-aware": confusion(audited_labels, predictions_by_baseline["evolution_aware"], "maintenance_needed"),
    }
    expected_confusions = {
        "initial gap-only": {"TP": 23, "FP": 29, "FN": 1, "TN": 11},
        "initial evolution-aware": {"TP": 20, "FP": 3, "FN": 4, "TN": 37},
        "audited gap-only": {"TP": 20, "FP": 28, "FN": 0, "TN": 12},
        "audited evolution-aware": {"TP": 19, "FP": 1, "FN": 1, "TN": 39},
    }
    for label, value in computed.items():
        audit.check(value == expected_confusions[label], f"recomputed {label} confusion matrix", str(value))

    coverage_ids = {row["case_id"] for row in coverage}
    reachability_ids = {row["case_id"] for row in reachability}
    audit.check(coverage_ids == pos_ids and all(row["status"] == "NOT_MEASURED" for row in coverage),
                "coverage table is honest and aligned", "20/20 explicitly NOT_MEASURED")
    audit.check(reachability_ids == pos_ids and all(row["metric_kind"] ==
                "static_direct_identifier_exposure_not_dynamic_reachability" for row in reachability),
                "static exposure is not mislabeled as dynamic reachability")

    counterfactual = read_csv(RESULTS / "counterfactual_summary.csv")
    final_vp1 = {row["case_id"] for row in positives if row["vp_criterion"] == "VP1"}
    compile_pattern = {
        row["case_id"] for row in counterfactual
        if row["s0_h0_compile"] == "PASS" and row["s1_h0_compile"] == "FAIL" and row["s1_h1_compile"] == "PASS"
    }
    audit.check(final_vp1 <= compile_pattern, "VP1 three-way compile evidence", f"{len(final_vp1 & compile_pattern)}/15")

    commit_rows = candidates + positives + negatives
    malformed = [row.get("case_id", row["commit_id"])
                 for row in commit_rows if not re.fullmatch(r"[0-9a-f]{40}", row["commit_id"])
                 or not re.fullmatch(r"[0-9a-f]{40}", row["parent_commit"])]
    audit.check(not malformed, "full Git commit identifiers", "all commit and parent IDs are 40 hex characters")
    unique_git_pairs = {(row["project"], row["commit_id"]) for row in commit_rows}
    missing_git = [f"{project}:{commit}" for project, commit in sorted(unique_git_pairs)
                   if not git_commit_exists(project, commit)]
    audit.check(not missing_git, "commits resolve in local Git clones",
                f"{len(unique_git_pairs) - len(missing_git)}/{len(unique_git_pairs)} unique project/commit pairs")
    expected_parent = {(row["project"], row["commit_id"]): row["parent_commit"] for row in commit_rows}
    parent_mismatches = [
        f"{project}:{commit}" for (project, commit), parent in sorted(expected_parent.items())
        if git_first_parent(project, commit) != parent
    ]
    audit.check(not parent_mismatches, "CSV parent commits match Git first parents",
                f"{len(expected_parent) - len(parent_mismatches)}/{len(expected_parent)}")

    audit.notes.extend([
        "Dynamic changed-code coverage was not measured; the artifact does not substitute the static exposure proxy.",
        "The audited 60-case scores are post-hoc sensitivity results because 7/64 labels changed or were excluded after prediction.",
        "Formal decision remains NO-GO despite passing the numerical gates.",
    ])
    return audit


def render(audit: Audit) -> str:
    status = "PASS" if not audit.failed else "FAIL"
    lines = [
        "# Automated artifact validation", "", f"**Overall status: {status}**", "",
        f"- Passed checks: {len(audit.passed)}", f"- Failed checks: {len(audit.failed)}", "",
        "## Passed", "",
    ]
    lines.extend(f"- {item}" for item in audit.passed)
    lines.extend(["", "## Failed", ""])
    if audit.failed:
        lines.extend(f"- {item}" for item in audit.failed)
    else:
        lines.append("- None.")
    lines.extend(["", "## Interpretation notes", ""])
    lines.extend(f"- {item}" for item in audit.notes)
    return "\n".join(lines) + "\n"


def main() -> None:
    audit = validate()
    report = render(audit)
    (REPORTS / "artifact_validation.md").write_text(report, encoding="utf-8")
    print(report, end="")
    if audit.failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
