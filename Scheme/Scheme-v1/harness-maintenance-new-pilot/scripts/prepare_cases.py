#!/usr/bin/env python3
"""Label candidates, materialize counterfactuals, and freeze the blind set.

This script deliberately keeps candidate screening/ground truth separate from
the blind inputs.  Candidate messages and H1 are written only to metadata and
ground-truth artifacts.  The input selector uses H0 plus the production diff;
it never reads H1 when selecting context.
"""

from __future__ import annotations

import csv
import hashlib
import json
import random
import re
import shutil
import subprocess
from pathlib import Path, PurePosixPath


HERE = Path(__file__).resolve()
OUT = HERE.parents[1]
ROOT = OUT.parent
PROJECT_ROOT = ROOT / "FSE2026-harness-degradation" / "sources" / "projects"
PRETEST = ROOT / "pre-test"
DATA = OUT / "data"
CASES = OUT / "cases"
SEED = 20260909
SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".inc", ".wuffs"}
EXCLUDED_PARTS = {
    "test", "tests", "testing", "fuzz", "fuzzing", "fuzzers", "doc",
    "docs", "example", "examples", "bench", "benchmark", "benchmarks",
    "third_party", "vendor",
}


# These are the candidates for which manual diff review found a direct,
# reproducible S0/H0 -> S1/H0 adequacy loss and an H1 repair.  build_counterfactual.py
# independently tests the compile claims and measure_reachability.py tests the
# source/harness token relationships.
POSITIVE_SPECS: dict[tuple[str, str], dict[str, str]] = {
    ("c-ares", "9ac7efc38268"): {
        "criterion": "VP3", "mechanism": "new_parser_entry_point",
        "affected": "ares_parse_uri_reply",
        "evidence": "S1 adds the URI reply parser; H0 invokes the pre-existing reply parsers but not URI, while H1 adds ares_parse_uri_reply and cleanup.",
    },
    ("c-ares", "f09f0a021be2"): {
        "criterion": "VP1", "mechanism": "api_symbol_rename",
        "affected": "ares__buf_* -> ares_buf_*",
        "evidence": "S1 removes the ares__ buffer symbol family used by H0; H1 replaces every affected type and call with the new ares_buf family.",
    },
    ("c-ares", "9dd78e2f23a4"): {
        "criterion": "VP3", "mechanism": "new_parser_entry_point",
        "affected": "ares_set_servers_csv",
        "evidence": "S1 adds URI parsing/writing behind ares_set_servers_csv; H0 only creates a DNS query name, while H1 initializes a channel and directly fuzzes the new CSV/URI entry path.",
    },
    ("leptonica", "44a6bc61a6ee"): {
        "criterion": "VP1", "mechanism": "api_signature_change",
        "affected": "fpixCopy; dpixCopy",
        "evidence": "S1 removes the destination argument from fpixCopy/dpixCopy; H0 supplies two arguments throughout, while H1 updates those calls to the one-argument protocol.",
    },
    ("libspng", "e90c6b8dd3c5"): {
        "criterion": "VP1", "mechanism": "initialization_signature_change",
        "affected": "spng_ctx_new",
        "evidence": "S1 changes the constructor to spng_ctx_new(int flags); H0 calls it without an argument and H1 supplies 0.",
    },
    ("libspng", "15f35da3f904"): {
        "criterion": "VP1", "mechanism": "declaration_visibility_change",
        "affected": "spng_set_chunk_limits; spng_get_chunk_limits",
        "evidence": "S1 removes the private chunk-limit declarations from common.h, which H0 includes; H1 restores compilability with explicit declarations while retaining the calls.",
    },
    ("libspng", "64688bb70ce8"): {
        "criterion": "VP1", "mechanism": "source_layout_build_protocol",
        "affected": "spng.h include path",
        "evidence": "S1 moves production code out of src/, invalidating H0's ../src/spng.h include; H1 changes the include to ../spng.h.",
    },
    ("libspng", "c21b8299781e"): {
        "criterion": "VP1", "mechanism": "source_layout_build_protocol",
        "affected": "spng/spng.h include path",
        "evidence": "S1 moves the installed header under spng/, invalidating H0's ../spng.h include; H1 changes it to ../spng/spng.h.",
    },
    ("libspng", "d504fd5f032c"): {
        "criterion": "VP4", "mechanism": "new_configuration_behavior",
        "affected": "SPNG_CRC_DISCARD ancillary CRC action",
        "evidence": "S1 makes ancillary CRC discard a default behavior and adds undo paths; H0 always forces SPNG_CRC_USE, while H1 makes DISCARD fuzzer-selectable.",
    },
    ("meshoptimizer", "546652c9e64c"): {
        "criterion": "VP4", "mechanism": "configuration_value_change",
        "affected": "meshopt_encodeVertexVersion",
        "evidence": "S1 changes the new vertex-codec version from 0xe to 1; H0 continues selecting 0xe and H1 selects 1 for the same fuzz-controlled branch.",
    },
    ("meshoptimizer", "74fd37bd1028"): {
        "criterion": "VP1", "mechanism": "api_signature_change",
        "affected": "meshopt_buildMeshletsSplit",
        "evidence": "S1 adds a fill-weight argument; each H0 call has the old arity and H1 supplies 0.f.",
    },
    ("meshoptimizer", "4da7fb294a4d"): {
        "criterion": "VP1", "mechanism": "api_signature_change",
        "affected": "meshopt_encodeVertexBufferLevel",
        "evidence": "S1 adds a version argument; H0 uses the old arity and H1 supplies -1 to both calls.",
    },
    ("meshoptimizer", "92822f05e4ac"): {
        "criterion": "VP1", "mechanism": "api_symbol_rename",
        "affected": "meshopt_buildMeshletsSplit -> meshopt_buildMeshletsSpatial",
        "evidence": "S1 removes/renames the entry point used by H0; H1 changes all six calls to meshopt_buildMeshletsSpatial.",
    },
    ("wuffs", "5b08ad2ba64b"): {
        "criterion": "VP4", "mechanism": "argument_order_protocol",
        "affected": "check_wuffs_version",
        "evidence": "S1 swaps receiver-size and version arguments; H0 keeps the old order, while H1 supplies sizeof(dec) before WUFFS_VERSION for both targets.",
    },
    ("wuffs", "d770e879abc1"): {
        "criterion": "VP1", "mechanism": "status_type_removal",
        "affected": "wuffs_foo__status -> wuffs_base__status",
        "evidence": "S1 removes codec-specific status types still declared by H0; H1 uses wuffs_base__status.",
    },
    ("wuffs", "3d035df90854"): {
        "criterion": "VP1", "mechanism": "work_buffer_protocol",
        "affected": "wuffs_gif__decoder__decode_frame",
        "evidence": "S1 adds a work-buffer argument to decode_frame; H0 omits it and H1 supplies an empty slice.",
    },
    ("wuffs", "1c75f7b748ae"): {
        "criterion": "VP1", "mechanism": "state_object_protocol_redesign",
        "affected": "image_config; pixel_buffer; frame_config",
        "evidence": "S1 replaces the image-buffer/config protocol with pixel_config, pixel_buffer, and frame_config; H0 uses removed fields/functions and H1 adopts the new state sequence.",
    },
    ("wuffs", "951d79fa0084"): {
        "criterion": "VP1", "mechanism": "argument_order_protocol",
        "affected": "wuffs_gif__decoder__decode_frame",
        "evidence": "S1 reorders decode_frame arguments; H0 retains the old typed ordering and H1 moves blend/disposal arguments before the reader/work buffer.",
    },
    ("wuffs", "fd43e777bc57"): {
        "criterion": "VP4", "mechanism": "initialization_error_protocol",
        "affected": "check_wuffs_version return status",
        "evidence": "S1 makes initialization/version checking return a status; H0 ignores it, while H1 checks the new result before decoding.",
    },
    ("wuffs", "2a32a86a6c62"): {
        "criterion": "VP1", "mechanism": "status_representation_change",
        "affected": "wuffs_base__status.code",
        "evidence": "S1 changes status from an integer to a struct; H0 uses scalar tests/comparisons and H1 accesses .code.",
    },
    ("wuffs", "b840c8004006"): {
        "criterion": "VP1", "mechanism": "status_representation_change",
        "affected": "wuffs_base__status const-char-pointer protocol",
        "evidence": "S1 changes status from a struct to const char*; H0 accesses .code and H1 tests/returns the pointer.",
    },
    ("wuffs", "6fed251b4001"): {
        "criterion": "VP1", "mechanism": "state_layout_change",
        "affected": "wuffs_base__io_buffer data/meta",
        "evidence": "S1 splits io_buffer fields into data and meta; H0 initializes/accesses removed flat fields and H1 constructs/accesses the nested layout.",
    },
    ("wuffs", "c9830ceb9afd"): {
        "criterion": "VP1", "mechanism": "work_buffer_protocol",
        "affected": "decode_io_writer",
        "evidence": "S1 adds a required work-buffer argument; H0 omits it and H1 allocates and passes a correctly sized slice.",
    },
    ("wuffs", "53760ce0fd2f"): {
        "criterion": "VP1", "mechanism": "initialization_protocol_change",
        "affected": "decoder initialize",
        "evidence": "S1 replaces check_wuffs_version on a zeroed decoder with initialize and flags; H0 uses the obsolete protocol and H1 invokes initialize before decoding.",
    },
}

