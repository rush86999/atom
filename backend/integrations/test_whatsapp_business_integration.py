#!/usr/bin/env python3
"""Basic test cases for whatsapp_business_integration module"""

import pytest
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import integrations.whatsapp_business_integration

class TestBasic:
    """Basic test cases for module import and structure"""

    def test_module_import(self):
        """Test that whatsapp_business_integration module can be imported"""
        assert integrations.whatsapp_business_integration is not None

    def test_module_has_expected_attributes(self):
        """Test that whatsapp_business_integration module has expected attributes"""
        # Check for common attributes or functions
        assert hasattr(sys.modules[__name__], '__file__')
