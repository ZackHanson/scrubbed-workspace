"""Local result bindings and proposals only; never an email/provider executor.

Integration contract (all calls are LOCAL):
* Intake calls bind_candidate with its private holds.valid_source reference, the
  SHA256 of original bytes, and CandidateStore's exact saved-byte digest. Do not
  add this mapping to candidate JSON or a Claude request. Source identity is never
  accepted from model output. Gmail UID references additionally need the raw-byte
  digest, because UID identity alone does not bind the retrieved content.
* After validating/capturing a Claude response, the adapter calls capture_result.
  result_version is SHA256 of canonical JSON via result_digest below. result_id
  and candidate version come from the local request ledger, not echoed model text.
  This module does not establish release eligibility or call Claude.
* A local consumer calls propose with those exact versions and a stable request_id.
  Retries return the same durable bundle. Replacement results/candidates require
  compare-and-swap against the previous version; old proposals remain readable,
  but cannot be reused as current. Rejection/withdrawal calls invalidate_candidate.

Result v1: {"schema_version": 1, "actions": [{"kind": "summarize" |
"suggest_organization" | "draft_reply", "text": "..."}]}. Text is inert untrusted
content. A draft_reply is only a body draft, with no recipients or routing fields.
Unknown fields/kinds fail closed. Medical care actions and every provider write
are unsupported. Clinical prose must still pass upstream exception policy; this
structural validator does not classify medical content or certify privacy.

Create ActionStore only in approved private local state, never in a source tree.
The SQLite file contains private routing references and potentially sensitive
results/drafts. No default path, logging, export or automatic startup is supplied.
"""
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from types import MappingProxyType
from result_v1 import canonical_result, KINDS, MAX_RESULT_BYTES

from holds import valid_source
from state_access import state_context, state_mutation


CAPABILITIES = MappingProxyType({
    'local_proposal': True,
    'send_email': False,
    'write_labels': False,
    'archive_email': False,
    'third_party_message': False,
    'medical_care': False,
})


class ActionError(Exception):
    """Fixed category only; never include source, result or provider error text."""


def _fail(code):
    raise ActionError(code)


def _existing_parent(path):
    parent = Path(path).parent
    if not parent.is_dir():
        _fail('store_unavailable')
    return parent


def _id(value):
    if type(value) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', value):
        _fail('invalid_id')
    return value


def _version(value):
    if type(value) is not str or not re.fullmatch(r'[0-9a-f]{64}', value):
        _fail('invalid_version')
    return value


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def _result(result):
    try:
        return canonical_result(result)
    except ValueError as error:
        _fail(str(error))


def result_digest(result):
    """Digest the exact accepted structured result; action order is significant."""
    return hashlib.sha256(_result(result).encode('utf-8')).hexdigest()


