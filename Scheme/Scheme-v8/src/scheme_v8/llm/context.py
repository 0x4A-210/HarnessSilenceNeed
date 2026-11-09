from __future__ import annotations
from collections import Counter
from pathlib import Path
from scheme_v8.analysis.changes import parse_diff
from scheme_v8.analysis.syntax import Syntax
from scheme_v8.context.search import Search
from scheme_v8.util import digest

class PacketBuilder:
    """Only this trusted layer reads source. The model has no file tools."""

    def __init__(self, reader, config):
        self.reader, self.config = (reader, config)
        self.syntax = Syntax(reader)
        self.search = Search(reader)
        self.blocks = {}
        self.issues = []
        self.retrieval = []
        self.groups = parse_diff(reader.read_diff())
        self.selected_groups = []
        self.harness_complete = {}
        self.limit = config.get('source_packet_chars', 18000)
        self.total_chars = 0
        self.harness_symbols = set()

    def add(self, eid, path, content, kind, **metadata):
        if eid in self.blocks:
            return True
        if self.total_chars + len(content) + 150 > self.limit:
            return False
        self.blocks[eid] = {'evidence_id': eid, 'path': path, 'kind': kind, 'text': content, 'sha256': digest(content.encode()), **metadata}
        self.total_chars += len(content) + 150
        return True

    def index_harness_symbols(self):
        for path in self.reader.case.harness_files:
            try:
                root = self.syntax.tree(path).root_node
                self.harness_symbols.update((name for name, _, _ in self.syntax.calls(root)))
            except (ValueError, RuntimeError, OSError) as exc:
                self.issues.append('harness_index:' + str(exc))

    @staticmethod
    def production(path):
        parts = set(Path(path).parts)
        return Path(path).suffix.lower() in {'.c', '.h', '.cc', '.cpp', '.hpp', '.cxx', '.inc'} and (not parts.intersection({'test', 'tests', 'docs', 'doc', 'examples', 'fuzz', 'fuzzing'}))

    def packet(self):
        files = Counter((g.path for g in self.groups))
        return {'sample_id': self.reader.case.sample_id, 'target': self.reader.case.target, 'scope': 'change_related', 'whole_project_reviewed': False, 'harness_direct_symbols': sorted(self.harness_symbols)[:120], 'changed_files': [{'path': p, 'hunks': count} for p, count in files.items()], 'total_change_groups': len(self.groups), 'selected_change_ids': self.selected_groups, 'omitted_change_group_count': len(self.groups) - len(self.selected_groups), 'harness_complete_files': self.harness_complete, 'retrieval': self.retrieval, 'issues': sorted(set(self.issues)), 'evidence': list(self.blocks.values())}
