<img src="assets/icon.svg" width="64" height="64" alt="">

# scrubbed-workspace

Local email redaction with Ollama and a desktop exception reviewer. Candidates
remain pending local review; automatic routing and Claude delivery are not enabled.

Requires Python 3.13 and the installed local `qwen3.5:9b-q4_K_M` model.

```powershell
python scrubber.py check
python -m unittest -v
python synthetic_check.py
python scrubber.py gmail --limit 5
```

`synthetic_check.py` uses a fake five-message Gmail inbox and the real local Qwen
model. It never connects to Gmail or reads existing candidates. It checks batch
completion, candidate storage, known synthetic identifiers, useful topic retention,
and attachment/HTML blocking. It also checks local review persistence and verifies
that the auditor blocks separate synthetic names/instructions, written dates and
ages over 89. Outputs use temporary storage and are removed after the test.
Clinical candidate yield is reported separately; this fixture set requires both
clinical examples to produce candidates so usefulness regressions fail the run.
Use `python synthetic_check.py --diagnose` to print model results for these built-in
synthetic fixtures only. This small fixture set is not a privacy guarantee.

To try the exception reviewer with temporary synthetic originals and held messages:

```powershell
python review.py --demo
```

To review actual messages locally, double-click **Run Local Review.cmd** or run
`python review.py`. It starts in **Open exceptions** and shows a fixed hold reason
and suggested next action for each message. Choose an exception, then:

- **View original locally** opens an inert text preview in a separate local
  window. Attachments are omitted; HTML is shown as literal text with no remote
  resources loaded. Identifier patterns are highlighted, but names and other
  identifiers may not be highlighted.
- **Retry original** fetches the same original and runs all local model gates again.
- **Check edited draft** checks the generalized subject/body you compose in the
  editor. Unchecked drafts stay in memory only. Failed checks retain your draft
  in the window and leave the exception open. Passed checks create a new pending
  candidate and close the exception; they never release content to Claude.
- **Dismiss exception** records that you will handle or skip it yourself. The
  original and exception record are retained. The same source is not added to the
  queue again on a later sequential import.

Use the list selector to switch to **Candidates** or **Closed exceptions**.
For candidates, **Save edits as pending** stores changes and resets review. After
checking the saved version, select the review checkbox and choose **Mark reviewed
locally**, or **Reject locally** to retain it as rejected. All statuses remain
local workflow records; none certifies de-identification or enables uploading,
forwarding or export. No message content is written to terminal logs.

The window opens and displays saved records without needing Ollama or Gmail.
Retrying/checking drafts requires the local Ollama model. Reopening a Gmail
original requires signing in again through native local dialogs with the source
address and app password; the password is not saved. Gmail is opened read-only
and messages use BODY.PEEK, so viewing/retrying does not mark them read.

Only new scrubber runs create exception records. Historical blocked messages
cannot be reconstructed from old count-only receipts. If a source moved out of
the inbox, changed, or disappeared, handle it in your mail client or re-import it.

The review window prevents overwriting changes saved in another review window.
Use **Reload list** after a conflict; unsaved edits require a discard
confirmation. Saves replace files atomically. A process crash during a save may
leave a `.review-lock` file beside its candidate; close all review windows before
removing that lock locally and reopening the reviewer. The candidate itself is
retained.

