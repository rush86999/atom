# Plan 1-2: Test Infrastructure Standardization

**Phase:** 1 - Foundation & Infrastructure
**Wave:** 1
**Autonomous:** yes
**Depends on:** None

## Objective

Standardize test infrastructure across the entire test suite, ensuring consistent fixtures, Hypothesis settings, and test utilities that prevent flaky tests and data fragility.

## Requirements

- AR-02: Test Infrastructure Standardization - Standardize fixtures, Hypothesis settings, test utilities for consistent testing

## Files Modified

- `tests/conftest.py` - Root conftest with standardized fixtures
- `tests/property_tests/conftest.py` - Hypothesis settings for property-based tests
- `tests/utilities/helpers.py` - Test helper functions
- `tests/utilities/assertions.py` - Custom assertion helpers
- `tests/utilities/factories.py` - Test data factories
- `tests/TEST_STANDARDS.md` - Documentation of standards and anti-patterns

## Tasks

### Task 1: Standardize Root conftest.py

**Files:** `tests/conftest.py`

**Action:**
```python
# Create standardized root conftest.py with all essential fixtures
import pytest
import tempfile
import shutil
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from unittest.mock import AsyncMock, MagicMock

# =============================================================================
# DATABASE FIXTURES
# =============================================================================

@pytest.fixture(scope="function")
def db_session():
    """
    Temp file-based SQLite database session for tests.

    Uses temp file instead of :memory: to avoid connection isolation issues
    with SQLAlchemy 2.0 and pytest-asyncio. Each test gets a clean database.

    Yields:
        Session: SQLAlchemy session for database operations
    """
    # Create temp file for SQLite database
    temp_db = tempfile.NamedTemporaryFile(mode="w", suffix=".db", delete=False)
    temp_db.close()

    # Create database engine
    engine = create_engine(f"sqlite:///{temp_db.name}", echo=False)

    # Create all tables
    from core.models import Base
    Base.metadata.create_all(engine)

    # Create session
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    yield session

    # Cleanup: close session and delete temp file
    session.close()
    engine.dispose()
    Path(temp_db.name).unlink(missing_ok=True)

# =============================================================================
# AGENT FIXTURES (All Maturity Levels)
# =============================================================================

@pytest.fixture(scope="function")
def test_agent(db_session):
    """
    Create a test agent at STUDENT maturity level.

    Yields:
        Agent: Test agent with STUDENT maturity
    """
    from core.models import AgentRegistry
    from core.agent_governance_service import GOVERNANCE_CONFIG

    agent = AgentRegistry(
        agent_id="test-student-agent",
        agent_name="Test Student Agent",
        maturity_level="STUDENT",
        confidence=0.3,
        capabilities=["present"],
        config=GOVERNANCE_CONFIG
    )
    db_session.add(agent)
    db_session.commit()

    return agent

@pytest.fixture(scope="function")
def test_intern_agent(db_session):
    """
    Create a test agent at INTERN maturity level.

    Yields:
        Agent: Test agent with INTERN maturity
    """
    from core.models import AgentRegistry
    from core.agent_governance_service import GOVERNANCE_CONFIG

    agent = AgentRegistry(
        agent_id="test-intern-agent",
        agent_name="Test Intern Agent",
        maturity_level="INTERN",
        confidence=0.6,
        capabilities=["present", "stream"],
        config=GOVERNANCE_CONFIG
    )
    db_session.add(agent)
    db_session.commit()

    return agent

@pytest.fixture(scope="function")
def test_supervised_agent(db_session):
    """
    Create a test agent at SUPERVISED maturity level.

    Yields:
        Agent: Test agent with SUPERVISED maturity
    """
    from core.models import AgentRegistry
    from core.agent_governance_service import GOVERNANCE_CONFIG

    agent = AgentRegistry(
        agent_id="test-supervised-agent",
        agent_name="Test Supervised Agent",
        maturity_level="SUPERVISED",
        confidence=0.8,
        capabilities=["present", "stream", "forms"],
        config=GOVERNANCE_CONFIG
    )
    db_session.add(agent)
    db_session.commit()

    return agent

@pytest.fixture(scope="function")
def test_autonomous_agent(db_session):
    """
    Create a test agent at AUTONOMOUS maturity level.

    Yields:
        Agent: Test agent with AUTONOMOUS maturity
    """
    from core.models import AgentRegistry
    from core.agent_governance_service import GOVERNANCE_CONFIG

    agent = AgentRegistry(
        agent_id="test-autonomous-agent",
        agent_name="Test Autonomous Agent",
        maturity_level="AUTONOMOUS",
        confidence=0.95,
        capabilities=["present", "stream", "forms", "delete"],
        config=GOVERNANCE_CONFIG
    )
    db_session.add(agent)
    db_session.commit()

    return agent

@pytest.fixture(scope="function")
def test_agent_by_maturity(db_session, maturity_level):
    """
    Create a test agent at the specified maturity level.

    Args:
        maturity_level: One of "STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"

    Yields:
        Agent: Test agent at requested maturity level
    """
    from core.models import AgentRegistry
    from core.agent_governance_service import GOVERNANCE_CONFIG

    # Map maturity levels to confidence and capabilities
    maturity_config = {
        "STUDENT": {"confidence": 0.3, "capabilities": ["present"]},
        "INTERN": {"confidence": 0.6, "capabilities": ["present", "stream"]},
        "SUPERVISED": {"confidence": 0.8, "capabilities": ["present", "stream", "forms"]},
        "AUTONOMOUS": {"confidence": 0.95, "capabilities": ["present", "stream", "forms", "delete"]}
    }

    config = maturity_config.get(maturity_level)
    assert config is not None, f"Invalid maturity level: {maturity_level}"

    agent = AgentRegistry(
        agent_id=f"test-{maturity_level.lower()}-agent",
        agent_name=f"Test {maturity_level} Agent",
        maturity_level=maturity_level,
        confidence=config["confidence"],
        capabilities=config["capabilities"],
        config=GOVERNANCE_CONFIG
    )
    db_session.add(agent)
    db_session.commit()

    return agent

# =============================================================================
# LLM FIXTURES (Deterministic Mocking)
# =============================================================================

@pytest.fixture(scope="function")
def mock_llm_response():
    """
    Mock LLM response fixture for deterministic testing.

    Returns a callable that generates deterministic LLM responses.

    Yields:
        Callable: Function that returns mocked LLM responses
    """
    def _create_response(text: str, tokens: int = 100) -> dict:
        return {
            "text": text,
            "tokens": tokens,
            "model": "mock-model",
            "finish_reason": "stop"
        }

    yield _create_response

@pytest.fixture(scope="function")
def mock_llm_stream():
    """
    Mock LLM streaming response fixture for deterministic testing.

    Yields:
        Callable: Async generator that yields streaming tokens
    """
    async def _stream_response(text: str):
        """Stream text token by token"""
        words = text.split()
        for i, word in enumerate(words):
            chunk = {
                "id": "mock-chunk-1",
                "object": "chat.completion.chunk",
                "created": 1234567890,
                "model": "mock-model",
                "choices": [{
                    "delta": {"content": word + (" " if i < len(words) - 1 else "")},
                    "finish_reason": None
                }]
            }
            yield chunk

        # Final chunk
        yield {
            "id": "mock-chunk-1",
            "object": "chat.completion.chunk",
            "created": 1234567890,
            "model": "mock-model",
            "choices": [{
                "delta": {},
                "finish_reason": "stop"
            }]
        }

    yield _stream_response

# =============================================================================
# EMBEDDING FIXTURES (Controlled Similarity)
# =============================================================================

@pytest.fixture(scope="function")
def mock_embedding_vectors():
    """
    Mock embedding vectors with controlled similarity for testing.

    Yields:
        Callable: Function that generates mock embeddings with predictable similarity
    """
    import numpy as np

    # Pre-defined vectors with known cosine similarities
    vectors = {
        "similar": np.array([0.8, 0.6, 0.0, 0.0]),  # Similar to query
        "neutral": np.array([0.0, 0.0, 1.0, 0.0]),   # Neutral similarity
        "dissimilar": np.array([0.0, 0.0, 0.0, 1.0])  # Dissimilar to query
    }

    def _get_embedding(text_type: str) -> list:
        """Get mock embedding by type"""
        return vectors.get(text_type, vectors["neutral"]).tolist()

    def _compute_similarity(embedding1: list, embedding2: list) -> float:
        """Compute cosine similarity between two embeddings"""
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        return float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))

    yield {
        "get_embedding": _get_embedding,
        "compute_similarity": _compute_similarity,
        "vectors": vectors
    }

# =============================================================================
# REDIS FIXTURES (Fake In-Memory)
# =============================================================================

@pytest.fixture(scope="function")
def fake_redis():
    """
    Fake Redis fixture for in-memory pub/sub testing.

    Uses fakeredis to avoid real Redis dependency in tests.

    Yields:
        fakeredis.FakeStrictRedis: In-memory Redis replacement
    """
    try:
        import fakeredis
    except ImportError:
        pytest.skip("fakeredis not installed - required for Redis testing")

    fake_redis = fakeredis.FakeStrictRedis(decode_responses=True)
    yield fake_redis

# =============================================================================
# PYTEST CONFIGURATION
# =============================================================================

def pytest_configure(config):
    """Pytest configuration hook"""
    # Register custom markers
    config.addinivalue_line(
        "markers", "unit: Unit tests (fast, isolated)"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests (database, external services)"
    )
    config.addinivalue_line(
        "markers", "property: Property-based tests with Hypothesis"
    )
    config.addinivalue_line(
        "markers", "slow: Slow tests (>10 seconds)"
    )
    config.addinivalue_line(
        "markers", "security: Security-focused tests"
    )

# =============================================================================
# HOOKS
# =============================================================================

@pytest.fixture(autouse=True)
def clean_test_files():
    """
    Auto-use fixture to clean up test files before and after each test.

    Prevents test data from leaking between tests.
    """
    # Setup: Run before test
    yield
    # Teardown: Run after test
    # Clean up any temporary files created during test
    temp_dir = Path("tests/tmp")
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
```

