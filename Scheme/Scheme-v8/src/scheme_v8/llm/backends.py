"""Replaceable model backends driven through local agent CLIs (no API keys).

Every backend exposes the same call:

    client.infer(prompt, schema, output, session=None, fork=False, persist=False)

* session=None starts a fresh conversation; persist=True keeps it resumable.
* session=<id> continues that conversation; only the new prompt is sent.
* fork=True (with session) branches a new conversation from that context, so a
  reviewer can see the evidence without sharing later turns.

After each call, client.last_session holds the conversation id. Each call is
recorded in client.calls with usage normalized to input/cached/cache-write/
output tokens. Tools are disabled for both CLIs; the evidence is the prompt.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

from scheme_v8.llm.schema import validate_schema
from scheme_v8.util import digest, write_json


class InferenceError(RuntimeError):
    pass


class TransientFailure(InferenceError):
    """Network, overload or rate-limit failure; the same call may be retried."""


class ContentFlagged(InferenceError):
    """The provider's safety filter refused the request; not retried."""


class QuotaExhausted(InferenceError):
    """Account usage limit reached; the batch must stop, not record unknown."""


TRANSIENT_MARKERS = ('at capacity', '429', 'too many requests', 'overloaded', 'connection failed',
                     'error sending request', 'tls handshake', 'stream disconnected', 'timed out',
                     'connection reset', 'econnreset', 'socket hang up', '529', '503', '502')
QUOTA_MARKERS = ('usage limit', "you've hit your", 'you’ve hit your', 'purchase more credits',
                 'credit balance is too low', 'quota exceeded', 'limit reached')


FLAG_MARKERS = ('flagged for possible cybersecurity risk', 'content_policy_violation', 'policy violation',
                'violates our usage policy', 'usage policy')


def classify_failure(text):
    lowered = text.lower()
    if any(m in lowered for m in QUOTA_MARKERS):
        return QuotaExhausted
    if any(m in lowered for m in FLAG_MARKERS):
        return ContentFlagged
    if any(m in lowered for m in TRANSIENT_MARKERS):
        return TransientFailure
    return InferenceError


class CLIBackend:
    provider = 'cli'

    def __init__(self, config, budget):
        self.config, self.budget = (config, budget)
        self.calls = []
        self.last_session = None
        # Sessions need a stable working directory for the whole conversation.
        self.workdir = Path(tempfile.mkdtemp(prefix=f'scheme-v8-{self.provider}-'))

    def close(self):
        shutil.rmtree(self.workdir, ignore_errors=True)

    # Subclasses: build the command, then parse (stdout, stderr, answer_file).
    def command(self, schema_path, answer_path, session, fork, persist):
        raise NotImplementedError

    def parse(self, stdout, stderr, answer_path):
        """Return (data or None, usage dict, session id, tools used, compacted, error text)."""
        raise NotImplementedError

    def per_turn(self, usage, session):
        """Usage of this turn only; backends reporting per turn need no change."""
        return usage

    def infer(self, prompt, schema, output: Path, session=None, fork=False, persist=False):
        executable = self.config.get('executable', self.default_executable)
        if not shutil.which(executable):
            raise InferenceError(f'{executable} CLI not found')
        reserved = (len(prompt.encode()) + len(json.dumps(schema))) // 3 + 12000
        self.budget.charge_llm(reserved)
        output.mkdir(parents=True, exist_ok=False)
        (output / 'prompt.txt').write_text(prompt, encoding='utf-8')
        write_json(output / 'schema.json', schema)
        started = time.monotonic()
        record = {'provider': self.provider, 'prompt_hash': digest(prompt.encode()), 'reserved_input_tokens': reserved,
                  'model': self.config['model'], 'reasoning_effort': self.config.get('reasoning_effort', 'medium'),
                  'session_in': session, 'fork': fork, 'session_out': None, 'compacted': False,
                  'tools_used': [], 'usage': None, 'error': None}
        self.calls.append(record)
        try:
            schema_path = self.workdir / f'schema-{len(self.calls)}.json'
            schema_path.write_text(json.dumps(schema), encoding='utf-8')
            answer_path = self.workdir / f'answer-{len(self.calls)}.json'
            args = self.command(schema_path, answer_path, session, fork, persist)
            record['argv'] = args
            env = {k: v for k, v in os.environ.items() if k not in ('CODEX_THREAD_ID', 'CODEX_SESSION_ID', 'CLAUDECODE')}
            remaining = self.budget.limits.seconds - (self.budget.clock() - self.budget.started)
            timeout = min(self.config.get('timeout_seconds', 300), max(1, remaining))
            with subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                  encoding='utf-8', errors='replace', env=env, cwd=self.workdir,
                                  start_new_session=True) as process:
                try:
                    stdout, stderr = process.communicate(prompt, timeout=timeout)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    stdout, stderr = process.communicate()
                    (output / 'events.jsonl').write_text(stdout, encoding='utf-8')
                    (output / 'stderr.log').write_text(stderr, encoding='utf-8')
                    raise TransientFailure(f'Model timeout after {timeout:.1f}s')
            (output / 'events.jsonl').write_text(stdout, encoding='utf-8')
            (output / 'stderr.log').write_text(stderr, encoding='utf-8')
            record['exit_code'] = process.returncode
            data, usage, sid, tools, compacted, error_text = self.parse(stdout, stderr, answer_path)
            usage = self.per_turn(usage, sid)
            record.update(usage=usage, session_out=sid, tools_used=tools, compacted=compacted)
            self.last_session = sid
            if usage and isinstance(usage.get('input_tokens'), int):
                total = usage['input_tokens'] + (usage.get('cached_input_tokens') or 0) + (usage.get('cache_write_input_tokens') or 0)
                self.budget.llm_input_tokens += total - reserved
                if self.budget.llm_input_tokens > self.budget.limits.max_llm_input_tokens:
                    self.budget.fail('llm_actual_input_tokens_exhausted')
            if tools:
                raise InferenceError('Inference attempted prohibited tools: ' + repr(tools))
            if process.returncode or data is None:
                failure = classify_failure(error_text + '\n' + stderr[-4000:])
                raise failure(f'{self.provider} inference failed, exit={process.returncode}: {error_text[:300]}')
            if compacted:
                # Earlier evidence may have been summarized away; never trust this turn.
                raise InferenceError('conversation_compacted')
            write_json(output / 'response.json', data)
            validate_schema(data, schema)
            return data
        except (ValueError, OSError, RuntimeError) as exc:
            record['error'] = str(exc)
            record['error_type'] = type(exc).__name__
            raise
        finally:
            record['seconds'] = round(time.monotonic() - started, 3)
            write_json(output / 'call.json', record)


