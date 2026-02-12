# Testing Patterns

**Analysis Date:** 2026-02-10

## Test Framework

**Runner:**
- Framework: pytest 7.4.0+
- Config: `pytest.ini` with comprehensive settings
- Async support: `asyncio_mode = auto`

**Assertion Library:**
- Standard: pytest assertions
- Additional: hypothesis for property-based testing

**Run Commands:**
```bash
# All tests with coverage
pytest tests/ -v --cov=core --cov=api --cov=tools --cov-report=html

# Property-based tests only
pytest tests/property_tests/ -v -m "property"

# Specific test categories
pytest tests/ -m "unit"
pytest tests/ -m "integration"
pytest tests/ -m "invariant"

# Parallel execution
pytest tests/ -n auto

# With coverage thresholds
pytest tests/ --cov-fail-under=80
```

## Test File Organization

**Location:**
- Main tests: `backend/tests/`
- Property tests: `backend/tests/property_tests/`
- Mutation tests: `backend/tests/mutation_tests/`
- Chaos tests: `backend/tests/chaos/`

**Naming:**
- Unit tests: `test_*.py`
- Property tests: `test_*_invariants.py`
- Integration tests: `test_*_integration.py`
- Component tests: `test_*_component.py`

**Structure:**
```
tests/
├── test_browser_automation.py          # Unit tests
├── test_governance_streaming.py        # Unit tests
├── property_tests/
│   ├── database/
│   │   └── test_database_invariants.py  # Property tests
│   ├── api/
│   │   └── test_api_contracts.py       # Property tests
│   └── ...
├── mutation_tests/
│   ├── targets/
│   └── scripts/
└── chaos/
    └── test_chaos.py                   # Chaos engineering
```

## Test Structure

**Suite Organization:**
```python
"""
Unit tests for browser automation with governance integration.

Tests cover:
- Browser session creation and management
- Navigation, screenshot, form filling
- Governance checks for browser actions (INTERN+ required)
- Browser audit trail creation
- Agent execution tracking
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch
import pytest
from sqlalchemy.orm import Session

from core.agent_context_resolver import AgentContextResolver
from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentStatus, User, Workspace
```

**Patterns:**
- Test classes: `TestClassName`
- Test methods: `test_specific_behavior()`
- Setup/teardown: `@pytest.fixture` functions
- Async tests: `@pytest.mark.asyncio`

## Mocking

**Framework:** unittest.mock + pytest-mock
**Patterns:**
```python
@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock(spec=Session)
    return db

@pytest.fixture
def mock_agent_student():
    """Mock student-level agent."""
    agent = Mock(spec=AgentRegistry)
    agent.id = "student-agent-1"
    agent.name = "Student Agent"
    agent.category = "test"
    agent.status = AgentStatus.STUDENT.value
    agent.confidence_score = 0.4
    return agent

# Patching external dependencies
with patch.object(mock_db, 'query') as mock_query:
    mock_filter = Mock()
    mock_query.return_value = mock_filter
    mock_filter.filter.return_value = mock_filter
    mock_filter.first.return_value = mock_agent_student
```

**What to Mock:**
- Database sessions
- External API calls
- File system operations
- Time-dependent functions
- Network requests

**What NOT to Mock:**
- Business logic within the same module
- Core model methods
- Database queries that test data integrity
- Simple utility functions

## Fixtures and Factories

**Test Data:**
```python
@pytest.fixture
def mock_user():
    """Mock user."""
    user = Mock(spec=User)
    user.id = "user-1"
    user.email = "test@example.com"
    return user

# Factory pattern for complex objects
@pytest.fixture
def create_agent(db, status=AgentStatus.STUDENT):
    """Factory for creating agents."""
    def _create_agent(name, category="test"):
        agent = AgentRegistry(
            name=name,
            category=category,
            status=status.value,
            confidence_score=0.5
        )
        db.add(agent)
        db.commit()
        return agent
    return _create_agent
```

**Location:**
- Fixtures: `conftest.py` for shared fixtures
- Test-specific fixtures: In individual test files
- Factory functions: In dedicated modules for complex objects

## Coverage

**Requirements:**
- Target: 80% minimum coverage
- Critical modules: 100% (Financial, Security, Models)
- High priority: >95% (Episodes, Multi-Agent, Tools)
- Metrics: `coverage.json`, HTML reports

**View Coverage:**
```bash
# HTML report
open tests/coverage_reports/html/index.html

# JSON metrics
cat tests/coverage_reports/metrics/coverage.json

# Coverage by module
pytest tests/ --cov=core --cov-report=term-missing
```

