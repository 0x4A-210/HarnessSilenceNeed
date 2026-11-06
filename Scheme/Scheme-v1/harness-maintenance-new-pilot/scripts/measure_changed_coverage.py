#!/usr/bin/env python3
"""Record changed-code coverage availability without inventing measurements.

The pilot's VP1 cases are established by build incompatibility and VP3/VP4 by
direct entry/configuration evidence.  Historical seed corpora and reproducible
instrumented builds are not available uniformly.  This script therefore emits
explicit NOT_MEASURED rows instead of mislabeling static overlap as coverage.
"""

from __future__ import annotations

import csv
from pathlib import Path


HERE = Path(__file__).resolve()
OUT = HERE.parents[1]


def main() -> None:
    target = OUT / "results" / "coverage_results.csv"
    if target.exists():
        raise SystemExit("Refusing to overwrite coverage results")
    cases = list(csv.DictReader((OUT / "data" / "verified_positive_cases.csv").open(encoding="utf-8", newline="")))
    fields = ["case_id", "project", "commit_id", "changed_coverage_h0", "changed_coverage_h1", "delta_changed_coverage", "status", "reason"]
    rows = [{
        "case_id": x["case_id"], "project": x["project"], "commit_id": x["commit_id"],
        "changed_coverage_h0": "", "changed_coverage_h1": "", "delta_changed_coverage": "",
        "status": "NOT_MEASURED",
        "reason": "No uniform historical corpus plus instrumented build; ground truth uses the registered alternative VP1/VP3/VP4 static or compile evidence.",
    } for x in cases]
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    print(f"wrote {len(rows)} explicit NOT_MEASURED rows")


if __name__ == "__main__":
    main()
