from __future__ import annotations
import re
from dataclasses import dataclass
from scheme_v8.analysis.changes import parse_diff
from scheme_v8.analysis.changes import safe_diff_path
from scheme_v8.source_text import source_lines
HUNK = re.compile('^@@ -(\\d+)(?:,(\\d+))? \\+(\\d+)(?:,(\\d+))? @@')

@dataclass
class Hunk:
    change_id: str
    old_start: int
    new_start: int
    old_count: int
    new_count: int
    lines: list[str]

@dataclass
class FilePatch:
    old_path: str
    new_path: str
    hunks: list[Hunk]
    unsupported: bool = False

def parse_file_patches(diff: str) -> dict[str, FilePatch]:
    """Use the same group numbering as analysis.changes.parse_diff."""
    result = {}
    group_id = 0
    for block in re.split('(?m)(?=^diff --git )', diff):
        if not block.strip():
            continue
        lines = source_lines(block)
        old_path = new_path = ''
        for line in lines:
            if line.startswith('--- '):
                old_path = safe_diff_path(line[4:])
            elif line.startswith('+++ '):
                new_path = safe_diff_path(line[4:])
        patch = FilePatch(old_path, new_path, [])
        current = None
        for line in lines:
            match = HUNK.match(line)
            if match:
                group_id += 1
                old_start, old_count, new_start, new_count = match.groups()
                current = Hunk(f'g{group_id:04d}', int(old_start), int(new_start), int(old_count or 1), int(new_count or 1), [])
                patch.hunks.append(current)
            elif current is not None and line.startswith((' ', '+', '-', '\\')):
                current.lines.append(line)
        if not patch.hunks:
            group_id += 1
            patch.unsupported = True
        key = new_path or old_path
        if key:
            result[key] = patch
    expected = {g.id for g in parse_diff(diff)}
    observed = {h.change_id for p in result.values() for h in p.hunks}
    if not observed.issubset(expected):
        raise ValueError('Preimage and detector change numbering diverged')
    return result

def reverse_file(post: str, patch: FilePatch) -> str:
    if patch.unsupported or not patch.hunks:
        raise ValueError('unsupported_non_text_patch')
    if not patch.old_path:
        return ''
    source = source_lines(post)
    result = []
    cursor = 0
    for hunk in patch.hunks:
        start = hunk.new_start - 1
        if start < cursor or start > len(source):
            raise ValueError('invalid_hunk_position')
        result.extend(source[cursor:start])
        pos = start
        old_used = new_used = 0
        for line in hunk.lines:
            prefix = line[:1]
            content = line[1:]
            if prefix == '\\':
                continue
            if prefix in (' ', '+'):
                if pos >= len(source) or source[pos] != content:
                    raise ValueError('reverse_patch_context_mismatch')
                pos += 1
                new_used += 1
            if prefix in (' ', '-'):
                result.append(content)
                old_used += 1
        if old_used != hunk.old_count or new_used != hunk.new_count:
            raise ValueError('reverse_patch_hunk_count_mismatch')
        cursor = pos
    result.extend(source[cursor:])
    return '\n'.join(result) + ('\n' if post.endswith('\n') else '')
