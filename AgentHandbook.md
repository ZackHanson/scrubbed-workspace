# Agent Handbook - Scrubbed Workspace

## Purpose and architecture

Owner: Zack. Create a useful separate workspace from locally scrubbed email.
Claude has no connection to intake, scrubbing, validation, routing, exception
review, storage or recovery. Its sole eventual role is the LAST consumer that
digests already-scrubbed email for the user. All upstream processing stays local.
The intended routine is automated local processing with human review for exceptions;
current candidates remain pending and shadow decisions grant no release authority.

## Source and working boundaries

Approved source is private `ZackHanson/scrubbed-workspace`. Preserve the established
T3 root and T3-managed task worktrees; canonical project location is
`C:\Users\zackw\Projects\scrubbed-workspace`. No extra clones/shell worktrees.
Preserve other writers, branches and private state. Never commit/push main.
Checkpoint owned branches and open one coherent draft PR; verify exact remote SHA
and clean tracking. Stored SSH origin fails host-key verification: use explicit
command-scoped HTTPS and the existing gh credential helper. Do not change stored
origin, SSH trust, global configuration or repository-local author identity.
Source integration is separate from release. Zack authorized consolidating PR10
into main and closing incorporated/superseded proposals, preserving branches and
worktrees. This does not activate email processing, Claude, services or schedules.
GitHub checks/deployments are not configured; protection inspection returned 403.
No protection enforcement is claimed and no settings workaround is authorized.

## Privacy and local state

Never put raw email, identifying source references, credentials, runtime stores or
real candidates into Git, cloud agents, prompts or logs. Do not inspect existing
real candidates or migrate them. Automated work uses invented messages and fresh
temporary state only, with sockets blocked for deterministic checks. Connected
Gmail tools are unsuitable for inspecting raw messages through a cloud agent.

Runtime is `%LOCALAPPDATA%\ScrubbedWorkspace`, outside source. Candidates and
results may still contain PHI. Private references in intake/holds/actions include
absolute .eml paths/hashes or hashed Gmail accounts plus UID/UIDVALIDITY. No raw
original copies or passwords are saved. Originals must remain recoverable locally.
Credentials are memory-only. Original previews are inert, local owner UI only.
Attachments, unsupported MIME, oversize input, uncertain/invalid model output,
suspected identifiers, stale evidence/sources and rejected versions fail closed.
Two passes through the same local model are correlated, not privacy certification.

## Run and check

Python 3.13, standard library only. Fixed local model `qwen3.5:9b-q4_K_M` at
numeric loopback `http://127.0.0.1:11434`, no proxies/redirects/cloud fallback.

- `python -B verify_synthetic.py`: full deterministic suite, temporary LOCALAPPDATA,
  blocked sockets; no inference.
- `python -B shadow_workflow.py demo`: isolated mocked workflow and separate fake
  result/proposal test; never translates shadow into release authorization.
- `python -B claude_pilot.py dry-run` and `shadow --request summary`: zero provider attempts.
- `python -B review.py --demo`: temporary offline mocked exception rehearsal.
  See REVIEW_REHEARSAL.md; automate only demo/temporary stores.
- Owner-local commands: `python scrubber.py check`, `files <path.eml>` and
  `gmail --limit 5` (Run Gmail Scrubber.cmd). These use the canonical durable
  shadow path with checked provenance. Gmail reads readonly INBOX using bounded
  UID/UIDVALIDITY/PEEK/size checks. Run receipts contain fixed categories/counts.
- `python review.py` (Run Local Review.cmd) opens the private local queue. Opening
  alone calls neither Gmail nor Qwen. Preview/retry asks for local Gmail sign-in;
  retry/draft checks run the fixed local model. Edits remain pending; local review
  markers never approve upload. Legacy entries remain local-only without evidence
  adoption. Rejection retains history and revokes current bindings.
- `python synthetic_check.py` uses real local inference on invented fixtures.
  Guarded evaluation instructions/evidence are in evaluation/LIVE_RESULTS.md.
  Do not run live inference for this source cleanup.

## Durable processing and recovery constraints

File/Gmail imports and managed reviewer use ShadowWorkflow, IntakeLedger and the
existing review coordinator. Evidence binds exact content, model digest, validator
and time; check it again with current sources/versions before local consumption.
Deduplication, source/lease fencing, retry generations, revocations and unknown
reservations survive restarts. Interrupted computations require explicit local
proof-based reconciliation; no missing-response retry or UI reset. Unchecked
drafts stay in memory. Late workers cannot publish evidence/candidates.

`recovery.py` is the sole supported snapshot/restore/acknowledgement system.
See RECOVERY.md for coordinated stores, auxiliary ledgers, exclusions and operator
attestations. No operations-only snapshot format or activation API is supported.
Restore fences before copying any runtime bytes, locks the destination, verifies
all bytes and stays inactive until explicit reconciliation. Unknown reservations
stay unknown. Snapshots exclude originals/credentials and do not prove encryption,
production backup coverage or provider reconciliation.

Keep recovery_guard.require_active read-only and active_state whole-operation,
nonblocking and same-thread reentrant. Normalize substores/Windows casing. Check
preexisting instances on every call. State, operations and candidate locks protect
different consistency boundaries; retain them. Preload source bindings on the
caller thread before bounded workers; workers must not reopen guarded IntakeLedger
DBs while the caller holds active_state. Cross-thread writes fail busy with safe
UI wording. Missing guard modules must fail closed. Disabled adapter/pilot APIs
create no state; enabled missing-parent adapter submit stops before validation,
and enabled reservation/dispatch/capture holds the active guard throughout.

## Evidence and limits

Live Qwen qualification at `123c26ef3923078e6016745f8038d94f011e87b5` passed
35/35 containment, 16/16 useful candidates/schema, 19/19 exact refusals and zero
execution errors. Model digest was pinned before/after inference:
`56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90`.
Expanded focused checks passed eight candidate cases and three auditor probes.
Earlier failure receipts and limits remain in evaluation/LIVE_RESULTS.md. This
is bounded synthetic evidence, not human semantic approval or privacy certification.
Model prompts, clinical corpus and thresholds stay unchanged in this cleanup.

## Current work

PR10 is the consolidated development baseline, including cleanup PR11 and all
earlier implementation branches. It has one canonical file/Gmail processing path,
coordinated recovery, shared strict ResultV1 validation and the offline reviewer.
A fresh verification of its cleanup tree passed 277/277 deterministic tests with
sockets blocked and temporary state; pilot dry-run/shadow made zero attempts and
the workflow demo passed. Model prompts/corpus/thresholds are unchanged. Review
findings for stale duplicate-source reads and timeout continuation are fixed.

Zack authorized retargeting PR10 to main, merging its exact verified head with
history preserved, and closing older proposals already included or superseded by
the current implementation/operator guides. GitHub records the exact merge SHA.
Preserve all source branches/worktrees and unique work. No new live inference or
private-runtime access is needed for source integration.

Owner chose Claude pilot PREPARATION WITHOUT SUBMISSIONS. No credentials,
account/model choice, provider calls, real messages, private-state access,
schedules/services, infrastructure, security changes or release are authorized.
Pilot budget, adapter reservations and action version bindings remain separate.
Next product work: owner offline usability rehearsal, a deliberate invented-email
qualification of the unified importer with local Qwen, then the final digest
experience. Broader privacy/utility qualification and production private-state
recovery remain pending. Final-consumer/provider/release work needs its own scope;
no automated real-message eligibility or upstream Claude connection is implied.
