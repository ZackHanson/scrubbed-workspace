"""Actual file/Gmail entrypoints, invented messages, temporary state, no sockets."""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

from holds import HoldStore, HoldError
from intake import IntakeLedger
from operations import reconcile
from review_workflow import Reviewer, managed
from shadow_workflow import ShadowWorkflow
from synthetic_workflow import fixture, synthetic_checks, MODEL_DIGEST
import scrubber


class LauncherWorkflowTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.state = self.root / 'state'
        self.source = fixture(self.root / 'invented.eml')
        self.raw = (self.root / 'invented.eml').read_bytes()
        self.enterContext(synthetic_checks())
        self.enterContext(patch.object(scrubber, 'STATE', self.state))
        self.transport = self.enterContext(patch('claude_adapter.ClaudeAdapter.submit',
                                               side_effect=AssertionError('no_transport')))

    def ticket(self):
        return IntakeLedger(self.state).ingest(self.source)

    def test_files_command_is_managed_and_has_full_provenance(self):
        with patch('sys.argv', ['scrubber.py', 'files', self.source['path']]):
            self.assertEqual(scrubber.main(), 0)
        ticket = self.ticket()
        self.assertTrue(managed(self.state, ticket))
        workflow = ShadowWorkflow(self.state)
        snapshot, decision = workflow.current(ticket)
        self.assertEqual(snapshot.record['status'], 'needs_local_review')
        self.assertEqual(decision.outcome, 'WOULD_SEND')
        self.assertFalse(decision.release_enabled)
        evidence = workflow._evidence(ticket)
        self.assertEqual((evidence.model_digest, evidence.redactor, evidence.auditor),
                         (MODEL_DIGEST, 'pass', 'pass'))
        self.assertEqual(workflow.intake.private_source(ticket)['source_version'],
                         hashlib.sha256(self.raw).hexdigest())
        self.assertEqual(workflow.actions.candidate_version(ticket), snapshot.digest)
        self.transport.assert_not_called()

    def test_gmail_command_manages_candidate_and_fetch_failure_and_deduplicates(self):
        client = MagicMock()
        client.select.return_value = ('OK', [])
        client.response.return_value = ('UIDVALIDITY', [b'123'])
        def uid(command, *args):
            if command == 'search':
                return 'OK', [b'1 2']
            number, fields = args
            if fields == '(UID RFC822.SIZE)':
                size = len(self.raw) if number == '1' else scrubber.MAX_BYTES + 1
                return 'OK', [f'1 (UID {number} RFC822.SIZE {size})'.encode()]
            self.assertEqual((number, fields), ('1', '(UID BODY.PEEK[])'))
            return 'OK', [(b'1 (UID 1 BODY[]', self.raw), b')']
        client.uid.side_effect = uid
        with patch.object(scrubber.imaplib, 'IMAP4_SSL') as connection, \
                patch('builtins.input', return_value='invented@example.test'), \
                patch.object(scrubber.getpass, 'getpass', return_value='invented-secret'), \
                patch('sys.argv', ['scrubber.py', 'gmail']), \
                patch.object(scrubber, 'scrub', wraps=scrubber.scrub) as model:
            connection.return_value.__enter__.return_value = client
            self.assertEqual(scrubber.main(), 0)
            self.assertEqual(scrubber.main(), 0)
            self.assertEqual(model.call_count, 1)
        workflow = ShadowWorkflow(self.state, source_reader=lambda source: self.raw)
        candidate = workflow.candidates.tickets()[0]
        hold = HoldStore(self.state).load(HoldStore(self.state).tickets()[0])
        for ticket in (candidate, hold.ticket):
            self.assertTrue(managed(self.state, ticket))
        self.assertEqual(workflow.current(candidate)[1].outcome, 'WOULD_SEND')
        self.assertEqual(hold.record['reason'], 'oversized')
        self.assertEqual(workflow.intake.status(hold.ticket)['state'], 'blocked')
        report = json.loads((self.state / 'run-status.json').read_text())
        self.assertEqual((report['saved_for_review'], report['blocked']), (1, 1))
        for private in ('invented@example.test', 'invented-secret', self.raw.decode()):
            self.assertNotIn(private, json.dumps(report))
        for call in client.select.call_args_list:
            self.assertEqual(call.kwargs, {'readonly': True})
        self.transport.assert_not_called()

    def test_failed_import_restarts_and_reviewer_retry_keeps_ticket(self):
        with patch.object(scrubber, 'scrub', side_effect=scrubber.Blocked('verifier_flagged')) as check:
            self.assertFalse(scrubber.process(self.raw, self.source))
            self.assertFalse(scrubber.process(self.raw, self.source))
            self.assertEqual(check.call_count, 1)
        ticket = self.ticket()
        hold = HoldStore(self.state).load(ticket)
        self.assertTrue(managed(self.state, ticket))
        self.assertEqual(Reviewer(self.state).retry(hold), ticket)
        self.assertEqual(HoldStore(self.state).load(ticket).record['status'], 'resolved')
        self.assertTrue(scrubber.process(self.raw, self.source))
        workflow = ShadowWorkflow(self.state)
        candidate = workflow.candidates.load(ticket)
        edited = workflow.candidates.save(candidate, 'General', 'General revised workflow.',
                                          'needs_local_review')
        self.assertFalse(scrubber.process(self.raw, self.source))
        checked = Reviewer(self.state).draft(HoldStore(self.state).load(ticket), self.raw)
        self.assertEqual(checked, ticket)
        current = workflow.candidates.load(ticket)
        workflow.candidates.save(current, current.record['subject'], current.record['body'],
                                 'rejected_locally')
        self.assertFalse(scrubber.process(self.raw, self.source))
        self.assertNotEqual(edited.digest, candidate.digest)

    def test_uncertain_publication_does_not_become_success_on_restart(self):
        with patch.object(IntakeLedger, 'materialize', side_effect=OSError('invented')), \
                patch.object(scrubber, 'scrub', wraps=scrubber.scrub) as check:
            self.assertFalse(scrubber.process(self.raw, self.source))
            self.assertEqual(check.call_count, 1)
        with patch.object(scrubber, 'scrub', side_effect=AssertionError('no_reinference')):
            self.assertFalse(scrubber.process(self.raw, self.source))
            ticket = self.ticket()
            with self.assertRaises(HoldError):
                Reviewer(self.state).retry(HoldStore(self.state).load(ticket))
            reconcile(self.state / 'operations', ticket, 'shadow')
            self.assertTrue(scrubber.process(self.raw, self.source))

    def test_missing_source_never_manufactures_evidence(self):
        with patch.object(scrubber, 'scrub_checked') as check:
            self.assertFalse(scrubber.process(self.raw))
        check.assert_not_called()
        self.assertFalse((self.state / 'workflow.sqlite3').exists())
        self.assertEqual(list(self.state.glob('*.json')), [])

    def test_existing_legacy_completion_is_held_without_adopting_evidence(self):
        ledger = IntakeLedger(self.state)
        ticket = ledger.ingest(self.source)
        ledger.complete(ledger.claim(ticket), {'status': 'needs_local_review',
                                              'subject': 'Legacy', 'body': 'General workflow.'})
        ledger.materialize(ticket)
        before = (self.state / (ticket + '.json')).read_bytes()
        with patch.object(scrubber, 'scrub_checked', side_effect=AssertionError('no_adoption')):
            self.assertFalse(scrubber.process(self.raw, self.source))
        self.assertEqual((self.state / (ticket + '.json')).read_bytes(), before)
        with closing(sqlite3.connect(self.state / 'workflow.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM checks').fetchone(), (0,))
        self.assertIn('missing_evidence', ShadowWorkflow(self.state).current(ticket)[1].reasons)

    def test_changed_source_during_check_is_held(self):
        check = scrubber.scrub_checked
        def changed(raw):
            result = check(raw)
            (self.root / 'invented.eml').write_bytes(b'Subject: Changed\n\nChanged source.')
            return result
        with patch.object(scrubber, 'scrub_checked', side_effect=changed):
            self.assertFalse(scrubber.process(self.raw, self.source))
        self.assertEqual(HoldStore(self.state).load(self.ticket()).record['reason'], 'source_changed')
        self.transport.assert_not_called()

    def test_completed_duplicate_rechecks_source_after_callers_read(self):
        self.assertTrue(scrubber.process(self.raw, self.source))
        (self.root / 'invented.eml').write_bytes(b'Subject: Changed\n\nChanged source.')
        with patch.object(scrubber, 'scrub_checked', side_effect=AssertionError('no_reinference')):
            self.assertFalse(scrubber.process(self.raw, self.source))
        self.assertEqual(HoldStore(self.state).load(self.ticket()).record['reason'], 'source_changed')

    def timeout_batch(self, command):
        release, finished = threading.Event(), threading.Event()
        checks, workflows = [], []
        factory = scrubber._workflow
        def make(reader=None):
            workflow = factory(reader)
            workflow.timeout = .03
            original = workflow.check
            def slow(raw):
                checks.append('started')
                try:
                    if not release.wait(3):
                        raise AssertionError('test_release_missing')
                    return original(raw)
                finally:
                    finished.set()
            workflow.check = slow
            workflows.append(workflow)
            return workflow
        client = MagicMock()
        client.select.return_value = ('OK', [])
        client.response.return_value = ('UIDVALIDITY', [b'123'])
        def uid(operation, *args):
            if operation == 'search':
                return 'OK', [b'1 2']
            number, fields = args
            self.assertEqual(number, '1', 'second source must not be fetched after timeout')
            if fields == '(UID RFC822.SIZE)':
                return 'OK', [f'1 (UID 1 RFC822.SIZE {len(self.raw)})'.encode()]
            return 'OK', [(b'1 (UID 1 BODY[]', self.raw), b')']
        client.uid.side_effect = uid
        second = self.root / 'second.eml'
        fixture(second)
        argv = (['scrubber.py', 'files', self.source['path'], str(second)]
                if command == 'files' else ['scrubber.py', 'gmail'])
        try:
            with patch.object(scrubber, '_workflow', side_effect=make), \
                    patch('sys.argv', argv), \
                    patch.object(scrubber.imaplib, 'IMAP4_SSL') as connection, \
                    patch('builtins.input', return_value='invented@example.test'), \
                    patch.object(scrubber.getpass, 'getpass', return_value='invented-secret'):
                connection.return_value.__enter__.return_value = client
                self.assertEqual(scrubber.main(), 1)
            self.assertEqual(checks, ['started'])
            self.assertEqual(len(workflows), 1)
            self.assertTrue(workflows[0].poisoned)
            self.assertEqual(list(self.state.glob('*.json')),
                             [] if command == 'files' else [self.state / 'run-status.json'])
        finally:
            release.set()
            self.assertTrue(finished.wait(3))
        self.assertEqual(workflows[0].candidates.tickets(), [])
        self.transport.assert_not_called()

    def test_files_timeout_stops_batch_before_second_message(self):
        self.timeout_batch('files')

    def test_gmail_timeout_stops_batch_before_second_uid(self):
        self.timeout_batch('gmail')
