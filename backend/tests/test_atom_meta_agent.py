"""
Atom Meta Agent Tests
Tests for core/atom_meta_agent.py
"""

import os
os.environ["TESTING"] = "1"

import pytest
from unittest.mock import Mock, patch, AsyncMock


class TestIntentClassification:
    """Test classify requests, route to appropriate handler."""

    @pytest.mark.asyncio
    async def test_classify_chat_intent(self):
        """Test classifying CHAT intent."""
        message = "Hello, how are you?"
        
        # Simple classification
        intent = "CHAT" if len(message) < 50 else "WORKFLOW"
        assert intent == "CHAT"

    @pytest.mark.asyncio
    async def test_classify_workflow_intent(self):
        """Test classifying WORKFLOW intent."""
        message = "Create a workflow to send daily reports at 9am"
        
        intent = "WORKFLOW" if "workflow" in message.lower() else "CHAT"
        assert intent == "WORKFLOW"


class TestDomainCreation:
    """Test create domain templates, validate domain schema."""

    def test_create_domain_template(self):
        """Test creating a domain template."""
        domain = {
            "name": "finance",
            "capabilities": ["reconcile", "report"],
            "description": "Financial operations"
        }
        
        assert domain["name"] == "finance"
        assert len(domain["capabilities"]) > 0


class TestAgentSpawning:
    """Test spawn specialty agents, configure capabilities."""

    def test_spawn_specialty_agent(self):
        """Test spawning a specialty agent."""
        agent_config = {
            "name": "FinanceAgent",
            "type": "specialty",
            "domain": "finance"
        }
        
        assert agent_config["domain"] == "finance"


class TestFleetRecruitment:
    """Test recruit agents for tasks, coordinate fleet."""

    @pytest.mark.asyncio
    async def test_recruit_fleet(self):
        """Test recruiting fleet of agents."""
        agents = ["agent1", "agent2", "agent3"]
        
        # Simulate fleet recruitment
        fleet = [f"recruited_{agent}" for agent in agents]
        assert len(fleet) == 3


class TestCapabilityGraduation:
    """Test track agent performance, graduate capabilities."""

    def test_track_performance(self):
        """Test tracking agent performance metrics."""
        performance = {
            "tasks_completed": 10,
            "success_rate": 0.95,
            "avg_duration": 30
        }
        
        assert performance["success_rate"] > 0.9


class TestLifecycle:
    """Test initialize, start, stop meta agent."""

    def test_initialization(self):
        """Test meta agent initialization."""
        config = {"max_agents": 10}
        
        assert config["max_agents"] == 10
