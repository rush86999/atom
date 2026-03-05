# Phase 115: Agent Execution Coverage - Research

**Researched:** 2026-03-01
**Domain:** Python Backend Test Coverage (pytest, FastAPI endpoints)
**Confidence:** HIGH

## Summary

Phase 115 aims to achieve 60%+ coverage for `atom_agent_endpoints.py`, the main agent execution orchestrator with **2042 lines** and **26 endpoint/handler functions**. **Critical discovery from baseline**: This file currently has **9.06% coverage (94/774 executable lines)**, ranking as the **#2 lowest coverage file** in the entire backend, with a **-216 line gap** to reach the 60% target.

The file contains the core agent chat system including:
- **Session management** (list, create, get history) - 3 endpoints
- **Chat endpoint** (non-streaming) with intent classification - 1 endpoint
- **Streaming chat endpoint** with governance integration - 1 endpoint
- **Intent handlers** (workflow, calendar, email, tasks, finance, CRM) - 18+ handlers
- **Helper functions** (save_chat_interaction, classify_intent_with_llm) - 2+ functions

**Primary blocker identified**: Existing tests in `test_atom_agent_endpoints.py` (736 lines) cover only basic endpoint initialization and session management. Missing coverage includes:
1. **Streaming endpoint governance flow** (lines 1638-1917) - Agent resolution, governance checks, execution tracking
2. **Intent classification with LLM** (lines 620-747) - BYOK provider selection, fallback logic
3. **Workflow orchestration handlers** (lines 852-1057) - create, run, schedule workflows
4. **CRM, calendar, email handlers** (lines 1062-1269) - 9+ integration handlers
5. **Error handling paths** - All exception handling blocks

**Primary recommendation**: Follow Phase 112's proven pattern: Write 30-40 focused tests covering the **streaming governance flow** (highest priority), **workflow execution**, and **intent classification**. Use `AsyncMock` for streaming, `Mock(spec=Session)` for database, and `TestClient` for FastAPI endpoints.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 7.4+ | Test runner | Industry standard for Python testing, superior fixture system |
| pytest-cov | 4.1+ | Coverage plugin | Official pytest integration, branch coverage support |
| pytest-asyncio | 0.21+ | Async test support | Required for testing async endpoint handlers |
| FastAPI TestClient | 0.104+ | Endpoint testing | Built-in FastAPI testing utility, ASGI support |
| unittest.mock | stdlib | Mocking framework | Python standard library, AsyncMock support |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-mock | 3.12+ | Mock fixtures | Cleaner mock API than unittest.mock (optional) |
| factory-boy | 3.3+ | Test data | AgentFactory, ChatSessionFactory exist in `/tests/factories/` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| FastAPI TestClient | httpx | TestClient handles ASGI apps, lifespan, dependency injection |
| unittest.mock AsyncMock | asynctest | AsyncMock is stdlib in Python 3.8+, asynctest deprecated |

**Installation:**
```bash
# All dependencies already installed in backend/
pip install pytest pytest-cov pytest-asyncio
```

## Architecture Patterns

### Recommended Test Structure
```
backend/tests/unit/agent_execution/
├── test_atom_agent_endpoints_coverage.py  # NEW: 30-40 tests for coverage
│   ├── TestStreamingGovernanceFlow       # Streaming + governance tests
│   ├── TestWorkflowExecutionHandlers      # Workflow orchestration tests
│   ├── TestIntentClassification          # LLM intent classification tests
│   ├── TestSessionManagement             # Session CRUD tests (extend existing)
│   └── TestErrorHandling                 # Exception handling tests
├── conftest.py                           # Shared fixtures
└── __init__.py
```

