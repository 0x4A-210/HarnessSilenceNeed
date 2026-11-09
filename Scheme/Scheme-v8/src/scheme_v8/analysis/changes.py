from __future__ import annotations
import re
import shlex
from pathlib import PurePosixPath
from scheme_v8.models import ChangeGroup
from scheme_v8.source_text import source_lines

def safe_diff_path(value):
    value = value.split('\t', 1)[0]
    if value.startswith('"'):
        value = shlex.split(value)[0]
    if value == '/dev/null':
        return ''
    if value.startswith(('a/', 'b/')):
        value = value[2:]
    p = PurePosixPath(value)
    if p.is_absolute() or '..' in p.parts or '\\' in value:
        raise ValueError('Unsafe diff path')
    return str(p)

def _parse_block(diff: str) -> list[ChangeGroup]:
    groups = []
    old_path = new_path = ''
    current = None
    old_line = new_line = 0
    used_old = used_new = 0
    hunk = re.compile('^@@ -(\\d+)(?:,(\\d+))? \\+(\\d+)(?:,(\\d+))? @@(.*)')

    def finish():
        if current and (used_old != current.old_count or used_new != current.new_count):
            raise ValueError('Malformed diff hunk counts')
    for line in source_lines(diff):
        if line.startswith('diff --git '):
            finish()
            current = None
        elif line.startswith('--- ') and current is None:
            old_path = safe_diff_path(line[4:])
        elif line.startswith('+++ ') and current is None:
            new_path = safe_diff_path(line[4:])
        elif (match := hunk.match(line)):
            finish()
            a, b, c, d, heading = match.groups()
            current = ChangeGroup(f'g{len(groups) + 1:04d}', new_path or old_path, old_path, int(a), int(b or 1), int(c), int(d or 1), [], [], [], heading.strip())
            groups.append(current)
            old_line, new_line = (int(a), int(c))
            used_old = used_new = 0
        elif current is not None:
            if line.startswith('+'):
                current.added_lines.append(new_line)
                current.added.append(line[1:])
                new_line += 1
                used_new += 1
            elif line.startswith('-'):
                current.removed.append(line[1:])
                old_line += 1
                used_old += 1
            elif line.startswith(' '):
                old_line += 1
                new_line += 1
                used_old += 1
                used_new += 1
            elif line.startswith('\\'):
                pass
    finish()
    if diff.strip() and (not groups):
        groups.append(ChangeGroup('g0001', new_path or old_path, old_path, 0, 0, 0, 0, [], [], [], reason='no_text_hunk_or_binary_change'))
    return groups

def parse_diff(diff: str) -> list[ChangeGroup]:
    groups = []
    for block in re.split('(?m)(?=^diff --git )', diff):
        if block.strip():
            groups.extend(_parse_block(block))
    for i, group in enumerate(groups, 1):
        group.id = f'g{i:04d}'
    return groups
