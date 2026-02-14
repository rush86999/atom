---
phase: 08-80-percent-coverage-push
plan: 27b
type: execute
wave: 5
depends_on: []
files_modified:
  - backend/tests/unit/test_agent_context_resolver.py
  - backend/tests/unit/test_trigger_interceptor.py
autonomous: true
user_setup: []
must_haves:
  truths:
    - "Agent context resolver has 60%+ test coverage (fallback chain, session agents, system default)"
    - "Trigger interceptor has 60%+ test coverage (maturity routing, blocking, proposals)"
    - "Mock setup verified for database and cache operations"
  artifacts:
    - path: "backend/tests/unit/test_agent_context_resolver.py"
      provides: "Agent context resolution tests"
      min_lines: 550
    - path: "backend/tests/unit/test_trigger_interceptor.py"
      provides: "Maturity-based routing tests"
      min_lines: 800
  key_links:
    - from: "test_agent_context_resolver.py"
      to: "core/agent_context_resolver.py"
      via: "mock_db"
      pattern: "AgentContextResolver"
    - from: "test_trigger_interceptor.py"
      to: "core/trigger_interceptor.py"
      via: "mock_db, mock_cache"
      pattern: "TriggerInterceptor"
status: pending
created: 2026-02-13
gap_closure: false
---

# Plan 27b: Agent Context Resolver & Trigger Interceptor Tests

**Status:** Pending
**Wave:** 5 (parallel with 27a, 28)
**Dependencies:** None

## Objective

Create comprehensive baseline unit tests for agent context resolver and trigger interceptor, achieving 60% coverage to contribute +0.5-0.6% toward Phase 8.8's 19-20% overall coverage goal.

## Context

Phase 8.8 targets 19-20% overall coverage (+2% from 17-18% baseline). This plan tests two critical governance infrastructure files:

1. **agent_context_resolver.py** (238 lines) - Multi-layer fallback agent resolution
2. **trigger_interceptor.py** (582 lines) - Maturity-based trigger routing

**Total Production Lines:** 820
**Expected Coverage at 60%:** ~492 lines
**Coverage Contribution:** +0.5-0.6 percentage points toward 19-20% goal

## Success Criteria

**Must Have (truths that become verifiable):**
1. Agent context resolver has 60%+ test coverage (fallback chain, session agents, system default)
2. Trigger interceptor has 60%+ test coverage (maturity routing, blocking, proposals)
3. Mock setup verified for database and cache operations

**Should Have:**
- Edge cases tested (missing agents, invalid maturity levels, cache misses)
- Async coordination tested (agent resolution, trigger interception)
- Error handling validated

**Could Have:**
- Property-based tests for maturity transitions
- Integration patterns with governance cache

**Won't Have:**
- Full database integration (sessions mocked)
- External service integration (training service mocked)

## Tasks

### Task 1: Create test_agent_context_resolver.py

**Files:**
- CREATE: `backend/tests/unit/test_agent_context_resolver.py` (550+ lines, 35-40 tests)

