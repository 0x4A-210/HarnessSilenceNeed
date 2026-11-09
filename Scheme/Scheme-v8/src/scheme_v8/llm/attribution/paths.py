from __future__ import annotations
import re
PATH = re.compile('\\b(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\\.(?:c|cc|cpp|h|hpp|py|sh|txt)\\b')

def _resolve_path(name, files):
    options = [p for p in files if p.startswith(('input/source/', 'input/harness/')) and (p.endswith('/' + name) or p == 'input/source/' + name or p == 'input/harness/' + name)]
    return min(options, key=lambda p: (p.count('/'), p)) if options else None
