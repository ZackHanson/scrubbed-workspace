"""Manually started, five-fixture synthetic pilot. No general release path.

Only this module knows how to construct a real HTTPS transport. Importing it,
dry runs and shadow calls never construct one. See PILOT.md before live use.
"""
import argparse
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, asdict
import getpass
import hashlib
import http.client
import json
import math
from pathlib import Path
import re
import sqlite3
import ssl
import time
import uuid
import warnings

from actions import ActionStore, result_digest
from claude_adapter import (AdapterConfig, ClaudeAdapter,
                            decision_digest, payload_digest, submission_key)


POLICY = 'synthetic-nonclinical-pilot-v1'
HOST = 'api.anthropic.com'
RESOURCE = '/v1/messages'
MAX_REQUEST_BYTES = 16_384
MAX_RESPONSE_BYTES = 65_536
SYSTEM = ('You assist with invented nonclinical office workflows only. Return only '
          'a JSON object with schema_version equal to 1 and actions: a nonempty '
          'array of objects with exactly kind and text. kind must be summarize, '
          'suggest_organization, or draft_reply. Text is an inert local suggestion. '
          'Do not call tools, send messages, schedule anything, or give medical advice.')
_FIXTURES = (
    ('summary', 'Workshop planning',
     'Summarize this invented office workshop plan: choose a topic, prepare slides, and collect feedback.'),
    ('organize', 'Supply cupboard',
     'Suggest how an imaginary office could organize stationery into paper, pens, and reusable supplies.'),
    ('reply', 'Reading club',
     'Draft a friendly body-only reply thanking an imaginary reading club for suggesting a book.'),
    ('checklist', 'Practice presentation',
     'Suggest a checklist for rehearsing an invented presentation: check slides, timing, and sound.'),
    ('compare', 'Fictional filing workflow',
     'Summarize the tradeoffs between alphabetical and topic-based filing for imaginary office templates.'),
)
FIXTURE_IDS = tuple(row[0] for row in _FIXTURES)


class PilotError(Exception):
    """Fixed public category, never provider text or configuration values."""


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True).encode('ascii')).hexdigest()


def fixture(request_id):
    for name, subject, body in _FIXTURES:
        if type(request_id) is str and request_id == name:
            return {'subject': subject, 'body': body}
    raise PilotError('fixture_required')


def _scope(request_id):
    # Independent of config, policy, credentials and process lifetime.
    return _hash(['bounded-pilot-request', request_id])[:32]


def _fixed_payload(payload):
    if type(payload) is not dict or not any(payload == fixture(i) for i in FIXTURE_IDS):
        raise PilotError('fixture_required')
    return dict(payload)


@dataclass(frozen=True, repr=False)
class PilotConfig:
    enabled: bool = False
    account: str = ''  # Local nonsecret approval alias; never in the provider payload.
    model: str = ''
    workspace_id: str = ''
    api_version: str = '2026-10-21'
    max_tokens: int = 512
    timeout_seconds: float = 30.0
    spend_approved: bool = False

    def __repr__(self):
        return 'PilotConfig(<local approval configuration>)'

    def validate(self):
        if (type(self.enabled) is not bool or type(self.spend_approved) is not bool
                or type(self.max_tokens) is not int or not 1 <= self.max_tokens <= 1024
                or type(self.timeout_seconds) not in {float, int}
                or not math.isfinite(self.timeout_seconds)
                or not 1 <= self.timeout_seconds <= 60
                or self.api_version != '2026-10-21'
                or type(self.account) is not str
                or not re.fullmatch('[a-z0-9][a-z0-9_-]{0,63}', self.account)
                or type(self.model) is not str
                or not re.fullmatch('claude-[a-z0-9][a-z0-9-]{0,95}', self.model)
                or type(self.workspace_id) is not str
                or (self.workspace_id and not re.fullmatch('wrkspc_[A-Za-z0-9]{1,96}', self.workspace_id))):
            raise PilotError('approval_config_required')


def _json_loads(raw):
    def pairs(items):
        output = {}
        for key, value in items:
            if key in output:
                raise PilotError('invalid_response')
            output[key] = value
        return output
    def constant(_):
        raise PilotError('invalid_response')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


