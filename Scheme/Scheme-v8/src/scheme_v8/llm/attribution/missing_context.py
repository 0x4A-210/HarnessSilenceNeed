from __future__ import annotations
import re
from scheme_v8.llm.attribution.symbols import STOP

def choose_scope_requests(missing, reasons, limit):
    """Prioritize explicitly missing facts, including C/C++ camel-case names."""
    names = []
    for part in [*missing, *reasons]:
        for name in re.findall('\\b[A-Za-z_][A-Za-z0-9_]{1,100}\\b', part):
            code_like = '_' in name or name.isupper() or re.search('[a-z][A-Z]|[A-Z]{2}[a-z]', name)
            if code_like and name not in STOP and (name not in names):
                names.append(name)
    return names[:limit]
