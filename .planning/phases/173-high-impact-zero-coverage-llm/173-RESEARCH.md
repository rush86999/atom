# Phase 173: High-Impact Zero Coverage (LLM) - Research

**Researched:** 2026-03-12
**Domain:** Python testing, pytest, TestClient patterns, LLM service coverage, cognitive tier system
**Confidence:** HIGH

## Summary

Phase 173 requires achieving 75%+ line coverage on high-impact zero-coverage LLM and cognitive tier files. The primary targets are:
1. **LLM service routes** (api/cognitive_tier_routes.py: 601 lines) - Zero coverage
2. **BYOK handler** (core/llm/byok_handler.py: 1,556 lines) - ~15% coverage from Phase 165
3. **Cognitive tier system** (core/llm/cognitive_tier_system.py: 297 lines) - ~40% coverage from Phase 165
4. **LLM integration tests** - End-to-end LLM workflow testing

This phase follows Phase 172 (governance routes) and builds on testing patterns from Phase 165 (governance & LLM service unit tests) and Phase 167 (TestClient-based API route testing). The LLM module files total ~6,371 lines across 8 files, with significant coverage gaps in cognitive tier orchestration, escalation management, and API endpoints.

**Primary recommendation:** Use TestClient-based API route tests for cognitive_tier_routes.py (following Phase 172 patterns), expand BYOK handler unit tests for missing methods (stream_completion, generate_with_cognitive_tier, structured responses), add property-based tests for cognitive tier invariants (tier boundaries, complexity scoring), and create integration tests for end-to-end LLM workflows with mock LLM providers.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | 7.4+ | Test runner and assertions | De facto standard for Python testing with powerful fixture system |
| **pytest-cov** | 4.1+ | Coverage reporting (uses coverage.py under the hood) | Standard for coverage measurement in pytest ecosystem |
| **coverage.py** | 7.3+ | Actual line coverage measurement | Gold standard for Python code coverage—supports branch coverage |
| **TestClient** | FastAPI builtin | API route testing | Official FastAPI testing utility for endpoint testing |
| **httpx** | 0.24+ | Async HTTP client mocking | Required for testing external LLM provider calls (Phase 170 pattern) |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **hypothesis** | 6.92+ | Property-based testing framework | For cognitive tier invariant testing (tier boundaries, classification) |
| **pytest-asyncio** | 0.21+ | Async test support | Required for testing async LLM streaming methods |
| **pytest-mock** | 3.12+ | Mocking fixture | Preferred over unittest.mock for cleaner pytest integration |
| **pytest-mock** | 3.12+ | AsyncMock support | For mocking async LLM client responses |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **TestClient** | **requests** | TestClient is integrated with FastAPI router, no need to run server |
| **httpx.MockTransport** | **responses** | httpx has better async support and is the library used by BYOK handler |
| **hypothesis** | **quickcheck** | Hypothesis has better pytest integration and more powerful strategies |

**Installation:**
```bash
pip install pytest pytest-cov hypothesis pytest-asyncio pytest-mock httpx
```

---

## Architecture Patterns

### Recommended Project Structure

```
backend/tests/
├── api/
│   └── test_cognitive_tier_routes.py        # NEW: TestClient-based API tests (601 lines target)
├── unit/
│   └── llm/
│       ├── test_byok_handler.py             # EXISTING: 23K lines, expand to 75%
│       ├── test_byok_handler_coverage.py    # EXISTING: 47K lines, expand to 75%
│       ├── test_cognitive_tier_coverage.py  # EXISTING: 22K lines, expand to 75%
│       └── test_escalation_manager.py       # NEW: Escalation logic tests
├── integration/
│   └── test_llm_integration.py              # NEW: End-to-end LLM workflows
├── property_tests/
│   └── llm/
│       ├── test_cognitive_tier_invariants.py # EXISTING: Tier boundary invariants
│       └── test_byok_handler_invariants.py  # EXISTING: Provider routing invariants
└── fixtures/
    └── llm_fixtures.py                      # NEW: Shared LLM test data
```

### Pattern 1: TestClient-Based API Route Testing

**What:** Use FastAPI's TestClient to test API endpoints without running a server

**When to use:** Testing FastAPI router endpoints (cognitive_tier_routes.py has 6 endpoints)

