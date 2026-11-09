from __future__ import annotations
from pathlib import Path
from tree_sitter import Parser
from scheme_v8.analysis.syntax import C
from scheme_v8.analysis.syntax import CPP
from scheme_v8.analysis.syntax import walk
from scheme_v8.util import digest
from scheme_v8.source_text import source_lines
from scheme_v8.llm.whole_functions import CODE
from scheme_v8.llm.whole_functions import UNITS
from scheme_v8.llm.whole_functions import function_name
from scheme_v8.llm.attribution.preimage import parse_file_patches
from scheme_v8.llm.attribution.preimage import reverse_file

def old_line(number, patch):
    shift = 0
    for h in patch.hunks:
        if number < h.new_start:
            break
        if h.new_count and number < h.new_start + h.new_count:
            return max(1, h.old_start + min(number - h.new_start, max(0, h.old_count - 1)))
        shift += h.old_count - h.new_count
    return max(1, number + shift)

def pair_packet(builder, packet, patch_resolver=None):
    patches = parse_file_patches(builder.reader.read_diff())
    evidence = [e for e in packet['evidence'] if e['kind'] == 'harness']
    chars = sum((len(e['text']) + 150 for e in evidence))
    limit = float('inf') if builder.config.get('unlimited_chars', False) else builder.config.get('whole_temporal_packet_chars', 750000)
    cache, provenance, errors, pair_records = ({}, [], [], [])
    for e in packet['evidence']:
        if e['kind'] != 'diff' or 'side' not in e:
            continue
        side = 'before' if e['side'] == 'removed' else 'after'
        value = e['text'][e['payload_start']:]
        if not value:
            value = 'NO ' + e['side'].upper() + ' TEXT IN THIS HUNK; this alone does not establish prior applicability.'
        clone = {**e, 'evidence_id': side + '-' + e['evidence_id'], 'kind': side + '_source', 'text': value, 'side_diff_only': True, 'invariant_source': False}
        if chars + len(value) + 150 <= limit:
            evidence.append(clone)
            chars += len(value) + 150
        else:
            errors.append('side_diff_capacity:' + e['change_id'])
    blocks = {e['evidence_id']: e for e in packet['evidence']}
    for record in packet['whole_units']:
        if record['kind'] != 'source' or not record['complete']:
            continue
        path = record['path']
        relative = path.removeprefix('input/source/')
        if not path.startswith('input/source/'):
            continue
        patch = patches.get(relative)
        try:
            if path not in cache:
                post = builder.reader.index(path).decode('utf-8')
                alignment = None
                if patch and patch_resolver is not None:
                    patch, alignment = patch_resolver(post, patch)
                    patches[relative] = patch
                old = reverse_file(post, patch) if patch else post
                tree = None
                if Path(path).suffix.lower() in CODE and old:
                    language = CPP if Path(path).suffix.lower() in {'.cpp', '.cc', '.cxx', '.hpp', '.hxx'} else C
                    tree = Parser(language).parse(old.encode())
                cache[path] = (old, tree)
                provenance.append({'path': path, 'reverse_patch_verified': bool(patch), 'unchanged_file': not bool(patch), 'post_sha256': digest(post.encode()), 'preimage_sha256': digest(old.encode()), **({'alignment': alignment} if alignment is not None else {})})
            old, tree = cache[path]
            after = ''.join((blocks[eid]['text'] for eid in record['evidence_ids']))
            ids = [g.id for g in builder.groups if g.path == relative and g.new_start <= record['end'] and (g.new_start + max(1, g.new_count) - 1 >= record['start'])]
            if not patch:
                before = after
                before_start, before_end = (record['start'], record['end'])
            elif not patch.old_path:
                before, before_start, before_end = ('FILE ABSENT BEFORE CHANGE', 0, 0)
            else:
                lines = source_lines(old, keepends=True)
                a, b = (old_line(record['start'], patch), old_line(record['end'], patch))
                candidates = []
                added_definition = False
                if record['unit_kind'] in ('function', 'function_window') and tree is not None:
                    candidates = [n for n in walk(tree.root_node) if n.type == 'function_definition' and function_name(n) == record['name']]
                    if not candidates:
                        added_lines = {line for g in builder.groups if g.path == relative for line in g.added_lines}
                        added_definition = all((line in added_lines for line in range(record.get('function_start', record['start']), record.get('function_end', record['end']) + 1)))
                        if not added_definition:
                            candidates = [n for n in walk(tree.root_node) if n.type == 'function_definition' and n.start_point.row + 1 <= a <= n.end_point.row + 1]
                elif record['unit_kind'] == 'file':
                    a, b = (1, len(lines))
                elif tree is not None:
                    candidates = [n for n in walk(tree.root_node) if n.type in UNITS and n.start_point.row + 1 <= a <= n.end_point.row + 1]
                if candidates:
                    node = min(candidates, key=lambda n: (abs(n.start_point.row + 1 - a), n.end_byte - n.start_byte))
                    if record['unit_kind'] == 'function_window':
                        a = max(node.start_point.row + 1, min(a, node.end_point.row + 1))
                        b = min(node.end_point.row + 1, max(a, b))
                    else:
                        a, b = (node.start_point.row + 1, node.end_point.row + 1)
                elif record['unit_kind'] in ('function', 'function_window') and (not added_definition):
                    errors.append(relative + ':old_function_correspondence_unresolved:' + record['name'])
                    continue
                before_start, before_end = (a, min(b, len(lines)))
                before = f'Verified preimage file {relative} has no function definition named {record['name']}. The entire after definition consists of added lines. This establishes absence in this file only; other implementations or equivalent paths must still be considered.' if added_definition else ''.join(lines[a - 1:before_end])
            invariant = before == after
            pair_pages = []
            for side, value, start, end in (('before', before, before_start, before_end), ('after', after, record['start'], record['end'])):
                chunks = [value[i:i + 12000] for i in range(0, len(value), 12000)] or ['']
                for part, chunk in enumerate(chunks):
                    pair_pages.append({'evidence_id': f'{side}-whole-{record['unit_id']}-{part:04d}', 'kind': side + '_source', 'path': path, 'text': chunk, 'unit_id': record['unit_id'], 'part': part, 'start': start, 'end': end, 'unit_kind': record['unit_kind'], 'complete_function': record['unit_kind'] == 'function', 'change_ids': ids, 'invariant_source': invariant, 'whole_side_sha256': digest(value.encode()), 'side_chars': len(value), 'truncated': False})
            if chars + sum((len(e['text']) + 150 for e in pair_pages)) > limit:
                errors.append(relative + ':whole_pair_capacity:' + record['unit_id'])
                continue
            evidence.extend(pair_pages)
            chars += sum((len(e['text']) + 150 for e in pair_pages))
            pair_records.append({'unit_id': record['unit_id'], 'path': path, 'name': record['name'], 'before_sha256': digest(before.encode()), 'after_sha256': digest(after.encode()), 'evidence_ids': [e['evidence_id'] for e in pair_pages], 'invariant_source': invariant})
        except (ValueError, OSError, UnicodeError, RuntimeError) as exc:
            errors.append(relative + ':' + str(exc))
    return {k: v for k, v in {**packet, 'evidence': evidence, 'preimage_manifest': provenance, 'preimage_errors': list(dict.fromkeys(errors)), 'paired_units': pair_records, 'temporal_packet_chars': chars, 'neutral_diff_coverage': packet.get('diff_coverage', [])}.items() if k not in {'whole_units', 'diff_coverage', 'prior_raw_verdict', 'prior_unresolved_questions'}}
