"""Private local intake ledger. Never put this database in Git or cloud storage.

IntakeLedger(folder) uses folder/intake/ledger.sqlite3. Source dictionaries are
local-only; successful_records/context expose opaque tickets and scrubbed records.
ingest -> claim -> complete/block is the worker protocol. Claims expire, and a
reclaimed job fences out its previous worker. Completion commits the scrubbed
result before materialize writes the compatible candidate JSON. Re-running
materialize repairs interrupted writes without repeating inference.

No method reads mail, calls a model, sends content, or grants release approval.
"""
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time
import uuid

from holds import HoldError, REASONS, valid_source, validity


class IntakeError(HoldError):
    pass


@dataclass(frozen=True)
class Claim:
    ticket: str
    token: str


def fetch_gmail(client, source, *, max_bytes=512_000):
    """Bounded PEEK on an already authenticated, readonly-selected INBOX.

    The caller owns sign-in and readonly selection. Explicit UID fields are
    checked; IMAP response sequence numbers are deliberately ignored.
    """
    source = identity(source)
    if source['kind'] != 'gmail' or source['mailbox'] != 'INBOX':
        raise IntakeError('source_unavailable')
    if validity(client) != source['uidvalidity']:
        raise IntakeError('source_changed')
    uid = source['uid']
    try:
        status, sizes = client.uid('fetch', uid, '(UID RFC822.SIZE)')
        lines = [x for x in sizes if isinstance(x, bytes) and b'RFC822.SIZE' in x]
        if status != 'OK' or len(lines) != 1:
            raise IntakeError('source_unavailable')
        check_uid = re.search(rb'\bUID (\d+)\b', lines[0])
        size = re.search(rb'\bRFC822.SIZE (\d+)\b', lines[0])
        if not check_uid or check_uid[1].decode('ascii') != uid or not size:
            raise IntakeError('source_changed')
        if int(size[1]) > max_bytes:
            raise IntakeError('oversized')
        status, fetched = client.uid('fetch', uid, '(UID BODY.PEEK[])')
        bodies = [x for x in fetched if isinstance(x, tuple) and len(x) == 2
                  and isinstance(x[0], bytes) and isinstance(x[1], bytes)]
        if status != 'OK' or len(bodies) != 1:
            raise IntakeError('source_unavailable')
        check_uid = re.search(rb'\bUID (\d+)\b', bodies[0][0])
        if not check_uid or check_uid[1].decode('ascii') != uid or validity(client) != source['uidvalidity']:
            raise IntakeError('source_changed')
        raw = bodies[0][1]
        if len(raw) > max_bytes:
            raise IntakeError('oversized')
        if len(raw) != int(size[1]):
            raise IntakeError('source_changed')
        return raw
    except HoldError:
        raise
    except Exception:
        raise IntakeError('source_unavailable') from None


def identity(source):
    """Canonical private identity; mailbox defaults to legacy INBOX references."""
    if not isinstance(source, dict):
        raise IntakeError('source_unavailable')
    source = dict(source)
    if source.get('kind') == 'file' and 'mailbox' in source:
        raise IntakeError('source_unavailable')
    mailbox = source.pop('mailbox', 'INBOX')
    if not valid_source(source) or source is None:
        raise IntakeError('source_unavailable')
    if source['kind'] == 'gmail':
        if not isinstance(mailbox, str) or not mailbox or len(mailbox) > 1024:
            raise IntakeError('source_unavailable')
        for key in ('uid', 'uidvalidity'):
            value = source[key]
            if len(value) > 10 or not 0 < int(value) <= 4294967295:
                raise IntakeError('source_unavailable')
            source[key] = str(int(value))
        source['mailbox'] = 'INBOX' if mailbox.upper() == 'INBOX' else mailbox
    else:
        source['path'] = os.path.normcase(source['path'])
    return source


