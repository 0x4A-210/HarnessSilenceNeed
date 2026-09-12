#!/usr/bin/env python3
"""Materialize and analyze the 36 valid task-4 cases as development-only data."""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
SOURCE = WORKSPACE / "n4-validation"
DEV = ROOT / "development-set"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


N4_FAILURE = {
    "N4006": ("E1_IMPACT_SCOPE", "The direct method narrowed scope to the ordinary JPEG decode path and rejected the already-uncovered restart API gap."),
    "N4018": ("E1_IMPACT_SCOPE", "It focused on WebP's integrated VP8 path and omitted the pre-existing direct VP8 API/configuration surface."),
    "N4007": ("E2_GAP_BEFORE", "It saw the post-commit restart/state gap but treated newly stored state as proof that the API exposure gap did not predate the commit."),
    "N4019": ("E1_IMPACT_SCOPE", "It treated integrated WebP reachability as exhaustive and did not retain the existing direct VP8 API gap as the comparison scope."),
    "N4010": ("E4_DELTA", "It acknowledged CRC64 was absent from H0 on both sides but called an internal slicing implementation an aggravation without a new harness obligation."),
    "N4001": ("CORRECT", "It identified the old restart protocol gap and correctly attributed the state-value rewrite as unchanged exposure."),
    "N4005": ("E4_DELTA", "It converted internal scan/swizzle suspension restructuring into AGGRAVATED although the harness obligation itself did not change."),
    "N4014": ("E4_DELTA", "It treated an internal CPU-selected CRC64 fast path as aggravating an unchanged absent-module gap."),
    "N4016": ("E1_IMPACT_SCOPE", "It rejected the selected historical work-buffer/configuration gap instead of comparing that same scope in S0 and S1."),
    "N4015": ("E1_IMPACT_SCOPE", "It focused only on ordinary JPEG reachability and discarded the old restart-state exposure gap."),
    "N4011": ("E2_GAP_BEFORE", "It recognized the changed get_quirk path after the commit but failed to preserve the already-uncovered getter API as GapBefore."),
    "N4008": ("E4_DELTA", "It acknowledged the module was absent in S0 and S1 but equated more internal SIMD code with a new harness requirement."),
    "N4009": ("CORRECT", "It explicitly found the XXHash gap on both sides and correctly classified the rollback as not commit-induced."),
    "N4004": ("E2_GAP_BEFORE", "It saw new state inside restart_frame but did not anchor the comparison on the restart API already omitted by H0."),
    "N4002": ("E1_IMPACT_SCOPE", "It called the changed ordinary decode wrapper covered and omitted the historical tell_me_more/metadata gap from the same-scope comparison."),
    "N4020": ("E1_IMPACT_SCOPE", "It focused on WebP's integrated ALPH path and omitted the existing direct VP8 configuration/API gap."),
}


