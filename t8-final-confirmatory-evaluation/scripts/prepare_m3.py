#!/usr/bin/env python3
"""Prepare the label-free input table and repository view for frozen Task-7 M3."""
from __future__ import annotations

import os
from pathlib import Path

from common import ROOT, REPOS, read_csv, write_csv


M3 = ROOT / "deterministic-baseline"


def main() -> None:
    dataset = M3 / "dataset" / "cases.csv"
    repos = M3 / "project-repos"
    if dataset.exists():
        raise SystemExit("refusing to overwrite M3 dataset")
    cases = read_csv(ROOT / "frozen-ground-truth" / "cases.csv")
    rows = [{
        "case_id": row["case_id"], "project": row["project"],
        "s0_commit": row["parent"], "s1_commit": row["commit"],
        "commit_time": row["commit_time"], "h0_harness_paths": row["h0_paths"],
        "phase": "TASK8_FINAL_CONFIRMATORY",
    } for row in cases]
    write_csv(dataset, rows, list(rows[0]))
    repos.mkdir(parents=True)
    for project, target in REPOS.items():
        link = repos / project
        if link.exists() or link.is_symlink():
            raise SystemExit(f"refusing to replace repository link: {link}")
        link.symlink_to(target.resolve(), target_is_directory=True)
    print(f"prepared {len(rows)} label-free M3 cases and {len(REPOS)} repository links")


if __name__ == "__main__":
    main()
