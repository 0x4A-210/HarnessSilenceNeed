#!/usr/bin/env python3
"""Compile S1+H0 and S1+H1 for every verified-positive candidate.

The probe is intentionally a translation-unit compatibility test.  It catches
API arity/name/type/layout/include changes without needing a historical
libFuzzer runtime.  Link/start/runtime are reported as NOT_APPLICABLE after a
syntax failure and NOT_RUN when syntax succeeds; VP1 never infers those stages.
"""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve()
OUT = HERE.parents[1]
ROOT = OUT.parent
PROJECT_ROOT = ROOT / "FSE2026-harness-degradation" / "sources" / "projects"

INCLUDE_FLAGS = {
    "c-ares": ["-Iinclude", "-Isrc/lib", "-Isrc/lib/include", "-I."],
    "leptonica": ["-Isrc", "-I."],
    "libspng": ["-I.", "-Isrc", "-Ispng"],
    "meshoptimizer": ["-Isrc", "-I."],
    "wuffs": ["-I."],
}


def archive(repo: Path, revision: str, target: Path) -> None:
    git = subprocess.Popen(["git", "-C", str(repo), "archive", revision], stdout=subprocess.PIPE)
    assert git.stdout is not None
    with tarfile.open(fileobj=git.stdout, mode="r|") as handle:
        handle.extractall(target, filter="data")
    if git.wait() != 0:
        raise RuntimeError(f"git archive failed: {repo} {revision}")


def overlay(source: Path, target: Path) -> list[str]:
    paths = []
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        paths.append(relative.as_posix())
    return paths


def prepare_generated_headers(project: str, tree: Path) -> None:
    """Materialize the minimal configure-generated headers for syntax checks."""
    if project == "c-ares":
        distributed = tree / "include" / "ares_build.h.dist"
        generated = tree / "include" / "ares_build.h"
        if distributed.exists() and not generated.exists():
            shutil.copyfile(distributed, generated)
    elif project == "leptonica":
        generated = tree / "src" / "endianness.h"
        if not generated.exists():
            generated.write_text(
                "#ifndef LEPTONICA_ENDIANNESS_H\n#define LEPTONICA_ENDIANNESS_H\n"
                "#define L_LITTLE_ENDIAN\n#endif\n",
                encoding="utf-8",
            )


def compile_one(project: str, tree: Path, path: str) -> tuple[list[str], subprocess.CompletedProcess[str]]:
    suffix = Path(path).suffix.lower()
    cpp = suffix in {".cc", ".cpp", ".cxx"}
    compiler = shutil.which("g++" if cpp else "gcc")
    if not compiler:
        raise RuntimeError("host compiler missing")
    command = [compiler, "-fsyntax-only", "-fdiagnostics-color=never"]
    command += ["-std=gnu++17"] if cpp else ["-std=gnu11", "-Werror=implicit-function-declaration"]
    command += INCLUDE_FLAGS.get(project, ["-I."])
    command.append(path)
    result = subprocess.run(command, cwd=tree, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    return command, result


def main() -> None:
    destination = OUT / "results" / "build_results_three_way.csv"
    if destination.exists():
        raise SystemExit("Refusing to overwrite results/build_results.csv")
    positives = list(csv.DictReader((OUT / "data" / "verified_positive_cases.csv").open(encoding="utf-8", newline="")))
    rows: list[dict[str, object]] = []
    for index, item in enumerate(positives, 1):
        case_id, project, commit = item["case_id"], item["project"], item["commit_id"]
        final_meta = json.loads((OUT / "cases" / case_id / "metadata.json").read_text(encoding="utf-8"))
        candidate = final_meta["candidate_case"]
        parent = final_meta["parent"]
        candidate_dir = OUT / "cases" / candidate
        repo = PROJECT_ROOT / project
        with tempfile.TemporaryDirectory(prefix=f"cf-{case_id}-") as temporary:
            temporary_path = Path(temporary)
            combinations = (("S0_H0", parent, "H0"), ("S1_H0", commit, "H0"), ("S1_H1", commit, "H1"))
            for side, revision, harness_side in combinations:
                tree = temporary_path / side
                tree.mkdir()
                archive(repo, revision, tree)
                paths = overlay(candidate_dir / harness_side, tree)
                prepare_generated_headers(project, tree)
                # fuzzlib.c is an included support fragment, not an independent
                # translation unit.  Compile the actual changed fuzz targets.
                target_paths = [p for p in paths if "/fuzzlib/" not in f"/{p}"]
                if target_paths:
                    paths = target_paths
                if not paths:
                    rows.append({
                        "case_id": case_id, "project": project, "commit_id": commit,
                        "side": side, "harness_file": "", "compile_success": "NOT_APPLICABLE",
                        "exit_code": "", "command": "", "diagnostic": "no harness file",
                        "link_success": "NOT_APPLICABLE", "harness_start_success": "NOT_APPLICABLE",
                        "runtime_success": "NOT_APPLICABLE",
                    })
                    continue
                for path in paths:
                    command, result = compile_one(project, tree, path)
                    rows.append({
                        "case_id": case_id, "project": project, "commit_id": commit,
                        "side": side, "harness_file": path,
                        "compile_success": str(result.returncode == 0).lower(),
                        "exit_code": result.returncode, "command": " ".join(command),
                        "diagnostic": (result.stderr or result.stdout)[-4000:].replace("\x00", ""),
                        "link_success": "NOT_APPLICABLE" if result.returncode else "NOT_RUN",
                        "harness_start_success": "NOT_APPLICABLE" if result.returncode else "NOT_RUN",
                        "runtime_success": "NOT_APPLICABLE" if result.returncode else "NOT_RUN",
                    })
        summary = {}
        for side in ("S0_H0", "S1_H0", "S1_H1"):
            values = [r for r in rows if r["case_id"] == case_id and r["side"] == side]
            summary[side] = f"{sum(r['compile_success']=='true' for r in values)}/{len(values)}"
        print(f"{index:02d}/{len(positives)} {case_id} {project} " + " ".join(f"{k}={v}" for k, v in summary.items()), flush=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fields = ["case_id", "project", "commit_id", "side", "harness_file", "compile_success", "exit_code", "command", "diagnostic", "link_success", "harness_start_success", "runtime_success"]
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
