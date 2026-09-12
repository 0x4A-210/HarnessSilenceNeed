#!/usr/bin/env python3
"""Measure direct source-change identifier exposure in H0 versus H1.

This is a static reachability/exposure metric, not dynamic coverage.  It is
reported separately to avoid presenting token evidence as executed coverage.
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path


HERE = Path(__file__).resolve()
OUT = HERE.parents[1]
TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")
STOP = {"const", "static", "return", "struct", "include", "define", "endif", "ifdef", "void", "size_t", "uint32_t", "uint64_t", "true", "false"}


def added_source_tokens(diff: str) -> set[str]:
    values = set()
    for line in diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            values.update(x for x in TOKEN.findall(line[1:]) if x not in STOP)
    return values


def side_text(case_dir: Path, side: str) -> str:
    return "\n".join(path.read_text(encoding="utf-8", errors="replace") for path in sorted((case_dir / side).rglob("*")) if path.is_file())


def main() -> None:
    target = OUT / "results" / "reachability_results.csv"
    if target.exists():
        raise SystemExit("Refusing to overwrite reachability results")
    cases = list(csv.DictReader((OUT / "data" / "verified_positive_cases.csv").open(encoding="utf-8", newline="")))
    rows = []
    for item in cases:
        case_dir = OUT / "cases" / item["case_id"]
        changed = added_source_tokens((case_dir / "source_diff.patch").read_text(encoding="utf-8", errors="replace"))
        h0, h1 = side_text(case_dir, "H0"), side_text(case_dir, "H1")
        h0_tokens, h1_tokens = set(TOKEN.findall(h0)), set(TOKEN.findall(h1))
        r0, r1 = sorted(changed & h0_tokens), sorted(changed & h1_tokens)
        newly_exposed = sorted((changed & h1_tokens) - h0_tokens)
        removed_exposure = sorted((changed & h0_tokens) - h1_tokens)
        rows.append({
            "case_id": item["case_id"], "project": item["project"],
            "commit_id": item["commit_id"], "changed_identifiers": len(changed),
            "h0_direct_exposure_count": len(r0), "h1_direct_exposure_count": len(r1),
            "delta_direct_exposure": len(r1) - len(r0),
            "newly_exposed_identifiers": json.dumps(newly_exposed, separators=(",", ":")),
            "removed_identifiers_from_harness": json.dumps(removed_exposure, separators=(",", ":")),
            "metric_kind": "static_direct_identifier_exposure_not_dynamic_reachability",
        })
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    print(json.dumps({"cases": len(rows), "positive_delta": sum(int(r["delta_direct_exposure"]) > 0 for r in rows), "zero_or_negative_delta": sum(int(r["delta_direct_exposure"]) <= 0 for r in rows)}))


if __name__ == "__main__":
    main()