**Example:**
```python
# Source: backend/tests/api/test_agent_governance_routes.py (Phase 172)
from fastapi.testclient import TestClient
from api.cognitive_tier_routes import router

@pytest.fixture
def client():
    """TestClient fixture for cognitive tier router."""
    return TestClient(router)

@pytest.fixture
def db_session():
    """Database session fixture."""
    from core.database import get_db
    from sqlalchemy.orm import sessionmaker
    # ... setup test database ...
    return session

class TestTierPreferenceEndpoints:
    def test_get_preferences_default(self, client, db_session):
        """Test GET /api/v1/cognitive-tier/preferences/{workspace_id} returns defaults."""
        response = client.get("/api/v1/cognitive-tier/preferences/test_workspace")
        assert response.status_code == 200
        data = response.json()
        assert data["default_tier"] == "standard"
        assert data["enable_cache_aware_routing"] is True

    def test_create_or_update_preferences(self, client, db_session):
        """Test POST /api/v1/cognitive-tier/preferences/{workspace_id}."""
        request_data = {
            "default_tier": "versatile",
            "monthly_budget_cents": 1000,
            "enable_cache_aware_routing": True
        }
        response = client.post(
            "/api/v1/cognitive-tier/preferences/test_workspace",
            json=request_data
        )
        assert response.status_code == 200
        data = response.json()
        assert data["default_tier"] == "versatile"
        assert data["monthly_budget_cents"] == 1000

    def test_estimate_cost_endpoint(self, client, db_session):
        """Test GET /api/v1/cognitive-tier/estimate-cost."""
        response = client.get(
            "/api/v1/cognitive-tier/estimate-cost?prompt=hello%20world&estimated_tokens=10"
        )
        assert response.status_code == 200
        data = response.json()
        assert "estimates" in data
        assert "recommended_tier" in data
        assert data["estimated_tokens"] == 10
```

### Pattern 2: HTTP Client Mocking for LLM Providers

**What:** Use httpx.MockTransport to mock external LLM API calls

**When to use:** Testing BYOK handler methods that call external LLM providers (OpenAI, Anthropic, DeepSeek, etc.)

**Example:**
```python
# Source: backend/tests/integration/services/test_llm_http_integration_coverage.py (Phase 170)
import httpx
from unittest.mock import AsyncMock, patch

class TestBYOKHandlerExternalCalls:
    @pytest.mark.asyncio
    async def test_generate_response_with_mock_openai(self):
        """Test generate_response() with mocked OpenAI API."""
        # Create mock response
        mock_response = {
            "choices": [{
                "message": {"content": "Test response"}
            }],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20
            }
        }

        # Mock httpx client
        with patch('core.llm.byok_handler.OpenAI') as mock_openai:
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = mock_response
            mock_openai.return_value = mock_client

            handler = BYOKHandler()
            result = await handler.generate_response(
                prompt="Test prompt",
                system_instruction="You are helpful."
            )

            assert result == "Test response"
            mock_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_stream_completion_with_mock_provider(self):
        """Test stream_completion() with mocked async streaming."""
        # Mock streaming chunks
        async def mock_stream():
            yield {"choices": [{"delta": {"content": "Hello"}}]}
            yield {"choices": [{"delta": {"content": " world"}}]}]

        with patch('core.llm.byok_handler.AsyncOpenAI') as mock_async_openai:
            mock_client = AsyncMock()
            mock_client.chat.completions.create.return_value = mock_stream()
            mock_async_openai.return_value = mock_client

            handler = BYOKHandler()
            tokens = []
            async for token in handler.stream_completion(
                messages=[{"role": "user", "content": "test"}],
                model="gpt-4o-mini",
                provider_id="openai"
            ):
                tokens.append(token)

            assert tokens == ["Hello", " world"]
```

### Pattern 3: Property-Based Tests for Cognitive Tier Invariants

**What:** Use Hypothesis to generate thousands of random prompts and verify tier classification invariants

**When to use:** Testing cognitive tier classification rules that MUST always be true

