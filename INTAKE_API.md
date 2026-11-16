# Local intake API

`intake.py` is standard-library infrastructure. Construct `IntakeLedger(state)`
with a **private local** state directory outside the repository. The SQLite file,
rollback journal, source references, fingerprints, and candidate content must
never be uploaded, logged, or inspected through a cloud agent. No raw messages,
addresses, routing headers, passwords, or model error payloads are persisted by
the ledger. Source references deliberately remain identifying private metadata.
Existing state is not scanned or migrated automatically.

## Worker protocol

1. `ingest(source, fingerprint=None)` returns a stable 32-character candidate
   ticket. Accepted sources follow `holds.valid_source`, with an optional Gmail
   `mailbox` (default INBOX). Account hash, exact mailbox, positive 32-bit
   UIDVALIDITY and UID form Gmail identity. File identity binds normalized absolute
   path and raw-byte SHA256. Changed file bytes or mailbox epochs raise
   `IntakeError('source_changed')`; no automatic epoch reset/rebind exists.
2. Gmail can register identity before fetch. Bind SHA256 of the actual in-memory
   raw bytes by calling `ingest(source, fingerprint=sha256(raw).hexdigest())`
   before completion. File fingerprint must match its source SHA256. A differing
   fingerprint on an existing identity fails closed. Completion without a bound
   fingerprint is prohibited.
3. `claim(ticket, lease_seconds=600)` returns immutable `Claim(ticket, token)` or
   `None` for completed, blocked, or currently leased jobs. SQLite serializes
   competing claims. Expired jobs can be reclaimed; every claim gets a new token.
   A stale/expired worker cannot complete or block a reclaimed job. Choose a lease
   longer than the expected processing timeout; there is no heartbeat service.
4. `complete(claim, record)` accepts only `{status: needs_local_review, subject,
   body}` from the existing successful scrub/audit pipeline. This API does not
   itself establish that caller-supplied text is scrubbed. Same-claim, same-result
   completion is idempotent. A different result fails closed. The scrubbed result
   is committed to SQLite with FULL synchronization.
5. `materialize(ticket)` publishes the compatible `<ticket>.json` locally using
   a flushed temporary file and an exclusive hard link. Existing files, including
   reviewer edits/rejections, are preserved. A crash after DB commit can be repaired
   by calling this again, without repeating inference. A precommit crash leaves a
   recoverable expired lease. Failed temp writes are cleaned during normal error
   handling; abrupt termination can leave content-bearing temp files in private
   `intake/`. No automatic cleanup/deletion service runs.
6. `block(claim, fixed_reason)` durably records a hold reason; same completion is
   idempotent. Write the corresponding `HoldStore` record afterward. A crash
   between them is repaired by re-creating the hold with the same ticket/source.
   `retry(ticket)` explicitly requeues blocked work and fences its old token.
   It atomically increments `retry_generation`; duplicate retry calls while pending
   return false without incrementing it. Blocked work never requeues itself.

`work_tickets()` lists only pending/expired opaque tickets. `status(ticket)` returns
state, attempt count, fixed reason and retry generation (zero for legacy items).
The integrated runner uses that generation to reopen known exceptions, never
uncertain operations. `private_source(ticket)` is **local-only**
and returns `{source, source_version}`; the latter is the original raw-byte hash
or None before Gmail fetch. INBOX references retain the existing holds/actions
shape. Other mailboxes need a mailbox-aware source reader; the built-in CLI only
supports INBOX. Never give this API response to routing or Claude.

## Routing and actions boundary

`successful_records()` returns `{ticket, record}` objects, with only scrubbed
candidate fields and opaque tickets. Results are the immutable initial scrubbed
records, not subsequent reviewer decisions or edits. Consumers must reconcile
current CandidateStore versions, rejection/withdrawal and routing policy before
acting. Ledger completion confers no approval and performs no release.

For `ActionStore.bind_candidate`, use the intake ticket as candidate_id,
`private_source(ticket).source` as source_ref and `.source_version` as
source_version. Compute candidate_version from the **exact current CandidateStore
saved bytes**, never from reserialized JSON or the ledger result. All action
bindings and invalidations remain the actions/operations owners' responsibility.

## Minimal thread context

`link_thread(ticket, message_id, references=())` accepts bounded identifiers from
in-memory headers, hashes them with account/mailbox/epoch scope and stores only
private hashes and random thread IDs. It uses exact relationships, never subject
or person matching. Ambiguous multi-message thread merges fail closed. Missing
headers leave isolated one-message context. `context(ticket, limit=10)` returns
only completed scrubbed records and opaque tickets, bounded to 1..100 items.
There is no automatic header linking or context injection into model prompts yet.

## Existing CLI integration and remaining seams

`scrubber.process(raw, source=None, source_reader=..., workflow=...)` returns bool through
ShadowWorkflow's single durable shadow path. Source-backed imports persist checked
model provenance before candidate publication. Missing source bindings create a
local source-unavailable hold; they cannot produce managed candidates. The optional
local reader supports an already signed-in Gmail connection and synthetic tests.
Passing `raw=None` reads through that reader after epoch registration. Supplied
bytes bind the input digest; every computation/freshness read uses the source
reader. Launchers retain one workflow per batch; computation timeout stops the
batch with a fixed restart-required error. A caller-supplied workflow is the same
implementation, allowing bounded synthetic configuration without another pipeline.
Completed duplicates recheck current eligibility without repeating inference;
blocked/busy/uncertain/rejected/edited/missing-evidence items return False. Counters
describe outcomes, not newly created files. Gmail retains readonly INBOX selection
and bounded UID/UIDVALIDITY/size/BODY.PEEK checks. Fetch failures become managed
blocked jobs. No transport is reachable from this path.

Managed `triage` review uses review_workflow.Reviewer: explicit retries retain
intake tickets and retry generations, checked corrections use separate revision
IDs, and edits/rejections revoke evidence/request/action bindings. Legacy entries
retain local-only review; no existing data is migrated or evidence manufactured.
Uncertain operations still require proof-based reconciliation.

Schema version is SQLite `user_version=1`: mailbox epoch registry; item identity,
fingerprint, state, lease token/expiry, attempts, scrubbed result, fixed reason,
opaque thread ID; scoped hashed thread links. Unknown versions fail closed.
Do not edit runtime databases to reset identities. No Gmail connection, live model,
Claude delivery, action execution, schedule or background service is started by
importing or constructing these APIs.