class CodexCLI(CLIBackend):
    provider = 'codex_cli'
    default_executable = 'codex'
    COUNTERS = ('input_tokens', 'cached_input_tokens', 'cache_write_input_tokens', 'output_tokens', 'reasoning_output_tokens')

    def __init__(self, config, budget):
        super().__init__(config, budget)
        self.thread_totals = {}

    def per_turn(self, usage, session):
        # `codex exec resume` reports usage accumulated over the whole thread
        # (verified: turn 2 input = turn 1 input + its own input). Subtract the
        # previous total of the same thread to obtain this turn's usage.
        # Keyed by the thread id returned by this call, so a new thread's first
        # turn also records its baseline.
        if not usage or not session:
            return usage
        raw = usage['raw']
        previous = self.thread_totals.get(session, {k: 0 for k in self.COUNTERS})
        self.thread_totals[session] = {k: raw.get(k, 0) or 0 for k in self.COUNTERS}
        turn = {k: (raw.get(k, 0) or 0) - previous[k] for k in self.COUNTERS}
        return {'input_tokens': turn['input_tokens'] - turn['cached_input_tokens'],
                'cached_input_tokens': turn['cached_input_tokens'],
                'cache_write_input_tokens': turn['cache_write_input_tokens'],
                'output_tokens': turn['output_tokens'], 'reasoning_output_tokens': turn['reasoning_output_tokens'],
                'raw': raw, 'raw_is_thread_cumulative': bool(self.thread_totals) and any(previous.values())}
    SETTINGS = {'features.shell_tool': 'false', 'features.multi_agent': 'false', 'features.apps': 'false',
                'features.plugins': 'false', 'features.browser_use': 'false', 'features.computer_use': 'false',
                'features.image_generation': 'false', 'features.memories': 'false', 'features.skill_search': 'false',
                'features.skip_host_skill_discovery': 'true', 'features.unbounded_connection_retries': 'false',
                'web_search': '"disabled"', 'project_doc_max_bytes': '0', 'suppress_unstable_features_warning': 'true'}

    def command(self, schema_path, answer_path, session, fork, persist):
        if fork:
            raise InferenceError('codex_cli does not support forking a conversation')
        exe = self.config.get('executable', 'codex')
        effort = {'model_reasoning_effort': json.dumps(self.config.get('reasoning_effort', 'medium'))}
        if session:
            # `exec resume` has no --sandbox/--cd flags; the sandbox is set by config.
            cmd = [exe, '--no-daemon', 'exec', 'resume', '--ignore-user-config', '--ignore-rules',
                   '--skip-git-repo-check', '--model', self.config['model'], '--json',
                   '--output-schema', str(schema_path), '--output-last-message', str(answer_path)]
            settings = {**effort, **self.SETTINGS, 'sandbox_mode': '"read-only"'}
        else:
            # Identical to the v7 command for one-shot calls; persist drops --ephemeral.
            cmd = [exe, '--no-daemon', 'exec'] + ([] if persist else ['--ephemeral']) + [
                   '--ignore-user-config', '--ignore-rules', '--skip-git-repo-check', '--sandbox', 'read-only',
                   '--model', self.config['model'], '--json', '--color', 'never', '--output-schema', str(schema_path),
                   '--output-last-message', str(answer_path), '--cd', str(self.workdir)]
            settings = {**effort, **self.SETTINGS}
        for key, value in settings.items():
            cmd += ['-c', key + '=' + value]
        return cmd + ([session, '-'] if session else ['-'])

    def parse(self, stdout, stderr, answer_path):
        usage, tools, sid, compacted, errors = (None, [], None, False, [])
        for line in stdout.splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = event.get('type', '')
            if kind == 'thread.started':
                sid = event.get('thread_id')
            elif kind == 'turn.completed':
                usage = event.get('usage')
            elif kind in ('error', 'turn.failed'):
                errors.append(event.get('message') or event.get('error', {}).get('message', ''))
            if 'compact' in kind:
                compacted = True
            item = event.get('item', {})
            if kind in ('item.started', 'item.completed'):
                itype = item.get('type', '')
                if itype and itype not in ('agent_message', 'reasoning', 'error'):
                    tools.append(itype)
                if itype == 'error':
                    errors.append(item.get('message', ''))
        normalized = None
        if usage:
            normalized = {'input_tokens': usage.get('input_tokens', 0) - usage.get('cached_input_tokens', 0),
                          'cached_input_tokens': usage.get('cached_input_tokens', 0),
                          'cache_write_input_tokens': usage.get('cache_write_input_tokens', 0),
                          'output_tokens': usage.get('output_tokens', 0),
                          'reasoning_output_tokens': usage.get('reasoning_output_tokens', 0), 'raw': usage}
        data = json.loads(answer_path.read_text()) if answer_path.exists() and answer_path.stat().st_size else None
        return data, normalized, sid, tools, compacted, '\n'.join(errors)


