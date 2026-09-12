#!/usr/bin/env python3
"""Run one of the three frozen Task-5 methods exactly once per blind case."""

from __future__ import annotations

import concurrent.futures
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CASES = 40


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in {"gap_only", "direct_evolution_aware", "delta_aware"}:
        raise SystemExit("usage: run_blind.py {gap_only|direct_evolution_aware|delta_aware}")
    method = sys.argv[1]
    config_path = ROOT / "frozen-experiment-config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    method_config = config["methods"][method]
    prompt = ROOT / method_config["prompt"]
    schema = ROOT / method_config["schema"]
    inputs_dir = ROOT / "frozen-inputs"
    input_manifest = json.loads((inputs_dir / "manifest.json").read_text(encoding="utf-8"))
    for path in (prompt, schema):
        key = str(path.relative_to(ROOT))
        if digest(path.read_bytes()) != config["file_sha256"][key]:
            raise SystemExit(f"frozen file hash mismatch: {key}")
    if input_manifest["input_hash"] != config["input_hash"]:
        raise SystemExit("frozen input hash mismatch")
    case_paths = sorted(inputs_dir.glob("T[0-9][0-9][0-9][0-9].md"))
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
    items = []
    expected_hashes = {row["case_id"]: row["sha256"] for row in input_manifest["case_inputs"]}
    for path in case_paths:
        case_id = path.stem
        case = path.read_text(encoding="utf-8")
        if f"\n{case_id}\n" not in case or digest(path.read_bytes()) != expected_hashes[case_id]:
            raise SystemExit(f"frozen case mismatch: {case_id}")
        model_input = fixed + "\n\n--- BEGIN ANONYMOUS CASE ---\n\n" + case + "\n--- END ANONYMOUS CASE ---\n"
        items.append({"case_id": case_id, "input": model_input, "input_sha256": digest(model_input.encode())})
    codex = shutil.which("codex")
    if not codex:
        raise SystemExit("codex executable not found")
    predictions.mkdir(exist_ok=True); raw.mkdir()
    started_at = now()
    manifest = {
        "status": "running", "method": method, "started_at": started_at, "finished_at": None,
        "ground_truth_files_read": False, "dataset_hash": config["dataset_hash"],
        "input_hash": config["input_hash"], "config_sha256": digest(config_path.read_bytes()),
        "model": config["model"], "reasoning_effort": config["reasoning_effort"],
        "temperature": config["temperature"], "max_tokens": config["max_tokens"],
        "retries": config["retries"], "concurrency": config["concurrency"],
        "timeout_seconds": config["timeout_seconds"],
        "prompt_sha256": digest(prompt.read_bytes()), "schema_sha256": digest(schema.read_bytes()),
        "protocol": config["protocol"],
        "command_template": [
            "codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
            "--skip-git-repo-check", "--sandbox", "read-only", "--model", config["model"],
            "--config", f"model_reasoning_effort=\"{config['reasoning_effort']}\"",
            "--output-schema", schema.name, "--output-last-message", "CASE.json",
            "--cd", "UNIQUE_EMPTY_TEMP_DIR", "-",
        ],
        "cases": [{"case_id": item["case_id"], "input_sha256": item["input_sha256"]} for item in items],
        "attempts": [],
    }
    write_json(manifest_path, manifest)

    def invoke(item: dict[str, str]) -> dict[str, object]:
        case_id = item["case_id"]
        output = raw / f"{case_id}.json"
        workdir = Path(tempfile.mkdtemp(prefix=f"t5-{method}-{case_id}-"))
        command = [
            codex, "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
            "--skip-git-repo-check", "--color", "never", "--sandbox", "read-only",
            "--model", config["model"],
            "--config", f"model_reasoning_effort=\"{config['reasoning_effort']}\"",
            "--output-schema", str(schema.resolve()), "--output-last-message", str(output.resolve()),
            "--cd", str(workdir), "-",
        ]
        started, clock = now(), time.monotonic()
        error = ""; stdout = stderr = ""
        try:
            completed = subprocess.run(
                command, input=item["input"], text=True, encoding="utf-8", errors="replace",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=config["timeout_seconds"],
                env=os.environ.copy(),
            )
            exit_code, stdout, stderr = completed.returncode, completed.stdout, completed.stderr
        except subprocess.TimeoutExpired as exc:
            exit_code, stdout, stderr = 124, exc.stdout or "", exc.stderr or ""
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
            "started_at": started, "finished_at": now(),
            "duration_seconds": round(time.monotonic() - clock, 3), "exit_code": exit_code,
            "valid_prediction": parsed is not None, "error": error, "prediction": parsed,
        }

    attempts: list[dict[str, object]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=config["concurrency"]) as executor:
        futures = [executor.submit(invoke, item) for item in items]
        for future in concurrent.futures.as_completed(futures):
            result = future.result(); attempts.append(result)
            manifest["attempts"] = [
                {key: value for key, value in attempt.items() if key not in {"input", "prediction"}}
                for attempt in sorted(attempts, key=lambda value: str(value["case_id"]))
            ]
            write_json(manifest_path, manifest)
            print(
                f"{len(attempts):02d}/{EXPECTED_CASES} {result['case_id']} "
                f"valid={result['valid_prediction']} seconds={result['duration_seconds']}", flush=True,
            )
    attempts.sort(key=lambda value: str(value["case_id"]))
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
    failures = [attempt for attempt in attempts if not attempt["valid_prediction"]]
    manifest.update({
        "status": "complete" if not failures else "complete_with_failures", "finished_at": now(),
        "valid_predictions": len(attempts) - len(failures), "failed_predictions": len(failures),
        "attempts": [
            {key: value for key, value in attempt.items() if key not in {"input", "prediction"}}
            for attempt in attempts
        ],
        "prediction_sha256": digest(output_jsonl.read_bytes()),
        "input_output_pairs_sha256": digest(pairs_jsonl.read_bytes()),
    })
    write_json(manifest_path, manifest)
    print(json.dumps({"method": method, "status": manifest["status"],
                      "valid": manifest["valid_predictions"], "failed": manifest["failed_predictions"]}))


if __name__ == "__main__":
    main()
