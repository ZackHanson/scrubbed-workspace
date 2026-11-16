"""Explicit bounded local shadow batches. No scheduler or Claude transport path.

Callers supply at most 100 opaque intake tickets, not an unbounded mailbox scan.
The CLI exposes only a built-in temporary synthetic demo. Runtime stores and
source readers must stay on the approved local machine, outside this source tree.
"""
from contextlib import closing, contextmanager
from dataclasses import asdict, replace
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import sqlite3
import threading
import time

from actions import ActionStore, result_digest
from holds import HoldError, HoldStore, read_source
from intake import IntakeLedger
from operations import Config, Runner, WorkItem
from review import CandidateStore
import routing
import scrubber


class WorkflowError(Exception):
    """Fixed content-free error category."""


def bounded_compute(function, timeout):
    """Bound waiting; late computation cannot write workflow state.

    Python cannot kill a running inference thread. After timeout, new work in
    this process is refused until it exits; the operations receipt is uncertain.
    There is no automatic retry, including after restart.
    """
    output = queue.Queue(maxsize=1)

    def invoke():
        try:
            output.put((True, function()))
        except BaseException as error:
            output.put((False, error))

    worker = threading.Thread(target=invoke, daemon=True)
    worker.start()
    try:
        ok, value = output.get(timeout=timeout)
    except queue.Empty:
        raise WorkflowError('computation_uncertain') from None
    if not ok:
        raise value
    return value


