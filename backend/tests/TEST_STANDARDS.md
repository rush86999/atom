# Test Standards and Best Practices

This document outlines the testing standards, patterns, and best practices for the Atom backend test suite. Following these guidelines ensures consistent, maintainable, and reliable tests across the codebase.

## Table of Contents

- [Fixture Usage Guidelines](#fixture-usage-guidelines)
- [Maturity Level Testing](#maturity-level-testing)
- [Property Test Patterns](#property-test-patterns)
- [Assertion Best Practices](#assertion-best-practices)
- [Performance Guidelines](#performance-guidelines)
- [Anti-Patterns](#anti-patterns)
- [Quick Reference](#quick-reference)

---

## Fixture Usage Guidelines

### Database Sessions

**DO:** Use `db_session` fixture for all database operations

```python
def test_agent_creation(db_session: Session):
    agent = AgentRegistry(name="test", category="test", ...)
    db_session.add(agent)
    db_session.commit()
    assert agent.id is not None
```

**DON'T:** Create database sessions directly in tests

```python
# BAD: Direct session creation
def test_agent_creation():
    engine = create_engine("sqlite:///:memory:")
    session = Session(engine)
    # Fragile: Breaks isolation, hard to maintain
```

### Test Agents

**DO:** Use maturity-specific fixtures for governance testing

```python
# GOOD: Use maturity-specific fixtures
def test_student_blocked_from_deletes(test_agent_student):
    with pytest.raises(PermissionError):
        execute_delete_action(test_agent_student)

def test_autonomous_can_delete(test_agent_autonomous):
    result = execute_delete_action(test_agent_autonomous)
    assert result.success is True
```

**DON'T:** Manually create agents with hardcoded maturity values

```python
# BAD: Manual agent creation
def test_student_blocked_from_deletes():
    agent = AgentRegistry(
        name="test",
        status=AgentStatus.STUDENT.value,  # Fragile: breaks if values change
        confidence_score=0.3,
        ...
    )
```

### LLM Mocking

**DO:** Use `mock_llm_response` fixture for deterministic LLM responses

```python
# GOOD: Deterministic LLM mocking
def test_agent_response(mock_llm_response):
    response = mock_llm_response.complete("test prompt")
    assert response == "Mock response 1 for: test prompt"

def test_llm_errors(mock_llm_response):
    mock_llm_response.set_error_mode("rate_limited")
    with pytest.raises(Exception, match="Rate limit"):
        mock_llm_response.complete("test")
```

**DON'T:** Call real LLM APIs in tests

```python
# BAD: Real API calls
def test_agent_response():
    handler = BYOKHandler()  # Calls real OpenAI/Anthropic APIs
    response = handler.complete("test")
    # Slow, expensive, non-deterministic
```

---

## Maturity Level Testing

### Testing Governance by Maturity

The Atom platform uses a four-tier maturity system for agent governance:

| Level | Confidence | Automated Triggers | Capabilities |
|-------|-----------|-------------------|--------------|
| STUDENT | <0.5 | **BLOCKED** | Read-only (charts, markdown) |
| INTERN | 0.5-0.7 | **PROPOSAL ONLY** | Streaming, form presentation |
| SUPERVISED | 0.7-0.9 | **RUN UNDER SUPERVISION** | Form submissions, state changes |
| AUTONOMOUS | >0.9 | **FULL EXECUTION** | Full autonomy, all actions |

### Maturity Testing Patterns

**Correct:** Use maturity-specific fixtures

```python
def test_student_read_only(test_agent_student, db_session):
    """STUDENT agents can only read, not write."""
    # Can read
    data = fetch_data(test_agent_student)
    assert data is not None

    # Cannot write
    with pytest.raises(PermissionError):
        modify_data(test_agent_student, {})

def test_intern_requires_approval(test_agent_intern, db_session):
    """INTERN agents require approval for actions."""
    proposal = submit_action(test_agent_intern, action="delete")
    assert proposal.status == "pending_approval"
    assert proposal.requires_approval is True

def test_supervised_monitored(test_agent_supervised, db_session):
    """SUPERVISED agents run under monitoring."""
    result = execute_action(test_agent_supervised, action="modify")
    assert result.executed is True
    assert result.monitored is True
    assert result.supervisor_id is not None

def test_autonomous_full_access(test_agent_autonomous, db_session):
    """AUTONOMOUS agents have full access."""
    result = execute_action(test_agent_autonomous, action="delete")
    assert result.success is True
    assert result.monitored is False
```

**Incorrect:** Hardcoded maturity values

```python
# BAD: Fragile to enum changes
def test_student_blocked_from_deletes():
    agent = AgentRegistry(
        name="test",
        status=AgentStatus.STUDENT.value,  # Breaks if value changes
        confidence_score=0.3,
    )
    # Test implementation...
```

### Using Custom Assertions

Use the custom assertion functions from `tests.utilities` for better error messages:

```python
from tests.utilities import assert_agent_maturity

def test_agent_promotion(db_session):
    agent = create_test_agent(db_session, maturity="STUDENT")
    promote_agent(agent, new_maturity="INTERN")
    assert_agent_maturity(agent, "INTERN")
    # Output: "INTERN agent has confidence 0.6, expected [0.5, 0.7)"
```

---

## Property Test Patterns

### When to Use Hypothesis

**Use Hypothesis (Property-Based Testing):**
- Testing system invariants (confidence scores, maturity transitions)
- Validating mathematical properties (cosine similarity, sorting)
- Finding edge cases that example-based tests miss
- Testing with random inputs within constraints

**Use Example-Based Testing:**
- Testing specific workflows and business logic
- API contracts and endpoint behavior
- Integration testing with external services
- UI/UX testing scenarios

### Property Test Examples

**Good:** Property test for confidence score invariants

```python
from hypothesis import given, settings
from tests.property_tests.conftest import DEFAULT_PROFILE, confidence_scores

@given(confidence_scores())
@settings(DEFAULT_PROFILE)
def test_confidence_in_bounds(confidence):
    """Confidence scores must be in [0.0, 1.0]."""
    agent = create_test_agent(db_session, confidence=confidence)
    assert 0.0 <= agent.confidence_score <= 1.0

@given(confidence_scores(), confidence_scores())
@settings(DEFAULT_PROFILE)
def test_confidence_comparison(conf1, conf2):
    """Confidence comparisons should be consistent."""
    if conf1 > conf2:
        agent1 = create_test_agent(db_session, confidence=conf1)
        agent2 = create_test_agent(db_session, confidence=conf2)
        assert agent1.confidence_score > agent2.confidence_score
```

**Good:** Property test for embedding similarity

```python
from tests.property_tests.conftest import DEFAULT_PROFILE
from hypothesis import strategies as st

@given(st.text(), st.text())
@settings(DEFAULT_PROFILE)
def test_cosine_similarity_bounds(text1, text2):
    """Cosine similarity should always be in [-1, 1]."""
    vec1 = mock_embedding_vectors.embed(text1)
    vec2 = mock_embedding_vectors.embed(text2)
    similarity = mock_embedding_vectors.cosine_similarity(vec1, vec2)
    assert -1.0 <= similarity <= 1.0
```

### Property Test Settings

Use the tiered settings for appropriate test execution time:

```python
from tests.property_tests.conftest import small_settings, medium_settings, large_settings

# Fast: <10s
@settings(small_settings)
def test_simple_invariant(x):
    assert x == x

# Standard: <60s
@settings(medium_settings)
def test_database_invariant(db_session, agent_id):
    agent = get_agent(db_session, agent_id)
    assert agent.id == agent_id

# Slow: <100s
@settings(large_settings)
def test_complex_system_invariant():
    # Expensive operations
    pass
```

---

## Assertion Best Practices

### Use Custom Assertions

**DO:** Use custom assertions with helpful error messages

```python
# GOOD: Custom assertion with detailed error
from tests.utilities import assert_agent_maturity, assert_governance_blocked

def test_governance_by_maturity(db_session):
    student = create_test_agent(db_session, maturity="STUDENT")
    assert_agent_maturity(student, "STUDENT")
    # Output: "STUDENT agent has confidence 0.3, expected < 0.5"

    result = execute_action(student, action="delete")
    assert_governance_blocked(student.id, "delete", reason="maturity")
    # Output: "Action delete was not blocked for agent abc-123"
```

**DON'T:** Use raw assert for complex conditions

```python
# BAD: Raw assert with vague error
def test_governance_by_maturity():
    agent = AgentRegistry(status=AgentStatus.STUDENT.value, ...)
    assert agent.status == "student", "Not student"  # Unhelpful message
```

### Assertion Patterns

**Database Assertions:**

```python
from tests.utilities import assert_episode_created, assert_canvas_presented

def test_episode_creation(db_session, agent_id):
    # Create episode segments
    create_segments(agent_id, [seg1, seg2, seg3])

    # Assert episode created with minimum segments
    episode = assert_episode_created(db_session, agent_id, min_segments=3)
    # Output: "Episode has 2 segments, expected >= 3"
```

**Performance Assertions:**

```python
from tests.utilities import assert_performance_baseline
import time

def test_query_performance(db_session):
    start = time.time()
    agents = db_session.query(AgentRegistry).all()
    duration = time.time() - start

    assert_performance_baseline(duration, 0.1, "query all agents")
    # Output: "query all agents took 0.15s, expected <= 0.10s"
```

**Coverage Assertions:**

```python
from tests.utilities import assert_coverage_threshold

def test_governance_coverage():
    with open("coverage.json") as f:
        coverage_data = json.load(f)

    assert_coverage_threshold(coverage_data, "governance_cache", 80.0)
    # Output: "Module governance_cache has 75.3% coverage, expected >= 80.0%"
```

---

## Performance Guidelines

### Test Duration Targets

| Test Type | Target | Rationale |
|-----------|--------|-----------|
| Unit tests | < 1s each | Fast feedback for development |
| Integration tests | < 5s each | Balance realism and speed |
| Property tests | < 60s total | Comprehensive invariant validation |

### Performance Optimization

**DO:** Mock external services

```python
# GOOD: Mock LLM, database, external APIs
def test_agent_logic(mock_llm_response, db_session):
    response = mock_llm_response.complete("test")
    assert "Mock response" in response
    # No network calls, deterministic output
```

**DON'T:** Call external services in tests

```python
# BAD: Real external calls
def test_agent_logic():
    handler = BYOKHandler()  # Calls OpenAI API
    response = handler.complete("test")
    # Slow, expensive, non-deterministic
```

### Parallel Execution

All tests must be parallel-safe using the `unique_resource_name` fixture:

```python
def test_file_operations(unique_resource_name):
    """No collision with parallel tests."""
    filename = f"{unique_resource_name}.txt"
    with open(filename, 'w') as f:
        f.write("test data")
    # Each test gets unique filename
```

**Anti-Pattern:** Shared state between tests

```python
# BAD: Shared state
class TestGroup:
    shared_resource = None  # Runs across tests!

    def test_one(self):
        self.shared_resource = "data"

    def test_two(self):
        # Fails if run in parallel with test_one
        assert self.shared_resource is None
```

---

## Anti-Patterns

### Hardcoded IDs

```python
# BAD: Hardcoded ID
agent = db_session.query(AgentRegistry).get("123e4567-e89b-12d3-a456-426614174000")

# GOOD: Create fresh agent or use fixture
agent = test_agent_autonomous(db_session)
```

### Shared State

```python
# BAD: Shared state between tests
class TestGroup:
    shared_agent = None  # Runs across tests!

# GOOD: Fresh fixtures per test
def test_one(test_agent):
    pass

def test_two(test_agent):  # Different instance
    pass
```

### Over-Mocking

```python
# BAD: Mocking everything, testing nothing
def test_agent_logic():
    agent = Mock()
    agent.execute = Mock(return_value="success")
    result = agent.execute("test")
    assert result == "success"  # Tautology

# GOOD: Test real logic, mock external dependencies
def test_agent_logic(db_session, mock_llm_response):
    agent = create_test_agent(db_session)
    result = agent.execute("test")  # Real logic
    assert result.success is True  # Real assertion
```

### Ignoring Test Isolation

```python
# BAD: Tests depend on execution order
def test_one():
    global state = "modified"

def test_two():
    # Fails if run before test_one
    assert global state is None

# GOOD: Each test is independent
def test_one(db_session):
    agent = create_test_agent(db_session, name="agent1")
    assert agent.name == "agent1"

def test_two(db_session):
    agent = create_test_agent(db_session, name="agent2")
    assert agent.name == "agent2"  # Isolated from test_one
```

---

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

| Fixture | Scope | Purpose |
|---------|-------|---------|
| `db_session` | Function | Database session (temp file-based SQLite) |
| `test_agent` | Function | Generic test agent |
| `test_agent_student` | Function | STUDENT maturity agent |
| `test_agent_intern` | Function | INTERN maturity agent |
| `test_agent_supervised` | Function | SUPERVISED maturity agent |
| `test_agent_autonomous` | Function | AUTONOMOUS maturity agent |
| `mock_llm_response` | Function | Deterministic LLM mock |
| `mock_embedding_vectors` | Function | Deterministic embedding mock |
| `unique_resource_name` | Function | Unique name for parallel tests |

### Assertion Reference

| Assertion | Purpose |
|-----------|---------|
| `assert_agent_maturity(agent, maturity)` | Assert maturity level |
| `assert_governance_blocked(agent_id, action)` | Assert action blocked |
| `assert_episode_created(db_session, agent_id)` | Assert episode exists |
| `assert_canvas_presented(db_session, agent_id)` | Assert canvas presented |
| `assert_coverage_threshold(coverage_data, module, min)` | Assert coverage |
| `assert_performance_baseline(duration, max, operation)` | Assert performance |

### Helper Reference

| Helper | Purpose |
|--------|---------|
| `create_test_agent(db_session, maturity, confidence)` | Create agent |
| `create_test_episode(db_session, agent_id)` | Create episode |
| `create_test_canvas(db_session, agent_id, canvas_type)` | Create canvas |
| `wait_for_condition(condition, timeout)` | Async wait |
| `mock_websocket()` | Mock WebSocket |
| `mock_byok_handler()` | Mock LLM handler |
| `clear_governance_cache(agent_id)` | Clear cache |

### Property Test Settings

| Setting | Max Examples | Deadline | Use For |
|---------|-------------|----------|---------|
| `small_settings` | 100 | 10s | Fast invariants |
| `medium_settings` | 200 | 60s | Standard tests |
| `large_settings` | 50 | 100s | Slow tests |
| `DEFAULT_PROFILE` | 200 (local) / 50 (CI) | None | Auto-select |

### Example Test Structure

```python
import pytest
from sqlalchemy.orm import Session
from tests.utilities import create_test_agent, assert_agent_maturity

class TestAgentFeature:
    """Test agent feature X."""

    def test_student_cannot_execute(self, test_agent_student, db_session):
        """STUDENT agents blocked from execution."""
        result = execute_action(test_agent_student, "delete")
        assert result.blocked is True

    def test_autonomous_can_execute(self, test_agent_autonomous, db_session):
        """AUTONOMOUS agents can execute."""
        result = execute_action(test_agent_autonomous, "delete")
        assert result.success is True
```

---

## Additional Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)
- [SQLAlchemy Testing](https://docs.sqlalchemy.org/en/20/orm/testing.html)
- [Factory Boy](https://factoryboy.readthedocs.io/)

---

*Last Updated: 2026-02-16*
*Phase: 01-foundation-infrastructure*
*Plan: 02*
