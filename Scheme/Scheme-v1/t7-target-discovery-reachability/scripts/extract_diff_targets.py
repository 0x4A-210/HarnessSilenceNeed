#!/usr/bin/env python3
"""Parse production-only S0->S1 changes into deterministic changed-line ranges."""
from __future__ import annotations

import re

from common import git, is_production


HUNK = re.compile(r"^@@ -(?P<old>\d+)(?:,(?P<old_n>\d+))? \+(?P<new>\d+)(?:,(?P<new_n>\d+))? @@")


def production_diff(project: str, s0: str, s1: str) -> dict:
    raw = git(project, "diff", "--no-ext-diff", "--no-renames", "--unified=0",
              "--diff-filter=ACMRT", s0, s1, "--").stdout.decode("utf-8", errors="replace")
    changed: dict[str, set[int]] = {}
    old_changed: dict[str, set[int]] = {}
    current_old = ""
    current_new = ""
    old_line = new_line = 0
    in_hunk = False
    for line in raw.splitlines():
        if line.startswith("diff --git "):
            in_hunk = False
            continue
        if line.startswith("--- "):
            current_old = line[4:].removeprefix("a/") if line[4:] != "/dev/null" else ""
            continue
        if line.startswith("+++ "):
            current_new = line[4:].removeprefix("b/") if line[4:] != "/dev/null" else ""
            continue
        match = HUNK.match(line)
        if match:
            old_line = int(match.group("old"))
            new_line = int(match.group("new"))
            in_hunk = True
            continue
        if not in_hunk:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            if current_new and is_production(current_new):
                changed.setdefault(current_new, set()).add(new_line)
            new_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            if current_old and is_production(current_old):
                old_changed.setdefault(current_old, set()).add(old_line)
            old_line += 1
        elif not line.startswith("\\"):
            old_line += 1
            new_line += 1
    return {
        "changed_lines_s1": {key: sorted(value) for key, value in sorted(changed.items())},
        "changed_lines_s0": {key: sorted(value) for key, value in sorted(old_changed.items())},
        "production_files_s1": sorted(changed),
        "production_files_s0": sorted(old_changed),
        "raw_diff_bytes": len(raw.encode("utf-8")),
    }


def intersects(lines: list[int], start: int, end: int) -> bool:
    return any(start <= line <= end for line in lines)
