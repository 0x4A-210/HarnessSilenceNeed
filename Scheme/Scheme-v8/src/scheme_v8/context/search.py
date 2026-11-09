from __future__ import annotations
import shutil
import subprocess
import time
from pathlib import Path
from scheme_v8.context.reader import Reader
CODE_SUFFIXES = {'.c', '.h', '.cc', '.cpp', '.cxx', '.hpp', '.hxx', '.inc'}

class Search:

    def __init__(self, reader: Reader):
        self.reader = reader
        self.cache = {}
        self.truncated = []

    def files(self, symbol: str) -> list[str]:
        if symbol in self.cache:
            return self.cache[symbol]
        budget = self.reader.budget
        budget.check()
        started = time.monotonic()
        budget.searches += 1
        limit = budget.limits.max_search_results
        rg = shutil.which('rg')
        matches = []
        try:
            if rg:
                root = self.reader.case.root
                remaining = max(0.05, budget.limits.seconds - (budget.clock() - budget.started))
                proc = subprocess.run([rg, '--files-with-matches', '--fixed-strings', '--', symbol, str(root / 'input/source')], capture_output=True, text=True, timeout=remaining)
                if proc.returncode not in (0, 1):
                    raise RuntimeError('rg search failed')
                for line in proc.stdout.splitlines():
                    p = Path(line)
                    if p.suffix.lower() in CODE_SUFFIXES:
                        rel = p.relative_to(root).as_posix()
                        self.reader.path(rel)
                        matches.append(rel)
            else:
                for rel in sorted(self.reader.case.manifest['files']):
                    if rel.startswith('input/source/') and Path(rel).suffix.lower() in CODE_SUFFIXES:
                        if symbol.encode() in self.reader.index(rel):
                            matches.append(rel)
                            if len(matches) > limit:
                                break
            if len(matches) > limit:
                self.truncated.append(symbol)
            result = sorted(matches)[:limit]
            self.cache[symbol] = result
            return result
        finally:
            budget.search_seconds += time.monotonic() - started
