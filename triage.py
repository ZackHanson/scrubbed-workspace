"""Recheck an exception locally; successful checks create pending candidates only."""
from email.message import EmailMessage

from holds import HoldError, HoldStore
import scrubber as s


def draft_message(subject, body):
    if not body.strip() or len((subject + body).encode('utf-8')) > s.MAX_CHARS:
        raise HoldError('context_limit' if body.strip() else 'empty_output')
    mail = EmailMessage()
    try:
        mail['Subject'] = subject
        mail.set_content(body)
    except (ValueError, TypeError):
        raise HoldError('malformed_message') from None
    return mail.as_bytes()


def recheck(folder, snapshot, raw):
    holds = HoldStore(folder)
    current = holds.load(snapshot.ticket)
    if current.digest != snapshot.digest or current.record['status'] != 'open':
        raise HoldError('source_changed')
    try:
        s.ensure_local_model()
    except Exception:
        holds.update(snapshot, status='open', reason='model_error')
        return None
    try:
        record = s.scrub(raw)
    except Exception as error:
        reason = error.code if isinstance(error, HoldError) else 'processing_failed'
        holds.update(snapshot, status='open', reason=reason)
        return None
    # A successful check is still a pending candidate, never automatic release.
    ticket = s.save_candidate(record, folder)
    holds.update(snapshot, status='resolved')
    return ticket
