#!/usr/bin/env python3
"""
Run trigger interceptor tests with coverage
"""
import sys
import os

# Set PYTHONPATH
sys.path.insert(0, '.')
os.environ['ENVIRONMENT'] = 'development'

# Import pytest
import pytest

# Run tests
test_file = 'tests/unit/core/test_trigger_interceptor_minimal.py'

# Run pytest with coverage
exit_code = pytest.main([
    test_file,
    '-v',
    '--tb=short',
    '--no-header',
    '-p', 'no:warnings',
    '--cov=core.trigger_interceptor',
    '--cov-report=term-missing',
    '-n', '0'  # Disable xdist for reliable coverage
])

sys.exit(exit_code)
