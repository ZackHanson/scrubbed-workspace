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
  Optional `retry_generation` defaults to zero and must be a nonnegative integer.
  A trusted intake adapter increments it only for an explicit blocked-item retry.
  A newer generation reopens a known `exception` with a fresh bounded attempt
  budget, once. It cannot reopen `shadow`, `claimed` or `uncertain` work. The
  consumed generation commits with the claim and survives restart/snapshot;
  older adapters/stores default to generation zero. It is not release authority.
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
is driven by ShadowWorkflow; file/Gmail commands also use that canonical path.
There is no independent legacy processing pipeline.

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

Use `recovery.snapshot`, `recovery.restore` and `recovery.acknowledge_restore`
from [RECOVERY.md](RECOVERY.md) for coordinated private-state recovery, including
this operations ledger. The former operations-only SQLite snapshot format and
its backup/restore/activation APIs are retired. There is no conversion or runtime
migration. Old `restore_pending` metadata still refuses execution; removing an API
does not grant permission to activate an old partial recovery.

## Validation

`python -B verify_synthetic.py` verifies the combined implementation with sockets
blocked and temporary state. Operations tests cover bounded batches, retries,
deduplication, uncertainty, process death and lock release. Coordinated recovery
tests cover inactivity before acknowledgement, restored operation claims and
receipts, unknown reservations and all supported state. No real intake, provider,
notifications, schedules or services are activated.