class ClaudeCLI(CLIBackend):
    provider = 'claude_cli'
    default_executable = 'claude'
    SYSTEM = ('You are a static code reviewer for software maintenance: you decide whether a fuzz-testing '
              'harness must be updated after a library change. All evidence is in the user messages. '
              'Answer only with the requested structured output.')

    def command(self, schema_path, answer_path, session, fork, persist):
        exe = self.config.get('executable', 'claude')
        cmd = [exe, '-p', '--output-format', 'json', '--json-schema', schema_path.read_text(),
               '--model', self.config['model'], '--tools', '', '--setting-sources', '',
               '--strict-mcp-config', '--disable-slash-commands', '--system-prompt', self.SYSTEM]
        effort = self.config.get('reasoning_effort')
        if effort:
            cmd += ['--effort', effort]
        if session:
            cmd += ['--resume', session]
            if fork:
                cmd.append('--fork-session')
        elif not persist:
            cmd.append('--no-session-persistence')
        return cmd

    def parse(self, stdout, stderr, answer_path):
        result = {}
        for candidate in (stdout.strip(), (stdout.strip().splitlines() or [''])[-1]):
            try:
                result = json.loads(candidate)
                break
            except json.JSONDecodeError:
                continue
        if isinstance(result, list):
            # Some versions emit the whole message list; the result event is last.
            result = next((m for m in reversed(result) if isinstance(m, dict) and m.get('type') == 'result'), {})
        usage = result.get('usage') or {}
        normalized = None
        if usage:
            normalized = {'input_tokens': usage.get('input_tokens', 0),
                          'cached_input_tokens': usage.get('cache_read_input_tokens', 0),
                          'cache_write_input_tokens': usage.get('cache_creation_input_tokens', 0),
                          'output_tokens': usage.get('output_tokens', 0), 'reasoning_output_tokens': None,
                          'cost_usd_reported': result.get('total_cost_usd'), 'raw': usage}
        data = result.get('structured_output')
        if data is None and isinstance(result.get('result'), str) and not result.get('is_error'):
            try:
                data = json.loads(result['result'])
            except json.JSONDecodeError:
                data = None
        error_text = '' if not result.get('is_error') else str(result.get('result', ''))
        if not result:
            error_text = stdout[-2000:]
        return data, normalized, result.get('session_id'), [], False, error_text


class Retrying:
    """Retry only transient failures; quota and semantic failures propagate."""

    def __init__(self, backend):
        self.backend = backend

    def __getattr__(self, name):
        return getattr(self.backend, name)

    def infer(self, prompt, schema, output, session=None, fork=False, persist=False):
        retries = self.backend.config.get('transient_retries', 3)
        for attempt in range(retries + 1):
            location = output if attempt == 0 else output.with_name(output.name + f'_retry_{attempt}')
            try:
                return self.backend.infer(prompt, schema, location, session=session, fork=fork, persist=persist)
            except TransientFailure:
                if attempt >= retries:
                    raise
                self.backend.budget.check()
                time.sleep(min(30, 5 * 2 ** attempt))


BACKENDS = {'codex_cli': CodexCLI, 'claude_cli': ClaudeCLI}


def make_client(llm_config, budget):
    provider = llm_config.get('provider', 'codex_cli')
    if provider not in BACKENDS:
        raise ValueError('unknown llm provider: ' + provider)
    return Retrying(BACKENDS[provider](llm_config, budget))
