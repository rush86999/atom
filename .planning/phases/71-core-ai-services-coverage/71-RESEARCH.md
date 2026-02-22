# Phase 71: Core AI Services Coverage - Research

**Researched:** February 22, 2026
**Domain:** Python test coverage for AI/LLM services (FastAPI, SQLAlchemy, Async)
**Confidence:** HIGH

## Summary

Phase 71 aims to achieve 80%+ test coverage for 5 core AI service areas: (1) Agent orchestration, (2) Agent governance and maturity routing, (3) LLM routing and BYOK handler, (4) Autonomous coding agents workflow, and (5) Episode and memory management services. Based on research from Phase 62's failures and successes, and current 2025 testing best practices, this research identifies the proven strategies, tooling stack, and architectural patterns needed to achieve the coverage target effectively.

**Primary Recommendation:** Use a hybrid approach combining (1) integration tests with real SQLite in-memory DB and TestClient for FastAPI routes, (2) property-based tests with Hypothesis for invariants and edge cases, (3) async testing with pytest-asyncio and httpx.AsyncClient, and (4) mock-based testing for LLM provider responses. Focus on high-risk critical paths first (governance, LLM routing, autonomous coding orchestration) with branch coverage enabled (--cov-branch) and daily incremental measurement.

## Key Findings from Phase 62 Research

### Why Phase 62 Failed (Critical Lessons)

| Issue | Impact | Root Cause | Solution |
|-------|--------|------------|----------|
| **Execution Blockers** | 92 tests couldn't execute | Import errors, wrong module paths | Fix blockers FIRST before writing new tests |
| **Unregistered Routes** | 50 tests returned 404 | Routes not registered in main_api_app.py | Register routes or skip API tests |
| **Heavy Mocking** | Tests passed but no coverage gains | Mocked workflows instead of real execution | Use integration tests with real DB/API |
| **Wrong Success Metric** | Focused on test count (567 tests) | Measured quantity, not coverage percentage | Track coverage % after EACH test file |
| **No Incremental Validation** | Issues found after 4 months | Coverage only measured at end | Daily coverage measurement, fix immediately |

**The Smoking Gun:** Phase 62 created ~15,000 test functions across 730 test files but only achieved 17.12% coverage. Research shows this is impossible unless tests aren't executing or covering real code.

### What Actually Works (Research-Backed)

**Test-to-Code Ratio:**
- Industry standard for production Python: 1:1 to 2:1 ratio
- Phase 62 achieved: ~0.14:1 (far below baseline)
- For 80% coverage on 164K LOC: Need ~105K-160K lines of test code

**Testing Pyramid Distribution:**
- 70% Unit Tests (fast, isolated)
- 20% Integration Tests (real DB/API)
- 10% E2E Tests (critical workflows only)

**High-Impact Patterns:**
1. **Parametrized Tests** (@pytest.mark.parametrize): 10x more coverage per test
2. **Property-Based Testing** (Hypothesis): Automated edge case generation
3. **Branch Coverage** (--cov-branch): 15-25% higher vs line-only
4. **Real DB Over Mocks**: Integration tests exercise 2-3x more code

### Quality Gates (TQ-01 through TQ-05)

From 62-RESEARCH.md, these quality standards must be validated:

- **TQ-01 (Independence):** Tests run in random order (pytest-xdist)
- **TQ-02 (Pass Rate):** 98%+ across 3 consecutive runs
- **TQ-03 (Performance):** Full suite <60 minutes
- **TQ-04 (Determinism):** Same results across runs
- **TQ-05 (Coverage Quality):** Branch coverage enabled, behavior-based tests

## Standard Stack

### Core Testing Framework

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | >=7.4.0 | Test runner | Industry standard, plugin ecosystem |
| **pytest-cov** | >=4.1.0 | Coverage plugin | Seamless pytest integration, branch coverage |
| **pytest-asyncio** | >=0.21.0 | Async test support | Required for FastAPI/async services |
| **pytest-mock** | >=3.11.0 | Mocking utilities | Cleaner API than unittest.mock |
| **pytest-xdist** | >=3.5.0 | Parallel execution | Speed up test suite 3-5x |
| **hypothesis** | >=6.92.0 | Property-based testing | Automated edge case generation |

