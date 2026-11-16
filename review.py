"""Local exception review with explicit Gmail reads and local checks; no sending/export."""
import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import queue
import tempfile
import threading
import uuid

from scrubber import MAX_BYTES, PATTERNS, STATE
from holds import HoldError, HoldStore, REASONS, file_source, preview, read_source
import triage


STATUSES = {'needs_local_review', 'reviewed_locally', 'rejected_locally'}
LABELS = {'needs_local_review': 'Needs local review',
          'reviewed_locally': 'Reviewed locally', 'rejected_locally': 'Rejected locally'}


class ReviewError(Exception):
    """Fixed user-facing error text; never include candidate content."""


@dataclass
class Snapshot:
    ticket: str
    record: dict
    digest: str


class CandidateStore:
    def __init__(self, folder):
        self.folder = Path(folder)

    def path(self, ticket):
        if not re.fullmatch(r'[0-9a-f]{32}', ticket):
            raise ReviewError('Invalid candidate ID.')
        path = self.folder / (ticket + '.json')
        if path.is_symlink():
            raise ReviewError('Linked candidate files cannot be reviewed.')
        return path

    def tickets(self):
        return sorted(path.stem for path in self.folder.glob('*.json')
                      if re.fullmatch(r'[0-9a-f]{32}', path.stem)
                      and path.is_file() and not path.is_symlink())

    @staticmethod
    def validate(record):
        if (not isinstance(record, dict)
                or set(record) != {'status', 'subject', 'body'}
                or not all(type(value) is str for value in record.values())
                or record['status'] not in STATUSES
                or not record['body'].strip()):
            raise ReviewError('Invalid candidate format. File was left unchanged.')
        if len(json.dumps(record).encode('utf-8')) > MAX_BYTES:
            raise ReviewError('Candidate is too large. File was left unchanged.')

    def load(self, ticket):
        try:
            with self.path(ticket).open('rb') as source:
                raw = source.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ReviewError('Candidate is too large.')
            record = json.loads(raw)
            self.validate(record)
            return Snapshot(ticket, record, hashlib.sha256(raw).hexdigest())
        except (OSError, ValueError):
            raise ReviewError('Candidate could not be read. File was left unchanged.') from None

    def save(self, snapshot, subject, body, status):
        record = {'status': status, 'subject': subject, 'body': body}
        self.validate(record)
        changed = any(record[key] != snapshot.record[key] for key in ('subject', 'body'))
        if changed and status != 'needs_local_review':
            raise ReviewError('Save edits first, then review the saved version.')
        if status == 'reviewed_locally' and any(
                re.search(pattern, value) for pattern in PATTERNS for value in (subject, body)):
            raise ReviewError('A possible identifier remains. Edit it before recording review.')
        path = self.path(snapshot.ticket)
        lock_path = path.with_suffix('.review-lock')
        temporary = None
        try:
            # Serialize review writers, then detect edits since this window loaded.
            lock = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise ReviewError('Another review may be saving this candidate. Try again later.') from None
        except OSError:
            raise ReviewError('Cannot save in the review folder. File was left unchanged.') from None
        try:
            os.close(lock)
            if self.load(snapshot.ticket).digest != snapshot.digest:
                raise ReviewError('Candidate changed in another window. Reload before saving.')
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                             dir=self.folder, suffix='.tmp', delete=False) as output:
                temporary = Path(output.name)
                json.dump(record, output, indent=2)
                output.flush()
                os.fsync(output.fileno())
            temporary.replace(path)
            return self.load(snapshot.ticket)
        except OSError:
            raise ReviewError('Could not save candidate. Reload to check its current state.') from None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            lock_path.unlink(missing_ok=True)


