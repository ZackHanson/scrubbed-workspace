"""Explicit local private snapshots. Originals and credentials are never copied.

Runtime integration must use recovery_guard.active_state for coherent snapshots.
No CLI defaults, cloud transfer, schedule, encryption or provider reconciliation.
"""
from contextlib import ExitStack, closing
from functools import wraps
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3

from operations import instance_lock
from recovery_guard import (RecoveryError, _state, _write_state, require_active,
                            safe_path, state_lock)


DATABASES = {'intake/ledger.sqlite3', 'workflow.sqlite3', 'actions.sqlite3',
             'operations/operations.sqlite3'}
DIRECTORIES = {'intake', 'holds', 'routing', 'operations', 'review-actions',
               '.recovery', '.recovery-lock', 'auxiliary'}
HEX = r'[0-9a-f]{32}'


def _fixed_errors(function):
    @wraps(function)
    def invoke(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (OSError, sqlite3.Error):
            raise RecoveryError('recovery_io_failed') from None
    return invoke


def _complete(files):
    if 'workflow.sqlite3' in files and not {'intake/ledger.sqlite3', 'actions.sqlite3'} <= files.keys():
        raise RecoveryError('missing_workflow_store')


def _allowed(name):
    return (name in DATABASES or name == 'run-status.json'
            or re.fullmatch(HEX + r'\.json', name) is not None
            or re.fullmatch('holds/' + HEX + r'\.json', name) is not None
            or re.fullmatch('routing/' + HEX + r'-[0-9a-f]{64}\.json', name) is not None
            or re.fullmatch(r'auxiliary/[a-z][a-z0-9_-]{0,31}\.sqlite3', name) is not None)


def _inventory(root, *, auxiliary=False):
    found = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        parent = Path(directory)
        for name in list(dirs):
            path = safe_path(parent / name)
            relative = path.relative_to(root).as_posix()
            if name in {'.recovery', '.recovery-lock'} and parent.name in DIRECTORIES:
                require_active(parent)
                dirs.remove(name)
                continue
            if relative not in DIRECTORIES:
                raise RecoveryError('unexpected_state_directory')
            if relative in {'.recovery', '.recovery-lock'}:
                dirs.remove(name)
        for name in files:
            path = safe_path(parent / name)
            relative = path.relative_to(root).as_posix()
            # Transient artifacts and originals are explicitly out of scope.
            if (name.endswith(('.review-lock', '.tmp', '.eml', '-wal', '-shm', '-journal'))
                    or relative in {'operations/operations.lock', 'review-actions/operations.lock'}):
                continue
            if not _allowed(relative) or (relative.startswith('auxiliary/') and not auxiliary):
                raise RecoveryError('unexpected_state_file')
            if not path.is_file():
                raise RecoveryError('unsafe_path')
            found[relative] = path
    return found


def _hash(path):
    digest = hashlib.sha256()
    size = 0
    with safe_path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
            size += len(block)
    return {'size': size, 'sha256': digest.hexdigest()}


def _integrity(path):
    try:
        with closing(sqlite3.connect(safe_path(path).as_uri() + '?mode=ro&immutable=1', uri=True)) as db:
            if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
                raise RecoveryError('invalid_database')
    except sqlite3.Error:
        raise RecoveryError('invalid_database') from None


def _fresh(path, sources):
    path = safe_path(path)
    if path.exists():
        raise RecoveryError('destination_exists')
    if not path.parent.is_dir():
        raise RecoveryError('missing_destination_parent')
    for source in sources:
        source = safe_path(source)
        if path == source or path.is_relative_to(source) or source.is_relative_to(path):
            raise RecoveryError('overlapping_paths')
    path.mkdir(mode=0o700)
    return path


@_fixed_errors
def snapshot(source, destination, *, extra_ledgers=None):
    """Copy selected private state into a NEW local directory.

    extra_ledgers maps an invented local role (e.g. adapter/pilot) to an explicit
    SQLite file. Its parent guard lock participates; no path is put in manifest.
    Partial destinations are retained and never cleaned up on failure.
    """
    root = safe_path(source)
    if not root.is_dir():
        raise RecoveryError('missing_source')
    extras = {}
    for role, path in (extra_ledgers or {}).items():
        if type(role) is not str or not re.fullmatch('[a-z][a-z0-9_-]{0,31}', role):
            raise RecoveryError('invalid_ledger_role')
        path = safe_path(path)
        if not path.is_file() or path.is_relative_to(root):
            raise RecoveryError('invalid_extra_ledger')
        extras['auxiliary/' + role + '.sqlite3'] = path
    target = safe_path(destination)
    # Validate overlap before taking any lock/creating metadata.
    for source_path in [root, *(p.parent for p in extras.values())]:
        if target == source_path or target.is_relative_to(source_path) or source_path.is_relative_to(target):
            raise RecoveryError('overlapping_paths')
    with ExitStack() as stack:
        for folder in sorted({root, *(p.parent for p in extras.values())}, key=str):
            stack.enter_context(state_lock(folder))
        require_active(root)
        for path in extras.values():
            require_active(path)
        # Match existing desktop lock order; do not remove abandoned locks.
        for folder in ('review-actions', 'operations'):
            if (root / folder).exists():
                stack.enter_context(instance_lock(root / folder))
        files = _inventory(root, auxiliary=True)
        _complete(files)
        if not files:
            raise RecoveryError('empty_state')
        files.update(extras)
        for name, path in sorted(files.items()):
            if path.suffix == '.json' and name != 'run-status.json' and not name.startswith('routing/'):
                lock = path.with_suffix('.review-lock')
                try:
                    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                except OSError:
                    raise RecoveryError('state_busy') from None
                os.close(fd)
                stack.callback(lock.unlink)
        databases = {name: path for name, path in files.items() if name.endswith('.sqlite3')}
        # Hold write reservations on ALL SQLite stores while taking backups.
        # Backup uses a separate reader, never the reserved writer connection.
        for path in databases.values():
            db = stack.enter_context(closing(sqlite3.connect(path.as_uri() + '?mode=rw',
                                                           uri=True, timeout=0)))
            try:
                db.execute('BEGIN IMMEDIATE')
            except sqlite3.Error:
                raise RecoveryError('state_busy') from None
        target = _fresh(target, [root, *(p.parent for p in extras.values())])
        (target / 'data').mkdir()
        manifest = {'version': 1, 'files': {}}
        for name, path in sorted(files.items()):
            output = target / 'data' / name
            output.parent.mkdir(parents=True, exist_ok=True)
            if name in databases:
                with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as src, \
                        closing(sqlite3.connect(output)) as dst:
                    src.backup(dst)
                    dst.execute('PRAGMA journal_mode=DELETE')
                _integrity(output)
            else:
                with path.open('rb') as src, output.open('xb') as dst:
                    for block in iter(lambda: src.read(1024 * 1024), b''):
                        dst.write(block)
                    dst.flush()
                    os.fsync(dst.fileno())
                if _hash(path) != _hash(output):
                    raise RecoveryError('source_changed')
            manifest['files'][name] = _hash(output)
        encoded = json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()
        with (target / 'manifest.json').open('xb') as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        verify_snapshot(target)
    return target


@_fixed_errors
def verify_snapshot(snapshot_dir):
    root = safe_path(snapshot_dir)
    try:
        manifest = json.loads(safe_path(root / 'manifest.json').read_text(encoding='utf-8'))
        if (set(manifest) != {'version', 'files'} or type(manifest['version']) is not int
                or manifest['version'] != 1 or type(manifest['files']) is not dict
                or not manifest['files']):
            raise ValueError
        for name, receipt in manifest['files'].items():
            parts = PurePosixPath(name)
            if (parts.is_absolute() or '..' in parts.parts or '\\' in name or not _allowed(name)
                    or type(receipt) is not dict or set(receipt) != {'size', 'sha256'}
                    or type(receipt['size']) is not int or receipt['size'] < 0
                    or type(receipt['sha256']) is not str
                    or not re.fullmatch('[0-9a-f]{64}', receipt['sha256'])):
                raise ValueError
        _complete(manifest['files'])
        expected = {'manifest.json', *('data/' + n for n in manifest['files'])}
        actual = set()
        expected_dirs = {'.', 'data'}
        for name in expected:
            expected_dirs.update(p.as_posix() for p in PurePosixPath(name).parents)
        for directory, dirs, files in os.walk(root, followlinks=False):
            for name in dirs:
                path = safe_path(Path(directory) / name)
                if path.relative_to(root).as_posix() not in expected_dirs:
                    raise ValueError
            for name in files:
                path = safe_path(Path(directory) / name)
                actual.add(path.relative_to(root).as_posix())
        if actual != expected:
            raise ValueError
        for name, receipt in manifest['files'].items():
            path = root / 'data' / name
            if _hash(path) != receipt:
                raise ValueError
            if path.suffix == '.sqlite3':
                _integrity(path)
        return manifest
    except (OSError, ValueError, TypeError, KeyError):
        raise RecoveryError('invalid_snapshot') from None


@_fixed_errors
def restore(snapshot_dir, destination):
    """Restore full bytes into a fresh fenced directory; never activate it."""
    source = safe_path(snapshot_dir)
    manifest = verify_snapshot(source)
    target = _fresh(destination, [source])
    _write_state(target, 'pending')  # Before publishing ANY runtime bytes.
    with state_lock(target):
        return _populate_restore(source, target, manifest)


def _populate_restore(source, target, manifest):
    for name, receipt in manifest['files'].items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with safe_path(source / 'data' / name).open('rb') as src, path.open('xb') as dst:
            for block in iter(lambda: src.read(1024 * 1024), b''):
                dst.write(block)
            dst.flush()
            os.fsync(dst.fileno())
        if _hash(path) != receipt:
            raise RecoveryError('restore_verification_failed')
        if path.suffix == '.sqlite3':
            _integrity(path)
    # Reverify source and full destination, including file count; keep fence on
    # any failure. Receipt is private local metadata, never a provider decision.
    if verify_snapshot(source) != manifest:
        raise RecoveryError('source_changed')
    if _inventory(target, auxiliary=True).keys() != manifest['files'].keys():
        raise RecoveryError('restore_verification_failed')
    for name, expected in manifest['files'].items():
        if _hash(target / name) != expected:
            raise RecoveryError('restore_verification_failed')
    with (target / '.recovery' / 'receipt.json').open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    return target


@_fixed_errors
def acknowledge_restore(root, *, operator_acknowledged=False, reconciliation_recorded=False):
    """Explicit local operator attestation, NOT a fabricated provider proof.

    Does not reset claims/reservations, IDs, revisions, source bindings or results.
    Unknown work stays unknown, requiring its existing per-item reconciliation.
    """
    root = safe_path(root)
    if operator_acknowledged is not True or reconciliation_recorded is not True:
        raise RecoveryError('operator_reconciliation_required')
    with state_lock(root):
        if _state(root) != 'pending':
            raise RecoveryError('not_pending_restore')
        try:
            receipt = json.loads(safe_path(root / '.recovery' / 'receipt.json').read_text())
            if _inventory(root, auxiliary=True).keys() != receipt['files'].keys():
                raise ValueError
            for name, expected in receipt['files'].items():
                if not _allowed(name) or _hash(root / name) != expected:
                    raise ValueError
                if name.endswith('.sqlite3'):
                    _integrity(root / name)
        except (OSError, ValueError, TypeError, KeyError):
            raise RecoveryError('restore_verification_failed') from None
        _write_state(root, 'active')
