#!/usr/bin/env python3
"""Freeze labels, anonymous inputs, prompts, and model configuration in order."""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
WORKSPACE = ROOT.parent
REPO = WORKSPACE / "FSE2026-harness-degradation" / "sources" / "projects" / "wuffs"
GT = ROOT / "ground-truth"
FROZEN_GT = ROOT / "frozen-ground-truth"
INPUTS = ROOT / "frozen-inputs"
PROMPTS = ROOT / "prompts"
DATA = ROOT / "data"
SEED = "task-4-n4-independent-order-v1"


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def git_show(revision: str, path: str) -> str:
    result = subprocess.run(["git", "-C", str(REPO), "show", f"{revision}:{path}"],
                            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return result.stdout


def lang(path: str) -> str:
    return "cpp" if Path(path).suffix in {".cc", ".cpp"} else "c"


def main() -> None:
    if FROZEN_GT.exists() or INPUTS.exists() or (ROOT / "frozen-experiment-config.json").exists():
        raise SystemExit("refusing to overwrite a frozen experiment")
    if any((ROOT / "predictions").glob("*.jsonl")):
        raise SystemExit("predictions already exist")
    csv.field_size_limit(sys.maxsize)
    audit_rows = []
    for filename in ("n4_audit.csv", "positive_audit.csv"):
        with (GT / filename).open(encoding="utf-8", newline="") as handle:
            audit_rows.extend(csv.DictReader(handle))
    if len(audit_rows) != 40 or any(r["audit_status"] != "VALID" for r in audit_rows):
        raise SystemExit("ground truth is not a fully valid 40-case audit")
    if any(r["audit_before_prediction"] != "true" for r in audit_rows):
        raise SystemExit("ground-truth ordering assertion failed")

    # Neutral IDs are assigned by a deterministic hash order fixed before any
    # prediction.  Neither Cxxx identifiers nor filenames encode the label.
    audit_rows.sort(key=lambda r: sha256(f"{SEED}|{r['commit']}".encode()))
    mapping = []
    labels = []
    for index, row in enumerate(audit_rows, 1):
        case_id = f"C{index:03d}"
        mapping.append({
            "case_id": case_id, "candidate_id": row["candidate_id"], "project": row["project"],
            "commit": row["commit"], "parent": row["parent"], "case_type": row["case_type"],
            "label": row["label"], "shuffle_seed": SEED,
        })
        labels.append({
            "case_id": case_id, "candidate_id": row["candidate_id"], "project": row["project"],
            "commit": row["commit"], "parent": row["parent"], "timestamp": row["timestamp"],
            "label": row["label"], "case_type": row["case_type"],
            "gap_exists_s0": row["gap_exists_s0"], "gap_exists_s1": row["gap_exists_s1"],
            "commit_induced": row["commit_induced"], "maintenance_needed": row["maintenance_needed"],
            "evidence_type": row["evidence_type"], "evidence_summary": row["evidence_summary"],
            "audit_status": row["audit_status"], "target_symbol": row["target_symbol"],
            "h0_path": row["h0_path"], "evidence_directory": row["evidence_directory"],
        })

    FROZEN_GT.mkdir(parents=True)
    label_path = FROZEN_GT / "labels.csv"
    with label_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(labels[0])); writer.writeheader(); writer.writerows(labels)
    with (DATA / "case_mapping.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(mapping[0])); writer.writeheader(); writer.writerows(mapping)
    dataset_basis = [{k: r[k] for k in ("case_id", "project", "commit", "parent", "target_symbol", "h0_path")}
                     for r in labels]
    dataset_hash = sha256(canonical(dataset_basis))
    gt_frozen_at = now()
    gt_manifest = {
        "frozen_at": gt_frozen_at, "case_count": 40, "valid_n4": 20, "valid_positive": 20,
        "dataset_hash": dataset_hash, "ground_truth_hash": sha256(label_path.read_bytes()),
        "labels_file_sha256": sha256(label_path.read_bytes()), "neutral_order_seed": SEED,
        "audit_manifest_sha256": sha256((GT / "audit_manifest.json").read_bytes()),
        "predictions_present_at_freeze": False, "relabel_after_freeze_allowed": False,
        "post_freeze_policy": "severe ground-truth errors may only be INVALIDATE; never relabel into main results",
    }
    write_json(FROZEN_GT / "manifest.json", gt_manifest)

    INPUTS.mkdir(parents=True)
    files = []
    by_candidate = {r["candidate_id"]: r for r in audit_rows}
    for item in mapping:
        case_id, candidate_id = item["case_id"], item["candidate_id"]
        row = by_candidate[candidate_id]
        evidence = ROOT / row["evidence_directory"]
        h0_path = row["h0_path"]
        h0_file = next(evidence.glob("H0.*"))
        h0 = h0_file.read_text(encoding="utf-8")
        source_diff = (evidence / "production_source.diff").read_text(encoding="utf-8")
        s0_context = (evidence / "target_context_s0.txt").read_text(encoding="utf-8")
        s1_context = (evidence / "target_context_s1.txt").read_text(encoding="utf-8")
        s0_context = s0_context.replace("TARGET ABSENT", "<no matching declaration in the selected S0 source file>")
        s1_context = s1_context.replace("TARGET ABSENT", "<no matching declaration in the selected S1 source file>")

        helper_sections = []
        for helper_name in sorted(set(re.findall(r'#include\s+"\.\./fuzzlib/([^"/]+)"', h0))):
            if helper_name == "fuzzlib.c":
                continue
            helper_path = f"fuzz/c/fuzzlib/{helper_name}"
            helper = git_show(row["parent"], helper_path)
            helper_sections.append(
                f"### Direct H0 helper: `{helper_path}`\n\n```c\n{helper.rstrip()}\n```\n"
            )
        helpers = "\n".join(helper_sections) if helper_sections else "No semantic helper beyond the generic runner is directly included.\n"
        text = f"""# Anonymous fuzz-harness case

## Case ID

{case_id}

## Existing harness H0

The complete project-owned harness translation unit is shown below. Framework
main/CLI scaffolding is not expanded; directly included semantic helper files
are shown separately under the fixed context rule.

Path: `{h0_path}`

```{lang(h0_path)}
{h0.rstrip()}
```

{helpers}
## Complete S0 -> S1 hand-written production-source diff

The fixed rule includes every changed `std/**/*.wuffs` production file. It
excludes generated release snapshots, tests, docs, examples, and commit text.

```diff
{source_diff.rstrip()}
```

## Uniform selected declaration context

This same mechanically selected S0/S1 context is supplied for every case.

### S0

```text
{s0_context.rstrip()}
```

### S1

```text
{s1_context.rstrip()}
```
"""
        path = INPUTS / f"{case_id}.md"
        path.write_text(text, encoding="utf-8")
        files.append({"case_id": case_id, "sha256": sha256(path.read_bytes()), "bytes": path.stat().st_size})
    input_hash = sha256(canonical(files))
    input_frozen_at = now()
    input_manifest = {
        "frozen_at": input_frozen_at, "case_count": 40, "dataset_hash": dataset_hash,
        "input_hash": input_hash, "files": files,
        "context_selection_version": "all-changed-wuffs+complete-H0+direct-semantic-helpers+target-context-v1",
        "context_rule": {
            "included": ["complete H0 translation unit", "direct semantic fuzzlib helper", "all changed hand-written Wuffs production diffs", "mechanically selected declaration context in S0 and S1"],
            "excluded": ["H1", "harness diff", "labels", "ground-truth evidence", "coverage/reachability results", "future actions", "commit ID/time/message", "generated snapshots", "tests/docs/examples"],
        },
        "labels_read_by_prediction_runner": False,
    }
    write_json(INPUTS / "manifest.json", input_manifest)

    prompt_files = sorted(PROMPTS.glob("*"))
    prompt_hashes = {str(p.relative_to(ROOT)): sha256(p.read_bytes()) for p in prompt_files if p.is_file()}
    prompt_hash = sha256(canonical(prompt_hashes))
    codex_version = subprocess.run([shutil.which("codex") or "codex", "--version"], text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout.strip()
    config_frozen_at = now()
    config = {
        "config_frozen_at": config_frozen_at, "model": "gpt-5.6-sol",
        "model_version": "service alias; exact backend revision not exposed by CLI",
        "reasoning_effort": "high", "temperature": None, "max_tokens": None,
        "one_shot": True, "retries": 0, "concurrency": 4, "timeout_seconds": 900,
        "system_prompt": "Codex built-in system prompt; isolated with --ignore-user-config --ignore-rules",
        "protocol": "one fresh ephemeral process per case and method; read-only unique empty working directory; runner reads only fixed prompt/schema plus one frozen input",
        "context_selection_version": input_manifest["context_selection_version"],
        "dataset_hash": dataset_hash, "input_hash": input_hash, "prompt_hash": prompt_hash,
        "prompt_files": prompt_hashes, "codex_cli_version_at_freeze": codex_version,
        "prompt_provenance": "byte-identical reuse of the already frozen task-3 prompts and schemas; no task-4 outcome tuning",
        "unset_parameter_note": "Codex CLI does not expose temperature or max output tokens; service defaults are frozen by leaving both unset.",
        "ordering": {
            "ground_truth_frozen_at": gt_frozen_at, "input_frozen_at": input_frozen_at,
            "prompt_and_model_config_frozen_at": config_frozen_at, "prediction_started_at": None,
        },
    }
    write_json(ROOT / "frozen-experiment-config.json", config)
    print(json.dumps({
        "ground_truth_frozen_at": gt_frozen_at, "input_frozen_at": input_frozen_at,
        "config_frozen_at": config_frozen_at, "dataset_hash": dataset_hash,
        "ground_truth_hash": gt_manifest["ground_truth_hash"], "input_hash": input_hash,
        "prompt_hash": prompt_hash, "cases": 40,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
