from __future__ import annotations
import re

def normalized(s):
    return re.sub('\\s+', '', s)

def verify_quotes(quotes, blocks, allowed=None):
    if not quotes:
        return (False, set(), ['missing_evidence'])
    kinds, errors = (set(), [])
    for quote in quotes:
        block = blocks.get(quote['evidence_id'])
        if block is None:
            errors.append('unprovided_evidence_id:' + quote['evidence_id'])
            continue
        phrase = normalized(quote['quote'])
        if len(phrase) < 8 or phrase not in normalized(block['text']):
            errors.append('quote_not_in_evidence:' + quote['evidence_id'])
            continue
        if allowed and block['kind'] not in allowed:
            errors.append('wrong_evidence_side:' + quote['evidence_id'])
            continue
        kinds.add(block['kind'])
    return (not errors, kinds, errors)
