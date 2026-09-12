#!/usr/bin/env python3
"""Run one frozen LLM method once per independent anonymous Task-8 case."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from common import ROOT, utc_now, write_json


EXPECTED_CASES = 104
METHODS = {"gap_only", "direct_evolution_aware", "delta_aware"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in METHODS:
        raise SystemExit("usage: run_blind.py {gap_only|direct_evolution_aware|delta_aware}")
    method = sys.argv[1]
    config_path = ROOT / "frozen-experiment-config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config["status"] != "FROZEN_BEFORE_PREDICTION":
        raise SystemExit("experiment config is not frozen")
    method_config = config["llm_methods"][method]
    prompt = ROOT / method_config["prompt"]
    schema = ROOT / method_config["schema"]
    inputs = ROOT / "frozen-inputs"
    input_manifest = json.loads((inputs / "manifest.json").read_text(encoding="utf-8"))
    for path in (prompt, schema, ROOT / "scripts" / "run_blind.py"):
        key = str(path.relative_to(ROOT))
        if digest(path.read_bytes()) != config["frozen_file_sha256"][key]:
            raise SystemExit(f"frozen file hash mismatch: {key}")
    if input_manifest["input_hash"] != config["input_hash"]:
        raise SystemExit("frozen input hash mismatch")
    case_paths = sorted(inputs.glob("T8[0-9][0-9][0-9].md"))
    if len(case_paths) != EXPECTED_CASES:
        raise SystemExit(f"expected {EXPECTED_CASES} cases, found {len(case_paths)}")

    predictions = ROOT / "predictions"
    raw = predictions / f"raw_{method}"
    output_jsonl = predictions / f"{method}.jsonl"
    pairs_jsonl = predictions / f"{method}_input_output_pairs.jsonl"
    manifest_path = predictions / f"run_manifest_{method}.json"
    if any(path.exists() for path in (raw, output_jsonl, pairs_jsonl, manifest_path)):
        raise SystemExit(f"refusing to rerun one-shot method {method}")
    fixed = prompt.read_text(encoding="utf-8").rstrip()
    expected_hashes = {row["case_id"]: row["sha256"] for row in input_manifest["case_inputs"]}
    items = []
    for path in case_paths:
        case_id = path.stem
        data = path.read_bytes()
        if digest(data) != expected_hashes[case_id]:
            raise SystemExit(f"frozen input mismatch: {case_id}")
        case = data.decode("utf-8")
        model_input = fixed + "\n\n--- BEGIN ANONYMOUS CASE ---\n\n" + case + "\n--- END ANONYMOUS CASE ---\n"
        items.append({"case_id": case_id, "input": model_input,
                      "input_sha256": digest(model_input.encode())})
    codex = shutil.which("codex")
    if not codex:
        raise SystemExit("codex executable not found")
    predictions.mkdir(exist_ok=True); raw.mkdir()
    manifest = {
        "status": "RUNNING", "method": method, "started_at": utc_now(), "finished_at": None,
        "ground_truth_files_read": False, "h1_or_harness_diff_read": False,
        "other_case_outputs_read": False, "dataset_hash": config["dataset_hash"],
        "ground_truth_hash_reference_only": config["ground_truth_hash"],
        "input_hash": config["input_hash"], "config_sha256": digest(config_path.read_bytes()),
        "model": config["model"], "reasoning_effort": config["reasoning_effort"],
        "temperature": config["temperature"], "max_tokens": config["max_tokens"],
        "retries": 0, "concurrency": config["concurrency"], "timeout_seconds": config["timeout_seconds"],
        "prompt_sha256": digest(prompt.read_bytes()), "schema_sha256": digest(schema.read_bytes()),
        "protocol": config["llm_protocol"],
        "cases": [{"case_id": row["case_id"], "input_sha256": row["input_sha256"]} for row in items],
        "attempts": [],
    }
    write_json(manifest_path, manifest)

    def invoke(item: dict[str, str]) -> dict[str, object]:
        case_id = item["case_id"]
        output = raw / f"{case_id}.json"
        workdir = Path(tempfile.mkdtemp(prefix=f"t8-{method}-{case_id}-"))
        command = [
            codex, "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
            "--skip-git-repo-check", "--color", "never", "--sandbox", "read-only",
            "--model", config["model"],
            "--config", f"model_reasoning_effort=\"{config['reasoning_effort']}\"",
            "--output-schema", str(schema.resolve()), "--output-last-message", str(output.resolve()),
            "--cd", str(workdir), "-",
        ]
        started_at, start = utc_now(), time.monotonic()
        stdout = stderr = error = ""
        try:
            completed = subprocess.run(
                command, input=item["input"], text=True, encoding="utf-8", errors="replace",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=config["timeout_seconds"],
                env=os.environ.copy(),
            )
            exit_code, stdout, stderr = completed.returncode, completed.stdout, completed.stderr
        except subprocess.TimeoutExpired as exc:
            exit_code = 124
            stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
            error = f"timeout after {config['timeout_seconds']}s"
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        (raw / f"{case_id}.stdout.log").write_text(stdout, encoding="utf-8", errors="replace")
        (raw / f"{case_id}.stderr.log").write_text(stderr, encoding="utf-8", errors="replace")
        parsed = None
        if exit_code == 0 and output.exists():
            try:
                parsed = json.loads(output.read_text(encoding="utf-8"))
                if parsed.get("case_id") != case_id:
                    error, parsed = f"case_id mismatch: {parsed.get('case_id')}", None
            except (json.JSONDecodeError, OSError) as exc:
                error = f"invalid JSON: {exc}"
        elif not error:
            error = f"codex exit code {exit_code}"
        return {
            "case_id": case_id, "input_sha256": item["input_sha256"], "input": item["input"],
            "started_at": started_at, "finished_at": utc_now(),
            "duration_seconds": round(time.monotonic() - start, 3), "exit_code": exit_code,
            "valid_prediction": parsed is not None, "error": error, "prediction": parsed,
        }

    attempts = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=config["concurrency"]) as pool:
        futures = [pool.submit(invoke, item) for item in items]
        for future in concurrent.futures.as_completed(futures):
            result = future.result(); attempts.append(result)
            manifest["attempts"] = [
                {k: v for k, v in row.items() if k not in {"input", "prediction"}}
                for row in sorted(attempts, key=lambda value: value["case_id"])
            ]
            write_json(manifest_path, manifest)
            print(f"{len(attempts):03d}/{EXPECTED_CASES} {result['case_id']} valid={result['valid_prediction']} seconds={result['duration_seconds']}", flush=True)
    attempts.sort(key=lambda value: value["case_id"])
    with output_jsonl.open("w", encoding="utf-8", newline="\n") as handle:
        for attempt in attempts:
            if attempt["prediction"] is not None:
                handle.write(json.dumps(attempt["prediction"], ensure_ascii=False, separators=(",", ":")) + "\n")
    with pairs_jsonl.open("w", encoding="utf-8", newline="\n") as handle:
        for attempt in attempts:
            handle.write(json.dumps({
                "case_id": attempt["case_id"], "input_sha256": attempt["input_sha256"],
                "model_input": attempt["input"], "model_output": attempt["prediction"],
                "exit_code": attempt["exit_code"], "error": attempt["error"],
            }, ensure_ascii=False, separators=(",", ":")) + "\n")
    failures = [row for row in attempts if not row["valid_prediction"]]
    manifest.update({
        "status": "COMPLETE" if not failures else "COMPLETE_WITH_FAILURES", "finished_at": utc_now(),
        "attempt_count": len(attempts), "valid_predictions": len(attempts) - len(failures),
        "failed_predictions": len(failures), "retries_per_case": 0,
        "attempts": [{k: v for k, v in row.items() if k not in {"input", "prediction"}} for row in attempts],
        "prediction_sha256": digest(output_jsonl.read_bytes()),
        "input_output_pairs_sha256": digest(pairs_jsonl.read_bytes()),
    })
    write_json(manifest_path, manifest)
    print(json.dumps({"method": method, "status": manifest["status"],
                      "valid": manifest["valid_predictions"], "failed": manifest["failed_predictions"]}, sort_keys=True))


if __name__ == "__main__":
    main()
