"""
Property-Based Tests for Governance Invariants

Tests CRITICAL governance system invariants:
- Confidence score bounds (0.0 to 1.0)
- Maturity level transitions
- Permission enforcement
- Cache consistency
- Governance check performance

These tests protect against governance bugs that could allow
unauthorized agent actions or break maturity level restrictions.
"""

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
import uuid
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.governance_cache import get_governance_cache
from core.models import AgentRegistry, AgentStatus


class TestGovernanceInvariants:
    """Test governance system maintains critical invariants."""

    @pytest.fixture
    def db_session(self, request):
        """Get database session fixture."""
        from backend.tests.conftest import db_session
        # Use the existing fixture from conftest
        return request.getfixturevalue("db_session")
