# Local private-state recovery

This is a manually invoked, local-only sensitive snapshot API using the standard
library. It installs no job, changes no destination or policy, and transfers
nothing. No runtime directory is selected by default. The implementation is not
encryption, authenticated storage, immutable storage, or production backup
qualification. Protect source, snapshots and restored directories as private
local data. Hashes detect byte damage against the manifest; an attacker who can
rewrite both data and manifest is outside that guarantee.

## Inventory and exclusions

`snapshot(source, destination, extra_ledgers=...)` requires an explicit existing
private state root and a nonexistent destination whose parent already exists.
It covers all present supported stores:

| Store | Snapshot content |
| --- | --- |
| Intake | `intake/ledger.sqlite3`, including source bindings, claims, source versions, results, threads and retry generations |
| Candidates | Root opaque-ticket JSON, exact authored bytes and review status |
| Holds | `holds/<ticket>.json`, including sensitive original references and closure state |
| Workflow | `workflow.sqlite3`, all tables including checks, requests, revocations and checked review revisions |
| Routing | `routing/<ticket>-<digest>.json`, exact decision receipts |
| Actions | `actions.sqlite3`, all candidate bindings, results and inert proposals |
| Operations | `operations/operations.sqlite3`, including claims, uncertainty, attempts and metadata |
| Run receipt | Optional content-free `run-status.json` |
| Adapter/pilot | Explicit separately configured SQLite files mapped by role in `extra_ledgers`; restored as `auxiliary/<role>.sqlite3` |

A workflow DB requires its intake and actions DBs; a partial workflow inventory
fails closed. Stores that have never been created, such as operations before the
first run, are optional. Source inventory is bounded to these known formats;
unknown files/directories are rejected rather than silently copied. Newly added
stores require updating this inventory before claiming coverage. Previously
restored auxiliary ledgers inside the explicit root are included on subsequent
snapshots.

Original `.eml` files are excluded; original paths/hashes and Gmail UID bindings
remain sensitive local references inside the included stores. Preserve originals
separately at their existing paths. Recovery neither follows those references nor
reads Gmail, substitutes sources, copies credentials, or reconstructs old originals.
Store credentials elsewhere; unknown credential/config files cause refusal.
Kernel lock metadata, `.review-lock` markers, SQLite WAL/SHM/journals and `.tmp`
files are not copied. A held or abandoned candidate/hold lock refuses the snapshot;
the implementation never deletes someone else's marker or guesses it is stale.

## API and operator sequence

```python
from recovery import snapshot, verify_snapshot, restore, acknowledge_restore

# All variables are explicit operator-selected LOCAL private paths.
snapshot(private_root, new_snapshot_directory,
         extra_ledgers={'adapter': separate_adapter_db, 'pilot': separate_pilot_db})
verify_snapshot(new_snapshot_directory)
restore(new_snapshot_directory, new_restore_directory)
# Remains fenced. Inspect/reconcile LOCAL receipts, originals and adapter state.
acknowledge_restore(new_restore_directory,
                    operator_acknowledged=True, reconciliation_recorded=True)
```

There is no default directory, scheduling hook, automatic activation or cleanup.
Omit `extra_ledgers` only when there are no separately configured ledgers in scope.
Duplicate/same-parent ledger guard locks are reentrant. Each external ledger's
parent must participate in the runtime guard; an auxiliary file is never restored
over its original location. Configure the application explicitly to use the fresh
root and its restored auxiliary ledger paths after reconciliation.

SQLite `BEGIN IMMEDIATE` reservations are held across all selected databases;
each is copied using SQLite's online backup API through a separate reader. This
includes committed WAL bytes. Snapshot DBs use DELETE journal mode, excluding
transient sidecars. Existing review-actions, operations and candidate/hold locks
also participate. Application guard integration below is REQUIRED for coherent
cross-store workflow transitions; SQLite snapshots alone cannot make independent
multi-store application updates atomic.

Manifest v1 records every included relative filename, full byte count and SHA-256.
Restore verifies exact file membership, names, hashes and SQLite integrity before
creating a directory; verifies every restored byte and database; then rechecks
the source manifest and destination. Missing, truncated, unexpected, traversing,
symlinked or junction-backed inputs fail closed. Existing destinations and
overlapping source/destination trees are refused. Failed partial destinations are
retained for local inspection and remain fenced; no other's work is overwritten
or cleaned up. Cooperating writers must use the guard; this is not a defense
against a hostile process changing filesystem entries during a copy.

