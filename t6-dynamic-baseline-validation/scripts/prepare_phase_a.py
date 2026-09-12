#!/usr/bin/env python3
from __future__ import annotations

import json

from common import (ROOT, SYNTHETIC_SEEDS, corpus_paths, sha256_bytes,
                    target_sources, tree_entries, utc_now, valid_cases,
                    write_csv, write_json)


def main() -> None:
    case_rows = []
    corpus_rows = []
    for row in valid_cases():
        project = row["project"]
        s0 = row["previous_commit"]
        targets = target_sources(project, s0)
        case_rows.append({
            "case_id": row["case_id"],
            "project": project,
            "s0_commit": s0,
            "s1_commit": row["commit_id"],
            "commit_time": row["commit_time"],
            "target_symbol": row["evidence_target_symbol"],
            "impact_scope": row["impact_scope"],
            "label": row["label"],
            "positive_subtype": "SILENT" if row["label"] == "POSITIVE" else "NA",
            "expected_maintenance": row["maintenance_needed"],
            "expected_delta": row["expected_delta"],
            "h0_fuzz_targets": ";".join(sorted(targets)),
            "h1_status": "UNAVAILABLE_NOT_IDENTIFIED_IN_TASK5",
            "phase": "A_DIAGNOSTIC",
            "source_gt": "t5-delta-aware-validation/frozen-ground-truth",
        })
        for target in sorted(targets):
            paths = corpus_paths(project, s0, target)
            entries = []
            total = 0
            tree = tree_entries(project, s0)
            for path in paths:
                blob_oid, size = tree[path]
                if total >= 0 and size >= 0:
                    total += size
                else:
                    total = -1
                entries.append((path, f"git-blob:{blob_oid}", size))
            if entries:
                payload = json.dumps(entries, separators=(",", ":")).encode()
                corpus_rows.append({
                    "case_id": row["case_id"], "project": project,
                    "fuzz_target": target, "source_commit": s0,
                    "corpus_source": "S0_PROJECT_HISTORICAL_TEST_DATA",
                    "source_paths": ";".join(x[0] for x in entries),
                    "file_count": len(entries), "total_bytes": total,
                    "corpus_sha256": sha256_bytes(payload),
                    "post_commit_data_used": "false",
                })
            else:
                entries = [(k, sha256_bytes(v), len(v))
                           for k, v in SYNTHETIC_SEEDS.items()]
                payload = json.dumps(entries, separators=(",", ":")).encode()
                corpus_rows.append({
                    "case_id": row["case_id"], "project": project,
                    "fuzz_target": target, "source_commit": s0,
                    "corpus_source": "FIXED_SYNTHETIC_SEED_SUITE",
                    "source_paths": ";".join(x[0] for x in entries),
                    "file_count": len(entries),
                    "total_bytes": sum(x[2] for x in entries),
                    "corpus_sha256": sha256_bytes(payload),
                    "post_commit_data_used": "false",
                })

    write_csv(ROOT / "dataset" / "cases.csv", case_rows, list(case_rows[0]))
    write_csv(ROOT / "dataset" / "corpus_manifest.csv", corpus_rows,
              list(corpus_rows[0]))
    write_json(ROOT / "dataset" / "preparation_manifest.json", {
        "prepared_at": utc_now(), "status": "PREPARED_BEFORE_FORMAL_EXECUTION",
        "case_count": len(case_rows),
        "n4_count": sum(r["label"] == "N4" for r in case_rows),
        "silent_positive_count": sum(r["label"] == "POSITIVE" for r in case_rows),
        "corpus_rows": len(corpus_rows),
        "h1_available_cases": 0,
        "note": "Task-5 did not identify an H1 update; B4 is unavailable, not imputed.",
    })


if __name__ == "__main__":
    main()