**Verify:**
- [ ] conftest.py created in tests/ directory
- [ ] All 5 fixture types included: db_session, test_agent (all 4 maturity levels), mock_llm_response, mock_llm_stream, mock_embedding_vectors
- [ ] db_session uses temp file (not :memory:) for SQLite
- [ ] test_agent fixtures parametrized by maturity level
- [ ] fake_redis fixture included with fakeredis
- [ ] pytest_configure adds markers: unit, integration, property, slow, security
- [ ] clean_test_files auto-use fixture prevents test data leakage

**Done:**
- conftest.py exists with standardized fixtures
- All tests can import and use these fixtures

---

### Task 2: Configure Hypothesis Settings

**Files:** `tests/property_tests/conftest.py`

**Action:**
```python
# Configure Hypothesis for property-based testing
from hypothesis import settings, Phase
import pytest

# =============================================================================
# HYPOTHESIS SETTINGS
# =============================================================================

# Local development: More examples for thorough testing
settings.register_profile(
    "local",
    max_examples=200,
    deadline=None,  # No deadline for complex property tests
    phases=[Phase.generate, Phase.target, Phase.shrink]
)

# CI: Fewer examples for faster feedback
settings.register_profile(
    "ci",
    max_examples=50,
    deadline=500,  # 500ms per test
    phases=[Phase.generate, Phase.target]  # Skip shrinking in CI
)

# Load default profile
settings.load_profile("local" if pytest.ini_exists("pytest.ini") else "ci")

# =============================================================================
# PYTEST FIXTURES FOR PROPERTY TESTS
# =============================================================================

@pytest.fixture(scope="session")
def hypothesis_settings():
    """
    Hypothesis settings fixture for property tests.

    Returns current Hypothesis settings for verification in tests.

    Yields:
        hypothesis.settings: Current Hypothesis settings
    """
    yield settings

# =============================================================================
# CUSTOM HYPOTHESIS STRATEGIES
# =============================================================================

from hypothesis import strategies as st
from typing import List
import numpy as np

# Agent ID strategy
agent_ids = st.text(min_size=5, max_size=50).filter(lambda x: x.isalnum() or "_" in x or "-" in x)

# Confidence score strategy (0.0 to 1.0, no NaN or Infinity)
confidence_scores = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

# Maturity level strategy
maturity_levels = st.sampled_from(["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"])

# Embedding vector strategy (384-dim, normalized)
embedding_vectors = st.lists(
    st.floats(min_value=-1.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    min_size=384,
    max_size=384
).map(lambda x: np.array(x) / np.linalg.norm(x))  # Normalize

# Episode ID strategy
episode_ids = st.uuids(version=4).map(str)

# Token count strategy (non-negative integers)
token_counts = st.integers(min_value=0, max_value=100000)

# =============================================================================
# PROPERTY TEST UTILITIES
# =============================================================================

def assume_governance_rules(agent_id: str, confidence: float, maturity: str, action_complexity: int):
    """
    Assume common governance rules for property tests.

    Helper function to assume invariants without failing tests.

    Args:
        agent_id: Agent identifier
        confidence: Confidence score
        maturity: Maturity level
        action_complexity: Action complexity (1-4)
    """
    from hypothesis import assume

    # STUDENT agents have confidence <0.5
    if maturity == "STUDENT":
        assume(confidence < 0.5)
        assume(action_complexity <= 1)  # Can only do complexity 1

    # INTERN agents have confidence 0.5-0.7
    elif maturity == "INTERN":
        assume(0.5 <= confidence < 0.7)
        assume(action_complexity <= 2)

    # SUPERVISED agents have confidence 0.7-0.9
    elif maturity == "SUPERVISED":
        assume(0.7 <= confidence < 0.9)
        assume(action_complexity <= 3)

    # AUTONOMOUS agents have confidence >0.9
    elif maturity == "AUTONOMOUS":
        assume(confidence >= 0.9)
        assume(action_complexity <= 4)
```

