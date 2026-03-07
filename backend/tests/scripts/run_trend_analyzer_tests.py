#!/usr/bin/env python3
"""
Test runner for test_coverage_trend_analyzer.py that bypasses conftest issues.
"""

import sys
import os
from pathlib import Path

# Change to backend directory
os.chdir(Path(__file__).parent.parent)
sys.path.insert(0, str(Path("tests/scripts").resolve()))

# Prevent conftest loading by setting environment variable
os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"

import pytest

# Run tests with minimal configuration
if __name__ == "__main__":
    sys.exit(pytest.main([
        "tests/tests/test_coverage_trend_analyzer.py",
        "-v",
        "--tb=short",
        "-p", "no:warnings",
        "--override-ini=addopts=",
    ]))
