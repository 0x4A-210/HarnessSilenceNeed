from __future__ import annotations
import json
import re
from pathlib import PurePosixPath
from scheme_v8.util import digest
RULES = "Diff pages carry complete added/removed text for each change group.\nConcatenate pages in part order for each side. lossless_rle_json is an EXACT\nrepresentation of data-fixture text: concatenate literal strings and repeat the\nsingle 'repeat' character 'count' times. Counts, punctuation and order matter.\nIt is not an execution result, a relevance classification, or a reason to ignore\ntest data. Assess every change group.\nQuote the supplied representation verbatim when referring to encoded fixtures.\n"

def fixture_path(path):
    p = PurePosixPath(path)
    return bool(set(p.parts) & {'testdata', 'tests', 'test', 'fixtures', 'corpus'}) and p.suffix.lower() in {'.xml', '.txt', '.json', '.csv', '.html', '.yaml', '.yml'}

def encode_runs(raw):
    """Find short run seeds, then extend without a huge regex capture stack."""
    parts, cursor = ([], 0)
    seed = re.compile('(.)\\1{63}', re.S)
    while (match := seed.search(raw, cursor)):
        start = match.start()
        end = re.compile(re.escape(match[1]) + '+').match(raw, start).end()
        if start > cursor:
            parts.append({'literal': raw[cursor:start]})
        parts.append({'repeat': match[1], 'count': end - start})
        cursor = end
    if cursor < len(raw):
        parts.append({'literal': raw[cursor:]})
    return json.dumps(parts, ensure_ascii=False, separators=(',', ':'))

def decode_runs(encoded, expected_chars):
    pieces, size = ([], 0)
    for part in json.loads(encoded):
        if set(part) == {'literal'} and isinstance(part['literal'], str):
            value = part['literal']
        elif set(part) == {'repeat', 'count'} and isinstance(part['repeat'], str) and (len(part['repeat']) == 1) and (type(part['count']) is int) and (0 < part['count'] <= expected_chars - size):
            value = part['repeat'] * part['count']
        else:
            raise ValueError('Invalid lossless fixture representation')
        size += len(value)
        if size > expected_chars:
            raise ValueError('Decoded fixture exceeds declared length')
        pieces.append(value)
    return ''.join(pieces)

def page_plan(groups, page_chars=16000):
    if page_chars < 256:
        raise ValueError('Diff page size must be at least 256 characters')
    pages, records = ([], [])
    for g in groups:
        record = {'change_id': g.id, 'path': g.path, 'heading': g.heading, 'old_start': g.old_start, 'new_start': g.new_start, 'sides': {}}
        for side, lines in (('removed', g.removed), ('added', g.added)):
            raw = '\n'.join(lines)
            encoded, encoding = (raw, 'literal')
            if fixture_path(g.path) and len(raw) > page_chars:
                candidate = encode_runs(raw)
                if len(candidate) < len(raw) * 0.7:
                    if decode_runs(candidate, len(raw)) != raw:
                        raise ValueError('Fixture lossless round trip failed')
                    encoded, encoding = (candidate, 'lossless_rle_json')
            ids = []
            chunks = [encoded[i:i + page_chars] for i in range(0, len(encoded), page_chars)] or ['']
            for part, chunk in enumerate(chunks):
                eid = f'dp-{g.id}-{side}-{part:04d}'
                ids.append(eid)
                prefix = f'CHANGE {g.id} {side.upper()} part {part + 1}/{len(chunks)} encoding={encoding}\n'
                pages.append({'evidence_id': eid, 'path': g.path, 'kind': 'diff', 'text': prefix + chunk, 'sha256': digest((prefix + chunk).encode()), 'change_id': g.id, 'side': side, 'part': part, 'payload_start': len(prefix), 'encoding': encoding, 'truncated': False, 'heading': g.heading})
            record['sides'][side] = {'raw_chars': len(raw), 'raw_sha256': digest(raw.encode()), 'encoding': encoding, 'evidence_ids': ids}
        records.append(record)
    return (pages, records)

def coverage_errors(packet):
    """Reconstruct supplied pages and verify against the trusted raw-diff ledger."""
    ledger = packet.get('diff_coverage')
    if ledger is None:
        return []
    blocks = {e['evidence_id']: e for e in packet['evidence']}
    errors = []
    ids = [r['change_id'] for r in ledger]
    if len(ids) != len(set(ids)) or len(ids) != packet['total_change_groups']:
        errors.append('invalid_diff_coverage_ledger')
    if set(ids) != set(packet['selected_change_ids']):
        errors.append('incomplete_diff_group_selection')
    for record in ledger:
        cid = record['change_id']
        for side, desc in record['sides'].items():
            try:
                parts = []
                for part, eid in enumerate(desc['evidence_ids']):
                    e = blocks[eid]
                    if e['kind'] != 'diff' or e['change_id'] != cid or e['side'] != side or (e['part'] != part) or (e['encoding'] != desc['encoding']) or (digest(e['text'].encode()) != e['sha256']):
                        raise ValueError('page identity mismatch')
                    parts.append(e['text'][e['payload_start']:])
                raw = ''.join(parts)
                if desc['encoding'] == 'lossless_rle_json':
                    raw = decode_runs(raw, desc['raw_chars'])
                if len(raw) != desc['raw_chars'] or digest(raw.encode()) != desc['raw_sha256']:
                    raise ValueError('page content mismatch')
            except (KeyError, ValueError, TypeError):
                errors.append(f'incomplete_diff_side:{cid}:{side}')
    return errors

def install_pages(builder, packet=None):
    """Replace old clipped diff blocks, retaining all non-diff evidence."""
    packet = dict(packet or {})
    pages, ledger = page_plan(builder.groups, builder.config.get('diff_page_chars', 16000))
    builder.blocks = {k: v for k, v in builder.blocks.items() if v['kind'] != 'diff'}
    builder.total_chars = sum((len(e['text']) + 150 for e in builder.blocks.values()))
    needed = builder.total_chars + sum((len(e['text']) + 150 for e in pages))
    builder.limit = float('inf') if builder.config.get('unlimited_chars', False) else min(max(builder.limit, needed + builder.config.get('diff_context_reserve_chars', 100000)), builder.config.get('diff_packet_ceiling_chars', 700000))
    for e in pages:
        builder.add(e['evidence_id'], e['path'], e['text'], e['kind'], **{k: v for k, v in e.items() if k not in ('evidence_id', 'path', 'text', 'kind', 'sha256')})
    selected = [r['change_id'] for r in ledger if any((eid in builder.blocks for s in r['sides'].values() for eid in s['evidence_ids']))]
    incomplete = [r['change_id'] for r in ledger if any((eid not in builder.blocks for s in r['sides'].values() for eid in s['evidence_ids']))]
    builder.selected_groups = selected
    packet.update(selected_change_ids=selected, total_change_groups=len(ledger), omitted_change_group_count=len(ledger) - len(selected), truncated_change_ids=incomplete, evidence=list(builder.blocks.values()), diff_coverage=ledger, diff_representation_rules=RULES, diff_pending_change_ids=incomplete, diff_packet_limit_chars=None if builder.limit == float('inf') else builder.limit)
    packet['diff_coverage_errors'] = coverage_errors(packet)
    packet['diff_coverage_complete'] = not packet['diff_coverage_errors'] and (not incomplete)
    return packet
