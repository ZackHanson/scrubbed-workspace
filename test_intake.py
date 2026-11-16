"""Deterministic synthetic ledger tests; no Gmail, model or runtime state."""
import hashlib
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from holds import account_hash, file_source
from intake import IntakeLedger, IntakeError, fetch_gmail
import scrubber


RECORD = {'status': 'needs_local_review', 'subject': 'General', 'body': 'Workflow question.'}


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.now = 100
        self.ledger = IntakeLedger(self.root, clock=lambda: self.now)
        self.source = {'kind': 'gmail', 'account_hash': account_hash('synthetic@example.invalid'),
                       'uidvalidity': '123', 'uid': '7'}

    def register(self, **changes):
        return self.ledger.ingest({**self.source, **changes}, fingerprint=hashlib.sha256(b'Synthetic original').hexdigest())

    def finish(self, ticket):
        claim = self.ledger.claim(ticket)
        self.ledger.complete(claim, RECORD)
        return claim

    def test_ingest_deduplicates_across_reopen_and_normalizes_uid(self):
        ticket = self.register()
        other = IntakeLedger(self.root)
        self.assertEqual(other.ingest({**self.source, 'uid': '0007', 'mailbox': 'inbox'}), ticket)

    def test_accounts_mailboxes_and_uids_are_separate(self):
        tickets = {self.register(), self.register(uid='8'), self.register(mailbox='Other'),
                   self.register(account_hash=account_hash('other@example.invalid'))}
        self.assertEqual(len(tickets), 4)

    def test_epoch_change_blocks_even_new_uid(self):
        self.register()
        with self.assertRaises(IntakeError) as caught:
            self.register(uidvalidity='124', uid='8')
        self.assertEqual(caught.exception.code, 'source_changed')

    def test_missing_invalid_zero_and_overflow_identity_rejected(self):
        for source in [None, {}, {**self.source, 'uid': '0'},
                       {**self.source, 'uidvalidity': '4294967296'},
                       {**self.source, 'password': 'synthetic-only'}]:
            with self.subTest(source=source), self.assertRaises(IntakeError):
                self.ledger.ingest(source)

    def test_changed_file_and_changed_gmail_bytes_fail_closed(self):
        path = self.root / 'synthetic.eml'
        source = file_source(path, b'Synthetic A')
        self.ledger.ingest(source)
        with self.assertRaises(IntakeError):
            self.ledger.ingest(file_source(path, b'Synthetic B'))
        digest = hashlib.sha256(b'Synthetic A').hexdigest()
        self.ledger.ingest(self.source, fingerprint=digest)
        with self.assertRaises(IntakeError):
            self.ledger.ingest(self.source, fingerprint=hashlib.sha256(b'Synthetic B').hexdigest())

    def test_live_claim_exclusive_and_expired_worker_fenced(self):
        ticket = self.register()
        old = self.ledger.claim(ticket, lease_seconds=5)
        self.assertIsNone(IntakeLedger(self.root, clock=lambda: self.now).claim(ticket))
        self.now += 6
        new = self.ledger.claim(ticket)
        with self.assertRaises(IntakeError):
            self.ledger.complete(old, RECORD)
        with self.assertRaises(IntakeError):
            self.ledger.block(old, 'model_error')
        self.ledger.complete(new, RECORD)
        self.assertEqual(self.ledger.status(ticket)['attempts'], 2)

    def test_concurrent_workers_only_one_claims(self):
        ticket = self.register()
        def claim(_):
            return IntakeLedger(self.root, clock=lambda: self.now).claim(ticket)
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(claim, range(2)))
        self.assertEqual(sum(c is not None for c in results), 1)

    def test_operations_work_list_and_private_source_contract(self):
        ticket = self.ledger.ingest(self.source)
        self.assertEqual(self.ledger.work_tickets(), [ticket])
        self.assertEqual(self.ledger.private_source(ticket), {'source': self.source, 'source_version': None})
        raw_hash = hashlib.sha256(b'Synthetic original').hexdigest()
        self.ledger.ingest(self.source, fingerprint=raw_hash)
        claim = self.ledger.claim(ticket, lease_seconds=1)
        self.assertEqual(self.ledger.work_tickets(), [])

        self.now += 1
        self.assertEqual(self.ledger.work_tickets(), [ticket])
        self.assertEqual(self.ledger.private_source(ticket)['source_version'], raw_hash)
        new = self.ledger.claim(ticket)
        self.ledger.block(new, 'model_error')
        self.assertEqual(self.ledger.work_tickets(), [])

    def test_unfetched_gmail_cannot_complete(self):
        ticket = self.ledger.ingest(self.source)
        claim = self.ledger.claim(ticket)
        with self.assertRaises(IntakeError):
            self.ledger.complete(claim, RECORD)

    def test_hold_write_failure_repaired_without_new_inference(self):
        raw = b'Subject: Synthetic\n\nGeneral workflow.'
        with patch.object(scrubber, 'STATE', self.root), patch.object(scrubber, 'scrub', side_effect=scrubber.Blocked('model_error')) as model:
            with patch('scrubber.HoldStore.create', side_effect=OSError('Synthetic failure')):
                with self.assertRaises(OSError):
                    scrubber.process(raw, self.source)
            self.assertFalse(scrubber.process(raw, self.source))
            self.assertEqual(model.call_count, 1)
        self.assertEqual(len(list((self.root / 'holds').glob('*.json'))), 1)

    def test_expired_worker_cannot_complete_before_reclaim(self):
        ticket = self.register()
        claim = self.ledger.claim(ticket, lease_seconds=1)
        self.now += 1
        with self.assertRaises(IntakeError):
            self.ledger.complete(claim, RECORD)

    def test_completion_idempotent_but_different_result_rejected(self):
        ticket = self.register()
        claim = self.finish(ticket)
        self.ledger.complete(claim, RECORD)
        with self.assertRaises(IntakeError):
            self.ledger.complete(claim, {**RECORD, 'body': 'Different'})
        self.assertIsNone(self.ledger.claim(ticket))

    def test_block_requires_explicit_retry_and_fences_previous_claim(self):
        ticket = self.register()
        old = self.ledger.claim(ticket)
        self.ledger.block(old, 'model_error')
        self.ledger.block(old, 'model_error')
        self.assertIsNone(self.ledger.claim(ticket))
        self.assertTrue(self.ledger.retry(ticket))
        self.assertFalse(self.ledger.retry(ticket))
        self.assertEqual(self.ledger.status(ticket)['retry_generation'], 1)
        new = self.ledger.claim(ticket)
        with self.assertRaises(IntakeError):
            self.ledger.complete(old, RECORD)
        self.ledger.complete(new, RECORD)

    def test_committed_result_repairs_interrupted_candidate_write(self):
        ticket = self.register()
        self.finish(ticket)
        with patch('intake.os.link', side_effect=OSError('synthetic disk failure')):
            with self.assertRaises(OSError):
                self.ledger.materialize(ticket)
        self.assertEqual(list(self.ledger.folder.glob('tmp*')), [])
        reopened = IntakeLedger(self.root)
        reopened.materialize(ticket)
        path = self.root / (ticket + '.json')
        self.assertEqual(json.loads(path.read_text()), RECORD)
        path.write_text(json.dumps({**RECORD, 'status': 'rejected_locally'}))
        reopened.materialize(ticket)
        self.assertEqual(json.loads(path.read_text())['status'], 'rejected_locally')

    def test_routing_api_has_no_source_identity_or_headers(self):
        ticket = self.register()
        self.ledger.link_thread(ticket, '<synthetic-message@example.invalid>')
        self.finish(ticket)
        output = self.ledger.successful_records()
        self.assertEqual(output, [{'ticket': ticket, 'record': RECORD}])
        serialized = json.dumps(output)
        for value in [self.source['account_hash'], 'uidvalidity', 'example.invalid', 'mailbox']:
            self.assertNotIn(value, serialized)
        database_bytes = self.ledger.path.read_bytes()
        self.assertNotIn(b'<synthetic-message@example.invalid>', database_bytes)

    def test_thread_context_links_exact_references_with_scope_isolation(self):
        first = self.register()
        second = self.register(uid='8')
        other = self.register(uid='9', mailbox='Other')
        self.ledger.link_thread(first, '<one>')
        self.ledger.link_thread(second, '<two>', ['<one>'])
        self.ledger.link_thread(other, '<three>', ['<one>'])
        for ticket in (first, second, other):
            self.finish(ticket)
        self.assertEqual([r['ticket'] for r in self.ledger.context(second)], [first, second])
        self.assertEqual([r['ticket'] for r in self.ledger.context(other)], [other])
        self.assertEqual(len(self.ledger.context(first, limit=1)), 1)

    def test_ambiguous_threads_fail_closed(self):
        first, second, third = self.register(), self.register(uid='8'), self.register(uid='9')
        self.ledger.link_thread(first, '<one>')
        self.ledger.link_thread(second, '<two>')
        with self.assertRaises(IntakeError):
            self.ledger.link_thread(third, '<three>', ['<one>', '<two>'])

    def test_late_thread_link_keeps_old_message_id_alias(self):
        first, second, third = self.register(), self.register(uid='8'), self.register(uid='9')
        self.ledger.link_thread(first, '<one>')
        self.ledger.link_thread(second, '<two>')
        self.ledger.link_thread(second, '<two>', ['<one>'])
        self.ledger.link_thread(third, '<three>', ['<two>'])
        for ticket in (first, second, third):
            self.finish(ticket)
        self.assertEqual(len(self.ledger.context(third)), 3)

    def gmail_client(self, *, size_uid='7', body_uid='7', size=None):
        raw = b'Subject: Synthetic\n\nGeneral workflow.'
        client = MagicMock()
        client.response.return_value = ('UIDVALIDITY', [b'123'])
        client.uid.side_effect = [('OK', [f'99 (UID {size_uid} RFC822.SIZE {len(raw) if size is None else size})'.encode()]),
                                  ('OK', [(f'99 (UID {body_uid} BODY[]'.encode(), raw), b')'])]
        return client, raw

    def test_fetch_checks_uid_not_sequence_number_and_uses_peek(self):
        client, raw = self.gmail_client()
        self.assertEqual(fetch_gmail(client, self.source), raw)
        self.assertEqual(client.uid.call_args_list[1].args, ('fetch', '7', '(UID BODY.PEEK[])'))

    def test_fetch_mismatches_fail_closed(self):
        for options in ({'size_uid': '8'}, {'body_uid': '8'}, {'size': 1}):
            client, _ = self.gmail_client(**options)
            with self.subTest(options=options), self.assertRaises(IntakeError) as caught:
                fetch_gmail(client, self.source)
            self.assertEqual(caught.exception.code, 'source_changed')

    def test_epoch_changes_during_fetch_fail_closed(self):
        client, _ = self.gmail_client()
        client.response.side_effect = [('UIDVALIDITY', [b'123']), ('UIDVALIDITY', [b'124'])]
        with self.assertRaises(IntakeError):
            fetch_gmail(client, self.source)

    def test_missing_epoch_or_oversized_message_blocks_before_body_fetch(self):
        client, _ = self.gmail_client(size=999999)
        with self.assertRaises(IntakeError) as caught:
            fetch_gmail(client, self.source)
        self.assertEqual(caught.exception.code, 'oversized')
        self.assertEqual(client.uid.call_count, 1)
        client.reset_mock()
        client.response.return_value = ('UIDVALIDITY', [None])
        with self.assertRaises(IntakeError):
            fetch_gmail(client, self.source)
        client.uid.assert_not_called()

    def test_source_backed_process_deduplicates_inference_and_candidates(self):
        raw = b'Subject: Synthetic\n\nGeneral question.'
        with patch.object(scrubber, 'STATE', self.root), patch.object(scrubber, 'scrub', return_value=RECORD) as model:
            self.assertTrue(scrubber.process(raw, self.source))
            self.assertTrue(scrubber.process(raw, self.source))
            self.assertEqual(model.call_count, 1)
        self.assertEqual(len(list(self.root.glob('*.json'))), 1)

    def test_failed_process_not_repeated_until_explicit_retry(self):
        raw = b'Subject: Synthetic\n\nGeneral question.'
        with patch.object(scrubber, 'STATE', self.root), patch.object(scrubber, 'scrub', side_effect=scrubber.Blocked('model_error')) as model:
            self.assertFalse(scrubber.process(raw, self.source))
            self.assertFalse(scrubber.process(raw, self.source))
            self.assertEqual(model.call_count, 1)
        self.assertEqual(len(list((self.root / 'holds').glob('*.json'))), 1)

    def test_full_synthetic_batch_fixture_offline(self):
        import synthetic_check
        def model(system, data, schema):
            if schema is scrubber.CHECK_SCHEMA:
                body = data.get('body', '')
                flag = any(value in body for value in ('Mara', 'June 4', '94 years'))
                return {'suspected_phi': flag, 'uncertain': False}
            return {'subject': 'General workflow',
                    'body': 'General hypertension diabetes asthma inhaler workflow.',
                    'uncertain': False}
        with patch.object(scrubber, 'ensure_local_model'), patch.object(scrubber, 'llm', side_effect=model), patch('sys.argv', ['synthetic_check.py']):
            self.assertEqual(synthetic_check.main(), 0)


if __name__ == '__main__':
    unittest.main()
