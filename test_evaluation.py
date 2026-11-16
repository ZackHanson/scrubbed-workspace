import io
import json
from pathlib import Path
import socket
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import scrubber as s
from evaluation.corpus import corpus
from evaluation.runner import assess, live_guard, main, run, summarize


class EvaluationTests(unittest.TestCase):
    def candidate(self, fixture, body=None):
        return {'status': 'needs_local_review', 'subject': 'General request',
                'body': fixture.reference if body is None else body}

    def test_mocked_contract_runs_production_validation_without_network(self):
        with patch.object(socket.socket, 'connect', side_effect=AssertionError('no network')):
            receipt = run()
        self.assertTrue(receipt['passed'], receipt)
        self.assertEqual(len(receipt['fixtures']), 35)
        self.assertEqual(receipt['counts']['utility']['pass'], 16)
        self.assertEqual(receipt['counts']['refusal']['pass'], 19)
        self.assertFalse(receipt['certification'])

    def test_fixture_ids_are_unique_and_meaning_is_fixture_specific(self):
        fixtures = corpus()
        self.assertEqual(len({f.id for f in fixtures}), len(fixtures))
        for fixture in fixtures:
            if fixture.meaning:
                with self.subTest(fixture=fixture.id):
                    self.assertEqual(assess(fixture, self.candidate(fixture))['utility'], 'pass')
                    self.assertEqual(assess(fixture, self.candidate(fixture, 'General question'))['utility'], 'fail')

    def test_all_blocking_fails_utility_even_with_privacy_containment(self):
        rows = [assess(f, reason=f.reason or 'verifier_flagged') for f in corpus()]
        receipt = summarize(rows, 'mocked_contract')
        self.assertEqual(receipt['counts']['privacy']['fail'], 0)
        self.assertEqual(receipt['counts']['utility']['fail'], 16)
        self.assertFalse(receipt['passed'])

    def test_identifiers_in_subject_body_and_other_fixture_fail(self):
        fixture = corpus()[0]
        for token in ('NERISSA', 'N e r i s s a', '202.555.0146', 'ÉLVIRA', 'CANARYLEAK',
                      'fixture-route@example.invalid'):
            for field in ('subject', 'body'):
                with self.subTest(token=token, field=field):
                    candidate = self.candidate(fixture)
                    candidate[field] += ' ' + token
                    self.assertEqual(assess(fixture, candidate)['privacy'], 'fail')

    def test_exact_fields_types_status_and_nonempty_body(self):
        fixture = corpus()[0]
        candidates = [dict(self.candidate(fixture), extra='route'),
                      dict(self.candidate(fixture), status='approved'),
                      dict(self.candidate(fixture), body=42),
                      dict(self.candidate(fixture), body=' '),
                      {'body': fixture.reference}, ['invalid']]
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                row = assess(fixture, candidate)
                self.assertEqual(row['schema'], 'fail')
                self.assertEqual(row['privacy'], 'fail')
                self.assertEqual(row['utility'], 'fail')

    def test_refusal_requires_exact_reason_and_absent_candidate(self):
        fixture = next(f for f in corpus() if f.reason)
        self.assertEqual(assess(fixture, reason=fixture.reason)['refusal'], 'pass')
        self.assertEqual(assess(fixture, reason='model_error')['refusal'], 'fail')
        self.assertEqual(assess(fixture, self.candidate(fixture, 'text'), fixture.reason)['refusal'], 'fail')
        self.assertEqual(assess(fixture, reason=fixture.reason, error=True)['refusal'], 'fail')

    def test_empty_or_partial_coverage_fails(self):
        self.assertFalse(summarize([], 'mocked_contract')['passed'])
        fixture = corpus()[0]
        self.assertFalse(summarize([assess(fixture, self.candidate(fixture))], 'mocked_contract')['passed'])

    def test_missing_utility_measurement_cannot_be_marked_not_applicable(self):
        receipt = run()
        receipt['fixtures'][0]['utility'] = 'not_applicable'
        self.assertFalse(summarize(receipt['fixtures'], 'mocked_contract')['passed'])

    def test_receipt_is_content_free_and_exceptions_are_sanitized(self):
        with patch.object(s, 'scrub', side_effect=RuntimeError('PRIVATE_EXCEPTION_CANARY')):
            receipt = run()
        self.assertFalse(receipt['passed'])
        self.assertEqual(receipt['execution_errors'], len(corpus()))
        encoded = json.dumps(receipt)
        for value in ('PRIVATE_EXCEPTION_CANARY', 'Nerissa', 'example.invalid', 'hypertension', 'Cedar', 'source'):
            self.assertNotIn(value, encoded)
        allowed = {'fixture_id', 'outcome', 'reason', 'privacy', 'utility', 'refusal',
                   'schema', 'identifier_matches', 'execution'}
        self.assertTrue(all(set(row) == allowed for row in receipt['fixtures']))

    def test_no_persistent_state_or_real_state_reads(self):
        with tempfile.TemporaryDirectory() as temp:
            state = Path(temp) / 'must-not-exist'
            with patch.object(s, 'STATE', state):
                self.assertTrue(run()['passed'])
                self.assertEqual(s.STATE, state)
            self.assertFalse(state.exists())

    def test_live_rejects_configuration_before_model_calls(self):
        for key, value in [('ENDPOINT', 'http://localhost:11434'),
                           ('ENDPOINT', 'https://example.invalid'), ('MODEL', 'other')]:
            with patch.object(s, key, value), patch.object(s, 'ensure_local_model') as ensure:
                with self.assertRaises(RuntimeError):
                    with live_guard():
                        self.fail('must not enter')
                ensure.assert_not_called()

    def test_live_lock_prevents_competing_experiments_and_is_released(self):
        with tempfile.TemporaryDirectory() as temp, patch('evaluation.runner.tempfile.gettempdir', return_value=temp), \
                patch.object(s, 'ensure_local_model'):
            with live_guard():
                with self.assertRaises(FileExistsError):
                    with live_guard():
                        self.fail('competing live run')
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_live_socket_guard_rejects_non_numeric_and_other_ports(self):
        with tempfile.TemporaryDirectory() as temp, patch('evaluation.runner.tempfile.gettempdir', return_value=temp), \
                patch.object(s, 'ensure_local_model'):
            with live_guard(), socket.socket() as sock:
                for address in [('localhost', 11434), ('127.0.0.1', 80), ('192.0.2.1', 11434)]:
                    with self.assertRaises(OSError):
                        sock.connect(address)

    def test_live_mode_keeps_faults_injected_and_calls_useful_fixtures_serially(self):
        by_raw = {fixture.raw: fixture for fixture in corpus() if fixture.meaning}
        calls = []

        def synthetic_scrub(raw):
            fixture = by_raw.get(raw)
            if fixture:
                calls.append(fixture.id)
                return self.candidate(fixture)
            return original(raw)

        original = s.scrub
        with tempfile.TemporaryDirectory() as temp, patch('evaluation.runner.tempfile.gettempdir', return_value=temp), \
                patch.object(s, 'ensure_local_model'), patch.object(s, 'scrub', side_effect=synthetic_scrub):
            receipt = run(live=True)
        self.assertTrue(receipt['passed'])
        self.assertEqual(calls, [f.id for f in corpus() if f.meaning])
        self.assertEqual(sum(row['execution'] == 'injected_fault' for row in receipt['fixtures']), 12)

    def test_cli_default_and_failure_are_json_only(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main([]), 0)
        self.assertEqual(json.loads(output.getvalue())['mode'], 'mocked_contract')
        output = io.StringIO()
        with patch('evaluation.runner.run', side_effect=RuntimeError('PRIVATE')), redirect_stdout(output):
            self.assertEqual(main(['--live-qwen']), 1)
        self.assertNotIn('PRIVATE', output.getvalue())
        self.assertEqual(json.loads(output.getvalue())['error'], 'evaluation_unavailable')


if __name__ == '__main__':
    unittest.main()
