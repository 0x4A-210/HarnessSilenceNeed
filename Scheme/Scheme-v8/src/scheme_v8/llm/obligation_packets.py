from __future__ import annotations
from collections import defaultdict
import json

def encode_prompt(instructions, packet):
    return instructions + '\nPACKET:\n' + json.dumps(packet, ensure_ascii=False, separators=(',', ':'))

def intervals_complete(views, unit):
    cursor = unit['start']
    for v in sorted((v for v in views if v['unit_id'] == unit['unit_id']), key=lambda v: v['provided_start']):
        if v['provided_start'] <= cursor:
            cursor = max(cursor, v['provided_end'] + 1)
    return cursor > unit['end']

def plan_packets(store, packet, instructions, max_chars=850000, unit_ids=None, extra=None):
    """Every selected unit is delivered; oversized pairs split into complete
    units, then line-contiguous parts. Nothing is silently truncated. The exact
    serialized prompt, including instructions/metadata/feedback, is measured.
    """
    ids = list(unit_ids if unit_ids is not None else store.units)
    catalog = [{k: u[k] for k in ('unit_id', 'kind', 'path', 'name', 'start', 'end', 'change_ids')} for u in store.units.values() if u['line_origin'] == 'file']
    base = {k: packet[k] for k in ('target', 'sample_id', 'build_environment_policy', 'source_root_inventory', 'program_facts') if k in packet}
    base.update(evidence_catalog=catalog, global_change_ids=packet.get('selected_change_ids', []), transport_policy='Parts are continuations. Missing catalog entries are not negative evidence.', **extra or {})

    def payload(views):
        gids = sorted({g for v in views for g in v['change_ids']})
        return {**base, 'selected_change_ids': gids, 'evidence': views}

    def fits(views):
        return len(encode_prompt(instructions, payload(views))) <= max_chars
    if not fits([]):
        raise ValueError('request_metadata_exceeds_transport_capacity')
    common, remaining = ([], [])
    for uid in ids:
        view = store.view(uid)
        if view['kind'] == 'harness' and len(encode_prompt(instructions, payload(common + [view]))) < max_chars // 2:
            common.append(view)
        else:
            remaining.append(uid)
    families = defaultdict(list)
    for uid in remaining:
        u = store.units[uid]
        families[u['path'], u['original_unit_id']].append(store.view(uid))
    pieces = []

    def split(view):
        if fits(common + [view]):
            return [[view]]
        a, b = (view['provided_start'], view['provided_end'])
        if a == b:
            raise ValueError('single_line_exceeds_transport_capacity:' + view['unit_id'] + ':' + str(a))
        mid = (a + b) // 2
        return split(store.view(view['unit_id'], a, mid)) + split(store.view(view['unit_id'], mid + 1, b))
    for family in families.values():
        if fits(common + family):
            pieces.append(family)
        else:
            for view in family:
                pieces.extend(split(view))
    batches, current = ([], list(common))
    for piece in pieces:
        if not fits(current + piece):
            batches.append(payload(current))
            current = list(common)
        current.extend(piece)
    if current or not batches:
        batches.append(payload(current))
    all_views = [v for b in batches for v in b['evidence']]
    if not all((intervals_complete(all_views, store.units[uid]) for uid in ids)):
        raise ValueError('lossless_transport_coverage_failed')
    for b in batches:
        if len(encode_prompt(instructions, b)) > max_chars:
            raise ValueError('serialized_transport_guard_failed')
    return batches
