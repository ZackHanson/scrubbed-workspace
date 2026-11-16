"""Local desktop coordination. No release, transport, raw-draft persistence or logs."""
from contextlib import closing
from dataclasses import asdict
import hashlib
import imaplib
import json
from pathlib import Path
import sqlite3
import ssl
import uuid

from actions import ActionError, ActionStore
from holds import HoldError, HoldStore, account_hash, read_source
from intake import fetch_gmail
from operations import instance_lock
from review import ReviewError
import routing
from shadow_workflow import ShadowWorkflow, WorkflowError
from state_access import state_read, state_mutation


@state_read(lambda folder, ticket: folder)
def managed(folder, ticket):
    """Do not create a workflow or adopt legacy files just by opening the UI."""
    root = Path(folder)
    if not (root / 'workflow.sqlite3').is_file():
        return False
    try:
        with closing(sqlite3.connect((root / 'intake' / 'ledger.sqlite3').resolve().as_uri()
                                    + '?mode=ro', uri=True)) as db:
            return db.execute('SELECT 1 FROM item WHERE ticket=?', (ticket,)).fetchone() is not None
    except sqlite3.Error:
        raise HoldError('reconciliation_required') from None


def read_original(source, credentials):
    if source['kind'] == 'file':
        return read_source(source)
    address, password = credentials
    if not address or not password or account_hash(address) != source['account_hash']:
        raise HoldError('source_unavailable')
    try:
        with imaplib.IMAP4_SSL('imap.gmail.com', 993, ssl_context=ssl.create_default_context(),
                              timeout=30) as client:
            client.login(address, password.replace(' ', ''))
            if client.select('INBOX', readonly=True)[0] != 'OK':
                raise HoldError('source_unavailable')
            return fetch_gmail(client, source)
    except HoldError:
        raise
    except Exception:
        raise HoldError('source_unavailable') from None


@state_mutation(lambda folder, *args, **kwargs: folder)
def invalidate_before_save(folder, snapshot, *, content_changed, rejected=False):
    """Called under the candidate writer lock, BEFORE replacing its bytes.

    Partial failures remain conservative: old evidence/results may be withdrawn
    even if the subsequent file save fails. No unchecked edit creates evidence.
    """
    root = Path(folder)
    try:
        if not managed(folder, snapshot.ticket):
            return
        with closing(sqlite3.connect(root / 'workflow.sqlite3')) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS revoked_requests (key TEXT PRIMARY KEY)')
            db.execute('INSERT OR IGNORE INTO revoked_requests SELECT key FROM requests WHERE ticket=?',
                       (snapshot.ticket,))
            if content_changed:
                db.execute('DELETE FROM checks WHERE ticket=?', (snapshot.ticket,))
        actions = ActionStore(root / 'actions.sqlite3')
        version = actions.candidate_version(snapshot.ticket)
        if version:
            actions.invalidate_candidate(candidate_id=snapshot.ticket, candidate_version=version)
        if content_changed and not rejected:
            workflow = ShadowWorkflow(root)
            holds = HoldStore(root)
            hold = holds.create(snapshot.ticket, 'needs_recheck',
                                workflow.intake.private_source(snapshot.ticket)['source'])
            if hold.record['status'] == 'resolved':
                holds.update(hold, status='open', reason='needs_recheck')
    except (ActionError, OSError, sqlite3.Error, HoldError):
        raise ReviewError('Could not withdraw previous work. Reload before saving.') from None


@state_mutation(lambda folder, *args, **kwargs: folder)
def close_rejected_hold(folder, ticket):
    try:
        if managed(folder, ticket):
            holds = HoldStore(folder)
            if holds.path(ticket).exists():
                hold = holds.load(ticket)
                if hold.record['status'] == 'open':
                    holds.update(hold, status='dismissed')
    except (HoldError, sqlite3.Error):
        raise ReviewError('Candidate was rejected. Reload to check its exception status.') from None