class ActionStore:
    @state_mutation(lambda self, path: _existing_parent(path))
    def __init__(self, path):
        self.path = Path(path)
        if self.path.is_symlink():
            _fail('store_unavailable')
        # Parent must already exist: no automatic runtime installation.
        with self._transaction() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS candidates (
                    id TEXT PRIMARY KEY, version TEXT NOT NULL,
                    source TEXT NOT NULL, source_version TEXT NOT NULL,
                    active INTEGER NOT NULL, result_id TEXT);
                CREATE TABLE IF NOT EXISTS sources (
                    reference TEXT PRIMARY KEY, version TEXT NOT NULL,
                    candidate_id TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS results (
                    id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL,
                    candidate_version TEXT NOT NULL, version TEXT NOT NULL,
                    payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS proposals (
                    request_id TEXT PRIMARY KEY, binding TEXT NOT NULL UNIQUE,
                    payload TEXT NOT NULL);
            ''')

    @state_context(lambda self: _existing_parent(self.path))
    @contextmanager
    def _transaction(self):
        db = None
        try:
            if self.path.is_symlink():
                _fail('store_unavailable')
            db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
            db.row_factory = sqlite3.Row
            db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except (sqlite3.Error, OSError):
            if db is not None:
                db.rollback()
            raise ActionError('store_unavailable') from None
        except BaseException:
            if db is not None:
                db.rollback()
            raise
        finally:
            if db is not None:
                db.close()

    def bind_candidate(self, *, candidate_id, candidate_version, source_ref,
                       source_version, expected_version=None):
        """Intake-only binding; use a stable candidate ID for each source reference.

        Changed candidate bytes require the prior candidate version. Changed
        originals must be re-imported with a new immutable source reference;
        neither a source nor an ID may be silently substituted here.
        """
        _id(candidate_id)
        _version(candidate_version)
        _version(source_version)
        if (source_ref is None or not valid_source(source_ref)
                or (source_ref['kind'] == 'file' and source_ref['sha256'] != source_version)):
            _fail('invalid_source')
        source = _json(source_ref)
        with self._transaction() as db:
            known_source = db.execute('SELECT * FROM sources WHERE reference=?', (source,)).fetchone()
            if known_source and known_source['version'] != source_version:
                _fail('source_mismatch')
            old = db.execute('SELECT * FROM candidates WHERE id=?', (candidate_id,)).fetchone()
            if old:
                if old['source'] != source or old['source_version'] != source_version:
                    _fail('source_mismatch')
                if old['version'] == candidate_version:
                    if not old['active']:
                        _fail('candidate_inactive')
                    if known_source['candidate_id'] != candidate_id:
                        _fail('stale_candidate')
                    return
                if expected_version != old['version']:
                    _fail('stale_candidate')
                db.execute('UPDATE candidates SET version=?, active=1, result_id=NULL WHERE id=?',
                           (candidate_version, candidate_id))
            else:
                if expected_version is not None:
                    _fail('missing_context')
                db.execute('INSERT INTO candidates VALUES (?,?,?,?,1,NULL)',
                           (candidate_id, candidate_version, source, source_version))
            if known_source and known_source['candidate_id'] != candidate_id:
                # New candidate IDs cannot silently supersede an existing intake.
                _fail('source_already_bound')
            db.execute('INSERT OR IGNORE INTO sources VALUES (?,?,?)',
                       (source, source_version, candidate_id))

    def candidate_version(self, candidate_id):
        """Local compare-and-swap context; no source reference or content."""
        _id(candidate_id)
        with self._transaction() as db:
            row = db.execute('SELECT version FROM candidates WHERE id=?', (candidate_id,)).fetchone()
            return row[0] if row else None

    def recheck_candidate(self, *, candidate_id, candidate_version):
        """Trusted local checker only: revive exact checked bytes, discard current result.

        The caller must hold the candidate writer lock, invalidate old requests,
        and persist fresh matching model evidence. A review marker cannot call this.
        """
        _id(candidate_id)
        _version(candidate_version)
        with self._transaction() as db:
            row = db.execute('SELECT version FROM candidates WHERE id=?', (candidate_id,)).fetchone()
            if row and row['version'] != candidate_version:
                _fail('stale_candidate')
            if row:
                db.execute('UPDATE candidates SET active=1,result_id=NULL WHERE id=?', (candidate_id,))

    @staticmethod
    def _current(db, candidate_id, candidate_version):
        row = db.execute('SELECT * FROM candidates WHERE id=?', (candidate_id,)).fetchone()
        if row is None:
            _fail('missing_context')
        if row['version'] != candidate_version:
            _fail('stale_candidate')
        if not row['active']:
            _fail('candidate_inactive')
        return row

    def invalidate_candidate(self, *, candidate_id, candidate_version):
        """Local rejection/withdrawal; retain every binding, result and proposal."""
        _id(candidate_id)
        _version(candidate_version)
        with self._transaction() as db:
            row = db.execute('SELECT * FROM candidates WHERE id=?', (candidate_id,)).fetchone()
            if row is None:
                _fail('missing_context')
            if row['version'] != candidate_version:
                _fail('stale_candidate')
            db.execute('UPDATE candidates SET active=0 WHERE id=?', (candidate_id,))

    def capture_result(self, *, candidate_id, candidate_version, result_id,
                       result_version, result, expected_result_id=None):
        """Local adapter ledger supplies IDs; result content supplies neither ID."""
        _id(candidate_id)
        _version(candidate_version)
        _id(result_id)
        _version(result_version)
        payload = _result(result)
        if hashlib.sha256(payload.encode('utf-8')).hexdigest() != result_version:
            _fail('result_mismatch')
        with self._transaction() as db:
            candidate = self._current(db, candidate_id, candidate_version)
            old = db.execute('SELECT * FROM results WHERE id=?', (result_id,)).fetchone()
            if old:
                if (old['candidate_id'], old['candidate_version'], old['version'], old['payload']) != (
                        candidate_id, candidate_version, result_version, payload):
                    _fail('conflicting_replay')
                if candidate['result_id'] != result_id:
                    _fail('stale_result')
                return
            if candidate['result_id'] != expected_result_id:
                _fail('stale_result')
            db.execute('INSERT INTO results VALUES (?,?,?,?,?)',
                       (result_id, candidate_id, candidate_version, result_version, payload))
            db.execute('UPDATE candidates SET result_id=? WHERE id=?', (result_id, candidate_id))

    def propose(self, *, request_id, candidate_id, candidate_version, result_id,
                result_version, capability='local_proposal'):
        """Persist inert proposals. No capability in this module executes effects."""
        if capability != 'local_proposal':
            _fail('capability_disabled')
        for identifier in (request_id, candidate_id, result_id):
            _id(identifier)
        _version(candidate_version)
        _version(result_version)
        binding = _json({'candidate_id': candidate_id, 'candidate_version': candidate_version,
                         'result_id': result_id, 'result_version': result_version})
        with self._transaction() as db:
            candidate = self._current(db, candidate_id, candidate_version)
            if candidate['result_id'] != result_id:
                _fail('stale_result')
            result = db.execute('SELECT * FROM results WHERE id=?', (result_id,)).fetchone()
            if result is None:
                _fail('missing_context')
            if (result['candidate_id'], result['candidate_version'], result['version']) != (
                    candidate_id, candidate_version, result_version):
                _fail('result_mismatch')
            try:
                stored_result = json.loads(result['payload'])
            except (ValueError, TypeError):
                _fail('invalid_result')
            if result_digest(stored_result) != result_version:
                _fail('result_mismatch')
            old = db.execute('SELECT * FROM proposals WHERE request_id=?', (request_id,)).fetchone()
            if old:
                if old['binding'] != binding:
                    _fail('conflicting_replay')
                return json.loads(old['payload'])
            if db.execute('SELECT 1 FROM proposals WHERE binding=?', (binding,)).fetchone():
                _fail('result_already_proposed')
            # Private source context stays in this LOCAL receipt, never model JSON.
            receipt = {'schema_version': 1, 'request_id': request_id,
                       **json.loads(binding), 'source_ref': json.loads(candidate['source']),
                       'source_version': candidate['source_version'], 'proposals': [
                           {**action, 'status': ('local_only' if action['kind'] == 'summarize'
                                                else 'pending_review')}
                           for action in stored_result['actions']]}
            db.execute('INSERT INTO proposals VALUES (?,?,?)', (request_id, binding, _json(receipt)))
            return receipt

    def read_proposal(self, request_id):
        """Local review/history only; does not authorize stale proposals for use."""
        _id(request_id)
        with self._transaction() as db:
            row = db.execute('SELECT payload FROM proposals WHERE request_id=?', (request_id,)).fetchone()
            if row is None:
                _fail('missing_context')
            return json.loads(row['payload'])
