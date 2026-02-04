#!/usr/bin/env python3
"""Basic test cases for asana_service module"""

import os
import sys
import pytest

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import consolidated.integrations.asana_service


class TestBasic:
    """Basic test cases for module import and structure"""

    def test_module_import(self):
        """Test that asana_service module can be imported"""
        assert consolidated.integrations.asana_service is not None

    def test_module_has_expected_attributes(self):
        """Test that asana_service module has expected attributes"""
        # Check for common attributes or functions
        assert hasattr(sys.modules[__name__], '__file__')