**Verify:**
- [ ] property_tests/conftest.py created
- [ ] Hypothesis profiles registered: local (200 examples), CI (50 examples)
- [ ] Default profile loaded based on environment
- [ ] Custom strategies defined: agent_ids, confidence_scores, maturity_levels, embedding_vectors, episode_ids, token_counts
- [ ] assume_governance_rules helper function included
- [ ] pytest fixtures: hypothesis_settings for verification

**Done:**
- Hypothesis settings configured for local and CI environments
- Property tests have consistent max_examples settings
- Custom strategies available for generating test data

---

### Task 3: Create Test Utilities

**Files:** `tests/utilities/helpers.py`, `tests/utilities/assertions.py`, `tests/utilities/__init__.py`

**Action:**

**helpers.py:**
```python
"""Test helper functions for common test operations."""

from typing import List, Dict, Any
from pathlib import Path
import tempfile
import shutil

def create_test_episode(db_session, agent_id: str, summary: str, **kwargs):
    """
    Create a test episode with default values.

    Args:
        db_session: Database session
        agent_id: Agent ID
        summary: Episode summary
        **kwargs: Additional episode fields

    Returns:
        Episode: Created episode object
    """
    from core.models import Episode
    from datetime import datetime, timezone

    episode = Episode(
        agent_id=agent_id,
        summary=summary,
        start_time=datetime.now(timezone.utc),
        end_time=datetime.now(timezone.utc),
        **kwargs
    )
    db_session.add(episode)
    db_session.commit()

    return episode

def create_test_skill(db_session, skill_name: str, skill_type: str, **kwargs):
    """
    Create a test community skill with default values.

    Args:
        db_session: Database session
        skill_name: Name of the skill
        skill_type: Type of skill (prompt or python)
        **kwargs: Additional skill fields

    Returns:
        CommunitySkill: Created skill object
    """
    from core.models import CommunitySkill

    skill = CommunitySkill(
        skill_name=skill_name,
        skill_type=skill_type,
        status="untrusted",
        **kwargs
    )
    db_session.add(skill)
    db_session.commit()

    return skill

def wait_for_condition(condition_func, timeout: float = 5.0, interval: float = 0.1):
    """
    Wait for a condition to become true.

    Useful for async tests with state changes.

    Args:
        condition_func: Callable that returns bool
        timeout: Maximum time to wait in seconds
        interval: Polling interval in seconds

    Returns:
        bool: True if condition met, False if timeout
    """
    import time

    start = time.time()
    while time.time() - start < timeout:
        if condition_func():
            return True
        time.sleep(interval)
    return False

def create_temp_directory():
    """
    Create a temporary directory for testing.

    Returns:
        Path: Path to temporary directory
    """
    temp_dir = Path(tempfile.mkdtemp())
    return temp_dir

def cleanup_temp_directory(temp_dir: Path):
    """
    Clean up a temporary directory.

    Args:
        temp_dir: Path to temporary directory
    """
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
```