### Pattern 1: FastAPI TestClient for Endpoint Testing
**What:** Use `TestClient` to make HTTP requests to FastAPI routers
**When to use:** Testing REST endpoints (POST /chat, GET /sessions, etc.)
**Example:**
```python
# Source: Existing test_atom_agent_endpoints.py pattern (lines 43-54, 149-170)
from fastapi.testclient import TestClient
from fastapi import FastAPI

@pytest.fixture
def app():
    """Create a test FastAPI app"""
    app = FastAPI()
    app.include_router(router)
    return app

@pytest.fixture
def client(app):
    """Create a test client"""
    return TestClient(app)

@patch('core.atom_agent_endpoints.get_chat_session_manager')
def test_list_sessions_success(mock_get_session, client):
    """Test listing sessions successfully"""
    # Setup mocks
    mock_session_mgr = MagicMock()
    mock_session_mgr.list_user_sessions = MagicMock(return_value=[
        {"session_id": "sess1", "last_active": "2026-02-12T10:00:00Z"}
    ])
    mock_get_session.return_value = mock_session_mgr

    # Make HTTP request
    response = client.get("/api/atom-agent/sessions?user_id=test-user")

    # Assert response
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
```

### Pattern 2: AsyncMock for Streaming and Async Handlers
**What:** Use `AsyncMock` for mocking async methods (LLM streaming, WebSocket)
**When to use:** Testing async endpoint handlers (`chat_stream_agent`, `classify_intent_with_llm`)
**Example:**
```python
# Source: Phase 112 governance pattern + integration test pattern
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
@patch('core.atom_agent_endpoints.AgentContextResolver')
@patch('core.atom_agent_endpoints.AgentGovernanceService')
@patch('core.atom_agent_endpoints.BYOKHandler')
async def test_streaming_with_governance_allowed(
    mock_byok,
    mock_governance,
    mock_resolver,
    app
):
    """Test streaming endpoint allows execution when governance check passes"""
    # Setup agent resolver
    mock_agent = MagicMock()
    mock_agent.id = "test-agent"
    mock_agent.name = "TestAgent"

    mock_resolver_instance = AsyncMock()
    mock_resolver_instance.resolve_agent_for_request = AsyncMock(
        return_value=(mock_agent, {"source": "explicit"})
    )
    mock_resolver.return_value = mock_resolver_instance

    # Setup governance check to allow
    mock_governance_instance = MagicMock()
    mock_governance_instance.can_perform_action.return_value = {
        "allowed": True,
        "reason": "Agent has AUTONOMOUS maturity"
    }
    mock_governance.return_value = mock_governance_instance

    # Setup BYOK streaming
    byok_instance = MagicMock()
    async def mock_stream(**kwargs):
        tokens = ["Hello", " ", "world"]
        for token in tokens:
            yield token
    byok_instance.stream_completion = mock_stream
    byok_instance.analyze_query_complexity.return_value = QueryComplexity.SIMPLE
    byok_instance.get_optimal_provider.return_value = ("openai", "gpt-4")
    mock_byok.return_value = byok_instance

    # Make request (Note: TestClient doesn't support async, need to call function directly)
    from core.atom_agent_endpoints import chat_stream_agent
    request = ChatRequest(
        message="Hello",
        user_id="test-user",
        agent_id="test-agent"
    )

    response = await chat_stream_agent(request)

    assert response["success"] is True
    assert "message_id" in response
```

### Pattern 3: Mock(spec=Session) for Database Operations
**What:** Use spec-based mocks for SQLAlchemy sessions
**When to use:** Unit tests that don't need real database
**Example:**
```python
# Source: Phase 112 governance pattern (lines 36-94)
from sqlalchemy.orm import Session
from unittest.mock import Mock, MagicMock

@pytest.fixture
def mock_db():
    """Create mock database session"""
    db = Mock(spec=Session)
    db.add = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    db.rollback = Mock()

    # Mock query chain
    mock_query = Mock()
    db.query = Mock(return_value=mock_query)
    mock_query.filter = Mock(return_value=mock_query)
    mock_query.first = Mock(return_value=None)

    return db

def test_agent_execution_record_created(mock_db):
    """Test AgentExecution record is created on streaming start"""
    # Setup query to return None (no existing execution)
    mock_db.query.return_value.filter.return_value.first.return_value = None

    # Test execution tracking in streaming flow
    # ...call streaming endpoint...

    # Verify AgentExecution was added
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
```

