#!/usr/bin/env python3
from pathlib import Path
from run_common import run_method

if __name__ == "__main__":
    run_method(Path(__file__).resolve().parents[1], "gap_only")