class AnthropicHTTPS:
    """One POST, fixed TLS origin, no redirects, proxies, tools or retries."""
    def __init__(self, config, *, api_key):
        config.validate()
        if (not config.enabled or not config.spend_approved or type(api_key) is not str
                or not 16 <= len(api_key) <= 512
                or not re.fullmatch('[A-Za-z0-9_-]+', api_key)):
            raise PilotError('memory_key_and_approval_required')
        self._config = config
        self._key = api_key

    def __repr__(self):
        return 'AnthropicHTTPS(<memory-only credential>)'

    def __call__(self, payload, *, timeout_seconds, idempotency_key):
        # Adapter correlation stays local; this is not a provider idempotency promise.
        content = _fixed_payload(payload)
        cfg = self._config
        if timeout_seconds != cfg.timeout_seconds:
            raise PilotError('config_mismatch')
        body = json.dumps({'model': cfg.model, 'max_tokens': cfg.max_tokens,
                           'stream': False, 'system': SYSTEM,
                           'messages': [{'role': 'user', 'content': json.dumps(content)}]},
                          ensure_ascii=True).encode('ascii')
        if len(body) > MAX_REQUEST_BYTES:
            raise PilotError('request_too_large')
        connection = None
        try:
            deadline = time.monotonic() + timeout_seconds
            connection = http.client.HTTPSConnection(
                HOST, port=443, timeout=timeout_seconds, context=ssl.create_default_context())
            headers = {'x-api-key': self._key, 'anthropic-version': cfg.api_version,
                       'content-type': 'application/json', 'accept': 'application/json',
                       'accept-encoding': 'identity'}
            if cfg.workspace_id:
                headers['anthropic-workspace-id'] = cfg.workspace_id
            connection.request('POST', RESOURCE, body=body, headers=headers)
            response = connection.getresponse()
            # Never read/log error bodies, Location or provider request IDs.
            if response.status != 200:
                raise PilotError('provider_error')
            if (response.getheader('Content-Type', '').split(';')[0].strip().lower()
                    != 'application/json'
                    or response.getheader('Content-Encoding', 'identity') != 'identity'):
                raise PilotError('invalid_response')
            length = response.getheader('Content-Length')
            if length is not None and (not length.isdigit() or int(length) > MAX_RESPONSE_BYTES):
                raise PilotError('response_too_large')
            chunks = bytearray()
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise PilotError('timeout')
                if connection.sock is not None:
                    connection.sock.settimeout(remaining)
                chunk = response.read1(min(4096, MAX_RESPONSE_BYTES + 1 - len(chunks)))
                if not chunk:
                    break
                chunks.extend(chunk)
                if len(chunks) > MAX_RESPONSE_BYTES:
                    raise PilotError('response_too_large')
            raw = bytes(chunks).decode('utf-8')
            # No echoed credential, even inside unused provider metadata, reaches disk.
            if self._key in raw or re.search(r'sk-ant-[A-Za-z0-9_-]+', raw):
                raise PilotError('credential_echo')
            envelope = _json_loads(raw)
            decoded = json.dumps(envelope, ensure_ascii=False)
            if self._key in decoded or re.search(r'sk-ant-[A-Za-z0-9_-]+', decoded):
                raise PilotError('credential_echo')
            if (type(envelope) is not dict or envelope.get('type') != 'message'
                    or envelope.get('role') != 'assistant' or envelope.get('model') != cfg.model
                    or envelope.get('stop_reason') != 'end_turn'
                    or type(envelope.get('content')) is not list or len(envelope['content']) != 1):
                raise PilotError('invalid_response')
            block = envelope['content'][0]
            if (type(block) is not dict or block.get('type') != 'text'
                    or set(block) - {'type', 'text', 'citations'}
                    or block.get('citations') not in (None, []) or type(block.get('text')) is not str):
                raise PilotError('invalid_response')
            result = _json_loads(block['text'])
            decoded_result = json.dumps(result, ensure_ascii=False)
            if self._key in decoded_result or re.search(r'sk-ant-[A-Za-z0-9_-]+', decoded_result):
                raise PilotError('credential_echo')
            result_digest(result)  # Strict ResultV1; no tool execution or routing fields.
            return {'result': result, 'stop_reason': 'end_turn'}
        except Exception:
            # Exceptions can carry a key, provider body, socket details or local paths.
            raise PilotError('provider_response_unavailable') from None
        finally:
            if connection is not None:
                try:
                    connection.close()
                except Exception:
                    pass


@contextmanager
def _active(root):
    # Sibling is intentionally optional until integration. Do not mask its failures.
    try:
        from recovery_guard import require_active, active_state
    except ModuleNotFoundError as error:
        if error.name != 'recovery_guard':
            raise
        guard = nullcontext()
    else:
        require_active(root)
        guard = active_state(root)
    with guard:
        yield


