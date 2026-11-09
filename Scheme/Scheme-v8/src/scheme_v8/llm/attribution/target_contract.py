from __future__ import annotations
import re
from scheme_v8.analysis.syntax import text
from scheme_v8.analysis.syntax import walk
from scheme_v8.llm.schema import TEXT
from scheme_v8.llm.schema import obj
from scheme_v8.llm.attribution.maintenance import CALL
from scheme_v8.llm.attribution.maintenance import COMMON
from scheme_v8.llm.attribution.maintenance import PROMPT
from scheme_v8.llm.attribution.necessity import DECISION_SCHEMA
from scheme_v8.llm.attribution.spec import render
IMPACT_SCHEMA = obj({**DECISION_SCHEMA['properties'], 'effect': {'type': 'string', 'enum': ['invalid_execution', 'invalid_existing_assertion', 'lost_supported_behavior', 'internal_coverage_only', 'speculative', 'unclear']}, 'finite_witness': TEXT})
IMPACT_PROMPT = 'Independently verify the proposed maintenance blockers using only the packet.\n' + render('E1', 'J1', 'J3', 'J5', 'D7', 'D8', 'D6', 'E2')
REPAIR_PROMPT = PROMPT + '\n' + render('PROT-RECONCILE')

def primary_calls(builder):
    calls = []
    for path in builder.reader.case.harness_files:
        for node in walk(builder.syntax.tree(path).root_node):
            if node.type != 'function_definition':
                continue
            if 'LLVMFuzzerTestOneInput' not in text(node.child_by_field_name('declarator')):
                continue
            calls.extend((c for c in CALL.findall(text(node.child_by_field_name('body'))) if c not in COMMON))
    # Entry calls in source order; no name-based priority.
    return list(dict.fromkeys(calls))
