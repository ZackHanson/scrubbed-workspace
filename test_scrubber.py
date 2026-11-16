import json
import tempfile
import unittest
from unittest.mock import MagicMock
from email.message import EmailMessage
from pathlib import Path
from unittest.mock import patch
import scrubber as s


def message(text='General clinical workflow question.'):
    mail = EmailMessage()
    mail['Subject'] = 'Workflow'
    mail['From'] = 'private@example.com'
    mail.set_content(text)
    return mail


class ScrubberTests(unittest.TestCase):
    def run_gmail_mock(self, client):
        with tempfile.TemporaryDirectory() as temp, patch.object(s, 'STATE', Path(temp)), patch.object(s, 'ensure_local_model'), patch.object(s.imaplib, 'IMAP4_SSL') as connection, patch('builtins.input', return_value='synthetic@example.com'), patch.object(s.getpass, 'getpass', return_value='synthetic-secret'), patch.object(s.sys, 'argv', ['scrubber.py', 'gmail']):
            connection.return_value.__enter__.return_value = client
            result = s.main()
            report = json.loads((Path(temp) / 'run-status.json').read_text())
            self.assertNotIn('synthetic@example.com', json.dumps(report))
            self.assertNotIn('synthetic-secret', json.dumps(report))
            return result, report

    def test_gmail_zero_unread_receipt(self):
        client = MagicMock()
        client.select.return_value = ('OK', [])
        client.uid.return_value = ('OK', [b''])
        result, report = self.run_gmail_mock(client)
        self.assertEqual(result, 0)
        self.assertTrue(report['authenticated'])
        self.assertEqual(report['stage'], 'completed')
        self.assertEqual(report['unread_found'], 0)
        client.select.assert_called_once_with('INBOX', readonly=True)

    def test_gmail_auth_error_receipt_contains_no_exception_payload(self):
        client = MagicMock()
        client.login.side_effect = s.imaplib.IMAP4.error('synthetic-secret synthetic@example.com')
        result, report = self.run_gmail_mock(client)
        self.assertEqual(result, 1)
        self.assertFalse(report['authenticated'])
        self.assertEqual(report['error'], 'authentication_failed')

    def test_gmail_blocked_message_receipt(self):
        client = MagicMock()
        client.select.return_value = ('OK', [])
        client.uid.side_effect = [('OK', [b'1']), ('OK', [b'1 (RFC822.SIZE 999999)'])]
        result, report = self.run_gmail_mock(client)
        self.assertEqual(result, 0)
        self.assertEqual(report['selected'], 1)
        self.assertEqual(report['blocked'], 1)
        self.assertEqual(report['saved_for_review'], 0)

    def test_headers_dropped(self):
        self.assertEqual(set(s.parse_message(message().as_bytes())), {'subject', 'body'})

    def test_attachments_block_before_model(self):
        mail = message()
        mail.add_attachment(b'private', maintype='application', subtype='pdf', filename='private.pdf')
        with patch.object(s, 'llm') as model:
            with self.assertRaises(s.Blocked):
                s.scrub(mail.as_bytes())
            model.assert_not_called()

    def test_html_only_blocked(self):
        mail = EmailMessage()
        mail.set_content('<p>Private</p>', subtype='html')
        with self.assertRaises(s.Blocked):
            s.parse_message(mail.as_bytes())

    def test_oversize_blocked(self):
        with self.assertRaises(s.Blocked):
            s.parse_message(b'x' * (s.MAX_BYTES + 1))

    def test_unicode_context_budget_blocked(self):
        with self.assertRaises(s.Blocked):
            s.parse_message(message('\U0001f600' * 5000).as_bytes())

    def test_uncertain_redactor_blocked(self):
        with patch.object(s, 'llm', return_value={'subject': '', 'body': 'text', 'uncertain': True}):
            with self.assertRaises(s.Blocked):
                s.scrub(message().as_bytes())

    def test_verifier_blocks_and_no_file_saved(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(s, 'STATE', Path(temp)), patch.object(s, 'llm', side_effect=[
            {'subject': 'Workflow', 'body': 'Name remains', 'uncertain': False},
            {'suspected_phi': True, 'uncertain': False}]):
            self.assertFalse(s.process(message().as_bytes()))
            self.assertEqual(list(Path(temp).glob('*.json')), [])
            hold = s.HoldStore(temp).load(s.HoldStore(temp).tickets()[0]).record
            self.assertEqual(hold, {'status': 'open', 'reason': 'verifier_flagged', 'source': None})

    def test_identifier_blocks_before_verifier(self):
        with patch.object(s, 'llm', return_value={'subject': 'a@example.com', 'body': 'text', 'uncertain': False}) as model:
            with self.assertRaises(s.Blocked):
                s.scrub(message().as_bytes())
            self.assertEqual(model.call_count, 1)

    def test_id_patterns_preserve_ordinary_policy_and_record_words(self):
        body = 'Review the policy and record medication adherence for the membership workflow.'
        with patch.object(s, 'llm', side_effect=[
            {'subject': 'Workflow', 'body': 'General question', 'uncertain': False},
            {'suspected_phi': False, 'uncertain': False}]) as model:
            s.scrub(message(body).as_bytes())
            self.assertEqual(model.call_args_list[0].args[1]['body'].strip(), body)

    def test_labeled_identifiers_redacted_before_model(self):
        with patch.object(s, 'llm', side_effect=[
            {'subject': 'Workflow', 'body': 'General question', 'uncertain': False},
            {'suspected_phi': False, 'uncertain': False}]) as model:
            s.scrub(message('MRN ZX812934, policy: ABCDEF, patient id 314159, MRN ALPHACODE.').as_bytes())
            data = model.call_args_list[0].args[1]['body']
            for identifier in ('ZX812934', 'ABCDEF', '314159', 'ALPHACODE'):
                self.assertNotIn(identifier, data)

    def test_error_does_not_save_source(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(s, 'STATE', Path(temp)), patch.object(s, 'llm', side_effect=RuntimeError('private text')):
            self.assertFalse(s.process(message().as_bytes()))
            self.assertEqual(list(Path(temp).glob('*.json')), [])
            hold = s.HoldStore(temp).load(s.HoldStore(temp).tickets()[0]).record
            self.assertEqual(hold, {'status': 'open', 'reason': 'processing_failed', 'source': None})

    def test_candidate_always_requires_review(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(s, 'STATE', Path(temp)), patch.object(s, 'llm', side_effect=[
            {'subject': 'Workflow', 'body': 'General question', 'uncertain': False},
            {'suspected_phi': False, 'uncertain': False}]):
            self.assertTrue(s.process(message().as_bytes()))
            record = json.loads(next(Path(temp).glob('*.json')).read_text())
            self.assertEqual(record['status'], 'needs_local_review')
            self.assertNotIn('From', record)

    def test_cloud_model_blocked(self):
        with patch.object(s, 'api', return_value={'models': [{'name': s.MODEL, 'remote_host': 'cloud'}]}):
            with self.assertRaises(s.Blocked):
                s.ensure_local_model()

    def test_schema_invalid_and_truncation_blocked(self):
        for response in [
            {'done': True, 'done_reason': 'length', 'message': {'content': '{}'}},
            {'done': True, 'done_reason': 'stop', 'message': {'content': '{"subject":"a","body":"b","uncertain":"false"}'}},
        ]:
            with patch.object(s, 'api', return_value=response):
                with self.assertRaises(s.Blocked):
                    s.llm('test', {}, s.SCHEMA)


if __name__ == '__main__':
    unittest.main()
