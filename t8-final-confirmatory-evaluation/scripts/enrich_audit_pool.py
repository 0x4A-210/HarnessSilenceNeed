#!/usr/bin/env python3
"""Add diff-only features to the pre-label audit pool."""
from __future__ import annotations

import json
import re
from collections import Counter

from common import ROOT, git, is_harness, read_csv, sha256_file, write_csv, write_json


IDENT = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]{2,}\b")
CALL = re.compile(r"([A-Za-z_~][A-Za-z0-9_:~]*)\s*\(")
CONTROL = {"if", "for", "while", "switch", "return", "sizeof", "defined", "catch"}
STOP = CONTROL | {"const", "static", "struct", "class", "void", "int", "char", "bool", "true", "false",
                  "size", "data", "input", "output", "include", "define", "nullptr", "NULL", "auto"}
COMMENTISH = re.compile(r"^(?:\s*|[/*]+|\*|//|#\s*(?:include|pragma)|[{};,]+)$")


def names(text: str) -> set[str]:
    return {name for name in IDENT.findall(text) if name not in STOP and len(name) >= 4}


def function_names(text: str) -> set[str]:
    return {match.group(1) for match in CALL.finditer(text)
            if match.group(1).split("::")[-1] not in CONTROL}


def analyze(row: dict[str, str]) -> dict:
    project, parent, commit = row["project"], row["parent"], row["commit"]
    production = row["production_paths"].split(";") if row["production_paths"] else []
    changed_harness = row["harness_paths_changed"].split(";") if row["harness_paths_changed"] else []
    patch = git(project, "diff", "--no-ext-diff", "--no-renames", "--unified=1",
                parent, commit, "--", *(production + changed_harness)).stdout
    group = ""; prod_add=[]; prod_del=[]; har_add=[]; har_del=[]; contexts=[]
    for line in patch.splitlines():
        if line.startswith("diff --git a/"):
            match = re.match(r"diff --git a/(.*?) b/(.*)", line)
            path = match.group(2) if match else ""
            group = "harness" if path in changed_harness else "production" if path in production else ""
        elif line.startswith("@@") and group == "production":
            contexts.append(line.split("@@", 2)[-1].strip())
        elif line.startswith("+") and not line.startswith("+++"):
            (har_add if group == "harness" else prod_add if group == "production" else []).append(line[1:])
        elif line.startswith("-") and not line.startswith("---"):
            (har_del if group == "harness" else prod_del if group == "production" else []).append(line[1:])
    prod_add_text="\n".join(prod_add); prod_del_text="\n".join(prod_del)
    har_add_text="\n".join(har_add); har_del_text="\n".join(har_del)
    context_functions = sorted(function_names("\n".join(contexts)))
    added_function_like = sorted(function_names(prod_add_text))
    harness_added_calls = sorted(function_names(har_add_text))
    linked_functions = sorted({x for x in context_functions + added_function_like
                               if x.split("::")[-1] in {y.split("::")[-1] for y in harness_added_calls}})
    shared = sorted(names(prod_add_text) & names(har_add_text))
    tree_paths = git(project, "ls-tree", "-r", "--name-only", parent).stdout.splitlines()
    h0_paths = sorted(path for path in tree_paths if is_harness(path))
    substantive = [line for line in prod_add + prod_del if not COMMENTISH.match(line.strip())]
    result = dict(row)
    result.update({
        "production_added": len(prod_add), "production_deleted": len(prod_del),
        "harness_added": len(har_add), "harness_deleted": len(har_del),
        "substantive_changed_lines": len(substantive), "h0_harness_count": len(h0_paths),
        "h0_harness_paths": ";".join(h0_paths),
        "hunk_function_contexts": json.dumps(context_functions, separators=(",", ":")),
        "added_function_like": json.dumps(added_function_like[:80], separators=(",", ":")),
        "harness_added_calls": json.dumps(harness_added_calls[:120], separators=(",", ":")),
        "linked_function_candidates": json.dumps(linked_functions[:80], separators=(",", ":")),
        "shared_added_identifiers": json.dumps(shared[:120], separators=(",", ":")),
        "shared_identifier_count": len(shared), "linked_function_count": len(linked_functions),
        "eligible_h0_exists": bool(h0_paths),
    })
    return result


def main() -> None:
    source = read_csv(ROOT / "mining" / "audit_pool.csv")
    selected=[]
    per_project_source=Counter()
    for row in source:
        if row["candidate_class"] == "COEVOLUTION":
            selected.append(row)
        elif per_project_source[row["project"]] < 80:
            selected.append(row); per_project_source[row["project"]] += 1
    enriched=[]
    for index,row in enumerate(selected,1):
        enriched.append(analyze(row))
        if index % 100 == 0: print(f"enriched {index}/{len(selected)}",flush=True)
    fields=list(enriched[0])
    write_csv(ROOT / "mining" / "enriched_audit_pool.csv", enriched, fields)
    write_json(ROOT / "mining" / "enrichment_manifest.json", {
        "input_count":len(source), "enriched_count":len(enriched),
        "coevolution_count":sum(x["candidate_class"]=="COEVOLUTION" for x in enriched),
        "source_only_count":sum(x["candidate_class"]=="SOURCE_ONLY" for x in enriched),
        "uses_ground_truth":False,"uses_predictions":False,
        "output_sha256":sha256_file(ROOT/"mining"/"enriched_audit_pool.csv"),
    })


if __name__ == "__main__":
    main()
