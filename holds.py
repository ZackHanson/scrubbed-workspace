"""Private local exception records and bounded, read-only source retrieval."""
from dataclasses import dataclass
from email.parser import BytesParser
import email.policy
import hashlib
import imaplib
import json
import os
from pathlib import Path
import re
import ssl
import tempfile
from state_access import state_read, state_mutation


MAX_BYTES = 512_000
REASONS = {
    'attachment': ('Attachment needs separate handling', 'View the message text locally. Handle attachments in your usual mail client.'),
    'unsupported_content': ('Unsupported message content', 'View the inert text preview or handle the original in your mail client.'),
    'oversized': ('Message is too large', 'Handle the original in your mail client, or compose a shorter generalized draft here.'),
    'malformed_message': ('Malformed email', 'Check the original in your mail client or compose a generalized draft.'),
    'context_limit': ('Text exceeds the local model budget', 'Compose a shorter generalized draft for another local check.'),
    'redactor_uncertain': ('Local redactor was uncertain', 'Inspect the original locally and compose a generalized draft, or retry.'),
    'empty_output': ('No useful redacted text returned', 'Compose a generalized draft or handle the original yourself.'),
    'identifier_remaining': ('Possible identifier remained', 'Inspect the original locally and remove identifiers from a new draft.'),
    'verifier_flagged': ('Local verifier flagged possible identifiers', 'Inspect the original locally; compose a draft without identifying details.'),
    'model_error': ('Local model could not finish', 'Check Ollama, then retry the original.'),
    'invalid_model_output': ('Invalid local model response', 'Retry the original after checking Ollama.'),
    'incomplete_model_output': ('Local model response was incomplete', 'Retry or compose a shorter generalized draft.'),
    'source_unavailable': ('Original could not be read', 'Check the source file or Gmail account, then retry.'),
    'source_changed': ('Original reference no longer matches', 'Re-import the message. The reviewer will not substitute another original.'),
    'processing_failed': ('Processing could not complete', 'Check the original and local model, then retry.'),
    'needs_recheck': ('Edited candidate needs local checks', 'Check a generalized draft here before using this revision.'),
    'reconciliation_required': ('Previous work needs local reconciliation', 'Do not retry uncertain work. Reconcile its saved local receipt first.'),
}


class HoldError(Exception):
    def __init__(self, code):
        self.code = code if code in REASONS else 'processing_failed'
        super().__init__(REASONS[self.code][0])


def account_hash(address):
    return hashlib.sha256(address.strip().casefold().encode()).hexdigest()


def validity(client):
    try:
        _, values = client.response('UIDVALIDITY')
        value = values[0].decode('ascii')
        return value if re.fullmatch(r'[0-9]+', value) else None
    except (TypeError, IndexError, AttributeError, ValueError):
        return None


def file_source(path, raw):
    return {'kind': 'file', 'path': str(Path(path).resolve()),
            'sha256': hashlib.sha256(raw).hexdigest()}


def valid_source(source):
    if source is None:
        return True
    if not isinstance(source, dict) or not all(type(value) is str for value in source.values()):
        return False
    if source.get('kind') == 'file':
        return (set(source) == {'kind', 'path', 'sha256'}
                and Path(source['path']).is_absolute()
                and Path(source['path']).suffix.casefold() == '.eml'
                and re.fullmatch(r'[0-9a-f]{64}', source['sha256']) is not None)
    if source.get('kind') == 'gmail':
        return (set(source) == {'kind', 'account_hash', 'uidvalidity', 'uid'}
                and re.fullmatch(r'[0-9a-f]{64}', source['account_hash']) is not None
                and re.fullmatch(r'[0-9]+', source['uidvalidity']) is not None
                and re.fullmatch(r'[0-9]+', source['uid']) is not None)
    return False


@dataclass
class HoldSnapshot:
    ticket: str
    record: dict
    digest: str