class Reviewer:
    @state_mutation(lambda self, folder, **kwargs: folder)
    def __init__(self, folder, *, reader=read_source):
        self.workflow = ShadowWorkflow(folder, source_reader=reader)
        self.root = Path(folder)
        self.holds = HoldStore(folder)
        with closing(sqlite3.connect(self.workflow.path)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS review_revisions '
                       '(id TEXT PRIMARY KEY,ticket TEXT,hold_digest TEXT,version TEXT,mode TEXT,'
                       'input_digest TEXT,state TEXT,record TEXT,evidence TEXT,checked REAL)')

    def _hold(self, snapshot):
        current = self.holds.load(snapshot.ticket)
        if current.digest != snapshot.digest or current.record['status'] != 'open':
            raise HoldError('source_changed')
        if self.workflow.intake.private_source(snapshot.ticket)['source'] != current.record['source']:
            raise HoldError('source_changed')
        path = self.workflow.candidates.path(snapshot.ticket)
        candidate = self.workflow.candidates.load(snapshot.ticket) if path.exists() else None
        if candidate and candidate.record['status'] == 'rejected_locally':
            raise HoldError('reconciliation_required')
        return candidate

    def _safe(self, ticket, candidate):
        path = self.root / 'operations' / 'operations.sqlite3'
        keys = [ticket]
        if candidate:
            keys.append(hashlib.sha256((ticket + candidate.digest + routing.VALIDATOR_VERSION)
                                       .encode()).hexdigest()[:32])
        if path.exists():
            with closing(sqlite3.connect(path)) as db:
                for key in keys:
                    row = db.execute('SELECT state FROM jobs WHERE key=?', (key,)).fetchone()
                    if row and row[0] in ('claimed', 'uncertain', 'retry'):
                        raise HoldError('reconciliation_required')
        with closing(sqlite3.connect(self.workflow.path)) as db:
            if db.execute("SELECT 1 FROM review_revisions WHERE ticket=? AND state IN ('checking','unknown')",
                          (ticket,)).fetchone():
                raise HoldError('reconciliation_required')

    @state_mutation('root')
    def retry(self, snapshot):
        with instance_lock(self.root / 'review-actions'):
            candidate = self._hold(snapshot)
            # Runner acquires this same operations lock for processing. The first
            # check prevents even requeueing an already uncertain intake job.
            with instance_lock(self.root / 'operations'):
                self._safe(snapshot.ticket, candidate)
            state = self.workflow.intake.status(snapshot.ticket)
            if state['state'] == 'completed':
                if candidate and self.workflow.current(snapshot.ticket)[1].outcome == 'WOULD_SEND':
                    self.holds.update(snapshot, status='resolved')
                    return snapshot.ticket
                return self._revision(snapshot, None, 'retry')
            if state['state'] == 'blocked':
                self.workflow.intake.retry(snapshot.ticket)
            report = self.workflow.run([snapshot.ticket])
            if report.uncertain or report.intake_errors:
                raise HoldError('reconciliation_required')
            current = self.workflow.intake.status(snapshot.ticket)
            self._hold(snapshot)
            if current['state'] != 'completed':
                self.holds.update(snapshot, reason=current['reason'] or 'processing_failed')
                return None
            if self.workflow.current(snapshot.ticket)[1].outcome != 'WOULD_SEND':
                raise HoldError('needs_recheck')
            self.holds.update(snapshot, status='resolved')
            return snapshot.ticket

    @state_mutation('root')
    def draft(self, snapshot, raw):
        with instance_lock(self.root / 'review-actions'):
            return self._revision(snapshot, raw, 'draft')

    def _revision(self, snapshot, raw, mode):
        workflow, ticket = self.workflow, snapshot.ticket
        with instance_lock(self.root / 'operations'):
            candidate = self._hold(snapshot)
            self._safe(ticket, candidate)
            version = candidate.digest if candidate else None
            input_digest = hashlib.sha256(raw).hexdigest() if raw is not None else None
            with closing(sqlite3.connect(workflow.path)) as db, db:
                db.row_factory = sqlite3.Row
                saved = None
                for item in db.execute("SELECT * FROM review_revisions WHERE ticket=? "
                                       "AND state IN ('checked','installed') ORDER BY rowid", (ticket,)).fetchall():
                    if item['state'] == 'installed':
                        installed = hashlib.sha256(json.dumps(json.loads(item['record']), indent=2).encode()).hexdigest()
                        if (item['hold_digest'], item['mode'], item['input_digest'], installed) != (
                                snapshot.digest, mode, input_digest, version):
                            # Its candidate/evidence/actions were already committed.
                            # A later edit/hold can safely start a separate revision.
                            db.execute("UPDATE review_revisions SET state='done' WHERE id=?", (item['id'],))
                            continue
                    saved = item
                    break
                if saved:
                    if (saved['hold_digest'], saved['mode'], saved['input_digest']) != (
                            snapshot.digest, mode, input_digest):
                        raise HoldError('reconciliation_required')
                    revision = saved['id']
                    record = json.loads(saved['record'])
                    evidence = routing.CheckEvidence(**json.loads(saved['evidence']))
                    checked, version = saved['checked'], saved['version']
                else:
                    revision = uuid.uuid4().hex
                    db.execute('INSERT INTO review_revisions VALUES (?,?,?,?,?,?,?,?,?,?)',
                               (revision, ticket, snapshot.digest, version, mode, input_digest,
                                'checking', None, None, None))
            if not saved:
                try:
                    binding = workflow.intake.private_source(ticket)
                    def compute():
                        original = workflow._source(ticket, allow_unbound=True, binding=binding)
                        record, evidence = workflow.check(original if raw is None else raw)
                        return record, evidence, hashlib.sha256(original).hexdigest()
                    record, evidence, fingerprint = workflow._compute(compute)
                    if routing.evaluate(record, evidence).outcome != 'WOULD_SEND':
                        raise HoldError('processing_failed')
                    workflow.intake.ingest(workflow.intake.private_source(ticket)['source'],
                                           fingerprint=fingerprint)
                except HoldError as error:
                    with closing(sqlite3.connect(workflow.path)) as db, db:
                        db.execute("UPDATE review_revisions SET state='failed' WHERE id=?", (revision,))
                    self.holds.update(snapshot, reason=error.code)
                    return None
                except BaseException:
                    # A timeout/crash does not become a new automatic retry.
                    with closing(sqlite3.connect(workflow.path)) as db, db:
                        db.execute("UPDATE review_revisions SET state='unknown' WHERE id=?", (revision,))
                    raise HoldError('reconciliation_required') from None
                checked = workflow.clock()
                with closing(sqlite3.connect(workflow.path)) as db, db:
                    db.execute("UPDATE review_revisions SET state='checked',record=?,evidence=?,checked=? WHERE id=?",
                               (json.dumps(record), json.dumps(asdict(evidence)), checked, revision))
            # Freeze the original check time during recovery. Reopening cannot
            # freshen old evidence or bypass changed source/model identity.
            binding = workflow.intake.private_source(ticket)
            workflow._compute(lambda: workflow._source(ticket, binding=binding))
            if (routing.evaluate(record, evidence).outcome != 'WOULD_SEND'
                    or not 0 <= workflow.clock() - checked <= workflow.max_age
                    or workflow._compute(workflow.model_digest) != evidence.model_digest):
                with closing(sqlite3.connect(workflow.path)) as db, db:
                    db.execute("UPDATE review_revisions SET state='failed' WHERE id=?", (revision,))
                self.holds.update(snapshot, reason='needs_recheck')
                return None
            encoded = json.dumps(record, indent=2).encode('utf-8')
            digest = hashlib.sha256(encoded).hexdigest()
            with workflow._candidate_lock(ticket):
                try:
                    current = self._hold(snapshot)
                except HoldError:
                    with closing(sqlite3.connect(workflow.path)) as db, db:
                        db.execute("UPDATE review_revisions SET state='failed' WHERE id=?", (revision,))
                    raise
                if (current.digest if current else None) not in (version, digest):
                    with closing(sqlite3.connect(workflow.path)) as db, db:
                        db.execute("UPDATE review_revisions SET state='failed' WHERE id=?", (revision,))
                    raise HoldError('source_changed')
                if current:
                    invalidate_before_save(self.root, current, content_changed=True)
                state = workflow.intake.status(ticket)['state']
                if state == 'blocked':
                    workflow.intake.retry(ticket)
                    state = 'pending'
                if state == 'pending':
                    claim = workflow.intake.claim(ticket)
                    if claim is None:
                        raise HoldError('reconciliation_required')
                    workflow.intake.complete(claim, record)
                elif state != 'completed':
                    raise HoldError('reconciliation_required')
                # Durable checked output precedes materialization. A failed save
                # can replay this revision without another model invocation.
                import os
                import tempfile
                temporary = None
                try:
                    with tempfile.NamedTemporaryFile(dir=self.root, delete=False) as output:
                        temporary = Path(output.name)
                        output.write(encoded)
                        output.flush()
                        os.fsync(output.fileno())
                    temporary.replace(workflow.candidates.path(ticket))
                finally:
                    if temporary:
                        temporary.unlink(missing_ok=True)
                with closing(sqlite3.connect(workflow.path)) as db, db:
                    db.execute('INSERT OR REPLACE INTO checks VALUES (?,?,?)',
                               (ticket, json.dumps(asdict(evidence)), checked))
                old = workflow.actions.candidate_version(ticket)
                if old == digest:
                    workflow.actions.recheck_candidate(candidate_id=ticket, candidate_version=digest)
                source = workflow.intake.private_source(ticket)
                workflow.actions.bind_candidate(candidate_id=ticket, candidate_version=digest,
                                                source_ref=source['source'], source_version=source['source_version'],
                                                expected_version=old)
                with closing(sqlite3.connect(workflow.path)) as db, db:
                    db.execute("UPDATE review_revisions SET state='installed' WHERE id=?", (revision,))
                self.holds.update(snapshot, status='resolved')
                with closing(sqlite3.connect(workflow.path)) as db, db:
                    db.execute("UPDATE review_revisions SET state='done' WHERE id=?", (revision,))
                return ticket

    @state_mutation('root')
    def dismiss(self, snapshot):
        with instance_lock(self.root / 'review-actions'):
            candidate = self._hold(snapshot)
            if candidate:
                self.workflow.candidates.save(candidate, candidate.record['subject'], candidate.record['body'],
                                              'rejected_locally')
                return self.holds.load(snapshot.ticket)
            return self.holds.update(snapshot, status='dismissed')
