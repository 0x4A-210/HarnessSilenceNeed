from __future__ import annotations
import re
from pathlib import Path
from scheme_v8.analysis.syntax import text
from scheme_v8.analysis.syntax import walk
from scheme_v8.llm.schema import BOOL
from scheme_v8.llm.schema import QUOTES
from scheme_v8.llm.schema import TEXT
from scheme_v8.llm.schema import arr
from scheme_v8.llm.schema import obj
from scheme_v8.llm.schema import validate_schema
from scheme_v8.llm.verify import verify_quotes
from scheme_v8.llm.diff_pages import RULES as DIFF_RULES
from scheme_v8.llm.diff_pages import coverage_errors
from scheme_v8.llm.attribution.build_context import _build_paths
from scheme_v8.llm.attribution.paths import _resolve_path
from scheme_v8.llm.attribution.scope import SCHEMA as SCOPE_SCHEMA
from scheme_v8.llm.attribution.scope import verify_closure
BLOCKER = obj({'id': TEXT, 'change_ids': arr(TEXT), 'kind': {'type': 'string', 'enum': ['build', 'configuration', 'input', 'lifecycle', 'state', 'check', 'call']}, 'necessary': BOOL, 'established': BOOL, 'requirement': TEXT, 'target_route': TEXT, 'failure_condition': TEXT, 'alternative_paths': TEXT, 'source_evidence': QUOTES, 'harness_evidence': QUOTES, 'missing_information': arr(TEXT)})
SCHEMA = obj({'scope': SCOPE_SCHEMA, 'blockers': arr(BLOCKER), 'assumptions': arr(TEXT), 'requested_symbols': arr(TEXT), 'requested_paths': arr(TEXT)})
PROMPT = DIFF_RULES + '\n' + """Review the OLD fuzz target against the supplied changed source.
Apply the DECISION SPECIFICATION supplied with these instructions. Return both
necessary blockers and an affirmative sufficiency assessment of the supplied scope.
Do not assume an earlier satisfied classification is correct; it is deliberately
not supplied.

Trace control flow from the entry to each changed behavior, including arguments,
guards, defaults and cleanup, and check the four target foundations (build, input,
lifecycle, control_flow) because a preexisting foundation failure counts (J2).

Blockers: report a blocker only when J1 holds; give requirement, target_route,
failure_condition and alternative_paths concretely, with source and harness
evidence. Missing evidence alone is never a blocker (J5). One established blocker
suffices even if other change groups are unresolved (J3). A blocker without
change_ids must correspond to a foundation assessed as blocked with evidence.

Scope assessment (J4): assess exactly every selected change ID as covered,
not_target_relevant, blocked or unknown; covered/not_target_relevant need source
AND harness evidence. Assess each foundation as pass/not_applicable/blocked/unknown;
pass and not_applicable require a specific reason and exact evidence.
all_relevant_changes_assessed is true only if the whole supplied scope is resolved.
No missing_information may remain for a negative. prior_alarm_resolution can be
empty for this fresh review.

If decisive facts remain unavailable, request exact symbol names (including simple
method names) and repository-relative file paths (E3). Output only JSON conforming
to the schema."""
COMMON = {'if', 'for', 'while', 'switch', 'sizeof', 'return', 'assert', 'abort', 'malloc', 'calloc', 'free', 'realloc', 'memcpy', 'memset', 'memcmp', 'strlen', 'printf', 'fprintf', 'LLVMFuzzerTestOneInput', 'LLVMFuzzerInitialize'}
CALL = re.compile('\\b([A-Za-z_][A-Za-z0-9_]{1,100})\\s*\\(')

