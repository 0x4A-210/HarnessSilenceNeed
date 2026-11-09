"""Two obligation classes (D4/D5 of docs/判定规格.md) and their gate checks.

The prompt text is rendered from spec.py; this module adds the class-specific
structural checks on the gate answer.
"""
from copy import deepcopy

from ..schema import TEXT, obj
from .necessity_proof import GATE_SCHEMA as PROOF_SCHEMA, verify_gate as verify_proof
from .spec import POLICY as SPEC_POLICY, render


POLICY = SPEC_POLICY

GATE_SCHEMA = deepcopy(PROOF_SCHEMA)
GATE_SCHEMA["properties"].update({
    "obligation_class": {"type": "string", "enum": [
        "execution_compatibility", "target_coverage", "unknown"]},
    "scope_basis": {"type": "string", "enum": [
        "target_api_or_format_contract", "target_state_contract", "target_execution_contract",
        "unrelated_library_capability", "unknown"]},
    "trigger_basis": {"type": "string", "enum": [
        "current_target_execution", "supported_behavior_blocked_by_target",
        "impossible_library_state", "unknown"]},
    "coverage_witness": obj({"supported_behavior": TEXT, "required_setup": TEXT,
        "actual_target_setup": TEXT, "blocked_behavior": TEXT, "equivalent_routes": TEXT}),
})
GATE_SCHEMA["properties"]["effect"]["enum"].append("blocked_target_coverage")
GATE_SCHEMA["required"] = list(GATE_SCHEMA["properties"])

GATE_HEADER = """Independently audit ONLY the supplied frozen obligation.
""" + render('PROT-HYP', 'E1')
GATE_PROTOCOL = """
Return obligation_class (execution_compatibility per D4, target_coverage per D5),
scope_basis, trigger_basis and the five checks of J1, each with status
established/refuted/unknown, a specific reason and exact evidence:
scope_contract (J1a, D2); feasible_trigger (J1b): for execution compatibility a
finite actual target execution, for target coverage the changed code together
with the build, setup or input framing that would execute it and that the target
cannot produce; observable_consequence (J1c);
alternatives_ruled_out (J1d, D8), including counterevidence supplied with the
candidate; identity_preserved (J1e; for timing also T1).

Use effect blocked_target_coverage only for target_coverage. For target_coverage
fill every coverage_witness field; for the other class use empty strings. These
fields do not replace the citations of each check.

decision=keep requires all five checks established with source and harness
evidence, a finite_witness and no decisive missing fact. decision=dismiss requires
a grounded refutation or equivalent route (J6). Otherwise return uncertain and
request the missing facts (E3). For maintenance, unresolved timing does not
invalidate a currently established obligation (J2).
"""
GATE_PROMPT = GATE_HEADER + POLICY + GATE_PROTOCOL


def ledger_rules(temporal):
    comparison = ("Compare the same frozen behavior on both source versions."
                  if temporal else
                  "Judge the current source against the old harness. Do not require occurrence timing or before-side proof for maintenance.")
    return """
This request may join grounded facts extracted from separate complete-function
reads. All cited original text is supplied again. Validate facts and
counterevidence. A catalog entry alone is not evidence. Request only decisive
missing facts. Context-only continuations cannot certify global scope.
If focus_candidate is present, assess precisely that frozen operation; do not
substitute other blockers. If its change_ids are empty, a current foundational
blocker still needs the corresponding grounded blocked foundation assessment.
""" + comparison


def verify_gate(raw, store, request, candidate_id):
    # Reuse all common grounding, identity and five-premise checks. Only the
    # class-specific coverage effect is translated to the existing proof kind.
    normalized = deepcopy(raw)
    if normalized["effect"] == "blocked_target_coverage":
        normalized["effect"] = "lost_supported_behavior"
    result = verify_proof(normalized, store, request, candidate_id)
    result["answer"]["effect"] = raw["effect"]
    issues = []
    if result["decision"] == "keep":
        if raw["obligation_class"] == "target_coverage":
            if raw["scope_basis"] not in ("target_api_or_format_contract", "target_state_contract"):
                issues.append("coverage_has_no_target_surface_contract")
            if raw["trigger_basis"] not in ("supported_behavior_blocked_by_target", "current_target_execution"):
                issues.append("coverage_has_no_supported_trigger")
            if raw["effect"] not in ("blocked_target_coverage", "lost_supported_behavior"):
                issues.append("coverage_effect_not_established")
            if not all(v.strip() for v in raw["coverage_witness"].values()):
                issues.append("coverage_witness_incomplete")
        elif raw["obligation_class"] == "execution_compatibility":
            if raw["trigger_basis"] != "current_target_execution":
                issues.append("compatibility_requires_actual_target_trigger")
            if raw["scope_basis"] not in ("target_execution_contract", "target_api_or_format_contract", "target_state_contract"):
                issues.append("compatibility_outside_target_contract")
            if raw["effect"] == "blocked_target_coverage":
                issues.append("coverage_effect_requires_coverage_class")
        else:
            issues.append("obligation_class_unresolved")
    if issues:
        result["decision"] = "uncertain"
        result["errors"].extend(issues)
    result["obligation_class"] = raw["obligation_class"]
    return result


def focused_schema(schema, temporal):
    """The model evaluates one object; Python owns its immutable identifiers."""
    properties = deepcopy(schema["properties"])
    array_key = "claims" if temporal else "blockers"
    item = properties.pop(array_key)["items"]
    for key in (("claim_id" if temporal else "id"), "change_ids"):
        item["properties"].pop(key)
        item["required"].remove(key)
    properties["assessment"] = item
    return obj(properties)


def bind_assessment(raw, candidate, temporal):
    bound = deepcopy(raw)
    item = bound.pop("assessment")
    id_field = "claim_id" if temporal else "id"
    item[id_field] = candidate[id_field]
    item["change_ids"] = list(candidate["change_ids"])
    bound["claims" if temporal else "blockers"] = [item]
    return bound
