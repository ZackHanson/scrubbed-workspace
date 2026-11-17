# Set up your own scrubbed workspace

Give this file and an approved copy of the source code to the model helping you.
It is a setup and handoff playbook for a separate user's installation. It does
not require the original owner's accounts, machine paths, T3, or agent services.

This edition describes source baseline
`466de50` (November 17, 2026): a Windows-first local email scrubber and desktop
reviewer. Verify the supplied revision before applying these instructions to
newer code. Automatic routing, Claude delivery, replies and background operation
are not part of this baseline.

## Copy this prompt to your assisting model

> Help me install my own Scrubbed Workspace using this playbook and the supplied
> source. Inspect source code and synthetic examples only. Never read real email,
> candidates, exception records, credentials or private source paths into your
> context, tools, screenshots or logs. Run synthetic setup checks, then guide me
> to run real intake and review in my own local terminal/window. Keep Ollama on
> numeric loopback with a local model and no cloud fallback. Preserve existing
> installations and work. Do not enable forwarding, Claude delivery, scheduling
> or automatic release. Report evidence for each completed check and distinguish
> untested steps. Ask only for missing setup choices that affect the result.

## 1. Establish the installation boundary

Ask for operating system, whether Python/Ollama are installed, whether approved
source is available, and Gmail versus local `.eml` intake. No mailbox address,
patient example or password is needed in chat. Default to native Windows with
Python 3.13, Tkinter and Ollama on the same computer.

Use a private, owner-approved workstation and local storage outside OneDrive,
Dropbox, shared drives and folders indexed or uploaded by other AI tools. Confirm
appropriate encryption, access controls and organizational permission before real
mail is used. A separate folder or mailbox alone does not de-identify anything.

Keep these areas separate:

| Area | Contents | Assisting cloud model access |
| --- | --- | --- |
| Source folder | Python, tests, launchers, documentation | Source and built-in synthetic fixtures only |
| Original mail | Mailbox or private `.eml` exports | Never |
| Local review store | Candidates, exception references, decisions, run receipt | Never inspect message-bearing records |
| Any future cloud workspace | Content released through a separately established process | Not configured by this playbook |

Raw mail goes only to the local application and local Ollama for processing.
Gmail intake also uses Google's mail service; local inference does not make the
whole workflow offline. Keep bodies, subjects, headers, attachments, filenames,
private paths and identifying routing details out of Git, chat, screenshots,
terminal capture and cloud logging. Treat candidates as potentially sensitive
even after they pass model checks.

## 2. Obtain an approved source bundle

The reference repository is private. Its existence is not permission to share it.
The owner must supply authorized repository access or a source-only bundle through
an approved channel. Do not copy their runtime store, credentials, mail or machine
configuration. If source is unavailable, stop at that dependency; this document
does not contain the implementation.

For the recipient's installation, choose one source folder, such as
`$HOME\Projects\scrubbed-workspace`. Reuse an existing folder after inspecting its
source state; do not overwrite it or create replacement clones to bypass access
errors. If authorized repository access is used, clone the supplied URL there
and check out the owner's specified revision. Record `git rev-parse HEAD`.
For a bundle, obtain its revision and checksum from the supplier and verify it.

Required application and verification files:

```text
scrubber.py          holds.py            review.py
triage.py            synthetic_check.py
test_scrubber.py     test_holds.py       test_review.py
Run Gmail Scrubber.cmd                  Run Local Review.cmd
.gitignore          README.md           assets/icon.svg
```

Read the supplied project guidance for source facts. Original-owner paths,
account identities, backup destinations and coordination threads are historical
context, not instructions to configure the recipient's machine. Do not install
the owner's global AGENTS, Git identity, Switchboard or credentials. Use the
recipient's approved source-control policy if making changes; never publish
private runtime files. Ignore rules are not a complete privacy check.

## 3. Install and verify the local runtime

