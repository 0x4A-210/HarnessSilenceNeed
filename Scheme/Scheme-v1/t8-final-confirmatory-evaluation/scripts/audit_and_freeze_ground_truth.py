#!/usr/bin/env python3
"""Audit and immutably freeze the Task-8 labels before any prediction.

This is deliberately a one-way operation.  It validates commit identities,
sample quotas, the three-snapshot construction, prior-case exclusion, and the
static compatibility evidence for every P1 case.  It does not claim that a
dynamic OSS-Fuzz build was executed during annotation.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

from common import ROOT, REPOS, git, read_csv, sha256_file, utc_now, write_csv, write_json


OUT = ROOT / "frozen-ground-truth"

# Evidence was read from the complete production and developer-harness diffs.
# T8012 is intentionally absent: its legacy API remains as a compatibility
# alias and was corrected to N2 before this freeze.
P1_EVIDENCE = {
    "T8021": ("REMOVED_INTERNAL_API", "H0 calls xmlErrMemory(ctxt, NULL); S1 replaces that interface and H1 calls xmlCtxtErrMemory(ctxt)."),
    "T8022": ("REMOVED_INTERNAL_API", "H0 calls xmlInputCreateMemory/xmlInputCreateUrl; S1 removes those declarations/definitions and H1 uses xmlNewInputFromMemory/xmlNewInputFromUrl."),
    "T8023": ("BUILD_BOUNDARY_CHANGE", "H0 compiles the fuzzer by defining XMLLINT_FUZZ and textually including xmllint.c; S1 splits the callable boundary and H1 includes private/lint.h instead."),
    "T8032": ("ACCESS_CONTROL_CHANGE", "H0 reads simdjson_result's inherited .first; S1 makes std::pair inheritance protected and H1 uses value_unsafe()."),
    "T8033": ("REMOVED_GLOBAL_API", "H0 assigns active_implementation and iterates available_implementations; S1 exposes accessor functions and H1 switches to them."),
    "T8034": ("REMOVED_MACRO", "H0 uses UNUSED; S1 prefixes the macro as SIMDJSON_UNUSED throughout and H1 changes both affected fuzzers."),
    "T8035": ("REMOVED_METHOD", "H0 uses simdjson_result::tie; S1 changes the result extraction protocol and H1 uses get()."),
    "T8040": ("NAMESPACE_API_MOVE", "H0 includes YulUtilFunctions and calls its static helper; S1 moves the helper to dev::StringUtils and H1 changes include, namespace, and calls."),
    "T8041": ("REMOVED_METHOD", "H0 calls CompilerStack::methodIdentifiers; S1 replaces it with contractIdentifiers()[\"methods\"] and H1 follows that API."),
    "T8042": ("SIGNATURE_CHANGE", "S1 adds a protocol argument to h2o_qpack_flatten_request; H0 has the old arity and H1 supplies the new argument."),
    "T8043": ("SIGNATURE_CHANGE", "S1 adds an explicit origin argument to h2o_socketpool_create_target; H0 has the old arity and H1 supplies it."),
    "T8044": ("SIGNATURE_CHANGE", "S1 adds a statistics accumulator to h2o_qpack_flatten_request; H0 has the old arity and H1 supplies it."),
    "T8045": ("SIGNATURE_CHANGE", "S1 adds conf_len to h2o_socketpool_target_create; H0 has the old arity and H1 supplies zero."),
    "T8046": ("REMOVED_HELPER_API", "S1 replaces h2o_timer_val/abs wrapper construction with raw integers; H0 calls removed h2o_timer_val_from_uint helpers and H1 uses integers."),
    "T8047": ("API_RENAME", "S1 renames h2o_timeout timer/wheel types and helper functions to h2o_timer names; H0 uses the removed names and H1 uses the replacements."),
}


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def composite_hash(paths: list[Path]) -> str:
    payload = b"".join(
        str(path.relative_to(ROOT)).encode() + b"\0" + path.read_bytes() + b"\0"
        for path in sorted(paths)
    )
    return digest_bytes(payload)


def main() -> None:
    if OUT.exists():
        raise SystemExit("refusing to overwrite frozen-ground-truth")
    predictions = ROOT / "predictions"
    if predictions.exists() and any(predictions.rglob("*")):
        raise SystemExit("predictions already exist; ground truth must freeze first")

    cases = read_csv(ROOT / "ground-truth" / "cases.csv")
    labels = read_csv(ROOT / "ground-truth" / "labels.draft.csv")
    scopes = read_csv(ROOT / "ground-truth" / "impact_scope.draft.csv")
    evidence = read_csv(ROOT / "ground-truth" / "evidence.draft.csv")
    snapshots = read_csv(ROOT / "ground-truth" / "snapshot_manifest.csv")
    prior = {row["commit"] for row in read_csv(ROOT / "mining" / "prior_case_exclusions.csv")}

    ids = [f"T8{i:03d}" for i in range(1, 105)]
    assert [row["case_id"] for row in cases] == ids
    for rows in (labels, scopes, evidence):
        assert [row["case_id"] for row in rows] == ids
    assert len(snapshots) == 312
    assert not ({row["commit"] for row in cases} | {row["parent"] for row in cases}) & prior
    assert len({row["commit"] for row in cases}) == 104
    assert len({row["parent"] for row in cases}) == 104

    label_by_id = {row["case_id"]: row for row in labels}
    evidence_by_id = {row["case_id"]: row for row in evidence}
    counts = Counter(row["label"] for row in labels)
    types = Counter(row["positive_type"] or row["negative_type"] for row in labels)
    projects = Counter(row["project"] for row in cases)
    assert counts == {"POSITIVE": 45, "N4": 25, "OTHER_NEGATIVE": 34}
    assert types["P1"] == 15 and sum(types[x] for x in ("P2", "P3", "P4", "P5")) == 30
    assert len(projects) == 10 and max(projects.values()) / 104 <= 0.20
    assert {row["project"] for row in cases if row["split"] == "UNSEEN_PROJECT_HOLDOUT"} == {
        "libarchive", "libxml2", "simdjson"
    }

    snap_by_case: dict[str, list[dict[str, str]]] = {}
    for row in snapshots:
        snap_by_case.setdefault(row["case_id"], []).append(row)
        assert row["construct_status"] == "CONSTRUCTED"
        assert "MISSING" not in row["harness_blobs"]
    audit_rows = []
    for case in cases:
        case_id = case["case_id"]
        label = label_by_id[case_id]
        ev = evidence_by_id[case_id]
        assert case["h0_paths"] and case["production_paths"]
        assert {row["snapshot"] for row in snap_by_case[case_id]} == {"S0_H0", "S1_H0", "S1_H1"}
        resolved = git(case["project"], "rev-parse", f"{case['commit']}^").stdout.strip()
        assert resolved == case["parent"]
        if label["label"] == "POSITIVE":
            assert case["candidate_class"] == "COEVOLUTION"
            assert ev["harness_diff_sha256"] != digest_bytes(b"")
            assert label["maintenance_needed"] == "YES"
            basis = "real co-committed developer H1 plus full production/harness diff semantic audit"
        else:
            assert label["maintenance_needed"] == "NO"
            basis = "S0/H0 and S1/H0 semantic comparison; H1 is the no-change negative control"
        if label["label"] == "N4":
            assert int(ev["s0_target_occurrences"]) == int(ev["s1_target_occurrences"]) > 0
            assert label["expected_delta"] == "UNCHANGED"
        audit_rows.append({
            "case_id": case_id, "project": case["project"], "commit": case["commit"],
            "parent_verified": "true", "prior_identity_overlap": "false",
            "three_snapshots_constructed": "true", "label": label["label"],
            "taxonomy": label["positive_type"] or label["negative_type"],
            "audit_basis": basis, "audit_status": "VALID",
        })

    actual_p1 = {row["case_id"] for row in labels if row["positive_type"] == "P1"}
    assert actual_p1 == set(P1_EVIDENCE)
    p1_rows = []
    for case_id in sorted(P1_EVIDENCE):
        kind, rationale = P1_EVIDENCE[case_id]
        case = next(row for row in cases if row["case_id"] == case_id)
        p1_rows.append({
            "case_id": case_id, "project": case["project"], "commit": case["commit"],
            "failure_class": kind, "s1_h0_static_result": "INCOMPATIBLE",
            "s1_h1_static_result": "UPDATED_TO_NEW_INTERFACE", "evidence": rationale,
            "dynamic_build_at_annotation": "NOT_RUN", "audit_status": "VALID_STATIC_P1_EVIDENCE",
        })

    # Record the compatibility correction as positive evidence that the P1
    # gate was actively checked rather than inferred from any harness edit.
    t8012_case = next(row for row in cases if row["case_id"] == "T8012")
    compatibility_rows = [{
        "case_id": "T8012", "project": "libarchive", "commit": t8012_case["commit"],
        "candidate": "archive_read_finish -> archive_read_free",
        "finding": "legacy archive_read_finish remains declared behind ARCHIVE_VERSION_NUMBER < 4000000",
        "freeze_action": "classified OTHER_NEGATIVE/N2 before prediction; no replacement",
    }]

    OUT.mkdir(parents=True)
    frozen_labels = [{**row, "audit_status": "VALID"} for row in labels]
    write_csv(OUT / "labels.csv", frozen_labels, list(frozen_labels[0]))
    write_csv(OUT / "impact_scope.csv", scopes, list(scopes[0]))
    write_csv(OUT / "evidence.csv", evidence, list(evidence[0]))
    write_csv(OUT / "cases.csv", cases, list(cases[0]))
    write_csv(OUT / "snapshot_manifest.csv", snapshots, list(snapshots[0]))
    write_csv(OUT / "pre_freeze_audit.csv", audit_rows, list(audit_rows[0]))
    write_csv(OUT / "p1_compatibility_audit.csv", p1_rows, list(p1_rows[0]))
    write_csv(OUT / "compatibility_corrections.csv", compatibility_rows, list(compatibility_rows[0]))
    write_csv(OUT / "invalidations.csv", [], ["case_id", "status", "reason", "recorded_at"])

    dataset_files = [OUT / "cases.csv", OUT / "snapshot_manifest.csv"]
    gt_files = [OUT / name for name in (
        "labels.csv", "impact_scope.csv", "evidence.csv", "pre_freeze_audit.csv",
        "p1_compatibility_audit.csv", "compatibility_corrections.csv", "invalidations.csv",
    )]
    frozen_at = utc_now()
    manifest = {
        "status": "FROZEN_BEFORE_ANY_PREDICTION", "frozen_at": frozen_at,
        "case_count": 104, "project_count": 10, "project_counts": dict(projects),
        "max_project_share": max(projects.values()) / 104,
        "label_counts": dict(counts), "taxonomy_counts": dict(types),
        "silent_positive_count": sum(types[x] for x in ("P2", "P3", "P4", "P5")),
        "explicit_positive_count": types["P1"], "seen_count": 57, "unseen_count": 47,
        "unseen_projects": ["libarchive", "libxml2", "simdjson"],
        "dataset_hash": composite_hash(dataset_files),
        "ground_truth_hash": composite_hash(gt_files),
        "all_prior_commits_and_parents_excluded": True,
        "prior_identity_count": len(prior), "prior_overlap_count": 0,
        "three_snapshot_rows": 312, "post_freeze_relabels": 0,
        "pre_freeze_corrections": ["T8012 P1 candidate -> OTHER_NEGATIVE/N2 after compatibility-alias audit"],
        "annotation_method": "single-investigator static semantic audit of complete production and real developer harness diffs",
        "dynamic_build_at_annotation": "NOT_RUN; dynamic baselines are an independent post-freeze measurement",
        "limitations": [
            "No independent second human auditor was available.",
            "Silent labels use semantic developer-H1 evidence; they are not all backed by measured coverage uplift.",
            "P1 labels have static incompatibility evidence but were not all dynamically built at annotation time.",
        ],
        "prediction_artifacts_present_at_freeze": False,
        "file_sha256": {str(path.relative_to(ROOT)): sha256_file(path) for path in dataset_files + gt_files},
        "ordering": {"ground_truth_frozen_at": frozen_at, "input_frozen_at": None, "prediction_started_at": None},
    }
    write_json(OUT / "audit_manifest.json", manifest)
    print(json.dumps({
        "status": manifest["status"], "cases": 104, "projects": 10,
        "labels": dict(counts), "silent": manifest["silent_positive_count"],
        "explicit": manifest["explicit_positive_count"],
        "dataset_hash": manifest["dataset_hash"], "ground_truth_hash": manifest["ground_truth_hash"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
