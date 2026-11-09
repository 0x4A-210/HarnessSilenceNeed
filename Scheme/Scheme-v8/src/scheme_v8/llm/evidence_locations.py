from __future__ import annotations
from collections import defaultdict
from copy import deepcopy
import re
from scheme_v8.util import digest
from scheme_v8.util import write_json
from scheme_v8.source_text import source_lines
from scheme_v8.llm.schema import TEXT
from scheme_v8.llm.schema import obj
LOCATION = obj({'unit_id': TEXT, 'start_line': {'type': 'integer'}, 'end_line': {'type': 'integer'}, 'role': {'type': 'string', 'enum': ['primary', 'dependency']}, 'dependency_reason': TEXT})
LOCATION_RULES = "\nCITATION PROTOCOL (replaces instructions asking you to copy quotation strings):\nSelect unit_id and inclusive start_line/end_line from the numbered evidence.\nThe program extracts the original text and verifies its immutable hash. Never\ninvent an ID or a line number. A citation may cross display pages of the SAME\nunit/version if every cited line was supplied. Source versions and harness are\ndifferent types. Diff-page line numbers address the displayed diff, not a file.\nUse role=primary for the obligation's direct contract. Use role=dependency for\nsupporting callers, error producers, declarations or configuration, explaining\nthe concrete causal relationship in dependency_reason. Each before/after\nassessment still needs a primary contract anchored to its change_ids (or an\nunchanged contract). A dependency can belong to a DIFFERENT change group; this\ndoes not make that group the origin of the obligation. Quoted text is extracted\nby the program; assess semantics using the surrounding code, not line IDs alone.\n"

def location_schema(schema):
    if isinstance(schema, dict):
        if schema.get('type') == 'object' and set(schema.get('properties', {})) == {'evidence_id', 'quote'}:
            return deepcopy(LOCATION)
        return {k: location_schema(v) for k, v in schema.items()}
    if isinstance(schema, list):
        return [location_schema(v) for v in schema]
    return schema

def walk_locations(value, path=''):
    if isinstance(value, dict):
        if set(value) == set(LOCATION['properties']):
            yield (path, value)
        else:
            for key, item in value.items():
                yield from walk_locations(item, path + '/' + key)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk_locations(item, path + '/' + str(index))

def set_pointer(value, pointer, replacement):
    parts = pointer.strip('/').split('/')
    for part in parts[:-1]:
        value = value[int(part)] if isinstance(value, list) else value[part]
    key = int(parts[-1]) if isinstance(value, list) else parts[-1]
    value[key] = replacement

