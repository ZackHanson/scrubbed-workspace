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

November 17: SETUP-PLAYBOOK.md is a complete implementation/installation brief
for another user's coding model, including automatic intake, local redaction and
release policy, Claude processing, separate results/chat workspace, actions/replies,
background operation, secure enrollment and recovery. Owner clarified that the
playbook must deliver the full independent system, not reproduce this prototype.
Approved source is optional; the model is instructed to build missing components.
Includes module contracts, a target operator CLI, full acceptance tests and live
activation/handoff criteria. README links to it. These documentation changes do
not implement or activate those components on this machine.

Owner further clarified that recipient systems/models vary. The playbook now
requires hardware/OS/workload inspection, measured local-model/runtime selection
and tuning, native platform integration and a recorded installation profile.
Reference model tags and Windows/Python/Ollama settings are examples, not universal
requirements. Privacy and complete-workflow acceptance requirements remain fixed.

Applied [writing-for-agents](https://github.com/mattpocock/skills/blob/main/skills/productivity/writing-for-agents/SKILL.md)
guidance to the playbook: explicit
phase completion evidence, execution/resume rules, conditional reference lookup
and one optional prototype appendix. Kept the shareable playbook self-contained;
the external skill was read for this edit, not installed as a project dependency.

November 17 playbook execution trial: a fresh native model received only a frozen
playbook and synthetic-only setup choices, building in local agent-cache storage
without project source. Independent real-local-model checks found lost task
details, a valid routine request blocked by a narrow keyword policy and a
subject-only request ignored. Playbook now requires work-preservation checks,
unseen acceptance cases, a working vertical slice and separate accounting for
unimplemented code versus unavailable live access. Trial evidence and retest
results are recorded in PLAYBOOK-TEST-REPORT.md; no real mail/API spend, startup
job installation or production activation is authorized by this documentation test.
Qualifying targeted retest: 12 independent messages, 15 actual local-model calls,
all six required routine cases handled with retained meaning; seven configured
requests/results exercised with substituted external HTTP. A separate batch
repair passed independent discovery of 95 distinct exports over multiple polls
and restart. These validate targeted synthetic repairs, not full live setup.

Continued November 17 evaluation targeted approximately 9/10 playbook quality.
Fresh source-free execution (with disclosed mandatory startup-history exposure)
passed 43 self-tests and independent routine/fidelity/fault checks using actual
local inference and fake provider HTTP. Portability and adversarial reviews drove
clearer partial evidence, source rebinding, account renewal, configuration,
profiles/stops, dirty installed identity, budget settlement and scoped context
contracts. Clean-context local-model reading passed 34 final decision checks.
PLAYBOOK-TEST-REPORT.md records a conservative 9.1/10 instruction-quality judgment;
this does not qualify live deployments or imply new runtime features are installed.

Owner clarified that SETUP-PLAYBOOK.md must address the setup model directly.
Replaced the human handoff preface and copyable prompt with an executable task,
explicit setup/user/local-model/Claude roles and direct implementation commands.
Kept the fourteen phases, privacy rules, adaptive model selection and completion
checks. README now points to the file as the model's task instructions.

Owner further clarified the starting point: assume no required software or models
are installed. The playbook now requires OS-native prerequisite discovery and
bootstrap, dependency-ordered installation, runtime and weight downloads before
evaluation, new-process path checks and a fresh-machine installer/test path.
Existing compatible installs can be reused only after verification. No software,
models or services were installed on this machine for this documentation change.

Added a short human Start here section to README with four steps and a pasteable
prompt for Claude or another coding agent. It supplies the model-directed playbook,
assumes no prerequisites, asks for stepwise help with human actions and keeps
private mail/credentials out of chat. Existing prototype instructions remain below.

README now contains only the human setup steps, pasteable prompt, a short prototype
status note and reference links. Existing prototype commands, review behavior and
privacy details moved unchanged to PROTOTYPE.md as product usage documentation.

README startup now explicitly creates a dedicated local project folder, opens it
in the coding agent, saves the playbook there and starts the project chat. The
prompt names that project folder as the build location; later setup resumes reuse
it. Local tool access remains required rather than implied by a chat project.

Clarified the folder's location in README: create it on the user's computer with
File Explorer on Windows, using the example user-profile Projects path, then
select that exact local folder in the coding agent. Added Mac/Linux home-folder
example and distinguished folder selection from naming a chat project.

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
