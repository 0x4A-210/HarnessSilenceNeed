#!/usr/bin/env python3
"""Create anonymous Task-8 inputs without opening labels or H1 content.

The target-guided +/-24-line supplement used by Task 5 is intentionally not
used here because its selector came from audited target metadata, which Task 8
explicitly forbids.  The unchanged core rule is retained: complete selected
H0 plus the complete production diff in git function-context mode.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from common import ROOT, git, read_csv, sha256_file, utc_now, write_json


OUT = ROOT / "frozen-inputs"
SOURCE_PROMPTS = ROOT.parent / "t5-delta-aware-validation" / "prompts"
PROMPT_NAMES = [
    "gap_only.md", "gap_only_schema.json",
    "direct_evolution_aware.md", "direct_evolution_aware_schema.json",
    "delta_aware.md", "delta_aware_schema.json",
]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def render(case: dict[str, str]) -> tuple[str, dict[str, object]]:
    project, parent, commit = case["project"], case["parent"], case["commit"]
    h0_paths = [path for path in case["h0_paths"].split(";") if path]
    production_paths = [path for path in case["production_paths"].split(";") if path]
    harness_sections = []
    for path in h0_paths:
        source = git(project, "show", f"{parent}:{path}").stdout.rstrip()
        harness_sections.append(f"### H0 path: `{path}`\n\n~~~~cpp\n{source}\n~~~~")
    diff = git(
        project, "diff", "--no-ext-diff", "--no-color", "--no-renames",
        "--function-context", parent, commit, "--", *production_paths,
    ).stdout.rstrip()
    if not diff:
        raise RuntimeError(f"{case['case_id']} has an empty production diff")
    content = (
        "# Anonymous fuzz-harness case\n\n"
        "## Case ID\n\n"
        f"{case['case_id']}\n\n"
        "## Existing harness H0\n\n"
        "The complete project-owned C/C++ source for the case's mechanically selected pre-change harness is shown below.\n\n"
        + "\n\n".join(harness_sections)
        + "\n\n## Complete S0 -> S1 production-source diff\n\n"
        "All changed production C/C++ paths and all hunks are included. Git function-context mode expands each changed function body. "
        "Harness, test, example, documentation, build, generated, and vendored paths are excluded by the frozen production-path rule.\n\n"
        f"~~~~diff\n{diff}\n~~~~\n\n"
        "## Uniform context-selection note\n\n"
        "Changed function bodies and changed public declarations are supplied by the complete function-context diff above. "
        "The optional one-hop/type/macro supplement is empty for every case; no target- or label-guided context is added.\n"
    )
    # Exact commit identity, subject, and future/developer-harness material are
    # metadata-only checks; none is rendered.
    forbidden = {
        "commit_id": commit in content,
        "parent_id": parent in content,
        "subject": bool(case["subject"] and case["subject"] in content),
        "developer_harness_diff_marker": "DEVELOPER HARNESS DIFF" in content,
        "h1_marker": "S1 + H1" in content or "S1_H1" in content,
    }
    if any(forbidden.values()):
        raise RuntimeError(f"blind-input leakage for {case['case_id']}: {forbidden}")
    return content, {
        "case_id": case["case_id"], "h0_file_count": len(h0_paths),
        "production_path_count": len(production_paths),
        "production_diff_bytes": len(diff.encode()), "forbidden_literal_hits": forbidden,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    gt_manifest_path = ROOT / "frozen-ground-truth" / "audit_manifest.json"
    gt = json.loads(gt_manifest_path.read_text(encoding="utf-8"))
    if gt["status"] != "FROZEN_BEFORE_ANY_PREDICTION" or gt["case_count"] != 104:
        raise SystemExit("ground truth must be frozen first")
    cases = read_csv(ROOT / "frozen-ground-truth" / "cases.csv")
    if len(cases) != 104:
        raise SystemExit("expected 104 cases")
    rendered = []
    for case in cases:
        content, meta = render(case)
        data = content.encode()
        rendered.append((case["case_id"], data, {**meta, "bytes": len(data), "sha256": digest(data)}))
    sizes = [len(data) for _case_id, data, _meta in rendered]
    summary = {
        "case_count": len(rendered), "min_bytes": min(sizes), "max_bytes": max(sizes),
        "median_bytes": sorted(sizes)[len(sizes) // 2], "total_bytes": sum(sizes),
        "largest_cases": [
            {"case_id": case_id, "bytes": len(data)}
            for case_id, data, _meta in sorted(rendered, key=lambda item: len(item[1]), reverse=True)[:10]
        ],
    }
    if args.preflight:
        print(json.dumps({"status": "PREFLIGHT_ONLY", **summary}, indent=2, sort_keys=True))
        return
    if OUT.exists() or (ROOT / "prompts").exists():
        raise SystemExit("refusing to overwrite frozen inputs/prompts")

    OUT.mkdir(parents=True)
    prompt_dir = ROOT / "prompts"
    prompt_dir.mkdir()
    for name in PROMPT_NAMES:
        shutil.copy2(SOURCE_PROMPTS / name, prompt_dir / name)
    case_meta = []
    for case_id, data, meta in rendered:
        path = OUT / f"{case_id}.md"
        path.write_bytes(data)
        case_meta.append({
            **meta, "input_path": str(path.relative_to(ROOT)),
        })
    payload = "".join(f"{row['case_id']}:{row['sha256']}\n" for row in case_meta).encode()
    frozen_at = utc_now()
    manifest = {
        "status": "FROZEN", "frozen_at": frozen_at, "case_count": 104,
        "dataset_hash": gt["dataset_hash"], "ground_truth_hash": gt["ground_truth_hash"],
        "ground_truth_frozen_at": gt["frozen_at"], "input_hash": digest(payload),
        "context_selection_version": "task5-core-complete-H0+complete-production-function-context-diff;no-GT-supplement-v2",
        "context_rule": {
            "H0": "all selected pre-change harness C/C++ paths recorded before label freeze; complete file content",
            "production_diff": "all mined production C/C++ paths; git --function-context; no hunk truncation",
            "supplement": "uniformly empty; target-guided Task-5 radius-24 supplement removed to satisfy Task-8 no-GT-input rule",
            "one_hop_callers_callees": "not selected for any case",
        },
        "protocol_deviation": {
            "from_task5_context_rule": True,
            "reason": "Task-5's literal identity selector consumed audited target_symbol; reusing it would violate Task-8 Section 13.",
            "timing": "decided and frozen before all Task-8 predictions",
        },
        "prohibited_material_injected": [],
        "leakage_audit": {
            "commit_ids": 0, "parent_ids": 0, "subjects": 0,
            "developer_harness_diff_markers": 0, "h1_markers": 0,
        },
        "case_inputs": case_meta, "size_summary": summary,
        "prompt_source": "byte-identical Task-5 frozen prompt/schema files",
        "prompt_file_sha256": {
            f"prompts/{name}": sha256_file(prompt_dir / name) for name in PROMPT_NAMES
        },
        "ordering": {
            "ground_truth_frozen_at": gt["frozen_at"], "input_frozen_at": frozen_at,
            "prediction_started_at": None,
        },
    }
    write_json(OUT / "manifest.json", manifest)
    print(json.dumps({"status": "FROZEN", "input_hash": manifest["input_hash"], **summary}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
