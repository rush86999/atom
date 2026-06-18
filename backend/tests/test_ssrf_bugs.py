"""
Test suite for SSRF (Server-Side Request Forgery) vulnerabilities.

RED PHASE: These tests expose SSRF bugs.

The bugs:
1. hitl_service.py:112-118 - callback_url from user input used without validation
2. skill_creation_agent.py:203-210 - URL from user input fetched without validation
3. base_agent_mixin.py:38 - fetch_url method without URL validation
"""

import pytest
import inspect


class TestSSRFVulnerabilities:
    """
    Test suite revealing SSRF vulnerabilities.

    The bug: User-controlled URLs are passed to HTTP clients without
    validation, allowing attackers to make requests to internal resources.
    """

    def test_hitl_callback_url_not_validated(self):
        """
        Test that callback_url is not validated before making request.

        BUG: Lines 112-118 - callback_url from action.params used directly.
        An attacker can specify internal URLs like http://localhost:6379
        """
        from core.hitl_service import HITLService

        source = inspect.getsource(HITLService._resume_workflow)

        # Verify the bug - callback_url used without validation
        assert 'callback_url' in source, \
            "Bug confirmed: callback_url extracted from user input"
        assert 'client.post(callback_url' in source, \
            "Bug confirmed: callback_url used in HTTP request without validation"

    def test_skill_creation_url_not_validated(self):
        """
        Test that API docs URL is not validated before fetching.

        BUG: Lines 203-210 - URL from user input fetched without validation.
        """
        from core.agents.skill_creation_agent import SkillCreationAgent

        source = inspect.getsource(SkillCreationAgent._fetch_api_docs)

        # Verify the bug - URL used without validation
        assert 'await self.client.get(url)' in source or 'client.get(url)' in source, \
            "Bug confirmed: URL passed to HTTP client without validation"
        assert 'raise_for_status' in source, \
            "Bug confirmed: HTTP client makes request to arbitrary URL"

    def test_base_agent_fetch_url_not_validated(self):
        """
        Test that fetch_url doesn't validate URL.

        BUG: Line 38-50 - URL passed to mcp_service without validation.
        """
        from core.base_agent_mixin import MCPCapableMixin

        source = inspect.getsource(MCPCapableMixin.fetch_url)

        # Verify the bug - URL used without validation
        assert 'url' in source and 'fetch_page' in source, \
            "Bug confirmed: URL parameter used without validation in tool call"

    def test_no_url_whitelist(self):
        """
        Test that no URL whitelist validation exists.

        BUG: No whitelist to prevent internal IP access.
        """
        from core.hitl_service import HITLService

        source = inspect.getsource(HITLService._resume_workflow)

        # Verify the bug - no URL validation
        assert 'whitelist' not in source.lower(), \
            "Bug confirmed: No URL whitelist validation in callback handling"

    def test_no_private_ip_check(self):
        """
        Test that private IP ranges are not blocked.

        BUG: No check for private IP ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16).
        """
        from core.hitl_service import HITLService

        source = inspect.getsource(HITLService._resume_workflow)

        # Verify the bug - no private IP blocking
        assert '10.0.0.0' not in source and '172.16.0.0' not in source, \
            "Bug confirmed: No private IP range blocking in callback handling"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
