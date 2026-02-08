"""
Root conftest.py for test suite configuration

This file is loaded before any test modules and sets up necessary fixtures
and configuration for the entire test suite.
"""

import sys
import os
import pytest

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# CRITICAL: This code runs when conftest.py is first imported by pytest.
# It restores numpy/pandas/lancedb/pyarrow modules that may have been
# set to None by previously imported test modules (like test_proactive_messaging_simple.py).
#
# This must happen at module level, not in a function, to ensure it runs
# before test collection begins.
for mod in ["numpy", "pandas", "lancedb", "pyarrow"]:
    if mod in sys.modules and sys.modules[mod] is None:
        sys.modules.pop(mod, None)


def pytest_configure(config):
    """
    Pytest hook called after command line options have been parsed
    but before test collection begins.
    """
    pass


@pytest.fixture(autouse=True)
def ensure_numpy_available(request):
    """
    Auto-use fixture that ensures numpy/pandas/lancedb/pyarrow are available
    before each test runs.

    This is a safety net in case any test sets these to None.
    """
    # Restore modules before each test
    for mod in ["numpy", "pandas", "lancedb", "pyarrow"]:
        if mod in sys.modules and sys.modules[mod] is None:
            sys.modules.pop(mod, None)

    yield

    # No cleanup needed