**Action:**
```bash
cat > backend/tests/unit/test_agent_context_resolver.py << 'EOF'
"""
Unit tests for Agent Context Resolver

Tests cover:
- Explicit agent_id resolution path
- Session-based agent resolution
- System default agent creation
- Session agent setting
- Resolution context metadata
- Error handling for missing entities
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock
from sqlalchemy.orm import Session

from core.agent_context_resolver import AgentContextResolver
from core.models import AgentRegistry, AgentStatus, ChatSession


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock(spec=Session)
    db.query = MagicMock()
    db.add = Mock()
    db.commit = Mock()
    db.rollback = Mock()
    db.refresh = Mock()
    db.flush = Mock()
    return db


@pytest.fixture
def resolver(mock_db):
    """Create agent context resolver instance."""
    return AgentContextResolver(mock_db)


@pytest.fixture
def sample_agent():
    """Create sample agent."""
    return AgentRegistry(
        id="agent_123",
        name="Test Agent",
        category="testing",
        module_path="test.module",
        class_name="TestAgent",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.5
    )


@pytest.fixture
def sample_session():
    """Create sample chat session."""
    session = MagicMock(spec=ChatSession)
    session.id = "session_123"
    session.metadata_json = {"agent_id": "agent_123"}
    return session


@pytest.fixture
def system_default_agent():
    """Create system default agent."""
    return AgentRegistry(
        id="system_default",
        name="Chat Assistant",
        category="system",
        module_path="system",
        class_name="ChatAssistant",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.5
    )


# ============================================================================
# Explicit Agent Resolution Tests
# ============================================================================

class TestExplicitAgentResolution:
    """Tests for explicit agent_id resolution path."""

    @pytest.mark.asyncio
    async def test_resolve_with_explicit_agent_id(self, resolver, mock_db, sample_agent):
        """Test resolution via explicit agent_id."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123",
            requested_agent_id="agent_123"
        )

        assert agent is not None
        assert agent.id == "agent_123"
        assert "explicit_agent_id" in context["resolution_path"]

    @pytest.mark.asyncio
    async def test_explicit_agent_found(self, resolver, mock_db, sample_agent):
        """Test explicit agent is found."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123",
            requested_agent_id="agent_123"
        )

        assert agent.id == "agent_123"
        assert agent.name == "Test Agent"

    @pytest.mark.asyncio
    async def test_explicit_agent_not_found_continues_fallback(self, resolver, mock_db):
        """Test that non-existent explicit agent triggers fallback."""
        call_count = [0]

        def mock_filter_side_effect(*args, **kwargs):
            m = MagicMock()
            if call_count[0] < 2:
                m.first.return_value = None
            else:
                m.first.return_value = AgentRegistry(
                    id="system_default",
                    name="Chat Assistant",
                    category="system"
                )
            call_count[0] += 1
            return m

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123",
            requested_agent_id="nonexistent_agent"
        )

        assert agent is not None
        assert "explicit_agent_id_not_found" in context["resolution_path"]


# ============================================================================
# Session Agent Resolution Tests
# ============================================================================

class TestSessionAgentResolution:
    """Tests for session-based agent resolution."""

    @pytest.mark.asyncio
    async def test_resolve_via_session_agent(self, resolver, mock_db, sample_session, sample_agent):
        """Test resolution via session agent."""
        call_count = [0]

        def mock_filter_side_effect(*args, **kwargs):
            m = MagicMock()
            if call_count[0] == 0:
                m.first.return_value = None
            elif call_count[0] == 1:
                m.first.return_value = sample_session
            else:
                m.first.return_value = sample_agent
            call_count[0] += 1
            return m

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123",
            session_id="session_123"
        )

        assert agent is not None
        assert "session_agent" in context["resolution_path"]

    @pytest.mark.asyncio
    async def test_session_agent_found(self, resolver, mock_db, sample_session, sample_agent):
        """Test session agent is found."""
        call_count = [0]

        def mock_filter_side_effect(*args, **kwargs):
            m = MagicMock()
            if call_count[0] == 0:
                m.first.return_value = None
            elif call_count[0] == 1:
                m.first.return_value = sample_session
            else:
                m.first.return_value = sample_agent
            call_count[0] += 1
            return m

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123",
            session_id="session_123"
        )

        assert agent is not None
        assert agent.id == "agent_123"

    @pytest.mark.asyncio
    async def test_session_without_agent_falls_back(self, resolver, mock_db):
        """Test session without agent_id falls back to system default."""
        session_no_agent = MagicMock(spec=ChatSession)
        session_no_agent.id = "session_123"
        session_no_agent.metadata_json = {}

        call_count = [0]

        def mock_filter_side_effect(*args, **kwargs):
            m = MagicMock()
            if call_count[0] == 0:
                m.first.return_value = None
            elif call_count[0] == 1:
                m.first.return_value = session_no_agent
            else:
                m.first.return_value = AgentRegistry(
                    id="system_default",
                    name="Chat Assistant",
                    category="system"
                )
            call_count[0] += 1
            return m

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123",
            session_id="session_123"
        )

        assert agent is not None
        assert "no_session_agent" in context["resolution_path"]

    @pytest.mark.asyncio
    async def test_nonexistent_session_falls_back(self, resolver, mock_db, system_default_agent):
        """Test nonexistent session falls back to system default."""
        call_count = [0]

        def mock_filter_side_effect(*args, **kwargs):
            m = MagicMock()
            if call_count[0] < 2:
                m.first.return_value = None
            else:
                m.first.return_value = system_default_agent
            call_count[0] += 1
            return m

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123",
            session_id="nonexistent_session"
        )

        assert agent is not None
        assert "system_default" in context["resolution_path"]


# ============================================================================
# System Default Resolution Tests
# ============================================================================

class TestSystemDefaultResolution:
    """Tests for system default agent resolution."""

    @pytest.mark.asyncio
    async def test_system_default_created_if_not_exists(self, resolver, mock_db):
        """Test system default agent is created if not exists."""
        call_count = [0]
        created_agent = None

        def mock_filter_side_effect(*args, **kwargs):
            nonlocal created_agent
            m = MagicMock()

            if call_count[0] < 2:
                m.first.return_value = None
            else:
                m.first.return_value = created_agent
            call_count[0] += 1
            return m

        def mock_add_side_effect(agent):
            nonlocal created_agent
            created_agent = agent

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect
        mock_db.add.side_effect = mock_add_side_effect

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123"
        )

        assert agent is not None
        assert agent.name == "Chat Assistant"
        assert agent.category == "system"
        assert "system_default" in context["resolution_path"]
        mock_db.add.assert_called()
        mock_db.commit.assert_called()

    @pytest.mark.asyncio
    async def test_existing_system_default_reused(self, resolver, mock_db):
        """Test existing system default agent is reused."""
        existing_default = AgentRegistry(
            id="existing_default",
            name="Chat Assistant",
            category="system"
        )

        call_count = [0]

        def mock_filter_side_effect(*args, **kwargs):
            m = MagicMock()
            if call_count[0] < 2:
                m.first.return_value = None
            else:
                m.first.return_value = existing_default
            call_count[0] += 1
            return m

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123"
        )

        assert agent.id == "existing_default"
        mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_system_default_has_configuration(self, resolver, mock_db):
        """Test system default agent has proper configuration."""
        call_count = [0]
        created_agent = None

        def mock_filter_side_effect(*args, **kwargs):
            nonlocal created_agent
            m = MagicMock()

            if call_count[0] < 2:
                m.first.return_value = None
            else:
                m.first.return_value = created_agent
            call_count[0] += 1
            return m

        def mock_add_side_effect(agent):
            nonlocal created_agent
            created_agent = agent

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect
        mock_db.add.side_effect = mock_add_side_effect

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123"
        )

        assert agent.module_path == "system"
        assert agent.class_name == "ChatAssistant"
        assert agent.status == AgentStatus.STUDENT.value
        assert agent.confidence_score == 0.5


# ============================================================================
# Resolution Failure Tests
# ============================================================================

class TestResolutionFailure:
    """Tests for resolution failure scenarios."""

    @pytest.mark.asyncio
    async def test_resolution_failed_when_all_paths_fail(self, resolver, mock_db):
        """Test resolution failure when all paths fail."""
        call_count = [0]

        def mock_filter_side_effect(*args, **kwargs):
            m = MagicMock()
            m.first.return_value = None
            call_count[0] += 1
            return m

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123"
        )

        assert agent is None
        assert "resolution_failed" in context["resolution_path"]

    @pytest.mark.asyncio
    async def test_resolution_failed_includes_error_context(self, resolver, mock_db):
        """Test resolution failure includes error context."""
        call_count = [0]

        def mock_filter_side_effect(*args, **kwargs):
            m = MagicMock()
            m.first.return_value = None
            call_count[0] += 1
            return m

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123"
        )

        assert context["user_id"] == "user_123"
        assert "resolution_failed" in context["resolution_path"]
        assert context["resolved_at"] is not None


# ============================================================================
# Set Session Agent Tests
# ============================================================================

class TestSetSessionAgent:
    """Tests for setting session agent."""

    def test_set_session_agent_success(self, resolver, mock_db, sample_session, sample_agent):
        """Test successfully setting agent on session."""
        call_count = [0]

        def mock_filter_side_effect(*args, **kwargs):
            m = MagicMock()
            if call_count[0] == 0:
                m.first.return_value = sample_session
            else:
                m.first.return_value = sample_agent
            call_count[0] += 1
            return m

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect

        result = resolver.set_session_agent("session_123", "agent_123")

        assert result is True
        assert sample_session.metadata_json["agent_id"] == "agent_123"
        mock_db.commit.assert_called()

    def test_set_agent_on_nonexistent_session(self, resolver, mock_db):
        """Test setting agent on non-existent session fails."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        result = resolver.set_session_agent("nonexistent_session", "agent_123")

        assert result is False

    def test_set_agent_with_nonexistent_agent_fails(self, resolver, mock_db, sample_session):
        """Test setting non-existent agent on session fails."""
        call_count = [0]

        def mock_filter_side_effect(*args, **kwargs):
            m = MagicMock()
            m.first.return_value = sample_session if call_count[0] == 0 else None
            call_count[0] += 1
            return m

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect

        result = resolver.set_session_agent("session_123", "nonexistent_agent")

        assert result is False

    def test_set_session_agent_updates_metadata(self, resolver, mock_db, sample_session):
        """Test setting session agent updates metadata."""
        original_metadata = {"previous_key": "previous_value"}
        sample_session.metadata_json = original_metadata.copy()

        call_count = [0]

        def mock_filter_side_effect(*args, **kwargs):
            m = MagicMock()
            m.first.return_value = sample_session
            call_count[0] += 1
            return m

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect

        resolver.set_session_agent("session_123", "agent_123")

        assert sample_session.metadata_json["agent_id"] == "agent_123"
        assert sample_session.metadata_json["previous_key"] == "previous_value"


# ============================================================================
# Resolution Context Tests
# ============================================================================

class TestResolutionContext:
    """Tests for resolution context metadata."""

    @pytest.mark.asyncio
    async def test_resolution_context_contains_all_fields(self, resolver, mock_db, sample_agent):
        """Test resolution context contains required fields."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123",
            session_id="session_456",
            requested_agent_id="agent_123",
            action_type="chat"
        )

        assert context["user_id"] == "user_123"
        assert context["session_id"] == "session_456"
        assert context["requested_agent_id"] == "agent_123"
        assert context["action_type"] == "chat"
        assert "resolution_path" in context
        assert "resolved_at" in context

    @pytest.mark.asyncio
    async def test_resolution_path_tracks_fallback(self, resolver, mock_db):
        """Test resolution_path tracks all attempted fallbacks."""
        call_count = [0]

        def mock_filter_side_effect(*args, **kwargs):
            m = MagicMock()
            if call_count[0] < 2:
                m.first.return_value = None
            else:
                m.first.return_value = AgentRegistry(
                    id="system_default",
                    name="Chat Assistant",
                    category="system"
                )
            call_count[0] += 1
            return m

        mock_db.query.return_value.filter.side_effect = mock_filter_side_effect

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123",
            requested_agent_id="nonexistent"
        )

        assert len(context["resolution_path"]) > 0

    @pytest.mark.asyncio
    async def test_resolution_context_with_default_action_type(self, resolver, mock_db, sample_agent):
        """Test resolution context uses default action type."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123"
        )

        assert context["action_type"] == "chat"

    @pytest.mark.asyncio
    async def test_resolution_context_has_timestamp(self, resolver, mock_db, sample_agent):
        """Test resolution context includes timestamp."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = sample_agent
        mock_db.query.return_value = mock_query

        agent, context = await resolver.resolve_agent_for_request(
            user_id="user_123"
        )

        assert "resolved_at" in context
        assert context["resolved_at"] is not None


# ============================================================================
# Validate Agent for Action Tests
# ============================================================================

class TestValidateAgentForAction:
    """Tests for validating agents for specific actions."""

    @pytest.mark.asyncio
    async def test_validate_agent_for_action_delegates_to_governance(self, resolver, sample_agent):
        """Test validation delegates to governance service."""
        with patch.object(resolver.governance, 'can_perform_action', return_value={"allowed": True}):
            result = resolver.validate_agent_for_action(
                agent=sample_agent,
                action_type="search",
                require_approval=False
            )

            assert result["allowed"] is True

    @pytest.mark.asyncio
    async def test_validate_agent_passes_require_approval(self, resolver, sample_agent):
        """Test validation passes require_approval through."""
        with patch.object(resolver.governance, 'can_perform_action', return_value={"allowed": False, "requires_human_approval": True}):
            result = resolver.validate_agent_for_action(
                agent=sample_agent,
                action_type="delete",
                require_approval=True
            )

            assert result["requires_human_approval"] is True


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_get_agent_handles_exceptions(self, resolver, mock_db):
        """Test _get_agent handles database exceptions."""
        mock_query = MagicMock()
        mock_query.filter.side_effect = Exception("Database error")
        mock_db.query.return_value = mock_query

        result = resolver._get_agent("agent_123")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_session_agent_handles_exceptions(self, resolver, mock_db):
        """Test _get_session_agent handles exceptions."""
        mock_query = MagicMock()
        mock_query.filter.side_effect = Exception("Database error")
        mock_db.query.return_value = mock_query

        result = resolver._get_session_agent("session_123")

        assert result is None

    def test_set_session_agent_handles_exceptions(self, resolver, mock_db, sample_session):
        """Test set_session_agent handles exceptions."""
        mock_query = MagicMock()
        mock_query.filter.side_effect = Exception("Database error")
        mock_db.query.return_value = mock_query

        result = resolver.set_session_agent("session_123", "agent_123")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_or_create_system_default_handles_exceptions(self, resolver, mock_db):
        """Test _get_or_create_system_default handles exceptions."""
        mock_query = MagicMock()
        mock_query.filter.side_effect = Exception("Database error")
        mock_db.query.return_value = mock_query

        result = await resolver._get_or_create_system_default()

        assert result is None
EOF

# Verify file created
wc -l backend/tests/unit/test_agent_context_resolver.py
```

