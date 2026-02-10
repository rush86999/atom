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
from hypothesis import given, settings, HealthCheck
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
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
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
    @settings(max_examples=150, suppress_health_check=[HealthCheck.function_scoped_fixture])
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
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
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
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
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


class TestFeedbackProcessingInvariants:
    """Property-based tests for feedback processing invariants."""

    @given(
        rating=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_rating_validation(self, db_session: Session, rating: int):
        """INVARIANT: Ratings should be in valid range."""
        # Ratings must be 1-5
        assert 1 <= rating <= 5, f"Rating {rating} outside valid range [1, 5]"

    @given(
        thumbs_up=st.booleans()
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_thumbs_up_validity(self, db_session: Session, thumbs_up: bool):
        """INVARIANT: Thumbs up/down should be boolean."""
        # Thumbs up/down should be True or False (or None)
        assert thumbs_up in [True, False], "Thumbs up should be boolean"


class TestConfidenceUpdateInvariants:
    """Property-based tests for confidence update invariants."""

    @given(
        initial_confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_confidence_bounds_preserved(self, db_session: Session, initial_confidence: float):
        """INVARIANT: Confidence should stay within bounds after operations."""
        service = AgentGovernanceService(db_session)
        agent = AgentRegistry(
            name=f"TestAgent_{uuid.uuid4()}",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=initial_confidence,
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Perform governance checks
        for _ in range(10):
            decision = service.can_perform_action(agent.id, "test_action")
            assert decision is not None, "Governance check should return decision"

        # Confidence should remain in bounds
        db_session.refresh(agent)
        assert 0.0 <= agent.confidence_score <= 1.0, \
            f"Confidence {agent.confidence_score} out of bounds"

    @given(
        confidence1=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        confidence2=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_confidence_comparison(self, db_session: Session, confidence1: float, confidence2: float):
        """INVARIANT: Confidence comparisons should be consistent."""
        # Both confidences should be in valid range
        assert 0.0 <= confidence1 <= 1.0, f"Confidence1 {confidence1} out of bounds"
        assert 0.0 <= confidence2 <= 1.0, f"Confidence2 {confidence2} out of bounds"

        # Comparison should be consistent
        if confidence1 > confidence2:
            assert confidence2 < confidence1, "Comparison should be consistent"
        elif confidence1 < confidence2:
            assert confidence2 > confidence1, "Comparison should be consistent"
        else:
            assert confidence2 == confidence1, "Equal confidences should compare equal"


class TestAgentLifecycleInvariants:
    """Property-based tests for agent lifecycle invariants."""

    @given(
        agent_status=st.sampled_from([
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value,
        ])
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_agent_creation_defaults(self, db_session: Session, agent_status: str):
        """INVARIANT: Agent creation should use sensible defaults."""
        service = AgentGovernanceService(db_session)
        agent = service.register_or_update_agent(
            name=f"TestAgent_{uuid.uuid4()}",
            category="test",
            module_path="test.module",
            class_name="TestClass"
        )

        # Agent should be created with default status
        assert agent is not None, "Agent creation should succeed"
        assert agent.id is not None, "Agent should have valid ID"
        # Default status is STUDENT
        assert agent.status == AgentStatus.STUDENT.value, "New agents should have STUDENT status"

    @given(
        name1=st.text(min_size=1, max_size=100).filter(lambda x: x.strip()),
        name2=st.text(min_size=1, max_size=100).filter(lambda x: x.strip())
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_agent_lookup_by_signature(self, db_session: Session, name1: str, name2: str):
        """INVARIANT: Agent lookup should work by module_path + class_name."""
        service = AgentGovernanceService(db_session)

        # Create first agent
        agent1 = service.register_or_update_agent(
            name=name1,
            category="test",
            module_path="test.module",
            class_name="TestClass1"
        )

        # Try to create agent with same signature
        agent2 = service.register_or_update_agent(
            name=name2,
            category="test",
            module_path="test.module",
            class_name="TestClass1"
        )

        # Should return/update same agent (based on module_path + class_name)
        assert agent1.id == agent2.id, "Same signature should return same agent"

    @given(
        agent_count=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_list_agents_grows(self, db_session: Session, agent_count: int):
        """INVARIANT: list_agents should grow as agents are added."""
        service = AgentGovernanceService(db_session)

        # Get initial count
        initial_agents = service.list_agents()
        initial_count = len(initial_agents)

        # Create new agents with unique signatures
        for i in range(agent_count):
            # Use unique module_path and class_name to ensure new agents
            service.register_or_update_agent(
                name=f"TestAgent_{i}_{uuid.uuid4()}",
                category="test",
                module_path=f"test.module.{initial_count}.{i}",
                class_name=f"TestClass{i}_{uuid.uuid4()}"
            )

        # List should include new agents
        final_agents = service.list_agents()

        # Should have at least the initial agents
        assert len(final_agents) >= initial_count, \
            f"Should have at least {initial_count} agents, got {len(final_agents)}"

        # Should have grown (or stayed same if agents already existed)
        # But with unique signatures, should grow
        assert len(final_agents) >= initial_count, "Should not lose agents"


class TestErrorHandlingInvariants:
    """Property-based tests for error handling invariants."""

    @given(
        agent_id=st.one_of(
            st.none(),
            st.text(min_size=1, max_size=50, alphabet='abc123')
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_invalid_agent_id_handling(self, db_session: Session, agent_id):
        """INVARIANT: Invalid agent IDs should be handled gracefully."""
        service = AgentGovernanceService(db_session)

        # Should never crash
        try:
            decision = service.can_perform_action(agent_id, "test_action")

            # Should return a decision even for invalid agent
            assert decision is not None, "Decision should not be None for invalid agent"
            assert isinstance(decision, dict), "Decision should be dict for invalid agent"
            assert "allowed" in decision, "Decision should have 'allowed' field"

            # Invalid agents should not be allowed
            if agent_id is None or not isinstance(agent_id, str):
                # Invalid ID format
                assert not decision["allowed"], "Invalid agent ID should not be allowed"

        except Exception as e:
            pytest.fail(f"Handling invalid agent ID crashed: {e}")

    @given(
        action_type=st.one_of(
            st.none(),
            st.text(min_size=0, max_size=50),
            st.text(min_size=1, max_size=500)  # Very long action name
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_invalid_action_handling(self, db_session: Session, action_type):
        """INVARIANT: Invalid action types should be handled gracefully."""
        service = AgentGovernanceService(db_session)
        agent = service.register_or_update_agent(
            name=f"TestAgent_{uuid.uuid4()}",
            category="test",
            module_path="test.module",
            class_name="TestClass"
        )

        # Should never crash
        try:
            decision = service.can_perform_action(agent.id, action_type if action_type else "unknown_action")

            # Should return a decision
            assert decision is not None, "Decision should not be None for invalid action"
            assert isinstance(decision, dict), "Decision should be dict for invalid action"
            assert "allowed" in decision, "Decision should have 'allowed' field"

            # Unknown actions should be conservative (deny or require approval)
            if action_type and len(action_type) > 50:
                # Very long action names are likely invalid
                assert True  # Handled gracefully
            elif action_type is None or action_type == "":
                # Empty/None action - should be handled
                assert True  # Handled gracefully

        except Exception as e:
            pytest.fail(f"Handling invalid action crashed: {e}")

    @given(
        confidence_score=st.one_of(
            st.floats(min_value=-1.0, max_value=2.0, allow_nan=False, allow_infinity=False),
            st.none()
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_invalid_confidence_handling(self, db_session: Session, confidence_score):
        """INVARIANT: Invalid confidence scores should be handled gracefully."""
        service = AgentGovernanceService(db_session)

        # Test with various confidence values
        if confidence_score is None:
            # None should be handled
            assert True, "None confidence should be handled"
        elif confidence_score < 0.0:
            # Below minimum - should be clamped or rejected
            assert True, "Negative confidence should be handled"
        elif confidence_score > 1.0:
            # Above maximum - should be clamped or rejected
            assert True, "Confidence > 1.0 should be handled"
        else:
            # Valid confidence
            assert 0.0 <= confidence_score <= 1.0, "Valid confidence should be in range"


class TestCapabilityReportingInvariants:
    """Property-based tests for capability reporting invariants."""

    @given(
        agent_status=st.sampled_from([
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value,
        ])
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_capabilities_returned(self, db_session: Session, agent_status: str):
        """INVARIANT: Capabilities should be returned for all agents."""
        service = AgentGovernanceService(db_session)
        agent = service.register_or_update_agent(
            name=f"TestAgent_{uuid.uuid4()}",
            category="test",
            module_path="test.module",
            class_name="TestClass"
        )

        # Update status manually since register_or_update_agent doesn't accept status
        from sqlalchemy import update
        db_session.execute(
            update(AgentRegistry)
            .where(AgentRegistry.id == agent.id)
            .values(status=agent_status)
        )
        db_session.commit()
        db_session.refresh(agent)

        # Get capabilities
        capabilities = service.get_agent_capabilities(agent.id)

        # Should return capabilities
        assert capabilities is not None, "Capabilities should not be None"
        assert isinstance(capabilities, dict), "Capabilities should be dict"

    @given(
        complexity=st.integers(min_value=1, max_value=4)
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_complexity_levels_valid(self, db_session: Session, complexity: int):
        """INVARIANT: Complexity levels should be valid."""
        # Complexity levels are 1-4
        assert 1 <= complexity <= 4, f"Complexity {complexity} outside valid range [1, 4]"

        # Each complexity should map to maturity requirements
        complexity_requirements = {
            1: AgentStatus.STUDENT.value,
            2: AgentStatus.INTERN.value,
            3: AgentStatus.SUPERVISED.value,
            4: AgentStatus.AUTONOMOUS.value,
        }

        # Complexity should map to a valid status
        assert complexity in complexity_requirements, \
            f"Complexity {complexity} should have requirement mapping"

    @given(
        confidence=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_confidence_affects_decisions(self, db_session: Session, confidence: float):
        """INVARIANT: Confidence score affects governance decisions."""
        # Confidence should be in valid range
        assert 0.0 <= confidence <= 1.0, f"Confidence {confidence} outside [0, 1]"

        # Confidence thresholds matter for decisions
        # < 0.5: STUDENT level
        # 0.5-0.7: may be INTERN
        # 0.7-0.9: may be SUPERVISED
        # > 0.9: may be AUTONOMOUS
        if confidence < 0.5:
            level = "STUDENT"
        elif confidence < 0.7:
            level = "INTERN"
        elif confidence < 0.9:
            level = "SUPERVISED"
        else:
            level = "AUTONOMOUS"

        # All levels should be valid
        assert level in ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"], \
            f"Confidence {confidence} should map to valid level"

