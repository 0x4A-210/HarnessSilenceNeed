#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
LEGACY_REPOS = WORKSPACE / "FSE2026-harness-degradation" / "sources" / "projects"
NEW_REPOS = ROOT / "mining" / "repos"
REPOS = {
    "c-ares": LEGACY_REPOS / "c-ares",
    "libspng": LEGACY_REPOS / "libspng",
    "selinux": LEGACY_REPOS / "selinux",
    "solidity": LEGACY_REPOS / "solidity",
    "h2o": LEGACY_REPOS / "h2o",
    "libplist": LEGACY_REPOS / "libplist",
    "meshoptimizer": LEGACY_REPOS / "meshoptimizer",
    "simdjson": NEW_REPOS / "simdjson",
    "libxml2": NEW_REPOS / "libxml2",
    "libarchive": NEW_REPOS / "libarchive",
}
SPLITS = {
    "c-ares": "SEEN_PROJECT",
    "libspng": "SEEN_PROJECT",
    "selinux": "SEEN_PROJECT",
    "solidity": "SEEN_PROJECT",
    "h2o": "SEEN_PROJECT",
    "libplist": "SEEN_PROJECT",
    "meshoptimizer": "SEEN_PROJECT",
    "simdjson": "UNSEEN_PROJECT_HOLDOUT",
    "libxml2": "UNSEEN_PROJECT_HOLDOUT",
    "libarchive": "UNSEEN_PROJECT_HOLDOUT",
}
SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".hxx", ".inc"}
HARNESS_PARTS = {"fuzz", "fuzzing", "fuzzers", "ossfuzz", "oss-fuzz"}
VENDORED_PARTS = {"third_party", "thirdparty", "vendor", "vendors", "deps", "extern", "external"}
NON_PRODUCTION_PARTS = {
    "test", "tests", "testing", "fuzz", "fuzzing", "fuzzers", "ossfuzz", "oss-fuzz",
    "doc", "docs", "demo", "demos", "example", "examples", "bench", "benchmark", "benchmarks",
    "third_party", "thirdparty", "vendor", "vendors", "deps", "extern", "external", "generated", "build",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def git(project: str, *args: str, check: bool = True, input_text: str | None = None) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", "-c", "http.proxy=", "-C", str(REPOS[project]), *args],
        input=input_text, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    if check and result.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed for {project}: {result.stderr[-2000:]}")
    return result


def is_harness(path: str) -> bool:
    value = PurePosixPath(path.lower())
    return value.suffix in SOURCE_SUFFIXES and not any(part in VENDORED_PARTS for part in value.parts) and (
        "fuzz" in value.name or "fuzzer" in value.name or any(part in HARNESS_PARTS for part in value.parts)
    )


def is_production(path: str) -> bool:
    value = PurePosixPath(path.lower())
    non_production_prefixes = ("test", "fuzz", "demo", "example", "bench")
    return (value.suffix in SOURCE_SUFFIXES and not is_harness(path)
            and not any(part in NON_PRODUCTION_PARTS or part.startswith(non_production_prefixes)
                        for part in value.parts))


def read_csv(path: Path) -> list[dict[str, str]]:
    import sys
    csv.field_size_limit(sys.maxsize)
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader(); writer.writerows(rows)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_symbol(value: str) -> str:
    return "".join(value.replace("operator =", "operator=").replace("operator []", "operator[]").split()).lstrip(":")


def symbol_matches(candidate: str, target: str) -> bool:
    candidate, target = normalize_symbol(candidate), normalize_symbol(target)
    return candidate == target or candidate.endswith("::" + target) or target.endswith("::" + candidate)


def percentile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    values = sorted(values); position = (len(values) - 1) * probability
    low = int(position); high = min(low + 1, len(values) - 1); fraction = position - low
    return values[low] * (1 - fraction) + values[high] * fraction
