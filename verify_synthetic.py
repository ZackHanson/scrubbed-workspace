"""Run deterministic tests with temporary runtime storage and sockets blocked."""
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch


def main():
    with tempfile.TemporaryDirectory(prefix='scrubbed-tests-') as folder, \
            patch.dict(os.environ, {'LOCALAPPDATA': folder, 'PYTHONDONTWRITEBYTECODE': '1'}), \
            patch.object(socket.socket, 'connect', side_effect=OSError('network_forbidden')), \
            patch.object(socket.socket, 'connect_ex', side_effect=OSError('network_forbidden')):
        # Import/discover only after runtime path isolation is in place.
        suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent))
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