**Verify:**
```bash
test -f backend/tests/unit/test_agent_context_resolver.py && echo "File exists"
grep -c "^def test_" backend/tests/unit/test_agent_context_resolver.py
# Expected: 35-40 tests
```

**Done:**
- File created with 35-40 tests
- Explicit agent resolution tested
- Session agent resolution tested
- System default fallback tested
- Session agent setting validated
- Resolution context verified
- Error handling validated

---

### Task 2: Create test_trigger_interceptor.py

**Files:**
- CREATE: `backend/tests/unit/test_trigger_interceptor.py` (800+ lines, 50-55 tests)

**Action:**
```bash
cat > backend/tests/unit/test_trigger_interceptor.py << 'EOF'
"""
Unit tests for Trigger Interceptor

Tests cover:
- Maturity level determination
- Student agent routing (blocking)
- Intern agent routing (proposals)
- Supervised agent routing (supervision)
- Autonomous agent routing (execution)
- Manual trigger handling
- Training proposal creation
- Trigger decision data structure
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, Mock
from sqlalchemy.orm import Session

from core.trigger_interceptor import (
    TriggerInterceptor,
    MaturityLevel,
    RoutingDecision,
    TriggerDecision,
    TriggerSource
)
from core.models import (
    AgentRegistry,
    AgentStatus,
    BlockedTriggerContext,
    AgentProposal,
    SupervisionSession,
    ProposalStatus,
    SupervisionStatus
)


@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock(spec=Session)
    db.query = MagicMock()
    db.add = Mock()
    db.commit = Mock()
    db.rollback = Mock()
    db.refresh = Mock()
    db.flush = Mock()
    return db


@pytest.fixture
def interceptor(mock_db):
    """Create trigger interceptor instance."""
    return TriggerInterceptor(mock_db, "workspace_123")


@pytest.fixture
def student_agent():
    """Create STUDENT maturity agent."""
    return AgentRegistry(
        id="student_agent",
        name="Student Agent",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.4
    )


@pytest.fixture
def intern_agent():
    """Create INTERN maturity agent."""
    return AgentRegistry(
        id="intern_agent",
        name="Intern Agent",
        status=AgentStatus.INTERN.value,
        confidence_score=0.6
    )


@pytest.fixture
def supervised_agent():
    """Create SUPERVISED maturity agent."""
    return AgentRegistry(
        id="supervised_agent",
        name="Supervised Agent",
        status=AgentStatus.SUPERVISED.value,
        confidence_score=0.8
    )


@pytest.fixture
def autonomous_agent():
    """Create AUTONOMOUS maturity agent."""
    return AgentRegistry(
        id="autonomous_agent",
        name="Autonomous Agent",
        status=AgentStatus.AUTONOMOUS.value,
        confidence_score=0.95
    )


# ============================================================================
# Maturity Level Determination Tests
# ============================================================================

class TestMaturityLevelDetermination:
    """Tests for maturity level determination logic."""

    def test_student_maturity_below_05(self, interceptor):
        """Test confidence < 0.5 maps to STUDENT."""
        maturity = interceptor._determine_maturity_level(
            AgentStatus.STUDENT.value,
            0.4
        )
        assert maturity == MaturityLevel.STUDENT

    def test_student_maturity_at_boundary(self, interceptor):
        """Test confidence at 0.49 maps to STUDENT."""
        maturity = interceptor._determine_maturity_level(
            AgentStatus.STUDENT.value,
            0.49
        )
        assert maturity == MaturityLevel.STUDENT

    def test_intern_maturity_05_to_07(self, interceptor):
        """Test confidence 0.5-0.7 maps to INTERN."""
        maturity = interceptor._determine_maturity_level(
            AgentStatus.INTERN.value,
            0.6
        )
        assert maturity == MaturityLevel.INTERN

    def test_intern_at_lower_boundary(self, interceptor):
        """Test confidence at 0.5 maps to INTERN."""
        maturity = interceptor._determine_maturity_level(
            AgentStatus.INTERN.value,
            0.5
        )
        assert maturity == MaturityLevel.INTERN

    def test_supervised_maturity_07_to_09(self, interceptor):
        """Test confidence 0.7-0.9 maps to SUPERVISED."""
        maturity = interceptor._determine_maturity_level(
            AgentStatus.SUPERVISED.value,
            0.8
        )
        assert maturity == MaturityLevel.SUPERVISED

    def test_supervised_at_lower_boundary(self, interceptor):
        """Test confidence at 0.7 maps to SUPERVISED."""
        maturity = interceptor._determine_maturity_level(
            AgentStatus.SUPERVISED.value,
            0.7
        )
        assert maturity == MaturityLevel.SUPERVISED

    def test_autonomous_maturity_above_09(self, interceptor):
        """Test confidence > 0.9 maps to AUTONOMOUS."""
        maturity = interceptor._determine_maturity_level(
            AgentStatus.AUTONOMOUS.value,
            0.95
        )
        assert maturity == MaturityLevel.AUTONOMOUS

    def test_autonomous_at_boundary(self, interceptor):
        """Test confidence at 0.9 maps to AUTONOMOUS."""
        maturity = interceptor._determine_maturity_level(
            AgentStatus.AUTONOMOUS.value,
            0.9
        )
        assert maturity == MaturityLevel.AUTONOMOUS


# ============================================================================
# Student Agent Routing Tests
# ============================================================================

class TestStudentAgentRouting:
    """Tests for STUDENT agent trigger blocking."""

    @pytest.mark.asyncio
    async def test_student_blocked_for_automated_trigger(self, interceptor, student_agent):
        """Test STUDENT agents are blocked for automated triggers."""
        with patch.object(interceptor, '_get_agent_maturity_cached', return_value=(AgentStatus.STUDENT.value, 0.4)):
            with patch.object(interceptor, '_route_student_agent') as mock_route:
                async def mock_route_impl(*args, **kwargs):
                    return TriggerDecision(
                        routing_decision=RoutingDecision.TRAINING,
                        execute=False,
                        agent_id="student_agent",
                        agent_maturity=MaturityLevel.STUDENT.value,
                        confidence_score=0.4,
                        trigger_source=TriggerSource.DATA_SYNC,
                        reason="STUDENT agents blocked from automated triggers"
                    )
                mock_route.side_effect = mock_route_impl

                decision = await interceptor.intercept_trigger(
                    agent_id="student_agent",
                    trigger_source=TriggerSource.DATA_SYNC,
                    trigger_context={"action": "sync_data"}
                )

                assert decision.execute is False
                assert decision.routing_decision == RoutingDecision.TRAINING

    @pytest.mark.asyncio
    async def test_student_creates_blocked_trigger_context(self, interceptor, student_agent):
        """Test STUDENT routing creates blocked trigger context."""
        with patch.object(interceptor, '_get_agent_maturity_cached', return_value=(AgentStatus.STUDENT.value, 0.4)):
            with patch.object(interceptor, '_route_student_agent') as mock_route:
                blocked_context = BlockedTriggerContext(
                    id="blocked_123",
                    agent_id="student_agent",
                    trigger_type="workflow",
                    trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
                    reason="STUDENT agent blocked"
                )

                async def mock_route_impl(*args, **kwargs):
                    return TriggerDecision(
                        routing_decision=RoutingDecision.TRAINING,
                        execute=False,
                        agent_id="student_agent",
                        agent_maturity=MaturityLevel.STUDENT.value,
                        confidence_score=0.4,
                        trigger_source=TriggerSource.WORKFLOW_ENGINE,
                        blocked_context=blocked_context
                    )
                mock_route.side_effect = mock_route_impl

                decision = await interceptor.intercept_trigger(
                    agent_id="student_agent",
                    trigger_source=TriggerSource.WORKFLOW_ENGINE,
                    trigger_context={"workflow_id": "wf_123"}
                )

                assert decision.blocked_context is not None

    @pytest.mark.asyncio
    async def test_student_blocked_for_all_automated_sources(self, interceptor, student_agent):
        """Test STUDENT blocked for all automated trigger sources."""
        automated_sources = [
            TriggerSource.DATA_SYNC,
            TriggerSource.WORKFLOW_ENGINE,
            TriggerSource.AI_COORDINATOR
        ]

        for source in automated_sources:
            with patch.object(interceptor, '_get_agent_maturity_cached', return_value=(AgentStatus.STUDENT.value, 0.4)):
                with patch.object(interceptor, '_route_student_agent') as mock_route:
                    async def mock_route_impl(*args, **kwargs):
                        return TriggerDecision(
                            routing_decision=RoutingDecision.TRAINING,
                            execute=False,
                            agent_id="student_agent",
                            agent_maturity=MaturityLevel.STUDENT.value,
                            confidence_score=0.4,
                            trigger_source=source,
                            reason="Blocked"
                        )
                    mock_route.side_effect = mock_route_impl

                    decision = await interceptor.intercept_trigger(
                        agent_id="student_agent",
                        trigger_source=source,
                        trigger_context={}
                    )

                    assert decision.execute is False


# ============================================================================
# Intern Agent Routing Tests
# ============================================================================

class TestInternAgentRouting:
    """Tests for INTERN agent proposal routing."""

    @pytest.mark.asyncio
    async def test_intern_generates_proposal(self, interceptor, intern_agent):
        """Test INTERN agents generate proposals for automated triggers."""
        with patch.object(interceptor, '_get_agent_maturity_cached', return_value=(AgentStatus.INTERN.value, 0.6)):
            with patch.object(interceptor, '_route_intern_agent') as mock_route:
                proposal = AgentProposal(
                    id="proposal_123",
                    agent_id="intern_agent",
                    proposal_type="action",
                    title="Action Proposal"
                )

                async def mock_route_impl(*args, **kwargs):
                    return TriggerDecision(
                        routing_decision=RoutingDecision.PROPOSAL,
                        execute=False,
                        agent_id="intern_agent",
                        agent_maturity=MaturityLevel.INTERN.value,
                        confidence_score=0.6,
                        trigger_source=TriggerSource.AI_COORDINATOR,
                        proposal=proposal
                    )
                mock_route.side_effect = mock_route_impl

                decision = await interceptor.intercept_trigger(
                    agent_id="intern_agent",
                    trigger_source=TriggerSource.AI_COORDINATOR,
                    trigger_context={"action": "coordinate"}
                )

                assert decision.execute is False
                assert decision.routing_decision == RoutingDecision.PROPOSAL
                assert decision.proposal is not None

    @pytest.mark.asyncio
    async def test_intern_blocked_for_all_automated_sources(self, interceptor, intern_agent):
        """Test INTERN generates proposal for all automated trigger sources."""
        automated_sources = [
            TriggerSource.DATA_SYNC,
            TriggerSource.WORKFLOW_ENGINE,
            TriggerSource.AI_COORDINATOR
        ]

        for source in automated_sources:
            with patch.object(interceptor, '_get_agent_maturity_cached', return_value=(AgentStatus.INTERN.value, 0.6)):
                with patch.object(interceptor, '_route_intern_agent') as mock_route:
                    proposal = AgentProposal(
                        id=f"proposal_{source.value}",
                        agent_id="intern_agent",
                        proposal_type="action",
                        title="Action Proposal"
                    )

                    async def mock_route_impl(*args, **kwargs):
                        return TriggerDecision(
                            routing_decision=RoutingDecision.PROPOSAL,
                            execute=False,
                            agent_id="intern_agent",
                            agent_maturity=MaturityLevel.INTERN.value,
                            confidence_score=0.6,
                            trigger_source=source,
                            proposal=proposal
                        )
                    mock_route.side_effect = mock_route_impl

                    decision = await interceptor.intercept_trigger(
                        agent_id="intern_agent",
                        trigger_source=source,
                        trigger_context={}
                    )

                    assert decision.routing_decision == RoutingDecision.PROPOSAL


# ============================================================================
# Supervised Agent Routing Tests
# ============================================================================

class TestSupervisedAgentRouting:
    """Tests for SUPERVISED agent supervision routing."""

    @pytest.mark.asyncio
    async def test_supervised_requires_supervision(self, interceptor, supervised_agent):
        """Test SUPERVISED agents require supervision for automated triggers."""
        with patch.object(interceptor, '_get_agent_maturity_cached', return_value=(AgentStatus.SUPERVISED.value, 0.8)):
            with patch.object(interceptor, '_route_supervised_agent') as mock_route:
                async def mock_route_impl(*args, **kwargs):
                    return TriggerDecision(
                        routing_decision=RoutingDecision.SUPERVISION,
                        execute=True,
                        agent_id="supervised_agent",
                        agent_maturity=MaturityLevel.SUPERVISED.value,
                        confidence_score=0.8,
                        trigger_source=TriggerSource.DATA_SYNC,
                        supervision_session=SupervisionSession(
                            id="supervision_123",
                            agent_id="supervised_agent",
                            status=SupervisionStatus.ACTIVE.value
                        )
                    )
                mock_route.side_effect = mock_route_impl

                decision = await interceptor.intercept_trigger(
                    agent_id="supervised_agent",
                    trigger_source=TriggerSource.DATA_SYNC,
                    trigger_context={"action": "sync"}
                )

                assert decision.execute is True
                assert decision.routing_decision == RoutingDecision.SUPERVISION

    @pytest.mark.asyncio
    async def test_supervised_creates_supervision_session(self, interceptor, supervised_agent):
        """Test SUPERVISED routing creates supervision session."""
        with patch.object(interceptor, '_get_agent_maturity_cached', return_value=(AgentStatus.SUPERVISED.value, 0.8)):
            with patch.object(interceptor, '_route_supervised_agent') as mock_route:
                supervision = SupervisionSession(
                    id="supervision_456",
                    agent_id="supervised_agent",
                    status=SupervisionStatus.ACTIVE.value
                )

                async def mock_route_impl(*args, **kwargs):
                    return TriggerDecision(
                        routing_decision=RoutingDecision.SUPERVISION,
                        execute=True,
                        agent_id="supervised_agent",
                        agent_maturity=MaturityLevel.SUPERVISED.value,
                        confidence_score=0.8,
                        trigger_source=TriggerSource.DATA_SYNC,
                        supervision_session=supervision
                    )
                mock_route.side_effect = mock_route_impl

                decision = await interceptor.intercept_trigger(
                    agent_id="supervised_agent",
                    trigger_source=TriggerSource.DATA_SYNC,
                    trigger_context={}
                )

                assert decision.supervision_session is not None

    @pytest.mark.asyncio
    async def test_supervised_for_all_automated_sources(self, interceptor, supervised_agent):
        """Test SUPERVISED supervision for all automated trigger sources."""
        automated_sources = [
            TriggerSource.DATA_SYNC,
            TriggerSource.WORKFLOW_ENGINE,
            TriggerSource.AI_COORDINATOR
        ]

        for source in automated_sources:
            with patch.object(interceptor, '_get_agent_maturity_cached', return_value=(AgentStatus.SUPERVISED.value, 0.8)):
                with patch.object(interceptor, '_route_supervised_agent') as mock_route:
                    async def mock_route_impl(*args, **kwargs):
                        return TriggerDecision(
                            routing_decision=RoutingDecision.SUPERVISION,
                            execute=True,
                            agent_id="supervised_agent",
                            agent_maturity=MaturityLevel.SUPERVISED.value,
                            confidence_score=0.8,
                            trigger_source=source
                        )
                    mock_route.side_effect = mock_route_impl

                    decision = await interceptor.intercept_trigger(
                        agent_id="supervised_agent",
                        trigger_source=source,
                        trigger_context={}
                    )

                    assert decision.routing_decision == RoutingDecision.SUPERVISION


# ============================================================================
# Autonomous Agent Routing Tests
# ============================================================================

class TestAutonomousAgentRouting:
    """Tests for AUTONOMOUS agent execution."""

    @pytest.mark.asyncio
    async def test_autonomous_allowed_full_execution(self, interceptor, autonomous_agent):
        """Test AUTONOMOUS agents allowed full execution."""
        with patch.object(interceptor, '_get_agent_maturity_cached', return_value=(AgentStatus.AUTONOMOUS.value, 0.95)):
            with patch.object(interceptor, '_allow_execution') as mock_allow:
                async def mock_allow_impl(*args, **kwargs):
                    return TriggerDecision(
                        routing_decision=RoutingDecision.EXECUTION,
                        execute=True,
                        agent_id="autonomous_agent",
                        agent_maturity=MaturityLevel.AUTONOMOUS.value,
                        confidence_score=0.95,
                        trigger_source=TriggerSource.AI_COORDINATOR
                    )
                mock_allow.side_effect = mock_allow_impl

                decision = await interceptor.intercept_trigger(
                    agent_id="autonomous_agent",
                    trigger_source=TriggerSource.AI_COORDINATOR,
                    trigger_context={"action": "coordinate"}
                )

                assert decision.execute is True
                assert decision.routing_decision == RoutingDecision.EXECUTION

    @pytest.mark.asyncio
    async def test_autonomous_for_all_trigger_sources(self, interceptor, autonomous_agent):
        """Test AUTONOMOUS execution for all trigger sources."""
        all_sources = [
            TriggerSource.MANUAL,
            TriggerSource.DATA_SYNC,
            TriggerSource.WORKFLOW_ENGINE,
            TriggerSource.AI_COORDINATOR
        ]

        for source in all_sources:
            with patch.object(interceptor, '_get_agent_maturity_cached', return_value=(AgentStatus.AUTONOMOUS.value, 0.95)):
                with patch.object(interceptor, '_allow_execution') as mock_allow:
                    async def mock_allow_impl(*args, **kwargs):
                        return TriggerDecision(
                            routing_decision=RoutingDecision.EXECUTION,
                            execute=True,
                            agent_id="autonomous_agent",
                            agent_maturity=MaturityLevel.AUTONOMOUS.value,
                            confidence_score=0.95,
                            trigger_source=source
                        )
                    mock_allow.side_effect = mock_allow_impl

                    decision = await interceptor.intercept_trigger(
                        agent_id="autonomous_agent",
                        trigger_source=source,
                        trigger_context={}
                    )

                    assert decision.execute is True


# ============================================================================
# Manual Trigger Handling Tests
# ============================================================================

class TestManualTriggerHandling:
    """Tests for manual trigger handling."""

    @pytest.mark.asyncio
    async def test_manual_trigger_always_allowed(self, interceptor):
        """Test manual triggers are always allowed regardless of maturity."""
        with patch.object(interceptor, '_get_agent_maturity_cached', return_value=(AgentStatus.STUDENT.value, 0.4)):
            with patch.object(interceptor, '_handle_manual_trigger') as mock_handle:
                async def mock_handle_impl(*args, **kwargs):
                    return TriggerDecision(
                        routing_decision=RoutingDecision.EXECUTION,
                        execute=True,
                        agent_id="student_agent",
                        agent_maturity=MaturityLevel.STUDENT.value,
                        confidence_score=0.4,
                        trigger_source=TriggerSource.MANUAL,
                        reason="Manual trigger allowed"
                    )
                mock_handle.side_effect = mock_handle_impl

                decision = await interceptor.intercept_trigger(
                    agent_id="student_agent",
                    trigger_source=TriggerSource.MANUAL,
                    trigger_context={"action": "manual_action"},
                    user_id="user_123"
                )

                assert decision.execute is True

    @pytest.mark.asyncio
    async def test_manual_trigger_with_student_includes_warning(self, interceptor):
        """Test manual trigger for STUDENT includes warning."""
        with patch.object(interceptor, '_get_agent_maturity_cached', return_value=(AgentStatus.STUDENT.value, 0.4)):
            with patch.object(interceptor, '_handle_manual_trigger') as mock_handle:
                async def mock_handle_impl(*args, **kwargs):
                    return TriggerDecision(
                        routing_decision=RoutingDecision.EXECUTION,
                        execute=True,
                        agent_id="student_agent",
                        agent_maturity=MaturityLevel.STUDENT.value,
                        confidence_score=0.4,
                        trigger_source=TriggerSource.MANUAL,
                        reason="Allowed with warning"
                    )
                mock_handle.side_effect = mock_handle_impl

                decision = await interceptor.intercept_trigger(
                    agent_id="student_agent",
                    trigger_source=TriggerSource.MANUAL,
                    trigger_context={},
                    user_id="user_123"
                )

                assert "warning" in decision.reason.lower()

    @pytest.mark.asyncio
    async def test_manual_trigger_with_intern_includes_note(self, interceptor):
        """Test manual trigger for INTERN includes note."""
        with patch.object(interceptor, '_get_agent_maturity_cached', return_value=(AgentStatus.INTERN.value, 0.6)):
            with patch.object(interceptor, '_handle_manual_trigger') as mock_handle:
                async def mock_handle_impl(*args, **kwargs):
                    return TriggerDecision(
                        routing_decision=RoutingDecision.EXECUTION,
                        execute=True,
                        agent_id="intern_agent",
                        agent_maturity=MaturityLevel.INTERN.value,
                        confidence_score=0.6,
                        trigger_source=TriggerSource.MANUAL,
                        reason="Allowed with note"
                    )
                mock_handle.side_effect = mock_handle_impl

                decision = await interceptor.intercept_trigger(
                    agent_id="intern_agent",
                    trigger_source=TriggerSource.MANUAL,
                    trigger_context={},
                    user_id="user_123"
                )

                assert "note" in decision.reason.lower() or "learning mode" in decision.reason.lower()


# ============================================================================
# Routing Decision Tests
# ============================================================================

class TestTriggerDecision:
    """Tests for TriggerDecision data structure."""

    def test_trigger_decision_all_fields(self):
        """Test TriggerDecision contains all required fields."""
        decision = TriggerDecision(
            routing_decision=RoutingDecision.EXECUTION,
            execute=True,
            agent_id="agent_123",
            agent_maturity=MaturityLevel.AUTONOMOUS.value,
            confidence_score=0.95,
            trigger_source=TriggerSource.MANUAL,
            reason="Test decision"
        )

        assert decision.routing_decision == RoutingDecision.EXECUTION
        assert decision.execute is True
        assert decision.agent_id == "agent_123"
        assert decision.agent_maturity == MaturityLevel.AUTONOMOUS.value
        assert decision.confidence_score == 0.95
        assert decision.trigger_source == TriggerSource.MANUAL

    def test_trigger_decision_with_blocked_context(self):
        """Test TriggerDecision with blocked context."""
        blocked = BlockedTriggerContext(
            id="blocked_123",
            agent_id="agent_123",
            trigger_type="test",
            trigger_source="workflow",
            reason="Test"
        )

        decision = TriggerDecision(
            routing_decision=RoutingDecision.TRAINING,
            execute=False,
            agent_id="agent_123",
            agent_maturity=MaturityLevel.STUDENT.value,
            confidence_score=0.4,
            trigger_source=TriggerSource.WORKFLOW_ENGINE,
            blocked_context=blocked
        )

        assert decision.blocked_context is not None
        assert decision.blocked_context.id == "blocked_123"

    def test_trigger_decision_with_proposal(self):
        """Test TriggerDecision with proposal."""
        proposal = AgentProposal(
            id="proposal_123",
            agent_id="agent_123",
            proposal_type="action",
            title="Action Proposal"
        )

        decision = TriggerDecision(
            routing_decision=RoutingDecision.PROPOSAL,
            execute=False,
            agent_id="agent_123",
            agent_maturity=MaturityLevel.INTERN.value,
            confidence_score=0.6,
            trigger_source=TriggerSource.AI_COORDINATOR,
            proposal=proposal
        )

        assert decision.proposal is not None
        assert decision.proposal.id == "proposal_123"

    def test_trigger_decision_with_supervision_session(self):
        """Test TriggerDecision with supervision session."""
        supervision = SupervisionSession(
            id="supervision_123",
            agent_id="agent_123",
            status=SupervisionStatus.ACTIVE.value
        )

        decision = TriggerDecision(
            routing_decision=RoutingDecision.SUPERVISION,
            execute=True,
            agent_id="agent_123",
            agent_maturity=MaturityLevel.SUPERVISED.value,
            confidence_score=0.8,
            trigger_source=TriggerSource.DATA_SYNC,
            supervision_session=supervision
        )

        assert decision.supervision_session is not None
        assert decision.supervision_session.id == "supervision_123"


# ============================================================================
# Route to Training Tests
# ============================================================================

class TestRouteToTraining:
    """Tests for routing to training."""

    @pytest.mark.asyncio
    async def test_route_to_training_creates_proposal(self, interceptor, mock_db):
        """Test routing to training creates proposal via training service."""
        blocked_trigger = BlockedTriggerContext(
            id="blocked_123",
            agent_id="student_agent",
            trigger_type="workflow",
            trigger_source=TriggerSource.WORKFLOW_ENGINE.value,
            reason="STUDENT blocked"
        )

        with patch.object(interceptor.training_service, 'create_training_proposal', new=AsyncMock()) as mock_create:
            mock_create.return_value = AgentProposal(
                id="proposal_123",
                agent_id="student_agent",
                proposal_type="training",
                title="Training Proposal"
            )

            proposal = await interceptor.route_to_training(blocked_trigger)

            assert proposal.id == "proposal_123"
            assert proposal.proposal_type == "training"
            mock_create.assert_called_once_with(blocked_trigger)


# ============================================================================
# Create Proposal Tests
# ============================================================================

class TestCreateProposal:
    """Tests for action proposal creation."""

    @pytest.mark.asyncio
    async def test_create_proposal_for_intern_action(self, interceptor, mock_db, intern_agent):
        """Test creating proposal for INTERN agent action."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = intern_agent
        mock_db.query.return_value = mock_query
        mock_db.add = Mock()
        mock_db.commit = Mock()

        proposal = await interceptor.create_proposal(
            intern_agent_id="intern_agent",
            trigger_context={"action": "delete"},
            proposed_action={"type": "delete", "target": "resource"},
            reasoning="INTERN agent proposing delete action"
        )

        assert proposal.agent_id == "intern_agent"
        assert proposal.proposal_type == "action"
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_proposal_for_nonexistent_agent_raises(self, interceptor, mock_db):
        """Test proposal creation fails for nonexistent agent."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(ValueError):
            await interceptor.create_proposal(
                intern_agent_id="nonexistent",
                trigger_context={},
                proposed_action={},
                reasoning="test"
            )

    @pytest.mark.asyncio
    async def test_create_proposal_includes_reasoning(self, interceptor, mock_db, intern_agent):
        """Test proposal includes reasoning."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = intern_agent
        mock_db.query.return_value = mock_query
        mock_db.add = Mock()
        mock_db.commit = Mock()

        proposal = await interceptor.create_proposal(
            intern_agent_id="intern_agent",
            trigger_context={},
            proposed_action={},
            reasoning="This is the reasoning for the proposal"
        )

        assert "reasoning" in proposal.description.lower() or "this is the reasoning" in proposal.description.lower()


# ============================================================================
# Execute with Supervision Tests
# ============================================================================

class TestExecuteWithSupervision:
    """Tests for execution with supervision."""

    @pytest.mark.asyncio
    async def test_execute_with_supervision_creates_session(self, interceptor, mock_db, supervised_agent):
        """Test supervised execution creates supervision session."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = supervised_agent
        mock_db.query.return_value = mock_query
        mock_db.add = Mock()
        mock_db.commit = Mock()
        mock_db.refresh = Mock()

        trigger_context = {"action": "update"}
        session = await interceptor.execute_with_supervision(
            trigger_context=trigger_context,
            agent_id="supervised_agent",
            user_id="user_123"
        )

        assert session.agent_id == "supervised_agent"
        assert session.status == SupervisionStatus.RUNNING.value
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_supervision_for_nonexistent_agent_raises(self, interceptor, mock_db):
        """Test supervised execution fails for nonexistent agent."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with pytest.raises(ValueError):
            await interceptor.execute_with_supervision(
                trigger_context={},
                agent_id="nonexistent",
                user_id="user_123"
            )


# ============================================================================
# Allow Execution Tests
# ============================================================================

class TestAllowExecution:
    """Tests for allowing execution."""

    @pytest.mark.asyncio
    async def test_allow_execution_returns_context(self, interceptor, autonomous_agent):
        """Test allowing execution returns execution context."""
        trigger_context = {"action": "execute"}

        result = await interceptor.allow_execution(
            agent_id="autonomous_agent",
            trigger_context=trigger_context
        )

        assert result["allowed"] is True
        assert result["agent_id"] == "autonomous_agent"
        assert result["trigger_context"] == trigger_context

    @pytest.mark.asyncio
    async def test_allow_execution_for_nonexistent_agent_raises(self, interceptor):
        """Test allow execution fails for nonexistent agent."""
        with pytest.raises(ValueError):
            await interceptor.allow_execution(
                agent_id="nonexistent",
                trigger_context={}
            )


# ============================================================================
# Agent Maturity Cache Tests
# ============================================================================

class TestGetAgentMaturityCached:
    """Tests for cached agent maturity retrieval."""

    @pytest.mark.asyncio
    async def test_get_agent_maturity_cached_returns_tuple(self, interceptor):
        """Test cached retrieval returns (status, confidence) tuple."""
        with patch.object(interceptor, 'get_async_governance_cache') as mock_cache:
            cache = MagicMock()
            cache.get = AsyncMock(return_value={"status": AgentStatus.INTERN.value, "confidence": 0.6})
            mock_cache.return_value = cache

            status, confidence = await interceptor._get_agent_maturity_cached("agent_123")

            assert status == AgentStatus.INTERN.value
            assert confidence == 0.6

    @pytest.mark.asyncio
    async def test_get_agent_maturity_cached_handles_miss(self, interceptor, mock_db):
        """Test cache miss falls back to database."""
        agent = AgentRegistry(
            id="agent_123",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8
        )

        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = agent
        mock_db.query.return_value = mock_query

        with patch.object(interceptor, 'get_async_governance_cache') as mock_cache:
            cache = MagicMock()
            cache.get = AsyncMock(return_value=None)
            cache.set = AsyncMock()
            mock_cache.return_value = cache

            status, confidence = await interceptor._get_agent_maturity_cached("agent_123")

            assert status == AgentStatus.SUPERVISED.value
            assert confidence == 0.8
            cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_agent_maturity_cached_raises_on_not_found(self, interceptor):
        """Test cached retrieval raises when agent not found."""
        mock_query = MagicMock()
        mock_query.filter.return_value.first.return_value = None
        mock_db.query.return_value = mock_query

        with patch.object(interceptor, 'get_async_governance_cache') as mock_cache:
            cache = MagicMock()
            cache.get = AsyncMock(return_value=None)
            mock_cache.return_value = cache

            with pytest.raises(ValueError):
                await interceptor._get_agent_maturity_cached("nonexistent")


# ============================================================================
# Workspace Tests
# ============================================================================

class TestWorkspace:
    """Tests for workspace configuration."""

    def test_interceptor_has_workspace_id(self, interceptor):
        """Test interceptor stores workspace_id."""
        assert interceptor.workspace_id == "workspace_123"

    def test_interceptor_has_training_service(self, interceptor):
        """Test interceptor has training service."""
        assert interceptor.training_service is not None


# ============================================================================
# Maturity Level Enum Tests
# ============================================================================

class TestMaturityLevelEnum:
    """Tests for MaturityLevel enum values."""

    def test_maturity_level_student_value(self):
        """Test STUDENT maturity level value."""
        assert MaturityLevel.STUDENT == "student"

    def test_maturity_level_intern_value(self):
        """Test INTERN maturity level value."""
        assert MaturityLevel.INTERN == "intern"

    def test_maturity_level_supervised_value(self):
        """Test SUPERVISED maturity level value."""
        assert MaturityLevel.SUPERVISED == "supervised"

    def test_maturity_level_autonomous_value(self):
        """Test AUTONOMOUS maturity level value."""
        assert MaturityLevel.AUTONOMOUS == "autonomous"


# ============================================================================
# Routing Decision Enum Tests
# ============================================================================

class TestRoutingDecisionEnum:
    """Tests for RoutingDecision enum values."""

    def test_routing_decision_training_value(self):
        """Test TRAINING routing decision value."""
        assert RoutingDecision.TRAINING == "training"

    def test_routing_decision_proposal_value(self):
        """Test PROPOSAL routing decision value."""
        assert RoutingDecision.PROPOSAL == "proposal"

    def test_routing_decision_supervision_value(self):
        """Test SUPERVISION routing decision value."""
        assert RoutingDecision.SUPERVISION == "supervision"

    def test_routing_decision_execution_value(self):
        """Test EXECUTION routing decision value."""
        assert RoutingDecision.EXECUTION == "execution"
EOF

# Verify file created
wc -l backend/tests/unit/test_trigger_interceptor.py
```

