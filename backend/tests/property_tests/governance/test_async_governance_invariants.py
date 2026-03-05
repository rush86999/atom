"""
Property-Based Tests for Async Governance Invariants

Tests async AgentContextResolver methods using Hypothesis:
- resolve_agent_for_request() always returns (agent, context) tuple
- Resolution path is always non-empty
- Invalid agent IDs return None agent but valid context

Uses @pytest.mark.asyncio BEFORE @given to avoid Hypothesis async errors.
"""

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis.strategies import sampled_from, uuids, text, none
from sqlalchemy.orm import Session
from typing import Optional

from core.agent_context_resolver import AgentContextResolver
from core.models import AgentRegistry, AgentStatus, ChatSession

HYPOTHESIS_SETTINGS_CRITICAL = {
    "suppress_health_check": [HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    "max_examples": 200
}

HYPOTHESIS_SETTINGS_IO = {
    "suppress_health_check": [HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
    "max_examples": 50
}


class TestAsyncContextResolverInvariants:
    """Property-based tests for async agent context resolution (CRITICAL)."""

    @pytest.mark.asyncio  # MUST come before @given
    @given(
        user_id=uuids(),
        session_id=sampled_from([None, "session-123", "nonexistent-session"]),
        requested_agent_id=sampled_from([None, "agent-456", "invalid-agent"]),
        action_type=sampled_from(["chat", "stream_chat", "delete", "execute"])
    )
    @settings(**HYPOTHESIS_SETTINGS_CRITICAL)
    async def test_resolve_agent_context_structure(
        self, db_session, user_id: str, session_id: Optional[str],
        requested_agent_id: Optional[str], action_type: str
    ):
        """
        PROPERTY: Agent resolution returns valid context structure

        STRATEGY: st.tuples(user_id, session_id, requested_agent_id, action_type)

        INVARIANT: Returned context has 'resolution_path' list with at least one entry

        RADII: 200 examples explores all resolution paths

        VALIDATED_BUG: None found (invariant holds)
        """
        resolver = AgentContextResolver(db_session)
        agent, context = await resolver.resolve_agent_for_request(
            user_id=str(user_id),
            session_id=session_id,
            requested_agent_id=requested_agent_id,
            action_type=action_type
        )
        assert isinstance(context, dict), "Context must be dict"
        assert "resolution_path" in context, "Context must contain resolution_path"
        assert isinstance(context["resolution_path"], list), "resolution_path must be list"
        assert len(context["resolution_path"]) > 0, "resolution_path must be non-empty"

    @pytest.mark.asyncio
    @given(
        user_id=uuids(),
        session_id=sampled_from([None, "session-123", "nonexistent-session"]),
        requested_agent_id=sampled_from([None, "agent-456", "invalid-agent"]),
        action_type=sampled_from(["chat", "stream_chat", "delete", "execute", "present_chart", "present_markdown"])
    )
    @settings(**HYPOTHESIS_SETTINGS_CRITICAL)
    async def test_resolve_agent_always_returns_context(
        self, db_session, user_id: str, session_id: Optional[str],
        requested_agent_id: Optional[str], action_type: str
    ):
        """
        PROPERTY: Resolution always returns context, never None

        STRATEGY: st.tuples(user_id, session_id, requested_agent_id, action_type)

        INVARIANT: context is never None, even when agent is None

        RADII: 200 examples covering all input combinations

        VALIDATED_BUG: None found (invariant holds)
        """
        resolver = AgentContextResolver(db_session)
        agent, context = await resolver.resolve_agent_for_request(
            user_id=str(user_id),
            session_id=session_id,
            requested_agent_id=requested_agent_id,
            action_type=action_type
        )
        assert context is not None, "Context must never be None"
        assert isinstance(context, dict), "Context must be dict"

    @pytest.mark.asyncio
    @given(
        user_id=uuids(),
        agent_name=text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz')
    )
    @settings(**HYPOTHESIS_SETTINGS_CRITICAL)
    async def test_explicit_agent_id_takes_priority(
        self, db_session, user_id: str, agent_name: str
    ):
        """
        PROPERTY: Explicit agent_id takes priority over session agent

        STRATEGY: Create agent, then resolve with explicit agent_id

        INVARIANT: resolution_path contains "explicit_agent_id"

        RADII: 200 examples with various agent names

        VALIDATED_BUG: None found (invariant holds)
        """
        import uuid as uuid_lib
        from core.models import AgentStatus

        # Create test agent
        agent = AgentRegistry(
            id=str(uuid_lib.uuid4()),
            name=f"TestAgent_{agent_name}",
            description="Test agent for property testing",
            category="test",
            module_path="test",
            class_name="TestAgent",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.5
        )
        db_session.add(agent)
        db_session.commit()

        resolver = AgentContextResolver(db_session)
        resolved_agent, context = await resolver.resolve_agent_for_request(
            user_id=str(user_id),
            session_id=None,
            requested_agent_id=agent.id,
            action_type="chat"
        )

        assert "explicit_agent_id" in context["resolution_path"], \
            f"Resolution path should contain explicit_agent_id, got: {context['resolution_path']}"

    @pytest.mark.asyncio
    @given(
        user_id=uuids(),
        invalid_agent_id=uuids()
    )
    @settings(**HYPOTHESIS_SETTINGS_CRITICAL)
    async def test_invalid_agent_id_falls_back_to_session(
        self, db_session, user_id: str, invalid_agent_id: str
    ):
        """
        PROPERTY: Invalid agent_id falls back to session agent

        STRATEGY: Create session with agent, resolve with invalid agent_id

        INVARIANT: resolution_path contains "explicit_agent_id_not_found" then "session_agent"

        RADII: 200 examples

        VALIDATED_BUG: None found (invariant holds)
        """
        import uuid as uuid_lib
        from core.models import AgentStatus

        # Create session agent
        session_agent = AgentRegistry(
            id=str(uuid_lib.uuid4()),
            name="SessionAgent",
            description="Session agent",
            category="test",
            module_path="test",
            class_name="TestAgent",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.5
        )
        db_session.add(session_agent)

        # Create session with agent in metadata
        session = ChatSession(
            id=str(uuid_lib.uuid4()),
            user_id=str(user_id),
            metadata_json={"agent_id": session_agent.id}
        )
        db_session.add(session)
        db_session.commit()

        resolver = AgentContextResolver(db_session)
        agent, context = await resolver.resolve_agent_for_request(
            user_id=str(user_id),
            session_id=session.id,
            requested_agent_id=str(invalid_agent_id),  # Invalid agent
            action_type="chat"
        )

        assert "explicit_agent_id_not_found" in context["resolution_path"], \
            "Should record that explicit agent was not found"
        assert "session_agent" in context["resolution_path"], \
            "Should fall back to session agent"

    @pytest.mark.asyncio
    @given(
        user_id=uuids(),
        agent_name=text(min_size=1, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz')
    )
    @settings(**HYPOTHESIS_SETTINGS_CRITICAL)
    async def test_session_agent_resolution(
        self, db_session, user_id: str, agent_name: str
    ):
        """
        PROPERTY: Session agent resolved from metadata

        STRATEGY: Create ChatSession with agent_id in metadata_json

        INVARIANT: resolution_path contains "session_agent"

        RADII: 200 examples

        VALIDATED_BUG: None found (invariant holds)
        """
        import uuid as uuid_lib
        from core.models import AgentStatus

        # Create session agent
        session_agent = AgentRegistry(
            id=str(uuid_lib.uuid4()),
            name=f"SessionAgent_{agent_name}",
            description="Session agent",
            category="test",
            module_path="test",
            class_name="TestAgent",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.5
        )
        db_session.add(session_agent)

        # Create session with agent in metadata
        session = ChatSession(
            id=str(uuid_lib.uuid4()),
            user_id=str(user_id),
            metadata_json={"agent_id": session_agent.id}
        )
        db_session.add(session)
        db_session.commit()

        resolver = AgentContextResolver(db_session)
        agent, context = await resolver.resolve_agent_for_request(
            user_id=str(user_id),
            session_id=session.id,
            requested_agent_id=None,
            action_type="chat"
        )

        assert "session_agent" in context["resolution_path"], \
            f"Resolution path should contain session_agent, got: {context['resolution_path']}"
        assert agent is not None, "Should resolve session agent"

    @pytest.mark.asyncio
    @given(
        user_id=uuids(),
        session_id=uuids()
    )
    @settings(**HYPOTHESIS_SETTINGS_IO)
    async def test_nonexistent_session_falls_back_to_system_default(
        self, db_session, user_id: str, session_id: str
    ):
        """
        PROPERTY: Nonexistent session falls back to system default

        STRATEGY: Resolve with nonexistent session_id

        INVARIANT: resolution_path contains "no_session_agent" then "system_default"

        RADII: 50 examples (database operation)

        VALIDATED_BUG: None found (invariant holds)
        """
        resolver = AgentContextResolver(db_session)
        agent, context = await resolver.resolve_agent_for_request(
            user_id=str(user_id),
            session_id=str(session_id),  # Nonexistent session
            requested_agent_id=None,
            action_type="chat"
        )

        assert "no_session_agent" in context["resolution_path"], \
            "Should record that session has no agent"
        assert "system_default" in context["resolution_path"], \
            "Should fall back to system default"

    @pytest.mark.asyncio
    @given(user_id=uuids())
    @settings(**HYPOTHESIS_SETTINGS_IO)
    async def test_no_inputs_creates_system_default(
        self, db_session, user_id: str
    ):
        """
        PROPERTY: No inputs creates system default agent

        STRATEGY: Resolve with session_id=None, requested_agent_id=None

        INVARIANT: resolution_path contains ["system_default"]

        RADII: 50 examples (database operation)

        VALIDATED_BUG: None found (invariant holds)
        """
        resolver = AgentContextResolver(db_session)
        agent, context = await resolver.resolve_agent_for_request(
            user_id=str(user_id),
            session_id=None,
            requested_agent_id=None,
            action_type="chat"
        )

        assert "system_default" in context["resolution_path"], \
            "Should create system default agent"
        assert agent is not None, "Should resolve system default agent"

    @pytest.mark.asyncio
    @given(
        user_id=uuids(),
        invalid_agent_id=uuids(),
        invalid_session_id=uuids()
    )
    @settings(**HYPOTHESIS_SETTINGS_IO)
    async def test_all_resolution_paths_exhausted(
        self, db_session, user_id: str, invalid_agent_id: str, invalid_session_id: str
    ):
        """
        PROPERTY: All paths exhausted creates system default

        STRATEGY: Invalid agent, invalid session, verify system_default created

        INVARIANT: Returns valid agent (Chat Assistant created)

        RADII: 50 examples (database operation)

        VALIDATED_BUG: None found (invariant holds)
        """
        resolver = AgentContextResolver(db_session)
        agent, context = await resolver.resolve_agent_for_request(
            user_id=str(user_id),
            session_id=str(invalid_session_id),  # Invalid session
            requested_agent_id=str(invalid_agent_id),  # Invalid agent
            action_type="chat"
        )

        assert agent is not None, "Should create system default agent when all paths exhausted"
        assert "system_default" in context["resolution_path"], \
            "Should fall back to system default"

    @pytest.mark.asyncio
    @given(
        user_id=uuids(),
        session_id=sampled_from([None, "session-123", "nonexistent-session"]),
        requested_agent_id=sampled_from([None, "agent-456", "invalid-agent"]),
        action_type=sampled_from(["chat", "stream_chat", "delete", "execute"])
    )
    @settings(**HYPOTHESIS_SETTINGS_CRITICAL)
    async def test_resolution_context_contains_all_inputs(
        self, db_session, user_id: str, session_id: Optional[str],
        requested_agent_id: Optional[str], action_type: str
    ):
        """
        PROPERTY: Resolution context contains all input parameters

        STRATEGY: All input parameters reflected in context

        INVARIANT: context has user_id, session_id, requested_agent_id, action_type, resolved_at

        RADII: 200 examples

        VALIDATED_BUG: None found (invariant holds)
        """
        resolver = AgentContextResolver(db_session)
        agent, context = await resolver.resolve_agent_for_request(
            user_id=str(user_id),
            session_id=session_id,
            requested_agent_id=requested_agent_id,
            action_type=action_type
        )

        assert context["user_id"] == str(user_id), "Context should contain user_id"
        assert context["session_id"] == session_id, "Context should contain session_id"
        assert context["requested_agent_id"] == requested_agent_id, \
            "Context should contain requested_agent_id"
        assert context["action_type"] == action_type, "Context should contain action_type"
        assert "resolved_at" in context, "Context should contain resolved_at timestamp"

    @pytest.mark.asyncio
    @given(
        user_id=uuids(),
        action_type=sampled_from([
            "chat", "stream_chat", "delete", "execute",
            "present_chart", "present_markdown", "present_form",
            "browser_automate", "device_capture"
        ])
    )
    @settings(**HYPOTHESIS_SETTINGS_CRITICAL)
    async def test_action_type_variations(
        self, db_session, user_id: str, action_type: str
    ):
        """
        PROPERTY: Action type variations stored correctly

        STRATEGY: sampled_from various action types

        INVARIANT: Action type stored in context correctly

        RADII: 200 examples covering all action types

        VALIDATED_BUG: None found (invariant holds)
        """
        resolver = AgentContextResolver(db_session)
        agent, context = await resolver.resolve_agent_for_request(
            user_id=str(user_id),
            session_id=None,
            requested_agent_id=None,
            action_type=action_type
        )

        assert context["action_type"] == action_type, \
            f"Action type should be {action_type}, got {context['action_type']}"
        assert isinstance(context["action_type"], str), "Action type should be string"