Install Python 3.13 with Tkinter from [Python for Windows](https://www.python.org/downloads/windows/)
and Ollama from [Ollama for Windows](https://docs.ollama.com/windows).
Use official installers under the recipient's installation policy. This source
uses only Python's standard library; there is no pip requirements file.

In PowerShell, from the source folder:

```powershell
python --version
python -c "import tkinter; print('Tkinter available')"
ollama --version
```

Ensure `python` resolves to Python 3.13. The `.cmd` launchers use that command too;
having only `py -3.13` available does not make those launchers work automatically.
Do not change a shared machine's default Python without considering other users.

Configure the Ollama server for this installation with these user environment
variables, then quit and restart Ollama so it inherits them:

```text
OLLAMA_HOST=127.0.0.1:11434
OLLAMA_NO_CLOUD=1
```

Preserve and record previous values locally if changing an existing installation.
Do not restart a server in use by someone else without arranging a handoff.
Ollama documents these controls and the required restart in its
[local FAQ](https://docs.ollama.com/faq). Do not use `0.0.0.0`, a LAN endpoint,
tunnel or public proxy. This application also fixes its requests to
`http://127.0.0.1:11434`, bypasses environment proxies, rejects HTTP redirects and
rejects model metadata that advertises a remote model.

Start the installed Ollama application. If using the CLI server instead, run
`ollama serve` in a separate local terminal with those environment variables;
do not start a second server over an existing listener. Download the exact model:

```powershell
ollama pull qwen3.5:9b-q4_K_M
ollama list
python scrubber.py check
Get-NetTCPConnection -LocalPort 11434 -State Listen |
    Select-Object LocalAddress,LocalPort
```

Expected check message: `Local model ready: qwen3.5:9b-q4_K_M`. Confirm the server
listens on `127.0.0.1`, not a wildcard or LAN address. Reachability alone does not
prove that boundary. The pull needs Internet access for model weights; do it
before using real mail. Do not silently substitute another model if the tag is
unavailable. Model changes require source review and fresh synthetic evaluation.

Use synthetic inference to establish whether the machine has enough memory and
acceptable speed. The application requests a 32,768-token context and allows
240 seconds per model API request. No hardware performance is promised here.

## 4. Verify with synthetic data before using mail

Run these commands in sequence and stop on failures:

```powershell
python -m unittest -v
python synthetic_check.py
python review.py --demo
```

- Unit tests must pass. This baseline has 51 deterministic tests with mocked
  inference/intake and temporary synthetic stores.
- The real-model synthetic batch must exit successfully: three candidates, two
  blocked inputs, clinical yield 2/2, blocked auditor probes, and verified local
  review/edit/rejection persistence. It uses a fake inbox, not real Gmail, and
  removes its temporary output. Allow several minutes for local inference.
- In the isolated demo, exercise Open exceptions, inert original preview, draft
  checking/retry, Candidates, saved edits as pending, local review and rejection.
  Use fake examples only for assisting-model UI inspection. Close the demo when
  done. Do not mistake the real queue for the demo.

`python synthetic_check.py --diagnose` prints only built-in synthetic model
results and can help diagnose failures. Do not adapt diagnostic printing to real
mail. A blocked synthetic clinical example is a failed usefulness check, not a
reason to remove an uncertainty or identifier gate. Passing this small suite is
setup evidence, not proof that every identifier will be removed.

## 5. Confirm local storage before real use

On Windows, the default store is `%LOCALAPPDATA%\ScrubbedWorkspace`, outside the
source folder. It contains random-named candidate JSON files, a `holds` subfolder
and `run-status.json`. No original-message copies or passwords are saved by the
application. Exception records do contain private source references: absolute
`.eml` paths plus hashes, or Gmail account hashes and inbox UID/UIDVALIDITY.

Keep the entire store private. Do not upload it for support or point an assisting
model at it. The code does not install encryption, access restrictions, backups
or automatic retention/deletion. The owner must establish those under their
local policy. Source backup does not back up this store or original messages.

For another local state root, the owner may set `LOCALAPPDATA` in a dedicated
launch process before starting Python. The application appends `ScrubbedWorkspace`.
Avoid changing it globally: that affects other software. Keep intake and reviewer
on the same root, and do not move existing records without a deliberate migration.

## 6. Owner-only first intake

The assisting model finishes its automated work here. The owner runs real intake
in a local terminal that is not captured by the model. Do not enter credentials
through an agent tool or display real queues through screen-sharing automation.

Start with one message, using either route below.

### Local export

Export a message as `.eml` using the mail client's local export feature into an
approved private folder outside the repository. Run locally, replacing the
illustrative path without sending the real path back to the model:

```powershell
python scrubber.py files "C:\PrivateMail\message.eml"
```

Keep that original available if exception retry is needed. Changed, missing or
moved sources fail the source-reference checks.

### Gmail

This version uses Gmail IMAP and an app password; OAuth is not implemented.
App passwords require 2-Step Verification and may be unavailable under account
or organization restrictions. Follow [Google's app-password instructions](https://support.google.com/accounts/answer/185833)
locally. Do not weaken account controls to make this prototype work; use local
exports if the method is unavailable.

```powershell
python scrubber.py gmail --limit 1
```

Enter the address and app password only in the local terminal prompts. Never
use the normal Google password or put credentials in command arguments, files or
chat. The application does not save the password. The limit can be 1 through 20;
the Gmail launcher defaults to 5. Intake selects unread inbox messages, opens
the inbox read-only and fetches with BODY.PEEK. It does not mark them read.
Repeated runs can produce repeated candidates; this is not a continuous or
exactly-once mailbox processor.

## 7. Owner-only review and routine use

Run `python review.py` or double-click **Run Local Review.cmd** locally. Opening
the real reviewer displays saved local records; it does not itself call Gmail
or Ollama. The owner, not the assisting cloud model, inspects real content.

In **Open exceptions**, use the displayed reason and suggested action. Original
preview is inert text; attachments are omitted and HTML resources are not loaded.
Pattern highlights do not identify every private detail. Retry requires the
fixed local model; Gmail source retrieval also requires local sign-in again.
**Check edited draft** validates a generalized draft before saving it. A passed
retry/draft creates a pending candidate and resolves the exception. Dismissal
records a local decision and retains records.

In **Candidates**, inspect usefulness, residual identifiers and identifying
combinations, including quoted history. Save edits as pending before recording
local review. Use the confirmation checkbox to mark reviewed locally, or reject
locally. Edits reset review status. These are local workflow markers; none releases
content or certifies de-identification. No export/send action exists.

Attachments, HTML-only messages, unsupported MIME, oversized/context-limit input,
model failures, malformed output, uncertain redaction and suspected identifiers
are blocked. Plain text in a multipart message may be processed while its HTML
alternative is omitted. Do not bypass blocking by forwarding the original to an
assisting model. Handle exceptions locally or in the mail client.

## 8. Troubleshooting and stopping safely

| Symptom | Action |
| --- | --- |
| `python` missing/wrong version or Tkinter missing | Repair the approved Python installation/PATH, reopen the terminal, rerun runtime checks. |
| Local-model check fails | Check Ollama is running locally, exact model tag is installed, server has inherited local-only settings and listener is loopback. No remote fallback. |
| Synthetic inference times out or runs out of memory | Close unrelated local workloads if appropriate; inspect hardware capacity using synthetic input. Do not disable gates or use real mail for diagnosis. |
| Gmail authentication fails | Owner checks app-password/account/IMAP policy locally; use `.eml` if unavailable. Do not send credentials or raw errors to the model. |
| No messages selected | Check for unread inbox mail locally. Zero unread is a valid completed run. |
| Held original unavailable/changed | Owner checks the original locally; re-export/re-import or handle it manually. Never edit hashes/UIDs to bypass identity checks. |
| Review save conflict | Reload and reconcile locally; do not overwrite another window's changes. |
| Stale `.review-lock` after crash | Close all review windows, verify no writer remains, then owner removes only the stale lock locally. Retain the candidate. |

For support, relay only versions, synthetic failures, counts and fixed error
categories. The application has a content-free run receipt, but do not give the
model directory-wide access to collect it. Stop a foreground run with Ctrl+C;
close the reviewer normally. This baseline installs no scheduler. Preserve data
on stop/uninstall; deletion and retention are deliberate owner decisions.

## 9. Completion report and future cloud use

The assisting model should hand back a short report containing source revision,
Python/Ollama versions, exact model tag, loopback verification, unit-test result,
synthetic result, demo result and any pending dependency. Record only that the
owner knows where local storage is; omit private paths and account identifiers.
Mark real intake/review as owner-run or untested, not observed by the model.

The intended future workflow is exception-focused handling with a separate cloud
assistant. This baseline still requires local review of routine candidates.
Do not create a destination mailbox, API integration, forwarding rule, reply sender
or background job as an implied setup step. Those require separate implementation,
synthetic testing, owner authorization and a defined release process that keeps
identity/routing local and sends only permitted content.

For clinical use, local LLM redaction and a second pass through the same model do
not establish regulatory compliance. HHS describes Safe Harbor and Expert
Determination as de-identification methods; the organization must establish the
applicable process before any release. See [HHS de-identification guidance](https://www.hhs.gov/hipaa/for-professionals/special-topics/de-identification/index.html).
Until that process and a tested delivery boundary exist, setup ends at local
scrubbing and local review.
