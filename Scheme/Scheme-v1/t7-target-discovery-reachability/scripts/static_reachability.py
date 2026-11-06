#!/usr/bin/env python3
"""Before/after delta attribution for an automatically selected symbol."""
from __future__ import annotations


def attribute(before: str, after: str, *, is_new: bool, exposure_changed: bool) -> dict:
    if after == "NOT_PRESENT":
        return {"delta": "NONE", "candidate_maintenance": "NO",
                "attribution_reason": "candidate absent after commit"}
    if after == "UNKNOWN" or (not is_new and before == "UNKNOWN"):
        return {"delta": "UNKNOWN", "candidate_maintenance": "ABSTAIN",
                "attribution_reason": "indirect/static uncertainty"}
    if is_new or before == "NOT_PRESENT":
        if after == "STATIC_UNREACHABLE":
            return {"delta": "NEW", "candidate_maintenance": "YES",
                    "attribution_reason": "new target absent before and unreachable after"}
        if after == "STATIC_REACHABLE":
            return {"delta": "NONE", "candidate_maintenance": "NO",
                    "attribution_reason": "new target reached by unchanged H0"}
    if before == "STATIC_REACHABLE" and after == "STATIC_UNREACHABLE":
        return {"delta": "AGGRAVATED", "candidate_maintenance": "YES",
                "attribution_reason": "reachable-before to unreachable-after"}
    if before == "STATIC_UNREACHABLE" and after == "STATIC_UNREACHABLE":
        if exposure_changed:
            return {"delta": "AGGRAVATED", "candidate_maintenance": "YES",
                    "attribution_reason": "existing target remains unreachable and exposure signature changed"}
        return {"delta": "UNCHANGED", "candidate_maintenance": "NO",
                "attribution_reason": "same target unreachable before and after without exposure change"}
    if before == "STATIC_REACHABLE" and after == "STATIC_REACHABLE":
        return {"delta": "NONE", "candidate_maintenance": "NO",
                "attribution_reason": "same target reachable before and after"}
    return {"delta": "UNKNOWN", "candidate_maintenance": "ABSTAIN",
            "attribution_reason": "unhandled or uncertain reachability transition"}


def aggregate(candidates: list[dict], top_k: int) -> dict:
    selected = candidates[:top_k]
    functions = [item for item in selected if item["target_type"] == "function"]
    if any(item.get("candidate_maintenance") == "YES" for item in functions):
        decision = "YES"
    elif not functions:
        decision = "NOT_APPLICABLE"
    elif any(item.get("candidate_maintenance") == "ABSTAIN" for item in functions):
        decision = "ABSTAIN"
    else:
        decision = "NO"
    return {
        "top_k": top_k,
        "selected_targets": [item["target"] for item in selected],
        "function_candidate_count": len(functions),
        "maintenance_needed": decision,
        "applicable": decision in {"YES", "NO"},
    }
