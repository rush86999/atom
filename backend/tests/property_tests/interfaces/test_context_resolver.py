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

import asyncio
import uuid

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from sqlalchemy.orm import Session

from core.agent_context_resolver import AgentContextResolver
from core.models import AgentRegistry, AgentStatus, User, UserRole, ChatSession


class TestAgentContextResolverContracts:
    """Test AgentContextResolver maintains its interface contracts."""

    @given(
        requested_agent_id=st.sampled_from([None, "invalid_agent_id", ""])
    )
    @settings(max_examples=50)
    def test_resolve_agent_always_returns_agent_or_none(
        self, db_session: Session, requested_agent_id: str
    ):
        """
        CONTRACT: resolve_agent_for_request MUST NEVER crash.

        Should always return (agent or None, context_dict), never raise exception.
        """
        # Arrange
        resolver = AgentContextResolver(db_session)

        # Create a test user with unique email
        import uuid
        user = User(
            email=f"test_{uuid.uuid4()}@example.com",
            role=UserRole.MEMBER.value,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Act: Should never crash - use asyncio.run to call async function
        import asyncio
        try:
            agent, context = asyncio.run(resolver.resolve_agent_for_request(
                user_id=user.id,
                session_id=None,
                requested_agent_id=requested_agent_id,
                action_type="chat"
            ))

            # Assert: Verify contract
            assert context is not None, "Context must never be None"
            assert isinstance(context, dict), "Context must be dict"

            # Agent can be None (if resolution failed) but must be the right type if present
            if agent is not None:
                assert isinstance(agent, AgentRegistry), "Agent must be AgentRegistry instance"

        except Exception as e:
            pytest.fail(f"resolve_agent_for_request crashed: {e}")

    @given(
        use_explicit_agent=st.booleans(),
        use_session_agent=st.booleans()
    )
    @settings(max_examples=50)
    def test_resolve_agent_fallback_chain(
        self, db_session: Session, use_explicit_agent: bool, use_session_agent: bool
    ):
        """
        CONTRACT: resolve_agent_for_request MUST follow fallback chain.

        Priority order:
        1. Explicit agent_id
        2. Session agent
        3. System default
        """
        # Arrange
        resolver = AgentContextResolver(db_session)

        # Create test user
        user = User(
            email=f"test_{uuid.uuid4()}@example.com",
            role=UserRole.MEMBER.value,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create explicit agent
        explicit_agent = AgentRegistry(
            name="ExplicitAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.5,
            
        )
        db_session.add(explicit_agent)
        db_session.commit()
        db_session.refresh(explicit_agent)

        # Create session with agent
        session = ChatSession(
            user_id=user.id,
            title="Test Session"
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        session_agent = AgentRegistry(
            name="SessionAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.5,
            
        )
        db_session.add(session_agent)
        db_session.commit()
        db_session.refresh(session_agent)

        # Set session agent
        resolver.set_session_agent(session.id, session_agent.id)

        # Determine expected agent based on fallback
        if use_explicit_agent:
            expected_agent_id = explicit_agent.id
            expected_path = ["explicit_agent_id"]
        elif use_session_agent:
            expected_agent_id = session_agent.id
            expected_path = ["session_agent"]
        else:
            # System default will be created
            expected_agent_id = None  # Don't know ID yet
            expected_path = ["system_default"]

        # Act
        requested_id = explicit_agent.id if use_explicit_agent else None
        session_id = session.id if use_session_agent else None

        agent, context = asyncio.run(resolver.resolve_agent_for_request(
            user_id=user.id,
            session_id=session_id,
            requested_agent_id=requested_id,
            action_type="chat"
        ))

        # Assert: Verify contract
        assert agent is not None, "Should always resolve to an agent"
        assert isinstance(agent, AgentRegistry), "Agent must be AgentRegistry"

        # Verify resolution path
        if use_explicit_agent:
            assert "explicit_agent_id" in context["resolution_path"], \
                "Should use explicit agent when provided"
        elif use_session_agent:
            assert "session_agent" in context["resolution_path"], \
                "Should use session agent when no explicit agent"

        # Context must have required fields
        assert "user_id" in context, "Context must have 'user_id'"
        assert "resolution_path" in context, "Context must have 'resolution_path'"
        assert "resolved_at" in context, "Context must have 'resolved_at'"

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
    def test_validate_agent_for_action_returns_dict(
        self, db_session: Session, agent_status: str, action_type: str
    ):
        """
        CONTRACT: validate_agent_for_action MUST return governance decision dict.

        Returns same structure as AgentGovernanceService.can_perform_action.
        """
        # Arrange
        resolver = AgentContextResolver(db_session)
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
        decision = resolver.validate_agent_for_action(agent, action_type)

        # Assert: Verify contract
        assert isinstance(decision, dict), "validate_agent_for_action must return dict"

        # Must have same fields as governance decision
        required_fields = ["allowed", "reason", "requires_human_approval"]
        for field in required_fields:
            assert field in decision, f"Missing required field: {field}"

        assert isinstance(decision["allowed"], bool), "'allowed' must be bool"
        assert isinstance(decision["reason"], str), "'reason' must be str"

    @given(
        valid_session=st.booleans(),
        valid_agent=st.booleans()
    )
    @settings(max_examples=50)
    def test_set_session_agent_returns_bool(
        self, db_session: Session, valid_session: bool, valid_agent: bool
    ):
        """
        CONTRACT: set_session_agent MUST return bool.

        Returns True on success, False on failure.
        """
        # Arrange
        resolver = AgentContextResolver(db_session)

        # Create test user and session
        user = User(
            email=f"test_{uuid.uuid4()}@example.com",
            role=UserRole.MEMBER.value,
        )
        db_session.add(user)
        db_session.commit()

        session_id = None
        if valid_session:
            session = ChatSession(
                user_id=user.id,
                title="Test Session"
            )
            db_session.add(session)
            db_session.commit()
            db_session.refresh(session)
            session_id = session.id
        else:
            session_id = str(uuid.uuid4())  # Invalid session

        agent_id = None
        if valid_agent:
            agent = AgentRegistry(
                name="TestAgent",
                category="test",
                module_path="test.module",
                class_name="TestClass",
                status=AgentStatus.INTERN.value,
                confidence_score=0.5,

            )
            db_session.add(agent)
            db_session.commit()
            db_session.refresh(agent)
            agent_id = agent.id
        else:
            agent_id = str(uuid.uuid4())  # Invalid agent

        # Act
        result = resolver.set_session_agent(session_id, agent_id)

        # Assert: Verify contract
        assert isinstance(result, bool), "set_session_agent must return bool"

        # Should return True only if both session and agent are valid
        if valid_session and valid_agent:
            assert result is True, "Should return True for valid session and agent"
        else:
            assert result is False, "Should return False for invalid session or agent"