class IntakeLedger:
    def __init__(self, folder, *, clock=time.time):
        self.root = Path(folder)
        self.folder = self.root / 'intake'
        self.clock = clock
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path = self.folder / 'ledger.sqlite3'
        if self.folder.is_symlink() or self.path.is_symlink():
            raise IntakeError('source_unavailable')
        with self._db() as db:
            if db.execute('PRAGMA user_version').fetchone()[0] not in (0, 1):
                raise IntakeError('source_unavailable')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS mailbox (
                    scope TEXT PRIMARY KEY, epoch TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS item (
                    ticket TEXT PRIMARY KEY, identity TEXT UNIQUE NOT NULL,
                    locator TEXT NOT NULL, fingerprint TEXT,
                    state TEXT NOT NULL DEFAULT 'pending', token TEXT,
                    expires REAL, attempts INTEGER NOT NULL DEFAULT 0,
                    result TEXT, reason TEXT, thread TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS thread_link (
                    scope TEXT NOT NULL, reference TEXT NOT NULL, thread TEXT NOT NULL,
                    PRIMARY KEY(scope, reference));
                CREATE TABLE IF NOT EXISTS retry_generation (
                    ticket TEXT PRIMARY KEY, generation INTEGER NOT NULL);
                PRAGMA user_version=1;
            ''')

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA synchronous=FULL')
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def ingest(self, source, *, fingerprint=None):
        """Register once. Changed file bytes/mailbox epochs fail closed.

        fingerprint is an optional SHA256 of in-memory bytes, never the bytes.
        Gmail callers must register the mailbox epoch before fetching content.
        """
        source = identity(source)
        if source['kind'] == 'file':
            if fingerprint is not None and fingerprint != source['sha256']:
                raise IntakeError('source_changed')
            fingerprint = source['sha256']
        if fingerprint is not None and (type(fingerprint) is not str or not re.fullmatch('[0-9a-f]{64}', fingerprint)):
            raise IntakeError('processing_failed')
        encoded = json.dumps(source, sort_keys=True)
        locator = (source['path'] if source['kind'] == 'file' else
                   json.dumps([source['account_hash'], source['mailbox'], source['uid']]))
        with self._db() as db:
            if source['kind'] == 'gmail':
                scope = json.dumps([source['account_hash'], source['mailbox']])
                epoch = db.execute('SELECT epoch FROM mailbox WHERE scope=?', (scope,)).fetchone()
                if epoch and epoch[0] != source['uidvalidity']:
                    raise IntakeError('source_changed')
                db.execute('INSERT OR IGNORE INTO mailbox VALUES (?,?)', (scope, source['uidvalidity']))
            old = db.execute('SELECT * FROM item WHERE locator=?', (locator,)).fetchone()
            if old:
                if old['identity'] != encoded or (fingerprint and old['fingerprint'] and fingerprint != old['fingerprint']):
                    raise IntakeError('source_changed')
                if fingerprint and not old['fingerprint']:
                    db.execute('UPDATE item SET fingerprint=? WHERE ticket=?', (fingerprint, old['ticket']))
                return old['ticket']
            ticket = uuid.uuid4().hex
            db.execute('INSERT INTO item(ticket,identity,locator,fingerprint,thread) VALUES (?,?,?,?,?)',
                       (ticket, encoded, locator, fingerprint, uuid.uuid4().hex))
            return ticket

    def claim(self, ticket, *, lease_seconds=600):
        if not math.isfinite(lease_seconds) or lease_seconds <= 0:
            raise ValueError('lease_seconds must be finite and positive')
        now = self.clock()
        token = uuid.uuid4().hex
        with self._db() as db:
            updated = db.execute('''UPDATE item SET state='processing',token=?,expires=?,attempts=attempts+1
                WHERE ticket=? AND (state='pending' OR (state='processing' AND expires<=?))''',
                (token, now + lease_seconds, ticket, now)).rowcount
            return Claim(ticket, token) if updated else None

    def _owned(self, db, claim):
        row = db.execute('SELECT * FROM item WHERE ticket=?', (claim.ticket,)).fetchone()
        if row is None or row['token'] != claim.token:
            raise IntakeError('source_changed')
        return row

    def complete(self, claim, record):
        """Commit only already-scrubbed pending records; same completion is safe."""
        if (not isinstance(record, dict) or set(record) != {'status', 'subject', 'body'}
                or record['status'] != 'needs_local_review'
                or type(record['subject']) is not str or type(record['body']) is not str
                or not record['body'].strip()):
            raise IntakeError('processing_failed')
        result = json.dumps(record, sort_keys=True)
        with self._db() as db:
            row = self._owned(db, claim)
            if row['fingerprint'] is None:
                raise IntakeError('source_unavailable')
            if row['state'] == 'completed' and row['result'] == result:
                return claim.ticket
            if row['state'] != 'processing' or row['expires'] <= self.clock():
                raise IntakeError('source_changed')
            db.execute("UPDATE item SET state='completed',result=?,reason=NULL WHERE ticket=?",
                       (result, claim.ticket))
        return claim.ticket

    def block(self, claim, reason):
        if reason not in REASONS:
            raise IntakeError('processing_failed')
        with self._db() as db:
            row = self._owned(db, claim)
            if row['state'] == 'blocked' and row['reason'] == reason:
                return
            if row['state'] != 'processing' or row['expires'] <= self.clock():
                raise IntakeError('source_changed')
            db.execute("UPDATE item SET state='blocked',reason=? WHERE ticket=?", (reason, claim.ticket))

    def retry(self, ticket):
        """Explicit retry only; blocked items are never automatically requeued."""
        with self._db() as db:
            changed = db.execute("UPDATE item SET state='pending',token=NULL WHERE ticket=? AND state='blocked'",
                                 (ticket,)).rowcount
            if changed:
                db.execute('INSERT INTO retry_generation VALUES (?,1) ON CONFLICT(ticket) '
                           'DO UPDATE SET generation=generation+1', (ticket,))
            return bool(changed)

    def successful_records(self):
        """Local routing input, not authorization to export or release content."""
        with self._db() as db:
            return [{'ticket': row['ticket'], 'record': json.loads(row['result'])}
                    for row in db.execute("SELECT ticket,result FROM item WHERE state='completed' ORDER BY rowid")]

    def status(self, ticket):
        with self._db() as db:
            row = db.execute('SELECT state,attempts,reason, COALESCE((SELECT generation '
                             'FROM retry_generation WHERE retry_generation.ticket=item.ticket),0) '
                             'AS retry_generation FROM item WHERE ticket=?', (ticket,)).fetchone()
            return dict(row) if row else None

    def original_candidate_digest(self, ticket):
        """Exact materialized byte version, for local edit/restart detection."""
        with self._db() as db:
            row = db.execute("SELECT result FROM item WHERE ticket=? AND state='completed'",
                             (ticket,)).fetchone()
            return hashlib.sha256(row[0].encode('utf-8')).hexdigest() if row else None

    def work_tickets(self):
        """Opaque pending/expired jobs for local operations; no blocked retries."""
        with self._db() as db:
            return [r[0] for r in db.execute('''SELECT ticket FROM item
                WHERE state='pending' OR (state='processing' AND expires<=?) ORDER BY rowid''', (self.clock(),))]

    def private_source(self, ticket):
        """LOCAL ONLY: identity + raw-byte SHA256 for retrieval/action binding.

        Never pass this response to routing, Claude, telemetry or cloud prompts.
        Unfetched Gmail has source_version=None. Legacy holds/actions accept
        INBOX references; other mailbox references need a mailbox-aware adapter.
        """
        with self._db() as db:
            row = db.execute('SELECT identity,fingerprint FROM item WHERE ticket=?', (ticket,)).fetchone()
            if row is None:
                raise IntakeError('source_unavailable')
            source = json.loads(row['identity'])
            if source.get('mailbox') == 'INBOX':
                source.pop('mailbox')
            return {'source': source, 'source_version': row['fingerprint']}

    def materialize(self, ticket):
        """Repair missing candidate after commit; never overwrite reviewer edits."""
        with self._db() as db:
            row = db.execute("SELECT result FROM item WHERE ticket=? AND state='completed'", (ticket,)).fetchone()
            if row is None:
                raise IntakeError('source_unavailable')
        target = self.root / (ticket + '.json')
        if target.is_symlink():
            raise IntakeError('source_changed')
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.folder, delete=False) as output:
                temporary = Path(output.name)
                output.write(row['result'])
                output.flush()
                os.fsync(output.fileno())
            try:
                os.link(temporary, target)
            except FileExistsError:
                pass
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)
        return ticket

    def link_thread(self, ticket, message_id, references=()):
        """Local-only exact Message-ID linking; no subject/person heuristics.

        Call only with bounded headers from the in-memory original. Header values
        are hashed with account/mailbox scope and never returned. Ambiguous merges
        fail closed; absence of a link simply yields one message of context.
        """
        values = [*references, message_id]
        if len(values) > 101 or any(type(v) is not str or not v or len(v) > 998 for v in values):
            raise IntakeError('processing_failed')
        with self._db() as db:
            row = db.execute('SELECT identity,thread FROM item WHERE ticket=?', (ticket,)).fetchone()
            if row is None:
                raise IntakeError('source_unavailable')
            source = json.loads(row['identity'])
            if source['kind'] != 'gmail':
                raise IntakeError('source_unavailable')
            scope = json.dumps([source['account_hash'], source['mailbox'], source['uidvalidity']])
            refs = [hashlib.sha256((scope + '\0' + v).encode()).hexdigest() for v in values]
            threads = {r[0] for ref in refs for r in db.execute(
                'SELECT thread FROM thread_link WHERE scope=? AND reference=?', (scope, ref))}
            own_count = db.execute('SELECT count(*) FROM item WHERE thread=?', (row['thread'],)).fetchone()[0]
            if len(threads) > 1 and own_count == 1:
                threads.discard(row['thread'])
            if len(threads) > 1:
                raise IntakeError('source_changed')
            thread = next(iter(threads), row['thread'])
            # Never split a thread already carrying other messages.
            if thread != row['thread'] and own_count > 1:
                raise IntakeError('source_changed')
            db.execute('UPDATE item SET thread=? WHERE ticket=?', (thread, ticket))
            db.execute('UPDATE thread_link SET thread=? WHERE scope=? AND thread=?',
                       (thread, scope, row['thread']))
            for ref in refs:
                db.execute('INSERT OR IGNORE INTO thread_link VALUES (?,?,?)', (scope, ref, thread))

    def context(self, ticket, *, limit=10):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('limit must be 1..100')
        with self._db() as db:
            rows = db.execute('''SELECT ticket,result FROM item WHERE state='completed'
                AND thread=(SELECT thread FROM item WHERE ticket=?) ORDER BY rowid DESC LIMIT ?''', (ticket, limit)).fetchall()
            return [{'ticket': r['ticket'], 'record': json.loads(r['result'])} for r in reversed(rows)]
