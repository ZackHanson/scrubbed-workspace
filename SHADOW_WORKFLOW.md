# Manual synthetic shadow integration

`python shadow_workflow.py demo` runs a built-in synthetic email through durable
intake, real scrubber validation with mocked Ollama responses, persisted check
evidence, shadow routing and private local action bindings. It then runs a
**separate** fake-adapter test and captures an inert summary proposal. Files live
in a temporary directory and are removed. Socket connections are blocked. The
command prints counts and fixed statuses only. It does not read existing runtime
state, call Qwen, access a mailbox or send anything.

Shadow execution has no adapter instance or submit call. `WOULD_SEND` stays an
experimental shadow classification with `release_enabled=False`. The fake test
requires the exact built-in candidate and built-in `FakeTransport`, and constructs
its own synthetic authorization. It never converts shadow to release mode.
The adapter defaults to disabled and has no real provider client.

## Local API and durable boundaries

`ShadowWorkflow(private_folder)` creates local stores, so callers must explicitly
choose approved private storage outside source control. The CLI intentionally
accepts no live folder/source.

1. `register(source)` durably deduplicates private identity without reading mail.
   `run([ticket, ...])` accepts at most 100 explicitly selected tickets, using the
   bounded operations runner and process lock. A configured batch smaller than
   the supplied tickets is rejected rather than silently truncated.
2. Intake claims a fenced lease. The reader checks original bytes against the
   private binding; the default reader supports local files. Gmail requires an
   explicitly supplied local reader using intake's bounded UID/PEEK contract and
   memory-only local sign-in. No Gmail reader is activated here.
3. `scrub_checked` verifies local-only model identity and its SHA-256 digest before
   and after both existing model gates. Evidence is issued only after success,
   bound to exact subject/body and validator version. Failures still block
   candidates. This is provenance, not authenticity or a privacy guarantee.
   Replacement during a call fails closed; external server changes between
   observations cannot be atomically fenced.
4. Evidence commits before intake completion. Intake commits before candidate
   materialization; replay repairs a missing file without repeating inference and
   never overwrites reviewer edits. Interrupted work stays uncertain and requires
   local reconciliation rather than automatic replay.
5. Routing rechecks current bytes, evidence age (at most one hour, future stamps
   rejected), validator version, installed model digest and original source hash.
   Missing/changed evidence HOLDs. File-byte versions stay separate from canonical
   content digests. Routing receipts contain no content or private source references.
   Private source bindings go only to the local action store.
6. Saved edits get distinct operations IDs. Old evidence cannot approve changed
   text. HOLDs invalidate action bindings and create fixed-reason exceptions;
   details stay in routing receipts. Review markers do not authorize release.
   An invalidated version is conservative: use an explicitly reconciled local
   recheck/reimport path rather than resetting its database.

Each source/check and current-source/model computation has bounded caller waiting
(default 120 seconds, configurable up to 600). Workers perform no workflow commits.
Python cannot terminate a stuck callable; after timeout this process refuses new
computation and records uncertain operations. Late results cannot commit
evidence/candidates. Restart does not automatically retry the operation. Operations
recovery changes interrupted claims to uncertain. Its existing `reconcile` API
requires actual local proof of committed outcome or safe retry; lease expiry alone
is insufficient. Uncertain operations remain visible in the local ledger rather
than being silently marked successful.

## Separate synthetic adapter and result capture

Before fixture submission, `bind_result_request` durably records the ticket,
exact file version and content-derived submission key. This is correlation only,
never release authorization. `submit_fixture` is the sole supplied submission
caller and accepts only the constant fixture and built-in fake.

The adapter reserves its key **before** transport, then commits validated response
bytes before returning. `captured(key)` never submits. Only complete `end_turn`
results advance. Refusals, truncation, invalid results, timeouts and uncertain
completion cannot create normal proposals and never automatically resubmit. A
crash after delivery but before persistence leaves a reservation without a
recoverable response; manual reconciliation remains necessary. The adapter ledger
now contains potentially sensitive result text. Legacy status-only ledgers cannot
recover responses that were never persisted.

`capture(ticket, adapter, key, expected_candidate_version=...)` rechecks current
source/bytes/freshness, matches the durable request, reads captured results,
validates action schema/digest and commits inert local proposals. It holds the
desktop review writer lock through final checks and commits. A crash between
action capture and proposal creation can replay the same response without
transport. Replacement/cross-version results fail closed. Historical proposals
remain readable but are not execution authority. Consume current proposals through
this workflow; raw store history is not a freshness check. Arbitrary external
file/database writers are outside these cooperative locks and trusted local state.

## Verification and remaining dependencies

`python verify_synthetic.py` runs the combined suite with sockets blocked and
LOCALAPPDATA redirected to temporary storage. `python -m unittest -v` also runs
the tests, whose individual fixtures use temporary state. Coverage includes duplicates, source/candidate edits, status changes,
rejection, missing/stale/versioned evidence, model replacement, private binding
isolation, hard process death, timeouts/late completion, restart materialization,
result replay and uncertain adapter completion. Integration fixtures block socket
connections and use temporary synthetic state. Mocked success proves contracts
only; expanded evaluator and live-Qwen qualification remain separate work and were
not merged here.

Legacy scrubber commands and desktop review retain their behavior. Their candidates
lack this evidence and HOLD. Desktop exception retry still creates independent
IDs rather than retrying intake jobs; do not silently bind those IDs to existing
sources or treat them as integrated successes. No mailbox discovery, automatic
hold retry, thread-context injection, real-store migration, service, email action
or Claude delivery is activated. Pilot UX, provider selection, separately
authorized release policy, privacy/utility qualification and local operator
reconciliation remain outstanding. Operations backup covers only its own ledger;
full private-state backup/restore is not implemented or claimed. Existing backups
and schedules are unchanged.
