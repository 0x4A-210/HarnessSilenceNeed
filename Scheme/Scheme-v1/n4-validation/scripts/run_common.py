#!/usr/bin/env python3
"""One-shot isolated runner for the two frozen task-4 methods."""

from __future__ import annotations

import concurrent.futures
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


MODEL = "gpt-5.6-sol"
REASONING_EFFORT = "high"
CONCURRENCY = 4
TIMEOUT_SECONDS = 900
EXPECTED_CASES = 40


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def run_method(root: Path, method: str) -> None:
    if method not in {"gap_only", "evolution_aware"}:
        raise ValueError(method)
    inputs = root / "frozen-inputs"
    prompt = root / "prompts" / f"{method}_prompt.md"
    schema = root / "prompts" / f"{method}_schema.json"
    predictions = root / "predictions"
    raw = predictions / f"raw_{method}"
    output_jsonl = predictions / f"{method}.jsonl"
    pairs = predictions / f"{method}_input_output_pairs.jsonl"
    manifest_path = predictions / f"run_manifest_{method}.json"
    if raw.exists() or output_jsonl.exists() or pairs.exists() or manifest_path.exists():
        raise SystemExit(f"refusing to rerun frozen one-shot method {method}")
    case_paths = sorted(inputs.glob("C[0-9][0-9][0-9].md"))
    if len(case_paths) != EXPECTED_CASES:
        raise SystemExit(f"expected {EXPECTED_CASES} frozen inputs, found {len(case_paths)}")
    fixed = prompt.read_text(encoding="utf-8").rstrip()
    codex = shutil.which("codex")
    if not codex:
        raise SystemExit("codex executable not found")
    version = subprocess.run([codex, "--version"], text=True, capture_output=True, check=True).stdout.strip()
    items = []
    for path in case_paths:
        case_id = path.stem
        case = path.read_text(encoding="utf-8")
        if f"\n{case_id}\n" not in case:
            raise SystemExit(f"case ID mismatch: {path}")
        model_input = fixed + "\n\n--- BEGIN ANONYMOUS CASE ---\n\n" + case + "\n--- END ANONYMOUS CASE ---\n"
        items.append({"case_id": case_id, "input": model_input,
                      "input_sha256": sha256(model_input.encode())})
    started_at = now()
    manifest = {
        "status": "running", "method": method, "started_at": started_at, "finished_at": None,
        "protocol": "one fresh ephemeral process per case; zero retries; runner reads only one frozen input plus fixed prompt/schema",
        "ground_truth_files_read": False, "model": MODEL, "reasoning_effort": REASONING_EFFORT,
        "temperature": None, "max_tokens": None, "codex_version": version,
        "concurrency": CONCURRENCY, "timeout_seconds": TIMEOUT_SECONDS,
        "prompt_sha256": sha256(prompt.read_bytes()), "schema_sha256": sha256(schema.read_bytes()),
        "command_template": [
            "codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
            "--skip-git-repo-check", "--sandbox", "read-only", "--model", MODEL,
            "--config", f'model_reasoning_effort="{REASONING_EFFORT}"',
            "--output-schema", schema.name, "--output-last-message", "CASE.json",
            "--cd", "UNIQUE_EMPTY_TEMP_DIR", "-",
        ],
        "cases": [{"case_id": x["case_id"], "input_sha256": x["input_sha256"]} for x in items],
        "attempts": [],
    }
    write_json(manifest_path, manifest)
    raw.mkdir(parents=True)

    def invoke(item: dict[str, str]) -> dict[str, object]:
        case_id = item["case_id"]
        output = raw / f"{case_id}.json"
        workdir = Path(tempfile.mkdtemp(prefix=f"n4-{method}-{case_id}-"))
        command = [
            codex, "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
            "--skip-git-repo-check", "--color", "never", "--sandbox", "read-only",
            "--model", MODEL, "--config", f'model_reasoning_effort="{REASONING_EFFORT}"',
            "--output-schema", str(schema.resolve()), "--output-last-message", str(output.resolve()),
            "--cd", str(workdir), "-",
        ]
        started, clock = now(), time.monotonic()
        error = ""
        stdout = stderr = ""
        try:
            completed = subprocess.run(
                command, input=item["input"], text=True, encoding="utf-8", errors="replace",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=TIMEOUT_SECONDS,
                env=os.environ.copy(),
            )
            exit_code, stdout, stderr = completed.returncode, completed.stdout, completed.stderr
        except subprocess.TimeoutExpired as exc:
            exit_code, stdout, stderr = 124, exc.stdout or "", exc.stderr or ""
            error = f"timeout after {TIMEOUT_SECONDS}s"
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        (raw / f"{case_id}.stdout.log").write_text(stdout, encoding="utf-8", errors="replace")
        (raw / f"{case_id}.stderr.log").write_text(stderr, encoding="utf-8", errors="replace")
        parsed = None
        if exit_code == 0 and output.exists():
            try:
                parsed = json.loads(output.read_text(encoding="utf-8"))
                if parsed.get("case_id") != case_id:
                    error, parsed = f"response case_id mismatch: {parsed.get('case_id')}", None
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
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = [executor.submit(invoke, item) for item in items]
        for future in concurrent.futures.as_completed(futures):
            result = future.result(); attempts.append(result)
            manifest["attempts"] = [{k: v for k, v in x.items() if k not in {"input", "prediction"}}
                                      for x in sorted(attempts, key=lambda y: str(y["case_id"]))]
            write_json(manifest_path, manifest)
            print(f"{len(attempts):02d}/{EXPECTED_CASES} {result['case_id']} exit={result['exit_code']} "
                  f"valid={result['valid_prediction']} seconds={result['duration_seconds']}", flush=True)
    attempts.sort(key=lambda x: str(x["case_id"]))
    failures = [x for x in attempts if not x["valid_prediction"]]
    with output_jsonl.open("w", encoding="utf-8", newline="\n") as handle:
        for attempt in attempts:
            if attempt["prediction"] is not None:
                handle.write(json.dumps(attempt["prediction"], ensure_ascii=False, separators=(",", ":")) + "\n")
    with pairs.open("w", encoding="utf-8", newline="\n") as handle:
        for attempt in attempts:
            handle.write(json.dumps({
                "case_id": attempt["case_id"], "input_sha256": attempt["input_sha256"],
                "model_input": attempt["input"], "model_output": attempt["prediction"],
                "exit_code": attempt["exit_code"], "error": attempt["error"],
            }, ensure_ascii=False, separators=(",", ":")) + "\n")
    manifest.update({
        "status": "complete" if not failures else "complete_with_failures", "finished_at": now(),
        "valid_predictions": len(attempts) - len(failures), "failed_predictions": len(failures),
        "attempts": [{k: v for k, v in x.items() if k not in {"input", "prediction"}} for x in attempts],
        "prediction_sha256": sha256(output_jsonl.read_bytes()),
        "input_output_pairs_sha256": sha256(pairs.read_bytes()),
    })
    write_json(manifest_path, manifest)
    print(json.dumps({"method": method, "status": manifest["status"],
                      "valid": manifest["valid_predictions"], "failed": manifest["failed_predictions"]}))

