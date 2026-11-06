#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
T5 = WORKSPACE / "t5-delta-aware-validation"
T6 = WORKSPACE / "t6-dynamic-baseline-validation"
PROJECTS = WORKSPACE / "FSE2026-harness-degradation" / "sources" / "projects"

SOURCE_SUFFIXES = (".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx")
EXCLUDED_PRODUCTION_PARTS = {
    "test", "tests", "fuzz", "fuzzer", "fuzzers", "tools", "tool",
    "example", "examples", "demo", "demos", "build", "generated",
    "third_party", "thirdparty", "vendor", "vendors",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(command: list[str], *, cwd: Path | None = None, check: bool = True,
        input_bytes: bytes | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, check=check, input=input_bytes,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def git(project: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return run(["git", "-C", str(PROJECTS / project), *args], check=check)


def is_source(path: str) -> bool:
    return path.lower().endswith(SOURCE_SUFFIXES)


def is_production(path: str) -> bool:
    if not is_source(path):
        return False
    parts = {part.lower() for part in Path(path).parts}
    return not bool(parts & EXCLUDED_PRODUCTION_PARTS)


def normalize_symbol(value: str) -> str:
    value = value.replace("operator =", "operator=").replace("operator []", "operator[]")
    return "".join(value.split()).lstrip(":")


def symbol_matches(candidate: str, target: str) -> bool:
    candidate = normalize_symbol(candidate)
    target = normalize_symbol(target)
    return candidate == target or candidate.endswith("::" + target) or target.endswith("::" + candidate)


def percentile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def git_paths(project: str, commit: str) -> list[str]:
    result = git(project, "ls-tree", "-r", "--name-only", commit)
    return result.stdout.decode("utf-8", errors="replace").splitlines()


def materialize_snapshot(project: str, commit: str, paths: list[str], destination: Path) -> None:
    """Extract tracked files without changing the deliberately dirty project worktree."""
    destination.mkdir(parents=True, exist_ok=True)
    if not paths:
        return
    archive = subprocess.Popen(
        ["git", "-C", str(PROJECTS / project), "archive", "--format=tar", commit, "--", *paths],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert archive.stdout is not None
    extracted = subprocess.run(
        ["tar", "-x", "-C", str(destination)],
        stdin=archive.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    archive.stdout.close()
    archive_stderr = archive.stderr.read() if archive.stderr else b""
    archive_code = archive.wait()
    if archive_code or extracted.returncode:
        raise RuntimeError(
            "snapshot extraction failed: "
            + archive_stderr.decode(errors="replace")
            + extracted.stderr.decode(errors="replace")
        )


def peak_rss_kib() -> int:
    # Linux reports ru_maxrss in KiB.
    import resource
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


class Timer:
    def __enter__(self):
        self.started = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.seconds = time.perf_counter() - self.started
