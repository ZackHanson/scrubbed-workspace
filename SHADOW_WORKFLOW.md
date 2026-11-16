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
exact file version and ticket/content-derived submission key. This is correlation only,
never release authorization. `submit_fixture` is the sole supplied submission
caller and accepts only the constant fixture and built-in fake.
Distinct tickets with identical scrubbed text do not collide. Repeated calls for
the same ticket/content keep their key. Existing content-only request bindings
can still capture durable results; new binding attempts for those legacy requests
require reconciliation rather than silently resubmitting under a scoped key.

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
only; expanded live-Qwen outcomes and their exact evaluated revision are recorded
separately in evaluation/LIVE_RESULTS.md.

Legacy scrubber commands and legacy desktop entries retain their local-review
behavior. Their candidates lack integrated evidence and HOLD; opening the reviewer
does not adopt them. Managed desktop entries now use the coordinator below.
No mailbox discovery, automatic
hold retry, thread-context injection, real-store migration, service, email action
or Claude delivery is activated. Pilot UX, provider selection, separately
authorized release policy, privacy/utility qualification and local operator
reconciliation remain outstanding. Operations backup covers only its own ledger;
full private-state backup/restore is not implemented or claimed. Existing backups
and schedules are unchanged.

Explicit `workflow.intake.retry(ticket)` increments a durable retry generation
only when it requeues blocked intake. `run` passes that generation to operations,
which can reopen a known terminal exception once per explicit retry. Restarting
or repeating a batch does not increment it. Claimed/uncertain and successful
operations cannot be reopened by a new generation; uncertain work still needs
explicit proof-based reconciliation. Generation records are local ledger state
and are included in that ledger's snapshots.

## Managed desktop review

`review_workflow.Reviewer` coordinates existing managed tickets only; triage
dispatches legacy entries to the existing local reviewer. The demo now seeds
managed synthetic exceptions without reading live storage or calling a model.

- Retry keeps the original ticket, source identity and bounded operations receipt.
  A completed checked item whose exception closure failed can finish closing it
  without another inference. An uncertain/claimed operation cannot be bypassed
  by editing a draft or reopening the window.
- Checking a correction uses the full local model pipeline and source checks.
  It records a separate random revision ID linked to the existing ticket, expected
  candidate bytes, hold snapshot and draft digest. Unchecked text stays in memory;
  only successful checked output/evidence is journaled. Original source references
  stay local and do not become draft/candidate content. Managed Gmail preview,
  retry and draft verification require local memory-only sign-in and strict
  UID/UIDVALIDITY/size checks with readonly INBOX and UID BODY.PEEK.
- Candidate edits/rejections revoke old requests and action bindings under the
  same writer lock used for result capture. Edits delete prior check evidence and
  open a needs-recheck exception; rejection closes it as dismissed. Status markers
  never manufacture evidence. A failed file save can leave prior work conservatively
  withdrawn. Historical proposals are retained but cannot be captured as current.
- Review actions share a nonblocking local lock; model work stays off the Tk thread.
  Final publication checks source/model/policy/age again and uses candidate/hold
  compare-and-swap. Stale edits are preserved. The revision journal commits checked
  output before candidate publication, then records installation before hold
  closure. Recovery can replay checked output without inference, never refreshes
  its check timestamp, and rejects stale validators. Completed installation does
  not strand a later correction after a crash during hold closure.

Interrupted model computation remains checking/unknown and requires explicit local
operator reconciliation; the UI offers no reset that could bypass it. Do not delete
receipts or locks to force a retry. Full private-state recovery remains separate:
the operations-ledger snapshot does not cover review revisions, candidates, holds,
intake, evidence, revoked requests or action/result stores. No real-store migration,
production transport, automatic release or scheduled operation is enabled.
