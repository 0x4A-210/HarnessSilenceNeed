#!/usr/bin/env python3
"""Freeze the pre-audit candidate selection and construct matched pairs.

This script never reads model outputs.  Selection is based only on immutable
repository facts, the pre-declared exclusion lists, and the N4/P definitions in
task-4.md.  Ground-truth audit and prediction freezing are separate steps.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment


HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
WORKSPACE = ROOT.parent
REPO = WORKSPACE / "FSE2026-harness-degradation" / "sources" / "projects" / "wuffs"
DATA = ROOT / "data"

# These were selected before any task-4 prediction.  Formatting-only language
# migrations and commits that themselves introduce an unexposed config/package
# were deliberately not admitted as N4 controls.
N4_RAW_IDS = [
    "R0002", "R0003", "R0008", "R0010", "R0011", "R0013", "R0014",
    "R0019", "R0020", "R0023", "R0024", "R0028", "R0029", "R0032",
    "R0035", "R0044", "R0045", "R0046", "R0047",
]
POSITIVE_RAW_IDS = [
    "R0001", "R0007", "R0009", "R0016", "R0018", "R0021", "R0022",
    "R0025", "R0027", "R0030", "R0033",
    "R0036", "R0038", "R0039", "R0042", "R0043",
]

# A clean, previously unused source-only JPEG bug fix.  restart_frame was a
# direct-API exposure gap on both sides; the commit changes work-buffer logic,
# not the exposure requirement for restart_frame.
CUSTOM_N4 = {
    "raw_id": "X0001",
    "project": "wuffs",
    "commit": "53b3b0a9d002a6a43f390f88c6442fe06fa0b7b1",
    "parent": "affff51fbf47d401918845583e126e9d622069ce",
    "timestamp": "2024-09-08T11:29:01+10:00",
    "commit_message": "std/jpeg: fix default-quality workbuf length check",
    "source_file": "std/jpeg/decode_jpeg.wuffs",
    "target_function": "decoder.restart_frame",
    "simple_name": "restart_frame",
    "signal": "N4_EXISTING_GAP_SIGNAL",
    "signature_s0": "pub func decoder.restart_frame!(index: base.u64, io_position: base.u64) base.status {",
    "signature_s1": "pub func decoder.restart_frame!(index: base.u64, io_position: base.u64) base.status {",
    "fuzz_refs_s0": "0",
    "fuzz_refs_s1": "0",
    "internal_calls_s0": "0",
    "internal_calls_s1": "0",
    "semantic_added_loc_file": "2",
    "semantic_deleted_loc_file": "2",
    "source_files_changed": '["std/jpeg/decode_jpeg.wuffs"]',
}

# The raw miner found these commits through an existing method.  Their actual
# positive targets are newly introduced public configurations and states.
SPECIAL_POSITIVE_OVERRIDES = {
    "R0031": {
        "target_function": "QUIRK_ALLOW_NON_ZERO_INITIAL_BYTE",
        "simple_name": "QUIRK_ALLOW_NON_ZERO_INITIAL_BYTE", "signature_s0": "ABSENT",
        "signature_s1": "pub const QUIRK_ALLOW_NON_ZERO_INITIAL_BYTE : base.u32 = 0x5058_E000 | 0x00",
        "signal": "COMMIT_INDUCED_POSITIVE_SIGNAL", "source_file": "std/lzma/decode_quirks.wuffs",
    },
    "R0037": {
        "target_function": "QUIRK_REJECT_PROGRESSIVE_JPEGS",
        "simple_name": "QUIRK_REJECT_PROGRESSIVE_JPEGS", "signature_s0": "ABSENT",
        "signature_s1": "pub const QUIRK_REJECT_PROGRESSIVE_JPEGS : base.u32 = 0x48BF_D800 | 0x00",
        "signal": "COMMIT_INDUCED_POSITIVE_SIGNAL", "source_file": "std/jpeg/decode_quirks.wuffs",
    },
    "R0041": {
        "target_function": "QUIRK_JUST_RAW_THUMBHASH",
        "simple_name": "QUIRK_JUST_RAW_THUMBHASH", "signature_s0": "ABSENT",
        "signature_s1": "pub const QUIRK_JUST_RAW_THUMBHASH : base.u32 = 0x660F_6000 | 0x00",
        "signal": "COMMIT_INDUCED_POSITIVE_SIGNAL", "source_file": "std/thumbhash/decode_quirks.wuffs",
    },
}

# A pre-window but previously unused full decoder introduction.  It replaces a
# weak read-only-getter candidate; the source entry point itself is material.
CUSTOM_POSITIVE = {
    "raw_id": "X0002", "project": "wuffs",
    "commit": "58c30e9d6d306fcb772db24aa42c4817f36b4497",
    "parent": "47a231f67905157ca7322fcbd4bef3e3a3912c32",
    "timestamp": "2020-12-23T22:11:04+11:00", "commit_message": "Add std/png",
    "source_file": "std/png/decode_png.wuffs", "target_function": "decoder.decode_frame",
    "simple_name": "wuffs_png", "signal": "COMMIT_INDUCED_POSITIVE_SIGNAL",
    "signature_s0": "ABSENT",
    "signature_s1": "pub func decoder.decode_frame?(dst: ptr base.pixel_buffer, src: base.io_reader, blend: base.pixel_blend, workbuf: slice base.u8, opts: nptr base.decode_frame_options) {",
    "fuzz_refs_s0": "0", "fuzz_refs_s1": "0", "internal_calls_s0": "0", "internal_calls_s1": "0",
    "semantic_added_loc_file": "287", "semantic_deleted_loc_file": "0",
    "source_files_changed": '["std/png/decode_png.wuffs"]',
}


def git(*args: str) -> str:
    result = subprocess.run(["git", "-C", str(REPO), *args], text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return result.stdout


def production_stats(commit: str) -> tuple[list[str], int, int, int]:
    paths: list[str] = []
    added = deleted = 0
    for line in git("show", "--numstat", "--format=", "--no-renames", commit).splitlines():
        fields = line.split("\t")
        if len(fields) != 3:
            continue
        a, d, path = fields
        # Wuffs .wuffs files are the hand-written production sources. Generated
        # release snapshots are omitted from model context and matching stats.
        if path.startswith("std/") and path.endswith(".wuffs"):
            paths.append(path)
            added += int(a) if a.isdigit() else 0
            deleted += int(d) if d.isdigit() else 0
    return sorted(paths), added, deleted, added + deleted


def family(row: dict[str, str]) -> str:
    path = row["source_file"]
    module = path.split("/")[1] if path.startswith("std/") else "other"
    target = row["target_function"]
    if "hasher" in target or module in {"adler32", "crc32", "crc64", "sha256", "xxhash32", "xxhash64"}:
        return "hash-api"
    if target.startswith("QUIRK_") or target.endswith("get_quirk"):
        return "decoder-config"
    if "history" in target:
        return "decoder-history"
    if any(x in target for x in ("frame", "animation", "tell_me_more")):
        return "image-decoder-api"
    return "decoder-api"


def decorate(row: dict[str, str], candidate_id: str, case_type: str) -> dict[str, str]:
    row = dict(row)
    paths, added, deleted, changed = production_stats(row["commit"])
    row.update({
        "candidate_id": candidate_id,
        "case_type": case_type,
        "label": "NEGATIVE" if case_type == "N4_EXISTING_GAP" else "POSITIVE",
        "production_source_files": json.dumps(paths, separators=(",", ":")),
        "production_file_count": str(len(paths)),
        "production_added_loc": str(added),
        "production_deleted_loc": str(deleted),
        "production_changed_loc": str(changed),
        "functional_family": family(row),
        "selection_uses_predictions": "false",
    })
    return row


def parse_time(value: str) -> dt.datetime:
    return dt.datetime.fromisoformat(value)


def main() -> None:
    csv.field_size_limit(sys.maxsize)
    with (DATA / "raw_candidates.csv").open(encoding="utf-8", newline="") as handle:
        raw = list(csv.DictReader(handle))
    by_id = {row["raw_id"]: row for row in raw}
    missing = (set(N4_RAW_IDS) | set(POSITIVE_RAW_IDS) | set(SPECIAL_POSITIVE_OVERRIDES)) - set(by_id)
    if missing:
        raise SystemExit(f"missing raw candidates: {sorted(missing)}")

    n4_source = [by_id[x] for x in N4_RAW_IDS] + [CUSTOM_N4]
    positive_source = [by_id[x] for x in POSITIVE_RAW_IDS] + [CUSTOM_POSITIVE]
    for raw_id, overrides in SPECIAL_POSITIVE_OVERRIDES.items():
        special = dict(by_id[raw_id]); special.update(overrides); positive_source.append(special)

    n4_source.sort(key=lambda r: (r["timestamp"], r["commit"]))
    positive_source.sort(key=lambda r: (r["timestamp"], r["commit"]))
    n4 = [decorate(row, f"N4{index:03d}", "N4_EXISTING_GAP")
          for index, row in enumerate(n4_source, 1)]
    positives = [decorate(row, f"P{index:03d}", "COMMIT_INDUCED_POSITIVE")
                 for index, row in enumerate(positive_source, 1)]
    if len(n4) != 20 or len(positives) != 20:
        raise SystemExit(f"expected 20+20, got {len(n4)}+{len(positives)}")
    if len({x["commit"] for x in n4 + positives}) != 40:
        raise SystemExit("case commits are not unique")

    fields = list(n4[0])
    for name, rows in (("n4_candidates.csv", n4), ("positive_candidates.csv", positives)):
        with (DATA / name).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader(); writer.writerows(rows)

    # Pair on facts that exist before prediction.  Costs are explicit and are
    # used only for matching, never for labels.
    matrix = np.zeros((len(n4), len(positives)))
    for i, left in enumerate(n4):
        for j, right in enumerate(positives):
            days = abs((parse_time(left["timestamp"]) - parse_time(right["timestamp"])).total_seconds()) / 86400
            loc_delta = abs(math.log1p(int(left["production_changed_loc"])) -
                            math.log1p(int(right["production_changed_loc"])))
            file_delta = abs(int(left["production_file_count"]) - int(right["production_file_count"]))
            family_penalty = 0 if left["functional_family"] == right["functional_family"] else 1
            matrix[i, j] = (days / 365.25) + (0.75 * loc_delta) + (0.20 * file_delta) + (0.50 * family_penalty)
    rows_i, rows_j = linear_sum_assignment(matrix)
    pairs = []
    for number, (i, j) in enumerate(sorted(zip(rows_i, rows_j), key=lambda p: n4[p[0]]["candidate_id"]), 1):
        left, right = n4[i], positives[j]
        pairs.append({
            "pair_id": f"M{number:03d}", "n4_candidate_id": left["candidate_id"],
            "positive_candidate_id": right["candidate_id"], "project_match": "true",
            "n4_commit": left["commit"], "positive_commit": right["commit"],
            "time_distance_days": f"{abs((parse_time(left['timestamp']) - parse_time(right['timestamp'])).total_seconds()) / 86400:.3f}",
            "n4_changed_loc": left["production_changed_loc"],
            "positive_changed_loc": right["production_changed_loc"],
            "n4_file_count": left["production_file_count"],
            "positive_file_count": right["production_file_count"],
            "n4_family": left["functional_family"],
            "positive_family": right["functional_family"],
            "functional_family_exact_match": str(left["functional_family"] == right["functional_family"]).lower(),
            "matching_cost": f"{matrix[i, j]:.6f}",
            "matching_algorithm": "minimum-total-cost Hungarian; pre-prediction facts only",
        })
    with (DATA / "matched_pairs.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(pairs[0]))
        writer.writeheader(); writer.writerows(pairs)

    selected_raw = set(N4_RAW_IDS) | set(POSITIVE_RAW_IDS) | set(SPECIAL_POSITIVE_OVERRIDES)
    exclusions = []
    reason_by_id = {
        "R0004": "formatting-only commit; violates N4-5",
        "R0005": "formatting-only commit; violates N4-5",
        "R0006": "language-wide syntax migration; no stable production-behavior contrast",
        "R0012": "new read-only getter alone is not a sufficiently material fuzz target",
        "R0015": "new history-length getter alone is not a sufficiently material fuzz target",
        "R0017": "new checksum getter alone is not a sufficiently material fuzz target",
        "R0026": "adds LZMA2 support and can aggravate an absent-subsystem gap; ambiguous N4",
        "R0034": "language syntax cleanup; no meaningful behavior change",
        "R0040": "implements a previously placeholder decoder; commit-induced gap confound",
    }
    for row in raw:
        if row["raw_id"] in selected_raw:
            continue
        exclusions.append({
            "raw_id": row["raw_id"], "project": row["project"], "commit": row["commit"],
            "signal": row["signal"], "reason": reason_by_id.get(row["raw_id"], "surplus candidate not needed after fixed 20+20 sampling"),
            "excluded_before_predictions": "true",
        })
    with (DATA / "excluded_cases.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(exclusions[0]))
        writer.writeheader(); writer.writerows(exclusions)

    manifest = {
        "stage": "candidate-selection-before-ground-truth-audit",
        "n4_count": len(n4), "positive_count": len(positives), "unique_commit_count": 40,
        "project_count": len({x["project"] for x in n4 + positives}),
        "selection_uses_predictions": False,
        "prediction_files_present_when_selected": False,
        "matching_algorithm": pairs[0]["matching_algorithm"],
        "raw_candidate_manifest": json.loads((DATA / "mining_manifest.json").read_text()),
    }
    (DATA / "selection_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
