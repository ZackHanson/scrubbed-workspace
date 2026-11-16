"""Deterministic operations tests: synthetic payloads and temporary state only."""
from dataclasses import asdict
from contextlib import closing
import io
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import operations as o


KEY = 'a' * 32
PRIVATE = 'synthetic-private-address@example.invalid synthetic-secret synthetic-body'


class FakeIntake:
    def __init__(self, items=None):
        self.items = items if items is not None else [o.WorkItem(KEY, PRIVATE)]

    def poll(self, limit, credentials):
        return iter(self.items)


class FakeRouter:
    def __init__(self, results=None):
        self.results = iter(results or ['shadow'])
        self.calls = 0

    def shadow(self, item):
        self.calls += 1
        result = next(self.results)
        if isinstance(result, BaseException):
            raise result
        return result


class OperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / 'state'

    def states(self, folder=None):
        with closing(sqlite3.connect((folder or self.folder) / 'operations.sqlite3')) as db:
            return db.execute('SELECT key,state,attempts,due FROM jobs ORDER BY key').fetchall()

    def test_default_shadow_no_delivery_and_dedup(self):
        router = FakeRouter()
        runner = o.Runner(self.folder, FakeIntake(), router, config=o.Config(cycles=3))
        report = runner.run()
        self.assertEqual((report.cycles, report.attempted, report.shadow), (3, 1, 1))
        self.assertEqual(runner.run().attempted, 0)
        self.assertEqual(router.calls, 1)
        for config in ({'shadow': False}, {'remote_delivery': True}):
            with self.assertRaisesRegex(o.OperationsError, 'delivery_unavailable'):
                o.Config(**config)

    def test_batch_and_cycles_bound_even_infinite_intake(self):
        import itertools
        class Infinite:
            def poll(self, limit, credentials):
                return (o.WorkItem(f'{n:032x}') for n in itertools.count())
        report = o.Runner(self.folder, Infinite(), FakeRouter(['shadow'] * 3),
                          config=o.Config(batch_size=3)).run()
        self.assertEqual(report.attempted, 3)

    def test_retry_backoff_persisted_and_attempts_capped(self):
        now = [100.0]
        router = FakeRouter([o.RetryableError(PRIVATE)] * 3)
        runner = o.Runner(self.folder, FakeIntake(), router, clock=lambda: now[0],
                          config=o.Config(backoff_seconds=5, max_backoff_seconds=6))
        self.assertEqual(runner.run().deferred, 1)
        self.assertEqual(self.states()[0][3], 105)
        self.assertEqual(runner.run().attempted, 0)
        now[0] = 105
        runner.run()
        self.assertEqual(self.states()[0][3], 111)
        now[0] = 111
        self.assertEqual(runner.run().exceptions, 1)
        now[0] = 1000
        self.assertEqual(runner.run().attempted, 0)
        self.assertEqual(router.calls, 3)

    def test_interrupt_is_uncertain_and_not_retried(self):
        router = FakeRouter([KeyboardInterrupt(PRIVATE), 'shadow'])
        runner = o.Runner(self.folder, FakeIntake(), router)
        report = runner.run()
        self.assertTrue(report.interrupted)
        self.assertEqual(report.uncertain, 1)
        self.assertEqual(self.states()[0][1], 'uncertain')
        self.assertEqual(runner.run().attempted, 0)
        o.reconcile(self.folder, KEY, 'retry')
        self.assertEqual(runner.run().shadow, 1)

    def test_crash_claim_recovers_to_uncertain(self):
        with o.instance_lock(self.folder), o.ledger(self.folder) as db, db:
            db.execute('INSERT INTO jobs VALUES (?,?,?,?,?)', (KEY, 'claimed', 1, 0, 1))
        router = FakeRouter()
        report = o.Runner(self.folder, FakeIntake(), router).run()
        self.assertEqual(report.recovered, 1)
        self.assertEqual(router.calls, 0)
        o.reconcile(self.folder, KEY, 'shadow')
        self.assertEqual(self.states()[0][1], 'shadow')
        with self.assertRaises(o.OperationsError):
            o.reconcile(self.folder, KEY, 'retry')

    def test_unknown_error_and_bad_outcome_fail_closed_without_payload(self):
        notifications = []
        runner = o.Runner(self.folder, FakeIntake(), FakeRouter([ValueError(PRIVATE)]),
                          notify=notifications.append, credentials=o.MemoryCredentials({'gmail': PRIVATE}))
        report = runner.run()
        self.assertEqual(report.uncertain, 1)
        self.assertEqual(len(notifications), 1)
        serialized = json.dumps(notifications)
        self.assertNotIn(KEY, serialized)
        self.assertNotIn(PRIVATE, serialized)
        for path in self.folder.iterdir():
            self.assertNotIn(PRIVATE.encode(), path.read_bytes())
        o.reconcile(self.folder, KEY, 'retry')
        runner.router = FakeRouter(['unrecognized ' + PRIVATE])
        self.assertEqual(runner.run().uncertain, 1)

    def test_single_instance_and_crash_released_os_lock(self):
        with o.instance_lock(self.folder):
            with self.assertRaisesRegex(o.OperationsError, 'already_running'):
                o.Runner(self.folder, FakeIntake(), FakeRouter()).run()
            with self.assertRaises(o.OperationsError):
                o.backup(self.folder, Path(self.temp.name) / 'locked.sqlite3')
        # A persistent lock file is safe: the OS lock, not file existence, owns it.
        self.assertTrue((self.folder / 'operations.lock').exists())
        self.assertEqual(o.Runner(self.folder, FakeIntake(), FakeRouter()).run().shadow, 1)

    def test_process_exit_releases_lock_and_preserves_claim(self):
        # Crash a synthetic child without cleanup, not a service or email process.
        script = '''
import os, sys
import operations as o
with o.instance_lock(sys.argv[1]), o.ledger(sys.argv[1]) as db, db:
    db.execute('INSERT INTO jobs VALUES (?,?,?,?,?)', ('a'*32, 'claimed', 1, 0, 1))
    db.commit()
    os._exit(7)
'''
        child = subprocess.run([sys.executable, '-B', '-c', script, str(self.folder)],
                               capture_output=True, timeout=10)
        self.assertEqual(child.returncode, 7)
        report = o.Runner(self.folder, FakeIntake(), FakeRouter()).run()
        self.assertEqual((report.recovered, report.attempted), (1, 0))

    def test_lowered_attempt_limit_does_not_retry(self):
        runner = o.Runner(self.folder, FakeIntake(), FakeRouter([o.RetryableError()]),
                          config=o.Config(backoff_seconds=0))
        runner.run()
        runner.config = o.Config(max_attempts=1)
        report = runner.run()
        self.assertEqual((report.attempted, report.exceptions), (0, 1))

    def test_fresh_restore_is_inactive_and_preserves_dedup(self):
        o.Runner(self.folder, FakeIntake(), FakeRouter()).run()
        # Nearby credentials/private files are deliberately outside snapshot scope.
        (self.folder / 'credentials.fake').write_text(PRIVATE)
        snapshot = Path(self.temp.name) / 'recovery.sqlite3'
        o.backup(self.folder, snapshot)
        self.assertNotIn(PRIVATE.encode(), snapshot.read_bytes())
        fresh = Path(self.temp.name) / 'restored'
        o.restore(snapshot, fresh)
        self.assertEqual([p.name for p in fresh.iterdir()], ['operations.sqlite3'])
        router = FakeRouter()
        runner = o.Runner(fresh, FakeIntake(), router)
        with self.assertRaisesRegex(o.OperationsError, 'restore_requires_acknowledgement'):
            runner.run()
        o.acknowledge_restore(fresh)
        self.assertEqual(runner.run().attempted, 0)
        self.assertEqual(router.calls, 0)
        self.assertEqual(self.states(), self.states(fresh))
        with self.assertRaises(FileExistsError):
            o.restore(snapshot, fresh)
        with self.assertRaises(FileExistsError):
            o.backup(self.folder, snapshot)

    def test_backup_claim_restore_still_requires_reconciliation(self):
        with o.instance_lock(self.folder), o.ledger(self.folder) as db, db:
            db.execute('INSERT INTO jobs VALUES (?,?,?,?,?)', (KEY, 'claimed', 1, 0, 1))
        snapshot = Path(self.temp.name) / 'snapshot.sqlite3'
        o.backup(self.folder, snapshot)
        fresh = Path(self.temp.name) / 'fresh'
        o.restore(snapshot, fresh)
        o.acknowledge_restore(fresh)
        report = o.Runner(fresh, FakeIntake(), FakeRouter()).run()
        self.assertEqual((report.recovered, report.attempted), (1, 0))

    def test_foreign_database_not_modified_or_restored(self):
        self.folder.mkdir()
        foreign = self.folder / 'operations.sqlite3'
        with closing(sqlite3.connect(foreign)) as db, db:
            db.execute('CREATE TABLE unrelated (value TEXT)')
        before = foreign.read_bytes()
        with self.assertRaisesRegex(o.OperationsError, 'invalid_ledger'):
            o.Runner(self.folder, FakeIntake(), FakeRouter()).run()
        self.assertEqual(foreign.read_bytes(), before)
        fresh = Path(self.temp.name) / 'fresh'
        with self.assertRaisesRegex(o.OperationsError, 'backup_invalid'):
            o.restore(foreign, fresh)
        self.assertFalse(fresh.exists())

    def test_notification_failure_does_not_repeat_work(self):
        def bad_notify(report):
            raise ValueError(PRIVATE)
        runner = o.Runner(self.folder, FakeIntake(), FakeRouter(['exception']), notify=bad_notify)
        self.assertEqual(runner.run().notification_errors, 1)
        self.assertEqual(runner.run().attempted, 0)

    def test_intake_error_fixed_summary(self):
        class Broken:
            def poll(self, limit, credentials):
                raise ValueError(PRIVATE)
        report = o.Runner(self.folder, Broken(), FakeRouter()).run()
        self.assertEqual(report.intake_errors, 1)
        self.assertNotIn(PRIVATE, json.dumps(asdict(report)))

    def test_retention_is_preview_and_capacity_fails_closed(self):
        config = o.Config(max_ledger_items=1)
        runner = o.Runner(self.folder, FakeIntake(), FakeRouter(), config=config)
        runner.run()
        preview = o.retention_preview(self.folder, 1e20)
        self.assertEqual(preview, {'terminal_records_older_than_cutoff': 1, 'deletion_enabled': False})
        runner.intake = FakeIntake([o.WorkItem('b' * 32)])
        self.assertEqual(runner.run().intake_errors, 1)
        self.assertEqual(len(self.states()), 1)

    def test_invalid_config_and_private_key_rejected(self):
        for kwargs in ({'cycles': 0}, {'batch_size': True}, {'max_attempts': 11},
                       {'backoff_seconds': float('nan')}, {'cycle_pause_seconds': 31}):
            with self.assertRaises(o.OperationsError):
                o.Config(**kwargs)
        with self.assertRaises(o.OperationsError):
            o.WorkItem(PRIVATE)
        provider = o.MemoryCredentials({'gmail': PRIVATE})
        self.assertNotIn(PRIVATE, repr(provider))
        self.assertEqual(provider.get('gmail'), PRIVATE)
        provider.clear()
        self.assertIsNone(provider.get('gmail'))

    def test_cli_demo_and_schedule_are_inert(self):
        with patch('sys.stdout', new_callable=io.StringIO) as output:
            self.assertEqual(o.main(['demo']), 0)
            self.assertEqual(json.loads(output.getvalue())['shadow'], 1)
        with patch('sys.stdout', new_callable=io.StringIO) as output:
            o.main(['schedule-preview', '--enabled', '--interval-minutes', '30'])
            preview = json.loads(output.getvalue())
        self.assertFalse(preview['installed'])
        self.assertFalse(preview['automatic_startup'])
        self.assertTrue(preview['runner']['shadow'])
        self.assertFalse(preview['runner']['remote_delivery'])


if __name__ == '__main__':
    unittest.main()
