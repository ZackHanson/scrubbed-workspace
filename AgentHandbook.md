# Agent Handbook - Scrubbed Workspace

## Purpose and success

Help doctors create a separate workspace from locally scrubbed email. Owner: Zack.
Raw email must never be sent to a cloud AI, agent prompt, Git, or cloud logging.
The local model is Ollama qwen3.5:9b-q4_K_M on numeric loopback only.
Owner clarified the product goal: Claude should handle the user's messages to
save time, with human review rare and reserved for exceptions. The current
review-every-candidate prototype is a development stage, not the intended routine
workflow. Raw messages and identifying routing information must remain local;
automatic release and Claude integration still require implementation and testing.

## Run and verify

Python 3.13, standard library only. `python scrubber.py check` checks the local
model; `python -m unittest -v` checks synthetic failure and review gates.
`python scrubber.py gmail --limit 5` prompts locally for source address and a Google
app password, reads unread messages without marking them read, and scrubs locally.
`python scrubber.py files <path.eml>` accepts a local export.
`python synthetic_check.py` runs a fake-inbox batch with real local inference,
review persistence checks and separate auditor probes. `--diagnose` prints only
built-in synthetic model outputs. `python review.py --demo` opens an isolated
synthetic desktop example; `python review.py` or Run Local Review.cmd opens the
actual local exception/candidate queue. Opening the window does not call Gmail or
Ollama. Preview/retry of Gmail originals explicitly requests local sign-in; retry
and edited-draft checks call the fixed loopback model.

## Boundaries

All outputs are unapproved candidates in `%LOCALAPPDATA%\ScrubbedWorkspace`,
outside the repository. Treat candidates as potentially containing PHI. No sender,
recipient, routing headers, raw message, attachment or source filename is saved
in candidate content. Exception records now store private source references in
the local holds subfolder: absolute .eml path plus content hash, or hashed Gmail
account plus inbox UID/UIDVALIDITY. Treat these references as private; never put
them in Git, agent prompts, candidate output or logs. No raw original copies or
passwords are saved. Source previews are for the owner locally, never cloud agents.
Attachments, unsupported MIME, oversized input, model errors, uncertain redaction,
suspected remaining identifiers and invalid output block candidate creation.
No forwarding, automatic approval or Claude integration exists yet. Local review
and an appropriate de-identification process remain required before any upload.
Two passes through the same model are correlated and cannot certify compliance.
Do not use connected Gmail tools to inspect raw messages in a cloud agent.
The desktop review tool records needs_local_review, reviewed_locally or
rejected_locally. These are workflow markers, not de-identification approval.
Edits must be saved as pending before recording review. Rejection retains files;
no export/upload action exists. Review content only in the local window, never
through a cloud agent. Use --demo and temporary stores for automated UI testing.

## Current work

### November 16 integrated shadow workflow (task worktree)

Work is isolated on feature/integrated-shadow-workflow from owner-approved local
base 466de50eee9d7cae10d41c74d9f00672f61ae578. All six specified track heads were
merged with their full histories, including adapter prerequisite 65f5234. No
unfinished evaluator or UX branch was merged. No remote fetch, origin/trust/global
configuration change, real mailbox read, live inference or delivery was performed.

The manually invoked integration now connects durable intake, checked model
provenance, shadow routing and private local action bindings. Shadow never calls
an adapter. A separate constant-fixture fake adapter test captures durable results
and produces inert local proposals. Twenty-one integration tests pass,
covering duplicates, stale evidence/candidates/sources, hard process death,
timeouts, intake materialization recovery and adapter/result capture restart.
Final combined verification: `python verify_synthetic.py` passed all 180 tests
with sockets blocked and LOCALAPPDATA redirected to temporary state. The temporary
CLI demo passed with one shadow classification, zero duplicate attempts and one
separately authorized fake result/local proposal. No live model was tested.
GitHub confirms private source, main/default at the approved base, main unprotected,
zero Actions workflows, hooks and deployments. Security settings were not changed.
Source-only draft PR: https://github.com/ZackHanson/scrubbed-workspace/pull/3,
linked to this T3 thread. Implementation checkpoint b2a0900 follows history-preserving
six-track merge 3ff83e5. Branch publication used command-scoped HTTPS pushurl and
existing gh login after the SSH transport failed; stored origin, SSH trust and
global configuration were preserved. No automatic merge is authorized here.
Expanded/live-Qwen evaluation, legacy desktop retry-to-ledger wiring, pilot UX,
release/provider qualification and full private-state recovery remain dependencies.