**assertions.py:**
```python
"""Custom assertion helpers for common test checks."""

from typing import List, Optional
import numpy as np

def assert_coverage_at_least(actual_coverage: float, minimum_coverage: float, component: str):
    """
    Assert that actual coverage meets minimum threshold.

    Args:
        actual_coverage: Actual coverage percentage
        minimum_coverage: Minimum required coverage
        component: Component name for error message

    Raises:
        AssertionError: If coverage below minimum
    """
    assert actual_coverage >= minimum_coverage, (
        f"{component} coverage ({actual_coverage:.1f}%) below minimum ({minimum_coverage:.1f}%)"
    )

def assert_maturity_routing(confidence: float, expected_maturity: str):
    """
    Assert that confidence score maps to expected maturity level.

    Args:
        confidence: Confidence score
        expected_maturity: Expected maturity level

    Raises:
        AssertionError: If confidence doesn't match maturity level
    """
    maturity_rules = {
        "STUDENT": (0.0, 0.5),
        "INTERN": (0.5, 0.7),
        "SUPERVISED": (0.7, 0.9),
        "AUTONOMOUS": (0.9, 1.0)
    }

    min_conf, max_conf = maturity_rules.get(expected_maturity, (0, 0))

    assert min_conf <= confidence <= max_conf, (
        f"Confidence {confidence} doesn't match {expected_maturity} (expected range: {min_conf}-{max_conf})"
    )

def assert_embedding_similarity(embedding1: List[float], embedding2: List[float], min_similarity: float = 0.85):
    """
    Assert that two embeddings have minimum cosine similarity.

    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector
        min_similarity: Minimum required similarity

    Raises:
        AssertionError: If similarity below minimum
    """
    vec1 = np.array(embedding1)
    vec2 = np.array(embedding2)

    similarity = float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))

    assert similarity >= min_similarity, (
        f"Embedding similarity ({similarity:.3f}) below minimum ({min_similarity:.3f})"
    )

def assert_governance_cache_performance(latency_ms: float, max_latency_ms: float = 10.0):
    """
    Assert that governance cache lookup meets performance requirement.

    Args:
        latency_ms: Actual latency in milliseconds
        max_latency_ms: Maximum acceptable latency

    Raises:
        AssertionError: If latency exceeds maximum
    """
    assert latency_ms <= max_latency_ms, (
        f"Governance cache lookup ({latency_ms:.3f}ms) exceeds maximum ({max_latency_ms:.3f}ms)"
    )

def assert_no_duplicates(items: List[Any], item_type: str = "items"):
    """
    Assert that a list contains no duplicate items.

    Args:
        items: List of items to check
        item_type: Type name for error message

    Raises:
        AssertionError: If duplicates found
    """
    unique_items = set(items)
    duplicates = [item for item in unique_items if items.count(item) > 1]

    assert len(duplicates) == 0, (
        f"Found {len(duplicates)} duplicate {item_type}: {duplicates[:5]}"
        + (f" ... and {len(duplicates) - 5} more" if len(duplicates) > 5 else "")
    )
```

