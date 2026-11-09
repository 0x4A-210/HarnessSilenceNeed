from __future__ import annotations
from pathlib import Path
from scheme_v8.budget import Budget
from scheme_v8.models import EvidenceRef
from scheme_v8.models import InputCase
from scheme_v8.source_text import source_lines
from scheme_v8.util import digest
from scheme_v8.util import inside
from scheme_v8.util import read_json
from scheme_v8.context.cache import RunCache

class InputViolation(ValueError):
    pass

def load_case(root: Path) -> InputCase:
    root = root.resolve()
    for name in ('case.json', 'manifest.json'):
        if (root / name).is_symlink():
            raise InputViolation('Symlink metadata is not allowed')
    data = read_json(root / 'case.json')
    manifest = read_json(root / 'manifest.json')
    if digest((root / 'case.json').read_bytes()) != manifest.get('case_hash'):
        raise InputViolation('case.json hash mismatch')
    return InputCase(data['id'], root, data['project'], data['harness_target'], data['harness_files'], data.get('build_script'), manifest)

class Reader:

    def __init__(self, case: InputCase, budget: Budget):
        self.case = case
        self.budget = budget
        self.cache = RunCache()
        self.evidence: list[EvidenceRef] = []
        self.requests: list[dict] = []

    def path(self, relative: str) -> Path:
        if not relative.startswith('input/') or relative not in self.case.manifest['files']:
            raise InputViolation('File is not in input allowlist: ' + relative)
        p = inside(self.case.root, relative)
        cursor = self.case.root
        for part in Path(relative).parts:
            cursor = cursor / part
            if cursor.is_symlink():
                raise InputViolation('Symlinks are not permitted')
        if not p.is_file():
            raise InputViolation('Input file missing: ' + relative)
        return p

    def index(self, relative: str) -> bytes:
        """Syntactic indexing is separately charged; semantic reads use snippet."""
        self.budget.check()
        if not relative.startswith('input/') or relative not in self.case.manifest['files']:
            raise InputViolation('File is not in input allowlist: ' + relative)
        expected = self.case.manifest['files'][relative]['sha256']
        key = (relative, expected)
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        p = self.path(relative)
        self.budget.charge_index(p.stat().st_size)
        data = p.read_bytes()
        if digest(data) != expected:
            raise InputViolation('Input changed since preparation: ' + relative)
        return self.cache.put(key, data)

    def snippet(self, relative: str, start: int, end: int, reason: str, depth=0):
        data = self.index(relative)
        lines = source_lines(data.decode('utf-8', errors='replace'), keepends=True)
        if start < 1 or end < start or start > len(lines):
            raise ValueError('Invalid source range')
        end = min(end, len(lines))
        self.budget.charge(relative, start, end, depth)
        text = ''.join(lines[start - 1:end])
        eid = 'e-' + digest(f'{relative}:{start}:{end}:{digest(data)}'.encode())[:16]
        if not any((e.id == eid for e in self.evidence)):
            self.evidence.append(EvidenceRef(eid, relative, start, end, digest(data), reason))
        self.requests.append({'path': relative, 'start': start, 'end': end, 'reason': reason, 'depth': depth, 'evidence_id': eid})
        return (text, eid)

    def node(self, relative, node, reason, depth=0):
        return self.snippet(relative, node.start_point.row + 1, node.end_point.row + 1, reason, depth)

    def read_diff(self):
        p = self.path('input/change.diff')
        if p.stat().st_size > self.budget.limits.max_diff_bytes:
            self.budget.fail('diff_size_limit')
        data = p.read_bytes()
        if digest(data) != self.case.manifest['files']['input/change.diff']['sha256']:
            raise InputViolation('Diff content hash mismatch')
        return data.decode('utf-8', errors='replace')