def main() -> None:
    labels = list(csv.DictReader((SOURCE / "frozen-ground-truth" / "labels.csv").open(encoding="utf-8", newline="")))
    invalid = {r["case_id"] for r in csv.DictReader(
        (SOURCE / "frozen-ground-truth" / "invalidations.csv").open(encoding="utf-8", newline=""))}
    evo = {r["case_id"]: r for r in
           (json.loads(line) for line in (SOURCE / "predictions" / "evolution_aware.jsonl").read_text().splitlines() if line)}
    valid = [r for r in labels if r["case_id"] not in invalid]
    if len(valid) != 36:
        raise SystemExit(f"expected 36 valid task-4 cases, got {len(valid)}")
    for path in (DEV / "n4", DEV / "positives", DEV / "analysis"):
        path.mkdir(parents=True, exist_ok=True)

    manifest_rows = []
    for label in sorted(valid, key=lambda r: r["candidate_id"]):
        candidate, old_case = label["candidate_id"], label["case_id"]
        group = "n4" if label["case_type"] == "N4_EXISTING_GAP" else "positives"
        src = SOURCE / "frozen-inputs" / f"{old_case}.md"
        dst = DEV / group / f"{candidate}.md"
        shutil.copyfile(src, dst)
        prediction = evo[old_case]
        if group == "n4":
            failure_type, diagnosis = N4_FAILURE[candidate]
            recognized_gap = "YES" if prediction["gap_exists"] else "NO"
            attribution_ok = "YES" if prediction["commit_induced"] == "NO" else "NO"
            direct_correct = prediction["maintenance_needed"] is False
            before_diagnosis = (
                "The direct schema had no explicit GapBefore field; its reason preserves the historical gap."
                if failure_type == "CORRECT" else
                "Not independently observable in the old schema; the reason did not establish the required same-scope S0 gap."
            )
            explicit_help = (
                "Already correct; explicit fields would make the evidence auditable."
                if failure_type == "CORRECT" else
                "Yes in principle: fixing one impact scope, requiring separate S0/H0 and S1/H0 evidence, and forbidding internal code growth alone as AGGRAVATED directly targets this failure."
            )
            text = f"""# Development analysis — {candidate}

- Prior neutral ID: `{old_case}`
- Commit: `{label['commit']}`
- Target: `{label['target_symbol']}`
- Frozen development expectation: GapBefore=YES, GapAfter=YES, Delta=UNCHANGED, Maintenance=NO.

## 1. Previous Direct Evolution-Aware prediction

```json
{json.dumps(prediction, indent=2, ensure_ascii=False)}
```

## 2. Did it identify the real gap?

**{recognized_gap}.** The old `gap_exists` field only represented S1+H0; it did not expose a separate S0 judgment.

## 3. Was commit attribution correct?

**{attribution_ok}.** Final maintenance classification was {'correct' if direct_correct else 'a false positive'}.

## 4. Failure stage

Primary classification: **{failure_type}**. {diagnosis}

- GapBefore: {before_diagnosis}
- GapAfter: {'recognized' if prediction['gap_exists'] else 'missed/rejected for the selected historical scope'}.
- Impact scope: {'adequate' if failure_type in {'CORRECT', 'E2_GAP_BEFORE', 'E4_DELTA'} else 'incorrectly narrowed or switched'}.
- Delta attribution: {'correct UNCHANGED' if failure_type == 'CORRECT' else ('incorrect NEW/AGGRAVATED inference' if prediction['commit_induced'] == 'YES' else 'not reached because the gap was rejected')}.

## 5. Unrelated API/subsystem association

{'No; the main error was temporal attribution within the selected scope.' if failure_type in {'CORRECT', 'E2_GAP_BEFORE', 'E4_DELTA'} else 'Yes or effectively so: the method switched from the selected historical gap to the ordinary/integrated changed path and therefore compared different scopes.'}

## 6. Would explicit Before/After help?

{explicit_help}
"""
        else:
            config = label["target_symbol"].split(":", 1)[1].startswith("QUIRK_")
            target = label["target_symbol"]
            if config:
                impact = "configuration_change"
                context = "public config declaration; set/get quirk caller and callee; state field and gated branch"
            elif any(x in target for x in ("xxhash", "sha256", "crc64")):
                impact = "new_entry_point / stateful hasher API"
                context = "public API declaration; hasher state type; update/finalization callees"
            else:
                impact = "new_entry_point / decoder or major format surface"
                context = "new entry declaration; decoder state type; one-hop caller/callee and module configuration"
            text = f"""# Development attribution analysis — {candidate}

- Prior neutral ID: `{old_case}`
- Commit: `{label['commit']}`
- Target: `{target}`
- Frozen development expectation: GapBefore=NO, GapAfter=YES, Delta=NEW, Maintenance=YES.

## 1. Is the impact scope clear?

**YES.** Primary scope: `{impact}`. The selected production declaration is absent in S0 and introduced in S1.

## 2. S0+H0

The target declaration/configuration does not exist in S0, so this target gap is absent rather than historical.

## 3. S1+H0

The target exists in S1 while the unchanged H0 has no direct exposure/configuration path for it. A new gap exists.

## 4. Correct attribution

**NEW.** The previous Direct Evolution-Aware prediction was
`gap_exists={str(prediction['gap_exists']).lower()}`,
`commit_induced={prediction['commit_induced']}`,
`maintenance_needed={str(prediction['maintenance_needed']).lower()}` and was correct.

## 5. Fixed context needed

{context}. This requirement is assigned by case type, not by model outcome.
"""
        analysis_path = DEV / "analysis" / f"{candidate}.md"
        analysis_path.write_text(text, encoding="utf-8")
        manifest_rows.append({
            "development_id": candidate, "prior_case_id": old_case, "project": label["project"],
            "commit": label["commit"], "case_type": label["case_type"],
            "expected_gap_before": "YES" if group == "n4" else "NO",
            "expected_gap_after": "YES", "expected_delta": "UNCHANGED" if group == "n4" else "NEW",
            "maintenance_needed": "NO" if group == "n4" else "YES",
            "input_path": str(dst.relative_to(ROOT)), "input_sha256": sha256(dst.read_bytes()),
            "analysis_path": str(analysis_path.relative_to(ROOT)),
        })
    with (DEV / "cases.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_rows[0])); writer.writeheader(); writer.writerows(manifest_rows)
    manifest = {
        "created_at": dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z"),
        "designation": "DELTA_AWARE_DEVELOPMENT_SET", "case_count": 36,
        "n4_count": 16, "positive_count": 20, "excluded_task4_invalidations": sorted(invalid),
        "source_ground_truth_hash": json.loads((SOURCE / "frozen-ground-truth" / "manifest.json").read_text())["ground_truth_hash"],
        "development_dataset_hash": sha256(json.dumps(manifest_rows, sort_keys=True, separators=(",", ":")).encode()),
        "allowed_uses": ["error analysis", "prompt development", "schema development", "context-rule development", "taxonomy refinement"],
        "prohibited_use": "final unbiased blind test",
    }
    (DEV / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