def verify_balanced(answer, packet):
    validate_schema(answer, SCHEMA)
    scope = verify_closure(answer['scope'], packet)
    diff_errors = coverage_errors(packet)
    if diff_errors or packet['omitted_change_group_count'] or packet.get('truncated_change_ids') or (not packet['harness_complete_files']) or (not all(packet['harness_complete_files'].values())):
        scope.update(verdict='unknown', coverage_complete=False)
        scope['errors'].append('incomplete_input_scope')
        scope['errors'].extend(diff_errors)
    blocks = {e['evidence_id']: e for e in packet['evidence']}
    accepted, rejected = ([], [])
    seen = set()
    for b in answer['blockers']:
        errors = []
        if not b['id'] or b['id'] in seen:
            errors.append('invalid_blocker_id')
        seen.add(b['id'])
        if b['change_ids']:
            if not set(b['change_ids']).issubset(packet['selected_change_ids']):
                errors.append('missing_change_anchor')
        else:
            foundations = {'build': ('build',), 'input': ('input',), 'call': ('control_flow',), 'configuration': ('build', 'control_flow'), 'lifecycle': ('lifecycle', 'control_flow'), 'state': ('lifecycle', 'control_flow'), 'check': ('control_flow',)}[b['kind']]
            grounded = any((answer['scope']['foundation'][name]['status'] == 'blocked' and verify_quotes(answer['scope']['foundation'][name]['evidence'], blocks)[0] for name in foundations))
            if not grounded or not packet['harness_complete_files'] or (not all(packet['harness_complete_files'].values())):
                errors.append('missing_change_anchor')
        if not b['necessary'] or not b['established'] or b['missing_information']:
            errors.append('unproven_or_optional_blocker')
        for key in ('requirement', 'target_route', 'failure_condition', 'alternative_paths'):
            if len(b[key].strip()) < 24:
                errors.append('insufficient_' + key)
        for key, kinds in (('source_evidence', {'source', 'diff', 'before_source', 'after_source'}), ('harness_evidence', {'harness'})):
            valid, found_kinds, issues = verify_quotes(b[key], blocks, kinds)
            if not valid:
                errors.extend((key + ':' + issue for issue in issues))
            if key == 'source_evidence' and (not found_kinds.intersection({'source', 'diff', 'after_source'})):
                errors.append('no_current_source_contract')
        (rejected if errors else accepted).append({**b, 'errors': errors})
    uncertain_blocker = any((b['necessary'] for b in rejected))
    verdict = 'needs_update' if accepted else 'satisfied_in_scope' if scope['coverage_complete'] and (not uncertain_blocker) else 'unknown'
    return {'verdict': verdict, 'scope': scope, 'accepted': accepted, 'rejected': rejected, 'assumptions': answer['assumptions'], 'semantic_proof': False}

def _safe(builder, label, fn):
    try:
        return fn()
    except (ValueError, OSError, RuntimeError) as exc:
        builder.issues.append(label + ':' + str(exc))
        return None

def _read_path(builder, path, reason, max_lines=800):
    lines = builder.reader.index(path).decode('utf-8', errors='replace').splitlines()
    kind = 'harness' if path.startswith('input/harness/') or path == builder.reader.case.build_script else 'source'
    return builder.snippet(path, 1, min(len(lines), max_lines), reason, kind, 1)

def _symbols(builder, symbols, max_callees=8):
    """Read requested definitions and one bounded layer of their callees."""
    names = list(dict.fromkeys((s for s in symbols if re.fullmatch('[A-Za-z_]\\w{0,100}', s) and s not in COMMON)))
    for symbol in names:
        _safe(builder, 'symbol:' + symbol, lambda s=symbol: builder.symbol(s, 'return_contract', 'target prerequisite or missing behavior'))
    callees = []
    visited = set()
    for e in list(builder.blocks.values()):
        if e['kind'] not in ('source', 'harness') or not e['path'].startswith('input/'):
            continue
        if Path(e['path']).suffix.lower() not in {'.c', '.h', '.cpp', '.cc', '.hpp', '.cxx', '.inc'}:
            continue
        if e['path'] in visited:
            continue
        visited.add(e['path'])
        tree = _safe(builder, 'tree', lambda p=e['path']: builder.syntax.tree(p))
        if tree is None:
            continue
        for node in walk(tree.root_node):
            if node.type != 'function_definition':
                continue
            head = text(node.child_by_field_name('declarator')).split('(', 1)[0]
            if not any((re.search('\\b' + re.escape(s) + '\\b', head) for s in names)):
                continue
            for call in CALL.findall(text(node.child_by_field_name('body'))):
                if call not in names and call not in COMMON and (call not in callees):
                    callees.append(call)
    for symbol in callees[:max_callees]:
        _safe(builder, 'callee:' + symbol, lambda s=symbol: builder.symbol(s, 'return_contract', 'one-hop target contract'))
    return (names, callees[:max_callees])
