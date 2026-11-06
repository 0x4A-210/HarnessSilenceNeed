#!/usr/bin/env python3
"""Measure executable changed-line coverage for selected Wuffs cases.

Only S1 source lines that GCC/gcov identifies as executable in at least one of
H0 or H1 are used as the denominator. Generated Wuffs source is included by
the real fuzz translation units, so gcov reports it with its original path.
Uninstrumentable generator lines are deliberately not estimated.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import random
import re
import subprocess
import sys
import tarfile
import tempfile
from collections import defaultdict
from pathlib import Path


HERE = Path(__file__).resolve()
ROOT = HERE.parents[1]
WORKSPACE = ROOT.parent
REPO = WORKSPACE / "FSE2026-harness-degradation" / "sources" / "projects" / "wuffs"
DATA = ROOT / "data"


def git_bytes(*args: str, check: bool = True) -> bytes:
    result = subprocess.run(["git", "-C", str(REPO), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and result.returncode:
        raise RuntimeError(result.stderr.decode(errors="replace"))
    return result.stdout


def extract(commit: str, destination: Path) -> None:
    archive = subprocess.Popen(["git", "-C", str(REPO), "archive", commit], stdout=subprocess.PIPE)
    assert archive.stdout is not None
    with tarfile.open(fileobj=archive.stdout, mode="r|") as handle:
        handle.extractall(destination, filter="data")
    if archive.wait() != 0:
        raise RuntimeError(f"git archive failed for {commit}")


def overlay_h0(tree: Path, parent: str, harness_paths: list[str]) -> None:
    for relative in harness_paths:
        target = tree / relative
        exists = subprocess.run(
            ["git", "-C", str(REPO), "cat-file", "-e", f"{parent}:{relative}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
        if exists:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(git_bytes("show", f"{parent}:{relative}"))
        elif target.exists():
            target.unlink()


def changed_line_map(parent: str, commit: str, source_paths: list[str]) -> dict[str, set[int]]:
    patch = git_bytes("diff", "--unified=0", parent, commit, "--", *source_paths).decode(errors="replace")
    result: dict[str, set[int]] = defaultdict(set)
    current = ""
    for line in patch.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
            continue
        match = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
        if current and match:
            start = int(match.group(1)); count = int(match.group(2) or "1")
            result[current].update(range(start, start + count))
    return result


def make_corpus(tree: Path) -> list[Path]:
    corpus = tree / ".coverage-corpus"
    corpus.mkdir()
    payloads = [
        b"{}\n", b"[]\n", b"0\n", b"true\n", b"0 // trailing\n",
        b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x00\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
        b"\x01", b"\xa1\x61a\x01", bytes(range(64)), bytes(range(255, -1, -1)),
    ]
    rng = random.Random(0x5EED2026)
    for _ in range(118):
        length = rng.randrange(1, 513)
        payloads.append(bytes(rng.randrange(256) for _ in range(length)))
    paths = []
    for index, payload in enumerate(payloads):
        path = corpus / f"input-{index:03d}"
        path.write_bytes(payload)
        paths.append(path)
    return paths


def normalize_source(value: str, tree: Path) -> str:
    path = Path(value)
    try:
        return path.resolve().relative_to(tree.resolve()).as_posix()
    except ValueError:
        return path.as_posix().lstrip("./")


def collect_gcov(tree: Path, data_file: Path) -> tuple[dict[tuple[str, int], int], list[dict[str, object]], str]:
    before = set(tree.glob("*.gcov.json.gz"))
    result = subprocess.run(["gcov", "-j", str(data_file)], cwd=tree, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    after = set(tree.glob("*.gcov.json.gz"))
    created = sorted(after - before, key=lambda p: p.stat().st_mtime_ns)
    if result.returncode != 0 or not created:
        return {}, [], result.stdout
    path = created[-1]
    document = json.load(gzip.open(path, "rt", encoding="utf-8"))
    path.unlink()
    lines: dict[tuple[str, int], int] = {}
    functions: list[dict[str, object]] = []
    for file_entry in document.get("files", []):
        relative = normalize_source(str(file_entry["file"]), tree)
        for line in file_entry.get("lines", []):
            key = (relative, int(line["line_number"]))
            lines[key] = lines.get(key, 0) + int(line.get("count", 0))
        for function in file_entry.get("functions", []):
            functions.append({"file": relative, **function})
    return lines, functions, result.stdout


def measure_side(candidate_id: str, commit: str, parent: str, harness_paths: list[str],
                 use_h0: bool) -> tuple[dict[tuple[str, int], int], list[dict[str, object]], str, str]:
    with tempfile.TemporaryDirectory(prefix=f"silent-wuffs-cov-{candidate_id}-") as temporary:
        tree = Path(temporary)
        extract(commit, tree)
        if use_h0:
            overlay_h0(tree, parent, harness_paths)
        harnesses = [p for p in harness_paths if (tree / p).is_file() and "fuzzer" in Path(p).name.lower()]
        corpus = make_corpus(tree)
        all_lines: dict[tuple[str, int], int] = {}
        all_functions: list[dict[str, object]] = []
        logs: list[str] = []
        compiled_count = 0
        runtime_count = 0
        for index, relative in enumerate(harnesses):
            source = tree / relative
            compiler = "g++" if source.suffix in {".cc", ".cpp", ".cxx"} else "gcc"
            standard = "-std=gnu++17" if compiler == "g++" else "-std=gnu11"
            executable = tree / f"coverage-probe-{index}"
            command = [compiler, standard, "-O0", "--coverage", "-DWUFFS_CONFIG__FUZZLIB_MAIN",
                       relative, "-o", str(executable)]
            built = subprocess.run(command, cwd=tree, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=240)
            logs.append("BUILD " + relative + " exit=" + str(built.returncode) + "\n" + built.stdout.decode(errors="replace")[-3000:])
            if built.returncode:
                continue
            compiled_count += 1
            ran = subprocess.run([str(executable), *map(str, corpus)], cwd=tree, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, timeout=120)
            logs.append("RUN " + relative + " exit=" + str(ran.returncode) + "\n" + ran.stdout.decode(errors="replace")[-3000:])
            if ran.returncode == 0:
                runtime_count += 1
            for data_file in sorted(tree.glob(f"coverage-probe-{index}-*.gcda")):
                lines, functions, output = collect_gcov(tree, data_file)
                logs.append("GCOV " + data_file.name + "\n" + output[-2000:])
                for key, count in lines.items():
                    all_lines[key] = all_lines.get(key, 0) + count
                all_functions.extend(functions)
        build_status = "PASS" if harnesses and compiled_count == len(harnesses) else ("NOT_APPLICABLE" if not harnesses else "FAIL")
        runtime_status = "PASS" if harnesses and runtime_count == len(harnesses) else ("NOT_APPLICABLE" if not harnesses else "FAIL")
        return all_lines, all_functions, build_status, runtime_status + "\n" + "\n".join(logs)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidate_ids", nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--details", type=Path, required=True)
    args = parser.parse_args()
    csv.field_size_limit(sys.maxsize)
    candidates = {r["candidate_id"]: r for r in csv.DictReader((DATA / "new_candidates.csv").open(encoding="utf-8", newline=""))}
    rows = []
    detail_rows = []
    for candidate_id in args.candidate_ids:
        item = candidates[candidate_id]
        paths = json.loads(item["harness_files_changed"])
        sources = json.loads(item["source_files_changed"])
        changed = changed_line_map(item["parent"], item["commit"], sources)
        print(candidate_id, "H0", flush=True)
        h0_lines, h0_functions, h0_build, h0_log = measure_side(candidate_id, item["commit"], item["parent"], paths, True)
        print(candidate_id, "H1", flush=True)
        h1_lines, h1_functions, h1_build, h1_log = measure_side(candidate_id, item["commit"], item["parent"], paths, False)
        executable = {
            (path, line) for path, line_numbers in changed.items() for line in line_numbers
            if (path, line) in h0_lines or (path, line) in h1_lines
        }
        h0_covered = {key for key in executable if h0_lines.get(key, 0) > 0}
        h1_covered = {key for key in executable if h1_lines.get(key, 0) > 0}
        function_names = set()
        for function in h0_functions + h1_functions:
            file_name = str(function.get("file", ""))
            start = int(function.get("start_line", 0)); end = int(function.get("end_line", start))
            if any((file_name, line) in executable for line in range(start, end + 1)):
                function_names.add(str(function.get("demangled_name") or function.get("name") or ""))
        denominator = len(executable)
        h0_rate = (len(h0_covered) / denominator) if denominator else None
        h1_rate = (len(h1_covered) / denominator) if denominator else None
        rows.append({
            "candidate_id": candidate_id,
            "changed_lines": denominator if denominator else "NOT_MEASURED",
            "changed_functions": json.dumps(sorted(function_names), separators=(",", ":")) if function_names else "NOT_MEASURED",
            "h0_changed_lines_covered": len(h0_covered) if denominator else "NOT_MEASURED",
            "h1_changed_lines_covered": len(h1_covered) if denominator else "NOT_MEASURED",
            "h0_changed_coverage": f"{h0_rate:.6f}" if h0_rate is not None else "NOT_MEASURED",
            "h1_changed_coverage": f"{h1_rate:.6f}" if h1_rate is not None else "NOT_MEASURED",
            "delta_changed_coverage": f"{h1_rate-h0_rate:.6f}" if h0_rate is not None and h1_rate is not None else "NOT_MEASURED",
            "h0_instrumented_build": h0_build,
            "h1_instrumented_build": h1_build,
            "measurement_scope": "S1 executable added/modified lines recognized by GCC 13 gcov; deterministic 128-input corpus",
        })
        detail_rows.extend([
            {"candidate_id": candidate_id, "side": "S1_H0", "log": h0_log},
            {"candidate_id": candidate_id, "side": "S1_H1", "log": h1_log},
        ])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["candidate_id", "changed_lines", "changed_functions", "h0_changed_lines_covered",
              "h1_changed_lines_covered", "h0_changed_coverage", "h1_changed_coverage",
              "delta_changed_coverage", "h0_instrumented_build", "h1_instrumented_build", "measurement_scope"]
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    with args.details.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["candidate_id", "side", "log"]); writer.writeheader(); writer.writerows(detail_rows)
    print(json.dumps({"rows": len(rows), "output": str(args.output)}))


if __name__ == "__main__":
    main()