class ShadowWorkflow:
    def __init__(self, folder, *, source_reader=read_source,
                 check=scrubber.scrub_checked, model_digest=scrubber.ensure_local_model,
                 timeout_seconds=120, clock=time.time, max_evidence_age=3600):
        if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
                or not 0 < timeout_seconds <= 600
                or type(max_evidence_age) not in (int, float)
                or not math.isfinite(max_evidence_age) or not 0 < max_evidence_age <= 3600):
            raise WorkflowError('invalid_config')
        self.root = Path(folder)
        self.intake = IntakeLedger(folder, clock=clock)
        self.candidates = CandidateStore(folder)
        self.actions = ActionStore(self.root / 'actions.sqlite3')
        self.decisions = routing.DecisionStore(self.root / 'routing')
        self.reader, self.check, self.model_digest = source_reader, check, model_digest
        self.timeout, self.clock, self.max_age = timeout_seconds, clock, max_evidence_age
        self.poisoned = False
        self.path = self.root / 'workflow.sqlite3'
        if self.path.is_symlink():
            raise WorkflowError('invalid_store')
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS checks '
                       '(ticket TEXT PRIMARY KEY, evidence TEXT NOT NULL, checked REAL NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS requests '
                       '(key TEXT PRIMARY KEY, ticket TEXT NOT NULL, version TEXT NOT NULL)')

    def register(self, source):
        """Local source registration only. No reads, inference or cloud calls."""
        return self.intake.ingest(source)

    def _compute(self, function):
        if self.poisoned:
            raise WorkflowError('restart_required')
        try:
            return bounded_compute(function, self.timeout)
        except WorkflowError as error:
            if str(error) == 'computation_uncertain':
                self.poisoned = True
            raise

    def _source(self, ticket, *, allow_unbound=False):
        binding = self.intake.private_source(ticket)
        raw = self.reader(binding['source'])
        if (type(raw) is not bytes or len(raw) > scrubber.MAX_BYTES
                or (not (allow_unbound and binding['source_version'] is None)
                    and hashlib.sha256(raw).hexdigest() != binding['source_version'])):
            raise HoldError('source_changed')
        return raw

    def _evidence(self, ticket):
        with closing(sqlite3.connect(self.path)) as db:
            row = db.execute('SELECT evidence,checked FROM checks WHERE ticket=?', (ticket,)).fetchone()
        if row is None:
            return None
        evidence = routing.CheckEvidence(**json.loads(row[0]))
        # Expired/future-dated provenance and a changed installed model HOLD.
        if not 0 <= self.clock() - row[1] <= self.max_age:
            return replace(evidence, auditor='uncertain')
        current = self.model_digest()
        if current != evidence.model_digest:
            return replace(evidence, auditor='uncertain')
        return evidence

    def _prepare(self, ticket):
        state = self.intake.status(ticket)
        if state is None:
            raise WorkflowError('unknown_ticket')
        if state['state'] == 'blocked':
            HoldStore(self.root).create(ticket, state['reason'],
                                       self.intake.private_source(ticket)['source'])
            return False
        if state['state'] != 'completed':
            claim = self.intake.claim(ticket, lease_seconds=self.timeout + 30)
            if claim is None:
                raise WorkflowError('intake_busy')
            try:
                def compute():
                    raw = self._source(ticket, allow_unbound=True)
                    record, evidence = self.check(raw)
                    return record, evidence, hashlib.sha256(raw).hexdigest()
                record, evidence, fingerprint = self._compute(compute)
                if routing.evaluate(record, evidence).outcome != 'WOULD_SEND':
                    raise HoldError('processing_failed')
            except HoldError as error:
                self.intake.block(claim, error.code)
                HoldStore(self.root).create(ticket, error.code,
                                           self.intake.private_source(ticket)['source'])
                return False
            self.intake.ingest(self.intake.private_source(ticket)['source'], fingerprint=fingerprint)
            # Evidence first: an interruption leaves no routable completed item
            # without evidence. Intake's fencing token prevents stale completion.
            with closing(sqlite3.connect(self.path)) as db, db:
                db.execute('INSERT OR REPLACE INTO checks VALUES (?,?,?)',
                           (ticket, json.dumps(asdict(evidence)), self.clock()))
            self.intake.complete(claim, record)
        self.intake.materialize(ticket)
        return True

    @contextmanager
    def _candidate_lock(self, ticket):
        # Cooperate with the desktop review writer across the final version check
        # and local result/proposal commit. Crash locks require local inspection.
        path = self.candidates.path(ticket).with_suffix('.review-lock')
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except OSError:
            raise WorkflowError('candidate_busy') from None
        try:
            os.close(fd)
            yield
        finally:
            path.unlink(missing_ok=True)

    def current(self, ticket):
        """Recheck versions/source/model/age immediately before local consumption."""
        with self._candidate_lock(ticket):
            return self._current(ticket)

    def _current(self, ticket):
        snapshot = self.candidates.load(ticket)
        evidence = self._compute(lambda: (self._source(ticket), self._evidence(ticket))[1])
        decision = self.decisions.record(ticket, snapshot.record, evidence)
        source = self.intake.private_source(ticket)
        # Keep exact file-byte versions separate from canonical content digests.
        self.actions.bind_candidate(candidate_id=ticket, candidate_version=snapshot.digest,
                                    source_ref=source['source'], source_version=source['source_version'],
                                    expected_version=self.actions.candidate_version(ticket))
        if decision.outcome != 'WOULD_SEND':
            self.actions.invalidate_candidate(candidate_id=ticket, candidate_version=snapshot.digest)
        if self.candidates.load(ticket).digest != snapshot.digest:
            raise WorkflowError('candidate_changed')
        return snapshot, decision

    def shadow(self, item):
        ticket, expected = item.payload
        if not self._prepare(ticket):
            return 'exception'
        try:
            snapshot, decision = self.current(ticket)
        except HoldError as error:
            HoldStore(self.root).create(ticket, error.code,
                                       self.intake.private_source(ticket)['source'])
            return 'exception'
        if expected is not None and snapshot.digest != expected:
            raise WorkflowError('candidate_changed')
        # No adapter object, release contract or transport is reachable here.
        if decision.outcome == 'HOLD':
            HoldStore(self.root).create(ticket, 'processing_failed',
                                       self.intake.private_source(ticket)['source'])
        return 'shadow' if decision.outcome == 'WOULD_SEND' else 'exception'

    def run(self, tickets, *, config=None):
        if type(tickets) not in (list, tuple) or not 1 <= len(tickets) <= 100:
            raise WorkflowError('invalid_batch')
        items = []
        for ticket in dict.fromkeys(tickets):
            WorkItem(ticket)  # Validate before touching any source or path.
            state = self.intake.status(ticket)
            version = None
            if state and state['state'] == 'completed':
                self.intake.materialize(ticket)
                version = self.candidates.load(ticket).digest
            # New edits generate new work, but uncertain initial computations
            # retain their original ticket key and cannot be retried on restart.
            key = ticket if version in (None, self.intake.original_candidate_digest(ticket)) else hashlib.sha256(
                (ticket + version + routing.VALIDATOR_VERSION).encode()).hexdigest()[:32]
            items.append(WorkItem(key, (ticket, version),
                                  retry_generation=state['retry_generation'] if state else 0))

        class Batch:
            def poll(self, limit, credentials):
                return iter(items)

        chosen = config or Config(batch_size=len(items))
        if chosen.batch_size < len(items):
            raise WorkflowError('batch_exceeds_config')
        return Runner(self.root / 'operations', Batch(), self, config=chosen).run()

    def capture(self, ticket, adapter, submission_key, *, expected_candidate_version):
        """Consume only a locally durable complete response; never call submit.

        In this task only the separate synthetic harness supplies such a response.
        Every replay checks current state first; historical proposals stay inert.
        """
        with self._candidate_lock(ticket):
            return self._capture(ticket, adapter, submission_key, expected_candidate_version)

    def _capture(self, ticket, adapter, submission_key, expected_candidate_version):
        snapshot, decision = self._current(ticket)
        if decision.outcome != 'WOULD_SEND' or snapshot.digest != expected_candidate_version:
            raise WorkflowError('stale_result')
        with closing(sqlite3.connect(self.path)) as db:
            request = db.execute('SELECT ticket,version FROM requests WHERE key=?',
                                 (submission_key,)).fetchone()
        if request != (ticket, snapshot.digest):
            raise WorkflowError('result_binding_mismatch')
        result = adapter.captured(submission_key)
        payload = {k: snapshot.record[k] for k in ('subject', 'body')}
        from claude_adapter import submission_key as key_for
        # Existing content-only requests may still recover their durable result.
        # New requests are scoped to the immutable local intake ticket.
        if submission_key not in (key_for(payload), key_for(payload, request_scope=ticket)):
            raise WorkflowError('result_binding_mismatch')
        if self.candidates.load(ticket).digest != snapshot.digest:
            raise WorkflowError('candidate_changed')
        version = result_digest(result.result)
        self.actions.capture_result(candidate_id=ticket, candidate_version=snapshot.digest,
                                    result_id=submission_key, result_version=version, result=result.result)
        return self.actions.propose(request_id=submission_key, candidate_id=ticket,
                                    candidate_version=snapshot.digest, result_id=submission_key,
                                    result_version=version)

    def bind_result_request(self, ticket, *, expected_candidate_version):
        """Bind a separate authorized test request BEFORE adapter invocation.

        This is local correlation only, never release authorization. Shadow.run
        cannot reach it. The only supplied caller is the built-in fake harness.
        """
        from claude_adapter import submission_key
        snapshot, decision = self.current(ticket)
        if snapshot.digest != expected_candidate_version or decision.outcome != 'WOULD_SEND':
            raise WorkflowError('stale_request')
        payload = {k: snapshot.record[k] for k in ('subject', 'body')}
        key = submission_key(payload, request_scope=ticket)
        with closing(sqlite3.connect(self.path)) as db, db:
            if db.execute('SELECT 1 FROM requests WHERE key=? AND ticket=?',
                          (submission_key(payload), ticket)).fetchone():
                raise WorkflowError('legacy_request_requires_reconciliation')
            db.execute('INSERT OR IGNORE INTO requests VALUES (?,?,?)', (key, ticket, snapshot.digest))
            if db.execute('SELECT ticket,version FROM requests WHERE key=?', (key,)).fetchone() != (
                    ticket, snapshot.digest):
                raise WorkflowError('request_already_bound')
        return key


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['demo'])
    parser.parse_args()
    from synthetic_workflow import demo
    print(json.dumps(demo(), sort_keys=True))