**Example:**
```python
# Source: backend/tests/property_tests/llm/test_cognitive_tier_invariants.py
from hypothesis import given, settings
from hypothesis.strategies import text, integers
from core.llm.cognitive_tier_system import CognitiveTier, CognitiveClassifier

class TestCognitiveTierInvariants:
    @given(
        prompt=text(min_size=0, max_size=10000),
        task_size=integers(min_value=0, max_value=100)
    )
    @settings(max_examples=200)
    def test_tier_always_valid_enum(self, prompt, task_size):
        """
        INVARIANT: classify() MUST return a valid CognitiveTier enum value.

        This ensures no invalid tier values can be produced regardless of input.
        """
        classifier = CognitiveClassifier()
        tier = classifier.classify(prompt)
        assert tier in CognitiveTier, \
            f"Invalid tier {tier} for prompt length {len(prompt)}"

    @given(
        prompt_size=integers(min_value=0, max_value=20000)
    )
    @settings(max_examples=100)
    def test_micro_tier_for_very_short_prompts(self, prompt_size):
        """
        INVARIANT: Prompts < 100 characters should classify as MICRO or STANDARD.

        Ensures very short queries don't get classified as high-complexity tiers.
        """
        classifier = CognitiveClassifier()
        prompt = "a" * prompt_size

        if prompt_size < 100:
            tier = classifier.classify(prompt)
            assert tier in [CognitiveTier.MICRO, CognitiveTier.STANDARD], \
                f"Short prompt ({prompt_size} chars) classified as {tier.value}, expected MICRO/STANDARD"
```

### Anti-Patterns to Avoid

- **Testing external services directly:** Never make real HTTP calls to OpenAI/Anthropic in tests. Always mock with httpx.MockTransport or unittest.mock.
- **Shared database state:** Each test should create its own data and clean up. Use database transaction rollback per test (Phase 167 pattern).
- **Over-mocking:** Don't mock the code you're testing. Only mock external dependencies (LLM providers, database, external APIs).
- **Testing implementation details:** Focus on behavior (inputs → outputs), not internal implementation. Tests should break when behavior changes, not when code is refactored.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP client mocking | Custom mock classes for each provider | **httpx.MockTransport** or **pytest_httpx** | Handles async streaming, connection pooling, error simulation |
| Async test execution | Custom event loop management | **pytest-asyncio** `@pytest.mark.asyncio` | Handles async fixtures, teardown, error propagation |
| API route testing | Start real server with requests | **FastAPI TestClient** | Faster, no network overhead, direct router calls |
| Property testing | Custom input generators | **Hypothesis** with `@given` | Shrinks failing examples to minimal case, coverage reporting |
| Database fixtures | Manual create/cleanup logic | **SQLAlchemy fixtures** with transaction rollback | Faster, automatic cleanup, isolation |

**Key insight:** Test infrastructure should be boring and reliable. Save creativity for test scenarios, not test utilities.

---

## Common Pitfalls

### Pitfall 1: Not Isolating External LLM Calls

**What goes wrong:** Tests make real HTTP calls to OpenAI/Anthropic/DeepSeek APIs, causing:
- Slow test execution (seconds per test vs milliseconds)
- Flaky tests (network failures, rate limits, API changes)
- Cost accumulation (paying for LLM calls in CI)

**Why it happens:** BYOK handler initializes real OpenAI clients in `__init__`, making it hard to mock.

**How to avoid:**
```python
# GOOD: Patch at import time before handler initialization
with patch('core.llm.byok_handler.OpenAI') as mock_openai:
    mock_client = AsyncMock()
    mock_openai.return_value = mock_client
    handler = BYOKHandler()  # Will use mocked client

# BAD: Create handler first, then try to patch (too late)
handler = BYOKHandler()
with patch.object(handler, 'clients'):  # Won't work, clients already initialized
    pass
```

**Warning signs:** Tests take >1 second each, intermittent network errors, API quota exceeded.

### Pitfall 2: Not Testing Async Streaming Code Paths

**What goes wrong:** Coverage reports high coverage but async generators (stream_completion) are never actually iterated.

**Why it happens:** Tests mock the streaming method but don't consume the async generator.

**How to avoid:**
```python
# GOOD: Actually consume the async generator
async for token in handler.stream_completion(...):
    tokens.append(token)
assert len(tokens) > 0  # Verify streaming happened

# BAD: Just call the method without consuming
handler.stream_completion(...)  # Generator created but never executed
```

**Warning signs:** Coverage shows 100% on stream_completion but tests pass instantly without actually streaming tokens.

### Pitfall 3: Database Leaks Between Tests

**What goes wrong:** Test data from one test affects another, causing intermittent failures.

**Why it happens:** Tests create data but don't clean up, or use shared database sessions.

