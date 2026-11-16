from contextlib import redirect_stdout
from email.message import EmailMessage
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import uuid

import holds as h
import scrubber as s
import triage


def message(body='Synthetic general workflow.'):
    mail = EmailMessage()
    mail['Subject'] = 'Synthetic test'
    mail.set_content(body)
    return mail


class HoldTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.path = self.folder / 'synthetic.eml'
        self.raw = message().as_bytes()
        self.path.write_bytes(self.raw)
        self.source = h.file_source(self.path, self.raw)
        self.store = h.HoldStore(self.folder)
        self.hold = self.store.create(uuid.uuid4().hex, 'model_error', self.source)

    def test_metadata_contains_reference_but_no_message_or_credentials(self):
        with patch.object(s, 'STATE', self.folder), patch.object(s, 'llm', side_effect=RuntimeError('SECRET PAYLOAD')):
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertFalse(s.process(message('IDENTIFYING MESSAGE CONTENT').as_bytes()))
        saved = '\n'.join(path.read_text() for path in self.store.folder.glob('*.json'))
        self.assertNotIn('SECRET PAYLOAD', saved + output.getvalue())
        self.assertNotIn('IDENTIFYING MESSAGE CONTENT', saved + output.getvalue())
        self.assertEqual(list(self.folder.glob('*.json')), [])

    def test_duplicate_source_does_not_resurface_after_dismissal(self):
        dismissed = self.store.update(self.hold, status='dismissed')
        duplicate = self.store.create(uuid.uuid4().hex, 'model_error', self.source)
        self.assertEqual(duplicate.ticket, dismissed.ticket)
        self.assertEqual(duplicate.record['status'], 'dismissed')
        self.assertEqual(len(self.store.tickets()), 1)

    def test_changed_file_is_not_substituted(self):
        self.path.write_bytes(message('Changed original').as_bytes())
        with self.assertRaises(h.HoldError) as caught:
            h.read_source(self.source)
        self.assertEqual(caught.exception.code, 'source_changed')

    def test_file_preview_is_bounded_and_inert(self):
        mail = message()
        mail.set_content('<img src="https://example.invalid/track">Synthetic HTML', subtype='html')
        text = h.preview(mail.as_bytes())
        self.assertIn('displayed as text only', text)
        self.assertIn('<img', text)
        with self.assertRaises(h.HoldError):
            h.preview(b'x' * (h.MAX_BYTES + 1))

    def test_preview_omits_attachment_and_embedded_message_content(self):
        mail = message()
        mail.add_attachment(message('EMBEDDED CONTENT MUST BE OMITTED'))
        text = h.preview(mail.as_bytes())
        self.assertIn('Attachments omitted', text)
        self.assertNotIn('EMBEDDED CONTENT', text)

    def test_reference_validation_refuses_unexpected_keys_or_non_eml(self):
        self.assertFalse(h.valid_source({**self.source, 'password': 'synthetic-secret'}))
        self.assertFalse(h.valid_source({**self.source, 'path': str(self.folder / 'other.txt')}))
        with self.assertRaises(h.HoldError):
            self.store.load('../other')

    def test_stale_window_cannot_overwrite_hold_decision(self):
        self.store.update(self.hold, status='dismissed')
        with self.assertRaises(h.HoldError):
            self.store.update(self.hold, status='resolved')
        self.assertEqual(self.store.load(self.hold.ticket).record['status'], 'dismissed')

    def test_failed_save_keeps_hold_and_cleans_temporary_files(self):
        with patch.object(Path, 'replace', side_effect=OSError('synthetic failure')):
            with self.assertRaises(h.HoldError):
                self.store.update(self.hold, status='dismissed')
        self.assertEqual(self.store.load(self.hold.ticket).digest, self.hold.digest)
        self.assertEqual(len(list(self.store.folder.iterdir())), 1)

    def test_recheck_success_creates_only_pending_candidate_then_resolves(self):
        candidate = {'status': 'needs_local_review', 'subject': 'General', 'body': 'Workflow question.'}
        with patch.object(s, 'ensure_local_model'), patch.object(s, 'scrub', return_value=candidate):
            ticket = triage.recheck(self.folder, self.hold, self.raw)
        self.assertEqual(json.loads((self.folder / (ticket + '.json')).read_text()), candidate)
        self.assertEqual(self.store.load(self.hold.ticket).record['status'], 'resolved')

    def test_recheck_failure_updates_reason_and_keeps_source_without_candidate(self):
        with patch.object(s, 'ensure_local_model'), patch.object(s, 'scrub', side_effect=s.Blocked('verifier_flagged')):
            self.assertIsNone(triage.recheck(self.folder, self.hold, self.raw))
        record = self.store.load(self.hold.ticket).record
        self.assertEqual(record['status'], 'open')
        self.assertEqual(record['reason'], 'verifier_flagged')
        self.assertEqual(record['source'], self.source)
        self.assertEqual(list(self.folder.glob('*.json')), [])

    def test_model_unavailable_remains_held(self):
        with patch.object(s, 'ensure_local_model', side_effect=OSError('SENSITIVE')), patch.object(s, 'scrub') as scrub:
            self.assertIsNone(triage.recheck(self.folder, self.hold, self.raw))
            scrub.assert_not_called()
        self.assertEqual(self.store.load(self.hold.ticket).record['reason'], 'model_error')

    def test_closed_exception_cannot_be_retried(self):
        self.store.update(self.hold, status='dismissed')
        with patch.object(s, 'ensure_local_model') as model:
            with self.assertRaises(h.HoldError):
                triage.recheck(self.folder, self.hold, self.raw)
            model.assert_not_called()

    def test_edited_draft_uses_mime_and_never_writes_unchecked_text(self):
        raw = triage.draft_message('General question', 'General workflow.')
        self.assertEqual(s.parse_message(raw)['subject'], 'General question')
        for subject, body in [('Invalid\nHeader', 'Text'), ('Subject', ''), ('Subject', 'x' * s.MAX_CHARS)]:
            with self.assertRaises(h.HoldError):
                triage.draft_message(subject, body)
        self.assertEqual(list(self.folder.glob('*.json')), [])


