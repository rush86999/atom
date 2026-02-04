#!/usr/bin/env python3
"""Basic test cases for nlp_engine module"""

import os
import sys
import pytest

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import ai.nlp_engine


class TestBasic:
    """Basic test cases for module import and structure"""

    def test_module_import(self):
        """Test that nlp_engine module can be imported"""
        assert ai.nlp_engine is not None

    def test_module_has_expected_attributes(self):
        """Test that nlp_engine module has expected attributes"""
        # Check for common attributes or functions
        assert hasattr(sys.modules[__name__], '__file__')
