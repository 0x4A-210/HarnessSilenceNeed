#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
T5 = WORKSPACE / "t5-delta-aware-validation"
SOURCES = WORKSPACE / "FSE2026-harness-degradation" / "sources"
PROJECTS = Path(os.environ.get("T6_PROJECTS_DIR", str(SOURCES / "projects")))
OSS_FUZZ = SOURCES / "oss-fuzz"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def composite_hash(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for path in sorted(paths, key=lambda p: str(p)):
        h.update(str(path.relative_to(ROOT)).encode())
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(cmd: list[str], *, cwd: Path | None = None, check: bool = True,
        text: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, check=check, text=text,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def git(project: str, *args: str, text: bool = True,
        check: bool = True) -> subprocess.CompletedProcess:
    return run(["git", "-C", str(PROJECTS / project), *args],
               text=text, check=check)


def valid_cases() -> list[dict[str, str]]:
    labels = read_csv(T5 / "frozen-ground-truth" / "labels.csv")
    invalid = {
        r["case_id"]
        for r in read_csv(T5 / "frozen-ground-truth" / "invalidations.csv")
        if r.get("status") == "INVALIDATE"
    }
    evidence = {
        r["case_id"]: r
        for r in read_csv(T5 / "frozen-ground-truth" / "evidence.csv")
    }
    rows = []
    for label in labels:
        if label["case_id"] in invalid:
            continue
        row = dict(label)
        row.update({f"evidence_{k}": v for k, v in evidence[label["case_id"]].items()})
        rows.append(row)
    return rows


TARGET_SOURCES = {
    "c-ares": {
        "ares_parse_reply_fuzzer": "test/ares-test-fuzz.c",
        "ares_create_query_fuzzer": "test/ares-test-fuzz-name.c",
    },
    "libplist": {
        "bplist_fuzzer": "fuzz/bplist_fuzzer.cc",
        "xplist_fuzzer": "fuzz/xplist_fuzzer.cc",
        "jplist_fuzzer": "fuzz/jplist_fuzzer.cc",
        "oplist_fuzzer": "fuzz/oplist_fuzzer.cc",
    },
    "libspng": {"spng_read_fuzzer": "tests/spng_read_fuzzer.c"},
    "meshoptimizer": {
        "clusterfuzzer": "tools/clusterfuzz.cpp",
        "codecfuzzer": "tools/codecfuzz.cpp",
        "simplifyfuzzer": "tools/simplifyfuzz.cpp",
    },
}

CORPUS_RULES = {
    "c-ares": {
        "ares_parse_reply_fuzzer": ("test/fuzzinput/", None),
        "ares_create_query_fuzzer": ("test/fuzznames/", None),
    },
    "libplist": {
        "bplist_fuzzer": ("test/data/", (".bplist",)),
        "xplist_fuzzer": ("test/data/", (".plist", ".xml")),
        "jplist_fuzzer": ("test/data/", (".json",)),
        "oplist_fuzzer": ("test/data/", (".ostep", ".openstep")),
    },
    "libspng": {"spng_read_fuzzer": ("tests/", (".png",))},
    "meshoptimizer": {
        "clusterfuzzer": (None, None),
        "codecfuzzer": (None, None),
        "simplifyfuzzer": (None, None),
    },
}


@lru_cache(maxsize=None)
def tree_paths(project: str, commit: str) -> list[str]:
    return list(tree_entries(project, commit))


@lru_cache(maxsize=None)
def tree_entries(project: str, commit: str) -> dict[str, tuple[str, int]]:
    """Return path -> (Git blob object id, byte size) with one Git process."""
    out = git(project, "ls-tree", "-r", "-l", commit).stdout
    result = {}
    for line in out.splitlines():
        meta, path = line.split("\t", 1)
        _mode, kind, oid, size = meta.split()
        if kind == "blob":
            # Partial/promisor clones report BAD until a blob is materialized.
            # The immutable Git object id is still valid provenance.
            result[path] = (oid, -1 if size == "BAD" else int(size))
    return result


def target_sources(project: str, commit: str) -> dict[str, str]:
    paths = set(tree_paths(project, commit))
    return {name: path for name, path in TARGET_SOURCES[project].items()
            if path in paths}


def corpus_paths(project: str, commit: str, target: str) -> list[str]:
    prefix, suffixes = CORPUS_RULES[project][target]
    if prefix is None:
        return []
    result = []
    for path in tree_paths(project, commit):
        if not path.startswith(prefix):
            continue
        if suffixes is not None and not path.lower().endswith(suffixes):
            continue
        result.append(path)
    return result


SYNTHETIC_SEEDS = {
    "seed-001.bin": bytes([0]),
    "seed-004.bin": bytes([0, 1, 2, 3]),
    "seed-016.bin": bytes(range(16)),
    "seed-064.bin": bytes((i * 37 + 11) % 256 for i in range(64)),
    "seed-256.bin": bytes(range(256)),
}
