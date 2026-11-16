"""Opt-in synthetic Claude boundary; no provider client, credentials or networking.

See CLAUDE_ADAPTER.md for the trust/configuration contract. Digests bind data;
they do not authenticate a decision or prove that content is de-identified.
"""
from dataclasses import dataclass, field
from contextlib import closing
import hashlib
import json
import math
from pathlib import Path
import queue
import re
import sqlite3
import threading

from scrubber import MAX_CHARS, PATTERNS


class ContractError(ValueError):
    """Fixed error categories only; never embed rejected data."""


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                     separators=(',', ':')).encode('ascii')).hexdigest()


def _payload(value):
    if (type(value) is not dict or set(value) != {'subject', 'body'}
            or any(type(v) is not str for v in value.values())):
        raise ContractError('invalid_payload')
    value = value.copy()
    if not value['body'].strip() or len(value['subject']) + len(value['body']) > MAX_CHARS:
        raise ContractError('invalid_payload')
    if any(re.search(pattern, text) for pattern in PATTERNS for text in value.values()):
        raise ContractError('identifier_detected')
    if any(re.search(r'(?im)^\s*(?:from|to|cc|bcc|reply-to|message-id|received):', text)
           for text in value.values()):
        raise ContractError('routing_detected')
    return value


def payload_digest(payload):
    """Canonical content digest, distinct from CandidateStore's file-byte digest."""
    return _digest(_payload(payload))


def decision_digest(decision):
    if (type(decision) is not dict
            or set(decision) != {'eligible', 'mode', 'candidate_digest', 'policy_version'}
            or type(decision['eligible']) is not bool
            or type(decision['mode']) is not str or decision['mode'] not in {'shadow', 'release'}
            or type(decision['candidate_digest']) is not str
            or not re.fullmatch('[0-9a-f]{64}', decision['candidate_digest'])
            or type(decision['policy_version']) is not str
            or not re.fullmatch('[a-z0-9][a-z0-9._-]{0,63}', decision['policy_version'])):
        raise ContractError('invalid_decision')
    return _digest(decision)


def _action_result(value):
    """Project the actions v1 wire contract without importing its local store."""
    if (type(value) is not dict or set(value) != {'schema_version', 'actions'}
            or type(value['schema_version']) is not int or value['schema_version'] != 1
            or type(value['actions']) is not list or not 1 <= len(value['actions']) <= 20):
        raise ContractError('invalid_response')
    actions = []
    for action in value['actions']:
        if (type(action) is not dict or set(action) != {'kind', 'text'}
                or type(action['kind']) is not str
                or action['kind'] not in {'summarize', 'suggest_organization', 'draft_reply'}
                or type(action['text']) is not str or not action['text'].strip()
                or len(action['text']) > 128 * 1024):
            raise ContractError('invalid_response')
        actions.append(action.copy())
    result = {'schema_version': 1, 'actions': actions}
    if len(json.dumps(result, sort_keys=True, ensure_ascii=True,
                      separators=(',', ':')).encode('ascii')) > 128 * 1024:
        raise ContractError('invalid_response')
    return result


@dataclass(frozen=True)
class AdapterConfig:
    enabled: bool = False
    timeout_seconds: float = 30.0

    def __post_init__(self):
        if (type(self.enabled) is not bool
                or type(self.timeout_seconds) not in {int, float}
                or not math.isfinite(self.timeout_seconds)
                or not 0 < self.timeout_seconds <= 120):
            raise ContractError('invalid_config')


@dataclass(frozen=True)
class AdapterResult:
    status: str
    code: str
    submission_key: str = ''
    # Provider output is untrusted local content, excluded from logs/repr.
    result: dict | None = field(default=None, repr=False)
    stop_reason: str = ''


