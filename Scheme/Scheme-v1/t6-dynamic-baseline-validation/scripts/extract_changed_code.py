#!/usr/bin/env python3
from __future__ import annotations

import re

from common import ROOT, git, read_csv, write_csv

HUNK = re.compile(r"^@@ -(?P<a>\d+)(?:,(?P<ac>\d+))? \+(?P<b>\d+)(?:,(?P<bc>\d+))? @@")


def ranges(values: set[int]) -> str:
    if not values:
        return ""
    parts = []
    start = last = min(values)
    for value in sorted(values)[1:]:
        if value == last + 1:
            last = value
            continue
        parts.append(str(start) if start == last else f"{start}-{last}")
        start = last = value
    parts.append(str(start) if start == last else f"{start}-{last}")
    return ";".join(parts)


def main() -> None:
    out = []
    for case in read_csv(ROOT / "dataset" / "cases.csv"):
        proc = git(case["project"], "diff", "--unified=0", "--no-renames",
                   case["s0_commit"], case["s1_commit"], "--")
        path = None
        old_line = new_line = 0
        added: dict[str, set[int]] = {}
        deleted: dict[str, set[int]] = {}
        for line in proc.stdout.splitlines():
            if line.startswith("+++ b/"):
                path = line[6:]
                added.setdefault(path, set())
                deleted.setdefault(path, set())
                continue
            match = HUNK.match(line)
            if match:
                old_line = int(match.group("a"))
                new_line = int(match.group("b"))
                continue
            if path is None or line.startswith(("diff --git", "index ", "--- ")):
                continue
            if line.startswith("+"):
                added[path].add(new_line)
                new_line += 1
            elif line.startswith("-"):
                deleted[path].add(old_line)
                old_line += 1
            else:
                old_line += 1
                new_line += 1
        for path in sorted(set(added) | set(deleted)):
            if not path.lower().endswith((".c", ".cc", ".cpp", ".cxx", ".h", ".hpp")):
                continue
            if any(part in path.lower() for part in ("test", "fuzz", "example")):
                continue
            out.append({
                "case_id": case["case_id"], "project": case["project"],
                "path": path, "s1_added_or_modified_lines": ranges(added.get(path, set())),
                "s0_deleted_or_modified_lines": ranges(deleted.get(path, set())),
                "s1_changed_line_count": len(added.get(path, set())),
                "s0_changed_line_count": len(deleted.get(path, set())),
                "target_symbol": case["target_symbol"],
            })
    fields = ["case_id", "project", "path", "s1_added_or_modified_lines",
              "s0_deleted_or_modified_lines", "s1_changed_line_count",
              "s0_changed_line_count", "target_symbol"]
    write_csv(ROOT / "dataset" / "changed_code.csv", out, fields)


if __name__ == "__main__":
    main()
