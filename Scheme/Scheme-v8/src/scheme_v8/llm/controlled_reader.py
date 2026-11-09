from __future__ import annotations
import re
from scheme_v8.analysis.syntax import text
from scheme_v8.analysis.syntax import walk
from scheme_v8.util import digest
from scheme_v8.llm.whole_functions import WholeFunctionBuilder

def normalize_symbol(value):
    value = value.strip()
    match = re.match('((?:[A-Za-z_]\\w*::)*(?:operator\\s*(?:==|!=|<=|>=|<|>|\\[\\]|\\(\\))|[A-Za-z_]\\w*))', value)
    return re.sub('\\s+', '', match[1]) if match else value

class ControlledReader(WholeFunctionBuilder):

    def __init__(self, reader, config):
        if config.get('unlimited_chars', False):
            config = {**config, 'max_harness_chars': float('inf')}
        super().__init__(reader, config)
        if config.get('unlimited_chars', False):
            self.limit = float('inf')
        self.mode = config.get('function_reading', 'whole')
        if self.mode != 'whole':
            raise ValueError('This package reads whole functions only')
        self.anchor = None

    def snippet(self, path, start, end, reason, kind='source', depth=0):
        previous = self.anchor
        self.anchor = (path, start, end)
        try:
            return super().snippet(path, start, end, reason, kind, depth)
        finally:
            self.anchor = previous

    def unit(self, path, start, end, reason, kind='source', unit_kind='function', name='', depth=0):
        full_start, full_end = (start, end)
        result = super().unit(path, start, end, reason, kind, unit_kind, name, depth)
        key = digest(f'{kind}:{path}:{start}:{end}'.encode())[:20]
        if key in self.units and unit_kind in ('function', 'function_window'):
            self.units[key].update(function_start=full_start, function_end=full_end)
        return result

    def symbol(self, symbol, focus, question):
        symbol = normalize_symbol(symbol)
        leaf = symbol.rsplit('::', 1)[-1]
        if re.fullmatch('[A-Za-z_]\\w*', leaf):
            for path in self.search.files(leaf):
                try:
                    tree = self.syntax.tree(path)
                    for node in walk(tree.root_node):
                        if node.type not in ('preproc_def', 'preproc_function_def'):
                            continue
                        if text(node.child_by_field_name('name')) != leaf:
                            continue
                        kind = 'harness' if path.startswith('input/harness/') else 'source'
                        super().unit(path, node.start_point.row + 1, node.end_point.row + 1, question, kind, 'declaration', leaf, 1)
                        parent = node.parent
                        while parent is not None:
                            if parent.type in ('preproc_if', 'preproc_ifdef', 'preproc_elif', 'preproc_else'):
                                super().unit(path, parent.start_point.row + 1, parent.start_point.row + 1, 'governing preprocessor directive', kind, 'non_function_context', depth=1)
                            parent = parent.parent
                except (ValueError, OSError, RuntimeError) as exc:
                    self.issues.append('macro_definition:' + path + ':' + str(exc))
        return super().symbol(symbol, focus, question)

    def enrich_packet(self, packet):
        result = super().enrich_packet(packet)
        result['function_policy'] = 'Evidence carries its actual source extent. complete_function=true means a full body; function_window means only the stated lines. Pages continue one selected unit. Do not infer absence outside supplied ranges; request missing contracts explicitly.'
        return result