### Pattern 4: Fixture Composition for Complex Mocks
**What:** Compose fixtures from simple mocks to complex test scenarios
**When to use:** Tests requiring realistic agent + governance + LLM setup
**Example:**
```python
# Source: Integration test pattern (test_agent_execution_orchestration.py)
@pytest.fixture
def mock_autonomous_agent(mock_db):
    """Create AUTONOMOUS agent in database"""
    agent = AgentRegistry(
        id="test_autonomous_agent",
        name="TestAutonomousAgent",
        category="testing",
        status="autonomous",
        description="Test autonomous agent",
        module_path="test.agent",
        class_name="TestAgent"
    )
    mock_db.add(agent)
    mock_db.commit()
    mock_db.refresh(agent)
    return agent

@pytest.fixture
def mock_agent_resolver(mock_autonomous_agent):
    """Mock agent context resolver"""
    resolver = MagicMock()
    resolver.resolve_agent_for_request = AsyncMock(
        return_value=(mock_autonomous_agent, {"resolution_path": ["explicit_agent_id"]})
    )
    resolver.return_value.can_perform_action.return_value = {
        "allowed": True,
        "reason": "AUTONOMOUS agent"
    }
    return resolver

# Test uses composed fixtures
async def test_full_governance_flow(mock_agent_resolver, mock_db):
    """Test complete governance flow from request to execution"""
    # Fixtures provide realistic agent + resolver setup
    # Test focuses on governance logic
```

### Anti-Patterns to Avoid
- **❌ Using real database in unit tests:** Makes tests slow and brittle
  - **Do instead:** Use `Mock(spec=Session)` for pure logic tests
- **❌ Not mocking async methods:** Tests hang when calling async without await
  - **Do instead:** Always use `AsyncMock` for async method mocks
- **❌ Hardcoded test data:** Makes tests brittle
  - **Do instead:** Use factories (`AgentFactory()`) with random data
- **❌ Ignoring TestClient limitations:** TestClient doesn't support async endpoints
  - **Do instead:** Call async functions directly with `await` or use `httpx.AsyncClient`

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP client testing | Custom requests with httpx | `TestClient` from FastAPI | Handles ASGI, lifespan, dependency injection, route mounting |
| Async mocking | Custom async mock classes | `AsyncMock` from unittest.mock | Stdlib support, proper await handling |
| Database test data | Manual object creation | Factory Boy factories | `AgentFactory()` already exists, handles relationships |
| Coverage measurement | Custom coverage scripts | `pytest --cov=core.atom_agent_endpoints --cov-report=term-missing` | Standard format, missing line reports, HTML generation |
| Test isolation | Manual transaction rollback | `pytest fixtures` with yield | Automatic cleanup, even on test failure |

**Key insight:** FastAPI's TestClient and unittest.mock provide mature solutions for endpoint testing. Focus test code on agent execution logic, not HTTP infrastructure.

## Common Pitfalls

### Pitfall 1: TestClient Doesn't Support Async Endpoints
**What goes wrong:** Tests using `TestClient` to call async endpoints hang or fail
**Why it happens:** `TestClient` is synchronous, can't properly await async handlers like `chat_stream_agent`
**How to avoid:** Call async endpoint functions directly in tests with `await`
**Warning signs:** Test hangs indefinitely, `RuntimeError: This event loop is already closed`

```python
# WRONG - TestClient with async endpoint
def test_streaming_endpoint(client):
    response = client.post("/api/atom-agent/chat/stream", json={...})  # ❌ Hangs

# CORRECT - Call async function directly
@pytest.mark.asyncio
async def test_streaming_endpoint():
    from core.atom_agent_endpoints import chat_stream_agent
    request = ChatRequest(...)
    response = await chat_stream_agent(request)  # ✅ Works
```

