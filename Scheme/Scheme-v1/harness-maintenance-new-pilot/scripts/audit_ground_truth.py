#!/usr/bin/env python3
"""Apply the mandatory three-way (S0+H0/S1+H0/S1+H1) label audit.

The initial frozen labels are preserved verbatim.  Corrections are explicit and
were made only after both one-shot baseline runs had completed; therefore the
audited scores are reported as a sensitivity analysis, not silently substituted
for the pre-run labels.
"""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path


HERE = Path(__file__).resolve()
OUT = HERE.parents[1]
DATA = OUT / "data"
CASES = OUT / "cases"
RESULTS = OUT / "results"

RELABEL = {
    "C013": ("negative", "adequate_valid_flow_no_delta", "S0+H0, S1+H0, and S1+H1 all compile. H0 supplies the required valid size/version constants, so the new status result is deterministically OK; H1 adds defensive handling but does not restore lost fuzz reach."),
    "C030": ("negative", "historical_gap_not_commit_induced", "S0+H0 and S1+H0 both fail on the same missing spng_ctx_new(int flags) argument. The source diff only introduces an equivalent typedef; H1 repairs an already-existing harness build failure."),
    "C040": ("negative", "historical_gap_not_commit_induced", "S0+H0 already fails because including common.h as C++ defines uninitialized const arrays. S1+H0 adds a missing-declaration error, but adequacy was already at build failure; H1 repairs the historical build gap rather than a measurable S0-to-S1 loss."),
}

EXCLUDE = {
    "C018": ("unverified_negative", "H0 does not reach the commit-changed readHeaderMemTiff output semantics. With no H1 repair, the case cannot be shown either H0-adequate (negative) or counterfactually repaired (positive)."),
    "C034": ("unverified_negative", "S1 adds public sarrayConcatUniformly and H0 cannot reach it, but the concurrent H1 edit is formatting and provides no counterfactual repair. The initial negative is therefore not verified."),
    "C047": ("unverified_negative", "S1 adds ares_expand_string_ex and H0 does not call it, while H1 does not expose it. This is a plausible commit-induced gap without the required H1 validation, so neither polarity is stable."),
    "C053": ("ineligible_candidate", "The mined non-harness path is script/bench-c-deflate-fragmentation.c; the commit changes examples, a benchmark, and harnesses but no production/library source. It fails Task 1 eligibility."),
}


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def filter_positive_measurements(final_positive_ids: set[str]) -> None:
    """Preserve pre-audit measurements and expose the audited positive subset.

    Coverage and reachability are measured before the label audit in the
    registered execution order. Their canonical filenames must nevertheless
    describe the final Verified Positive table. Always filter from the
    preserved pre-audit copy so repeated audits are idempotent.
    """
    for name in ("coverage_results", "reachability_results"):
        canonical = RESULTS / f"{name}.csv"
        initial = RESULTS / f"{name}_initial.csv"
        if not canonical.exists() and not initial.exists():
            continue
        if not initial.exists():
            shutil.copyfile(canonical, initial)
        rows = list(csv.DictReader(initial.open(encoding="utf-8", newline="")))
        if not rows:
            raise RuntimeError(f"empty measurement table: {initial}")
        filtered = [row for row in rows if row["case_id"] in final_positive_ids]
        filtered_ids = {row["case_id"] for row in filtered}
        if filtered_ids != final_positive_ids:
            raise RuntimeError(f"{name} lacks audited positives: {sorted(final_positive_ids - filtered_ids)}")
        write_csv(canonical, filtered, list(rows[0]))