class ReviewWindow:
    def __init__(self, root, store, demo=False):
        import tkinter as tk
        from tkinter import messagebox, ttk
        from tkinter.scrolledtext import ScrolledText

        self.root, self.store = root, store
        self.holds = HoldStore(store.folder)
        self.messagebox = messagebox
        self.snapshot = None
        self.hold = None
        self.busy = False
        self.results = queue.Queue()
        self.active_view = 'Open exceptions'
        self.ids = []
        root.title('Scrubbed Workspace — ' + ('SYNTHETIC EXCEPTION DEMO' if demo else 'Exception review'))
        root.geometry('1120x790')
        root.minsize(1000, 700)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(1, weight=1)
        heading = ttk.Frame(root, padding=12)
        heading.grid(row=0, column=0, sticky='ew')
        ttk.Label(heading, text='Message exceptions', font=('Segoe UI', 16, 'bold')).pack(anchor='w')
        ttk.Label(heading, text=('Synthetic demo: temporary examples only.' if demo else
                                'Candidates may still contain identifying information.')).pack(anchor='w', pady=(6, 0))
        ttk.Label(heading, text='Local review records your progress. It does not certify de-identification or authorize uploading.').pack(anchor='w')
        self.summary = tk.StringVar()
        ttk.Label(heading, textvariable=self.summary).pack(anchor='w', pady=(6, 0))

        pane = ttk.Panedwindow(root, orient='horizontal')
        pane.grid(row=1, column=0, sticky='nsew', padx=12)
        sidebar = ttk.Frame(pane, padding=(0, 0, 12, 0))
        sidebar.rowconfigure(2, weight=1)
        sidebar.columnconfigure(0, weight=1)
        self.view = tk.StringVar(value=self.active_view)
        self.filter = ttk.Combobox(sidebar, textvariable=self.view, state='readonly',
                                   values=('Open exceptions', 'Candidates', 'Closed exceptions'))
        self.filter.grid(row=0, column=0, sticky='ew', pady=(0, 8))
        self.filter.bind('<<ComboboxSelected>>', self.change_view)
        ttk.Label(sidebar, text='Select a message').grid(row=1, column=0, sticky='w', pady=(0, 6))
        self.queue = tk.Listbox(sidebar, width=31, exportselection=False)
        self.queue.grid(row=2, column=0, sticky='nsew')
        scroll = ttk.Scrollbar(sidebar, orient='vertical', command=self.queue.yview)
        scroll.grid(row=2, column=1, sticky='ns')
        self.queue.configure(yscrollcommand=scroll.set)
        self.queue.bind('<<ListboxSelect>>', self.select)
        self.reload_button = ttk.Button(sidebar, text='Reload list', command=self.reload)
        self.reload_button.grid(row=3, column=0, sticky='ew', pady=8)
        pane.add(sidebar, weight=1)

        editor = ttk.Frame(pane)
        editor.columnconfigure(0, weight=1)
        editor.rowconfigure(5, weight=1)
        self.reason = tk.StringVar(value='Select an exception to see why it stopped.')
        ttk.Label(editor, textvariable=self.reason, wraplength=720,
                  font=('Segoe UI', 11, 'bold')).grid(row=0, column=0, sticky='ew', pady=(0, 4))
        self.guidance = tk.StringVar(value='Automatic delivery to Claude is not enabled.')
        ttk.Label(editor, textvariable=self.guidance, wraplength=720).grid(row=1, column=0, sticky='ew', pady=(0, 10))
        ttk.Label(editor, text='Subject / edited draft subject').grid(row=2, column=0, sticky='w')
        self.subject = tk.StringVar()
        self.subject_entry = tk.Entry(editor, textvariable=self.subject)
        self.subject_entry.grid(row=3, column=0, sticky='ew', pady=(4, 10))
        ttk.Label(editor, text='Body / new generalized draft (no unchecked draft is saved)').grid(row=4, column=0, sticky='w')
        self.body = ScrolledText(editor, wrap='word', undo=True, font=('Segoe UI', 11))
        self.body.grid(row=5, column=0, sticky='nsew', pady=(4, 8))
        self.body.tag_configure('identifier', background='#ffe0a6', foreground='#522b00')
        exceptions = ttk.Frame(editor)
        exceptions.grid(row=6, column=0, sticky='ew', pady=(0, 8))
        self.exception_buttons = []
        for label, action in [('View original locally', self.view_original),
                              ('Retry original', self.retry_original),
                              ('Check edited draft', self.check_draft),
                              ('Dismiss exception', self.dismiss)]:
            button = ttk.Button(exceptions, text=label, command=action)
            button.pack(side='left', padx=(0, 6))
            self.exception_buttons.append(button)
        self.confirmed = tk.BooleanVar(value=False)
        ttk.Checkbutton(editor, text='I checked the saved subject and body for remaining identifying details.',
                        variable=self.confirmed).grid(row=7, column=0, sticky='w', pady=6)
        buttons = ttk.Frame(editor)
        buttons.grid(row=8, column=0, sticky='ew', pady=(4, 8))
        self.candidate_buttons = []
        for label, action in [('Save edits as pending', self.save_edits),
                              ('Mark reviewed locally', self.mark_reviewed),
                              ('Reject locally', self.reject)]:
            button = ttk.Button(buttons, text=label, command=action)
            button.pack(side='left', padx=(0, 8))
            self.candidate_buttons.append(button)
        pane.add(editor, weight=3)
        self.notice = tk.StringVar(value='Select a candidate to begin.')
        ttk.Label(root, textvariable=self.notice, padding=12, wraplength=950).grid(row=2, column=0, sticky='ew')
        self.subject.trace_add('write', self.edited)
        self.body.bind('<<Modified>>', self.edited)
        self.refresh()
        self.controls()

    def edited(self, *args):
        self.confirmed.set(False)
        self.body.edit_modified(False)
        self.highlight()

    def highlight(self):
        self.subject_entry.configure(background='#ffe0a6' if any(
            re.search(pattern, self.subject.get()) for pattern in PATTERNS) else 'white')
        self.body.tag_remove('identifier', '1.0', 'end')
        text = self.body.get('1.0', 'end-1c')
        for pattern in PATTERNS:
            for match in re.finditer(pattern, text):
                self.body.tag_add('identifier', f'1.0+{match.start()}c', f'1.0+{match.end()}c')

    def values(self):
        return self.subject.get(), self.body.get('1.0', 'end-1c')

    def dirty(self):
        if self.hold is not None:
            return any(self.values())
        return self.snapshot is not None and self.values() != (
            self.snapshot.record['subject'], self.snapshot.record['body'])

    def leave(self):
        return not self.dirty() or self.messagebox.askyesno(
            'Unsaved edits', 'Discard unsaved edits?', parent=self.root)

    def refresh(self):
        current = self.snapshot.ticket if self.snapshot else self.hold.ticket if self.hold else None
        entries = []
        unreadable = 0
        for ticket in self.holds.tickets():
            try:
                entries.append(self.holds.load(ticket))
            except HoldError:
                unreadable += 1
        open_count = sum(item.record['status'] == 'open' for item in entries)
        self.summary.set(f'{open_count} open exceptions | {len(entries) - open_count} closed | '
                         f'{len(self.store.tickets())} pending/reviewed candidates | Nothing sent to Claude'
                         + (f' | {unreadable} unreadable exception records' if unreadable else ''))
        if self.active_view == 'Candidates':
            self.ids = self.store.tickets()
            labels = self.ids
        else:
            filtered = [item for item in entries if (item.record['status'] == 'open')
                        == (self.active_view == 'Open exceptions')]
            self.ids = [item.ticket for item in filtered]
            labels = [item.ticket[:8] + ' | ' + REASONS[item.record['reason']][0]
                      for item in filtered]
        self.queue.delete(0, 'end')
        for label in labels:
            self.queue.insert('end', label)
        if current in self.ids:
            self.queue.selection_set(self.ids.index(current))
        if not self.ids:
            self.notice.set('This list is empty. New runs record exceptions; older blocked messages have no saved references.')

    def change_view(self, event=None):
        if self.busy or not self.leave():
            self.view.set(self.active_view)
            return
        self.active_view = self.view.get()
        self.show(None)
        self.refresh()

    def show(self, snapshot):
        self.hold = None
        self.snapshot = snapshot
        self.body.configure(state='normal')
        self.subject.set(snapshot.record['subject'] if snapshot else '')
        self.body.delete('1.0', 'end')
        self.body.insert('1.0', snapshot.record['body'] if snapshot else '')
        self.body.edit_reset()
        self.body.edit_modified(False)
        self.confirmed.set(False)
        self.notice.set(LABELS[snapshot.record['status']] if snapshot else 'Select a candidate to begin.')
        self.reason.set('Candidate: human review remains required' if snapshot else 'Select an exception or candidate.')
        self.guidance.set('Highlighted body text matches identifier patterns; the subject is also checked when recording review.'
                          if snapshot else 'Automatic delivery to Claude is not enabled.')
        self.highlight()
        self.controls()

    def show_hold(self, hold):
        self.show(None)
        self.hold = hold
        self.reason.set(REASONS[hold.record['reason']][0])
        self.guidance.set(REASONS[hold.record['reason']][1] +
                          ' Original previews stay local. Names and other identifiers may not be highlighted.')
        self.notice.set(f"Exception {hold.ticket[:8]} is {hold.record['status']}. " +
                        ('Use View original locally, or compose a new generalized draft above.'
                         if hold.record['source'] else 'No source reference is available; locate the original yourself.'))
        self.controls()

    def controls(self):
        for button in self.candidate_buttons:
            button.configure(state='normal' if self.snapshot and not self.busy else 'disabled')
        for index, button in enumerate(self.exception_buttons):
            allowed = self.hold and self.hold.record['status'] == 'open' and not self.busy
            if index < 2:
                allowed = allowed and self.hold.record['source'] is not None
            button.configure(state='normal' if allowed else 'disabled')
        editable = not self.busy and (self.snapshot or self.hold and self.hold.record['status'] == 'open')
        self.subject_entry.configure(state='normal' if editable else 'disabled')
        self.body.configure(state='normal' if editable else 'disabled')
        self.queue.configure(state='disabled' if self.busy else 'normal')
        self.filter.configure(state='disabled' if self.busy else 'readonly')
        self.reload_button.configure(state='disabled' if self.busy else 'normal')

    def select(self, event=None):
        if self.busy:
            return
        selected = self.queue.curselection()
        if not selected:
            return
        ticket = self.ids[selected[0]]
        if self.snapshot and ticket == self.snapshot.ticket:
            return
        if self.hold and ticket == self.hold.ticket:
            return
        if not self.leave():
            self.queue.selection_clear(0, 'end')
            current = self.snapshot.ticket if self.snapshot else self.hold.ticket
            self.queue.selection_set(self.ids.index(current))
            return
        try:
            if self.active_view == 'Candidates':
                self.show(self.store.load(ticket))
            else:
                self.show_hold(self.holds.load(ticket))
        except (ReviewError, HoldError) as error:
            self.show(None)
            self.notice.set(str(error))

    def reload(self):
        if not self.busy and self.leave():
            self.show(None)
            self.refresh()

    def save(self, status):
        if self.busy:
            return
        if self.snapshot is None:
            self.notice.set('Select a candidate first.')
            return
        try:
            self.show(self.store.save(self.snapshot, *self.values(), status))
        except ReviewError as error:
            self.notice.set(str(error))

    def save_edits(self):
        self.save('needs_local_review')

    def mark_reviewed(self):
        if not self.confirmed.get():
            self.notice.set('Check the saved content, then select the review checkbox.')
            return
        self.save('reviewed_locally')

    def reject(self):
        if self.busy:
            return
        if self.snapshot is None:
            self.notice.set('Select a candidate first.')
        elif self.dirty():
            self.notice.set('Save or discard edits before rejecting the candidate.')
        elif self.messagebox.askyesno('Reject candidate',
                                     'Mark this candidate rejected locally? The file will be retained.',
                                     parent=self.root):
            self.save('rejected_locally')

    def credentials(self):
        source = self.hold.record['source']
        if source is None or source['kind'] != 'gmail':
            return (None, None)
        from tkinter import simpledialog
        address = simpledialog.askstring('Local Gmail sign-in',
                                         'Source Gmail address (used locally, never saved):', parent=self.root)
        if not address:
            return None
        password = simpledialog.askstring('Local Gmail sign-in',
                                          'Google app password (never saved):', show='*', parent=self.root)
        return (address, password) if password else None

    def start_work(self, operation, action):
        if self.busy or self.hold is None or self.hold.record['status'] != 'open':
            return
        self.busy = True
        self.controls()
        self.notice.set('Working locally. Gmail originals may require a connection; model checks may take a few minutes.')

        def run():
            try:
                self.results.put((operation, action(), None))
            except HoldError as error:
                self.results.put((operation, None, error.code))
            except Exception:
                # Never place exception payloads or traceback text in logs/UI.
                self.results.put((operation, None, 'processing_failed'))

        threading.Thread(target=run, daemon=True).start()
        self.root.after(100, self.finish_work)

    def finish_work(self):
        try:
            operation, result, error = self.results.get_nowait()
        except queue.Empty:
            self.root.after(100, self.finish_work)
            return
        self.busy = False
        self.controls()
        if error:
            self.notice.set(REASONS[error][0] + '. ' + REASONS[error][1])
        elif operation == 'preview':
            self.open_preview(result)
            self.notice.set('Original shown locally only. No attachment or HTML resource was opened.')
        else:
            ticket = self.hold.ticket
            draft = self.values()
            try:
                self.show_hold(self.holds.load(ticket))
                if not result:
                    self.subject.set(draft[0])
                    self.body.insert('1.0', draft[1])
                self.refresh()
                self.notice.set('Local checks passed. A new pending candidate is in Candidates; nothing was sent.'
                                if result else 'Still held: ' + REASONS[self.hold.record['reason']][0])
            except HoldError:
                self.notice.set('Exception changed or could not be read. Reload the list; any candidate stays pending.')

    def open_preview(self, text):
        import tkinter as tk
        from tkinter.scrolledtext import ScrolledText
        window = tk.Toplevel(self.root)
        window.title('Original — local display only')
        window.geometry('850x600')
        display = ScrolledText(window, wrap='word', font=('Segoe UI', 11))
        display.pack(fill='both', expand=True, padx=12, pady=12)
        display.insert('1.0', text)
        display.tag_configure('identifier', background='#ffe0a6', foreground='#522b00')
        for pattern in PATTERNS:
            for match in re.finditer(pattern, text):
                display.tag_add('identifier', f'1.0+{match.start()}c', f'1.0+{match.end()}c')
        display.configure(state='disabled')

    def view_original(self):
        if self.busy or self.hold is None or self.hold.record['source'] is None:
            return
        credentials = self.credentials()
        if credentials is not None:
            source = self.hold.record['source']
            self.start_work('preview', lambda: preview(read_source(source, *credentials)))

    def retry_original(self):
        if self.busy or self.hold is None or self.hold.record['source'] is None or not self.leave():
            return
        credentials = self.credentials()
        if credentials is not None:
            snapshot = self.hold
            self.start_work('retry', lambda: triage.recheck(self.store.folder, snapshot,
                                                           read_source(snapshot.record['source'], *credentials)))

    def check_draft(self):
        if self.busy or self.hold is None:
            return
        try:
            raw = triage.draft_message(*self.values())
        except HoldError as error:
            self.notice.set(str(error))
            return
        snapshot = self.hold
        self.start_work('draft', lambda: triage.recheck(self.store.folder, snapshot, raw))

    def dismiss(self):
        if self.busy or self.hold is None or self.hold.record['status'] != 'open' or not self.leave():
            return
        if self.messagebox.askyesno('Dismiss exception',
                                   'Record that you will handle or skip this message yourself? The original stays unchanged.',
                                   parent=self.root):
            try:
                self.show_hold(self.holds.update(self.hold, status='dismissed'))
                self.refresh()
            except HoldError as error:
                self.notice.set(str(error))

    def close(self):
        if self.busy:
            self.notice.set('Wait for the local operation to finish before closing.')
            return
        if self.leave():
            self.root.destroy()