RELATED_NON_POSITIVE = {
    ("brotli", "ccabf811ffce"),
    ("c-ares", "f4c079d9d025"), ("c-ares", "3b10e571daba"),
    ("leptonica", "4cb5129c2a9e"), ("leptonica", "748723a795e4"),
    ("libspng", "a365eb90c6e0"), ("libspng", "264f5c9437b8"),
    ("libspng", "949680795e7d"),
}
UNCERTAIN = {
    ("c-ares", "4a721bac3c52"), ("c-ares", "5d7abd1f8c06"),
    ("leptonica", "187250bda910"), ("leptonica", "989e05e68f30"),
    ("leptonica", "a0b59604bcf2"),
}

# Exactly 20 co-evolution negatives are selected before predictions.  They
# include historical-gap and unrelated-harness hard negatives.
COEV_NEGATIVE = {
    ("brotli", "6ece1d8791a8"), ("brotli", "6db17c87f5b7"),
    ("brotli", "6ee96e291db8"),
    ("c-ares", "f4c079d9d025"), ("c-ares", "c1b00c41a7a1"),
    ("c-ares", "3b10e571daba"), ("c-ares", "1549415228e0"),
    ("c-ares", "8293a05f6340"), ("c-ares", "4a721bac3c52"),
    ("leptonica", "187250bda910"), ("leptonica", "8b06c6b77c92"),
    ("leptonica", "45b3395d4fb3"), ("leptonica", "4cb5129c2a9e"),
    ("leptonica", "989e05e68f30"), ("leptonica", "688a4466c9d1"),
    ("leptonica", "c3b2f15c4316"), ("leptonica", "748723a795e4"),
    ("libspng", "a365eb90c6e0"), ("libspng", "264f5c9437b8"),
    ("libspng", "949680795e7d"),
}