class FakeTransport:
    """Deterministic synthetic response; no external I/O or content echo."""

    def __call__(self, payload, *, timeout_seconds, idempotency_key):
        return {'result': {'schema_version': 1, 'actions': [
            {'kind': 'summarize', 'text': 'Synthetic workflow assistance.'}]},
                'stop_reason': 'end_turn'}


class ClaudeAdapter:
    def __init__(self, ledger_path, *, config=AdapterConfig(), transport=None):
        if type(config) is not AdapterConfig:
            raise ContractError('invalid_config')
        self.config = config
        self.transport = transport
        # No directory creation or store opening on construction/disabled calls.
        self.ledger_path = Path(ledger_path)

    def _reserve(self, key):
        # Persist BEFORE invoking transport. Crash/timeout reservations are never
        # automatically cleared, including when a new adapter process starts.
        with closing(sqlite3.connect(self.ledger_path, timeout=0.1)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS submissions '
                       '(key TEXT PRIMARY KEY, status TEXT NOT NULL)')
            try:
                db.execute('INSERT INTO submissions VALUES (?, ?)', (key, 'unknown'))
            except sqlite3.IntegrityError:
                return False
        return True

    def _finish(self, key, status):
        with closing(sqlite3.connect(self.ledger_path, timeout=0.1)) as db, db:
            db.execute('UPDATE submissions SET status=? WHERE key=?', (status, key))

    def submit(self, payload, decision, *, expected_candidate_digest, expected_decision_digest):
        if not self.config.enabled:
            return AdapterResult('disabled', 'transport_disabled')
        try:
            content = _payload(payload)
            # Copy validated inputs before any asynchronous execution.
            bound_decision = dict(decision) if type(decision) is dict else decision
            digest = decision_digest(bound_decision)
            candidate = _digest(content)
            if (candidate != expected_candidate_digest
                    or bound_decision['candidate_digest'] != candidate
                    or digest != expected_decision_digest):
                raise ContractError('digest_mismatch')
            if not bound_decision['eligible'] or bound_decision['mode'] != 'release':
                raise ContractError('not_eligible')
        except ContractError as error:
            return AdapterResult('blocked', str(error))
        if not callable(self.transport):
            return AdapterResult('disabled', 'transport_missing')
        # One submission per content even if a policy decision changes. This
        # conservative rule prevents a new decision from bypassing an unknown send.
        key = _digest({'adapter': 'claude-v1', 'candidate_digest': candidate})
        try:
            if not self._reserve(key):
                return AdapterResult('duplicate', 'already_reserved', key)
        except (OSError, sqlite3.Error):
            return AdapterResult('blocked', 'ledger_unavailable')

        output = queue.Queue(maxsize=1)

        def invoke():
            try:
                response = self.transport(content, timeout_seconds=self.config.timeout_seconds,
                                          idempotency_key=key)
                if (type(response) is not dict or set(response) != {'result', 'stop_reason'}
                        or type(response['stop_reason']) is not str
                        or response['stop_reason'] not in {'end_turn', 'max_tokens', 'refusal'}):
                    result = AdapterResult('unknown', 'invalid_response', key)
                else:
                    result = AdapterResult('completed', 'response_received', key,
                                           _action_result(response['result']), response['stop_reason'])
            except ContractError:
                result = AdapterResult('unknown', 'invalid_response', key)
            except Exception:
                # Do not propagate transport exceptions, which may contain secrets.
                result = AdapterResult('unknown', 'transport_error', key)
            output.put(result)

        try:
            threading.Thread(target=invoke, daemon=True).start()
            result = output.get(timeout=self.config.timeout_seconds)
        except queue.Empty:
            result = AdapterResult('unknown', 'timeout', key)
        except RuntimeError:
            result = AdapterResult('unknown', 'worker_unavailable', key)
        try:
            self._finish(key, result.status)
        except (OSError, sqlite3.Error):
            # The durable reservation still prevents a retry. A response may
            # exist locally, but persistence could not confirm the final state.
            return AdapterResult('unknown', 'ledger_update_failed', key)
        return result
