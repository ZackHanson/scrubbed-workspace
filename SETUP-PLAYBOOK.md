# Build and run your own complete scrubbed workspace

This is an implementation and installation playbook. Give it to a coding model
with access to your development environment. Its task is to deliver a working
system on your computer, including the components it must build. Access to the
original author's private repository, accounts or machine is **not required**.

The finished system automatically collects selected email, scrubs it locally,
routes eligible messages to Claude, captures Claude's work in a separate workspace,
and handles permitted actions through local controls. Human attention is reserved
for exceptions and actions outside the owner's standing policy. A manual scrubber,
a mocked Claude connection or a written architecture is not the completed result.

## Copy this instruction to the model doing the setup

> Build, install and verify my complete Scrubbed Workspace using this playbook.
> Reuse approved source if available; implement missing components yourself.
> Continue through intake, local redaction, automatic routing, Claude processing,
> result capture, actions/replies, background operation and recovery. Give me a
> usable workspace and operating instructions. Use synthetic data for development
> and testing. Never bring original email, private routing maps, credentials or
> potentially identifying candidates into your cloud context, screenshots or logs.
> Real mail is processed by the local application and local model only; the
> runtime Claude connection receives only content permitted by the release policy.
> Configure my accounts through secure local setup, not credentials pasted in chat.
> Prepare and test the complete system before asking me for any remaining live
> activation decisions. Use authorization I have already given for specific
> destinations, costs and actions. Do not claim completion until the full workflow
> runs, exceptions recover, and the installed worker survives restart.

## 1. Agree on the recipient's setup

Resolve these choices early. Continue independent implementation while waiting
on account access or other prerequisites. Never ask for a patient example or
password in chat.

| Choice | Default or decision needed |
| --- | --- |
| Host | Dedicated or approved native Windows computer; adapt installation for macOS/Linux if requested. |
| Source mail | Gmail, with a locally configured account and selected folder/label. Another provider needs its own tested adapter. |
| Intake scope | New messages after an explicit start point; backfill is a separate bounded choice. |
| Local model | Ollama on numeric loopback; use `qwen3.5:9b-q4_K_M` when available and adequate. Validate any replacement. |
| Claude | Recipient's Anthropic API project, approved model and spending ceiling. Confirm API access/billing separately from any chat subscription. |
| Workspace | Local desktop application with scrubbed tasks, results, follow-up chat and exceptions. Optional dedicated scrubbed mailbox mirror. |
| Processing policy | Eligible work categories, excluded content, de-identification requirements and automatic-release rules. |
| Action policy | Automatic local task/draft updates; external sends only under explicit, bounded standing rules or individual approval. |
| Operations | Poll interval, daily budget, startup behavior, private retention and encrypted backup destination. |

Record decisions in a private local configuration and a content-free setup
receipt. Do not inherit the original author's paths, Git identity, accounts,
agent services, scheduling, backup destinations or coordination threads.

Real clinical messages require an organization-approved de-identification and
release process. HHS describes Safe Harbor and Expert Determination; LLM redaction
and two passes through the same model alone do not establish either. Implement the
chosen process as an enforceable release policy. An unresolved process is a live
activation dependency, not a reason to omit the cloud pipeline from the build.
See [HHS de-identification guidance](https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html).

## 2. Architecture and privacy boundary

Implement this complete route:

```text
Original mailbox / local export
    -> local intake and private source map
    -> local parsing, redaction, generalization and audit
    -> local policy: release automatically / local exception / ignore
    -> durable release outbox containing only permitted scrubbed content
    -> Claude API, with no raw-mail tools or private context
    -> validated result stored in the scrubbed workspace
    -> local action policy and optional approval
    -> local dispatcher resolves recipient/thread and executes permitted action

Exceptions -> local reviewer -> corrected draft or retry -> all release gates again
```

Separate these roles in code and storage; separate worker processes where
practical. Claude must not have direct access to intake, the original mailbox,
filesystem search, the credential store, source previews or the routing database.
The coding model helping set up the system has the same restriction on real data.

| Local-only private data | Permitted cloud payload |
| --- | --- |
| Originals, sender/recipient addresses, Reply-To, headers, source filenames/paths, attachment bytes, source message IDs, account hashes, exact private timestamps and identity mappings | Only generalized subject/body and a bounded task request that passed the recorded release policy |
| Credential material, local diagnostics and backups | No credentials or local diagnostics |
| Private conversation history and unscreened owner follow-ups | Only separately screened conversation turns |