**__init__.py:**
```python
"""Test utilities module."""

from .helpers import (
    create_test_episode,
    create_test_skill,
    wait_for_condition,
    create_temp_directory,
    cleanup_temp_directory
)

from .assertions import (
    assert_coverage_at_least,
    assert_maturity_routing,
    assert_embedding_similarity,
    assert_governance_cache_performance,
    assert_no_duplicates
)

__all__ = [
    # Helpers
    "create_test_episode",
    "create_test_skill",
    "wait_for_condition",
    "create_temp_directory",
    "cleanup_temp_directory",
    # Assertions
    "assert_coverage_at_least",
    "assert_maturity_routing",
    "assert_embedding_similarity",
    "assert_governance_cache_performance",
    "assert_no_duplicates"
]
```

**Verify:**
- [ ] tests/utilities/ directory created
- [ ] helpers.py created with 6 helper functions
- [ ] assertions.py created with 5 assertion functions
- [ ] __init__.py exports all utilities
- [ ] All helpers have docstrings
- [ ] All assertions have clear error messages

**Done:**
- Test utilities module created
- Helpers reduce test boilerplate
- Assertions provide consistent error messages

---

### Task 4: Document Test Standards

**Files:** `tests/TEST_STANDARDS.md`

**Action:**
```markdown
# Test Standards and Guidelines

**Last Updated:** February 17, 2026
**Purpose:** Document testing standards, patterns, and anti-patterns for the Atom test suite

---

## Fixture Usage Standards

### Database Fixtures

**DO:**
```python
def test_episode_creation(db_session):
    episode = Episode(summary="test")
    db_session.add(episode)
    db_session.commit()

    assert episode.id is not None
