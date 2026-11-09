"""Verification plan 1: session start/resume/fork with structured output.

Usage: python tools/verify_sessions.py <provider> <model> <out_dir> [effort] [vary]

With `vary`, calls 2 and 3 use a different output schema than call 1, to
measure whether a per-turn schema change breaks prefix caching.

Three calls against one backend, each with a JSON schema:
  1. new persistent session; prompt = long fixed evidence prefix + question A
  2. resume that session; prompt = question B only (needs facts from call 1)
  3. fork from the session of call 1 (if supported); prompt = question C only
Reports per-call usage, including cached/cache-write tokens, and whether the
answers prove the evidence was available without re-sending it.
"""
import json
import sys
from pathlib import Path

from scheme_v8.budget import Budget
from scheme_v8.llm.backends import make_client
from scheme_v8.util import write_json

provider, model, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
effort = sys.argv[4] if len(sys.argv) > 4 else 'low'
vary = len(sys.argv) > 5 and sys.argv[5] == 'vary'
budget = Budget({'max_files': 1, 'max_lines': 1, 'max_depth': 1, 'seconds': 1800, 'max_llm_calls': 10,
                 'max_llm_input_tokens': 2_000_000})
client = make_client({'provider': provider, 'model': model, 'reasoning_effort': effort, 'timeout_seconds': 600}, budget)

# About 20k tokens of synthetic "evidence"; one line carries the fact to recall.
lines = [f'{n}| static int helper_{n}(int x) {{ return x * {n % 97} + {n % 13}; }}' for n in range(1, 1601)]
lines[1233] = '1234| static const int SECRET_LIMIT = 4093; /* decisive fact */'
evidence = '\n'.join(lines)
schema = {'type': 'object', 'additionalProperties': False, 'required': ['answer', 'line'],
          'properties': {'answer': {'type': 'string'}, 'line': {'type': 'integer'}}}
later = schema if not vary else {**schema, 'required': ['answer', 'line', 'note'],
                                 'properties': {**schema['properties'], 'note': {'type': 'string'}}}

calls = []
first = client.infer('EVIDENCE (numbered source lines):\n' + evidence +
                     '\n\nQuestion A: which line defines helper_17? Reply with its line number.',
                     schema, out / 'call-1', persist=True)
session = client.last_session
calls.append({'call': 'start', 'session': session, 'answer': first})
second = client.infer('Question B: using the evidence from the first message, what is the value of '
                      'SECRET_LIMIT and on which line is it defined?', later, out / 'call-2', session=session)
calls.append({'call': 'resume', 'session': client.last_session, 'answer': second})
try:
    third = client.infer('Question C: what does helper_20 return for x = 1? Give the number as answer '
                         'and its line.', later, out / 'call-3', session=session, fork=True)
    calls.append({'call': 'fork', 'session': client.last_session, 'answer': third})
except Exception as exc:  # codex_cli has no fork
    calls.append({'call': 'fork', 'error': str(exc)})

for record, row in zip(client.calls, calls):
    row.update(usage={k: v for k, v in (record.get('usage') or {}).items() if k != 'raw'},
               seconds=record.get('seconds'), session_in=record.get('session_in'), error=record.get('error'))
summary = {'provider': provider, 'model': model, 'effort': effort, 'vary_schema': vary,
           'resume_recalled_fact': str(second.get('answer', '')).strip().startswith('4093') or '4093' in str(second),
           'resume_kept_session': calls[1]['session'] == session,
           'fork_new_session': calls[2].get('session') not in (None, session), 'calls': calls}
write_json(out / 'summary.json', summary)
print(json.dumps(summary, ensure_ascii=False, indent=2))
client.close()