class GmailSourceTests(unittest.TestCase):
    def setUp(self):
        self.source = {'kind': 'gmail', 'account_hash': h.account_hash('synthetic@example.invalid'),
                       'uidvalidity': '12345', 'uid': '7'}

    def test_wrong_account_is_rejected_before_connection(self):
        with patch.object(h.imaplib, 'IMAP4_SSL') as connect:
            with self.assertRaises(h.HoldError):
                h.read_source(self.source, 'other@example.invalid', 'synthetic-only')
            connect.assert_not_called()

    def test_gmail_readonly_and_peek_fetch(self):
        raw = message().as_bytes()
        client = MagicMock()
        client.select.return_value = ('OK', [])
        client.response.return_value = ('UIDVALIDITY', [b'12345'])
        client.uid.side_effect = [('OK', [f'7 (RFC822.SIZE {len(raw)})'.encode()]),
                                  ('OK', [(b'7 (BODY[]', raw), b')'])]
        with patch.object(h.imaplib, 'IMAP4_SSL') as connect:
            connect.return_value.__enter__.return_value = client
            self.assertEqual(h.read_source(self.source, 'synthetic@example.invalid', 'synthetic-only'), raw)
        client.select.assert_called_once_with('INBOX', readonly=True)
        self.assertEqual(client.uid.call_args_list[1].args, ('fetch', '7', '(BODY.PEEK[])'))

    def test_uidvalidity_change_blocks_before_fetch(self):
        client = MagicMock()
        client.select.return_value = ('OK', [])
        client.response.return_value = ('UIDVALIDITY', [b'99999'])
        with patch.object(h.imaplib, 'IMAP4_SSL') as connect:
            connect.return_value.__enter__.return_value = client
            with self.assertRaises(h.HoldError) as caught:
                h.read_source(self.source, 'synthetic@example.invalid', 'synthetic-only')
        self.assertEqual(caught.exception.code, 'source_changed')
        client.uid.assert_not_called()


if __name__ == '__main__':
    unittest.main()