Initial implementation on feature/local-email-scrubber in the existing T3 root.
Installed local model discovered successfully. All 15 synthetic unit tests passed.
Live Qwen synthetic email test removed the tested name, date of birth, record number,
street/city and phone despite an embedded instruction to repeat names. Candidate
remained marked needs_local_review. This is a smoke test, not a privacy guarantee.
Gmail trials save a content-free run-status.json (stage, authentication outcome,
counts and fixed error categories) locally, tested for zero unread, failed sign-in
and blocked input. The latest trial authenticated and saved one local review
candidate. On November 14 the content-free receipt confirmed that the prior live
trial completed: five selected, five saved for local review, zero blocked, no
reported error. No existing candidate content was inspected through the cloud agent.
Forwarding remains absent.

November 14 follow-up: diagnosed the original clinical yield of 0/2 using only
built-in synthetic model outputs. An overbroad ID regex consumed ordinary words
after policy/record; the redactor retained attack text and identity-only profiles;
the verifier inferred identifiers from empty placeholder profiles. Narrowed the
ambiguous label regex (strong MRN/DOB/SSN/patient-id labels still redact alphabetic
IDs) and made the prompt prioritize generalized useful requests, dropping identity
profiles and instruction attacks. Audit instructions distinguish placeholders and
general clinical topics from identifiers; uncertainty/identifier gates remain.

The final five-message live-model batch saves three review candidates (both
clinical examples plus clean workflow) and blocks attachment/HTML inputs. Separate
auditor probes block a name with an instruction attack, a written date and age 94.
Known synthetic identifiers and attack phrases are absent from saved outputs;
clinical topics are retained. Model-generated candidates also pass local
review/edit/rejection persistence checks. This is a small smoke test, not a privacy
guarantee; broader clinical examples and local human evaluation remain needed.

Desktop reviewer implemented in review.py using standard-library Tkinter. It
supports editing, recording local review and rejection, checkbox confirmation,
pending status after edits, conflict detection, atomic saves and per-candidate
writer locks. Existing real candidates were not inspected or modified. All 29
unit/UI tests pass with temporary synthetic storage. The synthetic desktop demo
was opened and its candidate selected for the owner to try. It uses temporary
examples only; no existing candidates were displayed through computer use.
Exception reviewer implemented next: new blocked inputs create fixed typed reason
records in local holds storage with source references when available. Open
exceptions, Candidates and Closed exceptions are separate views. The UI displays
hold reasons/actions and can preview originals locally as inert text, retry through
the full model gates, check a newly composed draft, or dismiss an exception. Regex
highlights cover matching body/subject values but do not detect every identifier.
Unchecked drafts are never saved; failed checks preserve the in-memory draft.
Successful checks close the exception and create a new needs_local_review candidate.
Dismissal retains the original; sequential reimports deduplicate matching sources.
Gmail reopen uses the exact account hash/UIDVALIDITY/UID, read-only inbox and PEEK;
credentials come from native local dialogs, never saved. Changed/missing sources
fail closed. No attachment is opened or remote HTML resource fetched. Source reads
and inference run in a worker so the local UI remains responsive.

