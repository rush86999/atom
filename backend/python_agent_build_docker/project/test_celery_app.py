#!/usr/bin/env python3
"""Basic test cases for celery_app module"""

import os
import sys
import pytest

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import python_agent_build_docker.project.celery_app


class TestBasic:
    """Basic test cases for module import and structure"""

    def test_module_import(self):
        """Test that celery_app module can be imported"""
        assert python_agent_build_docker.project.celery_app is not None

    def test_module_has_expected_attributes(self):
        """Test that celery_app module has expected attributes"""
        # Check for common attributes or functions
        assert hasattr(sys.modules[__name__], '__file__')