Or double-click **Run Gmail Scrubber.cmd**. Enter your source Gmail address and a
Google **app password** in that local terminal. The password is hidden and is not
saved. Do not use your normal Google password. Availability depends on your Google
account and Workspace administrator; see [Google's setup instructions](https://knowledge.workspace.google.com/admin/sync/set-up-gmail-with-a-third-party-email-client).
If app passwords are unavailable, use local `.eml` exports for now:
`python scrubber.py files "C:\local-private-folder\message.eml"`.

The Gmail command reads up to five unread inbox messages without marking them read.
It also saves `run-status.json` in the local review folder, containing only run
stage, counts, sign-in success and fixed error categories. This lets us diagnose
a run after its terminal closes without reading email content or credentials.
Running it again can process the same messages. Headers are discarded; plain-text
bodies and subjects pass through pattern redaction, Qwen generalization/redaction
and Qwen review. Identifying profiles and irrelevant instruction attacks are
removed while useful clinical/work requests are retained. This generalization may
omit context; review candidates for usefulness as well as identifying details.
Messages with attachments or unsupported content are blocked. No attachments or
HTML resources are opened or downloaded. Only the local Ollama endpoint receives text.

Candidates are stored under `%LOCALAPPDATA%\ScrubbedWorkspace` with random names,
never under the repository. Inspect those files locally; they may still contain
PHI. The command prints only random IDs and fixed review/block categories. Original
message copies are not stored by this program. The private `holds` subfolder now
stores fixed reason/status records with references: an absolute local `.eml` path
and content hash, or a Gmail account hash, inbox UID and UIDVALIDITY. Paths can
themselves contain sensitive information; keep the whole review folder private.
These references never become candidate content or terminal logs. File hashes,
account checks and UIDVALIDITY checks prevent silently substituting another source.
Use an approved encrypted workstation and local storage; retention and deletion
of candidates and exception records are currently manual.

This is a prototype, not a HIPAA compliance certification. The second pass uses
the same model and can share its mistakes. HHS describes Safe Harbor and Expert
Determination as de-identification methods; redaction by an LLM alone does not
establish either. See [HHS guidance](https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html).
Forwarding to a second account and connecting Claude remain unimplemented until
the review and de-identification requirements are established.

## Exception journey and proposed pilot acceptance

November 16 readiness assessment at base `466de50`: the desktop journey exists,
but routine messages still become pending candidates requiring local review.
The intended outcome is a useful local Claude result for routine eligible messages,
with owner attention reserved for exceptions. No automatic delivery is enabled.

Source contracts inspected through local Git (separate feature heads, **not an
integrated build**):

| Track / inspected head | Exists in that branch | Integration acceptance gap |
| --- | --- | --- |
| Intake / `f7eeaf6` | Durable tickets, source fingerprints, leases, repairable candidate publication | Reviewer retry must preserve the intake ticket; edited drafts need distinct derived identities. Initial ledger results do not reflect later edits/rejection. |
| Shadow routing / `1216b3c` | Typed HOLD/WOULD_SEND, exact content/evidence binding; execution disabled | Pipeline must supply real check/model provenance; old review markers cannot create it. Map policy holds into understandable owner exceptions. |
| Evaluation / `292cb40` | 35 invented fixtures, separate privacy/utility/refusal/schema/execution checks | Run against the combined build; mock passes do not establish real model quality. |
| Claude adapter / `266c286` | Disabled default, allowlisted subject/body, fake transport, durable submission reservation | No real client or review wiring. Caller must recheck current eligibility and persist valid results; unknown delivery has no automatic retry. |
| Actions / `16218b1` | Version-bound local results and inert proposals; provider writes disabled | Wire candidate edit/rejection invalidation and result replacement. Private source binding stays local; old proposals remain history only. |
| Operations / `8e063f0` | Bounded manual shadow runner, uncertain recovery, ledger-only backup/restore | Intake/router adapters and coordinated state recovery remain separate work. This runner cannot deliver to Claude. |

### Acceptance scenarios

Use temporary synthetic state and fake transports first. The following are required
integrated observations, not claims that the current baseline passes them all.

| Synthetic scenario | Owner-visible outcome and pass criterion |
| --- | --- |
| Routine: "Prepare an asthma education and inhaler technique checklist" (`utility-01`) | One current result retains asthma, inhaler and technique; no compulsory review click in the eventual routine flow. Shadow rehearsal shows WOULD_SEND and zero outbound calls. |
| Held: demo attachment, possible identifier, model failure | Open exceptions shows a specific reason and safe next action. Attachment handling stays in the mail client; model failure permits local retry; identifier uncertainty permits a generalized draft. Every held item is accounted for, with no delivery. |
| Correction/retry: demo asthma request after model recovery | Failed check keeps the draft and open hold. Successful full check creates one current pending candidate and resolves the hold; it does not itself authorize release. Two retries/restarts cannot create duplicate current work. |
| Dismissal: demo attachment handled elsewhere | Confirmation moves it to Closed exceptions, preserves original/history, and a repeated import does not reopen or dispatch it. |
| Stale work: edit/reject while checks or fake delivery are in flight; replace a result | Old evidence, file version, result and proposal cannot become current. Rejection revokes future use. Two windows cannot overwrite one another. Recheck freshness at commit/capture, not only when work starts. |
| Inaccessible original: delete synthetic file, change bytes, wrong fake account or mailbox epoch | Explain unavailable/changed source without substituting another message. Keep exception open; offer owner mail-client handling or explicit re-import. No release from a stale reference. |
| Recovery: fail a save, restart after a claim, fake transport timeout, restore older state | Retain saved work and history; reconcile duplicate/uncertain work before continuing. Unknown delivery never auto-retries. Restore stays inactive until local receipts/mappings are reconciled; ledger-only backup is not full recovery. |
| Useful meaning: `utility-03` bleeding warning/urgent-help intent; `utility-04` do-not-stop constraint; `context-01` rare identifying context | Preserve requested meaning and negation, remove identifying context, introduce no unsupported advice. Owner judges semantics locally; lexical fixture checks alone cannot establish this. These are evaluation cases, outside the initial remote pilot. |

Observed here: Python 3.13.15 ran all **51 baseline tests successfully**, with
`socket.socket.connect` blocked and LOCALAPPDATA redirected to temporary storage.
`test_review` exercises Tkinter with demo stores: three open holds, displayed reasons,
worker preview, failed-draft preservation, successful pending-candidate creation,
dismissal and discard cancellation. `test_holds` covers changed originals, wrong
account/epoch, read-only PEEK, stale decisions and retry failure. Candidate tests
cover edits resetting review, conflicting windows, locks and failed atomic saves.
No manual visual inspection, real queue access, live Qwen run, feature-suite rerun
or combined-build test occurred in this assessment. Prior handbook model receipts
are historical evidence, not fresh results from this branch.

### Staged acceptance and owner decisions

1. **Integrated synthetic rehearsal:** integration owner runs the scenarios above
   and the existing 35-fixture evaluator on a named combined SHA. Require zero
   unexpected sends, identifier-canary leaks, wrong-source bindings, duplicate
   results or stale-result acceptance; all expected holds must remain contained.
   Require all 16 useful evaluator fixtures to retain their meaning groups and
   all 19 expected refusals to return their exact reason. Record mock and live
   Qwen outcomes separately; injected failures remain labeled injected.
2. **Rare-exception usability rehearsal:** owner tries `review.py --demo` and the
   integrated equivalent. Require correct reason/next action for all three demo
   holds, successful correction/retry/dismissal without assistance, and preserved
   work after a failed check/reload. In a separately declared ten-item clean
   routine synthetic batch, target zero mandatory intervention and at least nine
   useful results. Record wall-clock time and owner handling time against doing
   the same ten tasks manually; proceed only if handling time is lower. Count
   deliberate fault/identifier cases separately: their hold rate cannot estimate
   how rare real exceptions will be.
3. **Proposed first real Claude pilot, only after separate owner approval:** one
   manually initiated session, at most five predeclared, owner-checked synthetic
   nonclinical workflow requests, one request at a time, summaries/organization
   suggestions only. Use an explicitly approved provider/model/account and
   transport with bounded timeouts. Keep results local and inert; no mail intake,
   replies, provider writes, schedules or automatic retries. Require five useful
   results, zero duplicate submissions, and a local terminal receipt for every
   attempt (completed, held, refused or unknown). A timeout/unknown ends the pilot
   pending reconciliation; do not resend to achieve five successes.

Stop either rehearsal/pilot on any unexpected outbound content, identifier/routing
leak, source mismatch, stale/rejected result use, duplicate dispatch, lost exception,
unsupported action, unreconciled delivery or meaning-changing output. Pause new
submissions, retain private local receipts, handle the item locally, fix and rerun
the synthetic case before proposing another pilot. No destructive cleanup.

Owner decisions before stage 3: acceptable workload/utility and time-saving target,
provider/model/account and permitted payload, local retention/result access,
who reconciles unknown delivery, and the explicit start/stop control. A later
real-message pilot additionally needs an owner-established de-identification and
release process, eligible message classes, local privacy review and coordinated
recovery scope. Neither this plan, review markers nor correlated model passes
certify privacy/compliance or authorize real-message release.

Project state and boundaries: [AgentHandbook](AgentHandbook.md).
