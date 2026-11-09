from dataclasses import replace
from scheme_v8.llm.attribution.preimage import reverse_file
from scheme_v8.source_text import source_lines

def _match(source, start, hunk):
    pos, lines = (start, [])
    for line in hunk.lines:
        prefix, content = (line[:1], line[1:])
        if prefix == '\\':
            continue
        if prefix == '-':
            lines.append(line)
            continue
        if prefix == ' ' and (not content.strip()):
            if pos >= len(source) or source[pos] != content:
                return None
            lines.append(line)
            pos += 1
            while pos < len(source) and (not source[pos].strip()):
                lines.append(' ' + source[pos])
                pos += 1
            continue
        if pos >= len(source) or source[pos] != content:
            return None
        lines.append(line)
        pos += 1
    return (pos, lines)

def align_patch(post, patch):
    """Return the original patch or an unambiguous verified contextual alignment.

    No whitespace inside a nonblank statement, changed line, reordered code or
    semantic mismatch is tolerated. Extra blank context is retained unchanged.
    A forward round trip must reproduce the supplied post file exactly.
    """
    try:
        reverse_file(post, patch)
        return (patch, {'method': 'exact_original_coordinates'})
    except ValueError:
        if patch.unsupported or not patch.old_path:
            raise
    source = source_lines(post)
    hunks, cursor, shift, audit = ([], 0, 0, [])
    for h in patch.hunks:
        significant = next((l[1:] for l in h.lines if l.startswith((' ', '+'))), None)
        if significant is None:
            raise ValueError('cannot_relocate_zero_length_post_hunk')
        matches = []
        for pos in range(cursor, len(source)):
            if source[pos] != significant:
                continue
            result = _match(source, pos, h)
            if result is not None:
                matches.append((pos, *result))
        if len(matches) != 1:
            raise ValueError('preimage_alignment_not_unique:' + h.change_id + ':' + str(len(matches)))
        pos, end, lines = matches[0]
        old_count = sum((l.startswith((' ', '-')) for l in lines))
        new_count = sum((l.startswith((' ', '+')) for l in lines))
        adjusted = replace(h, new_start=pos + 1, old_start=pos + 1 + shift, old_count=old_count, new_count=new_count, lines=lines)
        hunks.append(adjusted)
        audit.append({'change_id': h.change_id, 'original_new_start': h.new_start, 'aligned_new_start': pos + 1, 'extra_blank_context': new_count - h.new_count})
        shift += old_count - new_count
        cursor = end
    aligned = replace(patch, hunks=hunks)
    before = reverse_file(post, aligned)
    inverted = replace(aligned, old_path=aligned.new_path, new_path=aligned.old_path, hunks=[replace(h, old_start=h.new_start, new_start=h.old_start, old_count=h.new_count, new_count=h.old_count, lines=[('-' if l[0] == '+' else '+' if l[0] == '-' else l[0]) + l[1:] for l in h.lines]) for h in hunks])
    if reverse_file(before, inverted) != post:
        raise ValueError('preimage_alignment_roundtrip_failed')
    return (aligned, {'method': 'unique_relocation_extra_blank_context', 'hunks': audit, 'forward_roundtrip_verified': True})
