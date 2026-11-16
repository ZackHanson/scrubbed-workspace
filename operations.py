"""Manually invoked shadow operations. No network, credential storage or scheduler."""
from __future__ import annotations

import argparse
from contextlib import closing, contextmanager
from dataclasses import asdict, dataclass, field
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time
from typing import Callable, Iterable, Protocol
from state_access import state_context, state_mutation, state_read


class OperationsError(Exception):
    """Fixed, content-free operational error."""


class RetryableError(Exception):
    """Adapter guarantees no side effect occurred; retry is safe."""


@dataclass(frozen=True)
class WorkItem:
    # Random stable local ID, never an address, source path, UID or content hash.
    key: str
    payload: object = field(default=None, repr=False, compare=False)
    retry_generation: int = 0

    def __post_init__(self):
        if not isinstance(self.key, str) or not re.fullmatch(r'[0-9a-f]{32}', self.key):
            raise OperationsError('invalid_operation_id')
        if type(self.retry_generation) is not int or self.retry_generation < 0:
            raise OperationsError('invalid_retry_generation')


class CredentialProvider(Protocol):
    def get(self, purpose: str) -> object: ...


class MemoryCredentials:
    """Explicit memory-only injection; no keyring, file or environment fallback."""
    def __init__(self, values=None):
        self._values = dict(values or {})

    def get(self, purpose):
        return self._values.get(purpose)

    def clear(self):
        self._values.clear()

    def __repr__(self):
        return 'MemoryCredentials()'


class Intake(Protocol):
    def poll(self, limit: int, credentials: CredentialProvider) -> Iterable[WorkItem]:
        """Bounded local read; reoffer IDs until runner has a terminal receipt."""
        ...


class Router(Protocol):
    def shadow(self, item: WorkItem) -> str:
        """Idempotent by item.key; return 'shadow' or 'exception'. Never deliver."""
        ...


@dataclass(frozen=True)
class Config:
    cycles: int = 1
    batch_size: int = 20
    max_attempts: int = 3
    backoff_seconds: float = 5
    max_backoff_seconds: float = 300
    cycle_pause_seconds: float = 0
    max_ledger_items: int = 100_000
    shadow: bool = True
    remote_delivery: bool = False

    def __post_init__(self):
        for value, upper in ((self.cycles, 100), (self.batch_size, 100),
                             (self.max_attempts, 10), (self.max_ledger_items, 1_000_000)):
            if type(value) is not int or not 1 <= value <= upper:
                raise OperationsError('invalid_config')
        for value, upper in ((self.backoff_seconds, 3600),
                             (self.max_backoff_seconds, 3600),
                             (self.cycle_pause_seconds, 30)):
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= upper:
                raise OperationsError('invalid_config')
        if self.shadow is not True or self.remote_delivery is not False:
            raise OperationsError('delivery_unavailable')


@dataclass
class Summary:
    cycles: int = 0
    attempted: int = 0
    shadow: int = 0
    exceptions: int = 0
    deferred: int = 0
    uncertain: int = 0
    recovered: int = 0
    intake_errors: int = 0
    notification_errors: int = 0
    interrupted: bool = False


@contextmanager
def instance_lock(folder):
    """Kernel lock survives neither crash nor exit; never remove a 'stale' file."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / 'operations.lock'
    if path.is_symlink():
        raise OperationsError('unsafe_state_path')
    handle = path.open('a+b')
    acquired = False
    try:
        if os.name == 'nt':
            import msvcrt
            handle.seek(0, 2)
            if handle.tell() == 0:
                handle.write(b'0')
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise OperationsError('already_running') from None
        else:
            import fcntl
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                raise OperationsError('already_running') from None
        acquired = True
        yield
    finally:
        if acquired:
            if os.name == 'nt':
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()


SCHEMA = """CREATE TABLE IF NOT EXISTS jobs (
    key TEXT PRIMARY KEY, state TEXT NOT NULL CHECK(state IN
    ('claimed','retry','shadow','exception','uncertain')),
    attempts INTEGER NOT NULL, due REAL NOT NULL, updated REAL NOT NULL);
    CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS retry_generation (key TEXT PRIMARY KEY, generation INTEGER NOT NULL);
    PRAGMA user_version=1;
    PRAGMA application_id=1398230864;
