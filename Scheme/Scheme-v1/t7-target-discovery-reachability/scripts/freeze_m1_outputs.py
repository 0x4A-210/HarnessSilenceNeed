#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from common import ROOT, read_csv, sha256_file, utc_now, write_json


def main() -> None:
    expected = [row["case_id"] for row in read_csv(ROOT / "dataset" / "cases.csv")]
    files = [ROOT / "target-discovery" / f"{case_id}.json" for case_id in expected]
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        raise SystemExit(f"missing M1 outputs: {missing}")
    hashes = {path.name: sha256_file(path) for path in files}
    aggregate = hashlib.sha256("".join(f"{name}:{digest}\n" for name, digest in sorted(hashes.items()))
                               .encode("utf-8")).hexdigest()
    config = json.loads((ROOT / "frozen-experiment-config.json").read_text(encoding="utf-8"))
    run = json.loads((ROOT / "results" / "m1_run_manifest.json").read_text(encoding="utf-8"))
    write_json(ROOT / "target-discovery" / "prediction_freeze_manifest.json", {
        "schema_version": "t7-m1-output-freeze-v1",
        "frozen_at": utc_now(),
        "rule_frozen_at": config["frozen_at"],
        "case_count": len(files),
        "successful_independent_processes": run["success_count"],
        "ground_truth_opened_by_m1": False,
        "per_file_sha256": hashes,
        "aggregate_sha256": aggregate,
        "immutable_for_evaluation": True,
    })


if __name__ == "__main__":
    main()