Before restoring any runtime bytes, restore creates `.recovery/state.json` with
pending status. The private restoration receipt lives beside it. Missing or
malformed state inside an existing anchor fails closed. Acknowledgement verifies
the restored receipt/bytes again, requires BOTH explicit boolean attestations,
and only changes the fence to active. It does not renew evidence, reset IDs,
retry claims, clear reservations, un-revoke requests, approve candidates, send
anything, or activate unsupported operations-only snapshots. Current source/model/
validator/version checks still apply. A claimed/uncertain job needs its existing
proof-based reconciliation. Unknown adapter reservations remain unknown: this
module cannot fabricate provider reconciliation. The booleans record operator
intent, not an independent provider proof.

## Runtime guard integration

The implementation supplies `recovery_guard.require_active(path)` (read-only) and
`active_state(path)` (whole-operation context manager). Direct existing runtime
entrypoints are not fenced merely by importing this module. The combined build
now wires the following through state_access decorators/context adapters:

| Module | Guard callsites |
| --- | --- |
| `shadow_workflow.py` | Mutating constructor and public `register`, `current`, `shadow`, `run`, `capture`, `bind_result_request` |
| `review_workflow.py` | `Reviewer` constructor, `retry`, `draft`, `dismiss`, plus standalone `invalidate_before_save`; read checks for `managed` |
| `review.py` | `CandidateStore.save` whole operation; read checks for constructor, `path`, `tickets`, `load` |
| `holds.py` | `HoldStore.create`, `update` whole operations; read checks for constructor, `path`, `tickets`, `load` |
| `intake.py` | Guard `_db` context for all DB methods; `materialize` across DB read and candidate publication; constructor before mkdir |
| `actions.py` | Constructor and entire `_transaction` context, including read methods using it |
| `routing.py` | Entire `DecisionStore.record`; preserve in-memory/no-folder behavior |
| `operations.py` | Entire `Runner.run`, including refusal of old partial restores, polling and dispatch; maintenance mutators must use the guard too |
| `claude_adapter.py` | Enabled `submit` across reservation, transport and finish; read check for `captured`; disabled constructor/submit retain no-files behavior |
| New pilot | Whole run/reconciliation with canonical state root and separately configured ledger parent lock |
| Intake output writers | Canonical scrubber process/Gmail batches and legacy candidate publication/hold paths must also participate in the same root guard |

Every call on a preexisting object must recheck/lock; constructor-only checks are
insufficient. Mutating constructors lock BEFORE creating stores. Guards import
operations locks lazily so operations may import the guard without a cycle.
Recovery errors have fixed content-free categories. UI handlers should surface a
safe restore/reconciliation notice without swallowing the fence and proceeding.

Known nested `intake`, `routing`, `holds`, `operations`, `review-actions` and
`auxiliary` folders normalize to the parent state root even before an anchor
exists. SQLite/JSON file paths normalize through their parent. If multiple
anchors exist, the OUTERMOST ancestor anchor owns the canonical lock; existing
immediate known-store anchors are also locked during adoption. Do not establish
arbitrary nested standalone roots during concurrent parent adoption. Establish
the workflow root first. Extra adapter/pilot ledgers use their explicit parent
guard. No default application path or private runtime scan is used.

The kernel lock is nonblocking, exclusive and same-thread reentrant. A worker
thread must not reopen a guarded store while its calling thread waits holding
that guard. Preload private source bindings on the calling thread before
`bounded_compute`; pass those bindings into source reads. Workers may read original
bytes and perform inference, but must not mutate/reopen workflow stores. Current
source checks and post-compute validation must remain intact.

## Evidence and limitations

`python -m unittest test_recovery -v` uses only fresh temporary invented stores
and built-in mocked model/fake transport fixtures. The complete journey creates
real intake, checked evidence, routing, action/result, edited/rechecked revision,
revoked request and rejected-candidate state. All SQLite logical dumps and every
manifest byte are compared after restoration. An additional adapter unknown
reservation remains unknown after acknowledgement; captured results stay durable.
Tests also cover committed WAL bytes, held SQLite/candidate locks, cross-thread
and process contention, normal/old nested anchors, partial restore failure,
missing/truncated/unexpected/traversing files, malformed fences, failed fsync,
and Windows junction rejection. No real state or credentials were opened.

The module's local guard test explicitly wraps runtime invocation to demonstrate
the fence API. Combined test_state_access additionally calls unwrapped direct
ShadowWorkflow, Reviewer, Runner, stores, legacy writers, adapter and pilot APIs,
including objects created before a pending fence. A full synthetic snapshot and
restore verifies that direct use stays blocked until acknowledgement, and that
duplicate work remains suppressed afterward. Copy-time regressions attempt direct
activation before the first runtime file is copied and while destination copying
holds its lock. Operations-only recovery APIs/format are retired; only this
coordinated system is supported. Source
tests do not prove real operator/provider reconciliation, separate-original
recoverability, encryption, production permissions, or crash durability of the
underlying storage hardware. No live-model or provider qualification is claimed.
