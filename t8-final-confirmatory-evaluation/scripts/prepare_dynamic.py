#!/usr/bin/env python3
"""Prepare label-free M0/M1/M2 inputs using the frozen Task-6 adapter scope."""
from __future__ import annotations

import re
from pathlib import Path

from common import ROOT, git, read_csv, write_csv


DYNAMIC = ROOT / "dynamic-baseline"
TARGET_BY_PATH = {
    "test/ares-test-fuzz.c": "ares_parse_reply_fuzzer",
    "test/ares-test-fuzz-name.c": "ares_create_query_fuzzer",
    "fuzz/bplist_fuzzer.cc": "bplist_fuzzer",
    "fuzz/xplist_fuzzer.cc": "xplist_fuzzer",
    "fuzz/jplist_fuzzer.cc": "jplist_fuzzer",
    "fuzz/oplist_fuzzer.cc": "oplist_fuzzer",
    "tests/spng_read_fuzzer.c": "spng_read_fuzzer",
    "tests/spng_read_fuzzer.cc": "spng_read_fuzzer",
    "tools/clusterfuzz.cpp": "clusterfuzzer",
    "tools/codecfuzz.cpp": "codecfuzzer",
    "tools/simplifyfuzz.cpp": "simplifyfuzzer",
}
SUPPORTED = {"c-ares", "libplist", "libspng", "meshoptimizer"}
HUNK = re.compile(r"^@@ -(?P<a>\d+)(?:,(?P<ac>\d+))? \+(?P<b>\d+)(?:,(?P<bc>\d+))? @@")


def ranges(values: set[int]) -> str:
    if not values:
        return ""
    output = []
    start = last = min(values)
    for value in sorted(values)[1:]:
        if value == last + 1:
            last = value
        else:
            output.append(str(start) if start == last else f"{start}-{last}")
            start = last = value
    output.append(str(start) if start == last else f"{start}-{last}")
    return ";".join(output)


def changed_rows(case: dict[str, str]) -> list[dict[str, object]]:
    paths = [path for path in case["production_paths"].split(";") if path]
    raw = git(case["project"], "diff", "--unified=0", "--no-renames",
              case["parent"], case["commit"], "--", *paths).stdout
    path = None
    old_line = new_line = 0
    added: dict[str, set[int]] = {}
    deleted: dict[str, set[int]] = {}
    for line in raw.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
            added.setdefault(path, set()); deleted.setdefault(path, set())
            continue
        match = HUNK.match(line)
        if match:
            old_line, new_line = int(match.group("a")), int(match.group("b"))
            continue
        if path is None or line.startswith(("diff --git", "index ", "--- ")):
            continue
        if line.startswith("+"):
            added[path].add(new_line); new_line += 1
        elif line.startswith("-"):
            deleted[path].add(old_line); old_line += 1
        elif not line.startswith("\\"):
            old_line += 1; new_line += 1
    return [{
        "case_id": case["case_id"], "project": case["project"], "path": path,
        "s1_added_or_modified_lines": ranges(added.get(path, set())),
        "s0_deleted_or_modified_lines": ranges(deleted.get(path, set())),
        "s1_changed_line_count": len(added.get(path, set())),
        "s0_changed_line_count": len(deleted.get(path, set())),
    } for path in sorted(set(added) | set(deleted))]


def main() -> None:
    dataset = DYNAMIC / "dataset" / "cases.csv"
    if dataset.exists():
        raise SystemExit("refusing to overwrite dynamic dataset")
    cases = read_csv(ROOT / "frozen-ground-truth" / "cases.csv")
    rows = []
    changes = []
    corpus = []
    for case in cases:
        h0_paths = [path for path in case["h0_paths"].split(";") if path]
        targets = sorted({TARGET_BY_PATH[path] for path in h0_paths if path in TARGET_BY_PATH})
        adapter_supported = case["project"] in SUPPORTED and bool(targets)
        rows.append({
            "case_id": case["case_id"], "project": case["project"],
            "s0_commit": case["parent"], "s1_commit": case["commit"],
            "h0_harness_paths": ";".join(h0_paths), "h0_fuzz_targets": ";".join(targets),
            "adapter_supported": str(adapter_supported).lower(),
            "adapter_scope_reason": "FROZEN_TASK6_ADAPTER" if adapter_supported else "NO_FROZEN_TASK6_ADAPTER_OR_TARGET_MAPPING",
        })
        changes.extend(changed_rows(case))
        for target in targets:
            corpus.append({
                "case_id": case["case_id"], "project": case["project"], "fuzz_target": target,
                "source_commit": case["parent"], "corpus_source": "TASK6_FIXED_SYNTHETIC_FALLBACK",
                "seed_count": 5, "post_commit_data_used": "false",
            })
    write_csv(dataset, rows, list(rows[0]))
    write_csv(DYNAMIC / "dataset" / "changed_code.csv", changes, list(changes[0]))
    write_csv(DYNAMIC / "dataset" / "corpus_manifest.csv", corpus, list(corpus[0]))
    print(f"prepared {len(rows)} cases; {sum(r['adapter_supported'] == 'true' for r in rows)} have frozen adapters")


if __name__ == "__main__":
    main()
