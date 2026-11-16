"""Experimental local shadow routing. No decision authorizes delivery.

Integration contract: the local model pipeline supplies CheckEvidence only after
its checks finish, including the installed model's SHA-256 digest. Evidence is
local provenance, not a signature or proof of de-identification. Legacy candidates
without evidence HOLD. Do not construct evidence from review workflow markers.
Only subject/body can be proposed; private source references belong elsewhere.
"""
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re

from scrubber import (AUDIT_SYSTEM, CHECK_SCHEMA, MAX_CHARS, MODEL, PATTERNS,
                      SCHEMA, STATE, SYSTEM)


POLICY_VERSION = 'experimental-shadow-v1'


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True,
                      separators=(',', ':')).encode('utf-8')


def _hash(value):
    return hashlib.sha256(_json(value)).hexdigest()


VALIDATOR_VERSION = _hash({'redactor': SYSTEM, 'auditor': AUDIT_SYSTEM,
                           'patterns': PATTERNS, 'max_chars': MAX_CHARS,
                           'redactor_schema': SCHEMA, 'audit_schema': CHECK_SCHEMA})
RESULTS = frozenset({'pass', 'uncertain', 'identifier', 'model_error',
                     'invalid_output', 'incomplete_output'})
STATUSES = frozenset({'needs_local_review', 'reviewed_locally', 'rejected_locally'})
HEADER = re.compile(r'(?im)^\s*(?:from|to|cc|bcc|reply-to|return-path|received|'
                    r'message-id|in-reply-to|references|source|source_reference|'
                    r'uid|uidvalidity|account_hash|x-[\w-]+)\s*:')
SOURCE_REFERENCE = re.compile(r'(?i)(?:\bfile://|\b[a-z]:[\\/]|\\\\[^\s\\]+\\|'
                              r'(?:^|\s)/(?:home|users|tmp|var)/|\b[^\s/\\]+\.eml\b)')
HEX = re.compile(r'[0-9a-f]{64}')


class RoutingError(Exception):
    """Fixed errors only; never include input or exception text."""


def content_digest(candidate):
    """Hash exact subject/body values, without Unicode/whitespace normalization."""
    if (type(candidate) is not dict
            or set(candidate) != {'subject', 'body', 'status'}
            or any(type(candidate[k]) is not str for k in candidate)
            or candidate['status'] not in STATUSES):
        raise RoutingError('invalid_candidate')
    try:
        (candidate['subject'] + candidate['body']).encode('utf-8')
    except UnicodeError:
        raise RoutingError('invalid_candidate') from None
    return _hash({k: candidate[k] for k in ('subject', 'body')})


@dataclass(frozen=True)
class CheckEvidence:
    content_digest: str
    validator_version: str
    model: str
    model_digest: str
    redactor: str
    auditor: str


@dataclass(frozen=True)
class Decision:
    outcome: str
    reasons: tuple[str, ...]
    content_digest: str | None
    policy_version: str
    validator_version: str
    evidence: CheckEvidence | None
    mode: str = 'shadow'
    release_enabled: bool = False


def _valid_evidence(evidence):
    return (type(evidence) is CheckEvidence
            and all(type(v) is str for v in asdict(evidence).values())
            and HEX.fullmatch(evidence.content_digest) is not None
            and HEX.fullmatch(evidence.validator_version) is not None
            and HEX.fullmatch(evidence.model_digest) is not None
            and evidence.model == MODEL
            and evidence.redactor in RESULTS and evidence.auditor in RESULTS)


def evaluate(candidate, evidence=None):
    """Pure deterministic policy; no IO, inference, clock or transport calls.

    WOULD_SEND means only that this experimental shadow policy would select the
    candidate. It never constitutes authorization to send it anywhere.
    """
    reasons = []
    try:
        digest = content_digest(candidate)
    except RoutingError:
        digest = None
        reasons.append('invalid_candidate')
    if digest is not None:
        subject, body = candidate['subject'], candidate['body']
        if candidate['status'] == 'rejected_locally':
            reasons.append('rejected_locally')
        if not body.strip():
            reasons.append('empty_output')
        if len((subject + body).encode('utf-8')) > MAX_CHARS:
            reasons.append('context_limit')
        if ('\r' in subject or '\n' in subject
                or any(HEADER.search(v) or SOURCE_REFERENCE.search(v)
                       for v in (subject, body))):
            reasons.append('routing_content')
        if any(re.search(p, v) for p in PATTERNS for v in (subject, body)):
            reasons.append('identifier_remaining')
    valid = _valid_evidence(evidence)
    if evidence is None:
        reasons.append('missing_evidence')
    elif not valid:
        reasons.append('invalid_evidence')
    else:
        if evidence.content_digest != digest:
            reasons.append('stale_evidence')
        if evidence.validator_version != VALIDATOR_VERSION:
            reasons.append('validator_changed')
        if evidence.redactor != 'pass':
            reasons.append('redactor_' + evidence.redactor)
        if evidence.auditor != 'pass':
            reasons.append('auditor_' + evidence.auditor)
    return Decision('HOLD' if reasons else 'WOULD_SEND',
                    tuple(reasons) or ('shadow_checks_passed',), digest,
                    POLICY_VERSION, VALIDATOR_VERSION, evidence if valid else None)


def proposed_payload(candidate, evidence, decision):
    """Return a fresh allowlisted preview, never an envelope or release token."""
    current = evaluate(candidate, evidence)
    if type(decision) is not Decision or decision != current:
        raise RoutingError('stale_decision')
    if current.outcome != 'WOULD_SEND':
        raise RoutingError('candidate_held')
    return {k: candidate[k] for k in ('subject', 'body')}


def execute(candidate, evidence, decision, transport=None):
    """Adapter boundary deliberately disabled, including injected test transport."""
    raise RoutingError('release_disabled')


class DecisionStore:
    """Append-only content-addressed decision records in private local state.

    Callers must use the approved private state root (or temporary test storage).
    Records omit subject/body, source references, headers and model output text.
    Neither files nor evidence defend against a malicious local state writer.
    Persisted decisions must always be re-evaluated against current evidence and
    candidate before a preview; no downstream adapter may treat them as approval.
    """
    def __init__(self, folder=None):
        self.folder = Path(folder) if folder is not None else STATE / 'routing'

    def record(self, ticket, candidate, evidence=None):
        if type(ticket) is not str or not re.fullmatch(r'[0-9a-f]{32}', ticket):
            raise RoutingError('invalid_ticket')
        decision = evaluate(candidate, evidence)
        record = asdict(decision)
        data = _json(record)
        name = ticket + '-' + hashlib.sha256(data).hexdigest() + '.json'
        try:
            if self.folder.is_symlink():
                raise RoutingError('invalid_store')
            self.folder.mkdir(parents=True, exist_ok=True)
            path = self.folder / name
            # Exclusive creation never follows/replaces an existing record link.
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
            except BaseException:
                path.unlink(missing_ok=True)
                raise
        except FileExistsError:
            # Idempotence only when existing bytes are exactly the same.
            try:
                matches = not path.is_symlink() and path.read_bytes() == data
            except OSError:
                raise RoutingError('store_failed') from None
            if not matches:
                raise RoutingError('record_conflict') from None
        except OSError:
            raise RoutingError('store_failed') from None
        return decision
