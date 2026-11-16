from contextlib import closing
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from actions import ActionError
from claude_adapter import (AdapterConfig, ClaudeAdapter, ContractError, FakeTransport,
                            decision_digest, payload_digest)
from operations import Config, OperationsError
from intake import identity
from holds import HoldError
import routing
import scrubber
from shadow_workflow import ShadowWorkflow, WorkflowError
from synthetic_workflow import MODEL_DIGEST, PAYLOAD, demo, fixture, submit_fixture, synthetic_checks


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.enterContext(synthetic_checks())
        self.workflow = ShadowWorkflow(self.root / 'state')
        self.source = fixture(self.root / 'synthetic.eml')
        self.ticket = self.workflow.register(self.source)

    def run_shadow(self):
        return self.workflow.run([self.ticket])

    def adapter(self, **kwargs):
        return ClaudeAdapter(self.root / 'adapter.sqlite3', config=AdapterConfig(True, .03),
                             transport=kwargs.get('transport', FakeTransport()))

    def result(self):
        self.run_shadow()
        adapter = self.adapter()
        key, version, response = submit_fixture(self.workflow, self.ticket, adapter)
        self.assertEqual(response.status, 'completed')
        return adapter, key, version

    def test_combined_demo_and_duplicate_imports(self):
        with patch.object(ClaudeAdapter, 'submit', side_effect=AssertionError('shadow_must_not_submit')):
            report = self.run_shadow()
            self.assertEqual(report.shadow, 1)
            self.assertEqual(self.workflow.register(self.source), self.ticket)
            self.assertEqual(self.run_shadow().attempted, 0)
        self.assertEqual(demo()['local_proposals'], 1)

    def test_provenance_and_private_binding_are_separate(self):
        self.run_shadow()
        snapshot, decision = self.workflow.current(self.ticket)
        self.assertEqual(decision.evidence.model_digest, MODEL_DIGEST)
        self.assertEqual(decision.evidence.validator_version, routing.VALIDATOR_VERSION)
        self.assertEqual(decision.evidence.content_digest, routing.content_digest(snapshot.record))
        self.assertEqual(set(snapshot.record), {'status', 'subject', 'body'})
        for path in (self.root / 'state' / 'routing').glob('*.json'):
            stored = path.read_text()
            self.assertNotIn(self.source['path'].replace('\\', '\\\\'), stored)
            self.assertNotIn(PAYLOAD['body'], stored)
            self.assertNotIn('synthetic@example.test', stored)
        with self.workflow.actions._transaction() as db:
            row = db.execute('SELECT version,source_version FROM candidates').fetchone()
        self.assertEqual(tuple(row), (snapshot.digest, self.source['sha256']))

    def test_missing_or_unstable_model_digest_never_issues_evidence(self):
        for digests in ((None, None), ('a' * 64, 'b' * 64)):
            with patch.object(scrubber, 'ensure_local_model', side_effect=digests):
                with self.assertRaises((scrubber.Blocked, TypeError)):
                    scrubber.scrub_checked(Path(self.source['path']).read_bytes())
        with patch.object(scrubber, 'api', side_effect=[{'models': [{'name': scrubber.MODEL}]}, {}]):
            with self.assertRaises(scrubber.Blocked):
                scrubber.ensure_local_model()

    def test_changed_candidate_blocks_old_results_even_after_restart(self):
        adapter, key, version = self.result()
        snapshot = self.workflow.candidates.load(self.ticket)
        self.workflow.candidates.save(snapshot, snapshot.record['subject'], 'Changed general request.',
                                      'needs_local_review')
        restarted = ShadowWorkflow(self.root / 'state')
        self.assertEqual(restarted.run([self.ticket]).exceptions, 1)
        with self.assertRaises((WorkflowError, ActionError)):
            restarted.capture(self.ticket, adapter, key, expected_candidate_version=version)

    def test_status_edit_cannot_rebind_existing_result(self):
        adapter, key, version = self.result()
        snapshot = self.workflow.candidates.load(self.ticket)
        changed = self.workflow.candidates.save(snapshot, snapshot.record['subject'], snapshot.record['body'],
                                                'reviewed_locally')
        with self.assertRaises(WorkflowError):
            self.workflow.capture(self.ticket, adapter, key, expected_candidate_version=changed.digest)

    def test_rejected_candidate_never_proposes(self):
        adapter, key, version = self.result()
        snap = self.workflow.candidates.load(self.ticket)
        self.workflow.candidates.save(snap, snap.record['subject'], snap.record['body'], 'rejected_locally')
        with self.assertRaises((WorkflowError, ActionError)):
            self.workflow.capture(self.ticket, adapter, key, expected_candidate_version=version)

    def test_source_edits_fail_closed(self):
        adapter, key, version = self.result()
        Path(self.source['path']).write_bytes(b'Synthetic changed source')
        with self.assertRaises(HoldError):
            self.workflow.capture(self.ticket, adapter, key, expected_candidate_version=version)
        with self.workflow.actions._transaction() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM proposals').fetchone()[0], 0)

    def test_evidence_freshness_and_version_changes_hold(self):
        self.run_shadow()
        with closing(sqlite3.connect(self.workflow.path)) as db:
            encoded, checked = db.execute('SELECT evidence,checked FROM checks').fetchone()
        evidence = routing.CheckEvidence(**json.loads(encoded))
        cases = [(evidence, checked - 4000, MODEL_DIGEST),
                 (evidence, checked + 4000, MODEL_DIGEST),
                 (replace(evidence, validator_version='b' * 64), checked, MODEL_DIGEST),
                 (evidence, checked, 'b' * 64)]
        for ev, stamp, model in cases:
            with self.subTest(evidence=ev, stamp=stamp, model=model):
                # Fresh isolated ActionStore avoids permanent invalidation by an earlier HOLD.
                with closing(sqlite3.connect(self.workflow.path)) as db, db:
                    db.execute('UPDATE checks SET evidence=?,checked=?', (json.dumps(ev.__dict__), stamp))
                self.workflow.model_digest = lambda: model
                with self.workflow.actions._transaction() as db:
                    db.execute('UPDATE candidates SET active=1')
                self.assertEqual(self.workflow.current(self.ticket)[1].outcome, 'HOLD')

    def test_legacy_candidate_without_evidence_holds(self):
        self.run_shadow()
        with closing(sqlite3.connect(self.workflow.path)) as db, db:
            db.execute('DELETE FROM checks')
        self.assertIn('missing_evidence', self.workflow.current(self.ticket)[1].reasons)

    def test_blocked_input_has_private_exception_and_no_candidate(self):
        with patch.object(self.workflow, 'check', side_effect=scrubber.Blocked('verifier_flagged')):
            report = self.run_shadow()
        self.assertEqual(report.exceptions, 1)
        self.assertFalse(self.workflow.candidates.path(self.ticket).exists())
        self.assertEqual(self.workflow.intake.status(self.ticket)['state'], 'blocked')
        self.assertEqual(self.run_shadow().attempted, 0)

    def test_timeout_is_uncertain_and_late_check_cannot_commit(self):
        entered, release, finished = threading.Event(), threading.Event(), threading.Event()
        original = self.workflow.check

        def slow(raw):
            entered.set()
            release.wait(5)
            try:
                return original(raw)
            finally:
                finished.set()

        self.workflow.check = slow
        self.workflow.timeout = .02
        try:
            self.assertEqual(self.run_shadow().uncertain, 1)
            self.assertTrue(entered.is_set())
            self.assertTrue(self.workflow.poisoned)
        finally:
            release.set()
            self.assertTrue(finished.wait(2))
        restarted = ShadowWorkflow(self.root / 'state')
        self.assertEqual(restarted.run([self.ticket]).attempted, 0)
        self.assertEqual(restarted.intake.status(self.ticket)['state'], 'processing')
        self.assertFalse(restarted.candidates.path(self.ticket).exists())
        with closing(sqlite3.connect(restarted.path)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM checks').fetchone()[0], 0)

    def test_hard_process_crash_recovers_claim_as_uncertain(self):
        code = '''import os, socket, sys
from unittest.mock import patch
from shadow_workflow import ShadowWorkflow
with patch.object(socket.socket, 'connect', side_effect=AssertionError('no_network')):
    workflow = ShadowWorkflow(sys.argv[1], check=lambda raw: os._exit(7))
    workflow.run([sys.argv[2]])
'''
        completed = subprocess.run([sys.executable, '-c', code, str(self.workflow.root), self.ticket],
                                   capture_output=True, timeout=10)
        self.assertEqual(completed.returncode, 7, completed.stderr)
        restarted = ShadowWorkflow(self.workflow.root)
        report = restarted.run([self.ticket])
        self.assertEqual((report.recovered, report.attempted), (1, 0))

    def test_crash_after_intake_commit_repairs_without_reinference(self):
        with patch.object(self.workflow.intake, 'materialize', side_effect=OSError('SENSITIVE')):
            self.assertEqual(self.run_shadow().uncertain, 1)
        restarted = ShadowWorkflow(self.workflow.root, check=lambda raw: self.fail('no_reinference'))
        self.assertEqual(restarted.run([self.ticket]).attempted, 0)
        self.assertTrue(restarted.candidates.path(self.ticket).exists())
        self.assertEqual(restarted.current(self.ticket)[1].outcome, 'WOULD_SEND')

    def test_adapter_capture_survives_restart_without_resubmit(self):
        adapter, key, version = self.result()
        restarted = ShadowWorkflow(self.workflow.root)
        reopened = ClaudeAdapter(adapter.ledger_path)
        with patch.object(ClaudeAdapter, 'submit', side_effect=AssertionError('no_resubmit')):
            receipt = restarted.capture(self.ticket, reopened, key, expected_candidate_version=version)
            self.assertEqual(restarted.capture(self.ticket, reopened, key,
                                               expected_candidate_version=version), receipt)
        self.assertEqual(receipt['source_ref'], identity(self.source))
        self.assertEqual(receipt['proposals'][0]['status'], 'local_only')

    def test_capture_failure_replays_durable_result_without_resubmit(self):
        adapter, key, version = self.result()
        with patch.object(self.workflow.actions, 'propose', side_effect=OSError('SENSITIVE')):
            with self.assertRaises(OSError):
                self.workflow.capture(self.ticket, adapter, key, expected_candidate_version=version)
        restarted = ShadowWorkflow(self.workflow.root)
        receipt = restarted.capture(self.ticket, ClaudeAdapter(adapter.ledger_path), key,
                                     expected_candidate_version=version)
        self.assertEqual(len(receipt['proposals']), 1)

    def test_unknown_or_partial_adapter_result_never_becomes_proposal(self):
        adapter, key, version = self.result()
        for status, reason in [('unknown', ''), ('completed', 'refusal'), ('completed', 'max_tokens')]:
            with closing(sqlite3.connect(adapter.ledger_path)) as db, db:
                db.execute('UPDATE submissions SET status=?,stop_reason=?', (status, reason))
            with self.assertRaises(ContractError):
                self.workflow.capture(self.ticket, adapter, key, expected_candidate_version=version)

    def test_result_request_binding_cannot_be_substituted(self):
        adapter, key, version = self.result()
        with closing(sqlite3.connect(self.workflow.path)) as db, db:
            db.execute('UPDATE requests SET version=?', ('b' * 64,))
        with self.assertRaises(WorkflowError):
            self.workflow.capture(self.ticket, adapter, key, expected_candidate_version=version)

    def test_adapter_timeout_is_not_retried_or_captured_after_late_completion(self):
        self.run_shadow()
        snap = self.workflow.candidates.load(self.ticket)
        key = self.workflow.bind_result_request(self.ticket, expected_candidate_version=snap.digest)
        release, finished = threading.Event(), threading.Event()
        calls = []

        def slow(payload, **kwargs):
            calls.append(1)
            release.wait(5)
            try:
                return FakeTransport()(payload, **kwargs)
            finally:
                finished.set()

        # Explicit synthetic authorization, wholly separate from shadow decision.
        authorization = {'eligible': True, 'mode': 'release', 'policy_version': 'synthetic-test-v1',
                         'candidate_digest': payload_digest(PAYLOAD)}
        adapter = self.adapter(transport=slow)
        try:
            response = adapter.submit(PAYLOAD, authorization,
                                      expected_candidate_digest=payload_digest(PAYLOAD),
                                      expected_decision_digest=decision_digest(authorization))
            self.assertEqual((response.status, response.code), ('unknown', 'timeout'))
        finally:
            release.set()
            self.assertTrue(finished.wait(2))
        reopened = self.adapter(transport=slow)
        response = reopened.submit(PAYLOAD, authorization,
                                   expected_candidate_digest=payload_digest(PAYLOAD),
                                   expected_decision_digest=decision_digest(authorization))
        self.assertEqual(response.status, 'duplicate')
        self.assertEqual(len(calls), 1)
        with self.assertRaises(ContractError):
            self.workflow.capture(self.ticket, reopened, key, expected_candidate_version=snap.digest)

    def test_no_private_binding_in_model_or_adapter_inputs(self):
        from synthetic_workflow import synthetic_checks
        with patch.object(scrubber, 'llm', wraps=scrubber.llm) as model:
            self.run_shadow()
        for call in model.call_args_list:
            encoded = json.dumps(call.args[1])
            self.assertNotIn('synthetic@example.test', encoded)
            self.assertNotIn('source_version', encoded)
            self.assertNotIn('account_hash', encoded)
            self.assertNotIn(self.source['sha256'], encoded)
        with patch.object(FakeTransport, '__call__', autospec=True,
                          return_value={'result': {'schema_version': 1, 'actions': [
                              {'kind': 'summarize', 'text': 'Synthetic result.'}]},
                                        'stop_reason': 'end_turn'}) as transport:
            submit_fixture(self.workflow, self.ticket, self.adapter())
        self.assertEqual(transport.call_args.args[1], PAYLOAD)

    def test_review_lock_prevents_stale_local_commit(self):
        adapter, key, version = self.result()
        lock = self.workflow.candidates.path(self.ticket).with_suffix('.review-lock')
        lock.write_text('synthetic')
        with self.assertRaises(WorkflowError):
            self.workflow.capture(self.ticket, adapter, key, expected_candidate_version=version)

    def test_batch_bounds(self):
        for tickets in ([], [self.ticket] * 101, iter([self.ticket])):
            with self.assertRaises(WorkflowError):
                self.workflow.run(tickets)
        with self.assertRaises(OperationsError):
            self.workflow.run([self.ticket], config=Config(batch_size=1, remote_delivery=True))


if __name__ == '__main__':
    unittest.main()
