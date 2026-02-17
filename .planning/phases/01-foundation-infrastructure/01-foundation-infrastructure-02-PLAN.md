---
phase: 01-foundation-infrastructure
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/conftest.py
  - backend/tests/property_tests/conftest.py
  - backend/tests/factories/__init__.py
  - backend/tests/utilities/__init__.py
  - backend/tests/utilities/helpers.py
  - backend/tests/utilities/assertions.py
autonomous: true

must_haves:
  truths:
    - conftest.py standardized with db_session fixture using temp file-based SQLite
    - conftest.py has test_agent fixtures for all maturity levels (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
    - conftest.py has mock_llm_response fixture for deterministic LLM outputs
    - conftest.py has mock_embedding_vectors fixture for controlled similarity testing
    - property_tests/conftest.py has Hypothesis settings (max_examples=200 local, 50 CI)
    - Test utilities module created with factories, helpers, assertion libraries
    - All new tests use standardized fixtures (no ad-hoc setup)
  artifacts:
    - path: backend/tests/conftest.py
      provides: Root pytest configuration with standardized fixtures
      contains: db_session, test_agent, mock_llm_response, mock_embedding_vectors
    - path: backend/tests/property_tests/conftest.py
      provides: Hypothesis settings for property-based testing
      contains: max_examples, ci_profile, local_profile
    - path: backend/tests/utilities/__init__.py
      provides: Test utilities module
      contains: factories, helpers, assertions
  key_links:
    - from: test files
      to: conftest.py fixtures
      via: pytest fixture resolution
      pattern: def test_something(db_session, test_agent)
    - from: property tests
      to: property_tests/conftest.py settings
      via: @settings decorator
      pattern: @settings(DEFAULT_PROFILE)
---

<objective>
Standardize test infrastructure with consistent fixtures, Hypothesis settings, and reusable utilities to ensure all tests follow the same patterns and avoid ad-hoc setup.

Purpose: Prevent test data fragility and inconsistent patterns by standardizing db_session fixtures, test agents for all maturity levels, mock LLM responses, embedding vectors, Hypothesis settings, and utility functions across the entire test suite.

Output: Updated conftest.py files, new test utilities module, and documentation ensuring all new tests use standardized fixtures.
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md

# Existing Infrastructure
@backend/tests/conftest.py (existing db_session, test_agent fixtures)
@backend/tests/property_tests/conftest.py (existing Hypothesis settings)
@backend/tests/factories/ (existing factory_boy factories)
</context>

<tasks>

<task type="auto">
  <name>Standardize Root conftest.py with Maturity Level Fixtures and Mocks</name>
  <files>backend/tests/conftest.py</files>
  <action>
Enhance root conftest.py with standardized fixtures for all maturity levels and deterministic mocks:

1. Add maturity-specific test agent fixtures (STUDENT, INTERN, SUPERVISED, AUTONOMOUS):
   - `test_agent_student()`: Agent with STUDENT maturity (confidence < 0.5)
   - `test_agent_intern()`: Agent with INTERN maturity (0.5-0.7 confidence)
   - `test_agent_supervised()`: Agent with SUPERVISED maturity (0.7-0.9 confidence)
   - `test_agent_autonomous()`: Agent with AUTONOMOUS maturity (> 0.9 confidence)

2. Add mock_llm_response fixture for deterministic LLM outputs:
   - Returns predictable responses for testing without hitting real LLM APIs
   - Supports streaming responses with chunked output
   - Includes error response variants for testing failure modes

3. Add mock_embedding_vectors fixture for controlled similarity testing:
   - Generates deterministic vectors (same input = same vector)
   - Supports known similarity scores for testing retrieval logic
   - Includes dimension mismatch handling

4. Enhance existing db_session fixture (already uses temp file-based SQLite):
   - Verify it's using tempfile.mkstemp pattern (not :memory:)
   - Ensure per-test isolation with autouse fixtures
   - Add performance metrics logging for slow tests

5. Add fixture documentation in docstrings explaining:
   - When to use each fixture
   - Scope and isolation guarantees
   - Performance characteristics

Implementation should append to existing conftest.py without breaking current fixtures.

Key additions:
```python
@pytest.fixture(scope="function")
def test_agent_student(db_session: Session):
    \"\"\"Create a STUDENT maturity test agent (confidence < 0.5).\"\"\"
    agent = AgentRegistry(
        name="StudentAgent",
        category="test",
        module_path="test.module",
        class_name="TestStudent",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.3,  # Below STUDENT threshold
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent

@pytest.fixture(scope="function")
def test_agent_intern(db_session: Session):
    \"\"\"Create an INTERN maturity test agent (0.5-0.7 confidence).\"\"\"
    agent = AgentRegistry(
        name="InternAgent",
        category="test",
        module_path="test.module",
        class_name="TestIntern",
        status=AgentStatus.INTERN.value,
        confidence_score=0.6,  # INTERN range
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent

@pytest.fixture(scope="function")
def test_agent_supervised(db_session: Session):
    \"\"\"Create a SUPERVISED maturity test agent (0.7-0.9 confidence).\"\"\"
    agent = AgentRegistry(
        name="SupervisedAgent",
        category="test",
        module_path="test.module",
        class_name="TestSupervised",
        status=AgentStatus.SUPERVISED.value,
        confidence_score=0.8,  # SUPERVISED range
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent

@pytest.fixture(scope="function")
def test_agent_autonomous(db_session: Session):
    \"\"\"Create an AUTONOMOUS maturity test agent (>0.9 confidence).\"\"\"
    agent = AgentRegistry(
        name="AutonomousAgent",
        category="test",
        module_path="test.module",
        class_name="TestAutonomous",
        status=AgentStatus.AUTONOMOUS.value,
        confidence_score=0.95,  # AUTONOMOUS range
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent

@pytest.fixture(scope="function")
def mock_llm_response():
    \"\"\"Provide deterministic mock LLM responses for testing.

    Yields a mock object that returns predictable responses for:
    - Single completions: mock_llm_response.complete(prompt) -> "Mock response"
    - Streaming: mock_llm_response.stream(prompt) -> ["Mock", " response"]
    - Errors: mock_llm_response.set_error_mode(rate_limited|timeout)

    Usage:
        def test_agent_response(mock_llm_response):
            response = mock_llm_response.complete("test")
            assert response == "Mock response"
    \"\"\"
    from unittest.mock import MagicMock
    import asyncio
    from typing import AsyncIterator

    class MockLLMResponse:
        def __init__(self):
            self._error_mode = None
            self._response_count = 0

        def complete(self, prompt: str, **kwargs) -> str:
            \"\"\"Return deterministic mock response.\"\"\"
            self._response_count += 1
            if self._error_mode == "rate_limited":
                raise Exception("Rate limit exceeded")
            elif self._error_mode == "timeout":
                raise asyncio.TimeoutError("LLM timeout")
            return f"Mock response {self._response_count} for: {prompt[:50]}"

        async def stream(self, prompt: str, **kwargs) -> AsyncIterator[str]:
            \"\"\"Return deterministic mock streaming response.\"\"\"
            self._response_count += 1
            response = f"Mock streaming response {self._response_count}"
            for char in response:
                if self._error_mode:
                    if self._error_mode == "rate_limited":
                        raise Exception("Rate limit exceeded")
                    elif self._error_mode == "timeout":
                        raise asyncio.TimeoutError("LLM timeout")
                yield char
                await asyncio.sleep(0.001)  # Simulate network delay

        def set_error_mode(self, mode: str):
            \"\"\"Set error mode for testing failure scenarios.

            Args:
                mode: One of "rate_limited", "timeout", or None (no errors)
            \"\"\"
            self._error_mode = mode

        def reset(self):
            \"\"\"Reset error mode and response count.\"\"\"
            self._error_mode = None
            self._response_count = 0

    mock = MockLLMResponse()
    yield mock
    # Cleanup
    mock.reset()

@pytest.fixture(scope="function")
def mock_embedding_vectors():
    \"\"\"Provide deterministic mock embedding vectors for similarity testing.

    Yields a mock object that returns:
    - Deterministic vectors: same input always produces same vector
    - Known similarity scores: predefined cosine similarities
    - Dimension handling: supports 384-dim (FastEmbed) and 1536-dim (OpenAI)

    Usage:
        def test_similarity_search(mock_embedding_vectors):
            vec1 = mock_embedding_vectors.embed("query")
            vec2 = mock_embedding_vectors.embed("query")  # Same!
            assert vec1 == vec2
    \"\"\"
    import hashlib
    import numpy as np

    class MockEmbeddingVectors:
        def __init__(self):
            self._dimension = 384  # Default FastEmbed dimension
            self._known_similarities = {
                ("exact", "exact"): 1.0,
                ("similar", "similar"): 0.9,
                ("related", "related"): 0.7,
                ("unrelated", "unrelated"): 0.1,
            }

        def set_dimension(self, dim: int):
            \"\"\"Set embedding dimension (384 for FastEmbed, 1536 for OpenAI).\"\"\"
            self._dimension = dim

        def embed(self, text: str) -> list[float]:
            \"\"\"Generate deterministic embedding vector from text.

            Uses hash of text to generate consistent values.
            \"\"\"
            # Create hash of text for determinism
            hash_obj = hashlib.sha256(text.encode())
            hash_bytes = hash_obj.digest()

            # Convert to floats in [-1, 1] range
            values = []
            for i in range(self._dimension):
                byte_idx = i % len(hash_bytes)
                byte_val = hash_bytes[byte_idx]
                # Convert byte to float in [-1, 1]
                float_val = (byte_val - 128) / 128.0
                values.append(float_val)

            return values

        def embed_batch(self, texts: list[str]) -> list[list[float]]:
            \"\"\"Generate embeddings for multiple texts.\"\"\"
            return [self.embed(text) for text in texts]

        def cosine_similarity(self, vec1: list[float], vec2: list[float]) -> float:
            \"\"\"Calculate cosine similarity between two vectors.\"\"\"
            import math
            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            mag1 = math.sqrt(sum(a * a for a in vec1))
            mag2 = math.sqrt(sum(b * b for b in vec2))
            if mag1 == 0 or mag2 == 0:
                return 0.0
            return dot_product / (mag1 * mag2)

        def get_similarity(self, text1: str, text2: str) -> float:
            \"\"\"Get similarity score using known table or computed cosine.\"\"\"
            # Check known similarities first
            key = tuple(sorted([text1.lower(), text2.lower()]))
            for known_pair, score in self._known_similarities.items():
                if set(known_pair) == set([text1.lower(), text2.lower()]):
                    return score
            # Fall back to computed cosine similarity
            return self.cosine_similarity(self.embed(text1), self.embed(text2))

    mock = MockEmbeddingVectors()
    yield mock
```
  </action>
  <verify>
1. File modified: backend/tests/conftest.py
2. New fixtures defined: test_agent_student, test_agent_intern, test_agent_supervised, test_agent_autonomous
3. New fixtures defined: mock_llm_response, mock_embedding_vectors
4. All fixtures have proper docstrings

Command:
```bash
cd backend && grep -q "test_agent_student" tests/conftest.py && \
grep -q "test_agent_intern" tests/conftest.py && \
grep -q "test_agent_supervised" tests/conftest.py && \
grep -q "test_agent_autonomous" tests/conftest.py && \
grep -q "mock_llm_response" tests/conftest.py && \
grep -q "mock_embedding_vectors" tests/conftest.py
```
  </verify>
  <done>
Root conftest.py enhanced with:
- Maturity-specific agent fixtures (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
- Mock LLM response fixture for deterministic testing
- Mock embedding vectors fixture for similarity testing
- All fixtures documented with usage examples
- Existing fixtures preserved (db_session, unique_resource_name, etc.)
  </done>
</task>

<task type="auto">
  <name>Verify Hypothesis Settings in property_tests/conftest.py</name>
  <files>backend/tests/property_tests/conftest.py</files>
  <action>
Verify and enhance property_tests/conftest.py with proper Hypothesis settings:

1. Verify existing Hypothesis settings:
   - max_examples=200 for local development
   - max_examples=50 for CI environment
   - Deadline disabled for property tests
   - Health checks configured appropriately

2. Add Hypothesis settings documentation explaining:
   - Why max_examples differs between local and CI
   - Which health checks are suppressed and why
   - Performance targets for property tests

3. Add test size decorators for tiered testing:
   - @small: Fast property tests (<10s, max_examples=100)
   - @medium: Medium property tests (<60s, max_examples=200)
   - @large: Slow property tests (<100s, max_examples=50 in CI)

4. Add property test utilities:
   - `assume_valid_agent_id()`: Hypothesis assume for valid agent IDs
   - `assume_valid_confidence()`: Hypothesis assume for confidence scores
   - `assume_maturity_level()`: Hypothesis assume for maturity enums

Enhancements should append to existing property_tests/conftest.py without breaking current tests.

Key additions:
```python
# Add after existing imports
from hypothesis import strategies as st
from hypothesis import given, assume
import enum

# Property test size decorators
import pytest

@pytest.fixture(scope="session")
def small_settings():
    \"\"\"Fast property tests with fewer examples (10s target).\"\"\"
    from hypothesis import settings, HealthCheck
    return settings(
        max_examples=100,
        deadline=10000,  # 10 seconds per test
        suppress_health_check=list(HealthCheck)
    )

@pytest.fixture(scope="session")
def medium_settings():
    \"\"\"Standard property tests (60s target).\"\"\"
    from hypothesis import settings, HealthCheck
    return settings(
        max_examples=200,
        deadline=60000,  # 60 seconds per test
        suppress_health_check=list(HealthCheck)
    )

@pytest.fixture(scope="session")
def large_settings():
    \"\"\"Slow property tests with fewer examples (100s target).\"\"\"
    from hypothesis import settings, HealthCheck
    return settings(
        max_examples=50,
        deadline=100000,  # 100 seconds per test
        suppress_health_check=list(HealthCheck)
    )

# Property test strategies
@pytest.fixture(scope="session")
def valid_agent_ids():
    \"\"\"Strategy for generating valid agent IDs.\"\"\"
    return st.uuids()

@pytest.fixture(scope="session")
def confidence_scores():
    \"\"\"Strategy for generating valid confidence scores (0.0-1.0).\"\"\"
    return st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

@pytest.fixture(scope="session")
def maturity_levels():
    \"\"\"Strategy for generating maturity level enums.\"\"\"
    return st.sampled_from(['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'])

# Property test assumptions
def assume_valid_agent_id(agent_id):
    \"\"\"Assume agent_id is valid (not None, not empty string).\"\"\"
    assume(agent_id is not None)
    if isinstance(agent_id, str):
        assume(len(agent_id) > 0)

def assume_valid_confidence(confidence):
    \"\"\"Assume confidence is in valid range [0.0, 1.0].\"\"\"
    assume(0.0 <= confidence <= 1.0)

def assume_maturity_level(maturity):
    \"\"\"Assume maturity is a valid level.\"\"\"
    valid_levels = ['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS']
    assume(maturity in valid_levels)
```
  </action>
  <verify>
1. File modified: backend/tests/property_tests/conftest.py
2. New fixtures defined: small_settings, medium_settings, large_settings
3. New strategies defined: valid_agent_ids, confidence_scores, maturity_levels
4. New assume functions: assume_valid_agent_id, assume_valid_confidence, assume_maturity_level

Command:
```bash
cd backend && grep -q "small_settings" tests/property_tests/conftest.py && \
grep -q "medium_settings" tests/property_tests/conftest.py && \
grep -q "large_settings" tests/property_tests/conftest.py && \
grep -q "valid_agent_ids" tests/property_tests/conftest.py && \
grep -q "assume_valid_agent_id" tests/property_tests/conftest.py
```
  </verify>
  <done>
property_tests/conftest.py enhanced with:
- Test size decorators (small, medium, large) with performance targets
- Property test strategies for common inputs (agent IDs, confidence, maturity)
- Property test assumptions for validation
- Hypothesis settings documented
- Existing settings preserved (ci_profile, local_profile, DEFAULT_PROFILE)
  </done>
</task>

<task type="auto">
  <name>Create Test Utilities Module with Helpers and Assertions</name>
  <files>
    backend/tests/utilities/__init__.py
    backend/tests/utilities/helpers.py
    backend/tests/utilities/assertions.py
  </files>
  <action>
Create reusable test utilities module with helpers and assertion libraries:

1. Create utilities module structure:
```bash
mkdir -p backend/tests/utilities
touch backend/tests/utilities/__init__.py
```

2. Create helpers.py with common test helper functions:
- `create_test_agent()`: Helper for creating agents with specific maturity
- `create_test_episode()`: Helper for creating test episodes
- `create_test_canvas()`: Helper for creating test canvas presentations
- `wait_for_condition()`: Async helper for waiting on conditions
- `mock_websocket()`: Mock WebSocket for testing real-time features
- `mock_byok_handler()`: Mock BYOK LLM handler
- `clear_governance_cache()`: Clear governance cache between tests

3. Create assertions.py with custom assertion functions:
- `assert_agent_maturity()`: Assert agent has expected maturity level
- `assert_governance_blocked()`: Assert action was blocked by governance
- `assert_episode_created()`: Assert episode was created with segments
- `assert_canvas_presented()`: Assert canvas was presented successfully
- `assert_coverage_threshold()`: Assert coverage meets threshold
- `assert_performance_baseline()`: Assert test execution time within baseline

4. Create __init__.py that exports all utilities for easy importing:
```python
"""
Test utilities module.

Provides reusable helpers, assertions, and factories for consistent testing.
"""

# Helpers
from .helpers import (
    create_test_agent,
    create_test_episode,
    create_test_canvas,
    wait_for_condition,
    mock_websocket,
    mock_byok_handler,
    clear_governance_cache,
)

# Assertions
from .assertions import (
    assert_agent_maturity,
    assert_governance_blocked,
    assert_episode_created,
    assert_canvas_presented,
    assert_coverage_threshold,
    assert_performance_baseline,
)

__all__ = [
    # Helpers
    'create_test_agent',
    'create_test_episode',
    'create_test_canvas',
    'wait_for_condition',
    'mock_websocket',
    'mock_byok_handler',
    'clear_governance_cache',
    # Assertions
    'assert_agent_maturity',
    'assert_governance_blocked',
    'assert_episode_created',
    'assert_canvas_presented',
    'assert_coverage_threshold',
    'assert_performance_baseline',
]
```

helpers.py implementation:
```python
"""
Test helper functions for common test operations.

These helpers reduce test boilerplate and ensure consistent patterns
across the test suite.
"""

import asyncio
import uuid
from typing import Optional, Callable, Any
from unittest.mock import MagicMock, AsyncMock
from sqlalchemy.orm import Session

from core.models import AgentRegistry, AgentStatus, Episode, CanvasAudit
from core.governance_cache import governance_cache


def create_test_agent(
    db_session: Session,
    name: str = "TestAgent",
    maturity: str = "STUDENT",
    confidence: float = 0.5,
    category: str = "test"
) -> AgentRegistry:
    \"\"\"
    Create a test agent with specified parameters.

    Args:
        db_session: Database session
        name: Agent name
        maturity: Maturity level (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
        confidence: Confidence score (0.0-1.0)
        category: Agent category

    Returns:
        Created AgentRegistry instance
    \"\"\"
    agent = AgentRegistry(
        name=name,
        category=category,
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus[maturity].value,
        confidence_score=confidence,
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent


def create_test_episode(
    db_session: Session,
    agent_id: str,
    title: str = "Test Episode"
) -> Episode:
    \"\"\"
    Create a test episode for an agent.

    Args:
        db_session: Database session
        agent_id: Agent ID
        title: Episode title

    Returns:
        Created Episode instance
    \"\"\"
    episode = Episode(
        agent_id=agent_id,
        title=title,
        description="Test episode created by helper",
        segment_count=0,
        total_duration_ms=0,
    )
    db_session.add(episode)
    db_session.commit()
    db_session.refresh(episode)
    return episode


def create_test_canvas(
    db_session: Session,
    agent_id: str,
    canvas_type: str = "generic"
) -> CanvasAudit:
    \"\"\"
    Create a test canvas audit entry.

    Args:
        db_session: Database session
        agent_id: Agent ID
        canvas_type: Type of canvas (generic, docs, sheets, etc.)

    Returns:
        Created CanvasAudit instance
    \"\"\"
    canvas = CanvasAudit(
        agent_id=agent_id,
        canvas_id=str(uuid.uuid4()),
        action=\"present\",
        canvas_type=canvas_type,
        component_count=1,
    )
    db_session.add(canvas)
    db_session.commit()
    db_session.refresh(canvas)
    return canvas


async def wait_for_condition(
    condition: Callable[[], bool],
    timeout: float = 5.0,
    interval: float = 0.1,
    error_message: str = "Condition not met within timeout"
) -> None:
    \"\"\"
    Wait for a condition to become true.

    Args:
        condition: Callable that returns bool
        timeout: Maximum wait time in seconds
        interval: Check interval in seconds
        error_message: Error message if timeout exceeded

    Raises:
        TimeoutError: If condition not met within timeout
    \"\"\"
    start = asyncio.get_event_loop().time()
    while (asyncio.get_event_loop().time() - start) < timeout:
        if condition():
            return
        await asyncio.sleep(interval)
    raise TimeoutError(error_message)


def mock_websocket():
    \"\"\"
    Create a mock WebSocket for testing real-time features.

    Returns:
        MagicMock with async methods mocked
    \"\"\"
    ws = MagicMock()
    ws.send_text = AsyncMock()
    ws.send_json = AsyncMock()
    ws.close = AsyncMock()
    ws.accept = AsyncMock()
    return ws


def mock_byok_handler():
    \"\"\"
    Create a mock BYOK handler for LLM operations.

    Returns:
        AsyncMock with common LLM methods
    \"\"\"
    handler = AsyncMock()
    handler.complete = AsyncMock(return_value=\"Mock LLM response\")
    handler.stream = AsyncMock(return_value=[\"Mock\", \" response\"])
    return handler


def clear_governance_cache(agent_id: Optional[str] = None) -> None:
    \"\"\"
    Clear governance cache for an agent or all agents.

    Args:
        agent_id: Specific agent ID to clear, or None for all
    \"\"\"
    if agent_id:
        governance_cache.invalidate_agent(agent_id)
    else:
        # Clear all cache entries
        governance_cache._cache.clear()
        governance_cache._hits = 0
        governance_cache._misses = 0
```

assertions.py implementation:
```python
"""
Custom assertion functions for common test validations.

These assertions provide better error messages and ensure
consistent validation patterns across tests.
"""

import time
from typing import Optional
from sqlalchemy.orm import Session

from core.models import AgentRegistry, AgentStatus, Episode, CanvasAudit
from core.governance_cache import governance_cache


def assert_agent_maturity(
    agent: AgentRegistry,
    expected_maturity: str,
    confidence_delta: float = 0.01
) -> None:
    \"\"\"
    Assert agent has expected maturity level.

    Args:
        agent: Agent to check
        expected_maturity: Expected maturity (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
        confidence_delta: Allowed variance in confidence score

    Raises:
        AssertionError: If maturity doesn't match or confidence out of range
    \"\"\"
    actual_status = AgentStatus(agent.status)
    expected_status = AgentStatus[expected_maturity]

    # Check status matches
    assert actual_status == expected_status, \
        f\"Agent {agent.name} has maturity {actual_status.value}, expected {expected_status.value}\"

    # Check confidence is in expected range for maturity
    confidence = agent.confidence_score
    if expected_maturity == "STUDENT":
        assert confidence < 0.5, \
            f\"STUDENT agent has confidence {confidence}, expected < 0.5\"
    elif expected_maturity == "INTERN":
        assert 0.5 <= confidence < 0.7, \
            f\"INTERN agent has confidence {confidence}, expected [0.5, 0.7)\"
    elif expected_maturity == "SUPERVISED":
        assert 0.7 <= confidence < 0.9, \
            f\"SUPERVISED agent has confidence {confidence}, expected [0.7, 0.9)\"
    elif expected_maturity == "AUTONOMOUS":
        assert confidence >= 0.9, \
            f\"AUTONOMOUS agent has confidence {confidence}, expected >= 0.9\"


def assert_governance_blocked(
    agent_id: str,
    action: str,
    reason: Optional[str] = None
) -> None:
    \"\"\"
    Assert action was blocked by governance.

    Args:
        agent_id: Agent ID
        action: Action that was blocked
        reason: Expected reason for blocking (optional)

    Raises:
        AssertionError: If action wasn't blocked or reason doesn't match
    \"\"\"
    # Check governance cache for blocked decision
    decision = governance_cache.check(agent_id, action)
    assert decision.allowed is False, \
        f\"Action {action} was not blocked for agent {agent_id}\"

    if reason:
        assert reason in decision.reason.lower(), \
            f\"Blocking reason '{decision.reason}' doesn't contain '{reason}'\"


def assert_episode_created(
    db_session: Session,
    agent_id: str,
    min_segments: int = 1
) -> Episode:
    \"\"\"
    Assert episode was created for agent with minimum segments.

    Args:
        db_session: Database session
        agent_id: Agent ID
        min_segments: Minimum expected segment count

    Returns:
        The created Episode

    Raises:
        AssertionError: If no episode found or segment count too low
    \"\"\"
    episode = db_session.query(Episode).filter(
        Episode.agent_id == agent_id
    ).first()

    assert episode is not None, \
        f\"No episode found for agent {agent_id}\"

    assert episode.segment_count >= min_segments, \
        f\"Episode has {episode.segment_count} segments, expected >= {min_segments}\"

    return episode


def assert_canvas_presented(
    db_session: Session,
    agent_id: str,
    canvas_type: Optional[str] = None
) -> CanvasAudit:
    \"\"\"
    Assert canvas was presented by agent.

    Args:
        db_session: Database session
        agent_id: Agent ID
        canvas_type: Expected canvas type (optional)

    Returns:
        The CanvasAudit record

    Raises:
        AssertionError: If no canvas audit found
    \"\"\"
    query = db_session.query(CanvasAudit).filter(
        CanvasAudit.agent_id == agent_id,
        CanvasAudit.action == "present"
    )

    if canvas_type:
        query = query.filter(CanvasAudit.canvas_type == canvas_type)

    canvas = query.first()

    assert canvas is not None, \
        f\"No canvas presentation found for agent {agent_id}\" + \
        (f\" of type {canvas_type}\" if canvas_type else \"\")

    return canvas


def assert_coverage_threshold(
    coverage_data: dict,
    module: str,
    min_coverage: float
) -> None:
    \"\"\"
    Assert module meets coverage threshold.

    Args:
        coverage_data: Coverage data from coverage.json
        module: Module name to check
        min_coverage: Minimum required coverage (0-100)

    Raises:
        AssertionError: If coverage below threshold
    \"\"\"
    # Find module in coverage data
    module_coverage = 0.0
    for file_path, metrics in coverage_data.get('files', {}).items():
        if module in file_path:
            pct = metrics.get('summary', {}).get('percent_covered', 0)
            module_coverage = max(module_coverage, pct)

    assert module_coverage >= min_coverage, \
        f\"Module {module} has {module_coverage:.1f}% coverage, \" \
        f\"expected >= {min_coverage:.1f}%\"


def assert_performance_baseline(
    duration: float,
    max_duration: float,
    operation: str
) -> None:
    \"\"\"
    Assert operation completes within performance baseline.

    Args:
        duration: Actual operation duration (seconds)
        max_duration: Maximum allowed duration (seconds)
        operation: Operation name for error message

    Raises:
        AssertionError: If duration exceeds baseline
    \"\"\"
    assert duration <= max_duration, \
        f\"{operation} took {duration:.2f}s, expected <= {max_duration:.2f}s\"
```
  </action>
  <verify>
1. Directory created: backend/tests/utilities/
2. File exists: backend/tests/utilities/__init__.py
3. File exists: backend/tests/utilities/helpers.py
4. File exists: backend/tests/utilities/assertions.py
5. All utilities are exported from __init__.py

Command:
```bash
cd backend && test -d tests/utilities && \
test -f tests/utilities/__init__.py && \
test -f tests/utilities/helpers.py && \
test -f tests/utilities/assertions.py && \
grep -q "create_test_agent" tests/utilities/__init__.py && \
grep -q "assert_agent_maturity" tests/utilities/__init__.py
```
  </verify>
  <done>
Test utilities module created with:
- helpers.py: create_test_agent, create_test_episode, create_test_canvas, wait_for_condition, mock_websocket, mock_byok_handler, clear_governance_cache
- assertions.py: assert_agent_maturity, assert_governance_blocked, assert_episode_created, assert_canvas_presented, assert_coverage_threshold, assert_performance_baseline
- __init__.py: All utilities exported for easy importing
- Comprehensive docstrings and usage examples
  </done>
</task>

<task type="auto">
  <name>Create Test Standards Documentation</name>
  <files>backend/tests/TEST_STANDARDS.md</files>
  <action>
Create comprehensive test standards documentation:

1. Create TEST_STANDARDS.md with:
- Fixture usage guidelines (when to use db_session vs direct DB access)
- Maturity level testing patterns (how to test governance by maturity)
- Mock usage guidelines (when to mock LLM, external services)
- Property test patterns (when to use Hypothesis vs example-based)
- Assertion best practices (custom assertions vs raw assert)
- Performance guidelines (max test duration, parallel execution)

2. Include examples showing:
- Correct vs incorrect fixture usage
- Proper test isolation patterns
- Governance testing by maturity level
- LLM mocking for deterministic tests

3. Add anti-patterns section showing what NOT to do:
- Hardcoded IDs in tests
- Shared state between tests
- Over-mocking external dependencies
- Ignoring test isolation

4. Create quick reference section:
- Common imports
- Fixture reference
- Assertion reference
- Helper function reference

Document structure:
```markdown
# Test Standards and Best Practices

## Fixture Usage Guidelines

### Database Sessions
- **DO**: Use `db_session` fixture for all database operations
- **DON'T**: Create database sessions directly in tests

### Test Agents
- **DO**: Use maturity-specific fixtures (test_agent_student, test_agent_intern, etc.)
- **DON'T**: Manually create agents with hardcoded maturity values

### LLM Mocking
- **DO**: Use `mock_llm_response` fixture for deterministic LLM responses
- **DON'T**: Call real LLM APIs in tests

## Maturity Level Testing

### Testing Governance by Maturity

```python
# Correct: Use maturity-specific fixtures
def test_student_blocked_from_deletes(test_agent_student, db_session):
    # Student agent should be blocked
    with pytest.raises(PermissionError):
        execute_delete_action(test_agent_student)

# Incorrect: Hardcoded maturity values
def test_student_blocked_from_deletes_bad():
    agent = AgentRegistry(name="test", status=AgentStatus.STUDENT.value, ...)
    # Fragile: breaks if status values change
```

## Property Test Patterns

### When to Use Hypothesis
- **Use Hypothesis**: For system invariants (confidence scores, maturity transitions)
- **Use example-based**: For specific workflows, API contracts

### Property Test Example

```python
@given(confidence_scores())
@settings(medium_settings)
def test_confidence_in_bounds(confidence):
    \"\"\"Confidence scores must be in [0.0, 1.0].\"\"\"
    assert 0.0 <= confidence <= 1.0
```

## Assertion Best Practices

### Use Custom Assertions
- **DO**: Use custom assertions (assert_agent_maturity, assert_governance_blocked)
- **DON'T**: Use raw assert for complex conditions

### Assertion Examples

```python
# Good: Custom assertion with helpful error message
assert_agent_maturity(agent, "AUTONOMOUS")

# Bad: Raw assert with vague error
assert agent.status == "AUTONOMOUS", "Not autonomous"
```

## Performance Guidelines

### Test Duration Targets
- Unit tests: < 1s each
- Integration tests: < 5s each
- Property tests: < 60s total

### Parallel Execution
- All tests must be parallel-safe (use unique_resource_name fixture)
- No shared state between tests

## Anti-Patterns

### Hardcoded IDs
```python
# Bad: Hardcoded ID
agent = db_session.query(AgentRegistry).get("123e4567-e89b-12d3-a456-426614174000")

# Good: Create fresh agent or use fixture
agent = test_agent_autonomous(db_session)
```

### Shared State
```python
# Bad: Shared state between tests
class TestGroup:
    shared_agent = None  # Runs across tests!

# Good: Fresh fixtures per test
def test_one(test_agent):
    pass

def test_two(test_agent):  # Different instance
    pass
```

## Quick Reference

### Common Imports
```python
import pytest
from hypothesis import given, settings
from sqlalchemy.orm import Session

# Fixtures
from tests.conftest import db_session, test_agent_autonomous

# Utilities
from tests.utilities import create_test_agent, assert_agent_maturity
```

### Fixture Reference
- `db_session`: Database session (temp file-based SQLite)
- `test_agent`: Generic test agent
- `test_agent_student`: STUDENT maturity agent
- `test_agent_intern`: INTERN maturity agent
- `test_agent_supervised`: SUPERVISED maturity agent
- `test_agent_autonomous`: AUTONOMOUS maturity agent
- `mock_llm_response`: Deterministic LLM mock
- `mock_embedding_vectors`: Deterministic embedding mock

### Assertion Reference
- `assert_agent_maturity(agent, maturity)`: Assert maturity level
- `assert_governance_blocked(agent_id, action)`: Assert action blocked
- `assert_episode_created(db_session, agent_id)`: Assert episode exists
- `assert_canvas_presented(db_session, agent_id)`: Assert canvas presented
- `assert_coverage_threshold(coverage_data, module, min)`: Assert coverage
- `assert_performance_baseline(duration, max, operation)`: Assert performance

### Helper Reference
- `create_test_agent(db_session, maturity, confidence)`: Create agent
- `create_test_episode(db_session, agent_id)`: Create episode
- `create_test_canvas(db_session, agent_id, canvas_type)`: Create canvas
- `wait_for_condition(condition, timeout)`: Async wait
- `mock_websocket()`: Mock WebSocket
- `mock_byok_handler()`: Mock LLM handler
- `clear_governance_cache(agent_id)`: Clear cache
```
  </action>
  <verify>
1. File exists: backend/tests/TEST_STANDARDS.md
2. Document contains: Fixture usage guidelines, Maturity level testing patterns, Property test patterns, Assertion best practices, Performance guidelines, Anti-patterns, Quick reference

Command:
```bash
cd backend && grep -q "Fixture Usage Guidelines" tests/TEST_STANDARDS.md && \
grep -q "Maturity Level Testing" tests/TEST_STANDARDS.md && \
grep -q "Property Test Patterns" tests/TEST_STANDARDS.md && \
grep -q "Assertion Best Practices" tests/TEST_STANDARDS.md && \
grep -q "Quick Reference" tests/TEST_STANDARDS.md
```
  </verify>
  <done>
TEST_STANDARDS.md created with:
- Fixture usage guidelines (db_session, test agents, LLM mocking)
- Maturity level testing patterns (correct vs incorrect examples)
- Property test patterns (when to use Hypothesis)
- Assertion best practices (custom vs raw assert)
- Performance guidelines (duration targets, parallel execution)
- Anti-patterns section (hardcoded IDs, shared state, over-mocking)
- Quick reference (imports, fixtures, assertions, helpers)
  </done>
</task>

</tasks>

<verification>
After all tasks complete, verify:

1. Root conftest.py has all required fixtures:
   - db_session (temp file-based SQLite)
   - test_agent_student, test_agent_intern, test_agent_supervised, test_agent_autonomous
   - mock_llm_response, mock_embedding_vectors

2. property_tests/conftest.py has Hypothesis settings:
   - max_examples=200 for local, 50 for CI
   - Test size decorators (small, medium, large)
   - Property test strategies and assumptions

3. Test utilities module created:
   - helpers.py with 7 helper functions
   - assertions.py with 6 assertion functions
   - __init__.py exporting all utilities

4. Documentation created:
   - TEST_STANDARDS.md with guidelines and examples
   - Quick reference section for common operations

Command:
```bash
cd backend && \
grep -q "test_agent_student" tests/conftest.py && \
grep -q "test_agent_intern" tests/conftest.py && \
grep -q "test_agent_supervised" tests/conftest.py && \
grep -q "test_agent_autonomous" tests/conftest.py && \
grep -q "mock_llm_response" tests/conftest.py && \
grep -q "mock_embedding_vectors" tests/conftest.py && \
test -f tests/utilities/helpers.py && \
test -f tests/utilities/assertions.py && \
test -f tests/TEST_STANDARDS.md && \
python -c "from tests.utilities import create_test_agent, assert_agent_maturity" 2>&1 || echo "Utilities import check"
```
</verification>

<success_criteria>
1. conftest.py standardized with db_session fixture using temp file-based SQLite
2. conftest.py has test_agent fixtures for all maturity levels (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
3. conftest.py has mock_llm_response fixture for deterministic outputs
4. conftest.py has mock_embedding_vectors fixture for controlled similarity
5. property_tests/conftest.py has Hypothesis settings (max_examples=200 local, 50 CI)
6. Test utilities created (factories, helpers, assertion libraries)
7. TEST_STANDARDS.md documents all fixtures and patterns
8. All new tests can use standardized fixtures (no ad-hoc setup required)
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation-infrastructure/01-foundation-infrastructure-02-SUMMARY.md` with:
- List of all standardized fixtures added
- Test utilities module structure
- Coverage of TEST_STANDARDS.md
- Sample test showing proper fixture usage
- Recommendations for next phase (property-based testing, coverage measurement)
</output>
