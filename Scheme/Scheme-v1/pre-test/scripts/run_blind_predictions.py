#!/usr/bin/env python3
"""Run the frozen prompt once per anonymous case in isolated Codex processes."""

from __future__ import annotations

import concurrent.futures
import csv
import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


HERE = Path(__file__).resolve()
OUT = HERE.parents[1]
CASES = OUT / "cases"
PROMPT = OUT / "prompts" / "fixed_prompt.md"
SCHEMA = OUT / "prompts" / "prediction_schema.json"
RESULTS = OUT / "results"
RAW = RESULTS / "raw"
MANIFEST = RESULTS / "run_manifest.json"
PREDICTIONS = RESULTS / "llm_predictions.jsonl"
MODEL = "gpt-5.6-sol"
REASONING_EFFORT = "high"
CONCURRENCY = 4
TIMEOUT_SECONDS = 900


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    if MANIFEST.exists() or PREDICTIONS.exists() or RAW.exists():
        raise SystemExit(
            "Refusing to run: one-attempt blind-run artifacts already exist. "
            "Inspect results/run_manifest.json; do not retry cases selectively."
        )
    case_paths = sorted(CASES.glob("C*.md"))
    if len(case_paths) != 105:
        raise SystemExit(f"expected 105 cases, found {len(case_paths)}")
    fixed = PROMPT.read_text(encoding="utf-8").rstrip()
    codex = shutil.which("codex")
    if not codex:
        raise SystemExit("codex executable not found")
    version = subprocess.run([codex, "--version"], text=True, capture_output=True, check=True).stdout.strip()
    blind_root = Path(tempfile.mkdtemp(prefix="harness-blind-run-"))
    RAW.mkdir(parents=True)

    cases: list[dict] = []
    for path in case_paths:
        value = path.read_text(encoding="utf-8")
        case_id = path.stem
        if f"\n{case_id}\n" not in value:
            raise SystemExit(f"case ID mismatch in {path}")
        cases.append({"case_id": case_id, "path": path, "text": value, "sha256": sha256(value)})

    manifest = {
        "status": "running",
        "started_at": utc_now(),
        "finished_at": None,
        "protocol": "one fresh ephemeral process per case; no retries; label mapping not read",
        "model": MODEL,
        "reasoning_effort": REASONING_EFFORT,
        "codex_version": version,
        "concurrency": CONCURRENCY,
        "timeout_seconds": TIMEOUT_SECONDS,
        "fixed_prompt_sha256": sha256(fixed + "\n"),
        "schema_sha256": hashlib.sha256(SCHEMA.read_bytes()).hexdigest(),
        "working_directory": "fresh temporary empty directory (deleted after run)",
        "command_template": [
            "codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
            "--skip-git-repo-check", "--sandbox", "read-only", "--model", MODEL,
            "--config", f'model_reasoning_effort="{REASONING_EFFORT}"',
            "--output-schema", "prediction_schema.json", "--output-last-message", "CASE.json",
            "--cd", "EMPTY_TEMP_DIR", "-",
        ],
        "cases": [{"case_id": x["case_id"], "case_sha256": x["sha256"]} for x in cases],
        "attempts": [],
    }
    write_json(MANIFEST, manifest)

    def invoke(item: dict) -> dict:
        case_id = item["case_id"]
        output_path = RAW / f"{case_id}.json"
        prompt = (
            fixed
            + "\n\n--- BEGIN ANONYMOUS CASE ---\n\n"
            + item["text"]
            + "\n--- END ANONYMOUS CASE ---\n"
        )
        command = [
            codex, "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
            "--skip-git-repo-check", "--color", "never", "--sandbox", "read-only",
            "--model", MODEL, "--config", f'model_reasoning_effort="{REASONING_EFFORT}"',
            "--output-schema", str(SCHEMA.resolve()), "--output-last-message", str(output_path.resolve()),
            "--cd", str(blind_root), "-",
        ]
        started = utc_now()
        monotonic = time.monotonic()
        try:
            completed = subprocess.run(
                command,
                input=prompt,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=TIMEOUT_SECONDS,
                env=os.environ.copy(),
            )
            exit_code = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
            error = ""
        except subprocess.TimeoutExpired as exc:
            exit_code = 124
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            error = f"timeout after {TIMEOUT_SECONDS}s"
        duration = round(time.monotonic() - monotonic, 3)
        (RAW / f"{case_id}.stdout.log").write_text(stdout, encoding="utf-8", errors="replace")
        (RAW / f"{case_id}.stderr.log").write_text(stderr, encoding="utf-8", errors="replace")
        parsed = None
        if exit_code == 0 and output_path.exists():
            try:
                parsed = json.loads(output_path.read_text(encoding="utf-8"))
                if parsed.get("case_id") != case_id:
                    error = f"response case_id={parsed.get('case_id')!r}, expected {case_id}"
                    parsed = None
            except (json.JSONDecodeError, OSError) as exc:
                error = f"invalid JSON output: {exc}"
        elif not error:
            error = f"codex exit code {exit_code}"
        return {
            "case_id": case_id,
            "case_sha256": item["sha256"],
            "started_at": started,
            "finished_at": utc_now(),
            "duration_seconds": duration,
            "exit_code": exit_code,
            "valid_prediction": parsed is not None,
            "error": error,
            "prediction": parsed,
        }

    attempts: list[dict] = []
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
            futures = {executor.submit(invoke, item): item["case_id"] for item in cases}
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                attempts.append(result)
                print(
                    f"{len(attempts):03d}/105 {result['case_id']} "
                    f"exit={result['exit_code']} valid={result['valid_prediction']} "
                    f"seconds={result['duration_seconds']}",
                    flush=True,
                )
                manifest["attempts"] = sorted(
                    [{k: v for k, v in x.items() if k != "prediction"} for x in attempts],
                    key=lambda x: x["case_id"],
                )
                write_json(MANIFEST, manifest)
    finally:
        shutil.rmtree(blind_root, ignore_errors=True)

    attempts.sort(key=lambda x: x["case_id"])
    failures = [x for x in attempts if not x["valid_prediction"]]
    with PREDICTIONS.open("w", encoding="utf-8", newline="\n") as handle:
        for attempt in attempts:
            if attempt["prediction"] is not None:
                handle.write(json.dumps(attempt["prediction"], ensure_ascii=False, separators=(",", ":")) + "\n")
    if failures:
        with (RESULTS / "run_errors.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["case_id", "exit_code", "error"])
            writer.writeheader()
            writer.writerows(failures)
    manifest["status"] = "complete" if not failures else "complete_with_failures"
    manifest["finished_at"] = utc_now()
    manifest["valid_predictions"] = len(attempts) - len(failures)
    manifest["failed_predictions"] = len(failures)
    manifest["attempts"] = [
        {k: v for k, v in x.items() if k != "prediction"} for x in attempts
    ]
    write_json(MANIFEST, manifest)
    print(json.dumps({
        "status": manifest["status"],
        "valid_predictions": manifest["valid_predictions"],
        "failed_predictions": manifest["failed_predictions"],
    }))


if __name__ == "__main__":
    main()