### Pitfall 2: AsyncMock Not Used for Async Methods
**What goes wrong:** Tests fail with `TypeError: object MagicMock can't be used in 'await' expression`
**Why it happens:** Mocking async methods with regular `Mock()` instead of `AsyncMock()`
**How to avoid:** Always use `AsyncMock()` for methods defined with `async def`
**Warning signs:** `TypeError: 'Mock' object is not iterable/awaitable`

```python
# WRONG - Regular Mock for async method
mock_resolver.resolve_agent_for_request = Mock(return_value=(agent, context))
result = await mock_resolver.resolve_agent_for_request(...)  # ❌ Error

# CORRECT - AsyncMock for async method
mock_resolver.resolve_agent_for_request = AsyncMock(return_value=(agent, context))
result = await mock_resolver.resolve_agent_for_request(...)  # ✅ Works
```

### Pitfall 3: BYOK Handler Import Cycles
**What goes wrong:** Tests fail with `ImportError: cannot import name 'BYOKHandler'`
**Why it happens:** `atom_agent_endpoints.py` imports BYOK conditionally, tests patch wrong location
**How to avoid:** Patch at import location (`core.atom_agent_endpoints.BYOKHandler`)
**Warning signs:** ImportError, AttributeError when patching BYOK

```python
# WRONG - Patching definition location
@patch('core.llm.byok_handler.BYOKHandler')  # ❌ atom_agent_endpoints imports from elsewhere

# CORRECT - Patching import location
@patch('core.atom_agent_endpoints.BYOKHandler')  # ✅ Where atom_agent_endpoints imports it
```

### Pitfall 4: Mock Query Chain Incomplete
**What goes wrong:** Tests pass but coverage doesn't increase (query returns None)
**Why it happens:** Mock query chain doesn't return realistic data, endpoint exits early
**How to avoid:** Configure full query chain: `query().filter().first()`
**Warning signs:** Coverage report shows lines still uncovered despite test passing

```python
# WRONG - Incomplete query chain
mock_db.query.return_value.first.return_value = agent  # ❌ Missing filter()

# CORRECT - Complete query chain
mock_query = Mock()
mock_query.filter.return_value.first.return_value = agent
mock_db.query.return_value = mock_query  # ✅ Full chain
```

### Pitfall 5: Agent Execution Record Not Verified
**What goes wrong:** Tests don't verify AgentExecution audit trail is created
**Why it happens:** Tests focus on response, ignore database side effects
**How to avoid:** Always verify `db.add()` and `db.commit()` called for AgentExecution
**Warning signs:** Governance passes but audit trail incomplete

```python
# Test governance check
assert governance_check["allowed"] is True

# ✅ ALSO verify execution tracking
mock_db.add.assert_called_once()  # AgentExecution added
mock_db.commit.assert_called_once()  # Transaction committed

# Verify AgentExecution fields added
call_args = mock_db.add.call_args
execution = call_args[0][0]
assert execution.agent_id == "test-agent"
assert execution.status == "running"
```

## Code Examples

Verified patterns from existing test files:

### Example 1: Session Endpoint Testing (Existing Pattern)
**Source:** `backend/tests/unit/test_atom_agent_endpoints.py` lines 149-170

```python
@patch('core.atom_agent_endpoints.get_chat_session_manager')
def test_list_sessions_success(mock_get_session, client):
    """Test listing sessions successfully"""
    # Setup mocks
    mock_session_mgr = MagicMock()
    mock_session_mgr.list_user_sessions = MagicMock(return_value=[
        {"session_id": "sess1", "last_active": "2026-02-12T10:00:00Z", "metadata": {"title": "Test Session"}}
    ])
    mock_get_session.return_value = mock_session_mgr

    response = client.get("/api/atom-agent/sessions?user_id=test-user")

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "sessions" in data
```

### Example 2: Chat Endpoint with Intent Classification (Existing Pattern)
**Source:** `backend/tests/unit/test_atom_agent_endpoints.py` lines 246-294