All 51 unit/UI tests pass, including metadata privacy, source mismatch, Gmail read
semantics, stale decisions, failure recovery, draft preservation and exception
resolution. The real-model synthetic batch still yields 3 candidates/2 blocked;
blocked inputs have retrievable fake Gmail references. A synthetic held .eml also
passes the real retry path and becomes a pending candidate, closing its exception.
The updated synthetic demo was visually inspected, including local source preview
and identifier highlighting. Existing real candidates/messages were not opened or
modified. Old count-only blocked trials cannot be retroactively reconstructed.
Next: owner tries the exception demo; expand synthetic evaluation and implement
automatic routing decisions in shadow mode before any real Claude delivery.
Routine candidates still require local review; the exception UI alone does not
enable the eventual automatic workflow. Keep local identity/routing separate from
any content Claude receives. Forwarding remains absent; no automatic release
policy is activated.
Existing source destination is private ZackHanson/scrubbed-workspace, with no commits
on remote main. SSH remote fails host-key verification. User's global instructions
instead name hanster1 and a canonical Projects path; destination/path reconciliation
is pending. Git commit also failed because author identity is unset; no identity
settings were changed. Source files are staged locally, not committed or pushed.
Preserve the existing T3 view and staged starter files.


### November 16 source setup and seven-track coordination

The source-setup thread alone owns writes/Git setup in the existing T3 root until
an initial local baseline is ready. Preserve this root; do not create replacement
clones or shell worktrees. The six implementation threads remain read-only here,
then carry their existing task in the SAME thread into a T3-managed worktree using
the source owner's exact local baseline SHA, startFromOrigin:false and
runSetupScript:false. No real email/Claude delivery or scheduler activation.

Implementation thread IDs (common prefix
`thread:mcp:392f8e06-4950-4c4b-bf69-9e0177a2b114:scrubbed-workspace-seven-tracks-20261116-v1:`):
- `0`: Reliable email intake.
- `1`: Automatic routing in shadow mode.
- `2`: Expanded synthetic evaluation.
- `3`: Claude connection and result capture.
- `4`: Actions and reply workflow.
- `5`: Background operation and recovery.

Source inventory is exactly 15 selected files: .gitignore, AGENTS.md,
AgentHandbook.md, README.md, both .cmd launchers, assets/icon.svg, scrubber.py,
holds.py, review.py, triage.py, synthetic_check.py and the three test modules.
Original index had eight staged files; four staged blobs differ from working
bytes (handbook, README, scrubber and test_scrubber). Seven source files were
untracked. Original binary index, every staged blob and all on-disk source bytes
were copied and byte-verified outside Git under the owner's backups directory,
source-setup-20261116-144331, before deliberately changing staging. Ignored files
are generated Python caches only; no ignored authored assets were found.

All 51 deterministic synthetic tests pass with socket connections prohibited and
LOCALAPPDATA redirected to temporary storage. Source allowlist privacy inspection
found no credential signatures, raw email, candidates, runtime databases or private
source-reference records. No private runtime directory was opened. No local
workflow/deployment files or active Git hooks exist; launchers run Python manually.
GitHub CLI verifies ZackHanson and its private empty scrubbed-workspace repository;
the connected GitHub app is hanster1 and cannot access that repository. Author and
conflicting owner guidance await one bundled owner clarification in source setup.
No identity, SSH trust, global Git setting or remote URL has been changed.

Remote inspection: no branches, Actions workflows, hooks or deployments; Pages
lookup returns 404. Ruleset inspection returns 403 (GitHub Pro/public repository
required), so enforceable remote protection is not established. Do not change
visibility or security settings to work around this. Remote publication remains
pending; there is no verified remote source backup yet. This source-only work
never claims runtime/private-data backup. Source owner sends the exact baseline
SHA to all six existing threads as soon as author identity permits a checkpoint.


Owner resolution, November 16: Zack explicitly approved commit author Zack
<354641050+ZackHanson@users.noreply.github.com> and the existing private
ZackHanson/scrubbed-workspace source destination. This project-specific decision
supersedes the generic hanster1 destination guidance; the existing T3 root stays.
Only repository-local user.name/user.email were set. SSH trust and global Git
configuration remain unchanged. Initial baseline captures the verified 15-file
source allowlist; remote publication is pending at checkpoint creation.


Verified shared implementation baseline:
`c07001746060b4c53054fb42d61c451a4043e2a9`.
The source owner sent that exact SHA and same-thread T3 handoff instructions to all
six implementation threads. Their task worktrees must start from this local SHA,
not a remote/default branch. Root remains source-owner controlled.

