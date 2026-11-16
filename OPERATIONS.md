# Manual operations and recovery

`python operations.py demo` runs one built-in synthetic cycle in temporary storage.
`python operations.py schedule-preview` prints a disabled schedule plan.
`--enabled --interval-minutes 30` previews an opted-in plan; it installs nothing.
There is no live-mail CLI, automatic startup, task/service installer or network code.
Configuration is the validated `Config` dataclass; each invocation is limited to
1–100 cycles, 1–100 items per cycle and 1–10 attempts per operation. Cycle pauses
are capped at 30 seconds. Retry backoff is persisted, exponential and capped;
it never keeps the process sleeping until a retry is due.

## Integration contract

Application code explicitly constructs `Runner(private_operations_folder, intake,
router, ...)` and calls `run()`. Use a dedicated approved local state directory
outside Git, distinct from the existing candidate/holds directories. The module
does not discover or open any existing application state. All invocations,
reconciliation and snapshots of this ledger share an OS-held exclusive lock.
The lock file persists; never delete it to break a live runner's lock. A process
exit/crash releases the kernel lock automatically. Local filesystems only;
network-share locking is unsupported. State directories must be trusted local
directories without symlink/junction redirection or other concurrent writers.

- `Intake.poll(limit, credentials)` returns `WorkItem(key, payload)` objects. The
  stable key must be a randomly assigned 32-character lowercase hex operation ID.
  Never use message IDs, UIDs, account hashes, addresses, paths or content hashes.
  The intake adapter owns its private mapping and reoffers pending items, including
  retry items. Payloads remain in memory and are never serialized by this runner.
  Respect the poll limit and use bounded source/network timeouts. The runner
  consumes at most the configured batch, including duplicate or deferred items.
- `Router.shadow(item)` performs local shadow processing only, idempotently keyed
  by `item.key`, and returns `shadow` or `exception`. An exception outcome means
  the adapter has durably created its local review exception. No candidate or
  routing decision implies release permission. No delivery adapter is invoked;
  disabling shadow or enabling remote delivery is rejected. Future delivery must
  use a separately reviewed interface and durable idempotency/reconciliation.
- `CredentialProvider.get(purpose)` supplies credentials locally in memory.
  `MemoryCredentials()` is the empty/fake default. There is no environment,
  plaintext file, keyring or persistence fallback. Call `clear()` on owned
  providers when finished; Python cannot guarantee zeroing immutable strings.
  Production local prompting/provider integration remains with the intake owner.
- `notify(summary)` receives only fixed counters and an interruption flag, never
  payloads, exception text or operation IDs. It is called for new exceptions,
  uncertain recovery, intake errors or interruption. A notification failure is
  counted and does not repeat processing. No default remote notification exists.

Adapters must not log raw messages, identifying routing, credentials or exception
payloads. Adapter calls are synchronous; cycle/item bounds do not preempt a hung
adapter. The adapter must implement request timeouts and cancellation. This module
does not call the baseline global-state `scrubber.gmail()` or `process()` helpers;
intake/routing adapter wiring is an integration dependency.

## Interrupted work

The ledger durably records `claimed` before calling the router. Successful shadow
or exception receipts deduplicate subsequent polls. `RetryableError` is allowed
only when the adapter certifies that no side effect occurred. It schedules a
bounded retry; exhaustion creates a fixed exception receipt. Unknown exceptions,
invalid outcomes and interruption become `uncertain` and never auto-retry.
On restart any remaining `claimed` record also becomes `uncertain`.

For uncertain work, the local operator/adapter must compare the operation ID to its
own durable receipts. `reconcile(folder, key, 'shadow'|'exception')` records a proven
outcome. `reconcile(..., 'retry')` explicitly certifies safe replay. It does not
reconstruct payloads or restore missing source mappings. Never infer safe replay
from an absent remote response. An exhausted retry is reported to the notifier;
it is distinct from an adapter-created content exception and needs local attention.

## Retention, backup and restore scope

No deletion is automatic. `retention_preview(folder, older_than_epoch)` returns
only the number of old terminal records. Removing deduplication records can cause
old unread messages to be processed again; establish coordinated source cursor
retention and recovery before adding pruning. The ledger has a configured capacity
and fails closed for new operations when full. Keep backups and operational
exceptions until the owner establishes a retention policy; do not delete real data.

`backup(folder, destination)` creates an exclusive new SQLite snapshot under the
runner lock and verifies integrity. It includes only this operations ledger:
opaque IDs, attempts, due/updated times, fixed states and restore metadata. It
excludes adjacent files, credentials, lock files and all candidate/message data.
Keep the snapshot in an approved private local backup destination outside Git;
this code performs no upload, cloud backup, encryption setup or schedule change.
Private source mappings, source cursors, candidates, holds, routing/delivery
receipts and reviewer edits require their owners' coordinated backup mechanisms.
This snapshot alone cannot restore the full email system. Existing backup policy
and destinations are unchanged.

`restore(snapshot, fresh_directory)` refuses an existing destination, checks the
database identity/version/integrity, and restores into a fresh directory only.
The restored runner is blocked by `restore_pending`. Reconcile source/adapter
receipts and potentially newer outcomes first, then explicitly call
`acknowledge_restore(folder)`. Claimed records still recover to uncertain after
acknowledgement. Never acknowledge a restored older ledger against newer sources
without checking duplicates, including previously terminal IDs absent in the old
snapshot. A fresh restore test covers ledger integrity, inactivity and preserved
deduplication using temporary synthetic state; it makes no full-system or real
private-state recovery claim.

## Validation and source status

Run `PYTHONDONTWRITEBYTECODE=1 python -m unittest -v` (set the environment variable
using your shell). Tests use temporary synthetic state and fake credentials only.
Validation on November 16: all 68 tests passed (51 baseline plus 17 operations),
with sockets blocked and LOCALAPPDATA redirected to temporary storage. The process
exit test crashes a synthetic child to verify kernel-lock release and durable
claim recovery; the fresh-restore tests verify default inactivity and deduplication.
Implementation is based on local baseline
`c07001746060b4c53054fb42d61c451a4043e2a9`. Shared handbook/publication ownership
stays with source setup. PR integration awaits its approved base bootstrap.
No real intake, Claude delivery, notifications, schedules or services are activated.