def main() -> None:
    initial_pos = DATA / "verified_positive_cases_initial.csv"
    initial_neg = DATA / "verified_negative_cases_initial.csv"
    if not initial_pos.exists():
        shutil.copyfile(DATA / "verified_positive_cases.csv", initial_pos)
    if not initial_neg.exists():
        shutil.copyfile(DATA / "verified_negative_cases.csv", initial_neg)
    positives = list(csv.DictReader(initial_pos.open(encoding="utf-8", newline="")))
    negatives = list(csv.DictReader(initial_neg.open(encoding="utf-8", newline="")))
    positive_by_id = {x["case_id"]: x for x in positives}
    negative_by_id = {x["case_id"]: x for x in negatives}

    audit_rows: list[dict[str, str]] = []
    all_ids = sorted(set(positive_by_id) | set(negative_by_id))
    for case_id in all_ids:
        initial = "positive" if case_id in positive_by_id else "negative"
        final, status, reason = initial, "UNCHANGED", "Initial label survived the three-way audit."
        if case_id in RELABEL:
            final, status, reason = RELABEL[case_id]
            status = "RELABEL"
        elif case_id in EXCLUDE:
            final = "excluded"
            status, reason = EXCLUDE[case_id]
        audit_rows.append({
            "case_id": case_id, "initial_label": initial, "audited_label": final,
            "audit_status": status, "audit_reason": reason,
        })

    final_pos = [row for row in positives if next(x for x in audit_rows if x["case_id"] == row["case_id"])["audited_label"] == "positive"]
    final_neg: list[dict[str, str]] = []
    for row in negatives:
        if next(x for x in audit_rows if x["case_id"] == row["case_id"])["audited_label"] == "negative":
            final_neg.append(row)
    for case_id, (_, subtype, reason) in RELABEL.items():
        source = positive_by_id[case_id]
        final_neg.append({
            "case_id": case_id, "project": source["project"], "commit_id": source["commit_id"],
            "parent_commit": source["parent_commit"], "timestamp": source["timestamp"],
            "mechanism": "none", "negative_subtype": subtype,
        })
    final_pos.sort(key=lambda x: x["case_id"]); final_neg.sort(key=lambda x: x["case_id"])
    if len(final_pos) != 20 or len(final_neg) != 40:
        raise RuntimeError(f"audited cardinality mismatch: {len(final_pos)} positive, {len(final_neg)} negative")
    write_csv(DATA / "ground_truth_audit.csv", audit_rows,
              ["case_id", "initial_label", "audited_label", "audit_status", "audit_reason"])
    write_csv(DATA / "verified_positive_cases.csv", final_pos, list(positives[0]))
    write_csv(DATA / "verified_negative_cases.csv", final_neg,
              ["case_id", "project", "commit_id", "parent_commit", "timestamp", "mechanism", "negative_subtype"])
    filter_positive_measurements({row["case_id"] for row in final_pos})

    # Preserve the 50-row path-screened file, then make the canonical candidate
    # table the 49 actually eligible source+harness commits.
    initial_candidates = DATA / "co_evolution_candidates_initial.csv"
    if not initial_candidates.exists():
        shutil.copyfile(DATA / "co_evolution_candidates.csv", initial_candidates)
    candidates = list(csv.DictReader(initial_candidates.open(encoding="utf-8", newline="")))
    eligible = [x for x in candidates if not (x["project"] == "wuffs" and x["commit_id"].startswith("53760ce0fd2f"))]
    write_csv(DATA / "co_evolution_candidates.csv", eligible, list(candidates[0]))

    initial_semantic = DATA / "co_evolution_semantic_labels_initial.csv"
    if not initial_semantic.exists():
        shutil.copyfile(DATA / "co_evolution_semantic_labels.csv", initial_semantic)
    semantic = list(csv.DictReader(initial_semantic.open(encoding="utf-8", newline="")))
    candidate_overrides: dict[str, tuple[str, str, str]] = {}
    for case_id in ("C013", "C030", "C040", "C034", "C047", "C053"):
        meta = json.loads((CASES / case_id / "metadata.json").read_text(encoding="utf-8"))
        candidate_id = meta["candidate_case"]
        if case_id == "C013":
            candidate_overrides[candidate_id] = ("RELATED", "FAIL_NO_ADEQUACY_DELTA", "false")
        elif case_id in {"C030", "C040"}:
            candidate_overrides[candidate_id] = ("RELATED", "FAIL_HISTORICAL_GAP", "false")
        elif case_id in {"C034", "C047"}:
            candidate_overrides[candidate_id] = ("UNCERTAIN", "INCONCLUSIVE_LABEL_POLARITY", "false")
        else:
            candidate_overrides[candidate_id] = ("UNRELATED", "INELIGIBLE_NO_PRODUCTION_SOURCE", "false")
    audit_reasons = {x["case_id"]: x["audit_reason"] for x in audit_rows}
    candidate_to_case = {
        json.loads((CASES / cid / "metadata.json").read_text(encoding="utf-8")).get("candidate_case"): cid
        for cid in audit_reasons
    }
    for row in semantic:
        if row["candidate_case_id"] in candidate_overrides:
            label, status, verified = candidate_overrides[row["candidate_case_id"]]
            row.update({"semantic_label": label, "counterfactual_status": status, "verified_positive": verified})
            row["rationale"] = audit_reasons[candidate_to_case[row["candidate_case_id"]]]
    write_csv(DATA / "co_evolution_semantic_labels.csv", semantic, list(semantic[0]))

    for row in audit_rows:
        case_id = row["case_id"]
        meta_path = CASES / case_id / "metadata.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["initial_label"] = row["initial_label"]
        meta["actual_label"] = row["audited_label"]
        meta["ground_truth_audit_status"] = row["audit_status"]
        meta["ground_truth_audit_reason"] = row["audit_reason"]
        if case_id in RELABEL:
            meta["negative_subtype"] = RELABEL[case_id][1]
            meta["mechanism"] = "none"
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if row["audited_label"] != row["initial_label"]:
            (CASES / case_id / "ground_truth.md").write_text(
                f"# Audited ground truth: {case_id}\n\n"
                f"- Initial label: {row['initial_label']}\n"
                f"- Audited label: {row['audited_label']}\n"
                f"- Audit status: {row['audit_status']}\n"
                f"- Evidence: {row['audit_reason']}\n",
                encoding="utf-8",
            )
    manifest_path = DATA / "dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.update({
        "searched_project_count": 10,
        "searched_projects": ["c-ares", "libplist", "libspng", "tidy-html5", "brotli",
                              "leptonica", "meshoptimizer", "wuffs", "jansson", "h2o"],
        "coevolution_hit_project_count": 6,
        "positive_project_count": len({row["project"] for row in final_pos}),
        "path_screened_candidate_count": 50, "eligible_candidate_count": 49,
        "initial_verified_positive_count": 24, "initial_verified_negative_count": 40,
        "verified_positive_count": 20, "verified_negative_count": 40,
        "excluded_case_count": 4, "evaluation_case_count": 60,
        "evaluation_unique_commit_count": len({(row["project"], row["commit_id"])
                                                for row in final_pos + final_neg}),
        "excluded_cases": sorted(EXCLUDE),
        "audit_timing": "after both one-shot prediction runs; scores must show initial and audited views",
    })
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"eligible_candidates": len(eligible), "verified_positive": len(final_pos), "verified_negative": len(final_neg), "excluded": len(EXCLUDE)}, indent=2))


if __name__ == "__main__":
    main()
