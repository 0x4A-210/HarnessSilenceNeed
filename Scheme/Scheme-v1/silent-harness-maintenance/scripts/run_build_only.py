#!/usr/bin/env python3
"""Apply the frozen deterministic build-only rule without reading labels."""

import csv
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "ground-truth" / "build_runtime_validation.csv"
target = ROOT / "predictions" / "build_only.csv"
if target.exists():
    raise SystemExit("Refusing to overwrite frozen build-only predictions")
target.parent.mkdir(parents=True, exist_ok=True)
with source.open(encoding="utf-8", newline="") as handle:
    rows = list(csv.DictReader(handle))
output = []
for row in rows:
    needed = row["s1_h0_build"] != "PASS" or row["s1_h0_runtime"] != "PASS"
    output.append({
        "case_id": row["case_id"], "maintenance_needed": "YES" if needed else "NO",
        "s1_h0_build": row["s1_h0_build"], "s1_h0_runtime": row["s1_h0_runtime"],
        "rule": "YES iff build or runtime is not PASS",
        "predicted_at": datetime.now(timezone.utc).isoformat(),
    })
with target.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(output[0]))
    writer.writeheader(); writer.writerows(output)
print(f"wrote {len(output)} one-shot deterministic predictions")