**How to avoid:**
```python
# GOOD: Use database session with transaction rollback
@pytest.fixture
def db_session():
    """Create a fresh database session for each test."""
    from core.database import get_db_session
    session = get_db_session().__enter__()
    yield session
    session.rollback()  # Rollback transaction after test
    session.close()

# BAD: Use global database connection
db = get_db()  # Shared across all tests
```

**Warning signs:** Tests pass individually but fail in parallel, tests start failing after adding more tests.

### Pitfall 4: Testing Internal State Instead of Behavior

**What goes wrong:** Tests break when code is refactored even though behavior hasn't changed.

**Why it happens:** Tests assert on internal variables or call private methods.

**How to avoid:**
```python
# GOOD: Test public API behavior
tier = handler.classify_cognitive_tier("hello world")
assert tier == CognitiveTier.MICRO  # Behavior-focused

# BAD: Test internal state
classifier = handler.cognitive_classifier
assert classifier._last_score == -2  # Implementation detail
```

**Warning signs:** Tests fail after harmless refactoring (renaming variables, extracting methods).

---

## Code Examples

Verified patterns from existing codebase:

### TestClient Fixture Pattern (Phase 167)

```python
# Source: backend/tests/api/test_agent_guidance_routes.py
from fastapi.testclient import TestClient
from api.cognitive_tier_routes import router

@pytest.fixture
def client():
    """Create TestClient for cognitive tier router."""
    return TestClient(router)

@pytest.fixture
def mock_user(db: Session):
    """Create mock authenticated user."""
    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email=f"test-{user_id}@example.com",
        role="user"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
```

### Async LLM Mocking Pattern (Phase 165)

```python
# Source: backend/tests/unit/llm/test_byok_handler_coverage.py
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_generate_with_cognitive_tier_escalation(self):
    """Test generate_with_cognitive_tier() with escalation loop."""
    with patch('core.llm.byok_handler.get_byok_manager') as mock_manager:
        # Mock BYOK manager
        mock_mgr = MagicMock()
        mock_mgr.is_configured.return_value = False
        mock_manager.return_value = mock_mgr

        # Mock tier service escalation logic
        with patch('core.llm.cognitive_tier_service.CognitiveTierService') as mock_service:
            mock_service.return_value.select_tier.return_value = CognitiveTier.STANDARD
            mock_service.return_value.check_budget_constraint.return_value = True
            mock_service.return_value.get_optimal_model.return_value = ("deepseek", "deepseek-chat")
            mock_service.return_value.handle_escalation.return_value = (False, None, None)

            # Mock generate_response
            with patch.object(BYOKHandler, 'generate_response', new_callable=AsyncMock) as mock_gen:
                mock_gen.return_value = "Test response"

                handler = BYOKHandler()
                result = await handler.generate_with_cognitive_tier("test prompt")

                assert result["response"] == "Test response"
                assert result["tier"] == "standard"
```

### Property-Based Tier Classification (Phase 165)