**Installation:**
```bash
pip install pytest>=7.4.0 pytest-cov>=4.1.0 pytest-asyncio>=0.21.0 \
            pytest-mock>=3.11.0 pytest-xdist>=3.5.0 hypothesis>=6.92.0
```

### Async Testing Stack (FastAPI/SQLAlchemy 2.0)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **httpx** | >=0.24.0 | Async HTTP client | Testing FastAPI endpoints asynchronously |
| **AsyncClient** | (from httpx) | Async test client | All async API route tests |
| **AsyncSession** | (SQLAlchemy 2.0) | Async database | Integration tests with real async DB |

**Current Status:** ✅ Already configured in pytest.ini (asyncio_mode = auto)

### LLM Mocking Stack

| Library | Purpose | When to Use |
|---------|---------|-------------|
| **pytest-mock** | Mock LLM API responses | Unit tests for BYOK handler |
| **respx** | HTTP mocking for external APIs | Integration tests for LLM providers |
| **vcrpy** | Record/replay HTTP interactions | E2E tests with recorded LLM responses |

### Coverage Tools

| Tool | Purpose | When to Use |
|------|---------|-------------|
| **pytest-cov** | Coverage plugin for pytest | Default for all coverage measurement |
| **coverage.py** | Standalone coverage tool | CLI workflows, CI/CD scripts |
| **mutmut** | Mutation testing (optional) | Quality gate validation, NOT initial coverage |

**Recommendation:** Use `pytest-cov` with `--cov-branch` for all coverage measurement.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **pytest** | unittest | Less powerful, no parametrization, harder fixtures |
| **pytest-cov** | coverage.py standalone | More config, less seamless integration |
| **hypothesis** | pytest-parametrize only | Manual edge case specification vs automated generation |
| **httpx.AsyncClient** | TestClient (sync) | Doesn't exercise async code paths properly |
| **SQLite in-memory** | Mock DB | Mocks don't test real SQLAlchemy behavior |

## Architecture Patterns

### Recommended Project Structure

Current Atom structure (already follows best practices):
```
backend/tests/
├── unit/                    # Unit tests (fast, isolated)
│   ├── agent/              # Agent orchestration tests
│   ├── governance/         # Governance & maturity routing tests
│   ├── llm/                # LLM routing & BYOK tests
│   ├── episodes/           # Episode & memory tests
│   └── autonomous/         # Autonomous coding component tests
├── integration/            # Integration tests (real DB/API)
│   ├── agent/              # Agent execution orchestration
│   ├── governance/         # Governance integration
│   └── episodes/           # Episode memory integration
├── property_tests/         # Property-based tests (Hypothesis)
│   ├── agent/              # Agent coordination invariants
│   ├── governance/         # Governance cache invariants
│   ├── llm/                # BYOK handler invariants
│   └── episodes/           # Episode lifecycle invariants
└── fixtures/               # Shared test fixtures
    ├── agent_fixtures.py   # Agent test data
    └── episode_fixtures.py # Episode test data
```

### Pattern 1: Async Service Testing (FastAPI + SQLAlchemy 2.0)

**What:** Test async services using httpx.AsyncClient and AsyncSession

**When to use:** All FastAPI route tests, async service integration tests

**Example:**
```python
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from main import app
from core.database import get_async_session

@pytest.fixture
async def db_session():
    """Create async session with automatic rollback."""
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
        finally:
            await session.close()

@pytest.mark.asyncio
async def test_agent_execution_endpoint(db_session):
    """Test agent execution endpoint with real async DB."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        response = await ac.post(
            "/api/v1/agents/test-agent/execute",
            json={"message": "test"},
            params={"user_id": "test-user"}
        )
        assert response.status_code == 200
        assert "execution_id" in response.json()
```