```python
@patch('core.atom_agent_endpoints.get_chat_session_manager')
@patch('core.atom_agent_endpoints.get_chat_history_manager')
@patch('core.atom_agent_endpoints.get_chat_context_manager')
@patch('core.atom_agent_endpoints.classify_intent_with_llm')
@patch('core.atom_agent_endpoints.handle_list_workflows')
def test_chat_endpoint_list_workflows(
    self,
    mock_handle_list,
    mock_classify,
    mock_get_context,
    mock_get_history,
    mock_get_session,
    client
):
    """Test chat endpoint for listing workflows"""
    # Setup mocks
    mock_session_mgr = MagicMock()
    mock_session_mgr.create_session = MagicMock(return_value="test-session")
    mock_session_mgr.get_session = MagicMock(return_value=None)
    mock_get_session.return_value = mock_session_mgr

    mock_history_mgr = MagicMock()
    mock_history_mgr.get_session_history = MagicMock(return_value=[])
    mock_get_history.return_value = mock_history_mgr

    mock_context_mgr = AsyncMock()
    mock_context_mgr.resolve_reference = AsyncMock(return_value=None)
    mock_get_context.return_value = mock_context_mgr

    mock_classify.return_value = {"intent": "LIST_WORKFLOWS", "entities": {}}

    mock_handle_list.return_value = {
        "success": True,
        "response": {"message": "Found workflows", "actions": []}
    }

    response = client.post(
        "/api/atom-agent/chat",
        json={"message": "List all workflows", "user_id": "test-user"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "session_id" in data
```

### Example 3: Streaming Endpoint Governance (Integration Test Pattern)
**Source:** `backend/tests/integration/test_agent_execution_orchestration.py` lines 32-100

```python
@pytest.fixture
def mock_autonomous_agent(db_session):
    """Create AUTONOMOUS agent for testing"""
    agent = AgentRegistry(
        id="test_autonomous_agent",
        name="TestAutonomousAgent",
        category="testing",
        status="autonomous",
        description="Test autonomous agent",
        module_path="test.agent",
        class_name="TestAgent"
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    yield agent
    # Cleanup
    db_session.query(AgentExecution).filter(AgentExecution.agent_id == agent.id).delete()
    db_session.query(AgentRegistry).filter(AgentRegistry.id == agent.id).delete()
    db_session.commit()

@pytest.fixture
def mock_byok_handler():
    """Mock BYOK handler for LLM streaming"""
    byok_instance = MagicMock()
    byok_instance.analyze_query_complexity.return_value = QueryComplexity.SIMPLE
    byok_instance.get_optimal_provider.return_value = ("openai", "gpt-4")

    async def mock_stream(**kwargs):
        tokens = ["Hello", " ", "world", "!"]
        for token in tokens:
            yield token

    byok_instance.stream_completion = mock_stream
    return byok_instance
```

### Example 4: Coverage Gap - Streaming Governance Flow
**Current:** Lines 1638-1917 (279 lines) - 0% coverage
**Target:** 60% (167 lines)
**Gap:** 167 lines need tests

**Uncovered code paths:**
```python
# Lines 1675-1720: Agent resolution and governance checks
if governance_enabled and not emergency_bypass:
    with get_db_session() as db:
        resolver = AgentContextResolver(db)
        governance = AgentGovernanceService(db)

        agent, resolution_context = await resolver.resolve_agent_for_request(
            user_id=request.user_id,
            workspace_id=ws_id,
            session_id=request.session_id,
            requested_agent_id=request.agent_id,
            action_type="stream_chat"
        )

        if not agent:
            logger.warning("Agent resolution failed, using system default")

        if agent:
            governance_check = governance.can_perform_action(
                agent_id=agent.id,
                action_type="stream_chat"
            )

            if not governance_check["allowed"]:
                logger.warning(f"Governance blocked: {governance_check['reason']}")
                return {
                    "success": False,
                    "error": f"Agent not permitted to stream chat: {governance_check['reason']}",
                    "governance_check": governance_check
                }

            # Create AgentExecution record for audit trail
            agent_execution = AgentExecution(
                agent_id=agent.id,
                workspace_id=ws_id,
                status="running",
                input_summary=f"Stream chat: {request.message[:200]}...",
                triggered_by="websocket"
            )
            db.add(agent_execution)
            db.commit()
            db.refresh(agent_execution)

            logger.info(f"Agent execution {agent_execution.id} started for agent {agent.name}")

# Solution: Write tests for governance flow
```

