"""Run current heads from local prepared inputs; labels are never read here."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
import time

import threading

from .engine import analyze, protocol
from .llm.backends import QuotaExhausted
from .util import PROJECT_ROOT, digest, inside, read_json, write_json


def code_snapshot():
    files = list((PROJECT_ROOT / "src").rglob("*.py"))
    files += list((PROJECT_ROOT / "src").rglob("*.txt"))
    files += list((PROJECT_ROOT / "configs").glob("*.yaml"))
    files += [PROJECT_ROOT / "pyproject.toml"]
    return {p.relative_to(PROJECT_ROOT).as_posix(): digest(p.read_bytes()) for p in sorted(files)}


def freeze_run(run, code_unchanged=True):
    files = {p.relative_to(run).as_posix(): digest(p.read_bytes())
             for p in sorted(run.rglob("*")) if p.is_file()
             and p.name != "freeze.json" and "evaluation" not in p.relative_to(run).parts}
    write_json(run / "freeze.json", {"files": files,
                                     "code_unchanged_during_run": code_unchanged})


def verify_frozen(run):
    frozen = read_json(run / "freeze.json")
    if not frozen.get("code_unchanged_during_run"):
        raise ValueError("Run code changed during inference")

    def check_file(item):
        name, expected = item
        if digest(inside(run, name).read_bytes()) != expected:
            raise ValueError("Frozen artifact mismatch: " + name)

    entries = list(frozen["files"].items())
    with ThreadPoolExecutor(max_workers=12) as pool:
        for offset in range(0, len(entries), 1000):
            list(pool.map(check_file, entries[offset:offset + 1000]))
    return len(frozen["files"])


def verify_inputs(workspace):
    """Check the actual bytes, not just the metadata count."""
    from .context.reader import load_case
    samples, files, size = 0, 0, 0
    def check_file(item):
        root, name, entry = item
        if not name.startswith("input/"):
            raise ValueError("Invalid input path: " + name)
        path = inside(root, name)
        cursor = root
        for part in Path(name).parts:
            cursor /= part
            if cursor.is_symlink():
                raise ValueError("Input symlink: " + name)
        data = path.read_bytes()
        if digest(data) != entry["sha256"]:
            raise ValueError("Input checksum mismatch: " + str(path))
        return len(data)

    with ThreadPoolExecutor(max_workers=12) as pool:
        for metadata in sorted((workspace / "inputs").glob("case-*/manifest.json")):
            root = metadata.parent
            case = load_case(root)
            if case.sample_id != root.name:
                raise ValueError("Sample directory/ID mismatch")
            entries = list(case.manifest["files"].items())
            for offset in range(0, len(entries), 1000):
                batch = entries[offset:offset + 1000]
                size += sum(pool.map(check_file, ((root, name, entry) for name, entry in batch)))
                files += len(batch)
            samples += 1
    if not samples:
        raise ValueError("No prepared inputs")
    return {"samples": samples, "files": files, "bytes": size}


class QuotaStop(RuntimeError):
    pass


def quota_hit(prediction):
    return any(c.get("error_type") == "QuotaExhausted"
               for h in prediction.get("whole_function_heads", {}).values()
               for c in h.get("model_calls", []))


def retry_reason(prediction, folder):
    errors = [c.get("error", "") or ""
              for h in prediction.get("whole_function_heads", {}).values()
              for c in h.get("model_calls", [])]
    if not any(errors):
        return None
    terms = ("flagged for possible cybersecurity risk", "policy violation", "content_policy_violation")
    for path in folder.rglob("events.jsonl"):
        if any(term in path.read_text(encoding="utf-8", errors="replace").lower() for term in terms):
            return None
    if any("Model timeout" in e or "429" in e or "at capacity" in e or "inference failed" in e for e in errors):
        return "timeout_or_explicit_transient_capacity"
    return None


def run_batch(workspace, run, config, progress=print):
    inputs = sorted(p.parent for p in (workspace / "inputs").glob("case-*/manifest.json"))
    if not inputs:
        raise ValueError("No prepared inputs")
    run.mkdir(parents=True, exist_ok=False)
    snapshot = code_snapshot()
    identities = {p.name: digest((p / "manifest.json").read_bytes()) for p in inputs}
    workers = max(1, min(8, int(config.get("batch", {}).get("concurrency", 4))))
    stored_config = {**config, "workspace": "workspace"}
    write_json(run / "run_manifest.json", {
        "kind": "fresh_inference", "started_utc": datetime.now(timezone.utc).isoformat(),
        "samples": len(inputs), "config": stored_config, "code_files": snapshot,
        "inputs": identities, "protocol_hashes": protocol(config),
        "retry_policy": "Per call: up to llm.transient_retries for network/overload/rate limit. Per sample: one retry for timeout or transient capacity. Quota exhaustion stops the batch; never recorded as semantic unknown.",
        "labels": "Not read by inference; scoring occurs after freezing predictions."})
    started = time.monotonic()

    stop = threading.Event()

    def process(path):
        if stop.is_set():
            raise QuotaStop("not started: account usage limit reached earlier in this batch")
        folder = run / "samples" / path.name
        try:
            result = analyze(path, folder, config)
        except QuotaExhausted as exc:
            stop.set()
            raise QuotaStop("account usage limit reached during this sample: " + str(exc)) from exc
        if quota_hit(result):
            stop.set()
            raise QuotaStop("account usage limit reached during this sample")
        selection = {"selected_path": str(folder.relative_to(run)), "retried": False}
        reason = retry_reason(result, folder)
        if reason:
            folder = run / "technical-retries" / path.name
            write_json(run / "retry-triggers" / (path.name + ".json"), {"reason": reason})
            result = analyze(path, folder, config)
            selection = {"selected_path": str(folder.relative_to(run)), "retried": True, "reason": reason}
        return result, selection

    predictions, selections = [], {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = {pool.submit(process, p): p.name for p in inputs}
        for task in as_completed(pending):
            sample = pending[task]
            try:
                prediction, selection = task.result()
            except Exception as exc:
                error = type(exc).__name__ + ": " + str(exc)
                prediction = {"sample_id": sample, "maintenance_verdict": "unknown", "verdict": "unknown",
                    "attribution_status": "unknown", "maintenance_alarm": False, "joint_alarm": False,
                    "joint_origin": "not_applicable", "analysis_complete": False, "technical_error": error}
                selection = {"selected_path": "samples/" + sample, "retried": False, "technical_error": error}
                write_json(run / "samples" / sample / "prediction.json", prediction)
            predictions.append(prediction)
            selections[sample] = selection
            if progress:
                progress(f"{len(predictions)}/{len(inputs)} {sample}: "
                         f"{prediction['maintenance_verdict']} / {prediction['attribution_status']}")
    if stop.is_set():
        write_json(run / "incomplete.json", {"reason": "quota_exhausted", "selection": selections})
        raise RuntimeError("Account usage limit reached; run is incomplete and was not frozen: " + str(run))
    write_json(run / "predictions.json", sorted(predictions, key=lambda p: p["sample_id"]))
    write_json(run / "selection.json", selections)
    write_json(run / "runtime.json", {"wall_seconds": round(time.monotonic() - started, 3), "concurrency": workers})
    unchanged = snapshot == code_snapshot() and identities == {
        p.name: digest((p / "manifest.json").read_bytes()) for p in inputs}
    freeze_run(run, unchanged)
    if not unchanged:
        raise RuntimeError("Code/config/input metadata changed during inference")
    return {"samples": len(predictions), "run": str(run)}
