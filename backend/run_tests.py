#!/usr/bin/env python3.11
"""Simple test runner that bypasses conftest"""
import sys
import os

# Set PYTHONPATH
sys.path.insert(0, '.')
os.environ['ENVIRONMENT'] = 'development'

# Import pytest
import pytest

# Run tests on specific modules
test_files = [
    'tests/test_security_config.py',
    'tests/test_webhook_handlers.py',
    'tests/test_oauth_validation.py',
    'tests/test_secrets_encryption.py',
    'tests/test_task_queue.py',
    'tests/test_unified_search.py',
]

# Run pytest without conftest
exit_code = pytest.main(test_files + [
    '-v',
    '--tb=short',
    '--no-header',
    '-p', 'no:warnings'
])

sys.exit(exit_code)