The baseline was pushed to approved private ZackHanson/scrubbed-workspace on
feature/local-email-scrubber using command-scoped HTTPS transport with existing gh
login. Stored SSH origin and SSH trust were preserved. Remote branch SHA was
verified, and a fresh GitHub API restore of all 15 source blobs matched byte for
byte. Detailed receipts and restored files are outside Git under the source-setup
backup directory. This proves selected source recovery only, never runtime/private
data backup. Git's first archive applied Windows newline conversion; a second
archive with command-scoped core.autocrlf=false verified exact Git blob bytes.

The previously empty remote made the first feature branch its default; no main
branch exists. A PR cannot yet target main. Do not initialize/push main, change
repository visibility, or install protection under this setup authority. Source
branches may be backed up; PR/integration setup awaits an owner-approved base-branch
bootstrap. GitHub reports paid-plan requirements for private rulesets/protection.
No workflows, hooks, Pages deployment or deployment records were found.

Owner additionally requested changing Windows Codex startup repository guidance
from hanster1/<project> to ZackHanson/<project>. Only that text was replaced in
C:/Users/zackw/.codex/AGENTS.md after preserving its original bytes outside Git.
Existing explicitly recorded repository destinations are not migrated by this
local startup-default change. No global Git configuration changed.
### November 16 guarded live synthetic evaluation

This assigned worktree starts at exact evaluation tip
292cb40b5fa535d06719179215ae36e1841e6948. Remote main/default verified as
466de50eee9d7cae10d41c74d9f00672f61ae578. No root or other worktree changed.
Read evaluation README, runner, corpus, core transport and focused tests. All 15
focused evaluator tests pass. Privacy guard review confirms fixed numeric loopback,
fixed local model with remote metadata rejection, proxies/redirects disabled,
serial exclusive experiment lock, built-in synthetic inputs only, temporary STATE,
no persistence, and content-free receipts. Guarded live evaluation completed with exit 1;
receipts are in an operator-selected temporary directory outside private runtime
and Git. Seven input refusals and twelve injected faults are not live-model proof.
No inbox/private runtime inspection, delivery, service or security changes.

Live run at 292cb40 completed all 35 cases: privacy 34/35, required meaning 15/16,
exact refusals 19/19, candidate schema 16/16, unexpected errors 0. context-01
retained three rare identifying traits despite both model passes accepting it;
utility-05 lost diagnosis/prescription exclusions. Guarded focused replays
reproduced both. These are core/model issues, not established evaluator defects;
core files, corpus and thresholds remain unchanged. Two focused evaluator tests
preserve these failures. See evaluation/LIVE_RESULTS.md for separate live versus
injected outcomes, receipt provenance, limitations and the integrated-head rerun.
Original full deterministic suite passed 66/66 with network prohibited and temp
LOCALAPPDATA; final focused evaluator suite passes 17/17. No combined-system proof
or certification is claimed. Integration owner must address the reproductions
and rerun on the exact combined head; this thread does not wait for integration.
The task PR targets feature/synthetic-evaluation (existing 292cb40 evaluation tip)
to exclude pre-existing evaluation commits from this change. No main push/merge.
Remote protection inspection still returns 403; no enforcement claim or settings
change. Source checkpoint and remote SHA verification follow before handoff.
Final deterministic verification after adding reproductions: 68/68 passed with
network sockets blocked and temporary LOCALAPPDATA. Final focused tests: 17/17.
Source follow-up is published as PR #2:
https://github.com/ZackHanson/scrubbed-workspace/pull/2
The initial task checkpoint 14eaa3101b3551a91ffd429b4c1e5f663ea1851e was
verified against the remote branch and PR head, with a clean worktree and nothing
ahead. GitHub reported no checks and no reviews. This final documentation-only
checkpoint records that publication; its remote SHA is verified at handoff.
PR remains open for integration; no merge or combined-head rerun was performed.

### November 16 Qwen privacy and meaning fixes