class Pilot:
    """Trusted local fixture authorization, separate from routing's release policy.

    Use one designated private state directory for the entire pilot, never reset it.
    A crash while active permanently halts this state; no recovery resends requests.
    """
    def __init__(self, root, config=PilotConfig(), *, transport=None):
        self._selected_root = Path(root).absolute()
        self.root = Path(root).resolve()
        self.config = config
        self._transport = transport
        self._session = None
        # No filesystem access/creation on import, construction, dry run or shadow.

    @contextmanager
    def _db(self):
        self._check_path()
        with _active(self.root):
            db = sqlite3.connect(self.root / 'pilot.sqlite', timeout=0.1)
            try:
                db.execute('PRAGMA synchronous=FULL')
                db.execute('BEGIN IMMEDIATE')
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise
            finally:
                db.close()

    def _check_path(self):
        source = Path(__file__).resolve().parent
        if (self.root == source or source in self.root.parents
                or not self.root.is_dir()
                or any(p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction())
                       for p in (self._selected_root, *self._selected_root.parents))
                or any((p / '.git').exists() for p in (self.root, *self.root.parents))
                or (self.root / 'pilot.sqlite').is_symlink()):
            raise PilotError('private_state_required')

    def start(self):
        cfg = self.config
        if not cfg.enabled:
            return {'status': 'disabled', 'attempts': 0}
        cfg.validate()
        if not cfg.spend_approved or not callable(self._transport):
            raise PilotError('memory_transport_and_approval_required')
        # Never share an existing application database or create state inside source.
        self._check_path()
        if not (self.root / 'pilot.sqlite').exists() and any(self.root.iterdir()):
            raise PilotError('private_state_required')
        with self._db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS pilot '
                       '(id INTEGER PRIMARY KEY CHECK(id=1), config TEXT, status TEXT, session TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS pilot_attempts '
                       '(id TEXT PRIMARY KEY, digest TEXT, scope TEXT, status TEXT)')
            binding = _hash([asdict(cfg), POLICY, _FIXTURES, SYSTEM])
            row = db.execute('SELECT config,status FROM pilot WHERE id=1').fetchone()
            if row is None:
                db.execute('INSERT INTO pilot VALUES (1,?,?,NULL)', (binding, 'paused'))
                row = (binding, 'paused')
            count = db.execute('SELECT count(*) FROM pilot_attempts').fetchone()[0]
            if row[0] != binding or row[1] != 'paused' or count >= 5:
                db.execute("UPDATE pilot SET status='halted',session=NULL WHERE id=1")
                receipt = {'status': 'halted', 'attempts': count}
            else:
                self._session = uuid.uuid4().hex
                db.execute("UPDATE pilot SET status='active',session=? WHERE id=1", (self._session,))
                receipt = {'status': 'started', 'attempts': count}
        return receipt

    def pause(self):
        """Clean session exit; remaining unused fixtures need a new explicit start."""
        if self._session is None:
            return
        with self._db() as db:
            db.execute("UPDATE pilot SET status='paused',session=NULL WHERE id=1 "
                       "AND session=? AND status='active' AND NOT EXISTS "
                       "(SELECT 1 FROM pilot_attempts WHERE status='unknown')", (self._session,))
        self._session = None

    def stop(self):
        """Terminal stop, including another process's active session. No reset API."""
        if not (self.root / 'pilot.sqlite').is_file():
            raise PilotError('pilot_state_required')
        with self._db() as db:
            db.execute("UPDATE pilot SET status='stopped',session=NULL WHERE id=1")
        self._session = None
        return {'status': 'stopped'}

    def submit(self, request_id, *, mode='dry-run'):
        payload = fixture(request_id)
        if mode in {'dry-run', 'shadow'}:
            return {'status': mode, 'fixture': request_id, 'attempts': 0}
        if mode != 'pilot':
            raise PilotError('invalid_mode')
        if not self.config.enabled or self._session is None:
            return {'status': 'disabled', 'fixture': request_id}
        # Recovery guard covers reservation, dispatch, result and proposal capture.
        with _active(self.root):
            return self._submit(request_id, payload)

    def _submit(self, request_id, payload):
        digest, scope = payload_digest(payload), _scope(request_id)
        with self._db() as db:
            row = db.execute('SELECT status,session,config FROM pilot WHERE id=1').fetchone()
            count = db.execute('SELECT count(*) FROM pilot_attempts').fetchone()[0]
            binding = _hash([asdict(self.config), POLICY, _FIXTURES, SYSTEM])
            if row[2] != binding:
                db.execute("UPDATE pilot SET status='halted',session=NULL WHERE id=1")
                return {'status': 'halted', 'attempts': count}
            if row[:2] != ('active', self._session):
                return {'status': 'halted', 'attempts': count}
            if db.execute('SELECT 1 FROM pilot_attempts WHERE id=?', (request_id,)).fetchone():
                return {'status': 'duplicate', 'fixture': request_id, 'attempts': count}
            if count >= 5 or db.execute("SELECT 1 FROM pilot_attempts WHERE status='unknown'").fetchone():
                db.execute("UPDATE pilot SET status='halted',session=NULL WHERE id=1")
                return {'status': 'halted', 'attempts': count}
            db.execute('INSERT INTO pilot_attempts VALUES (?,?,?,?)',
                       (request_id, digest, scope, 'unknown'))
            count += 1
        # Reservation commits before thread/network creation. Every later failure counts.
        try:
            adapter = ClaudeAdapter(self.root / 'pilot.sqlite',
                                    config=AdapterConfig(True, self.config.timeout_seconds),
                                    transport=self._transport)
            decision = {'eligible': True, 'mode': 'release', 'candidate_digest': digest,
                        'policy_version': POLICY}
            output = adapter.submit(payload, decision, expected_candidate_digest=digest,
                                    expected_decision_digest=decision_digest(decision), request_scope=scope)
            good = (output.status == 'completed' and output.stop_reason == 'end_turn'
                    and output.submission_key == submission_key(payload, request_scope=scope))
            if good:
                captured = adapter.captured(output.submission_key)
                version = result_digest(captured.result)
                store = ActionStore(self.root / 'pilot.sqlite')
                # Entirely invented local source identity; no inbox/file is ever read.
                source = {'kind': 'file', 'path': str(self.root / ('fixture-' + request_id + '.eml')),
                          'sha256': digest}
                store.bind_candidate(candidate_id=request_id, candidate_version=digest,
                                     source_ref=source, source_version=digest)
                store.capture_result(candidate_id=request_id, candidate_version=digest,
                                     result_id=output.submission_key, result_version=version,
                                     result=captured.result)
                store.propose(request_id=request_id, candidate_id=request_id, candidate_version=digest,
                              result_id=output.submission_key, result_version=version)
        except Exception:
            good = False
        with self._db() as db:
            db.execute('UPDATE pilot_attempts SET status=? WHERE id=?',
                       ('completed' if good else 'unknown', request_id))
            if not good or count >= 5:
                db.execute("UPDATE pilot SET status='halted',session=NULL WHERE id=1")
        return {'status': 'captured' if good else 'halted', 'fixture': request_id, 'attempts': count}


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's usual error includes arbitrary rejected argument values.
        self.exit(2, 'invalid_pilot_arguments\n')


