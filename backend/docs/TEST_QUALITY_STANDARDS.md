# Test Quality Standards

**Version:** 1.0
**Last Updated:** 2026-02-20
**Applies To:** All test code in the Atom backend codebase

---

## Table of Contents

1. [TQ-01: Test Independence](#tq-01-test-independence)
2. [TQ-02: Pass Rate](#tq-02-pass-rate)
3. [TQ-03: Performance](#tq-03-performance)
4. [TQ-04: Determinism](#tq-04-determinism)
5. [TQ-05: Coverage Quality](#tq-05-coverage-quality)
6. [Test Writing Templates](#test-writing-templates)
7. [Common Test Patterns](#common-test-patterns)
8. [Mock Usage Guidelines](#mock-usage-guidelines)
9. [CI/CD Integration Examples](#cicd-integration-examples)
10. [Troubleshooting Guide](#troubleshooting-guide)

---

## TQ-01: Test Independence

### Definition

Tests must be completely independent of each other. No test should depend on:
- The execution order of other tests
- Shared state modified by other tests
- Data created by other tests
- External state (database, files, cache) unless properly isolated

### Requirements

**1. No Shared State**
```python
# BAD: Shared class variable
class TestAgent:
    agent_id = None  # Shared across all tests!

    def test_create_agent(self):
        self.agent_id = create_agent()

    def test_delete_agent(self):
        delete_agent(self.agent_id)  # Fails if run alone

# GOOD: Each test creates its own data
def test_create_agent(db_session):
    agent = create_agent(db_session)
    assert agent.id is not None

def test_delete_agent(db_session):
    agent = create_agent(db_session)  # Fresh data
    delete_agent(agent.id)
    assert not agent_exists(agent.id)
```

**2. Tests Must Pass in Random Order**
```bash
# Verify with pytest-random-order
pytest tests/ --random-order -v
```

**3. Each Test Creates and Cleans Up Its Own Data**
```python
# GOOD: Using fixtures for automatic cleanup
def test_workflow_execution(db_session):
    workflow = create_test_workflow(db_session)
    execution = execute_workflow(workflow.id)
    assert execution.status == "completed"
    # db_session fixture automatically cleans up
```

**4. Use Fixtures for Setup/Teardown**
```python
# GOOD: Fixture-based setup
@pytest.fixture
def sample_workflow(db_session):
    workflow = WorkflowDefinition(name="Test", status="active")
    db_session.add(workflow)
    db_session.commit()
    yield workflow
    # Cleanup happens automatically

def test_workflow(sample_workflow):
    assert sample_workflow.status == "active"
```

### Examples and Anti-Patterns

**Anti-Pattern 1: Test Order Dependency**
```python
# BAD: Tests fail if run in reverse order
def test_1_create_user():
    global user_id
    user_id = create_user()

def test_2_delete_user():
    delete_user(user_id)  # Fails if test_2 runs first
```

**Correct:**
```python
# GOOD: Each test is self-contained
def test_create_user(db_session):
    user = create_user(db_session)
    assert user.id is not None

def test_delete_user(db_session):
    user = create_user(db_session)  # Independent
    delete_user(user.id)
    assert not user_exists(user.id)
```

**Anti-Pattern 2: Shared Database State**
```python
# BAD: Tests share database records
@pytest.fixture(scope="module")
def db_data():
    # Creates data once, shared across all tests
    agent = AgentRegistry(name="Shared")
    db.add(agent)
    db.commit()
    return agent

def test_1_modify_agent(db_data):
    db_data.name = "Modified"  # Affects other tests

def test_2_read_agent(db_data):
    assert db_data.name == "Shared"  # FAILS!
```

**Correct:**
```python
# GOOD: Function-scoped fixtures
@pytest.fixture(scope="function")
def test_agent(db_session):
    agent = AgentRegistry(name="Test")
    db_session.add(agent)
    db_session.commit()
    yield agent
    # Fresh agent for each test
```

### Verification

```bash
# Run tests in random order 3 times
for i in {1..3}; do
    pytest tests/ --random-order -v
done

# All runs should pass with same results
```

---

## TQ-02: Pass Rate

### Definition

The test suite must maintain a 98%+ pass rate across 3 consecutive runs. Flaky tests (tests that intermittently fail) are not acceptable in CI/CD.

### Requirements

**1. 98%+ Pass Rate Across 3 Consecutive Runs**
```bash
# Run tests 3 times and verify pass rate
for i in {1..3}; do
    pytest tests/ -q --tb=no | tee run_$i.log
done

# Calculate pass rate (example: 970/1000 = 97%)
# Must be >= 98%
```

**2. No Tolerated Failures in CI/CD**
- All CI/CD pipelines must pass for merge approval
- Flaky tests must be fixed or disabled before merging
- No "known failures" or "expected failures" in main branch

**3. Retry Logic for Transient Failures**
```python
# Use pytest-rerun for transient network failures
# Only for genuinely transient failures (network, timing)
# NOT for hiding flaky tests!

# pytest.ini
[pytest]
addopts = --reruns 2 --reruns-delay 1

# Or command line:
pytest tests/ --reruns 2
```

**4. Pass Rate Monitoring and Alerts**
```yaml
# .github/workflows/ci.yml
- name: Check pass rate
  run: |
    python <<EOF
    import sys
    # Parse pytest output for pass rate
    # Alert if pass rate < 98%
    EOF
```

### Handling Flaky Tests

**Step 1: Identify Flaky Tests**
```bash
# Run tests multiple times to find flakes
pytest tests/ --repeat=10 -v

# Check for intermittent failures
pytest tests/ -x --random-order --reruns 0
```

**Step 2: Fix Root Causes**
- Race conditions → Add proper synchronization
- Timing dependencies → Use polling loops instead of sleep
- Shared state → Use isolated fixtures
- External dependencies → Mock or use fixtures

**Step 3: Verify Fix**
```bash
# Run fixed test 20 times
pytest tests/test_specific.py --count=20 -v
```

### Examples

**Flaky Test:**
```python
# BAD: Timing-dependent test
def test_agent_response():
    agent = Agent()
    agent.execute()
    time.sleep(1)  # Race condition!
    assert agent.is_complete
```

**Fixed:**
```python
# GOOD: Polling with timeout
def test_agent_response():
    agent = Agent()
    agent.execute()
    wait_until(lambda: agent.is_complete, timeout=5)
    assert agent.is_complete
```

### Monitoring

Track pass rate trends in CI/CD:
```yaml
# Track pass rate over time
- name: Report pass rate
  run: |
    pytest tests/ --junitxml=report.xml
    python scripts/parse_pass_rate.py report.json
```

---

## TQ-03: Performance

### Definition

The test suite must complete within specified time limits to ensure fast feedback during development.

### Requirements

**1. Full Suite < 60 Minutes**
```bash
# Verify full suite time
time pytest tests/ -v

# Must complete in < 3600 seconds (60 minutes)
```

**2. No Single Test > 30 Seconds**
```bash
# Find slow tests
pytest tests/ --durations=10

# Output shows 10 slowest tests
# None should exceed 30 seconds
```

**3. Performance by Test Type**
- **Unit tests:** < 1 second per test
- **Integration tests:** < 5 seconds per test
- **E2E tests:** < 30 seconds per test

**4. Performance Profiling**
```bash
# Profile test execution
pytest tests/ --profile

# Generate profile report
pytest tests/ --profile-svg
```

### Optimization Strategies

**1. Use Function Scope for Fast Tests**
```python
# GOOD: Function scope (default)
@pytest.fixture(scope="function")
def db_session():
    # Fresh database for each test
    # Fast setup/teardown
```

**2. Use Session Scope for Expensive Resources**
```python
# GOOD: Session scope for expensive resources
@pytest.fixture(scope="session")
def docker_container():
    # Start container once per session
    container = start_docker()
    yield container
    container.stop()

# All tests reuse the same container
```

**3. Parallel Execution**
```bash
# Use pytest-xdist for parallel tests
pytest tests/ -n auto  # Use all CPUs

# Monitor speedup
pytest tests/ -n 4 --durations=10
```

**4. Optimize Database Operations**
```python
# BAD: Slow database operations
def test_bulk_insert(db_session):
    for i in range(1000):
        db_session.add(Model(value=i))
        db_session.commit()  # 1000 commits!

# GOOD: Bulk operations
def test_bulk_insert(db_session):
    db_session.bulk_insert_mappings(Model, [
        {"value": i} for i in range(1000)
    ])
    db_session.commit()  # Single commit
```

### Performance Benchmarks

| Test Category | Target | Acceptable | Critical |
|--------------|--------|-----------|----------|
| Unit test | < 1s | < 2s | > 5s |
| Integration test | < 5s | < 10s | > 20s |
| E2E test | < 30s | < 45s | > 60s |
| Full suite | < 30m | < 60m | > 90m |

### Monitoring

Track test execution time trends:
```bash
# Generate baseline
pytest tests/ --durations=0 > baseline.txt

# Compare against baseline
pytest tests/ --durations=0 > current.txt
diff baseline.txt current.txt
```

---

## TQ-04: Determinism

### Definition

Tests must be deterministic - same code with same inputs must produce same results every time.

### Requirements

**1. No sleep() Calls (Use Polling)**
```python
# BAD: Arbitrary sleep
def test_async_operation():
    agent.execute_async()
    time.sleep(5)  # Wastes time, flaky
    assert agent.is_complete

# GOOD: Polling loop
def test_async_operation():
    agent.execute_async()
    wait_until(lambda: agent.is_complete, timeout=10)
    assert agent.is_complete
```

**2. No Dependency on Wall-Clock Time**
```python
# BAD: Depends on current time
def test_deadline():
    deadline = datetime.now() + timedelta(days=1)
    assert deadline.day == (datetime.now().day + 1)  # Fails at midnight!

# GOOD: Frozen time
def test_deadline(frozen_time):
    deadline = datetime.now() + timedelta(days=1)
    assert deadline.day == 2  # Always true
```

**3. Use frozen_time Fixture for Time-Dependent Tests**
```python
def test_episode_creation(frozen_time):
    episode = create_episode()
    assert episode.created_at == datetime(2024, 1, 1, 0, 0, 0)
```

**4. No Random Data Without Fixed Seed**
```python
# BAD: Random data
def test_random_agent():
    agent = create_agent(name=random_name())  # Different every run

# GOOD: Fixed seed or deterministic data
def test_random_agent():
    random.seed(42)
    agent = create_agent(name=random_name())  # Same every run
```

**5. Async Test Patterns**
```python
# GOOD: Use pytest-asyncio for async tests
@pytest.mark.asyncio
async def test_async_agent():
    agent = AsyncAgent()
    result = await agent.execute()
    assert result.success

# GOOD: Event loop fixtures
@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
```

### Examples

**Non-Deterministic Test:**
```python
# BAD: Depends on timing
def test_workflow_timeout():
    workflow = create_workflow(timeout=1)
    workflow.execute()
    time.sleep(2)  # Assumes execution takes < 2s
    assert workflow.timed_out
```

**Deterministic Version:**
```python
# GOOD: Mock time
def test_workflow_timeout(mock_time):
    workflow = create_workflow(timeout=1)
    workflow.execute()
    mock_time.advance(seconds=2)
    assert workflow.timed_out
```

### Verification

```bash
# Run tests with randomization
pytest tests/ --random-order --repeat=3 -v

# All runs should produce identical results
diff run1.log run2.log  # Should be identical
```

---

## TQ-05: Coverage Quality

### Definition

Coverage is a means to an end (testing behavior), not an end in itself. Focus on behavior-based testing, not line coverage chasing.

### Requirements

**1. Behavior-Based Testing (Not Line Coverage Chasing)**
```python
# BAD: Test implementation details
def test_agent_internal_state():
    agent = Agent()
    agent.execute()
    assert agent._internal_counter == 5  # Tests private state

# GOOD: Test observable behavior
def test_agent_execution_result():
    agent = Agent()
    result = agent.execute()
    assert result.status == "completed"
    assert result.output is not None
```

**2. Property-Based Tests for Stateful Logic**
```python
from hypothesis import given, strategies as st

# GOOD: Property-based invariant
@given(st.lists(st.integers(), min_size=0, max_size=100))
def test_workflow_roundtrip(steps):
    """Workflow serialization is lossless."""
    workflow = Workflow(steps=steps)
    serialized = workflow.serialize()
    deserialized = Workflow.deserialize(serialized)
    assert deserialized.steps == steps
```

**3. Edge Case and Error Path Testing**
```python
# GOOD: Test error cases
def test_workflow_execution_failure():
    workflow = create_workflow(invalid_step=True)
    with pytest.raises(WorkflowError):
        workflow.execute()

# GOOD: Test edge cases
@pytest.mark.parametrize("input", ["", None, [], {}])
def test_agent_with_empty_input(input):
    agent = Agent()
    result = agent.execute(input)
    assert result.status == "error"
```

**4. Minimum Coverage Thresholds Per File Type**
| File Type | Minimum Coverage | Recommended |
|-----------|------------------|-------------|
| Core logic (workflow_engine.py) | 70% | 85% |
| API endpoints | 60% | 80% |
| Services (LLM, episodic memory) | 65% | 80% |
| Utilities | 50% | 70% |
| Models | 40% | 60% |

**5. Coverage Exemptions Process**
```python
# Add exemption comment for untestable code
def production_only_function():
    # coverage: ignore - production-only code
    # Reason: Requires real AWS credentials
    # Ticket: https://github.com/atom/atom/issues/123
    pass
```

### Measuring Coverage Quality

**1. Assertion Density**
```bash
# Use pytest-assume to check assertion density
pytest tests/ --assertion-density

# Target: 15+ assertions per 100 lines of test code
```

**2. Mutation Testing (Advanced)**
```bash
# Use mutmut to test test quality
pip install mutmut
mutmut run --paths-to-mutate core/workflow_engine.py

# High mutation score = good tests
```

**3. Branch Coverage**
```bash
# Track branch coverage (not just line coverage)
pytest tests/ --cov=core --cov-branch --cov-report=term-missing

# Aim for high branch coverage on critical paths
```

### Examples

**Low-Quality Coverage:**
```python
# BAD: Tests implementation, not behavior
def test_agent_set_name():
    agent = Agent()
    agent.set_name("Test")  # Implementation detail
    assert agent._name == "Test"  # Tests private field
```

**High-Q Coverage:**
```python
# GOOD: Tests behavior
def test_agent_name_persistence(db_session):
    agent = create_agent(db_session, name="Test")
    db_session.commit()

    # Retrieve from database
    retrieved = db_session.query(AgentRegistry).filter_by(id=agent.id).first()
    assert retrieved.name == "Test"  # Behavior: name persists
```

### Coverage Report Analysis

```bash
# Generate detailed coverage report
pytest tests/ --cov=core --cov-report=html

# Open in browser
open htmlcov/index.html

# Look for:
# - Red files (low coverage)
# - Missing branches (yellow arrows)
# - Complex functions with low coverage
```

---

## Test Writing Templates

### Unit Test Template

```python
"""
Tests for workflow_engine.py
"""

import pytest
from core.workflow_engine import WorkflowEngine
from tests.fixtures.workflow_fixtures import create_test_workflow

class TestWorkflowEngine:
    """Test WorkflowEngine unit tests."""

    def test_workflow_execution_success(self, db_session):
        """Test successful workflow execution."""
        # Arrange
        workflow = create_test_workflow(db_session, name="TestWorkflow")
        engine = WorkflowEngine(db_session)

        # Act
        result = engine.execute(workflow.id)

        # Assert
        assert result.status == "completed"
        assert result.completed_at is not None

    @pytest.mark.parametrize("status", ["pending", "running", "failed"])
    def test_workflow_status_transitions(self, db_session, status):
        """Test workflow status transitions."""
        workflow = create_test_workflow(db_session, status=status)
        engine = WorkflowEngine(db_session)

        result = engine.execute(workflow.id)

        assert result.status in ["completed", "failed"]
```

### Integration Test Template

```python
"""
Tests for agent API endpoints
"""

import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

class TestAgentEndpoints:
    """Test agent API integration."""

    def test_agent_chat_endpoint(self, test_agent):
        """Test agent chat returns response."""
        response = client.post(
            f"/api/agents/{test_agent.id}/chat",
            json={"message": "Hello"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "response" in data
        assert data["agent_id"] == test_agent.id

    def test_agent_chat_invalid_id(self):
        """Test agent chat with invalid agent ID."""
        response = client.post(
            "/api/agents/invalid_id/chat",
            json={"message": "Hello"}
        )

        assert response.status_code == 404
```

### Property-Based Test Template

```python
"""
Property-based tests for episode segmentation
"""

from hypothesis import given, strategies as st
from core.episode_segmentation_service import EpisodeSegmentationService

class TestEpisodeSegmentationProperties:
    """Test episode segmentation invariants."""

    @given(st.lists(st.text(), min_size=1, max_size=100))
    def test_episode_segments_are_contiguous(self, messages):
        """Episode segments should be temporally contiguous."""
        service = EpisodeSegmentationService()
        segments = service.segment(messages)

        # Check no gaps in segment timestamps
        for i in range(len(segments) - 1):
            assert segments[i].end_time <= segments[i+1].start_time

    @given(st.lists(st.text(), min_size=0))
    def test_empty_input_produces_no_segments(self, messages):
        """Empty message list produces no segments."""
        service = EpisodeSegmentationService()
        segments = service.segment(messages)

        assert len(segments) == 0
```

---

## Common Test Patterns

### Database Testing

```python
def test_database_transaction_rollback(db_session):
    """Test transaction rollback on error."""
    agent = AgentRegistry(name="Test")
    db_session.add(agent)
    db_session.commit()

    # Simulate error
    try:
        db_session.delete(agent)
        db_session.commit()
    except Exception:
        db_session.rollback()

    # Verify rollback
    retrieved = db_session.query(AgentRegistry).filter_by(id=agent.id).first()
    assert retrieved is not None  # Still exists
```

### Async Testing

```python
@pytest.mark.asyncio
async def test_async_agent_execution():
    """Test async agent execution."""
    agent = AsyncAgent()
    result = await agent.execute_async()

    assert result.success
    assert await agent.is_complete()
```

### Mock Testing

```python
def test_llm_provider_fallback(mock_llm_response):
    """Test LLM provider fallback on error."""
    mock_llm_response.set_error_mode("timeout")

    with pytest.raises(TimeoutError):
        agent.execute_with_llm()
```

### Parametrized Testing

```python
@pytest.mark.parametrize("maturity,expected_access", [
    ("STUDENT", False),
    ("INTERN", True),
    ("SUPERVISED", True),
    ("AUTONOMOUS", True),
])
def test_agent_trigger_access(maturity, expected_access):
    """Test agent trigger access by maturity level."""
    agent = create_agent(maturity=maturity)
    assert agent.can_execute_triggers() == expected_access
```

---

## Mock Usage Guidelines

### When to Mock

**DO Mock:**
- External services (LLM providers, APIs)
- File system operations (use temp directories)
- Time/dates (use frozen_time fixture)
- Random data (use fixed seeds)

**DON'T Mock:**
- Database (use test database fixture)
- Core business logic (test actual behavior)
- Simple functions (test them directly)

### Mock Examples

```python
# GOOD: Mock external LLM API
def test_agent_with_mocked_llm(mock_llm_response):
    mock_llm_response.set_response("test", "Mocked response")

    agent = Agent()
    response = agent.chat("test")

    assert response == "Mocked response"
```

```python
# BAD: Mocking database (use fixture instead)
def test_with_mocked_db():
    mock_db = MagicMock()  # Don't do this
    agent = Agent(db=mock_db)
```

```python
# GOOD: Use test database fixture
def test_with_test_db(db_session):
    agent = Agent(db=db_session)  # Real database, test data
    agent.save()
    assert agent.id is not None
```

---

## CI/CD Integration Examples

### GitHub Actions

```yaml
name: Test Quality Gates

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Run tests with coverage
        run: |
          pytest tests/ \
            --cov=core \
            --cov=api \
            --cov-report=xml \
            --cov-report=html \
            --cov-fail-under=50

      - name: Check test independence
        run: pytest tests/ --random-order -v

      - name: Check test performance
        run: pytest tests/ --durations=10

      - name: Upload coverage reports
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
```

### Quality Gate Enforcement

```yaml
- name: Enforce TQ-01 (Independence)
  run: pytest tests/ --random-order --reruns 0

- name: Enforce TQ-02 (Pass Rate)
  run: |
    pytest tests/ -q --tb=no
    # Parse output for pass rate
    # Fail if < 98%

- name: Enforce TQ-03 (Performance)
  run: |
    pytest tests/ --durations=0
    # Fail if any test > 30s

- name: Enforce TQ-04 (Determinism)
  run: pytest tests/ --random-order --repeat=3

- name: Enforce TQ-05 (Coverage)
  run: pytest tests/ --cov=core --cov-fail-under=50
```

---

## Troubleshooting Guide

### Tests Pass Locally but Fail in CI

**Possible Causes:**
1. Timezone differences
2. Environment variable differences
3. Race conditions (CI is slower)
4. Missing dependencies

**Solutions:**
```python
# Use UTC for all timestamps
datetime.utcnow()  # GOOD
datetime.now()     # BAD

# Use environment isolation
@pytest.fixture(autouse=True)
def isolate_env():
    # Save/restore env vars

# Use polling instead of sleep
wait_until(condition, timeout=10)  # GOOD
time.sleep(5)  # BAD
```

### Flaky Tests

**Symptoms:** Test passes sometimes, fails other times

**Debug Steps:**
```bash
# Run test 100 times to identify flakiness
pytest tests/test_specific.py --count=100

# Check for shared state
pytest tests/test_specific.py --random-order

# Check for timing issues
pytest tests/test_specific.py -vv --tb=long
```

### Slow Tests

**Identify Slow Tests:**
```bash
pytest tests/ --durations=20
```

**Optimization Strategies:**
1. Use session-scoped fixtures for expensive resources
2. Parallelize independent tests with pytest-xdist
3. Use bulk database operations
4. Mock slow external services

### Coverage Not Increasing

**Problem:** Adding tests but coverage stays same

**Diagnosis:**
```bash
# Check which lines are covered
pytest tests/ --cov=core --cov-report=term-missing

# Generate HTML report for visual inspection
pytest tests/ --cov=core --cov-report=html
open htmlcov/index.html
```

**Solutions:**
1. Verify tests are actually calling target code
2. Check for conditional branches not tested
3. Add edge case tests
4. Review test assertions (may be passing without executing code)

---

## Appendix A: Quick Reference

### pytest Commands

```bash
# Run all tests
pytest tests/

# Run specific file
pytest tests/test_workflow_engine.py

# Run with coverage
pytest tests/ --cov=core

# Run in parallel
pytest tests/ -n auto

# Run with verbose output
pytest tests/ -v

# Run and stop on first failure
pytest tests/ -x

# Run matching pattern
pytest tests/ -k "workflow"

# Run with debugger
pytest tests/ --pdb

# Show slowest tests
pytest tests/ --durations=10

# Run tests in random order
pytest tests/ --random-order

# Run tests multiple times
pytest tests/ --repeat=3
```

### Fixture Scopes

| Scope | Description | Use Case |
|-------|-------------|----------|
| function | Fresh fixture for each test | Most fixtures (default) |
| class | Shared across test class methods | Expensive setup per class |
| module | Shared across module | Database session per module |
| session | Shared across all tests | Docker containers, external services |

### Common pytest.mark Options

```python
@pytest.mark.skip(reason="Not implemented yet")
def test_not_ready():
    pass

@pytest.mark.skipif(condition, reason="Skip on Windows")
def test_unix_only():
    pass

@pytest.mark.xfail(reason="Known bug #123")
def test_known_failure():
    pass

@pytest.mark.slow
def test_slow_operation():
    time.sleep(10)

@pytest.mark.asyncio
async def test_async():
    await async_operation()
```

---

## Appendix B: Test Quality Checklist

Before submitting a PR, verify:

- [ ] All tests pass locally
- [ ] Tests pass in random order (`pytest --random-order`)
- [ ] No test exceeds 30 seconds
- [ ] Coverage increased or maintained
- [ ] New tests follow TQ-01 through TQ-05
- [ ] No `sleep()` calls (use polling)
- [ ] No shared state between tests
- [ ] All fixtures properly scoped
- [ ] Async tests use `@pytest.mark.asyncio`
- [ ] External dependencies are mocked
- [ ] Tests have descriptive names
- [ ] Tests have docstrings explaining what/why

---

**Document Version:** 1.0
**Last Updated:** 2026-02-20
**Next Review:** 2026-03-20