class HoldStore:
    @state_read(lambda self, folder: folder)
    def __init__(self, folder):
        self.folder = Path(folder) / 'holds'

    @state_read('folder.parent')
    def path(self, ticket):
        if not re.fullmatch(r'[0-9a-f]{32}', ticket):
            raise HoldError('source_unavailable')
        path = self.folder / (ticket + '.json')
        if path.is_symlink():
            raise HoldError('source_unavailable')
        return path

    @state_read('folder.parent')
    def tickets(self):
        return sorted(path.stem for path in self.folder.glob('*.json')
                      if re.fullmatch(r'[0-9a-f]{32}', path.stem)
                      and path.is_file() and not path.is_symlink())

    @state_read('folder.parent')
    def load(self, ticket):
        try:
            with self.path(ticket).open('rb') as source:
                raw = source.read(16_001)
            if len(raw) > 16_000:
                raise HoldError('source_unavailable')
            record = json.loads(raw)
            if (not isinstance(record, dict) or set(record) != {'status', 'reason', 'source'}
                    or record['status'] not in ('open', 'resolved', 'dismissed')
                    or record['reason'] not in REASONS or not valid_source(record['source'])):
                raise HoldError('source_unavailable')
            return HoldSnapshot(ticket, record, hashlib.sha256(raw).hexdigest())
        except (OSError, ValueError, TypeError):
            raise HoldError('source_unavailable') from None

    @state_mutation('folder.parent')
    def create(self, ticket, reason, source=None):
        if reason not in REASONS or not valid_source(source):
            raise HoldError('processing_failed')
        self.folder.mkdir(parents=True, exist_ok=True)
        # Re-reading an unread source must not repeatedly interrupt the user.
        if source is not None:
            for existing in self.tickets():
                try:
                    snapshot = self.load(existing)
                except HoldError:
                    continue
                if snapshot.record['source'] == source:
                    return snapshot
        record = {'status': 'open', 'reason': reason, 'source': source}
        with self.path(ticket).open('x', encoding='utf-8') as output:
            json.dump(record, output, indent=2)
        return self.load(ticket)

    @state_mutation('folder.parent')
    def update(self, snapshot, *, status=None, reason=None):
        record = {**snapshot.record}
        if status is not None:
            record['status'] = status
        if reason is not None:
            record['reason'] = reason
        if record['status'] not in ('open', 'resolved', 'dismissed') or record['reason'] not in REASONS:
            raise HoldError('processing_failed')
        path = self.path(snapshot.ticket)
        lock_path = path.with_suffix('.review-lock')
        temporary = None
        try:
            lock = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except OSError:
            raise HoldError('processing_failed') from None
        try:
            os.close(lock)
            if self.load(snapshot.ticket).digest != snapshot.digest:
                raise HoldError('source_changed')
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.folder,
                                             suffix='.tmp', delete=False) as output:
                temporary = Path(output.name)
                json.dump(record, output, indent=2)
                output.flush()
                os.fsync(output.fileno())
            temporary.replace(path)
            return self.load(snapshot.ticket)
        except OSError:
            raise HoldError('processing_failed') from None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            lock_path.unlink(missing_ok=True)


def read_source(source, address=None, password=None):
    """Fetch into memory only; never mark mail read or open attachments/resources."""
    if source is None or not valid_source(source):
        raise HoldError('source_unavailable')
    try:
        if source['kind'] == 'file':
            path = Path(source['path'])
            if path.is_symlink():
                raise HoldError('source_unavailable')
            with path.open('rb') as original:
                raw = original.read(MAX_BYTES + 1)
            if hashlib.sha256(raw).hexdigest() != source['sha256']:
                raise HoldError('source_changed')
        else:
            if not address or not password or account_hash(address) != source['account_hash']:
                raise HoldError('source_unavailable')
            with imaplib.IMAP4_SSL('imap.gmail.com', 993,
                                  ssl_context=ssl.create_default_context(), timeout=30) as client:
                client.login(address, password.replace(' ', ''))
                status, _ = client.select('INBOX', readonly=True)
                if status != 'OK' or validity(client) != source['uidvalidity']:
                    raise HoldError('source_changed')
                status, sizes = client.uid('fetch', source['uid'], '(RFC822.SIZE)')
                match = re.search(rb'RFC822.SIZE (\d+)', b' '.join(x for x in sizes if isinstance(x, bytes)))
                if status != 'OK' or not match:
                    raise HoldError('source_unavailable')
                if int(match[1]) > MAX_BYTES:
                    raise HoldError('oversized')
                status, fetched = client.uid('fetch', source['uid'], '(BODY.PEEK[])')
                bodies = [item[1] for item in fetched if isinstance(item, tuple)
                          and len(item) == 2 and isinstance(item[1], bytes)]
                if status != 'OK' or len(bodies) != 1:
                    raise HoldError('source_unavailable')
                raw = bodies[0]
                client.logout()
        if len(raw) > MAX_BYTES:
            raise HoldError('oversized')
        return raw
    except HoldError:
        raise
    except Exception:
        raise HoldError('source_unavailable') from None


def preview(raw):
    """Return inert display text only. Nothing is rendered or executed."""
    if len(raw) > MAX_BYTES:
        raise HoldError('oversized')
    try:
        mail = BytesParser(policy=email.policy.default).parsebytes(raw)
        parts = []
        attachment = False
        def visit(part):
            nonlocal attachment
            if (part.get_filename() or part.get_content_disposition() == 'attachment'
                    or part.get_content_maintype() == 'message'):
                attachment = True
                return
            if part.is_multipart():
                for child in part.iter_parts():
                    visit(child)
            elif part.get_content_type() in ('text/plain', 'text/html'):
                text = part.get_content()
                if isinstance(text, str):
                    prefix = '[HTML source, displayed as text only]\n' if part.get_content_type() == 'text/html' else ''
                    parts.append(prefix + text)
        visit(mail)
        if attachment:
            parts.append('[Attachments omitted. Use your mail client to handle them.]')
        return 'Subject: ' + str(mail.get('Subject', '')) + '\n\n' + '\n\n'.join(parts)
    except Exception:
        raise HoldError('malformed_message') from None
