#!/usr/bin/env python3
"""Record severe post-freeze GT errors as INVALIDATE, never as relabels."""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FROZEN = ROOT / "frozen-ground-truth"

INVALID = {
    "N4003": (
        "The commit adds material JPEG DHT parsing while the selected H0 is a JSON-only harness; "
        "the uncovered JPEG surface is enlarged, so DeltaGap cannot be treated as approximately zero.",
        "production_source.diff adds seen_dht/Huffman tables and a new decode_dht path; H0 is fuzz/c/std/json_fuzzer.cc",
    ),
    "N4012": (
        "The commit changes the public LZMA history/work-buffer protocol rather than merely changing an "
        "implementation behind an unchanged exposure requirement.",
        "DECODER_DST_HISTORY_RETAIN_LENGTH changes 0xFFFFFFFF->0 and DECODER_WORKBUF_LEN changes 0->0xFFFFFFFF+273",
    ),
    "N4013": (
        "The commit introduces a new opt-in XZ configuration and concatenated-stream state; this is a "
        "commit-induced configuration gap, not an unchanged historical gap.",
        "adds public QUIRK_DECODE_STANDALONE_CONCATENATED_STREAMS and standalone_format-gated parsing",
    ),
    "N4017": (
        "The commit adds NIA animation-format support while H0 has no NIE/NIA harness; the existing absent-"
        "subsystem gap is materially aggravated.",
        "adds nïA parsing, animation state, frame iteration, restart behavior, and loop/frame counters",
    ),
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    freeze = json.loads((ROOT / "predictions" / "prediction_freeze_manifest.json").read_text())
    if freeze["status"] != "FROZEN_BEFORE_LABEL_REVEAL":
        raise SystemExit("predictions were not frozen")
    gt_manifest = json.loads((FROZEN / "manifest.json").read_text())
    label_path = FROZEN / "labels.csv"
    if sha256(label_path.read_bytes()) != gt_manifest["labels_file_sha256"]:
        raise SystemExit("frozen labels changed")
    labels = list(csv.DictReader(label_path.open(encoding="utf-8", newline="")))
    by_candidate = {r["candidate_id"]: r for r in labels}
    missing = set(INVALID) - set(by_candidate)
    if missing:
        raise SystemExit(f"unknown invalidations: {sorted(missing)}")
    rows = []
    for candidate_id, (reason, evidence) in INVALID.items():
        label = by_candidate[candidate_id]
        rows.append({
            "case_id": label["case_id"], "candidate_id": candidate_id, "project": label["project"],
            "commit": label["commit"], "frozen_label": label["label"],
            "post_freeze_status": "INVALIDATE", "replacement_label": "",
            "reason": reason, "objective_evidence": evidence,
            "discovered_after_prediction_freeze": "true", "included_in_main_results": "false",
        })
    rows.sort(key=lambda r: r["case_id"])
    out = FROZEN / "invalidations.csv"
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    manifest = {
        "audited_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "prediction_freeze_sha256": sha256((ROOT / "predictions" / "prediction_freeze_manifest.json").read_bytes()),
        "frozen_labels_unchanged": True, "relabels": 0, "invalidations": len(rows),
        "invalidated_n4": 4, "invalidated_positive": 0,
        "remaining_valid_n4": 16, "remaining_valid_positive": 20,
        "replacement_cases_added": 0, "selection_after_results": False,
        "policy": "severe errors are excluded as INVALIDATE; original labels remain immutable",
        "invalidations_sha256": sha256(out.read_bytes()),
    }
    (FROZEN / "post_freeze_audit_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