This host-managed task worktree starts at exact integrated head
92633ac067ee074b44ee5435f22e0b4ef5923f18, not main. Evaluation reproduction and
publication commits 14eaa31 and 2b92654 were cherry-picked with history preserved;
both existing handbook records were retained. No other worktree was modified.
Redactor instructions now separate requested work from distinctive biography and
explicitly retain scope, exclusions and negation. Auditor instructions explicitly
check residual trait combinations without requiring a name or location. Examples
use unrelated invented topics. Core corpus and strict thresholds are unchanged.
The guarded runner now pins the verified model digest across every inference.
Focused live probes include both reproductions, four independent synthetic cases,
and separate rare-context/clean auditor probes. Completed qualification follows below.

Completed qualification: clean combined code head
123c26ef3923078e6016745f8038d94f011e87b5 passed the full 35-case guarded live run:
privacy containment 35/35, useful candidates and schema 16/16, exact refusals 19/19,
zero execution errors. Model digest verified before/after each actual inference:
56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90.
All 184 deterministic tests passed with sockets blocked and temporary storage;
36 focused deterministic tests passed. Expanded focused live check passed eight
candidate cases and three auditor probes. An intermediate full run failed on
quoted history; the auditor correctly blocked residual context, and task
extraction was fixed without weakening it. Both receipts are retained and
explained in evaluation/LIVE_RESULTS.md. Corpus/thresholds remain unchanged.
Source-only stacked draft PR #4 targets feature/integrated-shadow-workflow and
is linked in T3. Remote main remains 466de50; no merge/release was performed.
Evaluation success is not privacy certification or release permission. Remaining:
broader local qualification, independent integration review, desktop retry wiring,
pilot UX, release/provider qualification and private-state recovery. These are
separate from this task. Subsequent checkpoint changes only result documentation.

### November 16 independent integration review and fixes

Reviewed combined integration/Qwen head 34eda178c90052b733747e24769bbfdcd4cd482e
with an independent read-only reviewer and synthetic temporary-state reproductions.
Two confirmed P2 findings: content-only submission keys prevented distinct messages
with identical generalizations from each obtaining a result; explicit intake retries
remained suppressed by terminal operations exceptions. No cross-source misbinding
was observed; the collision failed closed. Interrupted hold persistence was also
tested: it remains uncertain and is repairable after explicit safe-retry
reconciliation, as documented. The review is bounded evidence, not certification.

This isolated branch scopes new request keys to the immutable local ticket and
content, keeping policy/retry keys stable. Only a hash reaches fake transport;
payload stays subject/body. Legacy content reservations block new scoped sends,
and existing legacy results can still be recovered. Explicit intake retries now
atomically increment a local generation; operations consumes it with its claim
and reopens only a known exception. Unknown/claimed work still requires proof-based
reconciliation, and completed work stays deduplicated. Additive local ledger
tables default old items to generation zero; no existing real runtime was opened.

All 194 deterministic tests pass with sockets blocked and temporary LOCALAPPDATA,
including ten new regressions for distinct-message results, cross-ticket rejection,
legacy recovery/reservations, retry restart/deduplication and uncertain-work fencing.
The prior 35-case live-Qwen success is unchanged model-code evidence; this task
does not modify model prompts or rerun inference. Remaining desktop retry/exception
closure wiring, pilot UX, release/provider qualification and full private-state
recovery are separate. No merge, real data, delivery or schedule activation.
Source fixes are prepared as a stacked PR against feature/qwen-privacy-meaning-fixes;
publication and remote-head verification are reported at handoff.

### November 16 managed desktop workflow integration

Continued step 3 in the existing T3-managed worktree on a new owned branch,
feature/desktop-workflow-integration, based on step-2 head
327bea529820b86589f3bffa8ade8e723e3c98f7. Earlier source branches are preserved.
Managed desktop retries now retain intake tickets, use explicit retry generations,
and resolve successful exceptions. Checked corrections retain the source binding
and record separate local revision IDs rather than unrelated candidate identities.
Candidate edits withdraw old evidence/requests/results before saving; rejection
also closes an open hold. Legacy entries retain local-only review without silent
adoption. The synthetic exception demo now seeds managed tickets without inference.

