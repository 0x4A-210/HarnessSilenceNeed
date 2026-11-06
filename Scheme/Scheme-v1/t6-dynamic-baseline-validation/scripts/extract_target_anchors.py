#!/usr/bin/env python3
from __future__ import annotations

import re

from common import ROOT, git, read_csv, write_csv

MATCH = re.compile(r"^(.*?):(\d+):(.*)$")


def main() -> None:
    rows = []
    for case in read_csv(ROOT / "dataset" / "cases.csv"):
        kind = "NON_FUNCTION" if case["impact_scope"] == "configuration_change" else "FUNCTION"
        for version, commit in (("s0", case["s0_commit"]), ("s1", case["s1_commit"])):
            proc = git(case["project"], "grep", "-n", "-F", "--full-name",
                       case["target_symbol"], commit, "--", "*.c", "*.cc", "*.cpp",
                       "*.cxx", "*.h", "*.hpp", check=False)
            matches = []
            for line in proc.stdout.splitlines():
                # git grep prefixes each row with COMMIT:path:line:text.
                if line.startswith(commit + ":"):
                    line = line[len(commit) + 1:]
                match = MATCH.match(line)
                if not match:
                    continue
                path, lineno, excerpt = match.groups()
                if any(x in path.lower().split("/") for x in
                       ("test", "tests", "fuzz", "tools", "examples", "demo")):
                    continue
                matches.append((path, int(lineno), excerpt.strip()))
            rows.append({
                "case_id": case["case_id"], "project": case["project"],
                "version": version, "commit": commit,
                "target_symbol": case["target_symbol"], "target_kind": kind,
                "present": str(bool(matches)).lower(), "match_count": len(matches),
                "anchors": ";".join(f"{p}:{n}" for p, n, _ in matches),
                "excerpts": " | ".join(x for _, _, x in matches)[:4000],
            })
    fields = ["case_id", "project", "version", "commit", "target_symbol",
              "target_kind", "present", "match_count", "anchors", "excerpts"]
    write_csv(ROOT / "dataset" / "target_anchors.csv", rows, fields)


if __name__ == "__main__":
    main()
