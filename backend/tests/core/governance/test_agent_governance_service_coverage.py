"""
Coverage-driven tests for AgentGovernanceService (currently 0% -> target 75%+)

Target file: core/agent_governance_service.py (286 statements)

Focus areas from coverage gap analysis:
- __init__ and service initialization (lines 1-50)
- check_agent_permission maturity matrix (lines 50-150)
- Permission check error handling (lines 150-200)
- Cache invalidation methods (lines 200-250)
- Audit trail methods (lines 250-286)
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timezone
from uuid import uuid4

from core.agent_governance_service import AgentGovernanceService
from core.models import (
    AgentRegistry,
    AgentStatus,
    User,
    UserRole,
    FeedbackStatus,
    HITLAction,
    HITLActionStatus,
)


class TestAgentGovernanceServiceCoverage:
    """Coverage-driven tests for agent_governance_service.py"""

    def test_service_initialization(self, db_session):
        """Cover lines 25-27: Service initialization with dependencies"""
        service = AgentGovernanceService(db_session)
        assert service.db is db_session
        assert service.db is not None

    def test_register_or_update_agent_new_agent(self, db_session):
        """Cover lines 28-53: Register new agent"""
        service = AgentGovernanceService(db_session)

        agent = service.register_or_update_agent(
            name="Test Agent",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent",
            description="A test agent"
        )

        assert agent is not None
        assert agent.name == "Test Agent"
        assert agent.category == "Testing"
        assert agent.module_path == "test.module"
        assert agent.class_name == "TestAgent"
        assert agent.description == "A test agent"
        assert agent.status == AgentStatus.STUDENT.value

    def test_register_or_update_agent_existing_agent(self, db_session):
        """Cover lines 54-62: Update existing agent"""
        service = AgentGovernanceService(db_session)

        # Create initial agent
        agent1 = service.register_or_update_agent(
            name="Agent One",
            category="Testing",
            module_path="test.module",
            class_name="TestAgent"
        )

        # Update agent
        agent2 = service.register_or_update_agent(
            name="Agent Two",
            category="Updated",
            module_path="test.module",
            class_name="TestAgent",
            description="Updated description"
        )

        assert agent2.id == agent1.id
        assert agent2.name == "Agent Two"
        assert agent2.category == "Updated"
        assert agent2.description == "Updated description"

    def test_list_agents_all(self, db_session):
        """Cover lines 239-244: List all agents"""
        service = AgentGovernanceService(db_session)

        # Register multiple agents
        service.register_or_update_agent("Agent 1", "Cat1", "mod1", "Class1")
        service.register_or_update_agent("Agent 2", "Cat2", "mod2", "Class2")
        service.register_or_update_agent("Agent 3", "Cat3", "mod3", "Class3")

        agents = service.list_agents()
        assert len(agents) >= 3

    def test_list_agents_by_category(self, db_session):
        """Cover lines 242-243: List agents by category filter"""
        service = AgentGovernanceService(db_session)

        # Register agents with different categories
        service.register_or_update_agent("Agent 1", "Finance", "mod1", "Class1")
        service.register_or_update_agent("Agent 2", "Finance", "mod2", "Class2")
        service.register_or_update_agent("Agent 3", "HR", "mod3", "Class3")

        finance_agents = service.list_agents(category="Finance")
        assert len(finance_agents) >= 2
        for agent in finance_agents:
            assert agent.category == "Finance"