def demo_store(folder):
    store = CandidateStore(folder)
    record = {'status': 'needs_local_review', 'subject': 'Synthetic workflow example',
              'body': 'Please prepare a general checklist for asthma education and inhaler technique.\n\n'
                      'This is synthetic demonstration text. You can edit, save, review or reject it.'}
    (store.folder / (uuid.uuid4().hex + '.json')).write_text(json.dumps(record), encoding='utf-8')
    return store


def demo_exceptions(folder):
    """Create originals inside the isolated demo directory, never live storage."""
    from email.message import EmailMessage
    source_folder = Path(folder) / 'synthetic-originals'
    source_folder.mkdir()
    for index, (reason, body, attachment) in enumerate([
        ('verifier_flagged', 'Synthetic patient Mara Velquist, DOB 03/14/1972. '
         'Call 202-555-0146. Please discuss hypertension follow-up.', False),
        ('attachment', 'Please review the attached synthetic file.', True),
        ('model_error', 'Please prepare a general asthma education checklist.', False),
    ]):
        mail = EmailMessage()
        mail['Subject'] = 'Synthetic local original'
        mail.set_content(body)
        if attachment:
            mail.add_attachment(b'SYNTHETIC ONLY', maintype='application', subtype='pdf', filename='synthetic.pdf')
        raw = mail.as_bytes()
        path = source_folder / f'example-{index}.eml'
        path.write_bytes(raw)
        HoldStore(folder).create(uuid.uuid4().hex, reason, file_source(path, raw))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', action='store_true', help='Use temporary synthetic examples only')
    args = parser.parse_args()
    import tkinter as tk
    with tempfile.TemporaryDirectory(prefix='scrubber-review-demo-') as temp:
        store = demo_store(temp) if args.demo else CandidateStore(STATE)
        if args.demo:
            demo_exceptions(temp)
        root = tk.Tk()
        ReviewWindow(root, store, demo=args.demo)
        root.mainloop()


if __name__ == '__main__':
    main()
