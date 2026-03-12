#!/usr/bin/env python3
"""
Standalone test runner for DTO tests to avoid conftest issues
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

# Run pytest with isolated config
import pytest

if __name__ == "__main__":
    # Run pytest from this directory to avoid loading parent conftests
    sys.exit(pytest.main([
        __file__.replace("run_tests.py", "test_response_models.py"),
        "-v",
        "--no-header",
        "--tb=short",
        "-p", "no:cacheprovider"
    ]))