Use fresh random opaque cloud task IDs where needed; never derive cloud IDs from
names, addresses or mailbox identifiers. Keep the cloud/local ID mapping local.
Cross-message linking can itself be identifying: minimize it and scope cloud
history to the approved task. Do not automatically reinsert names into cloud
output. Any locally restored routing or identity makes that artifact private again.

Disable content tracing, SDK debug dumps, error-body logging, crash-report uploads
and analytics that could capture sensitive text. Do not fetch email tracking
pixels, remote HTML resources or attachments. Do not put runtime data in Git or
cloud-synced folders. Use approved encrypted storage and owner-only permissions;
the application must verify its actual state path and protect newly created files.

## 3. Start from source or implement the system

Use one recipient-owned project folder, separate from all private runtime data.
If approved source is supplied, inspect its revision and tests, preserve local
changes, and inventory which requirements below it actually implements. Do not
assume a feature exists because documentation mentions it. If no source is
available, create a new project and implement these requirements directly.

The reference prototype at revision `466de50` provides only Python local
scrubbing, synthetic checks and desktop candidate/exception review. Its files
include `scrubber.py`, `holds.py`, `review.py`, `triage.py`, `synthetic_check.py`
and three test modules. It can accelerate the local components; it is not the
completion target. Do not preserve its mandatory-review behavior as the routine
workflow or treat its local review status as permission to transmit.

Suggested module ownership boundaries for a new implementation:

| Module | Responsibility |
| --- | --- |
| `intake` | Mail authentication, cursors, source identity and bounded imports |
| `local_scrub` | Safe MIME parsing, generalization, identifier checks, local audit |
| `policy` | Versioned deterministic routing and release/action rules |
| `store` | SQLite migrations, source map, task state, leases, transactional outboxes |
| `cloud` | Narrow Claude transport, payload validation, response validation |
| `workspace` | Scrubbed tasks/results/chat and separate local exception preview |
| `actions` | Local routing, approval binding, outbound delivery and reconciliation |
| `worker` | Polling, recovery, budgets, health and pause controls |
| `setup` | Secure account enrollment, installation, diagnostics and uninstall |

Python 3.13, Tkinter and SQLite are a practical Windows starting point. Use an
isolated virtual environment and pin any added dependencies. The reference
prototype uses only the standard library; a full build may add official provider
SDKs, OAuth and OS credential-store integration. Include a dependency lockfile,
configuration schema, migrations, installers, synthetic fixtures and operator docs.

## 4. Install the local runtime