def main(argv=None):
    parser = _Parser(description=__doc__)
    parser.add_argument('command', choices=['dry-run', 'shadow', 'run', 'stop'], nargs='?', default='dry-run')
    parser.add_argument('--request', choices=FIXTURE_IDS, default='summary')
    parser.add_argument('--state', type=Path)
    parser.add_argument('--account', default='')
    parser.add_argument('--model', default='')
    parser.add_argument('--workspace-id', default='')
    parser.add_argument('--max-tokens', type=int, default=512)
    parser.add_argument('--approve-spend', action='store_true')
    args = parser.parse_args(argv)
    if args.command in {'dry-run', 'shadow'}:
        print(json.dumps(Pilot(Path('.')).submit(args.request, mode=args.command)))
        return 0
    pilot = None
    try:
        if args.state is None:
            raise PilotError('private_state_required')
        if args.command == 'stop':
            print(json.dumps(Pilot(args.state).stop()))
            return 0
        cfg = PilotConfig(enabled=True, account=args.account, model=args.model,
                          workspace_id=args.workspace_id, max_tokens=args.max_tokens,
                          spend_approved=args.approve_spend)
        cfg.validate()
        if not cfg.spend_approved:
            raise PilotError('spend_approval_required')
        # Never read environment, CLI token, key file or stdin; fail if echo-free input is unavailable.
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            key = getpass.getpass('Approved Anthropic API key (hidden, memory only): ')
        transport = AnthropicHTTPS(cfg, api_key=key)
        del key
        pilot = Pilot(args.state, cfg, transport=transport)
        receipt = pilot.start()
        if receipt['status'] == 'started':
            receipt = pilot.submit(args.request, mode='pilot')
        print(json.dumps(receipt))
        return 0 if receipt['status'] == 'captured' else 1
    except (Exception, KeyboardInterrupt):
        # No traceback, repr(exception), result text, key or state path in receipts.
        print('{"status":"halted","code":"local_pilot_unavailable"}')
        return 1
    finally:
        if pilot is not None:
            try:
                pilot.pause()
            except Exception:
                pass  # Durable active/unknown state will halt a later start.


if __name__ == '__main__':
    raise SystemExit(main())