# Two pre-registered "matched" source-only negatives per project, selected by
# list position rather than by their prior LLM outcome.
HISTORICAL_NEGATIVE_PREFIXES = {
    "brotli": ("0a3944c8c99b", "97006561ea9a"),
    "c-ares": ("5dd3629bc934", "3a46457deb9a"),
    "h2o": ("27a55d2e4a15", "7b45fd20aba6"),
    "jansson": ("53e9dd848f92", "1f889c4b603f"),
    "leptonica": ("c8c8974098f0", "4af068b56a96"),
    "libplist": ("a9e34bd29ae9", "2727078f8f2d"),
    "libspng": ("e414c532fe53", "f0a7eb97ddb4"),
    "meshoptimizer": ("0b5709201938", "a53af0ea92a7"),
    "tidy-html5": ("6001011c8099", "1d2a183f32cf"),
    "wuffs": ("fc48e6518994", "8d29cb15ce02"),
}


def run(command: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and result.returncode:
        raise RuntimeError(f"command failed: {' '.join(command)}\n{result.stderr}")
    return result


def git(repo: Path, *args: str, check: bool = True) -> str:
    return run(["git", "-C", str(repo), *args], check=check).stdout


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8", newline="\n")


def write_json(path: Path, value: object) -> None:
    write_text(path, json.dumps(value, indent=2, ensure_ascii=False))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def key_for(row: dict[str, str]) -> tuple[str, str]:
    for project, prefix in list(POSITIVE_SPECS) + list(RELATED_NON_POSITIVE) + list(UNCERTAIN) + list(COEV_NEGATIVE):
        if row["project"] == project and row["commit_id"].startswith(prefix):
            return project, prefix
    return row["project"], row["commit_id"][:12]


def source_paths(row: dict[str, str]) -> list[str]:
    return list(json.loads(row["source_files_changed"]))


def harness_paths(row: dict[str, str]) -> list[str]:
    return list(json.loads(row["harness_files_changed"]))


def file_at(repo: Path, revision: str, path: str) -> str | None:
    exists = run(["git", "-C", str(repo), "cat-file", "-e", f"{revision}:{path}"], check=False)
    if exists.returncode:
        return None
    return git(repo, "show", f"{revision}:{path}")


def rename_map(repo: Path, parent: str, commit: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in git(repo, "diff", "--name-status", "-M", parent, commit).splitlines():
        fields = line.split("\t")
        if fields and fields[0].startswith("R") and len(fields) == 3:
            result[fields[2]] = fields[1]
    return result


def copy_revision_files(repo: Path, revision: str, paths: list[str], target: Path,
                        old_names: dict[str, str] | None = None) -> list[str]:
    written: list[str] = []
    for new_path in paths:
        path = old_names.get(new_path, new_path) if old_names else new_path
        value = file_at(repo, revision, path)
        if value is None:
            continue
        write_text(target / path, value)
        written.append(path)
    return written


def language(path: str) -> str:
    return {".c": "c", ".h": "c", ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".wuffs": "text"}.get(PurePosixPath(path).suffix.lower(), "text")


def clip_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value.rstrip()
    head = value[: limit // 2]
    tail = value[-limit // 2 :]
    return head + "\n... [deterministic middle clipping] ...\n" + tail


def select_source_diff(diff: str, h0_text: str, limit: int = 70_000) -> tuple[str, bool]:
    """Select context using H0 identifiers only; H1 is never an input."""
    if len(diff) <= limit:
        return diff.rstrip(), False
    identifiers = {x for x in re.findall(r"[A-Za-z_][A-Za-z0-9_]{5,}", h0_text) if len(x) >= 6}
    lines = diff.splitlines()
    keep: set[int] = set(range(min(180, len(lines))))
    keep.update(range(max(0, len(lines) - 180), len(lines)))
    for index, line in enumerate(lines):
        if any(token in line for token in identifiers):
            keep.update(range(max(0, index - 18), min(len(lines), index + 25)))
    selected: list[str] = []
    previous = -2
    used = 0
    for index in sorted(keep):
        line = lines[index]
        extra = len(line) + 1
        if used + extra > limit:
            break
        if index != previous + 1:
            selected.append("... [unselected diff lines omitted by frozen H0-anchored rule] ...")
            used += 70
        selected.append(line)
        used += extra
        previous = index
    return "\n".join(selected).rstrip(), True


def candidate_blind_input(case_id: str, source_diff: str, h0_files: list[tuple[str, str]]) -> str:
    combined = "\n".join(value for _, value in h0_files)
    selected, clipped = select_source_diff(source_diff, combined)
    harness_sections = []
    for path, value in h0_files:
        harness_sections.append(f"### `{path}`\n\n~~~~{language(path)}\n{clip_text(value, 30_000)}\n~~~~")
    if not harness_sections:
        harness_sections.append("No pre-commit harness file exists at the changed harness path.")
    clipping = "The source diff is complete." if not clipped else "The source diff is a deterministic H0-identifier-anchored excerpt capped at 70,000 characters."
    return f"""# Case ID

{case_id}

## Existing Fuzz Harness H0

{chr(10).join(harness_sections)}

## Production Source Change (S0 -> S1)

Harness changes, commit messages, tests, outcomes, and future evidence are excluded. {clipping}

~~~~diff
{selected}
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
"""


def semantic_label(key: tuple[str, str]) -> tuple[str, str, str]:
    if key in POSITIVE_SPECS:
        return "RELATED", "PASS_VERIFIED_POSITIVE", POSITIVE_SPECS[key]["evidence"]
    if key in RELATED_NON_POSITIVE:
        if key == ("brotli", "ccabf811ffce"):
            return "RELATED", "NOT_VALIDATABLE_H0_ABSENT", "The new decoder target is semantically related, but no pre-commit H0 exists, so it cannot establish an evolution-induced loss in an existing harness."
        return "RELATED", "FAIL_NO_COMMIT_INDUCED_GAP", "The source and harness edits concern the same area, but review found no H0 adequacy loss caused by S0-to-S1; the H1 edit is cleanup, optional exposure, or repair of an already-existing gap."
    if key in UNCERTAIN:
        return "UNCERTAIN", "INCONCLUSIVE", "The commit bundles multiple source and harness fixes or is a duplicate/conditional-port change, so attribution cannot be isolated stably."
    return "UNRELATED", "NOT_RUN_UNRELATED", "The harness edit is formatting, licensing, warning cleanup, repository cleanup, or an independent harness bug fix not semantically caused by the production change."


def materialize_candidate(index: int, row: dict[str, str]) -> dict[str, object]:
    pid = f"P{index:03d}"
    repo = PROJECT_ROOT / row["project"]
    parent, commit = row["parent_commit"], row["commit_id"]
    paths_s, paths_h = source_paths(row), harness_paths(row)
    case_dir = CASES / pid
    old_names = rename_map(repo, parent, commit)
    h0_written = copy_revision_files(repo, parent, paths_h, case_dir / "H0", old_names)
    h1_written = copy_revision_files(repo, commit, paths_h, case_dir / "H1")
    source_diff = git(repo, "diff", "--no-ext-diff", "--find-renames", parent, commit, "--", *paths_s)
    harness_diff = git(repo, "diff", "--no-ext-diff", "--find-renames", parent, commit, "--", *paths_h)
    write_text(case_dir / "source_diff.patch", source_diff or "# No textual source diff")
    write_text(case_dir / "harness_diff.patch", harness_diff or "# No textual harness diff")
    h0_pairs = []
    for path in h0_written:
        h0_pairs.append((path, (case_dir / "H0" / path).read_text(encoding="utf-8", errors="replace")))
    key = key_for(row)
    label, validation, rationale = semantic_label(key)
    blind = candidate_blind_input(pid, source_diff, h0_pairs)
    write_text(case_dir / "blind_input.md", blind)
    write_text(case_dir / "ground_truth.md", f"""# Candidate ground truth: {pid}

- Semantic label: {label}
- Counterfactual status: {validation}
- Verified maintenance positive: {str(key in POSITIVE_SPECS).lower()}
- Rationale: {rationale}
""")
    metadata = {
        "case_id": pid, "case_role": "candidate", "project": row["project"],
        "commit": commit, "parent": parent, "timestamp": row["timestamp"],
        "source_files": paths_s, "harness_files": paths_h,
        "h0_files_materialized": h0_written, "h1_files_materialized": h1_written,
        "candidate_change_type": label, "counterfactual_status": validation,
        "verified_positive": key in POSITIVE_SPECS,
        "commit_message_withheld_from_predictor": row["commit_message"],
    }
    write_json(case_dir / "metadata.json", metadata)
    return {"pid": pid, "row": row, "key": key, "label": label,
            "validation": validation, "rationale": rationale,
            "blind": blind, "source_diff": source_diff, "harness_diff": harness_diff,
            "h0_written": h0_written, "h1_written": h1_written}


def copy_candidate_to_final(item: dict[str, object], case_id: str, label: str) -> dict[str, object]:
    source = CASES / str(item["pid"])
    target = CASES / case_id
    target.mkdir(parents=True)
    for name in ("source_diff.patch", "harness_diff.patch"):
        shutil.copyfile(source / name, target / name)
    shutil.copytree(source / "H0", target / "H0")
    shutil.copytree(source / "H1", target / "H1")
    blind = str(item["blind"]).replace(f"\n{item['pid']}\n", f"\n{case_id}\n", 1)
    write_text(target / "blind_input.md", blind)
    row = item["row"]
    assert isinstance(row, dict)
    key = item["key"]
    assert isinstance(key, tuple)
    spec = POSITIVE_SPECS.get(key)
    if label == "positive":
        assert spec
        gt = f"""# Ground truth: {case_id}

- Actual label: positive
- Criterion: {spec['criterion']}
- Mechanism: {spec['mechanism']}
- Affected function/API/state: {spec['affected']}
- Counterfactual evidence: {spec['evidence']}
"""
    else:
        gt = f"""# Ground truth: {case_id}

- Actual label: negative
- Negative subtype: coevolution_without_commit_induced_gap
- Semantic screen: {item['label']}
- Counterfactual result: {item['validation']}
- Evidence: {item['rationale']}
"""
    write_text(target / "ground_truth.md", gt)
    metadata = {
        "case_id": case_id, "case_role": "blind_test", "actual_label": label,
        "project": row["project"], "commit": row["commit_id"],
        "parent": row["parent_commit"], "timestamp": row["timestamp"],
        "candidate_case": item["pid"], "negative_subtype": "" if label == "positive" else "coevolution_without_commit_induced_gap",
        "mechanism": spec["mechanism"] if spec else "none",
    }
    write_json(target / "metadata.json", metadata)
    return metadata


def historical_negative_records() -> list[dict[str, str]]:
    mapping = list(csv.DictReader((PRETEST / "data" / "case_mapping.csv").open(encoding="utf-8", newline="")))
    records: list[dict[str, str]] = []
    for project, prefixes in HISTORICAL_NEGATIVE_PREFIXES.items():
        for prefix in prefixes:
            matches = [row for row in mapping if row["project"] == project and row["commit_id"].startswith(prefix)]
            if len(matches) != 1:
                raise RuntimeError(f"expected one prior mapping for {project} {prefix}, got {len(matches)}")
            row = matches[0]
            if row["actual_label"] != "negative":
                raise RuntimeError(f"prior source-only selection is not negative: {row}")
            records.append(row)
    return records


def copy_historical_negative(row: dict[str, str], case_id: str) -> dict[str, object]:
    prior = (PRETEST / "cases" / f"{row['case_id']}.md").read_text(encoding="utf-8")
    prior = prior.replace(f"\n{row['case_id']}\n", f"\n{case_id}\n", 1)
    prior = prior.split("\n## Question\n", 1)[0].rstrip() + "\n\n## Available Context\n\nOnly H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.\n"
    target = CASES / case_id
    target.mkdir(parents=True)
    write_text(target / "blind_input.md", prior)
    h0_match = re.search(r"## Existing Fuzz Harness H0\n(.*?)\n## Source Change", prior, re.S)
    diff_match = re.search(r"~~~~diff\n(.*?)\n~~~~", prior, re.S)
    h0_text = h0_match.group(1).strip() if h0_match else "Historical H0 is embedded in blind_input.md."
    diff_text = diff_match.group(1).strip() if diff_match else "# See blind_input.md"
    write_text(target / "H0" / "harness_context.md", h0_text)
    write_text(target / "H1" / "harness_context.md", h0_text)
    write_text(target / "source_diff.patch", diff_text)
    write_text(target / "harness_diff.patch", "# Harness unchanged for this source-only negative.")
    write_text(target / "ground_truth.md", f"""# Ground truth: {case_id}

- Actual label: negative
- Negative subtype: source_only_internal_change
- Evidence: The production change adds no entry point, calling protocol, initialization/state requirement, configuration requirement, or input constraint; the historical H0 retains the same high-level path.
""")
    metadata = {
        "case_id": case_id, "case_role": "blind_test", "actual_label": "negative",
        "project": row["project"], "commit": row["commit_id"],
        "parent": row["previous_commit"], "timestamp": row["commit_time"],
        "candidate_case": "", "negative_subtype": "source_only_internal_change",
        "mechanism": "none", "prior_materialization_case": row["case_id"],
    }
    write_json(target / "metadata.json", metadata)
    return metadata


def main() -> None:
    if any(CASES.glob("C*")) or any(CASES.glob("P*")):
        raise SystemExit("Refusing to overwrite frozen case directories")
    candidate_rows = list(csv.DictReader((DATA / "co_evolution_candidates.csv").open(encoding="utf-8", newline="")))
    if len(candidate_rows) != 50:
        raise RuntimeError(f"expected 50 candidates, found {len(candidate_rows)}")
    candidates = [materialize_candidate(index, row) for index, row in enumerate(candidate_rows, 1)]
    candidate_by_key = {item["key"]: item for item in candidates}
    missing_positive = set(POSITIVE_SPECS) - set(candidate_by_key)
    if missing_positive:
        raise RuntimeError(f"positive specifications not in candidate sample: {missing_positive}")
    if len(POSITIVE_SPECS) != 24 or len(COEV_NEGATIVE) != 20:
        raise RuntimeError("frozen sample cardinality changed")

    semantic_rows = []
    for item in candidates:
        row = item["row"]
        assert isinstance(row, dict)
        semantic_rows.append({
            "candidate_case_id": item["pid"], "project": row["project"],
            "commit_id": row["commit_id"], "parent_commit": row["parent_commit"],
            "semantic_label": item["label"], "counterfactual_status": item["validation"],
            "verified_positive": str(item["key"] in POSITIVE_SPECS).lower(),
            "rationale": item["rationale"],
        })
    write_csv(DATA / "co_evolution_semantic_labels.csv", semantic_rows, list(semantic_rows[0]))

    pool: list[dict[str, object]] = []
    for key in POSITIVE_SPECS:
        pool.append({"kind": "candidate", "label": "positive", "item": candidate_by_key[key], "sort": f"P:{key}"})
    for key in COEV_NEGATIVE:
        if key not in candidate_by_key:
            raise RuntimeError(f"co-evolution negative not sampled: {key}")
        pool.append({"kind": "candidate", "label": "negative", "item": candidate_by_key[key], "sort": f"N:{key}"})
    for row in historical_negative_records():
        pool.append({"kind": "historical", "label": "negative", "item": row, "sort": f"H:{row['project']}:{row['commit_id']}"})
    if len(pool) != 64:
        raise RuntimeError(f"expected 64 blind cases, found {len(pool)}")
    pool.sort(key=lambda x: str(x["sort"]))
    random.Random(SEED).shuffle(pool)

    final_metadata = []
    for index, entry in enumerate(pool, 1):
        cid = f"C{index:03d}"
        if entry["kind"] == "candidate":
            meta = copy_candidate_to_final(entry["item"], cid, str(entry["label"]))
        else:
            meta = copy_historical_negative(entry["item"], cid)
        final_metadata.append(meta)

    positives, negatives = [], []
    for meta in final_metadata:
        base = {
            "case_id": meta["case_id"], "project": meta["project"],
            "commit_id": meta["commit"], "parent_commit": meta["parent"],
            "timestamp": meta["timestamp"], "mechanism": meta["mechanism"],
            "negative_subtype": meta["negative_subtype"],
        }
        if meta["actual_label"] == "positive":
            key = next(key for key in POSITIVE_SPECS if key[0] == meta["project"] and str(meta["commit"]).startswith(key[1]))
            spec = POSITIVE_SPECS[key]
            base.update({"vp_criterion": spec["criterion"], "affected": spec["affected"], "counterfactual_evidence": spec["evidence"]})
            positives.append(base)
        else:
            negatives.append(base)
    write_csv(DATA / "verified_positive_cases.csv", positives,
              ["case_id", "project", "commit_id", "parent_commit", "timestamp", "mechanism", "vp_criterion", "affected", "counterfactual_evidence", "negative_subtype"])
    write_csv(DATA / "verified_negative_cases.csv", negatives,
              ["case_id", "project", "commit_id", "parent_commit", "timestamp", "mechanism", "negative_subtype"])
    manifest = {
        "seed": SEED, "candidate_count": len(candidates),
        "verified_positive_count": len(positives), "verified_negative_count": len(negatives),
        "case_count": len(final_metadata),
        "cases": [{"case_id": m["case_id"], "blind_input_sha256": hashlib.sha256((CASES / str(m["case_id"]) / "blind_input.md").read_bytes()).hexdigest()} for m in final_metadata],
    }
    write_json(DATA / "dataset_manifest.json", manifest)
    print(json.dumps({k: v for k, v in manifest.items() if k != "cases"}, indent=2))


if __name__ == "__main__":
    main()
