#!/usr/bin/env python3
"""Frozen transparent v1 candidate scoring."""
from __future__ import annotations

import re


UTILITY = re.compile(r"(?:^|_)(?:log|debug|trace|printf|format|stringify|error_message)(?:_|$)", re.I)
FUZZ_SOURCE = re.compile(r"(?:parse|decode|encode|reader|writer|stream|protocol|plist|png|mesh|ares)", re.I)
SEMANTIC_TOKENS = {
    "parse", "parser", "decode", "decoder", "encode", "encoder", "read", "reader",
    "write", "writer", "load", "save", "import", "export", "serialize", "deserialize",
    "protocol", "query", "queue", "feed", "scan", "token", "record", "filter", "mesh",
    "remesh", "optimize", "optimise", "process", "input",
}


def semantic_name(name: str) -> bool:
    # Tokenization prevents accidental matches such as read in thread.
    separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name)
    tokens = [token.lower() for token in re.split(r"[^A-Za-z0-9]+", separated) if token]
    return any(token in SEMANTIC_TOKENS for token in tokens)


def score_candidate(candidate: dict) -> dict:
    reasons = list(candidate.get("reason", []))
    components = []
    score = 0
    if candidate.get("is_new") and candidate.get("is_public"):
        components.append({"rule": "new_public_exported", "points": 3})
        reasons.append("newly_added_public_or_exported_function")
        score += 3
    if semantic_name(candidate["target"]):
        components.append({"rule": "fuzz_semantic_name", "points": 3})
        reasons.append("parser_decoder_encoder_writer_reader_or_protocol_name")
        score += 3
    if candidate.get("is_modified") and candidate.get("is_public"):
        components.append({"rule": "changed_public_api", "points": 2})
        reasons.append("modified_public_or_exported_api")
        score += 2
    if candidate.get("is_new") and candidate.get("connected_changed_caller"):
        components.append({"rule": "new_connected_changed_caller", "points": 2})
        reasons.append("new_function_connected_to_changed_caller")
        score += 2
    if candidate.get("target_type") == "non_function" or candidate.get("state_config_handler"):
        components.append({"rule": "enum_state_config", "points": 2})
        reasons.append("new_or_modified_enum_state_config_handler")
        score += 2
    if candidate.get("is_modified") and FUZZ_SOURCE.search(candidate.get("source", "")):
        components.append({"rule": "modified_fuzz_relevant_source", "points": 1})
        reasons.append("modified_function_in_fuzz_relevant_source")
        score += 1
    if candidate.get("reachable_before") == "STATIC_REACHABLE":
        components.append({"rule": "already_reachable_h0", "points": 1})
        reasons.append("modified_function_already_reachable_from_h0")
        score += 1
    if candidate.get("file_scope"):
        components.append({"rule": "static_internal_helper", "points": -2})
        reasons.append("static_or_internal_helper_penalty")
        score -= 2
    if candidate.get("test_only"):
        components.append({"rule": "test_only", "points": -2})
        reasons.append("test_only_helper_penalty")
        score -= 2
    if UTILITY.search(candidate["target"]):
        components.append({"rule": "utility_logging_formatting", "points": -2})
        reasons.append("utility_logging_or_formatting_penalty")
        score -= 2
    result = dict(candidate)
    result["reason"] = sorted(set(reasons))
    result["score_components"] = components
    result["rank_score"] = score
    return result


def rank_candidates(candidates: list[dict]) -> list[dict]:
    scored = [score_candidate(candidate) for candidate in candidates]
    scored.sort(key=lambda row: (
        -row["rank_score"],
        0 if row["target_type"] == "function" else 1,
        0 if row.get("is_public") else 1,
        row.get("source", ""), row.get("line", 0), row["target"],
    ))
    for rank, candidate in enumerate(scored, 1):
        candidate["rank"] = rank
    return scored
