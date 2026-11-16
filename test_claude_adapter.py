import contextlib
import io
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from claude_adapter import (AdapterConfig, ClaudeAdapter, ContractError,
                            FakeTransport, decision_digest, payload_digest)


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'synthetic-ledger.sqlite'
        self.payload = {'subject': 'Workflow', 'body': 'Explain general follow-up workflow.'}
        self.decision = {'eligible': True, 'mode': 'release', 'policy_version': 'synthetic-v1',
                         'candidate_digest': payload_digest(self.payload)}
        self.calls = []

    def transport(self, payload, **options):
        self.calls.append((payload, options))
        return FakeTransport()(payload, **options)

    def adapter(self, transport=None, timeout=1):
        return ClaudeAdapter(self.path, config=AdapterConfig(True, timeout),
                             transport=transport or self.transport)

    def submit(self, adapter=None, payload=None, decision=None, **bindings):
        values = {'expected_candidate_digest': payload_digest(self.payload),
                  'expected_decision_digest': decision_digest(self.decision)}
        values.update(bindings)
        return (adapter or self.adapter()).submit(
            self.payload if payload is None else payload,
            self.decision if decision is None else decision, **values)

    def test_disabled_default_has_no_side_effect(self):
        result = self.submit(ClaudeAdapter(self.path, transport=self.transport))
        self.assertEqual(result.status, 'disabled')
        self.assertFalse(self.path.exists())
        self.assertEqual(self.calls, [])

    def test_enabled_without_transport_is_disabled(self):
        self.assertEqual(self.submit(ClaudeAdapter(self.path, config=AdapterConfig(True))).code,
                         'transport_missing')
        self.assertFalse(self.path.exists())

    def test_synthetic_end_to_end_and_content_free_ledger(self):
        result = self.submit()
        self.assertEqual((result.status, result.stop_reason), ('completed', 'end_turn'))
        self.assertEqual(result.result, {'schema_version': 1, 'actions': [
            {'kind': 'summarize', 'text': 'Synthetic workflow assistance.'}]})
        self.assertEqual(self.calls[0][0], self.payload)
        self.assertEqual(set(self.calls[0][1]), {'timeout_seconds', 'idempotency_key'})
        with contextlib.closing(sqlite3.connect(self.path)) as db:
            rows = db.execute('SELECT key, status FROM submissions').fetchall()
        self.assertEqual(rows, [(result.submission_key, 'completed')])
        stored = self.path.read_bytes()
        self.assertNotIn(self.payload['body'].encode(), stored)
        self.assertNotIn(b'synthetic-v1', stored)

    def test_whitelist_rejects_routing_raw_status_and_source_fields(self):
        for key in ('from', 'to', 'raw', 'source', 'credentials', 'status', 'ticket'):
            with self.subTest(key=key):
                self.assertEqual(self.submit(payload={**self.payload, key: 'synthetic'}).code,
                                 'invalid_payload')
        self.assertEqual(self.calls, [])

    def test_payload_types_and_limits(self):
        for payload in (None, [], {'subject': 'Workflow', 'body': ''},
                        {'subject': 'Workflow', 'body': 42},
                        {'subject': 'Workflow', 'body': 'x' * 16001}):
            # Call directly so None isn't treated as the helper default.
            result = self.adapter().submit(payload, self.decision,
                                          expected_candidate_digest='x', expected_decision_digest='x')
            self.assertEqual(result.status, 'blocked')
        self.assertFalse(self.path.exists())

    def test_addresses_and_routing_headers_blocked(self):
        for body in ('Contact synthetic@example.test', 'To: synthetic recipient',
                     'Received: synthetic route', 'Call 212-555-0123'):
            result = self.submit(payload={'subject': 'Workflow', 'body': body})
            self.assertIn(result.code, {'identifier_detected', 'routing_detected'})
        self.assertEqual(self.calls, [])

    def test_mutated_content_or_bindings_blocked(self):
        self.assertEqual(self.submit(payload={**self.payload, 'body': 'Changed workflow.'}).code,
                         'digest_mismatch')
        self.assertEqual(self.submit(expected_candidate_digest='0' * 64).code, 'digest_mismatch')
        self.assertEqual(self.submit(expected_decision_digest='0' * 64).code, 'digest_mismatch')
        changed = {**self.decision, 'candidate_digest': '0' * 64}
        self.assertEqual(self.submit(decision=changed,
                                    expected_decision_digest=decision_digest(changed)).code,
                         'digest_mismatch')
        self.assertEqual(self.calls, [])

    def test_shadow_and_ineligible_cannot_submit(self):
        for changed in ({**self.decision, 'mode': 'shadow'},
                        {**self.decision, 'eligible': False}):
            result = self.submit(decision=changed,
                                 expected_decision_digest=decision_digest(changed))
            self.assertEqual(result.code, 'not_eligible')
        self.assertFalse(self.path.exists())

    def test_decision_whitelist_and_strict_boolean(self):
        for changed in ({**self.decision, 'eligible': 1},
                        {**self.decision, 'source': 'synthetic'},
                        {**self.decision, 'policy_version': 'synthetic@example.test'},
                        {**self.decision, 'mode': 'reviewed_locally'}, {}):
            self.assertEqual(self.submit(decision=changed).code, 'invalid_decision')
        self.assertEqual(self.calls, [])

    def test_digest_is_canonical_and_separate_from_file_hash(self):
        self.assertEqual(payload_digest(dict(reversed(list(self.payload.items())))),
                         payload_digest(self.payload))
        self.assertEqual(decision_digest(dict(reversed(list(self.decision.items())))),
                         decision_digest(self.decision))

    def test_duplicate_across_adapter_restart_and_policy_change(self):
        first = self.submit()
        self.assertEqual(self.submit().status, 'duplicate')
        changed = {**self.decision, 'policy_version': 'synthetic-v2'}
        result = self.submit(decision=changed, expected_decision_digest=decision_digest(changed))
        self.assertEqual(result.status, 'duplicate')
        self.assertEqual(result.submission_key, first.submission_key)
        self.assertEqual(len(self.calls), 1)

    def test_concurrent_submission_and_timeout_never_retry(self):
        entered, release, exited = threading.Event(), threading.Event(), threading.Event()

        def slow(payload, **options):
            self.calls.append((payload, options))
            entered.set()
            try:
                release.wait(2)
                return FakeTransport()(payload, **options)
            finally:
                exited.set()

        result = []
        caller = threading.Thread(target=lambda: result.append(self.submit(self.adapter(slow, .1))))
        caller.start()
        try:
            self.assertTrue(entered.wait(1))
            self.assertEqual(self.submit().status, 'duplicate')
            caller.join(1)
            self.assertFalse(caller.is_alive())
            self.assertEqual((result[0].status, result[0].code), ('unknown', 'timeout'))
            self.assertEqual(self.submit().status, 'duplicate')
        finally:
            release.set()
            caller.join(2)
            exited.wait(2)
        self.assertEqual(len(self.calls), 1)

    def test_transport_error_is_fixed_private_and_not_retried(self):
        def broken(payload, **options):
            raise RuntimeError('synthetic-secret synthetic@example.test')

        capture = io.StringIO()
        with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
            result = self.submit(self.adapter(broken))
        self.assertEqual(result.code, 'transport_error')
        self.assertEqual(capture.getvalue(), '')
        self.assertNotIn('synthetic-secret', repr(result))
        self.assertEqual(self.submit().status, 'duplicate')

    def test_response_whitelist_and_untrusted_text_repr(self):
        good = FakeTransport()(self.payload, timeout_seconds=1, idempotency_key='synthetic')
        invalid = ({**good, 'credential': 'synthetic'},
                   {**good, 'result': {'schema_version': True, 'actions': []}},
                   {**good, 'result': {'schema_version': 1, 'actions': [
                       {'kind': 'draft_reply', 'text': 'synthetic', 'to': 'synthetic'}]}},
                   {**good, 'result': {'schema_version': 1, 'actions': [
                       {'kind': 'draft_reply', 'text': ''}]}},
                   {**good, 'result': {'schema_version': 1, 'actions': [
                       {'kind': 'summarize', 'text': 'synthetic'}] * 21}},
                   {**good, 'result': {'schema_version': 1, 'actions': [
                       {'kind': 'summarize', 'text': 'x' * (128 * 1024)}]}},
                   {**good, 'stop_reason': 'tool_use'}, None)
        for index, response in enumerate(invalid):
            with self.subTest(response=index):
                adapter = ClaudeAdapter(Path(self.temp.name) / f'case-{index}.sqlite',
                                        config=AdapterConfig(True),
                                        transport=lambda *a, **kw: response)
                self.assertEqual(self.submit(adapter).code, 'invalid_response')
        result = self.submit(self.adapter(lambda *a, **kw: {**good, 'stop_reason': 'refusal'}))
        self.assertEqual(result.stop_reason, 'refusal')
        self.assertNotIn('Synthetic workflow assistance.', repr(result))

    def test_all_action_kinds_return_without_model_ids(self):
        response = {'result': {'schema_version': 1, 'actions': [
            {'kind': kind, 'text': 'Synthetic general assistance.'} for kind in (
                'summarize', 'suggest_organization', 'draft_reply')]}, 'stop_reason': 'end_turn'}
        result = self.submit(self.adapter(lambda *a, **kw: response))
        self.assertEqual(result.result, response['result'])
        self.assertIsNot(result.result, response['result'])

    def test_ledger_failure_prevents_transport(self):
        self.path.write_bytes(b'not a sqlite database')
        self.assertEqual(self.submit().code, 'ledger_unavailable')
        self.assertEqual(self.calls, [])

    def test_ledger_update_failure_keeps_reservation(self):
        adapter = self.adapter()
        with patch.object(adapter, '_finish', side_effect=sqlite3.OperationalError('synthetic-secret')):
            self.assertEqual(self.submit(adapter).code, 'ledger_update_failed')
        self.assertEqual(self.submit().status, 'duplicate')
        self.assertEqual(len(self.calls), 1)

    def test_worker_start_failure_keeps_reservation(self):
        with patch('claude_adapter.threading.Thread.start', side_effect=RuntimeError('synthetic-secret')):
            self.assertEqual(self.submit().code, 'worker_unavailable')
        self.assertEqual(self.submit().status, 'duplicate')
        self.assertEqual(self.calls, [])

    def test_config_rejects_unbounded_or_ambiguous_values(self):
        for timeout in (True, 0, -1, 121, float('inf'), float('nan'), '30'):
            with self.assertRaisesRegex(ContractError, '^invalid_config$'):
                AdapterConfig(True, timeout)
        with self.assertRaisesRegex(ContractError, '^invalid_config$'):
            AdapterConfig('yes')


if __name__ == '__main__':
    unittest.main()
