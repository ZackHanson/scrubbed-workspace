"""Evaluate built-in synthetic fixtures; stdout is a content-free JSON receipt."""
import argparse
from contextlib import ExitStack, contextmanager, redirect_stdout, redirect_stderr
import io
import json
import re
from pathlib import Path
import socket
import tempfile
import unicodedata
from unittest.mock import patch

import scrubber as s
from holds import REASONS
from .corpus import corpus


VERSION = 'synthetic-v1'
THRESHOLDS = {'privacy_failures_max': 0, 'utility_failures_max': 0,
              'refusal_failures_max': 0, 'schema_failures_max': 0,
              'execution_errors_max': 0,
              'useful_candidates_required': sum(bool(f.meaning) for f in corpus()),
              'correct_refusals_required': sum(bool(f.reason) for f in corpus())}


def normalized(value):
    return ''.join(char for char in unicodedata.normalize('NFKD', value).casefold()
                   if char.isalnum())


def assess(fixture, record=None, reason=None, error=False):
    """Return only fixed enums/counts and a built-in ID; never output content."""
    schema = (type(record) is dict and set(record) == {'status', 'subject', 'body'}
              and record.get('status') == 'needs_local_review'
              and type(record.get('subject')) is str and type(record.get('body')) is str
              and bool(record['body'].strip())) if record is not None else None
    text = '\n'.join((record['subject'], record['body'])) if schema else ''
    compact = normalized(text)
    # Check all corpus canaries too: leakage from another fixture must fail.
    forbidden = {token for item in corpus() for token in item.forbidden}
    forbidden.update(('fixture-route@example.invalid', 'fixture-destination@example.invalid',
                      'fixture-tracking@example.invalid'))
    leaks = sum(normalized(token) in compact for token in forbidden) if schema else 0
    privacy = 'fail' if error or schema is False or leaks else 'pass'
    utility = 'not_applicable'
    if fixture.meaning:
        utility = 'pass' if (schema and not error and all(
            any(normalized(alternative) in compact for alternative in group)
            for group in fixture.meaning)) else 'fail'
    refusal = 'not_applicable'
    if fixture.reason:
        refusal = 'pass' if record is None and not error and reason == fixture.reason else 'fail'
    return {'fixture_id': fixture.id,
            'outcome': 'error' if error else ('candidate' if record is not None else 'blocked'),
            'reason': reason if reason in REASONS else None,
            'privacy': privacy, 'utility': utility, 'refusal': refusal,
            'schema': 'not_applicable' if schema is None else ('pass' if schema else 'fail'),
            'identifier_matches': leaks}


def mock_api(fixture):
    """Mock transport, preserving production JSON/type/truncation validation."""
    def call(route, payload=None):
        if route != '/api/chat':
            raise AssertionError('Unexpected synthetic API route')
        audit = payload['format'] == s.CHECK_SCHEMA
        fault = fixture.fault
        if fault == 'timeout' or (audit and fault == 'audit_timeout'):
            raise TimeoutError('synthetic-only error payload must never enter receipts')
        if fault == 'json' or (audit and fault == 'audit_json'):
            return {'done': True, 'done_reason': 'stop', 'message': {'content': '{invalid'}}
        if audit:
            value = {'suspected_phi': fault == 'audit_phi', 'uncertain': fault == 'audit_uncertain'}
        else:
            value = {'subject': 'General request', 'body': fixture.reference,
                     'uncertain': fault == 'uncertain'}
            if fault == 'extra_field':
                value['unexpected'] = 'synthetic payload'
            elif fault == 'wrong_type':
                value['uncertain'] = 'false'
            elif fault == 'empty':
                value['body'] = ' '
            elif fault == 'identifier':
                value['body'] = 'Contact leak@example.invalid'
        return {'done': True, 'done_reason': 'length' if fault == 'truncated' else 'stop',
                'message': {'content': json.dumps(value)}}
    return call


