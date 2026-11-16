"""Recovery evidence uses invented fixtures and fresh temporary stores ONLY."""
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from claude_adapter import AdapterConfig, ClaudeAdapter, FakeTransport, ContractError
from holds import HoldStore
from recovery import snapshot, restore, verify_snapshot, acknowledge_restore
from recovery_guard import (RecoveryError, active_state, require_active, state_lock,
                            state_root, _write_state)
from shadow_workflow import ShadowWorkflow
from synthetic_workflow import fixture, submit_fixture, synthetic_checks
import triage


def dump(path):
    with closing(sqlite3.connect(path)) as db:
        return list(db.iterdump())


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='synthetic-recovery-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / 'state'
        self.enterContext(synthetic_checks())
        self.workflow = ShadowWorkflow(self.state)
        self.source = fixture(self.root / 'invented.eml')
        self.ticket = self.workflow.register(self.source)
        self.workflow.run([self.ticket])

    def backup(self, **kwargs):
        return snapshot(self.state, self.root / 'snapshot', **kwargs)

    def test_full_journey_preserves_bindings_revisions_revocations_results_unknown(self):
        external = self.root / 'external'
        external.mkdir()
        adapter = ClaudeAdapter(external / 'adapter.sqlite3', config=AdapterConfig(True),
                                transport=FakeTransport())
        key, version, result = submit_fixture(self.workflow, self.ticket, adapter)
        self.assertEqual(result.status, 'completed')
        self.workflow.capture(self.ticket, adapter, key, expected_candidate_version=version)
        candidate = self.workflow.candidates.load(self.ticket)
        self.workflow.candidates.save(candidate, 'General edit', 'Explain revised general workflow.',
                                      'needs_local_review')
        hold = HoldStore(self.state).load(self.ticket)
        triage.recheck(self.state, hold, triage.draft_message('Correction', 'General workflow.'))
        # A distinct rejected candidate and an uncertain adapter reservation.
        rejected = self.workflow.register(fixture(self.root / 'rejected.eml'))
        self.workflow.run([rejected])
        record = self.workflow.candidates.load(rejected)
        self.workflow.candidates.save(record, record.record['subject'], record.record['body'],
                                      'rejected_locally')
        with closing(sqlite3.connect(adapter.ledger_path)) as db, db:
            db.execute('INSERT INTO submissions(key,status,content_key) VALUES (?,?,?)',
                       ('f' * 64, 'unknown', 'e' * 64))
        with closing(sqlite3.connect(self.workflow.path)) as db:
            self.assertTrue(db.execute('SELECT * FROM checks').fetchall())
            self.assertTrue(db.execute('SELECT * FROM revoked_requests').fetchall())
            self.assertTrue(db.execute('SELECT * FROM review_revisions').fetchall())
        before = {p.relative_to(self.state).as_posix(): dump(p)
                  for p in self.state.rglob('*.sqlite3')}
        archive = self.backup(extra_ledgers={'adapter': adapter.ledger_path})
        manifest = verify_snapshot(archive)
        fresh = restore(archive, self.root / 'restored')
        for name, sql in before.items():
            self.assertEqual(dump(fresh / name), sql)
        for name in manifest['files']:
            self.assertEqual((fresh / name).read_bytes(), (archive / 'data' / name).read_bytes())
        self.assertEqual(dump(fresh / 'auxiliary/adapter.sqlite3'), dump(adapter.ledger_path))
        # Exact full-byte restoration preserves every authored JSON and DB value.
        self.assertEqual(json.loads((fresh / (rejected + '.json')).read_text())['status'], 'rejected_locally')
        with self.assertRaises(RecoveryError):
            require_active(fresh / 'intake/ledger.sqlite3')
        with self.assertRaises(RecoveryError):
            with active_state(fresh):
                ShadowWorkflow(fresh).run([self.ticket])
        acknowledge_restore(fresh, operator_acknowledged=True, reconciliation_recorded=True)
        restored = ShadowWorkflow(fresh)
        self.assertEqual(restored.intake.private_source(self.ticket),
                         self.workflow.intake.private_source(self.ticket))
        self.assertEqual(restored.register(self.source), self.ticket)
        captured = ClaudeAdapter(fresh / 'auxiliary/adapter.sqlite3')
        self.assertEqual(captured.captured(key).result, result.result)
        with self.assertRaises(ContractError):
            captured.captured('f' * 64)
        with closing(sqlite3.connect(captured.ledger_path)) as db:
            self.assertEqual(db.execute('SELECT status FROM submissions WHERE key=?',
                                        ('f' * 64,)).fetchone(), ('unknown',))

    def test_wal_snapshot_includes_committed_bytes_and_excludes_artifacts(self):
        with closing(sqlite3.connect(self.workflow.path)) as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.execute('CREATE TABLE synthetic_wal (value TEXT)')
            db.execute("INSERT INTO synthetic_wal VALUES ('invented')")
            db.commit()
            (self.state / 'excluded.eml').write_bytes(b'Invented original excluded')
            (self.state / 'unused.tmp').write_bytes(b'temporary')
            archive = self.backup()
        manifest = verify_snapshot(archive)
        self.assertFalse(any(n.endswith(('.lock', '.review-lock', '.eml', '-wal', '-shm', '.tmp'))
                             for n in manifest['files']))
        with closing(sqlite3.connect(archive / 'data/workflow.sqlite3')) as db:
            self.assertEqual(db.execute('SELECT * FROM synthetic_wal').fetchall(), [('invented',)])

    def test_missing_truncated_unexpected_and_traversal_fail_closed(self):
        archive = self.backup()
        path = archive / 'data' / (self.ticket + '.json')
        original = path.read_bytes()
        for contents in (b'', original[:-1]):
            path.write_bytes(contents)
            with self.assertRaises(RecoveryError):
                restore(archive, self.root / 'bad')
            self.assertFalse((self.root / 'bad').exists())
        path.unlink()
        with self.assertRaises(RecoveryError):
            verify_snapshot(archive)
        path.write_bytes(original)
        extra = archive / 'extra'
        extra.write_text('invented')
        with self.assertRaises(RecoveryError):
            verify_snapshot(archive)
        extra.unlink()
        manifest_path = archive / 'manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['files']['../escape.json'] = manifest['files'].pop(self.ticket + '.json')
        manifest_path.write_text(json.dumps(manifest))
        with self.assertRaises(RecoveryError):
            restore(archive, self.root / 'bad')

    def test_no_overwrite_or_overlap_or_cleanup(self):
        with self.assertRaises(RecoveryError):
            snapshot(self.state, self.state / 'backup')
        archive = self.backup()
        existing = self.root / 'existing'
        existing.mkdir()
        (existing / 'preserve').write_text('invented other work')
        with self.assertRaises(RecoveryError):
            restore(archive, existing)
        self.assertEqual((existing / 'preserve').read_text(), 'invented other work')
        with self.assertRaises(RecoveryError):
            self.backup()

    def test_unknown_private_files_are_rejected_not_copied(self):
        (self.state / 'credentials.json').write_text('invented credential sentinel')
        with self.assertRaises(RecoveryError):
            self.backup()
        self.assertFalse((self.root / 'snapshot').exists())

    def test_existing_candidate_lock_blocks_without_deleting_others_lock(self):
        lock = self.workflow.candidates.path(self.ticket).with_suffix('.review-lock')
        lock.write_text('invented owner')
        with self.assertRaises(RecoveryError):
            self.backup()
        self.assertEqual(lock.read_text(), 'invented owner')

    def test_sqlite_writer_blocks_snapshot(self):
        with closing(sqlite3.connect(self.workflow.path)) as db:
            db.execute('BEGIN IMMEDIATE')
            with self.assertRaisesRegex(RecoveryError, 'state_busy'):
                self.backup()

    def test_fence_is_ancestor_scoped_and_malformed_fails_closed(self):
        fresh = restore(self.backup(), self.root / 'restored')
        for child in ('operations', 'holds', 'intake/ledger.sqlite3', 'auxiliary/adapter.sqlite3'):
            with self.assertRaises(RecoveryError):
                require_active(fresh / child)
        with self.assertRaises(RecoveryError):
            acknowledge_restore(fresh, operator_acknowledged=True)
        (fresh / '.recovery/state.json').write_text('{}')
        with self.assertRaises(RecoveryError):
            require_active(fresh)

    def test_changed_restore_cannot_be_acknowledged(self):
        fresh = restore(self.backup(), self.root / 'restored')
        (fresh / (self.ticket + '.json')).write_text('{}')
        with self.assertRaises(RecoveryError):
            acknowledge_restore(fresh, operator_acknowledged=True, reconciliation_recorded=True)
        with self.assertRaises(RecoveryError):
            require_active(fresh)

    def test_missing_workflow_store_fails_closed(self):
        (self.state / 'actions.sqlite3').unlink()
        with self.assertRaisesRegex(RecoveryError, 'missing_workflow_store'):
            self.backup()

    def test_guard_io_failure_is_content_free_and_stays_blocked(self):
        fresh = self.root / 'new-state'
        with patch('recovery_guard.os.fsync', side_effect=OSError('invented sensitive path')):
            with self.assertRaisesRegex(RecoveryError, '^recovery_fence_write_failed$'):
                with active_state(fresh):
                    self.fail('must not enter runtime')
        with self.assertRaisesRegex(RecoveryError, '^invalid_recovery_fence$'):
            require_active(fresh)

    def test_failed_restore_retains_partial_fenced_directory(self):
        archive = self.backup()
        fresh = self.root / 'partial'
        from recovery import _hash
        def fail_on_destination(path):
            if Path(path).is_relative_to(fresh):
                raise OSError('invented local source')
            return _hash(path)
        with patch('recovery._hash', side_effect=fail_on_destination):
            with self.assertRaisesRegex(RecoveryError, '^recovery_io_failed$'):
                restore(archive, fresh)
        self.assertTrue(fresh.exists())
        with self.assertRaises(RecoveryError):
            require_active(fresh)
        with self.assertRaises(RecoveryError):
            acknowledge_restore(fresh, operator_acknowledged=True, reconciliation_recorded=True)

    def test_guard_reentrant_normalizes_live_and_old_nested_anchors(self):
        with active_state(self.state / 'routing') as root:
            self.assertEqual(root, self.state)
            with active_state(self.state / 'operations') as nested:
                self.assertEqual(nested, self.state)
        (self.state / 'routing').mkdir(exist_ok=True)
        _write_state(self.state / 'routing', 'active')
        self.assertEqual(state_root(self.state / 'routing'), self.state)
        with active_state(self.state):
            with active_state(self.state / 'routing'):
                require_active(self.state / 'routing')

    def test_cross_thread_and_process_guard_conflicts_fail_closed(self):
        errors = []
        def concurrent():
            try:
                with active_state(self.state / 'routing'):
                    errors.append('unsafe_acquisition')
            except RecoveryError:
                errors.append('blocked')
        with active_state(self.state):
            thread = threading.Thread(target=concurrent)
            thread.start()
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            code = ('from recovery_guard import active_state,RecoveryError; import sys\n'
                    'try:\n with active_state(sys.argv[1]): pass\n'
                    'except RecoveryError: sys.exit(23)\n')
            process = subprocess.run([sys.executable, '-c', code, str(self.state / 'operations')],
                                     capture_output=True, timeout=10)
            self.assertEqual(process.returncode, 23, process.stderr.decode())
        self.assertEqual(errors, ['blocked'])

    def test_symlinks_and_junctions_rejected(self):
        link = self.root / 'linked'
        try:
            link.symlink_to(self.state, target_is_directory=True)
        except OSError:
            if os.name != 'nt':
                raise
            subprocess.run(['cmd', '/c', 'mklink', '/J', str(link), str(self.state)],
                           check=True, capture_output=True)
        try:
            with self.assertRaises(RecoveryError):
                snapshot(link, self.root / 'snapshot')
        finally:
            if link.is_symlink():
                link.unlink()
            else:
                os.rmdir(link)


if __name__ == '__main__':
    unittest.main()