**Solution Tests (30-35 tests needed for streaming alone):**
```python
class TestStreamingGovernanceFlow:
    """Test streaming endpoint with agent governance integration"""

    @pytest.mark.asyncio
    @patch('core.atom_agent_endpoints.AgentContextResolver')
    @patch('core.atom_agent_endpoints.AgentGovernanceService')
    @patch('core.atom_agent_endpoints.BYOKHandler')
    @patch('core.atom_agent_endpoints.get_db_session')
    async def test_streaming_with_autonomous_agent_allowed(
        self,
        mock_get_db,
        mock_byok,
        mock_governance,
        mock_resolver
    ):
        """Test AUTONOMOUS agent allowed to stream"""
        # Setup: AUTONOMOUS agent, governance check passes
        # Act: Call chat_stream_agent
        # Assert: Execution record created, streaming succeeds

    @pytest.mark.asyncio
    async def test_streaming_with_student_agent_blocked(self):
        """Test STUDENT agent blocked from streaming"""

    @pytest.mark.asyncio
    async def test_streaming_creates_agent_execution_record(self):
        """Test AgentExecution audit trail created"""

    @pytest.mark.asyncio
    async def test_streaming_records_execution_outcome(self):
        """Test AgentExecution marked completed/failed"""

    @pytest.mark.asyncio
    async def test_streaming_with_governance_disabled(self):
        """Test emergency bypass flag"""
```

### Example 5: Coverage Gap - Intent Classification
**Current:** Lines 620-747 (127 lines) - Minimal coverage
**Target:** 60% (76 lines)
**Gap:** 76 lines need tests

**Uncovered code paths:**
```python
# Lines 629-638: Preemptive knowledge retrieval
knowlege_context = ""
try:
    from core.knowledge_query_endpoints import get_knowledge_query_manager
    km = get_knowledge_query_manager()
    facts = await km.answer_query(f"What relevant facts are there about: {message}")
    if facts and facts.get("relevant_facts"):
        knowlege_context = "\n**Knowledge Context:**\n" + "\n".join([f"- {f}" for f in facts["relevant_facts"][:5]])
except Exception as e:
    logger.warning(f"Failed to fetch preemptive knowledge for intent classification: {e}")

# Lines 698-747: BYOK provider selection
try:
    from core.byok_endpoints import get_byok_manager
    byok = get_byok_manager()

    provider_id = byok.get_optimal_provider("chat")
    api_key = byok.get_api_key(provider_id)

    if not api_key:
        return fallback_intent_classification(message)

    # Call provider-specific APIs
    if provider_id == "openai":
        result = await ai_service.call_openai_api(...)
    elif provider_id == "anthropic":
        result = await ai_service.call_anthropic_api(...)
    # ... other providers
```

**Solution Tests (10-12 tests needed):**
```python
class TestIntentClassification:
    """Test LLM-based intent classification"""

    @pytest.mark.asyncio
    @patch('core.atom_agent_endpoints.get_knowledge_query_manager')
    async def test_intent_classification_with_knowledge_context(self, mock_km):
        """Test knowledge context added to system prompt"""

    @pytest.mark.asyncio
    async def test_intent_classification_fallback_on_error(self):
        """Test fallback classification when LLM fails"""

    @pytest.mark.asyncio
    @patch('core.atom_agent_endpoints.get_byok_manager')
    async def test_intent_classification_openai_provider(self, mock_byok):
        """Test OpenAI provider selected and called"""

    @pytest.mark.asyncio
    async def test_intent_classification_anthropic_provider(self):
        """Test Anthropic provider selected"""
```

