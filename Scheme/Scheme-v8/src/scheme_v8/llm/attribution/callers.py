from __future__ import annotations
import re
from pathlib import Path
from scheme_v8.analysis.syntax import text
from scheme_v8.analysis.syntax import walk
from scheme_v8.llm.attribution.maintenance import _safe

def read_callers(builder, symbols, levels=2):
    """Read real macro aliases and enclosing caller bodies, not guessed aliases."""
    frontier = list(dict.fromkeys((s for s in symbols if re.fullmatch('[A-Za-z_]\\w*', s))))
    retrieved, visited = ([], set())
    max_functions = builder.config.get('diff_max_caller_functions', 48)
    for _ in range(levels):
        next_frontier = []
        for symbol in frontier:
            paths = _safe(builder, 'caller_search:' + symbol, lambda s=symbol: builder.search.files(s)) or []
            names = {symbol}
            for path in paths:
                if Path(path).suffix.lower() not in {'.h', '.hpp', '.inc'}:
                    continue
                tree = _safe(builder, 'macro_tree:' + path, lambda p=path: builder.syntax.tree(p))
                if tree is None:
                    continue
                for node in walk(tree.root_node):
                    if node.type != 'preproc_function_def':
                        continue
                    if re.search('\\b' + re.escape(symbol) + '\\b', text(node.child_by_field_name('value'))):
                        alias = text(node.child_by_field_name('name'))
                        if alias:
                            names.add(alias)
                            _safe(builder, 'macro:' + alias, lambda n=node, p=path: builder.snippet(p, n.start_point.row + 1, n.end_point.row + 1, 'verified macro route'))
            for name in sorted(names - {symbol}):
                paths += _safe(builder, 'alias_callers:' + name, lambda s=name: builder.search.files(s)) or []
            pattern = re.compile('\\b(?:' + '|'.join((re.escape(n) for n in names)) + ')\\b')
            for path in dict.fromkeys(paths):
                tree = _safe(builder, 'caller_tree:' + path, lambda p=path: builder.syntax.tree(p))
                if tree is None:
                    continue
                for node in walk(tree.root_node):
                    if node.type != 'function_definition' or not pattern.search(text(node.child_by_field_name('body'))):
                        continue
                    key = (path, node.start_point.row)
                    if key in visited:
                        continue
                    if len(visited) >= max_functions:
                        builder.issues.append('caller_function_limit')
                        return retrieved
                    visited.add(key)
                    start, end = (node.start_point.row + 1, node.end_point.row + 1)
                    complete = True
                    for line in range(start, end + 1, 300):
                        ok = _safe(builder, 'caller_body:' + path, lambda p=path, a=line, b=min(end, line + 299): builder.snippet(p, a, b, 'caller body for ' + symbol))
                        complete = complete and bool(ok)
                    head = text(node.child_by_field_name('declarator')).split('(', 1)[0]
                    found = re.findall('[A-Za-z_]\\w*', head)
                    caller = found[-1] if found else ''
                    retrieved.append({'requested': symbol, 'aliases': sorted(names - {symbol}), 'caller': caller, 'path': path, 'start': start, 'end': end, 'complete_body': complete})
                    if caller:
                        next_frontier.append(caller)
        frontier = list(dict.fromkeys(next_frontier))
    return retrieved
