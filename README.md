<img src="assets/icon.svg" width="64" height="64" alt="">

# scrubbed-workspace

Local email redaction with Ollama and a desktop exception reviewer. Candidates
remain pending local review; automatic routing and Claude delivery are not enabled.

Requires Python 3.13 and the installed local `qwen3.5:9b-q4_K_M` model.

To have another coding model build and install a complete independent system,
use the [full-system playbook](SETUP-PLAYBOOK.md). It covers automatic intake,
local scrubbing and routing, Claude processing, a separate results workspace,
actions/replies, background operation and recovery, including components beyond
this prototype and a copyable implementation prompt. The setup model must inspect
each recipient's system and select/test suitable local models, runtimes and settings;
the prototype's Windows/Python/Ollama choices are reference details.

Observed trial results and remaining validation gaps are recorded in the
[playbook execution test report](PLAYBOOK-TEST-REPORT.md).

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

Project state and boundaries: [AgentHandbook](AgentHandbook.md).