## Test Types

**Unit Tests:**
- Scope: Individual functions/classes
- Speed: Fast (< 1 second)
- Dependencies: Mock external services
- Coverage: High for isolated components
- Example: `test_agent_resolution_logic()`

**Integration Tests:**
- Scope: Component interactions
- Speed: Medium (1-10 seconds)
- Dependencies: Real database, partial mocks
- Coverage: API endpoints, service layers
- Example: `test_end_to_end_workflow()`

**Property-Based Tests:**
- Framework: Hypothesis
- Scope: System invariants
- Strategy: Generate random test data
- Coverage: Edge cases, boundary conditions
- Example: `test_transaction_atomicity()`

**E2E Tests:**
- Framework: Not extensively implemented
- Scope: Full user workflows
- Speed: Slow (> 30 seconds)
- Dependencies: Real services, external APIs
- Coverage: Complete user journeys

## Common Patterns

**Async Testing:**
```python
@pytest.mark.asyncio
async def test_browser_session_init(self):
    """Test browser session initialization."""
    session = BrowserSession(
        session_id="test-session",
        user_id="user-1",
        agent_id="agent-1",
        headless=True,
        browser_type="chromium"
    )

    assert session.session_id == "test-session"
    assert session.user_id == "user-1"
    assert session.agent_id == "agent-1"

# Async test with context manager
@pytest.mark.asyncio
async def test_agent_resolution_async(self):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/agents/test")
        assert response.status_code == 200
```

**Error Testing:**
```python
def test_agent_not_found_error(self):
    """Test error handling for missing agent."""
    with pytest.raises(HTTPException) as exc_info:
        get_agent("non-existent-id", mock_db)

    assert exc_info.value.status_code == 404
    assert "not found" in exc_info.value.detail

# Test specific error codes
def test_validation_error(self):
    """Test validation error handling."""
    with pytest.raises(ValidationError) as exc_info:
        validate_agent_data({})

    assert "missing required field" in str(exc_info.value)
```

**Property-Based Testing:**
```python
from hypothesis import given, strategies as st, settings

@given(
    initial_balance=st.integers(min_value=0, max_value=1000000),
    debit_amount=st.integers(min_value=1, max_value=1000),
    credit_amount=st.integers(min_value=1, max_value=1000)
)
@settings(max_examples=50)
def test_transaction_atomicity(self, initial_balance, debit_amount, credit_amount):
    """INVARIANT: Transactions should be atomic."""
    # Simulate transaction
    try:
        balance = initial_balance
        balance -= debit_amount
        if balance < 0:
            # Rollback
            balance = initial_balance
        else:
            balance += credit_amount

        # Invariant: Balance should never be negative after rollback
        assert balance >= 0, "Transaction atomicity preserved"
    except Exception:
        # Transaction aborted - state unchanged
        assert True
```

## Test Categories

**Governance Tests:**
- Markers: `@pytest.mark.governance`, `@pytest.mark.student/intern/supervised/autonomous`
- Coverage: Agent maturity levels, permission checks
- Example: `test_agent_can_perform_action()`

**API Tests:**
- Markers: `@pytest.mark.api`
- Coverage: Endpoint validation, request/response formats
- Example: `test_submit_form_endpoint()`

**Database Tests:**
- Markers: `@pytest.mark.database`
- Coverage: Model relationships, transactions, queries
- Example: `test_agent_persistence()`

**Integration Tests:**
- Markers: `@pytest.mark.integration`
- Coverage: Cross-module interactions
- Example: `test_canvas_governance_integration()`

## Test Configuration

**Markers:**
```ini
# pytest.ini markers
markers =
    # Test Type Markers
    unit: Unit tests (fast, isolated)
    integration: Integration tests (slower, requires dependencies)
    property: Property-based tests using Hypothesis
    invariant: Invariant tests (critical system invariants)
    slow: Slow tests (> 1 second)

    # Domain Markers
    financial: Financial operations tests
    security: Security validation tests
    api: API contract tests
    database: Database model tests
    governance: Agent governance tests

    # Priority Markers
    P0: Critical priority (security, financial)
    P1: High priority (core business logic)
    P2: Medium priority (API, tools)
    P3: Low priority (nice-to-have)
```

**Coverage Configuration:**
```ini
# .coveragerc
[run]
source =
    core
    api
    tools
    integrations

[report]
fail_under = 80.0
show_missing = True
skip_empty = True

[html]
directory = tests/coverage_reports/html
```

---

*Testing analysis: 2026-02-10*