@contextmanager
def live_guard():
    """One evaluator process at a time; reject changed model/endpoint/addresses."""
    if s.ENDPOINT != 'http://127.0.0.1:11434' or s.MODEL != 'qwen3.5:9b-q4_K_M':
        raise RuntimeError('live_configuration_rejected')
    lock = Path(tempfile.gettempdir()) / 'scrubbed-synthetic-evaluation.lock'
    # Exclusive creation, no stale-lock deletion: an existing owner fails closed.
    handle = lock.open('x')
    try:
        with ExitStack() as stack:
            original_connect = socket.socket.connect

            def connect(sock, address):
                if address != ('127.0.0.1', 11434):
                    raise OSError('non_loopback_rejected')
                return original_connect(sock, address)

            stack.enter_context(patch.object(socket.socket, 'connect', connect))
            stack.enter_context(patch.object(socket.socket, 'connect_ex', side_effect=OSError('non_loopback_rejected')))
            digest = s.ensure_local_model()
            if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
                raise RuntimeError('live_model_identity_rejected')
            original_api = s.api

            def pinned_api(route, payload=None):
                # Metadata uses this same proxy-free client; only chat is wrapped.
                if route == '/api/chat' and s.ensure_local_model() != digest:
                    raise s.Blocked('model_error')
                result = original_api(route, payload)
                if route == '/api/chat' and s.ensure_local_model() != digest:
                    raise s.Blocked('model_error')
                return result

            stack.enter_context(patch.object(s, 'api', side_effect=pinned_api))
            yield digest
    finally:
        handle.close()  # Windows cannot unlink an open lock file.
        lock.unlink()


def summarize(rows, mode):
    counts = {dimension: {result: sum(row[dimension] == result for row in rows)
                          for result in ('pass', 'fail', 'not_applicable')}
              for dimension in ('privacy', 'utility', 'refusal', 'schema')}
    errors = sum(row['outcome'] == 'error' for row in rows)
    passed = bool(rows) and not errors and all(counts[key]['fail'] == 0 for key in counts)
    # Coverage is mandatory: an empty/partial/all-refusal report cannot pass.
    complete = [row['fixture_id'] for row in rows] == [f.id for f in corpus()]
    passed = (passed and complete and counts['privacy']['pass'] == len(corpus())
              and counts['utility']['pass'] == THRESHOLDS['useful_candidates_required']
              and counts['refusal']['pass'] == THRESHOLDS['correct_refusals_required'])
    return {'receipt_version': VERSION, 'mode': mode, 'scope': 'synthetic_regression_only',
            'certification': False, 'thresholds': dict(THRESHOLDS),
            'complete': complete, 'passed': passed, 'counts': counts,
            'execution_errors': errors, 'fixtures': rows}


def run(live=False):
    """No path input. Only built-in bytes; no candidates are persisted or released."""
    rows = []
    with tempfile.TemporaryDirectory(prefix='scrubbed-evaluation-') as folder, ExitStack() as stack:
        stack.enter_context(patch.object(s, 'STATE', Path(folder)))
        # Defensive capture: future core diagnostics must not escape into receipts.
        stack.enter_context(redirect_stdout(io.StringIO()))
        stack.enter_context(redirect_stderr(io.StringIO()))
        digest = None
        if live:
            digest = stack.enter_context(live_guard())
        else:
            stack.enter_context(patch.object(socket.socket, 'connect', side_effect=OSError('network_disabled')))
            stack.enter_context(patch.object(socket.socket, 'connect_ex', side_effect=OSError('network_disabled')))
        for fixture in corpus():  # Deliberately serial, never concurrent inference.
            record, reason, error = None, None, False
            with ExitStack() as local:
                if not live or fixture.fault or fixture.reason:
                    local.enter_context(patch.object(s, 'api', side_effect=mock_api(fixture)))
                try:
                    record = s.scrub(fixture.raw)
                except s.Blocked as blocked:
                    reason = blocked.code if blocked.code in REASONS else 'processing_failed'
                except Exception:
                    error = True
                row = assess(fixture, record, reason, error)
                row['execution'] = 'injected_fault' if fixture.fault else ('live' if live and not fixture.reason else 'mocked')
                rows.append(row)
        if list(Path(folder).iterdir()):
            raise RuntimeError('unexpected_evaluation_state')
    receipt = summarize(rows, 'live_qwen' if live else 'mocked_contract')
    if live:
        receipt['model_digest'] = digest
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live-qwen', action='store_true', help='Explicit serial local inference on synthetic fixtures')
    args = parser.parse_args(argv)
    try:
        receipt = run(live=args.live_qwen)
    except Exception:
        # Includes unavailable model, held experiment lock and endpoint rejection.
        receipt = {'receipt_version': VERSION, 'scope': 'synthetic_regression_only',
                   'certification': False, 'passed': False, 'error': 'evaluation_unavailable'}
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