```

**DON'T:**
```python
# DON'T: Create database connections manually
def test_episode_creation():
    engine = create_engine("sqlite:///:memory:")
    # Bad: Connection isolation issues
```

**Rationale:** db_session fixture provides clean, isolated database per test with automatic cleanup.

---

### Agent Fixtures

**DO:**
```python
def test_student_agent_blocked(test_agent):
    assert test_agent.maturity_level == "STUDENT"
    assert test_agent.confidence < 0.5
```

**DON'T:**
```python
# DON'T: Hardcode agent properties
def test_agent_governance():
    agent = Agent(
        agent_id="test",
        maturity_level="STUDENT",
        confidence=0.3  # Magic number
    )
```

**Rationale:** Fixtures provide consistent, parametrized test data. Hardcoded values create maintenance burden.

---

### LLM Fixtures

**DO:**
```python
def test_llm_generation(mock_llm_response):
    response = mock_llm_response("Hello world", tokens=2)
    assert response["text"] == "Hello world"
    assert response["tokens"] == 2
```

**DON'T:**
```python
# DON'T: Call real LLM in unit tests
def test_llm_generation():
    llm = OpenAI(api_key="...")
    response = llm.generate("Hello")
    # Bad: Slow, non-deterministic, requires API key
```

**Rationale:** Mocked responses ensure deterministic, fast tests. Real LLM calls reserved for integration tests.

---

## Hypothesis Settings

### Local Development

- **max_examples:** 200 (thorough testing)
- **deadline:** None (no time limit)
- **Phases:** generate, target, shrink (full testing)

### CI Environment

- **max_examples:** 50 (faster feedback)
- **deadline:** 500ms per test
- **Phases:** generate, target (no shrinking for speed)

**Rationale:** More examples locally for thoroughness, fewer in CI for speed.

---

## Test Organization

### Test File Placement

```
tests/
├── unit/              # Fast, isolated unit tests
│   ├── test_governance.py
│   └── test_memory.py
├── integration/       # Component interaction tests
│   ├── test_agent_execution.py
│   └── test_episode_creation.py
├── property_tests/    # Hypothesis property tests
│   ├── governance/
│   │   └── test_cache_invariants.py
│   └── llm/
│       └── test_routing_invariants.py
└── utilities/         # Test helpers and assertions
    ├── helpers.py
    └── assertions.py
