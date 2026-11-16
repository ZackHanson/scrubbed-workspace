"""Local cooperative recovery fence. No default runtime paths or network I/O."""
from contextlib import contextmanager, ExitStack
import json
import os
from pathlib import Path
import threading


class RecoveryError(RuntimeError):
    """Content-free recovery error."""


_local = threading.local()
SUBSTORES = {'operations', 'routing', 'holds', 'intake', 'review-actions', 'auxiliary'}


def safe_path(path):
    """Reject symlinks/junctions in every existing component before resolving."""
    try:
        path = Path(os.path.abspath(path))
        for item in (path, *path.parents):
            if item.is_symlink() or (hasattr(item, 'is_junction') and item.is_junction()):
                raise RecoveryError('unsafe_path')
        return path
    except (OSError, ValueError):
        raise RecoveryError('unsafe_path') from None


def state_root(path):
    path = safe_path(path)
    if path.suffix in {'.sqlite3', '.db', '.json'}:
        path = path.parent
    # Outermost anchor wins, even if an older nested standalone anchor exists.
    anchors = [p for p in (path, *path.parents) if (p / '.recovery').exists()]
    if anchors:
        return anchors[-1]
    if path.name in SUBSTORES:
        path = path.parent
    return path


def _state(root):
    anchor = safe_path(root / '.recovery')
    if not anchor.exists():
        return None
    try:
        value = json.loads(safe_path(anchor / 'state.json').read_text(encoding='utf-8'))
        if (type(value) is not dict or set(value) != {'version', 'status'}
                or type(value['version']) is not int or value['version'] != 1
                or value['status'] not in {'active', 'pending'}):
            raise ValueError
        return value['status']
    except (OSError, ValueError, TypeError):
        raise RecoveryError('invalid_recovery_fence') from None


def require_active(path):
    """Read-only check, suitable for disabled APIs and preexisting instances."""
    path = safe_path(path)
    for root in (path, *path.parents):
        state = _state(root)
        if state == 'pending':
            raise RecoveryError('restore_requires_reconciliation')


def _write_state(root, status):
    try:
        anchor = safe_path(root / '.recovery')
        anchor.mkdir(exist_ok=True)
        target = safe_path(anchor / 'state.json')
        temporary = safe_path(anchor / 'state.tmp')
        with temporary.open('x', encoding='utf-8') as stream:
            json.dump({'version': 1, 'status': status}, stream, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(target)
    except OSError:
        raise RecoveryError('recovery_fence_write_failed') from None


@contextmanager
def state_lock(path):
    """Exclusive, same-thread reentrant; does not require an active restore."""
    from operations import instance_lock
    root = state_root(path)
    held = getattr(_local, 'held', {})
    _local.held = held
    key = str(root)
    if held.get(key):
        held[key] += 1
        try:
            yield root
        finally:
            held[key] -= 1
        return
    with ExitStack() as stack:
        # Existing nested anchors are also locked when adopting an enclosing
        # workflow root. Known store normalization avoids split live locks.
        try:
            roots = [root] + sorted((safe_path(p) for p in root.iterdir()
                                    if p.name in SUBSTORES and (p / '.recovery').exists()),
                                   key=str) if root.exists() else [root]
            for item in roots:
                safe_path(item / '.recovery-lock' / 'operations.lock')
                stack.enter_context(instance_lock(item / '.recovery-lock'))
        except Exception:
            raise RecoveryError('state_busy') from None
        held[key] = 1
        try:
            yield root
        finally:
            del held[key]


@contextmanager
def active_state(path):
    """Wrap the ENTIRE read/mutate/dispatch operation, not only construction."""
    with state_lock(path) as root:
        require_active(path)
        if _state(root) is None:
            _write_state(root, 'active')
        yield root
