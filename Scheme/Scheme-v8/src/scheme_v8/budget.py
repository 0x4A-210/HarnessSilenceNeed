from __future__ import annotations
import time
from dataclasses import dataclass

class BudgetExceeded(RuntimeError):
    pass

@dataclass
class Limits:
    max_files: int = 20
    max_lines: int = 3000
    max_depth: int = 2
    seconds: float = 120
    max_llm_calls: int = 2
    max_llm_input_tokens: int = 12000
    max_index_bytes: int = 33554432
    max_file_bytes: int = 2097152
    max_diff_bytes: int = 4194304
    max_search_results: int = 80

class Budget:

    def __init__(self, config: dict | None=None, clock=time.monotonic):
        self.limits = Limits(**config or {})
        self.clock = clock
        self.started = clock()
        self.lines: dict[str, set[int]] = {}
        self.indexed_bytes = 0
        self.indexed_files = 0
        self.searches = 0
        self.search_seconds = 0.0
        self.llm_calls = 0
        self.llm_input_tokens = 0
        self.stop_reasons: list[str] = []

    def fail(self, reason: str):
        if reason not in self.stop_reasons:
            self.stop_reasons.append(reason)
        raise BudgetExceeded(reason)

    def check(self, depth: int=0):
        if self.clock() - self.started >= self.limits.seconds:
            self.fail('time_budget_exhausted')
        if depth > self.limits.max_depth:
            self.fail('call_depth_exceeded')

    def charge(self, path: str, start: int, end: int, depth: int=0):
        self.check(depth)
        additions = set(range(start, end + 1)) - self.lines.get(path, set())
        if path not in self.lines and len(self.lines) >= self.limits.max_files:
            self.fail('file_budget_exhausted')
        if sum(map(len, self.lines.values())) + len(additions) > self.limits.max_lines:
            self.fail('line_budget_exhausted')
        self.lines.setdefault(path, set()).update(additions)

    def charge_index(self, size: int):
        self.check()
        if size > self.limits.max_file_bytes:
            self.fail('file_size_limit')
        if self.indexed_bytes + size > self.limits.max_index_bytes:
            self.fail('index_bytes_exhausted')
        self.indexed_bytes += size
        self.indexed_files += 1

    def charge_llm(self, tokens: int):
        self.check()
        if tokens < 0:
            raise ValueError('Negative token count')
        if self.llm_calls >= self.limits.max_llm_calls:
            self.fail('llm_calls_exhausted')
        if self.llm_input_tokens + tokens > self.limits.max_llm_input_tokens:
            self.fail('llm_tokens_exhausted')
        self.llm_calls += 1
        self.llm_input_tokens += tokens

    def snapshot(self):
        return {'seconds': round(self.clock() - self.started, 6), 'deep_files': len(self.lines), 'deep_unique_lines': sum(map(len, self.lines.values())), 'indexed_files': self.indexed_files, 'indexed_bytes': self.indexed_bytes, 'searches': self.searches, 'search_seconds': round(self.search_seconds, 6), 'llm_calls': self.llm_calls, 'llm_input_tokens': self.llm_input_tokens, 'stop_reasons': self.stop_reasons}
