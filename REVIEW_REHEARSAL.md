# Offline exception rehearsal

From the repository root, run one command:

```powershell
python review.py --demo
```

This creates three invented managed exceptions and one standalone candidate in a
temporary directory. The entire session uses mocked model responses and blocks
socket connections; it does not contact Ollama or Gmail. Closing the main window
removes the demo state. Restarting creates a fresh rehearsal. Normal launch without
`--demo` retains its existing local-model behavior and real private storage.

The mock returns the constant subject `Workflow` and body
`Explain general follow-up workflow.` for every successful check. This demonstrates
UI/state transitions, not meaning preservation or privacy performance. Enter
`DEMO_FAIL` in the draft subject to inject a verifier failure. This marker has
special meaning only during `--demo`.

## Owner walkthrough

Rows have random IDs; select by reason. The selected reason and next action appear
in full above the editor even when the narrow list clips a row's label.

1. Select **Local verifier flagged possible identifiers**. Choose **View original
   locally**. The inert text includes invented Mara Velquist, DOB and phone. DOB
   and phone are highlighted; the name is not. Close the preview. No attachment,
   HTML resource or link is opened.
2. Set the draft subject to `DEMO_FAIL` and body to `Explain a general workflow.`.
   Choose **Check edited draft**. The hold remains open; the editor retains both
   fields and explains that the draft has not been saved. Choose **Reload selected /
   list**, decline discard, and confirm the draft remains. Change the subject to
   `General workflow`, check again, and confirm a resolved hold plus one pending
   candidate in **Candidates**. The mock deliberately returns its fixed text.
3. Select the **Local model could not finish** open exception. **Retry original**
   simulates model recovery, retaining the managed ticket and closing its hold.
   Repeated clicks while working are disabled; completed work is not offered for
   retry. No model installation or service is needed.
4. Select **Attachment needs separate handling**, preview its text if desired,
   then **Dismiss exception** and confirm. It moves to **Closed exceptions**;
   its original remains until the temporary session ends. Attachments stay inert.
5. In **Candidates**, select the initial standalone candidate, edit its body and
   **Save edits as pending**. Check the review checkbox and **Mark reviewed locally**.
   Edit again: the checkbox clears; save returns it to pending. **Reject locally**
   retains the record with rejected status. The summary explicitly includes rejected
   candidates. Local review never authorizes delivery.
6. For a managed candidate produced by steps 2/3, edit/save it. Its evidence is
   withdrawn and an open **Edited candidate needs local checks** hold appears.
   Check a new draft there, or reject the saved candidate to dismiss that hold.

Reload asks before discarding unsaved work. Accepting discard is intentional data
loss for the in-memory draft; reload then loads the selected current record if it
is still in this view. Failed saves/conflicts keep the editor text. Production
uncertainty says **Do not retry uncertain work** and requires local receipt
reconciliation; the desktop does not provide a reset or bypass button.

## Agent observations and reproducible checks

Assessed the current build based on `cde70a09a391f5e205d5ba84e14448b967e82c3c`,
against the acceptance scenarios read from PR #1 head
`296cfbd3c967f434e85119b13657eb855cdba226`, rather than assuming its old gaps remain.

`python verify_synthetic.py` passes **220 tests** with temporary LOCALAPPDATA and
socket connections blocked (215 inherited, five new). The offline managed-window
test covers all three held reasons, worker preview, injected failure preserving
draft text, successful correction, original retry, dismissal and pending status.
New tests also cover conflicting-window save text retention, reload cancellation
and current-version loading, missing selected candidates, changed hold guidance,
and an uncertain worker preserving the draft with no-retry instructions. Existing
managed tests cover actual uncertainty fencing, source changes, concurrent edits,
rejected work, duplicate retry and interrupted publication/recovery. All use invented
inputs and temporary state. No actual queue was inspected.

Native computer-use inspection on Windows confirmed the main layout, all three
reason rows, expanded model/identifier guidance, successful mocked original retry
(3 open/0 closed/1 candidate became 2 open/1 closed/2 candidates), and inert original
preview with DOB/phone highlights. Both preview and main window were closed and
the launched process exited. Other flows are hidden Tk automation, not claimed as
manual visual coverage. Final wording changes after that inspection are covered by
Tk assertions, not a second visual pass.

Fixes from this rehearsal: offline repeatability of `--demo`, accurate demo model
guidance, selected-record reload after conflicts, explicit closed status, failed
check next actions/draft retention, and a summary that includes rejected records.

Owner-only judgments remain pending: unaided usability, useful meaning, exception
rarity, the ten-item routine comparison, owner handling time and time savings. Agent
automation establishes none of those. This is not a live-model qualification,
provider pilot, privacy certification or release approval.

## Integration

Integrate the task branch onto `feature/desktop-workflow-integration`; the draft PR
targets that branch. Changes are confined to review UI/tests, this focused guide
and the handbook Current work entry. No provider, pilot, recovery, core operations
or routing module changes are required. The primary owner handles combined-head
verification and stack integration; do not merge this PR independently.
