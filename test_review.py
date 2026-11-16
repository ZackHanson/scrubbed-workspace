import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import review as r


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.store = r.demo_store(self.folder)
        self.ticket = self.store.tickets()[0]
        self.snapshot = self.store.load(self.ticket)

    def test_only_candidate_ids_listed_and_traversal_refused(self):
        (self.folder / 'run-status.json').write_text('{}')
        self.assertEqual(self.store.tickets(), [self.ticket])
        with self.assertRaises(r.ReviewError):
            self.store.load('../run-status')

    def test_editing_reviewed_record_resets_to_pending(self):
        reviewed = self.store.save(self.snapshot, self.snapshot.record['subject'],
                                   self.snapshot.record['body'], 'reviewed_locally')
        edited = self.store.save(reviewed, 'Edited general request',
                                 'General workflow question.', 'needs_local_review')
        self.assertEqual(edited.record['status'], 'needs_local_review')
        self.assertEqual(self.store.load(self.ticket).record, edited.record)

    def test_edits_cannot_skip_saved_version_review(self):
        for status in ('reviewed_locally', 'rejected_locally'):
            with self.assertRaises(r.ReviewError):
                self.store.save(self.snapshot, 'Changed subject', 'Changed body', status)
        self.assertEqual(self.store.load(self.ticket).digest, self.snapshot.digest)

    def test_reject_retains_candidate(self):
        rejected = self.store.save(self.snapshot, self.snapshot.record['subject'],
                                   self.snapshot.record['body'], 'rejected_locally')
        self.assertEqual(rejected.record['status'], 'rejected_locally')
        self.assertEqual(rejected.record['body'], self.snapshot.record['body'])
        self.assertEqual(self.store.tickets(), [self.ticket])

    def test_identifier_prevents_recording_review(self):
        pending = self.store.save(self.snapshot, 'General question',
                                  'Contact synthetic@example.invalid', 'needs_local_review')
        with self.assertRaises(r.ReviewError):
            self.store.save(pending, pending.record['subject'], pending.record['body'], 'reviewed_locally')
        self.assertEqual(self.store.load(self.ticket).record['status'], 'needs_local_review')

    def test_other_window_changes_preserved(self):
        other = self.store.load(self.ticket)
        self.store.save(other, 'New version', 'New general workflow.', 'needs_local_review')
        with self.assertRaisesRegex(r.ReviewError, 'another window'):
            self.store.save(self.snapshot, 'Old window edit', 'Draft', 'needs_local_review')
        self.assertEqual(self.store.load(self.ticket).record['subject'], 'New version')

    def test_failed_atomic_replace_preserves_original_and_cleans_up(self):
        with patch.object(Path, 'replace', side_effect=OSError('synthetic failure')):
            with self.assertRaises(r.ReviewError):
                self.store.save(self.snapshot, 'Edit', 'New text', 'needs_local_review')
        self.assertEqual(self.store.load(self.ticket).digest, self.snapshot.digest)
        self.assertEqual(list(self.folder.iterdir()), [self.store.path(self.ticket)])

    def test_existing_writer_lock_is_preserved(self):
        lock = self.store.path(self.ticket).with_suffix('.review-lock')
        lock.touch()
        with self.assertRaisesRegex(r.ReviewError, 'Another review'):
            self.store.save(self.snapshot, 'Edit', 'Text', 'needs_local_review')
        self.assertTrue(lock.exists())
        self.assertEqual(self.store.load(self.ticket).digest, self.snapshot.digest)

    def test_invalid_record_is_not_overwritten(self):
        for record in ({'status': 'approved', 'subject': '', 'body': 'Text'},
                       {'status': 'needs_local_review', 'subject': '', 'body': 'Text', 'From': 'synthetic'},
                       {'status': 'needs_local_review', 'subject': '', 'body': ' '}):
            raw = json.dumps(record)
            self.store.path(self.ticket).write_text(raw)
            with self.assertRaises(r.ReviewError):
                self.store.load(self.ticket)
            self.assertEqual(self.store.path(self.ticket).read_text(), raw)


class WindowTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = r.demo_store(self.temp.name)
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.window = r.ReviewWindow(self.root, self.store, demo=True)
        self.root.update()
        self.window.view.set('Candidates')
        self.window.change_view()
        self.window.queue.selection_set(0)
        self.window.select()
        self.root.update()

    def test_edit_save_review_edit_and_reject_flow(self):
        window = self.window
        ticket = window.snapshot.ticket
        window.body.insert('end', '\nDiscuss general workflow.')
        self.root.update()
        self.assertTrue(window.dirty())
        window.confirmed.set(True)
        window.mark_reviewed()
        self.assertEqual(self.store.load(ticket).record['status'], 'needs_local_review')
        self.assertIn('Save edits first', window.notice.get())
        window.save_edits()
        self.root.update()
        self.assertFalse(window.dirty())
        self.assertFalse(window.confirmed.get())
        window.confirmed.set(True)
        window.mark_reviewed()
        self.root.update()
        self.assertEqual(self.store.load(ticket).record['status'], 'reviewed_locally')
        window.confirmed.set(True)
        window.subject.set('Edited again')
        self.root.update()
        self.assertFalse(window.confirmed.get())
        window.save_edits()
        self.assertEqual(self.store.load(ticket).record['status'], 'needs_local_review')
        with patch.object(window.messagebox, 'askyesno', return_value=True):
            window.reject()
        self.assertEqual(self.store.load(ticket).record['status'], 'rejected_locally')

    def test_reload_can_preserve_unsaved_draft(self):
        self.window.subject.set('Unsaved synthetic draft')
        with patch.object(self.window.messagebox, 'askyesno', return_value=False):
            self.window.reload()
        self.assertEqual(self.window.subject.get(), 'Unsaved synthetic draft')
        self.assertTrue(self.window.dirty())

    def test_review_checkbox_required(self):
        self.window.mark_reviewed()
        self.assertIn('checkbox', self.window.notice.get())
        self.assertEqual(self.store.load(self.window.snapshot.ticket).record['status'], 'needs_local_review')

    def test_conflict_keeps_draft_and_reload_loads_selected_current_version(self):
        ticket = self.window.snapshot.ticket
        other = self.store.load(ticket)
        self.store.save(other, 'Other window', 'Newer saved text.', 'needs_local_review')
        self.window.subject.set('My unsaved draft')
        self.window.save_edits()
        self.assertIn('another window', self.window.notice.get())
        self.assertEqual(self.window.subject.get(), 'My unsaved draft')
        with patch.object(self.window.messagebox, 'askyesno', return_value=False):
            self.window.reload()
        self.assertEqual(self.window.subject.get(), 'My unsaved draft')
        with patch.object(self.window.messagebox, 'askyesno', return_value=True):
            self.window.reload()
        self.assertEqual(self.window.snapshot.ticket, ticket)
        self.assertEqual(self.window.values(), ('Other window', 'Newer saved text.'))
        self.assertFalse(self.window.dirty())

    def test_reload_missing_selected_candidate_clears_editor(self):
        self.store.path(self.window.snapshot.ticket).unlink()
        self.window.reload()
        self.assertIsNone(self.window.snapshot)
        self.assertEqual(self.window.values(), ('', ''))


class ExceptionWindowTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = r.demo_store(self.temp.name)
        r.demo_exceptions(self.temp.name)
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.window = r.ReviewWindow(self.root, self.store, demo=True)
        self.root.update()
        self.window.queue.selection_set(0)
        self.window.select()
        self.root.update()

    def finish(self):
        deadline = time.monotonic() + 4
        while self.window.busy and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.assertFalse(self.window.busy, 'Synthetic worker did not finish')
        self.root.update()

    def test_default_list_contains_only_open_holds_and_reasons(self):
        self.assertEqual(self.window.active_view, 'Open exceptions')
        self.assertEqual(len(self.window.ids), 3)
        self.assertIsNone(self.window.snapshot)
        self.assertIn(self.window.hold.record['reason'], r.REASONS)
        self.assertEqual(self.window.reason.get(), r.REASONS[self.window.hold.record['reason']][0])
        self.assertIn('3 open exceptions', self.window.summary.get())

    def test_local_original_preview_runs_off_ui_thread(self):
        with patch.object(self.window, 'open_preview') as display:
            self.window.view_original()
            self.assertTrue(self.window.busy)
            self.finish()
            display.assert_called_once()
            self.assertIn('Subject: Synthetic local original', display.call_args.args[0])
        self.assertEqual(len(self.store.tickets()), 1)

    def test_identifier_highlight_and_failed_draft_preserved(self):
        import scrubber as s
        self.window.subject.set('Contact synthetic@example.invalid')
        self.window.body.insert('1.0', 'Call 202-555-0146 about the general request.')
        self.root.update()
        self.assertTrue(self.window.body.tag_ranges('identifier'))
        self.assertEqual(self.window.subject_entry.cget('background'), '#ffe0a6')
        with patch.object(s, 'ensure_local_model'), patch.object(s, 'scrub', side_effect=s.Blocked('verifier_flagged')):
            self.window.check_draft()
            self.finish()
        self.assertIn('202-555-0146', self.window.values()[1])
        self.assertEqual(self.window.hold.record['status'], 'open')
        self.assertEqual(len(self.store.tickets()), 1)

    def test_checked_draft_resolves_hold_and_adds_pending_candidate(self):
        import scrubber as s
        ticket = self.window.hold.ticket
        self.window.subject.set('General request')
        self.window.body.insert('1.0', 'Please discuss general workflow.')
        candidate = {'status': 'needs_local_review', 'subject': 'General', 'body': 'Please discuss general workflow.'}
        with patch.object(s, 'ensure_local_model'), patch.object(s, 'scrub', return_value=candidate):
            self.window.check_draft()
            self.finish()
        self.assertEqual(self.window.holds.load(ticket).record['status'], 'resolved')
        self.assertNotIn(ticket, self.window.ids)
        self.assertEqual(len(self.store.tickets()), 2)
        self.assertTrue(all(self.store.load(key).record['status'] == 'needs_local_review'
                            for key in self.store.tickets()))

    def test_dismiss_moves_hold_to_closed_and_preserves_original(self):
        ticket = self.window.hold.ticket
        source = self.window.hold.record['source']
        with patch.object(self.window.messagebox, 'askyesno', return_value=True):
            self.window.dismiss()
        self.assertNotIn(ticket, self.window.ids)
        self.assertEqual(self.window.holds.load(ticket).record['status'], 'dismissed')
        self.assertTrue(Path(source['path']).exists())
        self.window.view.set('Closed exceptions')
        self.window.change_view()
        self.assertIn(ticket, self.window.ids)

    def test_view_switch_keeps_draft_when_discard_declined(self):
        self.window.body.insert('1.0', 'Unsaved synthetic draft')
        with patch.object(self.window.messagebox, 'askyesno', return_value=False):
            self.window.view.set('Candidates')
            self.window.change_view()
        self.assertEqual(self.window.view.get(), 'Open exceptions')
        self.assertIn('Unsaved synthetic draft', self.window.values()[1])

    def test_reload_hold_refreshes_reason_and_preserves_selection(self):
        hold = self.window.hold
        self.window.holds.update(hold, reason='source_changed')
        self.window.reload()
        self.assertEqual(self.window.hold.ticket, hold.ticket)
        self.assertEqual(self.window.reason.get(), r.REASONS['source_changed'][0])
        self.assertIn('Re-import', self.window.guidance.get())

    def test_uncertain_worker_keeps_draft_and_explains_no_retry(self):
        self.window.body.insert('1.0', 'Unsaved invented correction.')
        with patch.object(r.triage, 'recheck', side_effect=r.HoldError('reconciliation_required')):
            self.window.check_draft()
            self.finish()
        self.assertEqual(self.window.values()[1], 'Unsaved invented correction.')
        self.assertIn('Do not retry uncertain work', self.window.notice.get())
        self.assertEqual(self.window.hold.record['status'], 'open')


if __name__ == '__main__':
    unittest.main()