The coordinator journals only checked output/evidence, input digests and local
version context, never unchecked draft text or credentials. It serializes review
actions, fences stale candidate/hold snapshots, preserves failed drafts in the UI,
and replays interrupted publication without repeating inference. Installation is
recorded before hold closure so a crash during closure cannot strand later edits.
Recovered output must still pass current policy/model/age/source checks. Unknown
computations remain blocked for explicit local reconciliation; there is no UI reset.
Managed Gmail preview/retry/draft verification uses memory-only native local sign-in
and strict UID/UIDVALIDITY/read-only PEEK checks. Existing real state was not opened.

Independent read-only review reproduced three P2 gaps during implementation:
missing Gmail draft credentials, closure/journal crash ordering, and missing current
validator checks on recovery. All three were fixed with regression reproductions.
Final deterministic suite passes 215/215 with sockets blocked and temporary storage;
21 new tests cover the coordinator, asynchronous desktop journey, source/privacy
checks, stale edits/rejection, restart/failure recovery and managed demo setup.
The synthetic CLI workflow demo also passes. No manual visual demo or live Qwen
rerun occurred; model prompts and evaluation fixtures/thresholds are unchanged.

Source-only PR is stacked on step-2 feature/integration-review-fixes. Publication
and exact remote head are verified at handoff. No main push, merge, real message,
Claude delivery, email action, service or scheduler activation. Remaining: owner
synthetic usability rehearsal, broader qualification, provider/release decisions
and full coordinated private-state recovery (operations-only backup is insufficient).

### November 16 coordinated private-state recovery source

Owned host-managed branch feature/coordinated-private-state-recovery starts at
desktop integrated head cde70a09a391f5e205d5ba84e14448b967e82c3c. Only new
recovery.py, recovery_guard.py, test_recovery.py, RECOVERY.md and this Current
work record changed. Existing core/UI/pilot modules are owned by the primary and
other threads; none were edited here.

Explicit local snapshot/restore APIs now inventory intake, candidate/hold JSON,
workflow checks/requests/revocations/revisions, routing receipts, actions/results,
operations and explicitly selected external adapter/pilot SQLite ledgers. Shared
guard locks, existing workflow writer locks and simultaneous SQLite reservations
coordinate snapshots. Full manifest membership/size/SHA-256 checks and SQLite
integrity checks reject missing/truncated/unexpected/traversing/symlink/junction
inputs. Fresh destinations only; partial failures remain private and fenced,
without cleanup or overwrite. Originals, credentials, locks/journals/temp files
are excluded. Sensitive original references remain inside private snapshots.

Restoration writes a persistent pending fence before any runtime bytes; explicit
operator acknowledgement/reconciliation is required. No IDs, unknown reservations,
completed results, revocations or versions are reset. Unknown provider state
remains unknown; no provider proof, encryption or production backup is claimed.
RECOVERY.md records precise primary-owned guard callsites and the worker-thread
source-binding preload needed before guarding intake DB access. This source branch
tests the guard API explicitly; the primary must wire and test direct workflow,
reviewer, runner, stores and pilot entrypoints on the final combined head before
claiming application-wide restored-runtime inactivity.

Final source verification: 15/15 focused recovery tests and 230/230 deterministic
tests pass with sockets blocked and temporary LOCALAPPDATA. Synthetic CLI demo
passes (one shadow classification, zero duplicate attempts, one fake result/inert
proposal). Fresh synthetic restoration compares every manifest byte and all DB
logical dumps, preserving source bindings/evidence, edits/revisions, rejection,
revocations, results and unknown adapter reservations. Windows junction refusal,
WAL data, locks, partial failure, malformed fences and cross-thread/process lock
contention are covered. No real runtime, email, credential or source originals
were opened; no live inference, cloud transfer, schedules/services or release.

GitHub still reports approved private ZackHanson/scrubbed-workspace, default main,
zero Actions workflows/hooks/deployments. Main protection lookup returns 403;
no settings were changed and no protection enforcement is claimed. Source draft
PR targets feature/desktop-workflow-integration; publication and exact clean/pushed
remote head are verified at handoff. The primary owns integration and combined
checks. No independent merge or main push is authorized.