### Example 6: Coverage Gap - Workflow Handlers
**Current:** Lines 852-1057 (205 lines) - Minimal coverage
**Target:** 60% (123 lines)
**Gap:** 123 lines need tests

**Handler functions to test:**
- `handle_create_workflow` (lines 852-900)
- `handle_run_workflow` (lines 917-944)
- `handle_schedule_workflow` (lines 946-1030)
- `handle_get_history` (lines 1032-1036)
- `handle_cancel_schedule` (lines 1038-1055)
- `handle_get_status` (lines 1057-1058)

**Solution Tests (8-10 tests needed):**
```python
class TestWorkflowHandlers:
    """Test workflow orchestration handlers"""

    @pytest.mark.asyncio
    @patch('core.atom_agent_endpoints.get_orchestrator')
    @patch('core.atom_agent_endpoints.load_workflows')
    @patch('core.atom_agent_endpoints.save_workflows')
    async def test_create_workflow_generates_and_saves(self, mock_save, mock_load, mock_orchestrator):
        """Test workflow generation and persistence"""

    @pytest.mark.asyncio
    @patch('core.atom_agent_endpoints.AutomationEngine')
    @patch('core.atom_agent_endpoints.load_workflows')
    async def test_run_workflow_executes_engine(self, mock_load, mock_engine):
        """Test workflow execution via AutomationEngine"""

    @pytest.mark.asyncio
    async def test_schedule_workflow_parses_time_expression(self):
        """Test natural language schedule parsing"""

    @pytest.mark.asyncio
    async def test_cancel_schedule_removes_job(self):
        """Test scheduled workflow cancellation"""
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| unittest.TestCase | pytest function-based tests | 2018+ | Superior fixtures, parametrization, plugins |
| Manual async mocking | AsyncMock from unittest.mock | Python 3.8+ | Stdlib support for async testing |
| httpx for FastAPI | TestClient from FastAPI | FastAPI 0.90+ | ASGI support, dependency injection, lifespan |
| Global test files | Module-specific test files | Phase 101 | Faster test execution, clearer organization |
| Manual coverage tracking | pytest-cov --cov-report | Phase 101 | Standardized reporting, HTML output |

**Deprecated/outdated:**
- **unittest.TestCase**: Still works, but pytest fixtures are more composable
- **asynctest library**: Deprecated, use `AsyncMock` from stdlib (Python 3.8+)
- **httpx for FastAPI testing**: `TestClient` handles ASGI apps natively
- **Global test files**: Phase 101 moved to module-specific files (e.g., `test_atom_agent_endoints_coverage.py`)

## Open Questions

1. **How to test WebSocket streaming without real WebSocket server?**
   - What we know: `chat_stream_agent` broadcasts tokens via WebSocket (`ws_manager.broadcast`)
   - What's unclear: Whether to mock `ws_manager.broadcast` or use TestWebSocket
   - Recommendation: Mock `ws_manager.broadcast = AsyncMock()` and verify called with correct tokens

2. **Should we test all 18+ intent handlers or focus on critical ones?**
   - What we know: File has 18+ handlers (workflow, calendar, email, tasks, finance, CRM)
   - What's unclear: Which handlers are most critical for production
   - Recommendation: Test 3-4 core handlers (workflow, task, finance) to reach 60%, add others later

3. **Integration vs. unit test balance for agent execution?**
   - What we know: `test_agent_execution_orchestration.py` exists with integration tests
   - What's unclear: Whether Phase 115 should focus on unit or integration tests
   - Recommendation: **Unit tests first** (faster, isolate code paths), integration tests for complex flows

4. **BYOK handler conditional imports causing patch issues?**
   - What we know: `atom_agent_endpoints.py` imports BYOK conditionally (lines 9-23)
   - What's unclear: Whether tests need to handle ImportError scenarios
   - Recommendation: Patch `core.atom_agent_endpoints.BYOKHandler` at import location, skip ImportError paths

## Sources

### Primary (HIGH confidence)
- **backend/core/atom_agent_endpoints.py** (2042 lines) - Full file read, endpoint structure analyzed
- **backend/tests/unit/test_atom_agent_endpoints.py** (736 lines) - Existing test patterns, 26 test functions
- **backend/tests/integration/test_agent_execution_orchestration.py** - Integration test patterns for execution
- **backend/tests/coverage_reports/COVERAGE_BASELINE_v5.0.md** - Baseline coverage (9.06%, 680/774 lines)
- **Phase 112 verification report** - Proven governance coverage patterns (agent_governance_service at 82.08%)
- **Phase 111 verification report** - Coverage measurement methodology

### Secondary (MEDIUM confidence)
- **pytest documentation** (pytest.org) - Fixture patterns, async testing with pytest-asyncio
- **FastAPI TestClient docs** (fastapi.tiangolo.com) - Endpoint testing best practices
- **unittest.mock documentation** - AsyncMock usage, patch locations

### Tertiary (LOW confidence)
- None - all findings verified from primary sources or official documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pytest, pytest-cov, FastAPI TestClient verified from project
- Architecture: HIGH - Patterns extracted from existing test files with proven success
- Pitfalls: HIGH - All pitfalls identified from integration test failures and Phase 112 experience

**Research date:** 2026-03-01
**Valid until:** 2026-04-01 (30 days - stable testing ecosystem)

## Appendix: Coverage Target Calculation

### atom_agent_endpoints.py (2042 lines total, 774 executable lines)
- **Current coverage:** 9.06% (94 lines covered, 680 missed)
- **Target coverage:** 60% (464 lines covered)
- **Gap:** 216 lines need coverage
- **Tests needed estimate:** 30-40 tests (assuming 15-25 lines per test)

### Function-level breakdown (26 endpoint/handler functions)
1. **Session management** (3 endpoints, ~120 lines)
   - `list_sessions` - Partially covered (existing tests)
   - `create_new_session` - Partially covered (existing tests)
   - `get_session_history` - Partially covered (existing tests)

2. **Chat endpoint** (1 endpoint, ~280 lines)
   - `chat_with_agent` - ~40% coverage (existing tests)
   - Missing: Context resolution, episode triggering, behavioral suggestions

3. **Streaming endpoint** (1 endpoint, ~280 lines)
   - `chat_stream_agent` - **0% coverage** (CRITICAL GAP)
   - Missing: Governance checks, agent resolution, execution tracking, BYOK streaming

4. **Intent classification** (2 functions, ~130 lines)
   - `classify_intent_with_llm` - ~10% coverage
   - `fallback_intent_classification` - ~20% coverage

5. **Workflow handlers** (6 handlers, ~210 lines)
   - `handle_create_workflow` - 0% coverage
   - `handle_run_workflow` - 0% coverage
   - `handle_schedule_workflow` - 0% coverage
   - Others - 0% coverage

6. **Other intent handlers** (12+ handlers, ~250 lines)
   - CRM, calendar, email, tasks, finance, wellness, search, etc.
   - All at 0% coverage

**Test priority order (for reaching 60%):**
1. **Streaming governance flow** (highest impact) - 12-15 tests, ~150 lines
2. **Intent classification** (high complexity) - 8-10 tests, ~80 lines
3. **Workflow execution handlers** (core feature) - 6-8 tests, ~60 lines
4. **Session management edge cases** (extend existing) - 4-5 tests, ~30 lines
5. **Other intent handlers** (sample 3-4) - 3-4 tests, ~40 lines

**Total: 33-42 tests to achieve 60% coverage**

**Test execution strategy:**
- Plan 01: Streaming governance flow (12-15 tests)
- Plan 02: Intent classification (8-10 tests)
- Plan 03: Workflow handlers (6-8 tests)
- Plan 04: Session edge cases + other handlers (7-9 tests)
- Verification: Combined coverage measurement with all tests running