```python
# Source: backend/tests/property_tests/llm/test_cognitive_tier_invariants.py
from hypothesis import given, settings, example
from hypothesis.strategies import text

class TestTierClassificationInvariants:
    @given(text(min_size=0, max_size=5000))
    @settings(max_examples=200)
    def test_classification_always_returns_valid_tier(self, prompt):
        """
        INVARIANT: Classification must always return a valid CognitiveTier.

        This property must hold for ANY input string, including:
        - Empty strings
        - Very long strings (5000 chars)
        - Special characters, emojis, unicode
        - Code snippets, JSON, XML
        """
        classifier = CognitiveClassifier()
        tier = classifier.classify(prompt)
        assert tier in CognitiveTier, \
            f"Invalid tier {tier} for prompt: {prompt[:50]}..."

    @given(text(min_size=0, max_size=100))
    @example("")  # Explicit test case for empty string
    def test_short_prompts_never_classify_as_complex(self, prompt):
        """
        INVARIANT: Short prompts (<100 chars) should not classify as COMPLEX tier.

        Ensures the classifier doesn't over-penalize brief queries.
        """
        classifier = CognitiveClassifier()
        tier = classifier.classify(prompt)
        if len(prompt) < 100:
            assert tier != CognitiveTier.COMPLEX, \
                f"Short prompt ({len(prompt)} chars) classified as COMPLEX: {prompt}"
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **unittest** | **pytest** | 2023+ | Better fixtures, parametrization, plugins |
| **requests** with live server | **TestClient** with direct router calls | 2024+ | 10x faster API tests, no network overhead |
| **Example-based testing** | **Property-based testing** (Hypothesis) | 2023+ | Catches edge cases human testers miss |
| **Shared test database** | **Transaction rollback per test** | 2024+ | Parallel test execution, no state pollution |
| **Manual HTTP mocking** | **httpx.MockTransport** | 2024+ | Proper async support, connection pooling simulation |

**Deprecated/outdated:**
- **unittest.TestCase**: Pytest's class-based tests are more flexible
- **mock.patch() everywhere**: Use pytest-mock's `mocker` fixture for cleaner syntax
- **setUp/tearDown methods**: Use pytest fixtures (they're more composable)
- **nose testing framework**: Deprecated, use pytest

---

## Open Questions

1. **Should we test all 6 cognitive tier routes or prioritize?**
   - What we know: All 6 routes have zero coverage. Phase 172 tested all 13 governance routes in one plan.
   - What's unclear: Whether 6 routes fit in one plan or should be split.
   - Recommendation: Follow Phase 172 pattern - test all 6 routes in Plan 01 (target: 400+ lines of tests).

2. **Should BYOK handler tests be split by method or by concern?**
   - What we know: byok_handler.py has 1,556 lines with ~15% coverage. Existing test file has 23K lines.
   - What's unclear: Whether to expand existing file or create new focused test files.
   - Recommendation: Expand existing test_byok_handler_coverage.py (47K lines) to add missing method coverage (stream_completion, generate_with_cognitive_tier, generate_structured_response, _get_coordinated_vision_description).

3. **How much integration testing is needed for LLM workflows?**
   - What we know: Phase 170 established integration testing patterns for HTTP clients. Phase 165 has property tests.
   - What's unclear: Whether end-to-end LLM integration tests are needed or if unit + API tests are sufficient.
   - Recommendation: Create one integration test file (test_llm_integration.py) with 20+ tests for critical workflows (provider fallback, escalation, streaming, budget enforcement).

4. **Should we test MiniMax integration separately?**
   - What we know: minimax_integration.py (184 lines) exists but Phase 68 notes "API access may be closed."
   - What's unclear: Whether to mock MiniMax or test graceful fallback behavior.
   - Recommendation: Test graceful fallback when MiniMax is unavailable (mock HTTP 503 error), don't test real MiniMax API.

---

## Sources

### Primary (HIGH confidence)
- **backend/tests/api/test_agent_guidance_routes.py** - TestClient fixture patterns for API route testing
- **backend/tests/unit/llm/test_byok_handler_coverage.py** - Existing BYOK handler unit tests (47K lines)
- **backend/tests/unit/llm/test_cognitive_tier_coverage.py** - Existing cognitive tier system tests (22K lines)
- **backend/tests/property_tests/llm/test_cognitive_tier_invariants.py** - Property-based tier classification tests
- **backend/tests/integration/services/test_llm_http_integration_coverage.py** - HTTP client mocking patterns with httpx
- **backend/api/cognitive_tier_routes.py** - Source file to test (6 endpoints, 601 lines)
- **backend/core/llm/byok_handler.py** - Source file to test (1,556 lines)
- **backend/core/llm/cognitive_tier_system.py** - Source file to test (297 lines)

### Secondary (MEDIUM confidence)
- **backend/tests/api/conftest.py** - Shared API test fixtures (db_session, client)
- **backend/tests/conftest.py** - Root conftest with environment isolation
- **backend/tests/integration/test_cognitive_tier_routes.py** - Test stub showing coverage gaps
- **.planning/phases/165-core-services-governance-llm/165-RESEARCH.md** - Phase 165 research on governance & LLM testing
- **.planning/phases/172-high-impact-zero-coverage-governance/172-01-PLAN.md** - Phase 172 plan for API route testing patterns

### Tertiary (LOW confidence)
- Coverage JSON files (backend/coverage.json) - Used for estimating current coverage
- Test execution timing (empirical data from test runs) - Used for performance targets

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pytest, TestClient, httpx are industry standards with official docs
- Architecture: HIGH - Patterns verified from existing codebase (Phases 165, 167, 170, 172)
- Pitfalls: HIGH - All pitfalls observed in existing test files or documented in pytest best practices
- Plan breakdown: MEDIUM - Exact number of plans (4-5) estimated based on Phase 172 having 5 plans for similar scope

**Research date:** 2026-03-12
**Valid until:** 2026-04-12 (30 days - stable domain, testing patterns don't change rapidly)
