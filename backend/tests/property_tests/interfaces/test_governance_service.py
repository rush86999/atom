"""
⚠️  PROTECTED PROPERTY-BASED TEST ⚠️

This file tests CRITICAL SYSTEM INVARIANTS for the Atom platform.

DO NOT MODIFY THIS FILE unless:
1. You are fixing a TEST BUG (not an implementation bug)
2. You are ADDING new invariants
3. You have EXPLICIT APPROVAL from engineering lead

These tests must remain IMPLEMENTATION-AGNOSTIC.
Test only observable behaviors and public API contracts.

Protection: tests/.protection_markers/PROPERTY_TEST_GUARDIAN.md
"""

import uuid

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentStatus, AgentFeedback


class TestAgentGovernanceServiceContracts:
    """Test AgentGovernanceService maintains its interface contracts."""

    @given(
        name=st.text(min_size=1, max_size=100).filter(lambda x: x.strip()),
        category=st.text(min_size=1, max_size=50).filter(lambda x: x.strip()),
        module_path=st.text(min_size=1, max_size=200).filter(lambda x: x.strip()),
        class_name=st.text(min_size=1, max_size=100).filter(lambda x: x.strip())
    )
    @settings(max_examples=100)
    def test_register_agent_returns_valid_agent_registry(
        self, db_session: Session, name: str, category: str, module_path: str, class_name: str
    ):
        """
        CONTRACT: register_or_update_agent MUST return AgentRegistry with valid fields.

        Returns:
            - AgentRegistry with valid UUID
            - Default status=student
            - Default confidence=0.5
        """
        # Arrange
        service = AgentGovernanceService(db_session)

        # Act
        agent = service.register_or_update_agent(
            name=name,
            category=category,
            module_path=module_path,
            class_name=class_name
        )

        # Assert: Verify contract
        assert agent is not None, "register_or_update_agent returned None"
        assert isinstance(agent, AgentRegistry), "Return type is not AgentRegistry"

        # Must have valid UUID
        try:
            uuid.UUID(agent.id)
        except ValueError:
            pytest.fail(f"Agent ID {agent.id} is not a valid UUID")

        # Must have default values
        assert agent.status == AgentStatus.STUDENT.value, \
            f"New agent should have status=student, got {agent.status}"
        assert agent.confidence_score == 0.5, \
            f"New agent should have confidence=0.5, got {agent.confidence_score}"

        # Must match input parameters
        assert agent.name == name, "Agent name doesn't match input"
        assert agent.category == category, "Agent category doesn't match input"
        assert agent.module_path == module_path, "Agent module_path doesn't match input"
        assert agent.class_name == class_name, "Agent class_name doesn't match input"

    @given(
        agent_status=st.sampled_from([
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value,
        ]),
        action_type=st.text(min_size=1, max_size=50).filter(lambda x: x.strip())
    )
    @settings(max_examples=150)
    def test_can_perform_action_returns_standardized_dict(
        self, db_session: Session, agent_status: str, action_type: str
    ):
        """
        CONTRACT: can_perform_action MUST return dict with specific structure.

        Returns:
            {
                "allowed": bool,
                "reason": str,
                "agent_status": str,
                "action_complexity": int,
                "required_status": str,
                "requires_human_approval": bool
            }
        """
        # Arrange
        service = AgentGovernanceService(db_session)
        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=agent_status,
            confidence_score=0.5,
            
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Act
        decision = service.can_perform_action(agent.id, action_type)

        # Assert: Verify contract
        assert isinstance(decision, dict), "can_perform_action must return dict"

        # Required fields
        required_fields = [
            "allowed",
            "reason",
            "agent_status",
            "requires_human_approval"
        ]

        for field in required_fields:
            assert field in decision, f"Missing required field: {field}"

        # Field types
        assert isinstance(decision["allowed"], bool), "'allowed' must be bool"
        assert isinstance(decision["reason"], str), "'reason' must be str"
        assert isinstance(decision["agent_status"], str), "'agent_status' must be str"
        assert isinstance(decision["requires_human_approval"], bool), "'requires_human_approval' must be bool"

        # Optional fields (if present)
        if "action_complexity" in decision:
            assert isinstance(decision["action_complexity"], int), "'action_complexity' must be int"
            assert 1 <= decision["action_complexity"] <= 4, "'action_complexity' must be 1-4"

        if "required_status" in decision:
            assert isinstance(decision["required_status"], str), "'required_status' must be str"
            valid_statuses = [
                AgentStatus.STUDENT.value,
                AgentStatus.INTERN.value,
                AgentStatus.SUPERVISED.value,
                AgentStatus.AUTONOMOUS.value,
            ]
            assert decision["required_status"] in valid_statuses, \
                f"'required_status' must be one of {valid_statuses}"

    @given(
        agent_status=st.sampled_from([
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value,
        ])
    )
    @settings(max_examples=50)
    def test_get_agent_capabilities_returns_valid_structure(
        self, db_session: Session, agent_status: str
    ):
        """
        CONTRACT: get_agent_capabilities MUST return dict with valid structure.

        Returns:
            {
                "agent_id": str,
                "agent_name": str,
                "maturity_level": str,
                "confidence_score": float,
                "max_complexity": int,
                "allowed_actions": List[str],
                "restricted_actions": List[str]
            }
        """
        # Arrange
        service = AgentGovernanceService(db_session)
        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=agent_status,
            confidence_score=0.5,
            
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Act
        capabilities = service.get_agent_capabilities(agent.id)

        # Assert: Verify contract
        assert isinstance(capabilities, dict), "get_agent_capabilities must return dict"

        # Required fields
        required_fields = [
            "agent_id",
            "agent_name",
            "maturity_level",
            "confidence_score",
            "max_complexity",
            "allowed_actions",
            "restricted_actions"
        ]

        for field in required_fields:
            assert field in capabilities, f"Missing required field: {field}"

        # Field types
        assert isinstance(capabilities["agent_id"], str), "'agent_id' must be str"
        assert isinstance(capabilities["agent_name"], str), "'agent_name' must be str"
        assert isinstance(capabilities["maturity_level"], str), "'maturity_level' must be str"
        assert isinstance(capabilities["confidence_score"], (int, float)), "'confidence_score' must be numeric"
        assert isinstance(capabilities["max_complexity"], int), "'max_complexity' must be int"
        assert isinstance(capabilities["allowed_actions"], list), "'allowed_actions' must be list"
        assert isinstance(capabilities["restricted_actions"], list), "'restricted_actions' must be list"

        # Value constraints
        assert 0.0 <= capabilities["confidence_score"] <= 1.0, \
            "'confidence_score' must be in [0.0, 1.0]"
        assert 1 <= capabilities["max_complexity"] <= 4, \
            "'max_complexity' must be in [1, 4]"

        # Logical consistency
        maturity_order = [
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value,
        ]
        agent_index = maturity_order.index(agent_status)
        expected_max_complexity = agent_index + 1

        assert capabilities["max_complexity"] == expected_max_complexity, \
            f"'max_complexity' should be {expected_max_complexity} for status {agent_status}"

    @given(
        agent_status=st.sampled_from([
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value,
        ])
    )
    @settings(max_examples=50)
    def test_list_agents_returns_valid_list(
        self, db_session: Session, agent_status: str
    ):
        """
        CONTRACT: list_agents MUST return list of AgentRegistry objects.
        """
        # Arrange
        service = AgentGovernanceService(db_session)

        # Create multiple agents
        for i in range(5):
            agent = AgentRegistry(
                name=f"TestAgent_{i}",
                category="test",
                module_path="test.module",
                class_name="TestClass",
                status=agent_status,
                confidence_score=0.5,
                
            )
            db_session.add(agent)
        db_session.commit()

        # Act
        agents = service.list_agents()

        # Assert: Verify contract
        assert isinstance(agents, list), "list_agents must return list"
        assert len(agents) >= 5, "list_agents should return at least 5 agents"

        for agent in agents:
            assert isinstance(agent, AgentRegistry), "All items must be AgentRegistry instances"
            assert hasattr(agent, "id"), "Agent must have 'id' attribute"
            assert hasattr(agent, "name"), "Agent must have 'name' attribute"
            assert hasattr(agent, "status"), "Agent must have 'status' attribute"
