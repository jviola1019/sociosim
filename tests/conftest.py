"""conftest.py: Patch RunStore default DB path to a Linux-writable tmp dir.

The production default (out/sociosim.db) sits on a Windows NTFS mount that
sqlite3 cannot write to from the Linux sandbox.  This hook redirects it before
any test module imports socio_sim.web.app (which calls RunStore() at module
level).
"""
from pathlib import Path
import tempfile

import pytest

# Patch before any test module is imported.  conftest.py is executed first.
def pytest_configure(config):
    try:
        import socio_sim.web.store as _store
        _tmpdir = Path(tempfile.mkdtemp(prefix="sociosim_test_"))
        _orig_init = _store.RunStore.__init__

        def _patched_init(self, path=None):
            _orig_init(self, path or _tmpdir / "test.db")

        _store.RunStore.__init__ = _patched_init
    except Exception:
        pass  # not a web test run; ignore
