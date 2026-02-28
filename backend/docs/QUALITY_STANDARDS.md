# Quality Standards

**Purpose**: Define testing patterns, conventions, and quality metrics for Atom OS backend test suite.

**Last Updated**: 2026-02-25

---

## Table of Contents

1. [Testing Philosophy](#testing-philosophy)
2. [Test Patterns](#test-patterns)
3. [Test Naming Conventions](#test-naming-conventions)
4. [Quality Metrics](#quality-metrics)
5. [Anti-patterns to Avoid](#anti-patterns-to-avoid)
6. [Code Examples](#code-examples)

---

## Testing Philosophy

### Core Principles

1. **Tests are Code**
   - Maintain the same quality standards as production code
   - Apply code review, linting, and refactoring to tests
   - Keep tests DRY (Don't Repeat Yourself)
   - Use meaningful variable names and abstractions

2. **Single Responsibility**
   - One assertion per test (one logical assertion)
   - Tests should validate one behavior, not multiple
   - If a test has multiple assertions, they should be closely related
   - Split complex tests into smaller, focused tests

3. **Independence & Determinism**
   - Tests must run independently (no shared state)
   - Tests must be deterministic (same result every time)
   - Random order execution must pass (`--random-order`)
   - Clean up test data in `finally` blocks or fixtures

4. **Mock External Dependencies**
   - Mock external APIs (OpenAI, Anthropic, payment providers)
   - Test internal logic, not external services
   - Use factories/factories for test data
   - Keep test execution fast (<5 min for full suite)

### Why These Principles Matter

- **Maintainability**: Clear tests are easier to update when code changes
- **Debugging**: Independent tests make it easy to identify failures
- **Speed**: Fast tests provide quick feedback during development
- **Confidence**: Reliable tests give trust in refactoring and changes

---

## Test Patterns

### Arrange-Act-Assert (AAA) Pattern

**Structure**:
1. **Arrange**: Set up test data, mocks, and preconditions
2. **Act**: Execute the function/method being tested
3. **Assert**: Verify the expected outcome

**Example**:
```python
def test_agent_permission_denied_for_student():
    """Test that STUDENT agents cannot execute high-complexity actions."""
    # Arrange
    agent = create_agent(maturity="STUDENT", confidence=0.6)
    action = AgentAction(complexity=4, name="delete_database")

    # Act
    result = agent_governance_service.check_permission(agent, action)

    # Assert
    assert result.granted is False
    assert result.reason == "Insufficient maturity for high-complexity action"
    assert result.required_maturity == "AUTONOMOUS"
```

### Given-When-Then (BDD Style)

**Structure**:
1. **Given**: Context and preconditions
2. **When**: Action is performed
3. **Then**: Expected outcome

**Example**:
```python
def test_agent_approval_workflow():
    """Test agent approval workflow for INTERN maturity."""
    # Given: INTERN agent proposes an action
    agent = create_agent(maturity="INTERN")
    action = AgentAction(complexity=2, name="update_record")

    # When: Agent requests approval
    proposal = agent_governance_service.create_proposal(agent, action)

    # Then: Proposal is created and requires approval
    assert proposal.status == "pending_approval"
    assert proposal.proposed_by == agent.id
    assert proposal.requires_approval is True
```

### Factory Pattern for Test Data

**Purpose**: Create consistent, realistic test data without repetition.

**Example**:
```python
# tests/factories/agent_factory.py
from factory import Factory, Faker, SubFactory

class AgentFactory(Factory):
    """Factory for creating Agent test data."""
    class Meta:
        model = Agent

    id = Faker("uuid4")
    name = Faker("name")
    maturity = "AUTONOMOUS"
    confidence = 0.85
    created_at = Faker("date_time_this_decade", tzinfo=timezone.utc)

# Usage in tests
def test_agent_creation():
    agent = AgentFactory(maturity="STUDENT", confidence=0.4)
    assert agent.maturity == "STUDENT"
    assert agent.confidence == 0.4
```

### Fixture Reuse

**Purpose**: Share common setup across tests.

**Example**:
```python
# tests/conftest.py
@pytest.fixture
def db_session():
    """Create a clean database session for each test."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()

@pytest.fixture
def agent_service(db_session):
    """Create AgentGovernanceService with test database."""
    return AgentGovernanceService(db_session)

# Usage in tests
def test_agent_lookup(agent_service):
    agent = agent_service.get_agent("agent_123")
    assert agent is not None
```

---

## Test Naming Conventions

### Unit Test Naming

**Format**: `test_unitOfWork_underWhatConditions_returnsExpectedResult`

**Examples**:
```python
def test_agent_permission_granted_with_autonomous_maturity():
    """Test permission grant for AUTONOMOUS agents."""
    pass

def test_agent_permission_denied_with_student_maturity():
    """Test permission denial for STUDENT agents."""
    pass

def test_agent_confidence_score_rounded_to_two_decimals():
    """Test confidence score rounding behavior."""
    pass

def test_agent_cache_hit_returns_cached_result():
    """Test cache hit scenario."""
    pass
```

### Error Condition Testing

**Format**: `test_errorCondition_throwsException` or `test_errorCondition_returnsError`

**Examples**:
```python
def test_invalid_agent_id_raises_agent_not_found():
    """Test that invalid agent ID raises AgentNotFoundError."""
    with pytest.raises(AgentNotFoundError):
        agent_service.get_agent("invalid_id")

def test_negative_confidence_raises_validation_error():
    """Test that negative confidence scores are rejected."""
    with pytest.raises(ValidationError, match="Confidence must be between 0 and 1"):
        create_agent(confidence=-0.1)
```

### Property Test Naming

**Format**: `test_invariantName_underConditions`

**Examples**:
```python
def test_confidence_always_between_zero_and_one():
    """Test that confidence scores are always normalized to [0, 1]."""
    pass

def test_debits_always_equal_credits_in_double_entry():
    """Test double-entry accounting invariant."""
    pass

def test_cache_hit_rate_improves_with_repeated_queries():
    """Test cache performance invariant."""
    pass
```

### Integration Test Naming

**Format**: `test_featureName_endToEnd_expectedOutcome`

**Examples**:
```python
def test_agent_execution_workflow_end_to_end_success():
    """Test complete agent execution workflow."""
    pass

def test_payment_processing_workflow_end_to_end_failure():
    """Test payment failure handling workflow."""
    pass
```

---

## Quality Metrics

### Assertion Density

**Definition**: Number of assertions per 100 lines of test code.

**Target**: 15+ assertions per 100 lines

**Why**: High assertion density indicates thorough testing without unnecessary code.

**Example**:
```python
# Good: 3 assertions in 8 lines (37.5 assertions per 100 lines)
def test_agent_permission_check():
    agent = create_agent(maturity="AUTONOMOUS")
    result = agent_service.check_permission(agent, "execute")
    assert result.granted is True
    assert result.required_maturity == "AUTONOMOUS"
    assert result.checked_at is not None

# Bad: 1 assertion in 15 lines (6.7 assertions per 100 lines)
def test_agent_permission_check():
    # Lots of unnecessary setup
    agent = create_agent()
    agent.maturity = "AUTONOMOUS"
    agent.confidence = 0.95
    agent.created_at = datetime.now()
    agent.updated_at = datetime.now()
    agent.status = "active"
    agent.permissions = ["read", "write", "execute"]
    agent.metadata = {"source": "test"}
    # ... more setup ...

    result = agent_service.check_permission(agent, "execute")
    assert result.granted is True  # Only one assertion
```

### Test Independence

**Metric**: Tests must pass when run in random order.

**Target**: 100% of tests pass with `--random-order` flag.

**Verification**:
```bash
pytest tests/ --random-order --random-order-seed=12345
```

**Common failure causes**:
- Shared state between tests (database records, cache entries)
- File system dependencies (test files not cleaned up)
- Time dependencies (hardcoded timestamps)
- Global state (environment variables, singletons)

### Pass Rate

**Definition**: Percentage of tests that pass on each run.

**Target**: 98%+ across entire test suite

**Tracking**: Use `check_pass_rate.py` to monitor trends.

**Alert**: If pass rate drops below 98%, CI gate fails.

**Example**:
```bash
# Track pass rate over time
python tests/scripts/check_pass_rate.py --threshold 98
```

### Execution Time

**Target**: <5 minutes for full test suite (excluding slow tests)

**Profiling**:
```bash
# Show slowest 10 tests
pytest tests/ --durations=10

# Mark slow tests
@pytest.mark.slow
def test_integration_with_external_api():
    # This test takes >1s
    pass
```

**Optimization strategies**:
- Mock external API calls
- Use in-memory databases (SQLite instead of PostgreSQL)
- Parallel execution: `pytest -n auto`
- Session-scoped fixtures for expensive setup

---

## Anti-patterns to Avoid

### 1. Testing Implementation Details

**Bad**: Tests break when refactoring code without changing behavior.

```python
# Bad: Testing private method implementation
def test_agent_cache_set_method():
    cache = GovernanceCache()
    cache._set_internal("agent_123", {"maturity": "AUTONOMOUS"})
    assert cache._data["agent_123"] == {"maturity": "AUTONOMOUS"}

# Good: Testing public API behavior
def test_agent_cache_returns_cached_value():
    cache = GovernanceCache()
    cache.set("agent_123", {"maturity": "AUTONOMOUS"})
    result = cache.get("agent_123")
    assert result["maturity"] == "AUTONOMOUS"
```

### 2. Brittle Tests (Over-Specific Assertions)

**Bad**: Tests break due to irrelevant changes (ordering, formatting).

```python
# Bad: Over-specific assertion
def test_agent_list_returns_all_agents():
    agents = agent_service.list_agents()
    assert agents[0].id == "agent_001"
    assert agents[1].id == "agent_002"  # Assumes order
    assert agents[0].created_at.strftime("%Y-%m-%d") == "2026-02-25"  # Brittle

# Good: Flexible assertion
def test_agent_list_returns_all_agents():
    agents = agent_service.list_agents()
    assert len(agents) == 2
    agent_ids = {a.id for a in agents}
    assert agent_ids == {"agent_001", "agent_002"}
    assert all(a.created_at is not None for a in agents)
```

### 3. Shared State Between Tests

**Bad**: Tests depend on execution order or previous test state.

```python
# Bad: Shared global state
global_agent = None

def test_create_agent():
    global global_agent
    global_agent = agent_service.create("test_agent")

def test_delete_agent():
    global global_agent
    agent_service.delete(global_agent.id)  # Depends on previous test

# Good: Independent tests
def test_create_agent():
    agent = agent_service.create("test_agent")
    assert agent.id is not None

def test_delete_agent():
    agent = agent_service.create("temp_agent")
    agent_service.delete(agent.id)
    assert agent_service.get(agent.id) is None
```

### 4. Mocking What You Don't Own

**Bad**: Mocking third-party libraries that you don't control.

```python
# Bad: Mocking third-party library internals
@patch('sqlalchemy.orm.session.Session.commit')
def test_agent_creation_with_mocked_commit(mock_commit):
    agent = agent_service.create("test")
    assert mock_commit.called  # Testing SQLAlchemy, not our code

# Good: Testing our code with real library (or in-memory DB)
def test_agent_creation_persists_to_database():
    agent = agent_service.create("test")
    retrieved = agent_service.get(agent.id)
    assert retrieved.id == agent.id
```

### 5. Test Code Duplication

**Bad**: Same setup code repeated across multiple tests.

```python
# Bad: Duplicated setup
def test_agent_permission_1():
    agent = Agent(
        id="agent_001",
        name="Test Agent",
        maturity="AUTONOMOUS",
        confidence=0.9,
        status="active",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    result = agent_service.check_permission(agent, "execute")
    assert result.granted is True

def test_agent_permission_2():
    agent = Agent(
        id="agent_002",  # Different values, but same structure
        name="Test Agent",
        maturity="AUTONOMOUS",
        confidence=0.9,
        status="active",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )
    result = agent_service.check_permission(agent, "read")
    assert result.granted is True

# Good: Use factory or fixture
def test_agent_permission_1():
    agent = AgentFactory(maturity="AUTONOMOUS")
    result = agent_service.check_permission(agent, "execute")
    assert result.granted is True

def test_agent_permission_2():
    agent = AgentFactory(maturity="AUTONOMOUS")
    result = agent_service.check_permission(agent, "read")
    assert result.granted is True
```

---

## Code Examples

### Good Test vs Bad Test Comparisons

#### Example 1: Testing Error Handling

**Bad Test**:
```python
def test_error_handling():
    try:
        agent_service.get_agent(None)
    except Exception as e:
        assert str(e) == "Invalid agent ID"
```

**Problems**:
- Catches generic `Exception` (too broad)
- Only checks error message (brittle)
- Doesn't verify exception type

**Good Test**:
```python
def test_invalid_agent_id_raises_validation_error():
    """Test that None agent ID raises ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        agent_service.get_agent(None)

    assert "agent_id" in str(exc_info.value).lower()
    assert exc_info.value.field == "agent_id"
```

**Improvements**:
- Specific exception type
- Structured assertion on exception attributes
- Clear test name

#### Example 2: Testing Database Operations

**Bad Test**:
```python
def test_database_operation():
    session = SessionLocal()
    agent = Agent(id="agent_001", maturity="AUTONOMOUS")
    session.add(agent)
    session.commit()
    result = session.query(Agent).filter_by(id="agent_001").first()
    assert result is not None
```

**Problems**:
- No cleanup (pollutes database)
- Tests SQLAlchemy, not our code
- No rollback on failure

**Good Test**:
```python
def test_agent_creation_persists_to_database(db_session):
    """Test that agents are correctly persisted to database."""
    agent = agent_service.create("test_agent", maturity="AUTONOMOUS")

    retrieved = db_session.query(Agent).filter_by(id=agent.id).first()

    assert retrieved is not None
    assert retrieved.id == agent.id
    assert retrieved.maturity == "AUTONOMOUS"
    assert retrieved.created_at is not None
```

**Improvements**:
- Uses `db_session` fixture (auto-cleanup)
- Tests service layer, not database internals
- Multiple assertions for validation

### Fixture Usage Examples

#### Database Fixture

```python
@pytest.fixture
def db_session():
    """Create a clean database session for each test."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
```

#### Mock Service Fixture

```python
@pytest.fixture
def mock_llm_service():
    """Mock LLM service for testing."""
    with patch('core.llm.byok_handler.OpenAIService') as mock:
        mock.return_value.stream_completion.return_value = ["Hello", " World"]
        yield mock
```

#### Test Data Factory

```python
@pytest.fixture
def sample_agent(db_session):
    """Create a sample agent for testing."""
    agent = AgentFactory(maturity="AUTONOMOUS", confidence=0.9)
    db_session.add(agent)
    db_session.commit()
    return agent
```

### Mock Patterns for External Services

#### Mocking API Calls

```python
from unittest.mock import patch, MagicMock

def test_external_api_call_with_mock():
    """Test that our service handles external API responses correctly."""
    with patch('core.services.external_api.Client') as mock_client:
        # Configure mock response
        mock_instance = MagicMock()
        mock_instance.post.return_value.status_code = 200
        mock_instance.post.return_value.json.return_value = {"success": True}
        mock_client.return_value = mock_instance

        # Test our code
        result = our_service.send_data({"key": "value"})

        # Verify interaction
        assert result["success"] is True
        mock_instance.post.assert_called_once_with("https://api.example.com/endpoint", json={"key": "value"})
```

#### Mocking Time-Dependent Code

```python
from freezegun import freeze_time

def test_timestamp_generation():
    """Test that timestamps are generated correctly."""
    with freeze_time("2026-02-25 12:00:00"):
        agent = agent_service.create("test_agent")
        assert agent.created_at == datetime(2026, 2, 25, 12, 0, 0)
```

---

## Related Documentation

- [TEST_COVERAGE_GUIDE.md](TEST_COVERAGE_GUIDE.md) - Coverage measurement and improvement
- [QUALITY_RUNBOOK.md](QUALITY_RUNBOOK.md) - Troubleshooting and debugging
- [backend/README.md](../README.md) - Project overview

---

*Last Updated: 2026-02-25*
*Phase: 090 (Quality Gates & CI/CD)*
*Plan: 06 (Documentation & Maintenance)*
