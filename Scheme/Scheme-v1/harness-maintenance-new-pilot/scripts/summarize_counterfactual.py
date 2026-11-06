#!/usr/bin/env python3
"""Aggregate translation-unit probes into per-case three-way evidence."""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


HERE = Path(__file__).resolve()
OUT = HERE.parents[1]


def main() -> None:
    build = list(csv.DictReader((OUT / "results" / "build_results_three_way.csv").open(encoding="utf-8", newline="")))
    audit = {x["case_id"]: x for x in csv.DictReader((OUT / "data" / "ground_truth_audit.csv").open(encoding="utf-8", newline=""))}
    positive = {x["case_id"]: x for x in csv.DictReader((OUT / "data" / "verified_positive_cases.csv").open(encoding="utf-8", newline=""))}
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in build:
        grouped[(row["case_id"], row["side"])].append(row)
    rows = []
    for case_id in sorted({x["case_id"] for x in build}):
        def state(side: str) -> str:
            values = grouped[(case_id, side)]
            if not values:
                return "NOT_RUN"
            return "PASS" if all(x["compile_success"] == "true" for x in values) else "FAIL"
        s0h0, s1h0, s1h1 = state("S0_H0"), state("S1_H0"), state("S1_H1")
        compile_delta = s0h0 == "PASS" and s1h0 == "FAIL" and s1h1 == "PASS"
        spec = positive.get(case_id, {})
        rows.append({
            "case_id": case_id, "audited_label": audit[case_id]["audited_label"],
            "vp_criterion": spec.get("vp_criterion", ""),
            "s0_h0_compile": s0h0, "s1_h0_compile": s1h0,
            "s1_h1_compile": s1h1, "compile_delta_evidence": str(compile_delta).lower(),
            "non_compile_evidence": spec.get("counterfactual_evidence", ""),
            "audit_status": audit[case_id]["audit_status"],
            "audit_reason": audit[case_id]["audit_reason"],
        })
    target = OUT / "results" / "counterfactual_summary.csv"
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    verified_compile = sum(x["audited_label"] == "positive" and x["compile_delta_evidence"] == "true" for x in rows)
    print(f"rows={len(rows)} verified_positive_compile_deltas={verified_compile}")


if __name__ == "__main__":
    main()
