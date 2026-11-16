"""Desktop/durable integration tests; invented messages and temporary stores only."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock

from actions import ActionError
from claude_adapter import AdapterConfig, ClaudeAdapter, FakeTransport
from holds import HoldError, HoldStore, account_hash
from intake import identity
from review import CandidateStore, ReviewError, ReviewWindow
from review_workflow import Reviewer, managed, read_original
from shadow_workflow import ShadowWorkflow, WorkflowError
from synthetic_workflow import fixture, submit_fixture, synthetic_checks
import scrubber
import triage


class ReviewWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / 'state'
        self.enterContext(synthetic_checks())
        self.workflow = ShadowWorkflow(self.state)
        self.source = fixture(self.root / 'synthetic.eml')
        self.ticket = self.workflow.register(self.source)
        self.holds = HoldStore(self.state)
        self.raw = triage.draft_message('General correction', 'Explain general workflow.')

    def block(self):
        with patch.object(self.workflow, 'check', side_effect=scrubber.Blocked('model_error')):
            self.assertEqual(self.workflow.run([self.ticket]).exceptions, 1)
        return self.holds.load(self.ticket)

    def test_retry_preserves_ticket_and_resolves_exception(self):
        hold = self.block()
        self.assertEqual(triage.retry_original(self.state, hold), self.ticket)
        self.assertEqual(CandidateStore(self.state).tickets(), [self.ticket])
        self.assertEqual(self.holds.load(self.ticket).record['status'], 'resolved')
        self.assertEqual(self.workflow.intake.status(self.ticket)['retry_generation'], 1)
        self.assertEqual(self.workflow.run([self.ticket]).attempted, 0)
        with self.assertRaises(HoldError):
            triage.retry_original(self.state, hold)

    def test_checked_draft_has_revision_and_real_provenance_not_new_source(self):
        hold = self.block()
        self.assertEqual(triage.recheck(self.state, hold, self.raw), self.ticket)
        snapshot, decision = self.workflow.current(self.ticket)
        self.assertEqual(snapshot.record['status'], 'needs_local_review')
        self.assertEqual(decision.outcome, 'WOULD_SEND')
        self.assertEqual(self.workflow.intake.private_source(self.ticket)['source'], identity(self.source))
        with closing(sqlite3.connect(self.workflow.path)) as db:
            revision, ticket, status = db.execute('SELECT id,ticket,state FROM review_revisions').fetchone()
        self.assertNotEqual(revision, ticket)
        self.assertEqual((ticket, status), (self.ticket, 'done'))

    def test_failed_draft_stays_open_and_never_persists_unchecked_text(self):
        hold = self.block()
        sentinel = 'SYNTHETIC_UNCHECKED_DRAFT_CANARY'
        reviewer = Reviewer(self.state)
        with patch.object(reviewer.workflow, 'check', side_effect=scrubber.Blocked('verifier_flagged')):
            self.assertIsNone(reviewer.draft(hold, triage.draft_message('Draft', sentinel)))
        self.assertEqual(self.holds.load(self.ticket).record['reason'], 'verifier_flagged')
        self.assertEqual(CandidateStore(self.state).tickets(), [])
        for path in self.state.rglob('*'):
            if path.is_file():
                self.assertNotIn(sentinel.encode(), path.read_bytes())

    def test_candidate_edit_revokes_old_result_and_requires_fresh_checks(self):
        self.workflow.run([self.ticket])
        adapter = ClaudeAdapter(self.root / 'adapter.sqlite3', config=AdapterConfig(True), transport=FakeTransport())
        key, version, _ = submit_fixture(self.workflow, self.ticket, adapter)
        self.workflow.capture(self.ticket, adapter, key, expected_candidate_version=version)
        store = CandidateStore(self.state)
        old = store.load(self.ticket)
        edited = store.save(old, 'Edited request', 'Explain a revised general workflow.', 'needs_local_review')
        hold = self.holds.load(self.ticket)
        self.assertEqual(hold.record['status'], 'open')
        with self.assertRaises((WorkflowError, ActionError)):
            self.workflow.capture(self.ticket, adapter, key, expected_candidate_version=version)
        self.assertEqual(triage.recheck(self.state, hold, self.raw), self.ticket)
        self.assertEqual(self.workflow.current(self.ticket)[1].outcome, 'WOULD_SEND')
        # Even if checking restores identical content, an old request stays revoked.
        with self.assertRaises((WorkflowError, ActionError)):
            self.workflow.capture(self.ticket, adapter, key,
                                  expected_candidate_version=store.load(self.ticket).digest)

    def test_rejection_closes_open_exception_and_blocks_recheck(self):
        hold = self.block()
        triage.recheck(self.state, hold, self.raw)
        store = CandidateStore(self.state)
        candidate = store.load(self.ticket)
        candidate = store.save(candidate, candidate.record['subject'], 'Edited general body.', 'needs_local_review')
        hold = self.holds.load(self.ticket)
        store.save(candidate, candidate.record['subject'], candidate.record['body'], 'rejected_locally')
        self.assertEqual(self.holds.load(self.ticket).record['status'], 'dismissed')
        with self.assertRaises(HoldError):
            triage.recheck(self.state, hold, self.raw)

    def test_dismiss_does_not_retry_or_reopen_on_reimport(self):
        hold = self.block()
        triage.dismiss(self.state, hold)
        self.assertEqual(self.workflow.register(self.source), self.ticket)
        self.assertEqual(self.workflow.run([self.ticket]).attempted, 0)
        self.assertEqual(self.holds.load(self.ticket).record['status'], 'dismissed')
        self.assertTrue(Path(self.source['path']).exists())

    def test_changed_source_cannot_be_replaced_by_draft(self):
        hold = self.block()
        Path(self.source['path']).write_bytes(b'Synthetic changed original')
        self.assertIsNone(triage.recheck(self.state, hold, self.raw))
        self.assertEqual(self.holds.load(self.ticket).record['reason'], 'source_changed')
        self.assertFalse(self.workflow.candidates.path(self.ticket).exists())

    def test_stale_hold_is_rejected_before_inference(self):
        hold = self.block()
        self.holds.update(hold, status='dismissed')
        with patch.object(scrubber, 'scrub_checked') as check:
            with self.assertRaises(HoldError):
                triage.recheck(self.state, hold, self.raw)
        check.assert_not_called()

    def test_edit_during_check_is_preserved(self):
        self.workflow.run([self.ticket])
        store = CandidateStore(self.state)
        old = store.load(self.ticket)
        store.save(old, 'General edit', 'First edit.', 'needs_local_review')
        hold = self.holds.load(self.ticket)
        reviewer = Reviewer(self.state)
        original = reviewer.workflow.check
        def concurrent_edit(raw):
            current = store.load(self.ticket)
            store.save(current, 'Concurrent edit', 'Keep this newer draft.', 'needs_local_review')
            return original(raw)
        with patch.object(reviewer.workflow, 'check', side_effect=concurrent_edit):
            with self.assertRaises(HoldError):
                reviewer.draft(hold, self.raw)
        self.assertEqual(store.load(self.ticket).record['body'], 'Keep this newer draft.')
        self.assertEqual(self.holds.load(self.ticket).record['status'], 'open')

    def test_failed_materialization_recovers_checked_revision_without_inference(self):
        hold = self.block()
        with patch.object(Path, 'replace', side_effect=OSError('synthetic save failure')):
            with self.assertRaises(OSError):
                triage.recheck(self.state, hold, self.raw)
        reviewer = Reviewer(self.state)
        with patch.object(reviewer.workflow, 'check', side_effect=AssertionError('must recover checked output')):
            self.assertEqual(reviewer.draft(self.holds.load(self.ticket), self.raw), self.ticket)
        self.assertEqual(self.workflow.current(self.ticket)[1].outcome, 'WOULD_SEND')

    def test_timeout_requires_reconciliation_even_for_different_draft(self):
        hold = self.block()
        reviewer = Reviewer(self.state)
        with patch.object(reviewer.workflow, '_compute', side_effect=WorkflowError('computation_uncertain')):
            with self.assertRaises(HoldError):
                reviewer.draft(hold, self.raw)
        with self.assertRaises(HoldError) as caught:
            Reviewer(self.state).draft(hold, triage.draft_message('Different', 'Different draft.'))
        self.assertEqual(caught.exception.code, 'reconciliation_required')

    def test_checked_revision_repairs_late_hold_save_failure_without_new_check(self):
        hold = self.block()
        with patch.object(HoldStore, 'update', side_effect=OSError('synthetic final save failure')):
            with self.assertRaises(OSError):
                triage.recheck(self.state, hold, self.raw)
        self.assertTrue(self.workflow.candidates.path(self.ticket).exists())
        reviewer = Reviewer(self.state)
        with patch.object(reviewer.workflow, 'check', side_effect=AssertionError('no repeated model call')):
            self.assertEqual(reviewer.draft(hold, self.raw), self.ticket)
        self.assertEqual(self.holds.load(self.ticket).record['status'], 'resolved')

    def test_crash_after_hold_resolution_does_not_strand_later_edit(self):
        hold = self.block()
        update = HoldStore.update
        def resolved_then_crash(store, snapshot, **changes):
            result = update(store, snapshot, **changes)
            if changes.get('status') == 'resolved':
                raise OSError('synthetic crash after committed hold resolution')
            return result
        with patch.object(HoldStore, 'update', resolved_then_crash):
            with self.assertRaises(OSError):
                triage.recheck(self.state, hold, self.raw)
        candidate = self.workflow.candidates.load(self.ticket)
        self.workflow.candidates.save(candidate, 'Later correction', 'Revise this general workflow.', 'needs_local_review')
        next_hold = self.holds.load(self.ticket)
        self.assertEqual(triage.recheck(self.state, next_hold,
                                        triage.draft_message('Later', 'Another correction.')), self.ticket)
        self.assertEqual(self.holds.load(self.ticket).record['status'], 'resolved')

    def test_recovered_revision_rechecks_current_validator_before_resolving(self):
        hold = self.block()
        with patch.object(Path, 'replace', side_effect=OSError('synthetic save failure')):
            with self.assertRaises(OSError):
                triage.recheck(self.state, hold, self.raw)
        import routing
        with patch.object(routing, 'VALIDATOR_VERSION', 'b' * 64):
            self.assertIsNone(triage.recheck(self.state, hold, self.raw))
        self.assertEqual(self.holds.load(self.ticket).record['status'], 'open')
        self.assertEqual(self.holds.load(self.ticket).record['reason'], 'needs_recheck')

    def test_managed_gmail_draft_passes_memory_only_credentials_to_strict_reader(self):
        source = {'kind': 'gmail', 'account_hash': account_hash('synthetic@example.test'),
                  'uidvalidity': '123', 'uid': '8'}
        raw = Path(self.source['path']).read_bytes()
        workflow = ShadowWorkflow(self.root / 'gmail-state', source_reader=lambda source: raw)
        ticket = workflow.register(source)
        with patch.object(workflow, 'check', side_effect=scrubber.Blocked('model_error')):
            workflow.run([ticket])
        hold = HoldStore(workflow.root).load(ticket)
        credentials = ('synthetic@example.test', 'synthetic-password')
        with patch('review_workflow.read_original', return_value=raw) as reader:
            self.assertEqual(triage.recheck(workflow.root, hold, self.raw, credentials=credentials), ticket)
        self.assertTrue(reader.called)
        self.assertTrue(all(call.args == (source, credentials) for call in reader.call_args_list))
        for path in workflow.root.rglob('*'):
            if path.is_file():
                self.assertNotIn(b'synthetic-password', path.read_bytes())

    def test_unfetched_managed_gmail_draft_binds_exact_original_bytes(self):
        source = {'kind': 'gmail', 'account_hash': account_hash('synthetic@example.test'),
                  'uidvalidity': '123', 'uid': '7'}
        raw = Path(self.source['path']).read_bytes()
        workflow = ShadowWorkflow(self.root / 'gmail-state', source_reader=lambda source: raw)
        ticket = workflow.register(source)
        with patch.object(workflow, 'check', side_effect=scrubber.Blocked('model_error')):
            workflow.run([ticket])
        self.assertIsNone(workflow.intake.private_source(ticket)['source_version'])
        hold = HoldStore(workflow.root).load(ticket)
        self.assertEqual(Reviewer(workflow.root, reader=lambda source: raw).draft(hold, self.raw), ticket)
        import hashlib
        self.assertEqual(workflow.intake.private_source(ticket)['source_version'], hashlib.sha256(raw).hexdigest())

    def test_uncertain_intake_cannot_be_bypassed_by_draft(self):
        with patch.object(self.workflow, 'check', side_effect=scrubber.Blocked('model_error')), \
                patch('shadow_workflow.HoldStore.create', side_effect=OSError('synthetic failure')):
            self.assertEqual(self.workflow.run([self.ticket]).uncertain, 1)
        hold = self.holds.create(self.ticket, 'model_error', self.source)
        with self.assertRaises(HoldError):
            triage.recheck(self.state, hold, self.raw)
        self.assertFalse(self.workflow.candidates.path(self.ticket).exists())

    def test_failed_edit_save_withdraws_prior_evidence_conservatively(self):
        self.workflow.run([self.ticket])
        candidate = self.workflow.candidates.load(self.ticket)
        with patch.object(Path, 'replace', side_effect=OSError('synthetic failure')):
            with self.assertRaises(ReviewError):
                self.workflow.candidates.save(candidate, 'New subject', 'New draft.', 'needs_local_review')
        self.assertEqual(self.workflow.candidates.load(self.ticket).digest, candidate.digest)
        self.assertEqual(self.workflow.current(self.ticket)[1].outcome, 'HOLD')


class ManagedWindowTests(unittest.TestCase):
    setUp = ReviewWorkflowTests.setUp
    block = ReviewWorkflowTests.block

    def test_offline_demo_rehearsal_failure_success_retry_and_dismissal(self):
        import tkinter as tk
        from review import demo_checks, demo_exceptions, demo_store
        import socket
        folder = self.root / 'rehearsal'
        folder.mkdir()
        store = demo_store(folder)
        with demo_checks():
            with self.assertRaises(AssertionError):
                with socket.socket() as connection:
                    connection.connect(('127.0.0.1', 11434))
            demo_exceptions(folder, managed=True)
            root = tk.Tk()
            root.withdraw()
            try:
                window = ReviewWindow(root, store, demo=True)
                holds = window.holds
                by_reason = {holds.load(t).record['reason']: holds.load(t) for t in holds.tickets()}
                def finish():
                    deadline = time.monotonic() + 4
                    while window.busy and time.monotonic() < deadline:
                        root.update()
                        time.sleep(.01)
                    self.assertFalse(window.busy)
                window.show_hold(by_reason['verifier_flagged'])
                with patch.object(window, 'open_preview') as display:
                    window.view_original()
                    finish()
                self.assertIn('Mara Velquist', display.call_args.args[0])
                window.subject.set('DEMO_FAIL')
                window.body.insert('1.0', 'Keep this invented draft.')
                window.check_draft()
                finish()
                self.assertEqual(window.values(), ('DEMO_FAIL', 'Keep this invented draft.'))
                self.assertIn('has not been saved', window.notice.get())
                self.assertEqual(len(store.tickets()), 1)
                window.subject.set('General request')
                window.check_draft()
                finish()
                self.assertEqual(holds.load(by_reason['verifier_flagged'].ticket).record['status'], 'resolved')
                window.show_hold(by_reason['model_error'])
                self.assertIn('Ollama is not contacted', window.guidance.get())
                window.retry_original()
                finish()
                self.assertEqual(holds.load(by_reason['model_error'].ticket).record['status'], 'resolved')
                self.assertTrue(window.reason.get().startswith('Closed (resolved):'))
                window.show_hold(by_reason['attachment'])
                with patch.object(window.messagebox, 'askyesno', return_value=True):
                    window.dismiss()
                self.assertEqual(holds.load(by_reason['attachment'].ticket).record['status'], 'dismissed')
                self.assertEqual(len(store.tickets()), 3)
                self.assertTrue(all(store.load(t).record['status'] == 'needs_local_review' for t in store.tickets()))
            finally:
                root.destroy()

    def test_managed_window_retry_and_draft_failure(self):
        import tkinter as tk
        hold = self.block()
        root = tk.Tk()
        root.withdraw()
        self.addCleanup(root.destroy)
        window = ReviewWindow(root, CandidateStore(self.state), demo=True)
        window.show_hold(hold)
        def finish():
            deadline = time.monotonic() + 4
            while window.busy and time.monotonic() < deadline:
                root.update()
                time.sleep(.01)
            self.assertFalse(window.busy)
        window.retry_original()
        finish()
        self.assertEqual(self.holds.load(self.ticket).record['status'], 'resolved')
        self.assertEqual(CandidateStore(self.state).tickets(), [self.ticket])
        current = window.store.load(self.ticket)
        window.store.save(current, 'Edited request', 'Check this revised draft.', 'needs_local_review')
        window.show_hold(self.holds.load(self.ticket))
        window.subject.set('General draft')
        window.body.insert('1.0', 'Keep this unsaved correction after a failed check.')
        with patch.object(scrubber, 'scrub', side_effect=scrubber.Blocked('verifier_flagged')):
            window.check_draft()
            finish()
        self.assertEqual(window.values()[1], 'Keep this unsaved correction after a failed check.')
        self.assertEqual(self.holds.load(self.ticket).record['status'], 'open')


class ManagedGmailTests(unittest.TestCase):
    def test_demo_exceptions_use_managed_tickets_without_model_calls(self):
        from review import demo_exceptions
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(scrubber, 'ensure_local_model', side_effect=AssertionError('no model on open')):
            demo_exceptions(folder, managed=True)
            tickets = HoldStore(folder).tickets()
            self.assertEqual(len(tickets), 3)
            self.assertTrue(all(managed(folder, ticket) for ticket in tickets))

    def test_managed_reader_requires_explicit_uid_and_peek(self):
        source = {'kind': 'gmail', 'account_hash': account_hash('synthetic@example.test'),
                  'uidvalidity': '123', 'uid': '7'}
        client = MagicMock()
        client.select.return_value = ('OK', [])
        client.response.return_value = ('UIDVALIDITY', [b'123'])
        raw = b'Subject: Synthetic\r\n\r\nGeneral workflow.'
        client.uid.side_effect = [('OK', [f'1 (UID 7 RFC822.SIZE {len(raw)})'.encode()]),
                                 ('OK', [(b'1 (UID 7 BODY[]', raw)])]
        with patch('review_workflow.imaplib.IMAP4_SSL') as connect:
            connect.return_value.__enter__.return_value = client
            self.assertEqual(read_original(source, ('synthetic@example.test', 'synthetic-password')), raw)
        client.select.assert_called_once_with('INBOX', readonly=True)
        self.assertEqual(client.uid.call_args_list[1].args, ('fetch', '7', '(UID BODY.PEEK[])'))
        with patch('review_workflow.imaplib.IMAP4_SSL') as connect:
            with self.assertRaises(HoldError):
                read_original(source, ('other@example.test', 'synthetic-password'))
            connect.assert_not_called()


if __name__ == '__main__':
    unittest.main()
