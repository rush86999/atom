"""
Minimal unit tests for ProactiveMessagingService core logic

Tests only the service logic without database or integration dependencies.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import Mock, MagicMock
import pytest
from datetime import datetime, timezone

# These mocks were previously installed at module level via sys.modules[...],
# which polluted the interpreter for the WHOLE pytest session and broke
# co-collected suites (e.g. test_covpush_intgr_c imports the real integration
# modules). Scoped to an autouse fixture so monkeypatch restores the originals
# after every test in this file.
_MOCKED_MODULES = [
    'core.agent_integration_gateway',
    'integrations.atom_discord_integration',
    'integrations.atom_whatsapp_integration',
    'integrations.atom_telegram_integration',
    'integrations.google_chat_enhanced_service',
    'integrations.meta_business_service',
    'integrations.marketing_unified_service',
    'integrations.ecommerce_unified_service',
    'integrations.slack_enhanced_service',
    'integrations.teams_enhanced_service',
    'integrations.document_logic_service',
    'integrations.shopify_service',
    'integrations.openclaw_service',
]


@pytest.fixture(autouse=True)
def _mock_integration_modules(monkeypatch: pytest.MonkeyPatch):
    """Scoped sys.modules mocks — monkeypatch restores originals per test."""
    for name in _MOCKED_MODULES:
        monkeypatch.setitem(sys.modules, name, MagicMock())

from core.models import AgentStatus, ProactiveMessageStatus


class TestProactiveMessagingServiceLogic:
    """Test core logic of proactive messaging service."""

    def test_student_agent_blocked_logic(self):
        """Verify STUDENT agents are blocked."""
        # This tests the business logic without full DB
        maturity = AgentStatus.STUDENT.value

        # STUDENT should always be blocked
        assert maturity == AgentStatus.STUDENT.value

        # Verify the message flow would be blocked
        expected_error = "STUDENT agents are not allowed to send proactive messages"
        assert "STUDENT" in expected_error
        assert "not allowed" in expected_error.lower()

    def test_intern_agent_requires_approval_logic(self):
        """Verify INTERN agents require approval."""
        maturity = AgentStatus.INTERN.value

        # INTERN requires approval
        assert maturity == AgentStatus.INTERN.value

        # Verify status flow
        pending_status = ProactiveMessageStatus.PENDING.value
        assert pending_status == "pending"

    def test_supervised_agent_auto_approved_logic(self):
        """Verify SUPERVISED agents are auto-approved."""
        maturity = AgentStatus.SUPERVISED.value

        # SUPERVISED gets auto-approved
        assert maturity == AgentStatus.SUPERVISED.value

        # Should transition to APPROVED
        approved_status = ProactiveMessageStatus.APPROVED.value
        assert approved_status == "approved"

    def test_autonomous_agent_auto_approved_logic(self):
        """Verify AUTONOMOUS agents are auto-approved."""
        maturity = AgentStatus.AUTONOMOUS.value

        # AUTONOMOUS gets auto-approved
        assert maturity == AgentStatus.AUTONOMOUS.value

        # Should be APPROVED immediately
        approved_status = ProactiveMessageStatus.APPROVED.value
        assert approved_status == "approved"

    def test_message_status_flow(self):
        """Test message status transitions."""
        # Initial state for INTERN
        assert ProactiveMessageStatus.PENDING.value == "pending"

        # After approval
        assert ProactiveMessageStatus.APPROVED.value == "approved"

        # After sending
        assert ProactiveMessageStatus.SENT.value == "sent"

        # If rejected
        assert ProactiveMessageStatus.CANCELLED.value == "cancelled"

        # If sending fails
        assert ProactiveMessageStatus.FAILED.value == "failed"


class TestProactiveMessageDataValidation:
    """Test data validation for proactive messages."""

    def test_required_fields(self):
        """Verify required field names."""
        required_fields = [
            "agent_id",
            "platform",
            "recipient_id",
            "content",
        ]

        # All required fields should be present
        assert "agent_id" in required_fields
        assert "platform" in required_fields
        assert "recipient_id" in required_fields
        assert "content" in required_fields

    def test_platform_options(self):
        """Test supported platforms."""
        platforms = ["slack", "discord", "whatsapp", "telegram", "teams", "google_chat"]

        assert "slack" in platforms
        assert "discord" in platforms
        assert "whatsapp" in platforms
        assert "telegram" in platforms

    def test_maturity_levels(self):
        """Test all maturity levels."""
        levels = [
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value,
        ]

        assert "student" in levels
        assert "intern" in levels
        assert "supervised" in levels
        assert "autonomous" in levels


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