**Source:** [FastAPI 异步测试官方文档](https://fastapi.tiangolo.com/zh/advanced/async-tests/), [FastAPI + SQLAlchemy 2.0 Async 最佳实践](https://www.juejin.cn/post/7570903763722289162)

### Pattern 2: Property-Based Testing (Hypothesis)

**What:** Use Hypothesis to generate test cases automatically and find edge cases

**When to use:** Invariants, algorithm validation, edge case discovery

**Example:**
```python
from hypothesis import given, strategies as st, settings
from hypothesis import HealthCheck

@settings(
    max_examples=50,  # Strategic limit based on Phase 62 findings
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    prompt=st.text(min_size=1, max_size=5000),
    provider=st.sampled_from(["openai", "anthropic", "deepseek", "gemini"])
)
def test_byok_handler_provider_selection(prompt, provider):
    """INVARIANT: BYOK handler selects valid provider for any prompt."""
    handler = BYOKHandler()
    complexity = handler.analyze_query_complexity(prompt)

    # Invariant: Provider must be configured
    assert provider in handler.clients, f"Provider {provider} not configured"

    # Invariant: Complexity must be valid enum
    assert complexity in {
        QueryComplexity.SIMPLE,
        QueryComplexity.MODERATE,
        QueryComplexity.COMPLEX,
        QueryComplexity.ADVANCED
    }
```

**Source:** Phase 62 property tests, existing Atom property_tests/llm/test_byok_handler_invariants.py

### Pattern 3: Parametrized Tests for Edge Cases

**What:** Use @pytest.mark.parametrize to test multiple scenarios in one function

**When to use:** Multiple inputs/outputs, edge case enumeration, status codes

**Example:**
```python
@pytest.mark.parametrize("maturity,action_complexity,expected_allowed", [
    ("STUDENT", 1, True),   # Presentations allowed
    ("STUDENT", 3, False),  # State changes blocked
    ("INTERN", 2, True),    # Streaming allowed
    ("INTERN", 4, False),   # Deletions blocked
    ("AUTONOMOUS", 4, True), # Full access
])
def test_governance_maturity_routing(maturity, action_complexity, expected_allowed):
    """Test governance maturity-based routing for all combinations."""
    governance = AgentGovernanceService(db_session)
    result = governance.check_permission(maturity, action_complexity)
    assert result.allowed == expected_allowed
```

**Source:** Phase 62 research on parametrized tests (10x more coverage per test)

### Pattern 4: LLM Response Mocking

**What:** Mock LLM API responses for deterministic testing

**When to use:** Unit tests for BYOK handler, autonomous coding agents

**Example:**
```python
from unittest.mock import AsyncMock, patch

@pytest.fixture
def mock_llm_response():
    """Mock LLM response for testing."""
    return {
        "choices": [{
            "message": {"content": "Test response"}
        }],
        "usage": {"total_tokens": 100}
    }

@pytest.mark.asyncio
async def test_byok_handler_streaming(mock_llm_response):
    """Test BYOK handler streaming with mock response."""
    with patch('core.llm.byok_handler.AsyncOpenAI') as mock_client:
        mock_client.return_value.chat.completions.create = AsyncMock(
            return_value=mock_llm_response
        )

        handler = BYOKHandler()
        response = await handler.stream_response("test prompt")

        assert response == "Test response"
```

**Source:** [LLM测试方法 2024](https://m.blog.csdn.net/wx17343624830/article/details/143484751)

### Anti-Patterns to Avoid

- **Heavy Mocking:** Don't mock service methods - test real execution
  - Bad: `@patch('core.agent_governance_service.AgentGovernanceService.check_permission')`
  - Good: Use real service with test database

- **Test Count Over Coverage:** Don't measure success by test count
  - Bad: "Created 567 tests"
  - Good: "Increased coverage from 17% to 45%"

- **Monolithic Tests:** Don't test everything in one function
  - Bad: `test_complete_agent_workflow_from_start_to_finish()`
  - Good: `test_agent_resolution()`, `test_governance_check()`, `test_execution()`

- **Ignoring Async:** Don't use sync TestClient for async endpoints
  - Bad: `client = TestClient(app)` (doesn't exercise async paths)
  - Good: `async with AsyncClient(...) as ac:`

- **No Branch Coverage:** Don't skip --cov-branch flag
  - Bad: `pytest --cov=core` (line coverage only)
  - Good: `pytest --cov=core --cov-branch`

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Property-based testing** | Custom random input generators | Hypothesis | Handles shrinking, reproducibility, edge cases automatically |
| **Async test client** | Custom aiohttp setup | httpx.AsyncClient | FastAPI-compatible, handles ASGI transport correctly |
| **Database mocking** | Custom SQLAlchemy mocks | SQLite in-memory DB | Tests real ORM behavior, not mock artifacts |
| **Coverage measurement** | Custom line counting | pytest-cov with --cov-branch | Industry standard, branch coverage, HTML reports |
| **Test parallelization** | Custom threading | pytest-xdist | Proper test isolation, crash recovery |
| **LLM mocking** | Custom response builders | pytest-mock + AsyncMock | Handles async coroutines, cleaner API |
| **Fixture management** | Custom setup/teardown | pytest fixtures (scope=) | Handles lifecycle, dependency injection |

**Key Insight:** Custom testing infrastructure creates maintenance burden and misses edge cases. Use mature, battle-tested libraries.

## Common Pitfalls

### Pitfall 1: Heavy Mocking (Phase 62 Failure)

**What goes wrong:** Tests pass but don't cover real code because everything is mocked

**Why it happens:** Desperate to make tests pass after import errors, developers mock everything

**How to avoid:**
- Use integration tests with real SQLite in-memory DB
- Only mock external dependencies (LLM APIs, external HTTP services)
- Test real execution paths, not mock-verified paths

**Warning signs:** Tests all pass but coverage stays at 17%

### Pitfall 2: Not Measuring Coverage Incrementally

**What goes wrong:** Write 567 tests, wait 4 months, discover coverage is still 17%

**Why it happens:** No feedback loop during test development

**How to avoid:**
- Run coverage after EACH test file: `pytest tests/unit/test_specific_file.py --cov=core --cov-report=term-missing`
- Set realistic thresholds: Start at 25%, increment by 5% per sprint
- Fix execution blockers immediately

**Warning signs:** Test count goes up but coverage percentage doesn't change

### Pitfall 3: Mixing Sync and Async in Tests

**What goes wrong:** Tests don't exercise async code paths, coverage misses async branches

**Why it happens:** Using TestClient (sync) instead of AsyncClient for async endpoints

**How to avoid:**
- Always use `@pytest.mark.asyncio` for async test functions
- Use `httpx.AsyncClient` for FastAPI route tests
- Use `AsyncSession` for SQLAlchemy 2.0 integration tests

**Warning signs:** Async functions showing 0% coverage despite tests "passing"

### Pitfall 4: Property Tests Without max_examples Limit

**What goes wrong:** Hypothesis generates 100+ examples per test, suite takes hours

**Why it happens:** Default Hypothesis settings too aggressive for large codebase

**How to avoid:**
- Strategic max_examples limits: 50 for fast tests, 100 for critical invariants
- Use `@settings(max_examples=50)` decorator
- Phase 62 research validated 50-200 as optimal range

**Warning signs:** Test suite >60 minutes, Hypothesis tests taking most time

### Pitfall 5: Not Testing Error Paths

**What goes wrong:** 80% line coverage but only happy paths tested

**Why it happens:** Developers test success cases, forget error handling

**How to avoid:**
- Parametrized tests with error cases: `@pytest.mark.parametrize("input,expected", [...])`
- Property tests with invalid inputs
- Explicit tests for exceptions: `with pytest.raises(ValueError):`

**Warning signs:** High line coverage, low branch coverage (<70%)

### Pitfall 6: LLM Tests Without Mock Strategy

**What goes wrong:** Tests fail when LLM API is down, costs money, non-deterministic

**Why it happens:** Calling real LLM APIs in tests

**How to avoid:**
- Mock LLM responses with pytest-mock for unit tests
- Use vcrpy to record/replay for integration tests
- Test error handling (timeouts, rate limits) with mocks

**Warning signs:** Flaky tests, API rate limit errors, test suite costs money

## Code Examples

### Example 1: Agent Orchestration Service Coverage

**File:** `backend/core/agent_execution_service.py` (164K LOC in core/)

**Testing Strategy:**
```python
# tests/unit/agent/test_agent_execution_service.py
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_execute_agent_chat_with_governance(db_session):
    """Test agent execution with full governance flow."""
    with patch('core.agent_execution_service.AgentContextResolver') as mock_resolver, \
         patch('core.agent_execution_service.AgentGovernanceService') as mock_governance:

        # Configure mocks
        mock_resolver.return_value.resolve_agent.return_value = agent
        mock_governance.return_value.check_permission.return_value = Permission(allowed=True)

        # Execute
        result = await execute_agent_chat(
            agent_id="test-agent",
            message="Hello",
            user_id="test-user"
        )

        # Verify
        assert result["success"] == True
        assert "execution_id" in result

@pytest.mark.parametrize("maturity,complexity,expected", [
    ("STUDENT", 3, False),  # State changes blocked
    ("INTERN", 2, True),   # Streaming allowed
    ("AUTONOMOUS", 4, True), # Full access
])
def test_governance_maturity_routing(maturity, complexity, expected):
    """Test all maturity/complexity combinations."""
    governance = AgentGovernanceService(db_session)
    result = governance.check_permission(maturity, complexity)
    assert result.allowed == expected
```

### Example 2: LLM BYOK Handler Coverage

**File:** `backend/core/llm/byok_handler.py`

**Testing Strategy:**
```python
# tests/property_tests/llm/test_byok_handler_invariants.py
from hypothesis import given, strategies as st, settings
from hypothesis import HealthCheck

@settings(
    max_examples=50,
    suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    prompt=st.text(min_size=1, max_size=5000),
    provider=st.sampled_from(["openai", "anthropic", "deepseek", "gemini"])
)
def test_provider_selection_invariant(prompt, provider):
    """INVARIANT: Provider selection returns valid provider for any prompt."""
    handler = BYOKHandler()
    complexity = handler.analyze_query_complexity(prompt)

    # Invariant: Selected provider must be available
    selected_provider = handler.select_provider(complexity, [provider])
    assert selected_provider in handler.clients

    # Invariant: Complexity must be valid enum
    assert complexity in {
        QueryComplexity.SIMPLE,
        QueryComplexity.MODERATE,
        QueryComplexity.COMPLEX,
        QueryComplexity.ADVANCED
    }

@pytest.mark.asyncio
async def test_llm_streaming_with_mock():
    """Test LLM streaming with mocked response."""
    with patch('core.llm.byok_handler.AsyncOpenAI') as mock_client:
        mock_response = AsyncMock()
        mock_response.choices = [{"message": {"content": "Test"}}]
        mock_client.return_value.chat.completions.create = AsyncMock(
            return_value=mock_response
        )

        handler = BYOKHandler()
        response = await handler.stream_response("test")

        assert "Test" in response
```

**Source:** Existing property_tests/llm/test_byok_handler_invariants.py

### Example 3: Autonomous Coding Orchestrator Coverage

**File:** `backend/core/autonomous_coding_orchestrator.py`

**Testing Strategy:**
```python
# tests/unit/autonomous/test_orchestrator.py
import pytest
from pathlib import Path

@pytest.fixture
def temp_git_repo(tmp_path):
    """Create temporary Git repository for testing."""
    import subprocess
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path, check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=tmp_path, check=True
    )
    # Create initial commit
    (tmp_path / "test.txt").write_text("initial")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial"],
        cwd=tmp_path, check=True
    )
    return tmp_path

def test_checkpoint_rollback(temp_git_repo):
    """Test checkpoint creation and rollback."""
    git_ops = GitOperations(repo_path=str(temp_git_repo))

    # Create checkpoint
    (temp_git_repo / "file.txt").write_text("new content")
    sha = git_ops.create_commit("Add file")

    # Modify and rollback
    (temp_git_repo / "file.txt").write_text("broken")
    git_ops.reset_to_sha(sha)

    # Verify rollback
    assert (temp_git_repo / "file.txt").read_text() == "new content"

@pytest.mark.asyncio
async def test_orchestrator_workflow_phases(db_session):
    """Test all 8 workflow phases execute in order."""
    with patch('core.autonomous_coding_orchestrator.PlanningAgent'), \
         patch('core.autonomous_coding_orchestrator.CodeGeneratorOrchestrator'):

        orchestrator = AgentOrchestrator(db_session, mock_byok_handler)

        result = await orchestrator.execute_feature(
            feature_request="Add OAuth",
            workspace_id="default"
        )

        # Verify all phases completed
        assert result["status"] == "completed"
        assert len(result["completed_phases"]) == 8
```

**Source:** Existing test_autonomous_coding_orchestrator.py

### Example 4: Episode Segmentation Service Coverage

**File:** `backend/core/episode_segmentation_service.py`

**Testing Strategy:**
```python
# tests/unit/episodes/test_episode_segmentation.py
from hypothesis import given, strategies as st, settings
from datetime import datetime, timedelta

@settings(max_examples=50)
@given(
    messages=st.lists(
        st.builds(ChatMessage, content=st.text(min_size=1, max_size=100))
    )
)
def test_time_gap_detection_invariant(messages):
    """INVARIANT: Time gaps detected correctly for any message sequence."""
    detector = EpisodeBoundaryDetector(lancedb_handler)

    # Add time gaps
    for i, msg in enumerate(messages):
        msg.created_at = datetime.now() + timedelta(minutes=i * 31)

    gaps = detector.detect_time_gap(messages)

    # Invariant: Gap count should be message count - 1
    assert len(gaps) == max(0, len(messages) - 1)

def test_topic_change_boundary():
    """Test topic change detection with semantic similarity."""
    detector = EpisodeBoundaryDetector(lancedb_handler)

    messages = [
        ChatMessage(content="Discussing Python programming", created_at=datetime.now()),
        ChatMessage(content="What about JavaScript?", created_at=datetime.now() + timedelta(minutes=35))
    ]

    changes = detector.detect_topic_changes(messages)

    # Topic change should be detected (different topics)
    assert len(changes) > 0
```

## State of the Art

### Old Approach vs Current Approach (2025)

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **TestClient (sync)** | httpx.AsyncClient | 2023-2024 | Async code paths now tested |
| **Mock.patch everywhere** | Integration tests with real DB | 2024-2025 | 2-3x more coverage per test |
| **Line coverage only** | Branch coverage (--cov-branch) | 2023 | 15-25% higher coverage quality |
| **1000+ max_examples** | Strategic max_examples (50-200) | 2024-2025 | Tests complete in <60 minutes |
| **Test count metric** | Coverage percentage metric | Phase 62 | Focus shifted to actual coverage |
| **Bare except clauses** | Specific exception types | Phase 70 | 98.6% reduction in bare except |

**Deprecated/outdated:**
- **TestClient for async routes:** Doesn't exercise async code paths → Use AsyncClient
- **Mock.patch on service methods:** Tests don't cover real code → Use integration tests
- **Coverage without --cov-branch:** Line coverage misleading → Always use branch coverage
- **pytest.ini "hypothesis_max_examples"**: Deprecated setting → Use @settings(max_examples=N)

## Open Questions

### 1. How to balance integration vs unit tests for 80% coverage target?

**What we know:** Phase 62 research shows integration tests provide 2-3x more coverage per test. Unit tests are faster but miss code paths.

**What's unclear:** Optimal ratio for Atom's specific architecture (164K LOC, 386 files in core/)

**Recommendation:**
- Start with integration tests for critical paths (API routes, service orchestration)
- Add unit tests for pure logic functions (validators, algorithms)
- Target 60% integration, 40% unit for core AI services

### 2. How to test autonomous coding workflow without real LLM calls?

**What we know:** Autonomous coding agents require LLM responses for natural language parsing, code generation, test generation.

**What's unclear:** Mock strategy that provides good coverage without real LLM costs.

**Recommendation:**
- Use pytest-mock AsyncMock for all LLM responses
- Create realistic mock responses covering success/error cases
- Test error handling (timeouts, rate limits, invalid responses)
- Consider vcrpy for recording real LLM responses in E2E tests

### 3. How to handle 146 remaining backref relationships in models.py?

**What we know:** Phase 70 verification found 146 backref relationships still in core/models.py (only 2% fixed). Backref causes AttributeError in SQLAlchemy 2.0.

**What's unclear:** Should Phase 71 fix these before coverage, or work around them?

**Recommendation:**
- Create Phase 71.1 sub-plan to fix remaining backref relationships (blocked by 70 gaps)
- Skip tests for models with backref issues until fixed
- Focus coverage efforts on service layer, not model layer
- Revisit model coverage after backref fixes complete

### 4. What's the current baseline coverage for the 5 target areas?

**What we know:** Overall coverage is 17.12% (Phase 62 baseline). Coverage test running in background.

**What's unclear:** Per-module coverage for agent orchestration, governance, LLM routing, autonomous coding, episodes.

**Recommendation:**
- Run per-module coverage report to establish baseline:
  ```bash
  pytest --cov=core/agent_execution_service --cov=core/agent_governance_service \
         --cov=core/llm/byok_handler --cov=core/autonomous_coding_orchestrator \
         --cov=core/episode_lifecycle_service --cov-report=term-missing
  ```
- Use baseline to prioritize highest-impact test files

## Sources

### Primary (HIGH confidence)

- **Phase 62 Research:** `/Users/rushiparikh/projects/atom/.planning/phases/62-test-coverage-80pct/62-RESEARCH.md` - Comprehensive research on why Phase 62 failed and what strategies actually work for 80% coverage
- **Phase 62 Redesign Summary:** `/Users/rushiparikh/projects/atom/.planning/phases/62-test-coverage-80pct/62-REDESIGN-SUMMARY.md` - Validated 6-week sprint approach with wave-based parallel execution
- **Phase 70 Verification:** `/Users/rushiparikh/projects/atom/.planning/phases/70-runtime-error-fixes/70-VERIFICATION.md` - Runtime error fixes and remaining gaps (backref relationships)
- **pytest Configuration:** `/Users/rushiparikh/projects/atom/backend/pytest.ini` - Current test setup with asyncio_mode, markers, Hypothesis settings
- **Coverage Configuration:** `/Users/rushiparikh/projects/atom/backend/.coveragerc` - Branch coverage enabled, 25% threshold
- **Existing Property Tests:** `/Users/rushiparikh/projects/atom/backend/tests/property_tests/llm/test_byok_handler_invariants.py` - Hypothesis usage patterns with max_examples=50

### Secondary (MEDIUM confidence)

- **FastAPI Async Testing:** [FastAPI 异步测试官方文档](https://fastapi.tiangolo.com/zh/advanced/async-tests/) - AsyncClient usage, async test patterns
- **FastAPI + SQLAlchemy 2.0 Best Practices:** [FastAPI × SQLAlchemy 2.0 Async：从"能跑"到"可压测"的完整工程实践](https://www.juejin.cn/post/7570903763722289162) - AsyncSession integration, transaction rollback
- **Pytest Best Practices 2025:** [Pytest 测试框架：编写简洁高效的 Python 测试](https://m.blog.csdn.net/qq_37956697/article/details/156104858) - Parametrized tests, fixtures
- **LLM Testing Strategies:** [2024年大模型测试的主要方法和策略](https://m.blog.csdn.net/wx17343624830/article/details/143484751) - Mock patterns for LLM responses
- **Coverage Optimization:** [为什么你的FastAPI测试覆盖率总是低得让人想哭？](https://m.blog.csdn.net/qq_42210428/article/details/151062419) - Coverage pitfalls and solutions
- **FastAPI Testing Deep Dive:** [【FastAPI测试利器全解析】：掌握高效自动化测试的5大核心工具与最佳实践](https://m.blog.csdn.net/learnflow/article/details/156511072) - Comprehensive testing toolkit

### Tertiary (LOW confidence - marked for validation)

- **Async Batch Testing:** [FastAPI + aiomysql + pytest 批量异步测试最佳实践总结](https://m.blog.csdn.net/goodparty/article/details/148738667) - Batch async test patterns
- **LLM Evaluation Methods:** [250个LLM 评估基准大盘点](https://m.blog.csdn.net/2501_93968832/article/details/156486489) - LLM testing metrics and benchmarks
- **Test Performance:** [FastAPI, Furious Tests: The Need for Speed](https://dev.to/polakshahar/fastapi-furious-tests-the-need-for-speed-11oi) - Test optimization techniques

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pytest, pytest-cov, pytest-asyncio, hypothesis are industry standards, verified in pyproject.toml
- Architecture: HIGH - Async testing patterns verified in official FastAPI docs, existing test files confirm correct usage
- Pitfalls: HIGH - Phase 62 research provides concrete evidence of failures and solutions
- LLM testing: MEDIUM - Based on 2024 research articles, needs validation with real Atom LLM integration tests
- Autonomous coding testing: MEDIUM - Existing test files provide patterns, but E2E workflow needs validation

**Research date:** February 22, 2026
**Valid until:** March 24, 2026 (30 days - testing stack is stable, but LLM testing practices evolving rapidly)

**Key constraints from prior phases:**
- Phase 62: Must use integration tests over mocks, measure coverage incrementally, use branch coverage
- Phase 70: 146 backref relationships in core/models.py remain unfixed (2% progress only) - may impact model coverage
- Phase 69: Autonomous coding agents have import errors (QUALITY_ENFORCEMENT_ENABLED) - must fix before testing

**Recommended next steps:**
1. Run per-module coverage baseline to identify highest-impact files
2. Fix remaining backref relationships (Phase 71.1) or skip model tests
3. Fix autonomous coding import errors before testing workflow
4. Start with integration tests for critical paths (governance, LLM routing)
5. Add property-based tests for invariants (Hypothesis with max_examples=50)
6. Measure coverage after EACH test file, not at end
