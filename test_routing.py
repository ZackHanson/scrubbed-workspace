"""Synthetic-only routing tests. No runtime state, inference or cloud calls."""
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import routing as r


class RoutingTests(unittest.TestCase):
    def setUp(self):
        self.candidate = {'subject': 'Workflow', 'body': 'Please review the general workflow.',
                          'status': 'needs_local_review'}
        self.evidence = r.CheckEvidence(r.content_digest(self.candidate),
                                       r.VALIDATOR_VERSION, r.MODEL, 'a' * 64,
                                       'pass', 'pass')

    def test_pass_is_shadow_only_and_deterministic(self):
        decision = r.evaluate(self.candidate, self.evidence)
        self.assertEqual(decision, r.evaluate(dict(self.candidate), self.evidence))
        self.assertEqual(decision.outcome, 'WOULD_SEND')
        self.assertEqual(decision.mode, 'shadow')
        self.assertIs(decision.release_enabled, False)
        self.assertEqual(decision.reasons, ('shadow_checks_passed',))

    def test_review_marker_grants_no_authority(self):
        for status in ('needs_local_review', 'reviewed_locally'):
            candidate = dict(self.candidate, status=status)
            self.assertEqual(r.evaluate(candidate).outcome, 'HOLD')
            self.assertEqual(r.evaluate(candidate).reasons, ('missing_evidence',))
        self.assertIn('rejected_locally', r.evaluate(
            dict(self.candidate, status='rejected_locally'), self.evidence).reasons)

    def test_all_negative_model_results_hold(self):
        for stage in ('redactor', 'auditor'):
            for result in r.RESULTS - {'pass'}:
                with self.subTest(stage=stage, result=result):
                    decision = r.evaluate(self.candidate, replace(
                        self.evidence, **{stage: result}))
                    self.assertEqual(decision.outcome, 'HOLD')
                    self.assertIn(stage + '_' + result, decision.reasons)

    def test_malformed_or_unknown_provenance_holds_without_echo(self):
        for evidence in ({'private': 'synthetic sentinel'},
                         replace(self.evidence, model='other'),
                         replace(self.evidence, model_digest=''),
                         replace(self.evidence, auditor=True),
                         replace(self.evidence, redactor='synthetic sentinel')):
            decision = r.evaluate(self.candidate, evidence)
            self.assertIn('invalid_evidence', decision.reasons)
            self.assertIsNone(decision.evidence)
            self.assertNotIn('sentinel', repr(decision))

    def test_version_and_exact_content_bindings(self):
        self.assertIn('validator_changed', r.evaluate(self.candidate, replace(
            self.evidence, validator_version='b' * 64)).reasons)
        decision = r.evaluate(self.candidate, self.evidence)
        for key in ('subject', 'body'):
            changed = dict(self.candidate)
            changed[key] += ' '
            self.assertIn('stale_evidence', r.evaluate(changed, self.evidence).reasons)
            with self.assertRaisesRegex(r.RoutingError, 'stale_decision'):
                r.proposed_payload(changed, self.evidence, decision)

    def test_identifiers_and_routing_lines_hold_even_with_pass_evidence(self):
        for body in ('Call 212-555-0199', 'From: [REDACTED]',
                     'To: [REDACTED]', 'Received: local', 'X-Source: local',
                     'References: [REDACTED]', 'MRN: ABC', 'UID: 12',
                     'source_reference: hidden', r'C:\synthetic\message.eml',
                     'file:///synthetic/message', '/home/synthetic/message',
                     r'\\synthetic\share\message', 'message.eml'):
            candidate = dict(self.candidate, body=body)
            evidence = replace(self.evidence, content_digest=r.content_digest(candidate))
            self.assertEqual(r.evaluate(candidate, evidence).outcome, 'HOLD')
        candidate = dict(self.candidate, subject='Workflow\nFrom: hidden')
        self.assertIn('routing_content', r.evaluate(candidate).reasons)

    def test_strict_candidate_schema_and_bounds(self):
        for candidate in (None, {}, dict(self.candidate, source='synthetic reference'),
                          dict(self.candidate, headers={}),
                          dict(self.candidate, status='approved'),
                          dict(self.candidate, body=1),
                          dict(self.candidate, body='\ud800')):
            self.assertIn('invalid_candidate', r.evaluate(candidate).reasons)
        self.assertIn('empty_output', r.evaluate(dict(self.candidate, body='  ')).reasons)
        self.assertIn('context_limit', r.evaluate(
            dict(self.candidate, body='x' * (r.MAX_CHARS + 1))).reasons)

    def test_payload_is_fresh_allowlist_and_decision_cannot_be_forged(self):
        decision = r.evaluate(self.candidate, self.evidence)
        payload = r.proposed_payload(self.candidate, self.evidence, decision)
        self.assertEqual(set(payload), {'subject', 'body'})
        payload['body'] = 'different'
        self.assertNotEqual(payload['body'], self.candidate['body'])
        for forged in (replace(decision, release_enabled=True),
                       replace(decision, mode='live'), replace(decision, policy_version='old')):
            with self.assertRaisesRegex(r.RoutingError, 'stale_decision'):
                r.proposed_payload(self.candidate, self.evidence, forged)
        with self.assertRaisesRegex(r.RoutingError, 'stale_decision'):
            r.proposed_payload(self.candidate, replace(self.evidence, model_digest='b' * 64),
                               decision)
        with self.assertRaisesRegex(r.RoutingError, 'candidate_held'):
            r.proposed_payload(self.candidate, None, r.evaluate(self.candidate))

    def test_no_transport_even_for_would_send_or_forged_decision(self):
        transport = Mock()
        decision = r.evaluate(self.candidate, self.evidence)
        for value in (decision, replace(decision, mode='live', release_enabled=True), None):
            with self.assertRaisesRegex(r.RoutingError, 'release_disabled'):
                r.execute(self.candidate, self.evidence, value, transport)
        transport.assert_not_called()

    def test_private_records_are_content_free_idempotent_and_keep_history(self):
        with tempfile.TemporaryDirectory() as folder:
            store = r.DecisionStore(Path(folder) / 'routing')
            ticket = '1' * 32
            decision = store.record(ticket, self.candidate, self.evidence)
            self.assertEqual(store.record(ticket, self.candidate, self.evidence), decision)
            paths = list(store.folder.glob('*.json'))
            self.assertEqual(len(paths), 1)
            data = json.loads(paths[0].read_bytes())
            self.assertEqual(data['content_digest'], self.evidence.content_digest)
            self.assertEqual(data['evidence']['model_digest'], 'a' * 64)
            self.assertNotIn(self.candidate['body'], paths[0].read_text())
            store.record(ticket, dict(self.candidate, body='Changed'), self.evidence)
            self.assertEqual(len(list(store.folder.glob('*.json'))), 2)
            paths[0].write_text('{}')
            with self.assertRaisesRegex(r.RoutingError, 'record_conflict'):
                store.record(ticket, self.candidate, self.evidence)

    def test_store_fixed_errors_and_no_partial_record_on_write_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            store = r.DecisionStore(folder)
            with self.assertRaisesRegex(r.RoutingError, 'invalid_ticket'):
                store.record('../escape', self.candidate)
            with patch('routing.os.fsync', side_effect=OSError('synthetic private detail')):
                with self.assertRaisesRegex(r.RoutingError, '^store_failed$'):
                    store.record('1' * 32, self.candidate, self.evidence)
            self.assertEqual(list(Path(folder).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