```

### Test Markers

Use pytest markers to categorize tests:

```python
@pytest.mark.unit
def test_governance_logic():
    """Unit test - fast, isolated"""
    pass

@pytest.mark.integration
def test_agent_execution():
    """Integration test - database, external services"""
    pass

@pytest.mark.property
def test_cache_performance():
    """Property test - Hypothesis generated"""
    pass

@pytest.mark.slow
def test_large_dataset_processing():
    """Slow test - takes >10 seconds"""
    pass

@pytest.mark.security
def test_shell_injection_blocked():
    """Security test - input validation, fuzzing"""
    pass
```

---

## Anti-Patterns to Avoid

### 1. Testing Implementation Details

**BAD:**
```python
def test_agent_internal_state():
    agent = Agent()
    assert agent._internal_cache == {}  # Tests private attribute
```

**GOOD:**
```python
def test_agent_behavior():
    agent = create_agent()
    result = agent.execute("test task")
    assert result.status == "completed"  # Tests observable behavior
```

---

### 2. Ignoring Test Data Cleanup

**BAD:**
```python
def test_episode_creation():
    episode = Episode(summary="test")
    db.add(episode)
    db.commit()
    # Missing cleanup - pollutes database for next test
```

**GOOD:**
```python
def test_episode_creation(db_session):
    episode = Episode(summary="test")
    db_session.add(episode)
    db_session.commit()

    try:
        assert episode.id is not None
    finally:
        db_session.delete(episode)
        db_session.commit()
```

**Even Better:** Let fixtures handle cleanup automatically (db_session fixture handles this).

---

### 3. Property Tests Without Invariants

**BAD:**
```python
@given(st.text())
def test_summary_generation(text):
    episode = Episode(summary=text)
    assert episode.summary == text  # Trivial, no invariant
```

**GOOD:**
```python
@given(st.text(min_size=1, max_size=1000))
def test_summary_length_invariant(text):
    """INVARIANT: Episode summaries must be <=1000 chars."""
    episode = Episode(summary=text)

    if len(text) > 1000:
        assert len(episode.summary) <= 1000
    else:
        assert len(episode.summary) == len(text)
```

---

### 4. Over-Mocking LLM Responses

**BAD:**
```python
def test_agent_execution():
    # Mock EVERYTHING - no real logic tested
    with patch('agent.llm'), patch('agent.db'), patch('agent.governance'):
        agent.execute()
```

**GOOD:**
```python
def test_agent_execution(db_session):
    # Use real database, mock only external LLM
    with patch('agent.llm.generate') as mock_llm:
        mock_llm.return_value = "Task completed"
        result = agent.execute("test task")

        assert result.status == "completed"
        # Verify database state
        executions = db_session.query(AgentExecution).all()
        assert len(executions) == 1
```

---

## Coverage Prioritization

### Priority Levels

1. **P0 (Critical)** - 100% coverage required:
   - Governance checks (maturity routing, permissions)
   - Security boundaries (shell injection, sandbox escape)
   - LLM integration (provider routing, streaming)
   - Episodic memory (segmentation, retrieval)

2. **P1 (High)** - 90%+ coverage:
   - Agent system (graduation, context resolution)
   - Community skills (parsing, sandbox)
   - Local agent (file access, command whitelist)

3. **P2 (Medium)** - 80%+ coverage:
   - Tools (browser, device, canvas)
   - API routes
   - IM adapters

4. **P3 (Low)** - 50%+ coverage:
   - Models/DTOs
   - Utilities
   - Helpers

---

## Performance Standards

### Test Execution Time

- **Unit tests:** <100ms each
- **Integration tests:** <1s each
- **Property tests:** <10s each (with max_examples=200)
- **Slow tests:** Explicitly marked with `@pytest.mark.slow`

### Parallel Execution

Use pytest-xdist for parallel execution:

```bash
# Run tests in parallel
pytest -n auto