Install Python with Tkinter from [Python for Windows](https://www.python.org/downloads/windows/)
and Ollama from [Ollama for Windows](https://docs.ollama.com/windows), using the
recipient's installation policy. Verify locally:

```powershell
python --version
python -c "import tkinter, sqlite3; print('Local UI and database available')"
ollama --version
```

Configure the Ollama server's environment, preserving previous settings:

```text
OLLAMA_HOST=127.0.0.1:11434
OLLAMA_NO_CLOUD=1
```

Quit and restart Ollama so those values take effect. Arrange a handoff before
restarting a shared installation. Do not start a second server on the same port.
Ollama documents configuration, cloud disabling and restart requirements in its
[local FAQ](https://docs.ollama.com/faq). Then download and verify the chosen model:

```powershell
ollama pull qwen3.5:9b-q4_K_M
ollama list
Get-NetTCPConnection -LocalPort 11434 -State Listen |
    Select-Object LocalAddress,LocalPort
```

Require `127.0.0.1:11434`; do not expose a wildcard, LAN listener, tunnel or proxy.
The client must also fix the numeric-loopback destination, bypass environment
proxies, reject redirects and remote-model metadata, validate JSON types and
schema, and reject incomplete outputs. Download weights before real use; do not
silently substitute a remote model after a failure. Verify capacity and latency
with synthetic inference on the actual machine rather than promising a RAM/GPU
minimum. The reference model uses a 32,768-token context and 240-second request
timeout; tune only with reevaluation.

If reusing the prototype, its existing checks are runnable now:

```powershell
python scrubber.py check
python -m unittest -v
python synthetic_check.py
python review.py --demo
```

The reference synthetic batch expects three candidates and two blocked messages,
clinical yield 2/2 and blocked auditor probes. These checks cover the seed only;
implement the full acceptance suite in section 13 as well.

## 5. Create private state and secure enrollment

Default Windows runtime root: `%LOCALAPPDATA%\ScrubbedWorkspace`, outside source
and sync roots. Support an application-specific state-path option; do not change
`LOCALAPPDATA` globally. Create distinct stores for private source references,
pending candidates, released tasks/results, content-free receipts and backups.
Keep all stores protected even when their contents are labeled scrubbed.

Use SQLite transactions and explicit migrations for durable state. Enforce unique
source keys, optimistic version checks, worker leases and atomic outbox claims.
Record model, prompt, policy and content versions with every decision. Retain
enough private audit history to explain release/actions without writing message
bodies to operational logs. Avoid storing raw originals if source references
suffice; any required private cache needs its own encrypted retention policy.

Build native local enrollment for mailbox OAuth/app passwords and the Anthropic
API key. Use Windows Credential Manager/DPAPI or the platform's secure credential
store with an established library. Config stores credential references, not secret
values. Never pass secrets in CLI arguments, `.env` committed to source, service
definitions, chat or screenshots. Test credential retrieval under the actual
background account, renewal/revocation, and a fixed-error re-enrollment flow.

For Gmail, prefer an implemented OAuth flow appropriate to the recipient's account
and deployment. Use official [Gmail IMAP/OAuth documentation](https://developers.google.com/workspace/gmail/imap/imap-smtp)
and [XOAUTH2 protocol](https://developers.google.com/workspace/gmail/imap/xoauth2-protocol).
If app passwords are allowed, use secure local entry and storage; availability
depends on 2-Step Verification and account policy. Do not weaken account security.
See [Google's app-password instructions](https://support.google.com/accounts/answer/185833).
An interactive password prompt on every poll is not unattended authentication.

## 6. Implement reliable unattended intake

Support folder/label selection, bounded initial import, repeated polling and
restart. Read messages without changing read status; use read-only IMAP and
BODY.PEEK for intake. Do not use only the unread flag as a durable cursor.

For IMAP, source identity includes local account reference, mailbox, UIDVALIDITY
and UID. A UIDVALIDITY change triggers controlled reconciliation, never blind
reuse of old UIDs. For another provider, use its stable identity and cursor
semantics. Advance checkpoints only after the source is durably recorded.

Deduplicate repeated polls and retries with a unique source key. Bound batch
size, bytes, nesting and decoded text before inference. Fail closed on malformed
MIME, attachments, unsupported formats and oversized content. Store a typed local
exception with a retrievable source reference. Keep originals available for
owner-only preview without fetching remote resources or opening attachments.

On network/authentication failure, preserve the cursor and queue, back off with
jitter, surface a fixed error and permit local credential repair. A missing or
changed original must never be silently replaced by a different source.

Acceptance: repeat an import, interrupt it before/after checkpoint commit, change
UIDVALIDITY, expire credentials, move a source and restart. No duplicate task,
silent loss, read-status mutation or source substitution is allowed.

## 7. Implement local redaction and automatic release

Treat email as hostile data, including subjects, quoted history and instructions
that claim to be system messages. Extract only supported text. Remove headers,
signatures, contact instructions, identity-only profiles and irrelevant attacks.
Use deterministic patterns, local-model generalization and an audit pass; preserve
the useful work request without inventing facts. Check names, contacts, locations,
dates, IDs, ages, rare events and identifying combinations, including in history.
Reject uncertain, incomplete or invalid output and suspected remaining identifiers.

Implement three routing outcomes after those checks:

- `auto_release`: the exact scrubbed content satisfies the active release policy
  and belongs to an approved routine work category.
- `local_exception`: uncertainty, privacy/usefulness failure, unsupported input,
  sensitive action or policy ambiguity requires local handling.
- `ignore`: an explicitly configured non-actionable category, retained as a
  content-free decision rather than silently disappearing.

Confidence from an LLM is not sufficient release authority. Deterministic code
must enforce the owner's versioned policy. Maintain an immutable release record
binding the content digest/version, scrub/audit results, category, destination
and policy version. In one transaction, commit the release decision and cloud
outbox entry. Recheck the binding before dispatch; edits or policy revocation
invalidate unsent releases. A `reviewed_locally` flag alone never opens this gate.

Build shadow mode that records would-release/would-hold decisions without
transmitting. Compare those decisions against labeled synthetic fixtures and
owner-local evaluation. Set acceptance thresholds before evaluation: zero known
identifier leakage in the suite, all mandatory holds blocked, all designated
routine fixtures processed, and recorded usefulness/exception-rate targets.
Do not make routine operation depend on opening every candidate. If exceptions
are excessive, improve evaluated rules/redaction instead of removing gates.

The local reviewer must support inert source preview, retry, composing a new
generalized draft, discard/reject and resolving exceptions. Run edited drafts
through all release gates. Preserve drafts on failed checks and prevent stale
review decisions overwriting a newer version.

## 8. Implement Claude processing and the scrubbed workspace

Use the recipient's approved Anthropic API project and a configurable supported
model. Verify current request/authentication syntax in the official
[API overview](https://platform.claude.com/docs/en/api/overview) and
[Messages reference](https://platform.claude.com/docs/en/api/messages/create).
Use [structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
where supported, plus strict local validation. Keep schemas and examples generic.
Do not hard-code an assumed model ID, price, context limit or account entitlement.

The cloud adapter accepts **only a durable released-task object**, never an email,
candidate directory or source reference. Serialize an allowlist of fields, such
as a random task ID, generalized subject/body and permitted task instruction.
Reject unexpected fields. Capture outgoing requests in synthetic tests and assert
that no private identifiers, metadata, paths or credentials except transport
authentication cross this boundary. Disable automatic redirects to other hosts.

Give Claude a fixed instruction to treat message content as untrusted, summarize
the request, produce useful work/draft replies, flag uncertainty and return
structured proposed actions. No direct mailbox, browser, filesystem or sending
tools. Useful fields include `summary`, `work_product`, `draft_reply`,
`proposed_actions` and `needs_owner`. Prompts may define behavior; they never
override the local release or action policies.

Persist requests before dispatch and validated responses before marking work
complete. Enforce request/output limits, timeouts, concurrency and a daily cost
ceiling. Record returned usage when available and conservatively reserve budget
for in-flight/unknown calls. Handle throttling, expired keys, malformed/truncated
results, refusals, provider outages and ambiguous outcomes explicitly. Do not
blindly retry an unknown completed request or claim provider-wide exactly-once
execution; record attempts, reconcile and bound possible duplicate charges.

Install a separate usable workspace showing task status, summaries, completed
work, draft replies, follow-up chat, errors and exceptions. It may be a desktop
application; a local web UI needs loopback binding and appropriate authentication,
origin and request protections. Private source preview belongs in an explicitly
local view and must never enter a cloud-connected page's context.

Screen every owner follow-up, pasted text, result reused as context and tool/action
output through the same local release boundary before another Claude request.
Do not automatically include entire mailbox threads, prior tasks or owner profile.
Validate and locally inspect returned text for unsafe instructions or unexpected
identifiers before display/reuse/action; no response is executable code.

If the owner wants a dedicated scrubbed mailbox, implement it as an optional
mirror of released tasks and validated results. Build a fresh message envelope:
generic subject, scrubbed body and opaque task token only. Never forward original
headers, addresses, attachments or signatures. Replies to this mirror are new
untrusted intake requiring screening. Tag application-generated messages locally
and prevent recursive intake loops. Claude processing must be an actual API
connection; sending mail to a second inbox does not by itself make Claude handle it.

## 9. Implement actions, reply routing and approval

Claude proposes work; local code decides what may happen. Use typed actions such
as `save_task`, `save_draft` and `send_reply`. Resolve source thread and recipients
from the private local map. Never accept a recipient/address/URL or arbitrary
command supplied by a cloud response as action authority.

Default behavior: automatically save results, tasks and drafts; send only under
an owner-established standing rule or explicit approval. A rule must specify
action type, allowed recipients/categories, content constraints, limits and
expiry. If the owner elects automatic routine replies, implement that option and
test it; do not require per-message approval inside the chosen scope. Route new
recipients, attachments, commitments, sensitive clinical decisions, money,
destructive requests and other excluded actions to exceptions.

For individual approval, display exact destination and final body locally and
bind approval to their digest, task/action version and expiration. Any edit,
recipient change or policy change invalidates it. Recheck authority at dispatch.
Use a separate outbound credential/scope where possible and include a hard
`send_enabled` control independent of cloud processing.

Use a durable action outbox and stable local action key. Record external message
IDs/receipts when available. If the network drops after submission, mark the send
`outcome_unknown`, reconcile against provider records where possible, and never
blindly resend. SMTP is not an exactly-once service. Test duplicate clicks,
concurrent workers and crashes on both sides of submission. Content/action loops
and bounced or auto-generated messages must not generate indefinite replies.

## 10. Install background operation and recovery

Implement one worker with a lease/heartbeat, bounded queues, backoff and graceful
shutdown. Suggested durable states:

```text
discovered -> scrubbing -> held | ignored | release_ready
release_ready -> cloud_queued -> cloud_inflight -> result_ready | retry_wait | held
result_ready -> action_pending -> approved -> sending -> sent | outcome_unknown
```

Make state transitions transactional and versioned. Recover abandoned leases
without discarding work. Distinguish a safe retry from an external operation
whose outcome is unknown. A worker crash must not erase an exception, cursor,
release decision, result, approval or send receipt.

Install an owner-approved Windows Scheduled Task, or the platform equivalent,
using absolute interpreter/source/config paths and the intended non-admin user.
Choose login start versus unattended boot deliberately: encrypted credentials,
session access and local model startup must work under the actual account.
Avoid storing passwords in task arguments. Prevent overlapping instances.
Start and health-check Ollama before processing; missing inference holds work
locally instead of falling back to cloud redaction. Test reboot/login and sleep/wake.

Expose distinct controls: pause intake, pause cloud release, disable sending,
resume, stop worker and health/status. A privacy incident pauses new cloud sends
without deleting records; recovery requires a deliberate reviewed resume.
Show last successful poll, queue counts, exception count, worker heartbeat,
model/API health, budget remaining and fixed error categories. Notifications must
contain counts or opaque references only, not subjects, names or message text.

## 11. Provide an operator interface and installer

Implement and document a single entry point. The following is a **required target
interface to build**, not commands provided by the reference prototype. Equivalent
names are acceptable if the delivered runbook gives the exact tested commands.

```powershell
python -m workspace setup                 # private paths and secure local enrollment
python -m workspace doctor                # runtime, loopback, credentials: no content
python -m workspace test --synthetic      # deterministic and local-model checks
python -m workspace test --e2e-synthetic   # complete route, real Claude if configured
python -m workspace run --mode shadow     # decisions only; no cloud release or sends
python -m workspace ui                    # tasks, results, chat and local exceptions
python -m workspace install-worker        # prepare/install approved startup task
python -m workspace activate              # apply recorded release/send policy
python -m workspace status                # content-free health and counts
python -m workspace pause --cloud --send
python -m workspace resume
python -m workspace stop
python -m workspace backup
python -m workspace restore-check
```

Make setup idempotent. Validate configuration before starting; include explicit
`mode`, account/source references, start cursor, model IDs, policy versions,
poll interval, cloud/send flags, destinations, limits, credential references and
retention settings. Generate a secret-free example configuration. Provide GUI
launchers for the owner; they must resolve the installed interpreter correctly.
Package installation/uninstall must preserve private data and unrelated jobs.

Include these recovery paths in the delivered UI and runbook:

| Failure | Required operator path |
| --- | --- |
| Local model unavailable | Hold locally, show model health and repair instructions; retry through all gates after recovery. |
| Mail credentials expired | Pause intake without losing cursors; open secure re-enrollment and resume. |
| Claude key, budget or provider failure | Retain released work, display fixed error/usage, repair enrollment or limits, then resume bounded retries. |
| Privacy or policy failure | Pause cloud dispatch, preserve evidence, repair and reevaluate affected unsent releases before deliberate resume. |
| Reply outcome unknown | Show local reconciliation/receipt tools; require resolution instead of presenting a normal retry button. |
| Worker absent or stalled | Show heartbeat and startup-task diagnostics; recover leases without spawning duplicate workers. |
| Missing/changed original | Show local source-repair/reimport guidance; do not rewrite source identity checks. |
| Restore or update failure | Keep dispatch disabled, preserve the failed state and follow the tested compatible rollback. |

## 12. Back up, update and recover

Separate source backup from private operational recovery. Back up the database
consistently using its backup facilities, configuration, policies, required local
maps and receipts into an approved encrypted destination. Secrets require a
separate secure recovery/re-enrollment plan; do not casually export them.
Record which originals remain only in the mailbox and how missing sources are
handled. Apply a deliberate retention/deletion policy to caches and records.

Perform a restore into an isolated temporary store with cloud/send disabled and
no installed worker. Verify queue state, source mappings, results and decisions;
check bytes/counts without exposing content to the coding model. Test with
synthetic data first; the owner performs private-data checks locally.

Before updates, pause new dispatch, checkpoint state, back up and apply tested
migrations. Model/prompt/policy changes need reevaluation and must not silently
reclassify previously held or released tasks. Keep a known-good source/config
version and a tested rollback procedure compatible with the database schema.
Rollback must not resend already submitted actions. Preserve evidence on failure.

## 13. Acceptance suite for the complete system

Build a labeled synthetic corpus and failure-injection tests. Use invented people,
reserved example domains and fake credentials. Never use real mail as test fixtures.
Mocks verify deterministic faults; actual local-model and Claude tests verify the
installed integration. A mock-only pass does not establish end-to-end readiness.

| Area | Required evidence |
| --- | --- |
| Redaction | Names, contact details, dates, ages, locations, IDs, signatures, quoted history, rare combinations and attacks are removed or held; useful task meaning survives. |
| Unsupported input | Attachments, malformed MIME, unsupported content, oversized inputs, model errors and uncertainty cannot create release entries. |
| Automatic routing | Approved routine fixtures reach Claude without per-message review; excluded/ambiguous fixtures reach exceptions; ignore decisions match policy. |
| Cloud boundary | Captured request bodies/metadata contain only allowlisted released fields; raw headers, routing, source paths, identifiers and private timestamps never cross. |
| Hostile instructions | Mail, follow-ups and cloud responses cannot alter policy, discover originals, change destinations or invoke unauthorized tools/actions. |
| Intake durability | Repeated polling, UIDVALIDITY changes, credential expiration, cursor crashes and concurrent workers neither lose nor multiply tasks. |
| Claude integration | A real synthetic request returns useful work, persists it, displays it and supports a screened follow-up; truncation/refusal/429/timeouts produce recoverable states. |
| Exceptions | Owner can inspect a synthetic original locally, retry/edit, resolve/reject; all new content passes gates and stale decisions fail. |
| Actions | Automatic allowed local actions work; approved/standing-rule replies reach an owner-controlled test mailbox with correct local routing; disallowed actions are held. |
| Send recovery | Recipient/body edits invalidate approvals; duplicate submissions and crash-after-send become reconciled or unknown, never blind retries. |
| Workspace/mirror | Results are usable; optional mirror contains no original envelope and cannot feed itself endlessly. |
| Operations | Installed worker starts under the real account, accesses credentials, resumes after reboot/sleep, respects pause and prevents overlap. |
| Budget and privacy stop | Caps halt new API work; invalid release bindings and privacy failures stop outbound processing while preserving queues. |
| Recovery | An isolated backup restore recreates synthetic state without triggering cloud calls or sends. |

Report corpus size, fixture categories, leakage/hold/usefulness results, exception
rate, latency and approximate API spend against thresholds agreed before testing.
Zero known leaks in a finite suite is necessary evidence, not a universal privacy
guarantee. Do not lower gates to make acceptance pass.

## 14. Activate the recipient's complete installation

Finish implementation, packaging, synthetic tests and a shadow run first. Verify
the exact source revision, release policy, destination, send rules, budget,
credential references, worker identity and recovery plan. Use already recorded
authorization; ask only for unresolved live account, cost or external-action
decisions. The coding model must not inspect real mail to obtain that confirmation.

Activate with a small bounded batch and conservative concurrency. The owner
locally verifies the initial real results and that exceptions are recoverable.
Then enable the intended automatic routine flow and installed background worker
under the approved limits. Verify at least one real eligible task reaches Claude
and returns to the workspace, one local exception can be handled, and the worker
continues after restart. The owner may attest to private checks using counts and
fixed outcomes; do not bring content into the setup model's context.

If external replies are authorized, demonstrate the chosen route to an
owner-controlled test mailbox before allowing the standing rule's real scope.
An owner may choose draft-only external actions while still having fully
automatic intake, Claude processing and results. Record the configured action
mode accurately. Optional mirrors are required only when the owner selected them.

Hand back:

- Installed workspace launcher and exact start/status/pause/resume/stop commands.
- Source revision, dependency/model versions and the installed worker identity.
- Secure enrollment/renewal instructions without secret values or private addresses.
- Active release/action rules, limits, excluded categories and exception workflow.
- Acceptance results, owner-attested live checks, reboot evidence and restore evidence.
- Update/rollback/uninstall and retention instructions, with any remaining dependency
  explicitly identified rather than reported as completed.

Completion means the recipient has their own functioning automatic workspace and
knows how to operate and recover it. If live access or an owner decision remains
unavailable, finish all independent build/test/install work and report precisely
what prevents activation. Do not stop at reproducing the seed prototype.
