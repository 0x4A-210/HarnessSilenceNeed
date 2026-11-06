#!/usr/bin/env python3
"""Universal-Ctags catalogue and conservative source-level call graph."""
from __future__ import annotations

import json
import re
import subprocess
from collections import deque
from pathlib import Path

from common import normalize_symbol


FUNCTION_KINDS = {"function", "method"}
DECLARATION_KINDS = {"prototype", "function", "method"}
NONFUNCTION_KINDS = {"macro", "enumerator", "enum", "member"}
CALL_RE = re.compile(r"(?<![\w])([A-Za-z_]\w*(?:::\w+)*)\s*\(")
COMMENT_RE = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)
STRING_RE = re.compile(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'')
CALL_KEYWORDS = {
    "if", "for", "while", "switch", "return", "sizeof", "alignof", "decltype",
    "static_cast", "reinterpret_cast", "const_cast", "dynamic_cast", "defined",
    "assert", "offsetof", "do", "catch", "new", "delete",
}


def ctags_version() -> str:
    completed = subprocess.run(["ctags", "--version"], check=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return completed.stdout.splitlines()[0]


def _canonical(tag: dict) -> str:
    name = tag.get("name", "")
    scope = tag.get("scope", "")
    if scope and tag.get("scopeKind", "") in {"class", "struct", "namespace", "union"}:
        return normalize_symbol(scope + "::" + name)
    return normalize_symbol(name)


def catalogue(root: Path, relative_paths: list[str], harness_paths: set[str]) -> dict:
    files = [str(root / path) for path in relative_paths if (root / path).is_file()]
    if not files:
        return {"definitions": [], "tags": [], "parse_errors": []}
    command = [
        "ctags", "--sort=no", "--output-format=json", "--fields=+neKSt",
        "--extras=-q", "--languages=C,C++", "-f", "-", *files,
    ]
    completed = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    tags = []
    errors = []
    for line in completed.stdout.splitlines():
        try:
            tag = json.loads(line)
        except json.JSONDecodeError:
            errors.append(line[:300])
            continue
        if tag.get("_type") != "tag":
            continue
        try:
            path = str(Path(tag["path"]).resolve().relative_to(root.resolve()))
        except (KeyError, ValueError):
            continue
        kind = str(tag.get("kind", ""))
        line_no = int(tag.get("line", 0) or 0)
        end = int(tag.get("end", line_no) or line_no)
        item = {
            "name": normalize_symbol(str(tag.get("name", ""))),
            "canonical": _canonical(tag),
            "kind": kind,
            "path": path,
            "line": line_no,
            "end": max(line_no, end),
            "signature": str(tag.get("signature", "")),
            "scope": str(tag.get("scope", "")),
            "scope_kind": str(tag.get("scopeKind", "")),
            "file_scope": bool(tag.get("file", False)),
            "is_harness": path in harness_paths,
        }
        tags.append(item)
    definitions = []
    seen = set()
    for tag in tags:
        # Definitions normally carry an end range. A one-line definition is retained.
        if tag["kind"] not in FUNCTION_KINDS or tag["line"] <= 0:
            continue
        key = (tag["canonical"], tag["signature"], tag["path"], tag["line"])
        if key in seen:
            continue
        seen.add(key)
        node = dict(tag)
        node["id"] = f'{tag["canonical"]}|{tag["signature"]}|{tag["path"]}:{tag["line"]}'
        definitions.append(node)
    return {"definitions": definitions, "tags": tags, "parse_errors": errors,
            "ctags_exit_code": completed.returncode,
            "ctags_stderr": completed.stderr[-2000:]}


def _body(root: Path, node: dict) -> str:
    try:
        lines = (root / node["path"]).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(lines[max(0, node["line"] - 1):node["end"]])


def build_graph(root: Path, definitions: list[dict]) -> dict:
    by_base: dict[str, list[str]] = {}
    nodes = {node["id"]: node for node in definitions}
    bodies = {}
    for node in definitions:
        by_base.setdefault(node["name"].split("::")[-1], []).append(node["id"])
        bodies[node["id"]] = _body(root, node)
    edges: dict[str, list[str]] = {}
    unresolved: dict[str, list[str]] = {}
    call_tokens: dict[str, list[str]] = {}
    for node_id, raw_body in bodies.items():
        clean = COMMENT_RE.sub(" ", STRING_RE.sub(" ", raw_body))
        calls = sorted(set(normalize_symbol(match.group(1)).split("::")[-1]
                           for match in CALL_RE.finditer(clean)))
        # Drop the definition's own first token only if there is no recursive call elsewhere;
        # retaining it is harmless for reachability and avoids syntax-specific parsing.
        call_tokens[node_id] = calls
        targets = set()
        missing = []
        for call in calls:
            if call in CALL_KEYWORDS:
                continue
            resolved = by_base.get(call, [])
            if resolved:
                targets.update(resolved)
            else:
                missing.append(call)
        edges[node_id] = sorted(targets)
        unresolved[node_id] = sorted(set(missing))
    entry = sorted(node["id"] for node in definitions
                   if node["is_harness"] and node["name"] == "LLVMFuzzerTestOneInput")
    reachable = set(entry)
    predecessor: dict[str, str] = {}
    queue = deque(entry)
    while queue:
        parent = queue.popleft()
        for child in edges.get(parent, []):
            if child not in reachable:
                reachable.add(child)
                predecessor[child] = parent
                queue.append(child)
    return {
        "nodes": nodes,
        "edges": edges,
        "unresolved": unresolved,
        "call_tokens": call_tokens,
        "bodies": bodies,
        "entry_nodes": entry,
        "reachable_nodes": sorted(reachable),
        "predecessor": predecessor,
    }


def chain_for(graph: dict, node_id: str) -> list[str]:
    if node_id not in set(graph["reachable_nodes"]):
        return []
    chain = [node_id]
    while chain[-1] in graph["predecessor"]:
        chain.append(graph["predecessor"][chain[-1]])
    chain.reverse()
    return [graph["nodes"][item]["canonical"] for item in chain]


def reachability_for_symbol(graph: dict, symbol: str) -> dict:
    wanted = normalize_symbol(symbol)
    matching = [node_id for node_id, node in graph["nodes"].items()
                if node["canonical"] == wanted or node["canonical"].endswith("::" + wanted)
                or wanted.endswith("::" + node["canonical"])]
    reachable_set = set(graph["reachable_nodes"])
    direct = [node_id for node_id in matching if node_id in reachable_set]
    unresolved = sorted(set(call for node_id in reachable_set for call in graph["unresolved"].get(node_id, [])))
    if direct:
        node_id = sorted(direct)[0]
        return {"status": "STATIC_REACHABLE", "path": chain_for(graph, node_id),
                "matching_nodes": matching, "unresolved_indirect_calls": unresolved}
    if not matching:
        return {"status": "NOT_PRESENT", "path": [], "matching_nodes": [],
                "unresolved_indirect_calls": unresolved}
    base = wanted.split("::")[-1]
    indirect_evidence = []
    address_pattern = re.compile(r"(?:&\s*)?\b" + re.escape(base) + r"\b(?!\s*\()")
    for node_id in reachable_set:
        if address_pattern.search(COMMENT_RE.sub(" ", STRING_RE.sub(" ", graph["bodies"].get(node_id, "")))):
            indirect_evidence.append(graph["nodes"][node_id]["canonical"])
    if indirect_evidence:
        return {"status": "UNKNOWN", "path": [], "matching_nodes": matching,
                "indirect_evidence_callers": sorted(set(indirect_evidence)),
                "unresolved_indirect_calls": unresolved}
    return {"status": "STATIC_UNREACHABLE", "path": [], "matching_nodes": matching,
            "unresolved_indirect_calls": unresolved}
