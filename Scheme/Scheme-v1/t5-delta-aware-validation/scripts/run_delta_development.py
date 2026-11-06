#!/usr/bin/env python3
"""Run one frozen prompt version over all 36 development cases."""

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


ROOT = Path(__file__).resolve().parents[1]
DEV = ROOT / "development-set"
PROMPT_VERSION = os.environ.get("DELTA_DEV_VERSION", "v1")
MODEL = "gpt-5.6-sol"
EFFORT = "high"
CONCURRENCY = 4
TIMEOUT = 900


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    run_dir = DEV / "runs" / PROMPT_VERSION
    if run_dir.exists():
        raise SystemExit(f"refusing to rerun development prompt {PROMPT_VERSION}")
    run_dir.mkdir(parents=True)
    raw = run_dir / "raw"; raw.mkdir()
    prompt = ROOT / "prompts" / f"delta_aware_{PROMPT_VERSION}.md"
    schema = ROOT / "prompts" / "delta_aware_schema.json"
    fixed = prompt.read_text(encoding="utf-8").rstrip()
    cases = list(csv.DictReader((DEV / "cases.csv").open(encoding="utf-8", newline="")))
    items = []
    for row in cases:
        path = ROOT / row["input_path"]
        old_id = row["prior_case_id"]
        content = path.read_text(encoding="utf-8")
        if f"\n{old_id}\n" not in content:
            raise SystemExit(f"case id mismatch: {row['development_id']}")
        model_input = fixed + "\n\n--- BEGIN DEVELOPMENT CASE ---\n\n" + content + "\n--- END DEVELOPMENT CASE ---\n"
        items.append({"development_id": row["development_id"], "case_id": old_id,
                      "input": model_input, "input_sha256": sha256(model_input.encode())})
    codex = shutil.which("codex")
    if not codex:
        raise SystemExit("codex not found")
    manifest = {
        "status": "running", "prompt_version": PROMPT_VERSION, "development_only": True,
        "started_at": now(), "finished_at": None, "model": MODEL, "reasoning_effort": EFFORT,
        "temperature": None, "max_tokens": None, "retries": 0, "concurrency": CONCURRENCY,
        "prompt_sha256": sha256(prompt.read_bytes()), "schema_sha256": sha256(schema.read_bytes()),
        "case_count": len(items), "attempts": [],
    }
    write_json(run_dir / "run_manifest.json", manifest)

    def invoke(item: dict[str, str]) -> dict:
        out = raw / f"{item['case_id']}.json"
        work = Path(tempfile.mkdtemp(prefix=f"delta-dev-{item['case_id']}-"))
        cmd = [codex, "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
               "--skip-git-repo-check", "--color", "never", "--sandbox", "read-only",
               "--model", MODEL, "--config", f'model_reasoning_effort="{EFFORT}"',
               "--output-schema", str(schema.resolve()), "--output-last-message", str(out.resolve()),
               "--cd", str(work), "-"]
        clock, started = time.monotonic(), now(); error = ""
        try:
            done = subprocess.run(cmd, input=item["input"], text=True, encoding="utf-8", errors="replace",
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=TIMEOUT,
                                  env=os.environ.copy())
            code, stdout, stderr = done.returncode, done.stdout, done.stderr
        except subprocess.TimeoutExpired as exc:
            code, stdout, stderr = 124, exc.stdout or "", exc.stderr or ""; error = "timeout"
        finally:
            shutil.rmtree(work, ignore_errors=True)
        (raw / f"{item['case_id']}.stdout.log").write_text(stdout, encoding="utf-8", errors="replace")
        (raw / f"{item['case_id']}.stderr.log").write_text(stderr, encoding="utf-8", errors="replace")
        parsed = None
        if code == 0 and out.exists():
            try:
                parsed = json.loads(out.read_text(encoding="utf-8"))
                if parsed.get("case_id") != item["case_id"]:
                    error, parsed = "case_id mismatch", None
            except Exception as exc:
                error = f"invalid JSON: {exc}"
        elif not error:
            error = f"exit {code}"
        return {**item, "started_at": started, "finished_at": now(),
                "duration_seconds": round(time.monotonic() - clock, 3), "exit_code": code,
                "valid": parsed is not None, "error": error, "prediction": parsed}

    attempts = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = [pool.submit(invoke, x) for x in items]
        for future in concurrent.futures.as_completed(futures):
            result = future.result(); attempts.append(result)
            manifest["attempts"] = [{k: v for k, v in a.items() if k not in {"input", "prediction"}}
                                      for a in sorted(attempts, key=lambda x: x["case_id"])]
            write_json(run_dir / "run_manifest.json", manifest)
            print(f"{len(attempts):02d}/36 {result['case_id']} valid={result['valid']} seconds={result['duration_seconds']}", flush=True)
    attempts.sort(key=lambda x: x["case_id"])
    with (run_dir / "predictions.jsonl").open("w", encoding="utf-8") as handle:
        for a in attempts:
            if a["prediction"] is not None:
                handle.write(json.dumps(a["prediction"], ensure_ascii=False, separators=(",", ":")) + "\n")
    with (run_dir / "input_output_pairs.jsonl").open("w", encoding="utf-8") as handle:
        for a in attempts:
            handle.write(json.dumps({"development_id": a["development_id"], "case_id": a["case_id"],
                                     "input_sha256": a["input_sha256"], "model_input": a["input"],
                                     "model_output": a["prediction"], "exit_code": a["exit_code"],
                                     "error": a["error"]}, ensure_ascii=False, separators=(",", ":")) + "\n")
    failures = [a for a in attempts if not a["valid"]]
    manifest.update({"status": "complete" if not failures else "complete_with_failures",
                     "finished_at": now(), "valid_predictions": len(attempts) - len(failures),
                     "failed_predictions": len(failures),
                     "attempts": [{k: v for k, v in a.items() if k not in {"input", "prediction"}} for a in attempts],
                     "prediction_sha256": sha256((run_dir / "predictions.jsonl").read_bytes()),
                     "input_output_pairs_sha256": sha256((run_dir / "input_output_pairs.jsonl").read_bytes())})
    write_json(run_dir / "run_manifest.json", manifest)
    print(json.dumps({"status": manifest["status"], "valid": manifest["valid_predictions"],
                      "failed": manifest["failed_predictions"]}))


if __name__ == "__main__":
    main()
