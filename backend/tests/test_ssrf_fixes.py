"""
Test suite for SSRF fix verification.

GREEN PHASE: These tests verify the SSRF fixes are applied.
"""

import pytest


class TestSSRFFixes:
    """Tests for verifying the SSRF fixes."""

    def test_hitl_url_validation_exists(self):
        """
        Test that HITL service now has URL validation.

        GREEN PHASE: After the fix, _validate_url method should exist.
        """
        from core.hitl_service import HITLService

        # Verify the fix - _validate_url method exists
        assert hasattr(HITLService, '_validate_url'), \
            "Fix applied: _validate_url method exists"

    def test_hitl_url_validation_called(self):
        """
        Test that callback URL is validated before request.

        GREEN PHASE: After the fix, _validate_url should be called.
        """
        from core.hitl_service import HITLService
        import inspect

        source = inspect.getsource(HITLService._resume_workflow)

        # Verify the fix - validation is called
        assert '_validate_url(callback_url)' in source, \
            "Fix applied: callback_url is validated before HTTP request"

    def test_skill_creation_url_validation_exists(self):
        """
        Test that skill creation agent has URL validation.

        GREEN PHASE: After the fix, _validate_url method should exist.
        """
        from core.agents.skill_creation_agent import SkillCreationAgent

        # Verify the fix - _validate_url method exists
        assert hasattr(SkillCreationAgent, '_validate_url'), \
            "Fix applied: _validate_url method exists"

    def test_skill_creation_url_validation_called(self):
        """
        Test that API docs URL is validated before fetch.

        GREEN PHASE: After the fix, _validate_url should be called.
        """
        from core.agents.skill_creation_agent import SkillCreationAgent
        import inspect

        source = inspect.getsource(SkillCreationAgent._fetch_api_docs)

        # Verify the fix - validation is called
        assert '_validate_url(url)' in source, \
            "Fix applied: URL is validated before HTTP request"

    def test_url_validation_blocks_private_ips(self):
        """
        Test that URL validation blocks private IP ranges.

        GREEN PHASE: After the fix, private IPs should be blocked.
        """
        from core.hitl_service import HITLService

        # Test that private IPs are blocked
        assert not HITLService()._validate_url("http://localhost:8000"), \
            "Fix applied: localhost is blocked"
        assert not HITLService()._validate_url("http://127.0.0.1:8000"), \
            "Fix applied: 127.0.0.1 is blocked"
        assert not HITLService()._validate_url("http://10.0.0.1:8000"), \
            "Fix applied: 10.0.0.0/8 range is blocked"
        assert not HITLService()._validate_url("http://192.168.1.1:8000"), \
            "Fix applied: 192.168.0.0/16 range is blocked"

    def test_url_validation_allows_public_urls(self):
        """
        Test that URL validation allows public URLs.

        GREEN PHASE: After the fix, public URLs should be allowed.
        """
        from core.hitl_service import HITLService

        # Test that public URLs are allowed
        assert HITLService()._validate_url("https://api.example.com/callback"), \
            "Fix applied: Public HTTPS URLs are allowed"
        assert HITLService()._validate_url("http://api.example.com/callback"), \
            "Fix applied: Public HTTP URLs are allowed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
