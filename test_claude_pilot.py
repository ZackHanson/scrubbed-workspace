import contextlib
from dataclasses import replace
import io
import json
from pathlib import Path
import socket
import sqlite3
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import Mock, patch

import claude_pilot as cp
from claude_adapter import FakeTransport


KEY = 'sk-ant-synthetic-test-key-never-real'
RESULT = {'schema_version': 1, 'actions': [{'kind': 'summarize', 'text': 'Invented office plan.'}]}


class Response:
    status = 200

    def __init__(self, raw, headers=None):
        self.raw = raw
        self.headers = headers or {'Content-Type': 'application/json'}
        self.reads = 0

    def getheader(self, name, default=None):
        return self.headers.get(name, default)

    def read1(self, count):
        self.reads += 1
        out, self.raw = self.raw[:count], self.raw[count:]
        return out


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cfg = cp.PilotConfig(True, 'approved-test-account', 'claude-synthetic-test',
                                  spend_approved=True, timeout_seconds=1)
        self.transport = Mock(side_effect=FakeTransport())
        self.addCleanup(patch.stopall)
        patch.object(socket.socket, 'connect', side_effect=AssertionError('socket_forbidden')).start()
        patch.object(socket.socket, 'connect_ex', side_effect=AssertionError('socket_forbidden')).start()

    def pilot(self, cfg=None, transport=None):
        return cp.Pilot(self.root, cfg or self.cfg,
                        transport=transport if transport is not None else self.transport)

    def start(self, **kw):
        pilot = self.pilot(**kw)
        self.assertEqual(pilot.start()['status'], 'started')
        return pilot

    def rows(self, query):
        with contextlib.closing(sqlite3.connect(self.root / 'pilot.sqlite')) as db:
            return db.execute(query).fetchall()

    def test_default_disabled_shadow_and_dry_run_no_side_effects(self):
        pilot = cp.Pilot(self.root / 'missing', transport=self.transport)
        self.assertEqual(pilot.start()['status'], 'disabled')
        for mode in ('shadow', 'dry-run', 'pilot'):
            self.assertIn(pilot.submit('summary', mode=mode)['status'], (mode, 'disabled'))
        self.assertFalse((self.root / 'missing').exists())
        self.transport.assert_not_called()

    def test_shadow_never_calls_transport_even_after_start(self):
        pilot = self.start()
        for name in cp.FIXTURE_IDS:
            pilot.submit(name, mode='shadow')
        self.transport.assert_not_called()
        self.assertEqual(self.rows('SELECT count(*) FROM pilot_attempts'), [(0,)])
        pilot.pause()

    def test_only_five_fixed_fixtures_and_no_text_paths_or_inbox(self):
        self.assertEqual(len(cp.FIXTURE_IDS), 5)
        for value in ('arbitrary request', 'inbox', str(self.root), {}, None):
            with self.assertRaisesRegex(cp.PilotError, '^fixture_required$'):
                self.pilot().submit(value, mode='pilot')
        for bad in ({'subject': 'x', 'body': 'free text'},
                    {**cp.fixture('summary'), 'to': 'invented'}, 'text'):
            with self.assertRaises(cp.PilotError):
                cp._fixed_payload(bad)
        copy = cp.fixture('summary')
        copy['body'] = 'changed'
        self.assertNotEqual(copy, cp.fixture('summary'))
        self.transport.assert_not_called()

    def test_max_five_and_private_captured_results_inert_proposals(self):
        pilot = self.start()
        for index, name in enumerate(cp.FIXTURE_IDS, 1):
            receipt = pilot.submit(name, mode='pilot')
            self.assertEqual(receipt, {'status': 'captured', 'fixture': name, 'attempts': index})
            self.assertNotIn('Synthetic workflow assistance', json.dumps(receipt))
        self.assertEqual(self.transport.call_count, 5)
        self.assertEqual(self.rows('SELECT count(*) FROM proposals'), [(5,)])
        self.assertEqual(self.rows('SELECT status FROM pilot'), [('halted',)])
        self.assertEqual(pilot.submit('summary', mode='pilot')['status'], 'halted')
        self.assertEqual(self.pilot().start(), {'status': 'halted', 'attempts': 5})
        self.assertEqual(self.transport.call_count, 5)

    def test_duplicate_across_clean_restart_no_resubmission(self):
        pilot = self.start()
        pilot.submit('summary', mode='pilot')
        scope = self.rows('SELECT scope FROM pilot_attempts')[0][0]
        pilot.pause()
        restarted = self.start()
        self.assertEqual(restarted.submit('summary', mode='pilot')['status'], 'duplicate')
        self.assertEqual(self.rows('SELECT scope FROM pilot_attempts'), [(scope,)])
        self.assertEqual(self.transport.call_count, 1)
        self.assertEqual(restarted.submit('organize', mode='pilot')['status'], 'captured')
        restarted.pause()

    def test_unknown_exception_counts_and_restart_halts_all_remaining(self):
        failure = Mock(side_effect=RuntimeError(KEY))
        pilot = self.start(transport=failure)
        receipt = pilot.submit('summary', mode='pilot')
        self.assertEqual(receipt, {'status': 'halted', 'fixture': 'summary', 'attempts': 1})
        pilot.pause()
        self.assertEqual(self.pilot().start(), {'status': 'halted', 'attempts': 1})
        self.assertEqual(self.rows('SELECT status FROM pilot_attempts'), [('unknown',)])
        self.assertNotIn(KEY.encode(), (self.root / 'pilot.sqlite').read_bytes())
        self.transport.assert_not_called()

    def test_crash_after_reservation_before_transport_is_unknown_on_restart(self):
        pilot = self.start()
        with patch.object(cp.ClaudeAdapter, 'submit', side_effect=SystemExit()):
            with self.assertRaises(SystemExit):
                pilot.submit('summary', mode='pilot')
        self.assertEqual(self.rows('SELECT status FROM pilot_attempts'), [('unknown',)])
        self.assertEqual(self.pilot().start(), {'status': 'halted', 'attempts': 1})
        self.transport.assert_not_called()

    def test_unclean_session_restart_without_attempt_also_halts(self):
        self.start()
        self.assertEqual(self.pilot().start(), {'status': 'halted', 'attempts': 0})
        self.transport.assert_not_called()

    def test_changed_model_account_policy_and_tokens_cannot_reset(self):
        for change in ({'model': 'claude-other-test'}, {'account': 'other-account'}, {'max_tokens': 123}):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                self.root = Path(tmp)
                first = self.start()
                first.submit('summary', mode='pilot')
                first.pause()
                changed = self.pilot(cfg=replace(self.cfg, **change))
                self.assertEqual(changed.start()['status'], 'halted')
        self.root = Path(self.temp.name)
        first = self.start()
        first.pause()
        with patch.object(cp, 'POLICY', 'synthetic-nonclinical-pilot-v2'):
            self.assertEqual(self.pilot().start()['status'], 'halted')

    def test_mid_session_config_change_halts_before_transport(self):
        pilot = self.start()
        pilot.config = replace(self.cfg, max_tokens=256)
        self.assertEqual(pilot.submit('summary', mode='pilot')['status'], 'halted')
        self.transport.assert_not_called()

    def test_digest_mismatch_counts_but_never_transports(self):
        pilot = self.start()
        with patch.object(cp, 'decision_digest', return_value='0' * 64):
            self.assertEqual(pilot.submit('summary', mode='pilot')['status'], 'halted')
        self.assertEqual(self.rows('SELECT count(*) FROM pilot_attempts'), [(1,)])
        self.transport.assert_not_called()

    def test_refusal_invalid_truncated_all_immediately_halt(self):
        for output in ({'result': RESULT, 'stop_reason': 'refusal'},
                       {'result': RESULT, 'stop_reason': 'max_tokens'},
                       {'result': {'text': 'bad'}, 'stop_reason': 'end_turn'}, None):
            with self.subTest(output=output), tempfile.TemporaryDirectory() as tmp:
                self.root = Path(tmp)
                transport = Mock(return_value=output)
                pilot = self.start(transport=transport)
                self.assertEqual(pilot.submit('summary', mode='pilot')['status'], 'halted')
                self.assertEqual(pilot.submit('organize', mode='pilot')['status'], 'halted')
                self.assertEqual(transport.call_count, 1)
                self.assertEqual(self.rows("SELECT name FROM sqlite_master WHERE name='proposals'"), [])

    def test_one_request_in_flight_concurrent_request_fails_closed(self):
        entered, release = threading.Event(), threading.Event()
        def slow(payload, **kwargs):
            entered.set()
            release.wait(2)
            return FakeTransport()(payload, **kwargs)
        pilot = self.start(transport=slow)
        thread = threading.Thread(target=lambda: pilot.submit('summary', mode='pilot'))
        thread.start()
        self.assertTrue(entered.wait(1))
        try:
            self.assertEqual(pilot.submit('organize', mode='pilot')['status'], 'halted')
        finally:
            release.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(self.rows('SELECT count(*) FROM pilot_attempts'), [(1,)])
        self.assertEqual(self.rows('SELECT status FROM pilot'), [('halted',)])

    def test_timeout_counts_no_retry_even_if_worker_finishes_later(self):
        release = threading.Event()
        def slow(payload, **kwargs):
            release.wait(3)
            return FakeTransport()(payload, **kwargs)
        pilot = self.start(transport=slow)
        try:
            self.assertEqual(pilot.submit('summary', mode='pilot')['status'], 'halted')
            self.assertEqual(self.pilot().start()['status'], 'halted')
        finally:
            release.set()
        self.assertEqual(self.rows('SELECT count(*) FROM pilot_attempts'), [(1,)])

    def test_explicit_stop_terminal_and_cannot_resume(self):
        pilot = self.start()
        self.assertEqual(pilot.stop(), {'status': 'stopped'})
        self.assertEqual(pilot.submit('summary', mode='pilot')['status'], 'disabled')
        self.assertEqual(self.pilot().start()['status'], 'halted')
        self.transport.assert_not_called()

    def test_private_state_must_be_empty_outside_source(self):
        for root in (Path(cp.__file__).parent, self.root / 'missing'):
            with self.assertRaisesRegex(cp.PilotError, '^private_state_required$'):
                cp.Pilot(root, self.cfg, transport=self.transport).start()
        (self.root / 'unrelated').write_text('synthetic')
        with self.assertRaises(cp.PilotError):
            self.pilot().start()

    def test_recovery_guard_hooks_cover_entire_dispatch_and_nested_mutations(self):
        depth = [0]
        @contextlib.contextmanager
        def active(root):
            depth[0] += 1
            try:
                yield
            finally:
                depth[0] -= 1
        def transport(payload, **kwargs):
            self.assertGreater(depth[0], 0)
            return FakeTransport()(payload, **kwargs)
        guard = types.SimpleNamespace(require_active=Mock(), active_state=active)
        with patch.dict(sys.modules, {'recovery_guard': guard}):
            pilot = self.start(transport=transport)
            self.assertEqual(pilot.submit('summary', mode='pilot')['status'], 'captured')
            pilot.pause()
            guard.require_active.assert_called_with(self.root)
        self.assertEqual(depth[0], 0)
        guard = types.SimpleNamespace(require_active=Mock(side_effect=RuntimeError('quarantined')),
                                      active_state=active)
        with patch.dict(sys.modules, {'recovery_guard': guard}):
            with self.assertRaises(RuntimeError):
                self.pilot().start()

    def envelope(self, **changes):
        value = {'type': 'message', 'role': 'assistant', 'model': self.cfg.model,
                 'stop_reason': 'end_turn', 'content': [{'type': 'text', 'text': json.dumps(RESULT)}]}
        value.update(changes)
        return json.dumps(value).encode()

    def https(self, raw=None, headers=None, status=200):
        response = Response(self.envelope() if raw is None else raw, headers)
        response.status = status
        connection = Mock()
        connection.getresponse.return_value = response
        constructor = patch.object(cp.http.client, 'HTTPSConnection', return_value=connection).start()
        transport = cp.AnthropicHTTPS(self.cfg, api_key=KEY)
        return transport, response, connection, constructor

    def invoke(self, transport):
        return transport(cp.fixture('summary'), timeout_seconds=1, idempotency_key='a' * 64)

    def test_https_fixed_origin_tls_headers_bounded_no_proxy_or_redirect(self):
        transport, _, connection, constructor = self.https()
        self.assertEqual(self.invoke(transport), {'result': RESULT, 'stop_reason': 'end_turn'})
        args, kwargs = constructor.call_args
        self.assertEqual(args, ('api.anthropic.com',))
        self.assertEqual(kwargs['port'], 443)
        self.assertTrue(kwargs['context'].check_hostname)
        call = connection.request.call_args
        self.assertEqual(call.args, ('POST', '/v1/messages'))
        self.assertEqual(call.kwargs['headers']['x-api-key'], KEY)
        body = json.loads(call.kwargs['body'])
        self.assertEqual(set(body), {'model', 'max_tokens', 'stream', 'system', 'messages'})
        self.assertEqual(json.loads(body['messages'][0]['content']), cp.fixture('summary'))
        self.assertNotIn(KEY, str(body))
        self.assertNotIn(self.cfg.account, str(body))
        self.assertNotIn('a' * 64, str(body))
        self.assertLess(len(call.kwargs['body']), cp.MAX_REQUEST_BYTES)
        connection.close.assert_called_once()

    def test_all_http_errors_no_body_read_no_retry_and_sanitized(self):
        for status in (301, 302, 307, 400, 401, 403, 429, 500, 529):
            transport, response, connection, _ = self.https(KEY.encode(), status=status)
            with self.assertRaisesRegex(cp.PilotError, '^provider_response_unavailable$'):
                self.invoke(transport)
            self.assertEqual(response.reads, 0)
            connection.request.assert_called_once()
            connection.close.assert_called_once()

    def test_https_credential_echo_literal_and_json_escaped_never_persist(self):
        for text in (KEY, KEY.replace('-', r'\u002d'), KEY.replace('-', r'\\u002d')):
            raw = self.envelope().replace(b'Invented office plan.', text.encode())
            transport, _, _, _ = self.https(raw)
            pilot = self.start(transport=transport)
            self.assertEqual(pilot.submit('summary', mode='pilot')['status'], 'halted')
            self.assertNotIn(KEY.encode(), (self.root / 'pilot.sqlite').read_bytes())
            # New temp state only for the next independent synthetic test scenario.
            self.temp2 = tempfile.TemporaryDirectory()
            self.addCleanup(self.temp2.cleanup)
            self.root = Path(self.temp2.name)

    def test_https_schema_refusal_tools_model_size_and_invalid_json(self):
        raws = [b'not json', b'{}', b'\xff', self.envelope(stop_reason='refusal'),
                self.envelope(stop_reason='max_tokens'), self.envelope(model='claude-other'),
                self.envelope(content=[{'type': 'tool_use', 'name': 'send_email'}]),
                self.envelope(content=[{'type': 'text', 'text': '{"schema_version":1,"actions":[]}' }]),
                self.envelope(content=[{'type': 'text', 'text': '{"schema_version":1,"schema_version":1,"actions":[]}' }]),
                b'x' * (cp.MAX_RESPONSE_BYTES + 1)]
        for raw in raws:
            with self.subTest(size=len(raw)):
                transport, _, connection, _ = self.https(raw)
                with self.assertRaises(cp.PilotError):
                    self.invoke(transport)
                connection.request.assert_called_once()
        for headers in ({'Content-Type': 'text/html'},
                        {'Content-Type': 'application/json', 'Content-Encoding': 'gzip'},
                        {'Content-Type': 'application/json', 'Content-Length': '65537'}):
            transport, response, _, _ = self.https(headers=headers)
            with self.assertRaises(cp.PilotError):
                self.invoke(transport)
            self.assertEqual(response.reads, 0)

    def test_https_provider_exceptions_do_not_expose_credentials(self):
        transport, _, connection, _ = self.https()
        connection.request.side_effect = RuntimeError(KEY)
        with self.assertRaises(cp.PilotError) as caught:
            self.invoke(transport)
        self.assertNotIn(KEY, str(caught.exception))
        self.assertNotIn(KEY, repr(transport))
        self.assertNotIn(KEY, repr(self.cfg))

    def test_approval_required_no_implicit_account_model_or_spend(self):
        for cfg in (cp.PilotConfig(enabled=True), replace(self.cfg, spend_approved=False),
                    replace(self.cfg, max_tokens=1025), replace(self.cfg, timeout_seconds=float('nan'))):
            with self.assertRaises(cp.PilotError):
                cp.AnthropicHTTPS(cfg, api_key=KEY)
        with self.assertRaises(cp.PilotError):
            cp.AnthropicHTTPS(self.cfg, api_key='bad\r\nkey')
        self.assertFalse((self.root / 'pilot.sqlite').exists())

    def test_cli_default_and_prepare_modes_never_request_key_or_construct_transport(self):
        with patch.object(cp.getpass, 'getpass') as prompt, \
                patch.object(cp, 'AnthropicHTTPS') as transport, contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(cp.main([]), 0)
            self.assertEqual(cp.main(['shadow', '--request', 'reply']), 0)
            self.assertEqual(cp.main(['run', '--state', str(self.root)]), 1)
        prompt.assert_not_called()
        transport.assert_not_called()
        self.assertNotIn(str(self.root), out.getvalue())

    def test_cli_rejected_arguments_do_not_echo_credentials(self):
        with contextlib.redirect_stderr(io.StringIO()) as out:
            with self.assertRaises(SystemExit):
                cp.main(['--api-key', KEY])
        self.assertEqual(out.getvalue(), 'invalid_pilot_arguments\n')


if __name__ == '__main__':
    unittest.main()