# Run only fast tests in parallel
pytest -n auto -m "not slow"
```

---

## Quality Checklist

Before committing new tests, verify:

- [ ] Tests use standardized fixtures (no manual setup)
- [ ] Tests have clear docstrings explaining what is tested
- [ ] Tests have at least one assertion
- [ ] Tests are deterministic (pass consistently)
- [ ] Tests are fast (<10s for unit/integration)
- [ ] Property tests document invariants in docstrings
- [ ] No hardcoded test data (use fixtures/factories)
- [ ] Tests follow naming convention: test_<function>_<behavior>
- [ ] Security tests use fuzzing where appropriate
- [ ] LLM tests use three-tier strategy (unit mocks, integration with temperature=0, E2E with temperature=0.7)

---

*Test standards documented: February 17, 2026*
*Next: Review and update quarterly*
```

**Verify:**
- [ ] TEST_STANDARDS.md created in tests/ directory
- [ ] Document covers fixtures, Hypothesis settings, test organization
- [ ] Anti-patterns section with examples of bad vs good patterns
- [ ] Coverage prioritization guidelines (P0-P3)
- [ ] Performance standards documented
- [ ] Quality checklist for test review

**Done:**
- Comprehensive test standards document created
- Team has clear guidelines for writing tests
- Anti-patterns documented to prevent common mistakes

---

## Success Criteria

### Must Haves

1. **Standardized Fixtures**
   - [ ] conftest.py with db_session (temp file-based SQLite)
   - [ ] test_agent fixtures for all 4 maturity levels
   - [ ] mock_llm_response and mock_llm_stream fixtures
   - [ ] mock_embedding_vectors fixture with controlled similarity
   - [ ] fake_redis fixture for in-memory pub/sub

2. **Hypothesis Configuration**
   - [ ] Local profile: max_examples=200, no deadline
   - [ ] CI profile: max_examples=50, 500ms deadline
   - [ ] Custom strategies defined (agent_ids, confidence_scores, etc.)
   - [ ] Property tests can import settings from conftest

3. **Test Utilities**
   - [ ] helpers.py with 6 helper functions
   - [ ] assertions.py with 5 custom assertion functions
   - [ ] __init__.py exports all utilities
   - [ ] All utilities have docstrings

4. **Documentation**
   - [ ] TEST_STANDARDS.md covers fixtures, Hypothesis, organization
   - [ ] Anti-patterns documented with examples
   - [ ] Coverage prioritization (P0-P3) defined
   - [ ] Performance standards documented
   - [ ] Quality checklist for test review

5. **Consistency**
   - [ ] All new tests use standardized fixtures
   - [ ] No hardcoded test data
   - [ ] Tests follow naming convention
   - [ ] Tests have clear docstrings
   - [ ] Tests are deterministic and fast

### Success Definition

Plan is **SUCCESSFUL** when:
- All 4 tasks completed successfully
- Standardized fixtures available for all tests
- Hypothesis configured for local and CI
- Test utilities reduce boilerplate
- Team has clear testing standards documented
- Foundation established for Phase 2 (Core Invariants)

---

## Open Questions

1. **Fixture Scope**: Should we use function scope for all fixtures (current approach) or session scope for expensive fixtures like fake_redis?
2. **Hypothesis max_examples**: Is 200 examples too many for local development? Should we reduce to 100 for faster iteration?
3. **Test Utilities**: Are there additional helper functions or assertions needed beyond the 6 helpers and 5 assertions?
4. **FakeRedis**: Should we include fakeredis as a required dependency or make it optional for tests that need Redis?

---

*Plan created: February 17, 2026*
*Estimated effort: 1-2 days*
*Dependencies: None*