class EvidenceStore:

    def __init__(self, packet):
        grouped = defaultdict(list)
        for block in packet['evidence']:
            grouped[block['kind'], block['path'], block.get('unit_id', block['evidence_id'])].append(block)
        self.units, self.aliases, self.alias_offsets = ({}, {}, {})
        records = {r['unit_id']: r for r in packet.get('whole_units', []) + packet.get('paired_units', [])}
        for (kind, path, identity), pages in grouped.items():
            pages.sort(key=lambda b: b.get('part', 0))
            if len(pages) > 1 and [b.get('part') for b in pages] != list(range(len(pages))):
                raise ValueError('noncontiguous_unit_pages:' + str(identity))
            first = pages[0]
            value = ''.join((p['text'] for p in pages))
            for p in pages:
                if p.get('sha256') and (not p.get('side_diff_only')) and (digest(p['text'].encode()) != p['sha256']):
                    raise ValueError('evidence_hash_mismatch:' + p['evidence_id'])
            expected = first.get('whole_side_sha256')
            if expected and expected != digest(value.encode()):
                raise ValueError('unit_hash_mismatch:' + str(identity))
            physical = 'unit_id' in first and first.get('start', 0) > 0 and (not first.get('side_diff_only'))
            start = min((p.get('start', 1) for p in pages)) if physical else 1
            lines = source_lines(value, keepends=True) or ['']
            sha = digest(value.encode())
            uid = 'u-' + digest(f'{kind}:{path}:{identity}:{start}:{sha}'.encode())[:20]
            gids = sorted({g for p in pages for g in p.get('change_ids', [])} | {p['change_id'] for p in pages if p.get('change_id')})
            if kind == 'source':
                for g in packet.get('diff_coverage', []):
                    if path == 'input/source/' + g['path'] and start <= g['new_start'] <= start + len(lines) - 1:
                        gids.append(g['change_id'])
            unit = {'unit_id': uid, 'original_unit_id': identity, 'kind': kind, 'path': path, 'version': {'before_source': 'before', 'after_source': 'after', 'harness': 'harness', 'source': 'after', 'diff': 'diff'}.get(kind, kind), 'name': records.get(identity, {}).get('name', ''), 'start': start, 'end': start + len(lines) - 1, 'line_origin': 'file' if physical else 'display', 'sha256': sha, 'text': value, 'change_ids': sorted(set(gids)), 'invariant_source': first.get('invariant_source', False), 'unit_kind': first.get('unit_kind', 'diff_page'), 'page_ids': [p['evidence_id'] for p in pages]}
            self.units[uid] = unit
            offset = 0
            for p in pages:
                self.aliases[p['evidence_id']] = uid
                self.alias_offsets[p['evidence_id']] = (offset, offset + len(p['text']))
                offset += len(p['text'])

    def save(self, folder):
        for uid, unit in self.units.items():
            write_json(folder / (uid + '.json'), unit)
        write_json(folder / 'index.json', {'units': [self.metadata(u) for u in self.units.values()], 'page_to_unit': self.aliases})

    @staticmethod
    def metadata(unit):
        return {k: v for k, v in unit.items() if k not in ('text', 'page_ids')}

    def view(self, uid, start=None, end=None):
        u = self.units[uid]
        start, end = (start if start is not None else u['start'], end if end is not None else u['end'])
        lines = source_lines(u['text'], keepends=True) or ['']
        return {**self.metadata(u), 'provided_start': start, 'provided_end': end, 'complete_unit': start == u['start'] and end == u['end'], 'numbered_text': ''.join((f'{n}|{lines[n - u['start']]}' + ('' if lines[n - u['start']].endswith('\n') else '\n') for n in range(start, end + 1)))}

    def resolve(self, location, delivered):
        uid = location['unit_id']
        if uid not in self.units:
            raise ValueError('unknown_unit_id:' + uid)
        unit = self.units[uid]
        a, b = (location['start_line'], location['end_line'])
        if type(a) is not int or type(b) is not int or (not unit['start'] <= a <= b <= unit['end']):
            raise ValueError(f'invalid_line_range:{uid}:{a}-{b}:available={unit['start']}-{unit['end']}')
        intervals = sorted(((v['provided_start'], v['provided_end']) for v in delivered if v['unit_id'] == uid))
        cursor = a
        for x, y in intervals:
            if x <= cursor <= y:
                cursor = y + 1
        if cursor <= b:
            raise ValueError(f'unprovided_lines:{uid}:{a}-{b}')
        if digest(unit['text'].encode()) != unit['sha256']:
            raise ValueError('unit_hash_mismatch:' + uid)
        if location['role'] == 'dependency' and len(location['dependency_reason'].strip()) < 16:
            raise ValueError('missing_dependency_relation:' + uid)
        lines = source_lines(unit['text'], keepends=True) or ['']
        quote = ''.join(lines[a - unit['start']:b - unit['start'] + 1])
        if len(re.sub('\\s+', '', quote)) < 8:
            raise ValueError('citation_too_short:' + uid)
        eid = 'loc-' + digest((uid + ':' + str(a) + ':' + str(b) + ':' + location['role'] + ':' + location['dependency_reason']).encode())[:24]
        block = {'evidence_id': eid, 'kind': unit['kind'], 'path': unit['path'], 'text': quote, 'change_ids': unit['change_ids'], 'invariant_source': unit['invariant_source'], 'citation_role': location['role'], 'dependency_reason': location['dependency_reason'], 'location': {'unit_id': uid, 'version': unit['version'], 'path': unit['path'], 'start_line': a, 'end_line': b, 'unit_sha256': unit['sha256'], 'quote_sha256': digest(quote.encode())}}
        return ({'evidence_id': eid, 'quote': quote}, block)

    def materialize(self, answer, delivered):
        result, blocks, errors, ledger = (deepcopy(answer), {}, [], [])
        for pointer, loc in walk_locations(answer):
            try:
                quote, block = self.resolve(loc, delivered)
                expected = 'before_source' if '/before/source_evidence/' in pointer else 'after_source' if '/after/source_evidence/' in pointer else 'harness' if '/harness_evidence/' in pointer else None
                if expected and block['kind'] != expected:
                    raise ValueError(f'wrong_evidence_side:{loc['unit_id']}:expected={expected}:actual={block['kind']}')
                if expected in ('before_source', 'after_source') and pointer.startswith('/claims/'):
                    claim = answer['claims'][int(pointer.split('/')[2])]
                    if loc['role'] == 'primary' and (not (set(block['change_ids']) & set(claim['change_ids']) or block['invariant_source'])):
                        raise ValueError(f'primary_change_mismatch:{loc['unit_id']}:claim={claim['change_ids']}:unit={block['change_ids']};use_dependency_only_if_causally_supporting')
                blocks[block['evidence_id']] = block
                set_pointer(result, pointer, quote)
                ledger.append({'pointer': pointer, **block})
            except ValueError as exc:
                errors.append({'pointer': pointer, 'location': loc, 'reason': str(exc)})
                set_pointer(result, pointer, {'evidence_id': 'INVALID:' + pointer, 'quote': 'invalid citation'})
        for index, claim in enumerate(answer.get('claims', [])):
            for side in ('before', 'after'):
                refs = claim.get(side, {}).get('source_evidence', [])
                if refs and (not any((r.get('role') == 'primary' for r in refs))):
                    pointer = f'/claims/{index}/{side}/source_evidence/0'
                    if not any((e['pointer'] == pointer for e in errors)):
                        errors.append({'pointer': pointer, 'location': refs[0], 'reason': f'missing_primary_contract:{side}:claim={claim.get('claim_id')};provide_the_direct_contract_not_just_dependencies'})
                    set_pointer(result, pointer, {'evidence_id': 'INVALID:' + pointer, 'quote': 'missing primary contract'})
        return (result, list(blocks.values()), errors, ledger)

    def locate_legacy(self, quote, expected_kind=None):
        """Unique exact normalized match, including cross-page matches; audit only."""
        original = self.aliases.get(quote['evidence_id'])
        candidates = [original] if original else []
        candidates += [u for u in self.units if u != original]
        needle = re.sub('\\s+', '', quote['quote'])
        found = []
        for uid in candidates:
            unit = self.units[uid]
            if expected_kind and unit['kind'] != expected_kind:
                continue
            positions = [i for i, c in enumerate(unit['text']) if not c.isspace()]
            hay = ''.join((unit['text'][i] for i in positions))
            occurrences, pos = ([], 0)
            while len(needle) >= 8:
                first = hay.find(needle, pos)
                if first < 0:
                    break
                if uid != original or self.alias_offsets[quote['evidence_id']][0] <= positions[first] < self.alias_offsets[quote['evidence_id']][1]:
                    occurrences.append(first)
                pos = first + 1
            if len(occurrences) != 1:
                continue
            first = occurrences[0]
            a = unit['start'] + unit['text'][:positions[first]].count('\n')
            b = unit['start'] + unit['text'][:positions[first + len(needle) - 1]].count('\n')
            found.append({'unit_id': uid, 'start_line': a, 'end_line': b, 'role': 'primary', 'dependency_reason': ''})
            if uid == original:
                return found[0]
        if len(found) != 1:
            raise ValueError('legacy_quote_not_uniquely_located')
        return found[0]
