"""Synthetic local-only action workflow and replay/failure tests."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import copy
import hashlib
from pathlib import Path
import socket
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import actions as a


def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


class FakeProvider:
    """Returns synthetic structured content without any transport or credentials."""
    def complete(self, payload):
        if set(payload) != {'subject', 'body'}:
            raise AssertionError('Private context entered provider payload')
        return {'schema_version': 1, 'actions': [
            {'kind': 'summarize', 'text': 'A general workflow discussion was requested.'},
            {'kind': 'suggest_organization', 'text': 'Consider the Workflow folder.'},
            {'kind': 'draft_reply', 'text': 'Thank you. I can discuss the general workflow.'}]}


class ActionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.network = patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden'))
        self.network.start()
        self.addCleanup(self.network.stop)
        self.path = Path(self.temp.name) / 'actions.sqlite3'
        self.store = a.ActionStore(self.path)
        self.source_version = digest('Synthetic source bytes')
        self.source = {'kind': 'gmail', 'account_hash': digest('synthetic.invalid'),
                       'uidvalidity': '5', 'uid': '12'}
        self.version = digest('Exact synthetic candidate saved bytes')
        self.result = FakeProvider().complete({'subject': 'Workflow', 'body': 'General discussion'})
        self.result_version = a.result_digest(self.result)
        self.bind()
        self.capture()

    def bind(self, **changes):
        args = dict(candidate_id='candidate_1', candidate_version=self.version,
                    source_ref=self.source, source_version=self.source_version)
        self.store.bind_candidate(**(args | changes))

    def capture(self, **changes):
        args = dict(candidate_id='candidate_1', candidate_version=self.version,
                    result_id='result_1', result_version=self.result_version, result=self.result)
        self.store.capture_result(**(args | changes))

    def propose(self, **changes):
        args = dict(request_id='request_1', candidate_id='candidate_1', candidate_version=self.version,
                    result_id='result_1', result_version=self.result_version)
        return self.store.propose(**(args | changes))

    def rejects(self, code, function, **kwargs):
        with self.assertRaisesRegex(a.ActionError, '^' + code + '$'):
            function(**kwargs)

    def test_local_workflow_keeps_exact_private_binding_and_pending_drafts(self):
        receipt = self.propose()
        self.assertEqual(receipt['source_ref'], self.source)
        self.assertEqual(receipt['source_version'], self.source_version)
        self.assertEqual(receipt['candidate_version'], self.version)
        self.assertEqual(receipt['result_version'], self.result_version)
        self.assertEqual([p['status'] for p in receipt['proposals']],
                         ['local_only', 'pending_review', 'pending_review'])
        self.assertEqual(receipt, self.store.read_proposal('request_1'))
        self.assertEqual(set(self.result), {'schema_version', 'actions'})
        self.assertNotIn('source_ref', self.result)

    def test_idempotent_across_reopen_and_returned_mutation(self):
        first = self.propose()
        self.bind()
        self.capture()
        self.store = a.ActionStore(self.path)
        self.assertEqual(first, self.propose())
        first['proposals'][1]['status'] = 'approved'
        first['source_ref']['uid'] = '999'
        again = self.propose()
        self.assertEqual(again['proposals'][1]['status'], 'pending_review')
        self.assertEqual(again['source_ref']['uid'], '12')

    def test_concurrent_exact_retries_create_one_bundle(self):
        with ThreadPoolExecutor(max_workers=4) as workers:
            receipts = list(workers.map(lambda _: self.propose(), range(8)))
        self.assertTrue(all(row == receipts[0] for row in receipts))
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('SELECT count(*) FROM proposals').fetchone()[0], 1)

    def test_different_request_id_cannot_replay_result(self):
        self.propose()
        self.rejects('result_already_proposed', self.propose, request_id='new_request')

    def test_request_id_cannot_be_reused_for_new_result(self):
        first = self.propose()
        self.capture(result_id='result_2', expected_result_id='result_1')
        self.rejects('conflicting_replay', self.propose, result_id='result_2')
        self.assertEqual(self.store.read_proposal('request_1'), first)

    def test_source_is_immutable_and_cross_candidate_reuse_rolls_back(self):
        self.rejects('source_mismatch', self.bind, source_ref=self.source | {'uid': '13'})
        self.rejects('source_mismatch', self.bind, source_version=digest('Changed source bytes'))
        self.rejects('source_already_bound', self.bind, candidate_id='candidate_2')
        self.rejects('missing_context', self.capture, candidate_id='candidate_2', result_id='result_2')
        self.propose()

    def test_missing_or_invalid_source_never_binds(self):
        for source in (None, {}, self.source | {'recipient': 'fake@example.invalid'}):
            self.rejects('invalid_source', self.bind, candidate_id='candidate_2', source_ref=source)

    def test_file_source_requires_exact_original_digest(self):
        source = {'kind': 'file', 'path': str(Path(self.temp.name) / 'synthetic.eml'),
                  'sha256': self.source_version}
        self.rejects('invalid_source', self.bind, candidate_id='file_candidate', source_ref=source,
                     source_version=digest('Wrong bytes'))
        self.bind(candidate_id='file_candidate', source_ref=source)

    def test_missing_candidate_and_missing_result_fail_closed(self):
        self.rejects('missing_context', self.propose, candidate_id='missing')
        self.rejects('stale_result', self.propose, result_id='missing')
        self.bind(candidate_id='new_candidate', source_ref=self.source | {'uid': '13'})
        self.rejects('stale_result', self.propose, candidate_id='new_candidate')

    def test_candidate_change_requires_compare_and_swap_and_invalidates_result(self):
        first = self.propose()
        changed = digest('Edited synthetic candidate')
        self.rejects('stale_candidate', self.bind, candidate_version=changed)
        self.bind(candidate_version=changed, expected_version=self.version)
        self.rejects('stale_candidate', self.propose)
        self.rejects('stale_result', self.propose, candidate_version=changed)
        self.rejects('stale_candidate', self.capture)
        self.rejects('stale_candidate', self.bind, candidate_version=digest('Out of date edit'),
                     expected_version=self.version)
        self.assertEqual(self.store.read_proposal('request_1'), first)

    def test_result_replacement_requires_compare_and_swap(self):
        self.rejects('stale_result', self.capture, result_id='result_2')
        self.capture(result_id='result_2', expected_result_id='result_1')
        self.rejects('stale_result', self.capture)
        self.rejects('stale_result', self.propose)
        self.propose(result_id='result_2')

    def test_result_id_immutable_across_payload_candidate_and_version(self):
        changed = copy.deepcopy(self.result)
        changed['actions'][0]['text'] = 'Changed summary'
        self.rejects('result_mismatch', self.capture, result=changed)
        self.rejects('conflicting_replay', self.capture, result=changed,
                     result_version=a.result_digest(changed))
        self.bind(candidate_id='candidate_2', source_ref=self.source | {'uid': '13'})
        self.rejects('conflicting_replay', self.capture, candidate_id='candidate_2')

    def test_rejection_retains_pending_review_and_cannot_be_undone_by_retry(self):
        first = self.propose()
        self.store.invalidate_candidate(candidate_id='candidate_1', candidate_version=self.version)
        self.store.invalidate_candidate(candidate_id='candidate_1', candidate_version=self.version)
        self.rejects('candidate_inactive', self.bind)
        self.rejects('candidate_inactive', self.capture)
        self.rejects('candidate_inactive', self.propose)
        self.assertEqual(self.store.read_proposal('request_1'), first)

    def test_stale_invalidation_cannot_reject_new_version(self):
        self.rejects('stale_candidate', self.store.invalidate_candidate,
                     candidate_id='candidate_1', candidate_version=digest('Stale'))
        self.propose()

    def test_write_send_and_medical_capabilities_always_disabled(self):
        for capability, enabled in a.CAPABILITIES.items():
            if capability != 'local_proposal':
                self.assertFalse(enabled)
                self.rejects('capability_disabled', self.propose, capability=capability)
        self.rejects('capability_disabled', self.propose, capability='arbitrary_write')
        with self.assertRaises(TypeError):
            a.CAPABILITIES['send_email'] = True

    def test_result_schema_rejects_routing_unknown_actions_and_missing_context(self):
        bad = [None, {}, {'schema_version': True, 'actions': self.result['actions']},
               self.result | {'source_ref': self.source},
               self.result | {'actions': []},
               self.result | {'actions': [{'kind': 'draft_reply', 'text': 'Hello',
                                          'to': 'fake@example.invalid'}]},
               self.result | {'actions': [{'kind': 'draft_reply', 'text': ' '}]},
               self.result | {'actions': [{'kind': [], 'text': 'Hello'}]}]
        for kind in ('send_email', 'write_labels', 'archive_email', 'third_party_message', 'medical_care'):
            bad.append(self.result | {'actions': [{'kind': kind, 'text': 'Attempt'}]})
        for result in bad:
            with self.subTest(result=result):
                self.rejects('invalid_result', self.capture, result=result)

    def test_size_ids_and_versions_are_bounded(self):
        result = self.result | {'actions': [{'kind': 'summarize', 'text': 'x' * a.MAX_RESULT_BYTES}]}
        self.rejects('result_too_large', self.capture, result=result)
        self.rejects('invalid_id', self.propose, request_id='../synthetic')
        self.rejects('invalid_version', self.propose, result_version='not a digest')

    def test_persistence_failure_is_fixed_and_leaves_existing_receipt(self):
        first = self.propose()
        with patch.object(a.sqlite3, 'connect', side_effect=sqlite3.OperationalError('PRIVATE ERROR')):
            self.rejects('store_unavailable', self.propose)
        self.assertEqual(self.store.read_proposal('request_1'), first)

    def test_failed_result_save_rolls_back_current_result_and_retains_review(self):
        first = self.propose()
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("CREATE TRIGGER fail_result BEFORE INSERT ON results "
                       "BEGIN SELECT RAISE(ABORT, 'Synthetic storage failure'); END")
            db.commit()
        self.rejects('store_unavailable', self.capture, result_id='result_2',
                     expected_result_id='result_1')
        self.assertEqual(self.propose(), first)

    def test_failed_proposal_save_can_be_retried_without_duplicate(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("CREATE TRIGGER fail_proposal BEFORE INSERT ON proposals "
                       "BEGIN SELECT RAISE(ABORT, 'Synthetic storage failure'); END")
            db.commit()
        self.rejects('store_unavailable', self.propose)
        self.rejects('missing_context', self.store.read_proposal, request_id='request_1')
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('DROP TRIGGER fail_proposal')
            db.commit()
        first = self.propose()
        self.assertEqual(first, self.propose())

    def test_changed_stored_result_cannot_generate_proposals(self):
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('UPDATE results SET payload=? WHERE id=?',
                       ('{"schema_version":1,"actions":[{"kind":"summarize","text":"Changed"}]}',
                        'result_1'))
            db.commit()
        self.rejects('result_mismatch', self.propose)


if __name__ == '__main__':
    unittest.main()
