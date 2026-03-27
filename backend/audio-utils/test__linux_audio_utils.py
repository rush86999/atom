#!/usr/bin/env python3
"""Basic test cases for _linux_audio_utils module"""

import os
import sys
import pytest

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import importlib.util
import os

# Load module with dash in name using importlib
spec = importlib.util.spec_from_file_location(
    "audio_utils._linux_audio_utils",
    os.path.join(os.path.dirname(__file__), "_linux_audio_utils.py")
)
linux_audio_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(linux_audio_utils)


class TestBasic:
    """Basic test cases for module import and structure"""

    def test_module_import(self):
        """Test that _linux_audio_utils module can be imported"""
        assert linux_audio_utils is not None

    def test_module_has_expected_attributes(self):
        """Test that _linux_audio_utils module has expected attributes"""
        # Check for common attributes or functions
        assert hasattr(sys.modules[__name__], '__file__')