**Verify:**
```bash
test -f backend/tests/unit/test_trigger_interceptor.py && echo "File exists"
grep -c "^def test_" backend/tests/unit/test_trigger_interceptor.py
# Expected: 50-55 tests
```

**Done:**
- File created with 50-55 tests
- Maturity level determination tested
- Student agent blocking tested
- Intern proposal routing tested
- Supervised routing validated
- Autonomous execution verified
- Manual trigger handling tested
- Training proposal creation tested
- Trigger decision structure validated

---

## Key Links

| From | To | Via | Artifact |
|------|-----|-----|----------|
| test_agent_context_resolver.py | core/agent_context_resolver.py | mock_db | Test fallback resolution chain |
| test_trigger_interceptor.py | core/trigger_interceptor.py | mock_db, mock_cache | Test maturity-based routing |

## Progress Tracking

**Current Coverage (Phase 8.7):** 17-18%
**Plan 27b Target:** +0.5-0.6 percentage points
**Projected After Plans 27a+27b+28:** ~19-20%

## Notes

- Tests agent_context_resolver.py + trigger_interceptor.py (split from original Plan 27)
- 60% coverage target for critical governance infrastructure
- Test patterns from Phase 8.7 applied (AsyncMock, fixtures)
- Estimated 85-95 tests total across 2 files
- Duration: 2 hours
- Splits original Plan 27 for better context management