"""


@state_context(lambda folder: folder)
@contextmanager
def ledger(folder):
    path = Path(folder) / 'operations.sqlite3'
    if path.is_symlink():
        raise OperationsError('unsafe_state_path')
    existed = path.exists()
    db = sqlite3.connect(path)
    try:
        if existed and (db.execute('PRAGMA application_id').fetchone() != (1398230864,)
                        or db.execute('PRAGMA user_version').fetchone() != (1,)):
            raise OperationsError('invalid_ledger')
        db.execute('PRAGMA synchronous=FULL')
        db.executescript(SCHEMA)
        yield db
    finally:
        db.close()


class Runner:
    @state_read(lambda self, folder, *args, **kwargs: folder)
    def __init__(self, folder, intake: Intake, router: Router, *, config=None,
                 credentials=None, notify: Callable[[dict], None] | None = None,
                 clock=time.time, sleep=time.sleep):
        self.folder, self.intake, self.router = Path(folder), intake, router
        self.config = config or Config()
        self.credentials = credentials if credentials is not None else MemoryCredentials()
        self.notify = notify
        self.clock, self.sleep = clock, sleep

    @state_mutation('folder')
    def run(self):
        report = Summary()
        with instance_lock(self.folder), ledger(self.folder) as db:
            if db.execute("SELECT 1 FROM metadata WHERE key='restore_pending'").fetchone():
                raise OperationsError('restore_requires_acknowledgement')
            with db:
                report.recovered = db.execute(
                    "UPDATE jobs SET state='uncertain', updated=? WHERE state='claimed'",
                    (self.clock(),)).rowcount
            try:
                for cycle in range(self.config.cycles):
                    report.cycles += 1
                    # Consume at most batch_size, even if a buggy adapter ignores limit.
                    try:
                        iterator = iter(self.intake.poll(self.config.batch_size, self.credentials))
                        for _ in range(self.config.batch_size):
                            try:
                                item = next(iterator)
                            except StopIteration:
                                break
                            if not isinstance(item, WorkItem):
                                raise OperationsError('invalid_intake')
                            self._process(db, item, report)
                    except KeyboardInterrupt:
                        raise
                    except Exception:
                        report.intake_errors += 1
                    if cycle + 1 < self.config.cycles and self.config.cycle_pause_seconds:
                        self.sleep(self.config.cycle_pause_seconds)
            except KeyboardInterrupt:
                report.interrupted = True
            # Callback receives only a freshly constructed fixed-schema summary.
            if self.notify and (report.exceptions or report.uncertain or report.recovered
                                or report.intake_errors or report.interrupted):
                try:
                    self.notify(asdict(report))
                except Exception:
                    report.notification_errors += 1
        return report

    def _process(self, db, item, report):
        now = self.clock()
        row = db.execute('SELECT state, attempts, due FROM jobs WHERE key=?', (item.key,)).fetchone()
        prior = db.execute('SELECT generation FROM retry_generation WHERE key=?', (item.key,)).fetchone()
        generation = prior[0] if prior else 0
        explicit_retry = bool(row and row[0] == 'exception' and item.retry_generation > generation)
        if item.retry_generation < generation or (row and row[0] != 'retry' and not explicit_retry):
            return
        if row and not explicit_retry and row[2] > now:
            report.deferred += 1
            return
        if row and not explicit_retry and row[1] >= self.config.max_attempts:
            with db:
                db.execute("UPDATE jobs SET state='exception', updated=? WHERE key=?", (now, item.key))
            report.exceptions += 1
            return
        if not row and db.execute('SELECT count(*) FROM jobs').fetchone()[0] >= self.config.max_ledger_items:
            raise OperationsError('ledger_capacity')
        attempts = (row[1] if row and not explicit_retry else 0) + 1
        with db:
            db.execute('INSERT OR REPLACE INTO retry_generation VALUES (?,?)',
                       (item.key, item.retry_generation))
            db.execute('INSERT OR REPLACE INTO jobs VALUES (?, ?, ?, ?, ?)',
                       (item.key, 'claimed', attempts, 0, now))
        report.attempted += 1
        try:
            outcome = self.router.shadow(item)
            if outcome not in ('shadow', 'exception'):
                # An invalid return cannot prove whether the adapter persisted work.
                raise OperationsError('invalid_outcome')
        except RetryableError:
            outcome = 'retry' if attempts < self.config.max_attempts else 'exception'
        except BaseException as error:
            with db:
                db.execute("UPDATE jobs SET state='uncertain', updated=? WHERE key=?",
                           (self.clock(), item.key))
            report.uncertain += 1
            # Never record exception strings, reprs or payloads. Preserve cancellation.
            if not isinstance(error, Exception):
                raise
            return
        delay = min(self.config.max_backoff_seconds,
                    self.config.backoff_seconds * 2 ** (attempts - 1)) if outcome == 'retry' else 0
        with db:
            db.execute('UPDATE jobs SET state=?, due=?, updated=? WHERE key=?',
                       (outcome, self.clock() + delay, self.clock(), item.key))
        if outcome == 'retry':
            report.deferred += 1
        elif outcome == 'exception':
            report.exceptions += 1
        else:
            report.shadow += 1


@state_mutation(lambda folder, *args, **kwargs: folder)
def reconcile(folder, key, outcome):
    """Local adapter/operator proves committed outcome or explicitly certifies safe retry."""
    WorkItem(key)
    if outcome not in ('shadow', 'exception', 'retry'):
        raise OperationsError('invalid_reconciliation')
    with instance_lock(folder), ledger(folder) as db, db:
        changed = db.execute("UPDATE jobs SET state=?, due=0, updated=? WHERE key=? AND state='uncertain'",
                             (outcome, time.time(), key)).rowcount
        if changed != 1:
            raise OperationsError('not_uncertain')


@state_mutation(lambda folder, *args, **kwargs: folder)
def retention_preview(folder, older_than):
    """Counts only. No automatic deletion: retained IDs prevent reimport duplicates."""
    if not math.isfinite(older_than):
        raise OperationsError('invalid_cutoff')
    with instance_lock(folder), ledger(folder) as db:
        return {'terminal_records_older_than_cutoff': db.execute(
            "SELECT count(*) FROM jobs WHERE state IN ('shadow','exception') AND updated<?",
            (older_than,)).fetchone()[0], 'deletion_enabled': False}


def schedule_preview(*, enabled=False, interval_minutes=15, config=None):
    config = config or Config()
    if type(enabled) is not bool or type(interval_minutes) is not int or not 1 <= interval_minutes <= 1440:
        raise OperationsError('invalid_schedule')
    return {'enabled': enabled, 'interval_minutes': interval_minutes,
            'installed': False, 'automatic_startup': False,
            'invocation': 'application adapter must explicitly invoke Runner.run()',
            'runner': asdict(config)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('demo', help='One synthetic cycle in temporary storage; no network')
    schedule = sub.add_parser('schedule-preview', help='Print configuration only; never install')
    schedule.add_argument('--enabled', action='store_true')
    schedule.add_argument('--interval-minutes', type=int, default=15)
    args = parser.parse_args(argv)
    if args.command == 'schedule-preview':
        result = schedule_preview(enabled=args.enabled, interval_minutes=args.interval_minutes)
    else:
        class DemoIntake:
            def poll(self, limit, credentials):
                return [WorkItem('0' * 32, 'synthetic workflow')]

        class DemoRouter:
            def shadow(self, item):
                return 'shadow'

        with tempfile.TemporaryDirectory() as folder:
            result = asdict(Runner(folder, DemoIntake(), DemoRouter()).run())
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OperationsError, OSError, sqlite3.Error):
        print('Operation stopped; check configuration locally.')
        raise SystemExit(1)
