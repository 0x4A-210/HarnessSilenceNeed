from __future__ import annotations
import re
from pathlib import Path
from scheme_v8.analysis.syntax import text
from scheme_v8.analysis.syntax import walk
from scheme_v8.util import digest
from scheme_v8.source_text import source_lines
from scheme_v8.llm.catalog import PacketBuilder as ContractBuilder
CODE = {'.c', '.h', '.cc', '.cpp', '.cxx', '.hpp', '.hxx', '.inc'}
UNITS = {'declaration', 'type_definition', 'preproc_def', 'preproc_function_def', 'enum_specifier', 'struct_specifier', 'class_specifier'}

def function_name(node):
    head = text(node.child_by_field_name('declarator'))
    operator = re.search('operator\\s*(?:==|!=|<=|>=|<|>|\\[\\]|\\(\\))', head)
    if operator:
        return re.sub('\\s+', '', operator[0])
    names = re.findall('[A-Za-z_]\\w*', head.split('(', 1)[0])
    return names[-1] if names else ''

class WholeFunctionBuilder(ContractBuilder):

    def __init__(self, reader, config):
        super().__init__(reader, config)
        self.units = {}
        self.function_nodes = {}

    def functions(self, path):
        if path not in self.function_nodes:
            self.function_nodes[path] = [n for n in walk(self.syntax.tree(path).root_node) if n.type == 'function_definition']
        return self.function_nodes[path]

    def unit(self, path, start, end, reason, kind='source', unit_kind='function', name='', depth=0):
        lines = source_lines(self.reader.index(path).decode('utf-8', errors='replace'), keepends=True)
        start, end = (max(1, start), min(end, len(lines)))
        if start > end:
            return False
        key = digest(f'{kind}:{path}:{start}:{end}'.encode())[:20]
        existing = self.units.get(key)
        if existing and existing['complete']:
            return True
        for record in self.units.values():
            if record['complete'] and record['path'] == path and (record['kind'] == kind) and (record['start'] <= start) and (record['end'] >= end):
                return True
        content = ''.join(lines[start - 1:end])
        page_lines = self.config.get('function_page_lines', 250)
        spans = [(a, min(end, a + page_lines - 1)) for a in range(start, end + 1, page_lines)]
        ids = [f'fn-{key}-{i:04d}' for i in range(len(spans))]
        record = {'unit_id': key, 'path': path, 'kind': kind, 'unit_kind': unit_kind, 'name': name, 'start': start, 'end': end, 'sha256': digest(content.encode()), 'chars': len(content), 'evidence_ids': ids, 'complete': False, 'reason': reason}
        self.units[key] = record
        if self.total_chars + len(content) + 150 * len(ids) > self.limit:
            record['pending_reason'] = 'whole_unit_packet_capacity'
            return False
        self.reader.budget.charge(path, start, end, depth)
        for i, (a, b) in enumerate(spans):
            value, _ = self.reader.snippet(path, a, b, reason, depth)
            self.add(ids[i], path, value, kind, start=a, end=b, unit_id=key, part=i, unit_start=start, unit_end=end, unit_kind=unit_kind, complete_function=unit_kind == 'function', complete_file=start == 1 and end == len(lines))
        record['complete'] = True
        record.pop('pending_reason', None)
        return True

    def snippet(self, path, start, end, reason, kind='source', depth=0):
        lines = source_lines(self.reader.index(path).decode('utf-8', errors='replace'))
        start, end = (max(1, start), min(end, len(lines)))
        if start > end:
            return False
        if kind == 'harness' or Path(path).suffix.lower() not in CODE or (start == 1 and end == len(lines)):
            return self.unit(path, 1, len(lines), reason, kind, 'file', depth=depth)
        functions = [n for n in self.functions(path) if n.start_point.row + 1 <= end and n.end_point.row + 1 >= start]
        results = []
        for node in functions:
            results.append(self.unit(path, node.start_point.row + 1, node.end_point.row + 1, reason, kind, 'function', function_name(node), depth))
        for node in walk(self.syntax.tree(path).root_node):
            if node.type not in UNITS or node.end_point.row + 1 < start or node.start_point.row + 1 > end:
                continue
            parent, inside_function = (node.parent, False)
            while parent is not None:
                if parent.type == 'function_definition':
                    inside_function = True
                    break
                parent = parent.parent
            if inside_function:
                continue
            if any((n.start_byte >= node.start_byte and n.end_byte <= node.end_byte for n in functions)):
                continue
            results.append(self.unit(path, node.start_point.row + 1, node.end_point.row + 1, reason, kind, 'declaration', depth=depth))
        if not results:
            return self.unit(path, start, end, reason, kind, 'non_function_context', depth=depth)
        return all(results)

    def symbol(self, symbol, focus, question):
        symbol = re.sub('\\s+', '', symbol)
        leaf = symbol.rsplit('::', 1)[-1]
        if not re.fullmatch('[A-Za-z_]\\w*|operator(?:==|!=|<=|>=|<|>|\\[\\]|\\(\\))', leaf):
            raise ValueError('unsupported_function_symbol')
        query = 'operator' if leaf.startswith('operator') else leaf
        companions = [p for p in self.reader.case.manifest['files'] if p.startswith('input/harness/') and Path(p).suffix.lower() in CODE]
        paths = list(dict.fromkeys(companions + self.search.files(query)))
        matches = []
        for path in paths:
            try:
                for node in self.functions(path):
                    if function_name(node) != leaf:
                        continue
                    qualified = text(node.child_by_field_name('declarator'))
                    parent = node.parent
                    while parent is not None:
                        if parent.type in {'class_specifier', 'struct_specifier', 'namespace_definition'}:
                            qualified += ' ' + text(parent.child_by_field_name('name'))
                        parent = parent.parent
                    qualifier = symbol.rsplit('::', 1)[0] if '::' in symbol else ''
                    matches.append(((bool(qualifier and qualifier not in qualified), not self.production(path), path), path, node))
            except (ValueError, OSError, RuntimeError) as exc:
                self.issues.append('whole_symbol:' + path + ':' + str(exc))
        for _, path, node in sorted(matches, key=lambda x: x[0])[:self.config.get('whole_symbol_definitions', 8)]:
            kind = 'harness' if path.startswith('input/harness/') else 'source'
            self.unit(path, node.start_point.row + 1, node.end_point.row + 1, question, kind, 'function', function_name(node), 1)
        pattern = re.compile('\\b' + re.escape(query) + '\\b')
        for path in paths[:self.config.get('whole_declaration_files', 6)]:
            try:
                tree = self.syntax.tree(path)
                count = 0
                for node in walk(tree.root_node):
                    if node.type not in UNITS or not pattern.search(text(node)):
                        continue
                    parent = node.parent
                    nested = False
                    while parent:
                        if parent.type in ('function_definition', 'declaration', 'type_definition'):
                            nested = True
                            break
                        parent = parent.parent
                    if nested or any((n.start_byte >= node.start_byte and n.end_byte <= node.end_byte for n in self.functions(path))):
                        continue
                    kind = 'harness' if path.startswith('input/harness/') else 'source'
                    self.unit(path, node.start_point.row + 1, node.end_point.row + 1, question, kind, 'declaration', leaf, 1)
                    count += 1
                    if count >= 6:
                        break
            except (ValueError, OSError, RuntimeError) as exc:
                self.issues.append('whole_declaration:' + path + ':' + str(exc))

    def enrich_packet(self, packet):
        records = list(self.units.values())
        return {**packet, 'evidence': list(self.blocks.values()), 'whole_units': records, 'pending_units': [r for r in records if not r['complete']], 'issues': self.issues, 'function_policy': 'Selected functions are complete contiguous bodies, paged without head/tail clipping; pending units are not proof.'}

def unit_errors(packet):
    blocks = {e['evidence_id']: e for e in packet['evidence']}
    errors = []
    for record in packet.get('whole_units', []):
        try:
            if not record['complete']:
                raise ValueError('pending')
            value = ''.join((blocks[eid]['text'] for eid in record['evidence_ids']))
            if len(value) != record['chars'] or digest(value.encode()) != record['sha256']:
                raise ValueError('content')
        except (KeyError, ValueError):
            errors.append('incomplete_function_unit:' + record['unit_id'])
    return errors
