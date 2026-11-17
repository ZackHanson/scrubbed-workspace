"""Small adapters for the shared local-state recovery fence."""
from contextlib import contextmanager
from functools import wraps

from recovery_guard import RecoveryError, active_state, require_active


def _path(location, args, kwargs):
    if callable(location):
        return location(*args, **kwargs)
    value = args[0]
    for attribute in location.split('.'):
        value = getattr(value, attribute)
    return value


def state_read(location, *, on_error=None):
    """Fence direct reads/construction without creating runtime files."""
    def decorate(function):
        @wraps(function)
        def guarded(*args, **kwargs):
            try:
                require_active(_path(location, args, kwargs))
                return function(*args, **kwargs)
            except RecoveryError as error:
                if on_error:
                    raise on_error(error) from None
                raise
        return guarded
    return decorate


def state_mutation(location, *, enabled=None, on_error=None):
    """Hold the state lock through mutation/dispatch, including nested calls."""
    def decorate(function):
        @wraps(function)
        def guarded(*args, **kwargs):
            try:
                path = _path(location, args, kwargs)
                require_active(path)
                if enabled is not None and not enabled(*args, **kwargs):
                    return function(*args, **kwargs)
                with active_state(path):
                    return function(*args, **kwargs)
            except RecoveryError as error:
                if on_error:
                    raise on_error(error) from None
                raise
        return guarded
    return decorate


def state_context(location):
    """Wrap an existing context manager for its entire entered lifetime."""
    def decorate(function):
        @wraps(function)
        @contextmanager
        def guarded(*args, **kwargs):
            with active_state(_path(location, args, kwargs)):
                with function(*args, **kwargs) as value:
                    yield value
        return guarded
    return decorate
