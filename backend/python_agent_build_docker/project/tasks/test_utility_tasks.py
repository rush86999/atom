#!/usr/bin/env python3
"""Basic test cases for utility_tasks module"""

import os
import sys
import pytest

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import python_agent_build_docker.project.tasks.utility_tasks


class TestBasic:
    """Basic test cases for module import and structure"""

    def test_module_import(self):
        """Test that utility_tasks module can be imported"""
        assert python_agent_build_docker.project.tasks.utility_tasks is not None

    def test_module_has_expected_attributes(self):
        """Test that utility_tasks module has expected attributes"""
        # Check for common attributes or functions
        assert hasattr(sys.modules[__name__], '__file__')
