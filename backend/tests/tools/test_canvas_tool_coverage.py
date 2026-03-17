"""Test coverage for canvas_tool.py - Target 50%+ coverage."""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session

from tools.canvas_tool import (
    present_chart,
    present_markdown,
    present_form,
    present_status_panel,
    update_canvas,
    close_canvas,
    canvas_execute_javascript,
    present_to_canvas,
    present_specialized_canvas,
    _create_canvas_audit
)
from core.models import AgentRegistry, CanvasAudit, AgentStatus


@pytest.fixture
def db_session():
    """Mock database session for testing."""
    return Mock(spec=Session)


@pytest.fixture
def student_agent():
    """Create a STUDENT level agent for testing."""
    agent = AgentRegistry(
        id="test-student-agent",
        tenant_id="test-tenant",
        name="Test Student Agent",
        category="Test",
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.3
    )
    return agent


@pytest.fixture
def intern_agent():
    """Create an INTERN level agent for testing."""
    agent = AgentRegistry(
        id="test-intern-agent",
        tenant_id="test-tenant",
        name="Test Intern Agent",
        category="Test",
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus.INTERN.value,
        confidence_score=0.6
    )
    return agent


@pytest.fixture
def supervised_agent():
    """Create a SUPERVISED level agent for testing."""
    agent = AgentRegistry(
        id="test-supervised-agent",
        tenant_id="test-tenant",
        name="Test Supervised Agent",
        category="Test",
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus.SUPERVISED.value,
        confidence_score=0.8
    )
    return agent


@pytest.fixture
def autonomous_agent():
    """Create an AUTONOMOUS level agent for testing."""
    agent = AgentRegistry(
        id="test-autonomous-agent",
        tenant_id="test-tenant",
        name="Test Autonomous Agent",
        category="Test",
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus.AUTONOMOUS.value,
        confidence_score=0.95
    )
    return agent


@pytest.fixture
def mock_governance_service():
    """Mock governance service."""
    mock_service = MagicMock()
    mock_service.can_perform_action = MagicMock(return_value={
        "allowed": True,
        "reason": ""
    })
    mock_service.record_outcome = AsyncMock()
    return mock_service


@pytest.fixture
def mock_agent_resolver():
    """Mock agent context resolver."""
    mock_resolver = MagicMock()
    mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(None, {}))
    return mock_resolver
