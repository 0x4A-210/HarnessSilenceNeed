#!/usr/bin/env python3
"""Shared one-shot, isolated blind-prediction runner."""

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


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_baseline(out: Path, baseline: str) -> None:
    if baseline not in {"gap_only", "evolution_aware"}:
        raise ValueError(baseline)
    cases_dir = out / "cases"
    prompt = out / "prompts" / f"{baseline}_prompt.md"
    schema = out / "prompts" / f"{baseline}_schema.json"
    results = out / "results"
    raw = results / f"raw_{baseline}"
    predictions = results / f"{baseline}_predictions.jsonl"
    pairs = results / f"{baseline}_input_output_pairs.jsonl"
    manifest_path = results / f"run_manifest_{baseline}.json"
    if raw.exists() or predictions.exists() or pairs.exists() or manifest_path.exists():
        raise SystemExit(f"Refusing to rerun one-shot baseline {baseline}")
    paths = sorted(cases_dir.glob("C*/blind_input.md"))
    if len(paths) != 64:
        raise SystemExit(f"expected 64 frozen blind inputs, found {len(paths)}")
    fixed = prompt.read_text(encoding="utf-8").rstrip()
    codex = shutil.which("codex")
    if not codex:
        raise SystemExit("codex executable not found")
    version = subprocess.run([codex, "--version"], text=True, capture_output=True, check=True).stdout.strip()
    items = []
    for path in paths:
        case_id = path.parent.name
        case = path.read_text(encoding="utf-8")
        if f"\n{case_id}\n" not in case:
            raise SystemExit(f"case ID mismatch: {path}")
        full_input = fixed + "\n\n--- BEGIN ANONYMOUS CASE ---\n\n" + case + "\n--- END ANONYMOUS CASE ---\n"
        items.append({"case_id": case_id, "input": full_input, "input_sha256": sha256(full_input.encode())})
    manifest = {
        "status": "running", "baseline": baseline, "started_at": now(), "finished_at": None,
        "protocol": "one fresh ephemeral process per case; no retries; runner reads only blind_input.md plus the fixed prompt/schema",
        "model": MODEL, "reasoning_effort": REASONING_EFFORT, "codex_version": version,
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
        workdir = Path(tempfile.mkdtemp(prefix=f"maintenance-{baseline}-{case_id}-"))
        command = [
            codex, "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
            "--skip-git-repo-check", "--color", "never", "--sandbox", "read-only",
            "--model", MODEL, "--config", f'model_reasoning_effort="{REASONING_EFFORT}"',
            "--output-schema", str(schema.resolve()), "--output-last-message", str(output.resolve()),
            "--cd", str(workdir), "-",
        ]
        started, clock = now(), time.monotonic()
        error = ""
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
            "started_at": started, "finished_at": now(), "duration_seconds": round(time.monotonic() - clock, 3),
            "exit_code": exit_code, "valid_prediction": parsed is not None, "error": error,
            "prediction": parsed,
        }

    attempts: list[dict[str, object]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        futures = [executor.submit(invoke, item) for item in items]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            attempts.append(result)
            compact = [{k: v for k, v in x.items() if k not in {"input", "prediction"}} for x in sorted(attempts, key=lambda y: str(y["case_id"]))]
            manifest["attempts"] = compact
            write_json(manifest_path, manifest)
            print(f"{len(attempts):02d}/64 {result['case_id']} exit={result['exit_code']} valid={result['valid_prediction']} seconds={result['duration_seconds']}", flush=True)
    attempts.sort(key=lambda x: str(x["case_id"]))
    failures = [x for x in attempts if not x["valid_prediction"]]
    with predictions.open("w", encoding="utf-8", newline="\n") as handle:
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
    })
    write_json(manifest_path, manifest)
    print(json.dumps({"baseline": baseline, "status": manifest["status"], "valid": manifest["valid_predictions"], "failed": manifest["failed_predictions"]}))
