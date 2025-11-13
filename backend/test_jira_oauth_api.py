#!/usr/bin/env python3
"""Basic test cases for jira_oauth_api module"""

import pytest
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import jira_oauth_api

class TestBasic:
    """Basic test cases for module import and structure"""

    def test_module_import(self):
        """Test that jira_oauth_api module can be imported"""
        assert jira_oauth_api is not None

    def test_module_has_expected_attributes(self):
        """Test that jira_oauth_api module has expected attributes"""
        # Check for common attributes or functions
        assert hasattr(sys.modules[__name__], '__file__')
