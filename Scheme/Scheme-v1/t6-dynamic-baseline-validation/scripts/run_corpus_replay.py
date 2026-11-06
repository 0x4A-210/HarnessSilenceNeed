#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from run_fuzz_budget import run_budget


def run_corpus_replay(case: dict[str, str], version: str, out_dir: Path,
                      base_corpus: Path, run_root: Path) -> dict:
    return run_budget(case, version, out_dir, base_corpus, run_root,
                      budget_name="corpus", budget_seconds=0, repeat=1)


if __name__ == "__main__":
    raise SystemExit("This module is called by run_phase_a.py.")
