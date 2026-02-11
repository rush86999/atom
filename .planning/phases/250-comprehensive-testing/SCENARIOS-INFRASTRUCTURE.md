# Atom Platform - Test Infrastructure Guide

**Phase:** 250-Comprehensive-Testing
**Plan:** 02 - Test Infrastructure Documentation
**Document Version:** 1.0
**Last Updated:** 2025-02-11

---

## Executive Summary

This document provides comprehensive documentation of the Atom platform's test infrastructure, including test data factories, helper utilities, environment configuration, and coverage tracking. This infrastructure supports the 250+ test scenarios documented in SCENARIOS.md.

---

## Table of Contents

1. [Test Data Factories](#test-data-factories)
2. [Test Helper Utilities](#test-helper-utilities)
3. [Test Environment Configuration](#test-environment-configuration)
4. [Coverage Tracking Setup](#coverage-tracking-setup)
5. [Platform-Specific Testing](#platform-specific-testing)
6. [Best Practices](#best-practices)

---

## Test Data Factories

Test factories use the [Factory Boy](https://factoryboy.readthedocs.io/) library to generate realistic, isolated test data. All factories inherit from `BaseFactory` which manages SQLAlchemy sessions.

### Base Factory Pattern

**Location:** `backend/tests/factories/base.py`

```python
class BaseFactory(SQLAlchemyModelFactory):
    """Base factory for all test data factories."""

    class Meta:
        abstract = True
        sqlalchemy_session = None  # Set dynamically
        sqlalchemy_session_persistence = "commit"

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override to handle session injection."""
        session = kwargs.pop('_session', None)
        if session:
            cls._meta.sqlalchemy_session = session
        else:
            if cls._meta.sqlalchemy_session is None:
                cls._meta.sqlalchemy_session = get_session()
        return super()._create(model_class, *args, **kwargs)
```

### Available Factories

#### Agent Factory
**Location:** `backend/tests/factories/agent_factory.py`

| Factory | Purpose | Key Attributes |
|----------|---------|----------------|
| `AgentFactory` | Generic agent | Random maturity, confidence 0.0-1.0 |
| `StudentAgentFactory` | STUDENT maturity | confidence < 0.5 |
| `InternAgentFactory` | INTERN maturity | confidence 0.5-0.7 |
| `SupervisedAgentFactory` | SUPERVISED maturity | confidence 0.7-0.9 |
| `AutonomousAgentFactory` | AUTONOMOUS maturity | confidence > 0.9 |

**Usage Examples:**

```python
from tests.factories import AgentFactory, StudentAgentFactory

# Create a single agent
agent = AgentFactory(
    name="TestAgent",
    category="testing",
    capabilities=["test_capability"]
)

# Create multiple agents
agents = AgentFactory.create_batch(10)

# Create agent with specific maturity
student = StudentAgentFactory(confidence_score=0.3)

# Use with test session
agent = AgentFactory(_session=db_session)
```

#### User Factory
**Location:** `backend/tests/factories/user_factory.py`

| Factory | Purpose | Role |
|----------|---------|------|
| `UserFactory` | Generic user | Random role/status |
| `AdminUserFactory` | Admin user | SUPER_ADMIN |
| `MemberUserFactory` | Regular member | MEMBER, ACTIVE |

**Usage Examples:**

```python
from tests.factories import UserFactory, AdminUserFactory

# Create test user
user = UserFactory(
    email="test@example.com",
    first_name="Test",
    last_name="User"
)

# Create admin user
admin = AdminUserFactory(email="admin@example.com")
```

#### Episode Factory
**Location:** `backend/tests/factories/episode_factory.py`

| Factory | Purpose |
|----------|---------|
| `EpisodeFactory` | Episode records |
| `EpisodeSegmentFactory` | Episode segments |

**Usage Examples:**

```python
from tests.factories import EpisodeFactory, EpisodeSegmentFactory

# Create episode with canvas and feedback linkage
episode = EpisodeFactory(
    agent_id="agent-123",
    maturity_at_time="STUDENT",
    canvas_ids=["canvas-1", "canvas-2"],
    feedback_ids=["feedback-1"]
)

# Create segment
segment = EpisodeSegmentFactory(
    episode_id=episode.id,
    segment_type="conversation",
    sequence_order=0
)
```

#### Execution Factory
**Location:** `backend/tests/factories/execution_factory.py`

| Factory | Purpose |
|----------|---------|
| `AgentExecutionFactory` | Agent execution records |

**Usage Examples:**

```python
from tests.factories import AgentExecutionFactory

# Create completed execution
execution = AgentExecutionFactory(
    agent_id="agent-123",
    status="completed",
    triggered_by="manual"
)

# Create failed execution
failed = AgentExecutionFactory(
    status="failed",
    error_message="Connection timeout"
)
```

#### Canvas Factory
**Location:** `backend/tests/factories/canvas_factory.py`

| Factory | Purpose |
|----------|---------|
| `CanvasAuditFactory` | Canvas audit records |

**Usage Examples:**

```python
from tests.factories import CanvasAuditFactory

# Create canvas audit
audit = CanvasAuditFactory(
    agent_id="agent-123",
    canvas_type="sheets",
    component_type="chart",
    action="present"
)
```

#### Chat Session Factory
**Location:** `backend/tests/factories/chat_session_factory.py`

| Factory | Purpose |
|----------|---------|
| `ChatSessionFactory` | Chat session records |

### Factory Patterns

#### Dynamic Values with Faker

```python
class AgentFactory(BaseFactory):
    id = factory.Faker('uuid4')
    name = factory.Faker('company')
    email = factory.Faker('email')
    created_at = factory.Faker('date_time_this_year')
```

#### Fuzzy Choices

```python
from factory import fuzzy

class AgentFactory(BaseFactory):
    status = fuzzy.FuzzyChoice([s.value for s in AgentStatus])
    confidence_score = fuzzy.FuzzyFloat(0.0, 1.0)
```

#### Lazy Attributes

```python
class AgentExecutionFactory(BaseFactory):
    started_at = factory.Faker('date_time_this_year')
    completed_at = factory.LazyAttribute(
        lambda o: o.started_at + timedelta(hours=1)
        if o.status == 'completed' else None
    )
```

#### Batch Creation

```python
# Create 10 agents
agents = AgentFactory.create_batch(10)

# Create 50 episodes
episodes = EpisodeFactory.create_batch(50)
```

---

## Test Helper Utilities

### Pytest Fixtures

#### Root Conftest
**Location:** `backend/tests/conftest.py`

Provides global test configuration and quality metrics.

**Key Fixtures:**

```python
@pytest.fixture(scope="function")
def unique_resource_name():
    """Generate unique resource name for parallel test execution."""
    worker_id = os.environ.get('PYTEST_XDIST_WORKER_ID', 'master')
    unique_id = str(uuid.uuid4())[:8]
    return f"test_{worker_id}_{unique_id}"
```

**Quality Gates:**

- Assertion density check (0.15 assertions per line threshold)
- Coverage summary display
- Numpy/pandas/lancedb/pyarrow module restoration

#### Property Tests Conftest
**Location:** `backend/tests/property_tests/conftest.py`

Provides in-memory database and test agents for Hypothesis property tests.

**Key Fixtures:**

```python
@pytest.fixture(scope="function")
def db_session():
    """Create a fresh in-memory database for each test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    engine.dispose()

@pytest.fixture(scope="function")
def test_agent(db_session: Session):
    """Create a test agent with default settings."""
    agent = AgentRegistry(
        name="TestAgent",
        category="test",
        status=AgentStatus.STUDENT.value,
        confidence=0.5
    )
    db_session.add(agent)
    db_session.commit()
    return agent

@pytest.fixture(scope="function")
def test_agents(db_session: Session):
    """Create multiple test agents with different maturity levels."""
    agents = []
    for status in AgentStatus:
        agent = AgentRegistry(status=status.value, ...)
        db_session.add(agent)
        agents.append(agent)
    return agents
```

#### Integration Tests Conftest
**Location:** `backend/tests/integration/conftest.py`

Provides FastAPI TestClient with dependency overrides and authentication.

**Key Fixtures:**

```python
@pytest.fixture(scope="function")
def client(db_session: Session):
    """Create TestClient with dependency override for test database."""
    def _get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()

@pytest.fixture(scope="function")
def auth_token(db_session: Session):
    """Create valid JWT token for test user."""
    user = UserFactory(email="integration@test.com")
    db_session.add(user)
    db_session.commit()
    token = create_access_token(data={"sub": user.id})
    return token

@pytest.fixture(scope="function")
def admin_token(db_session: Session):
    """Create JWT token for admin user."""
    admin = AdminUserFactory(email="admin@test.com")
    db_session.add(admin)
    db_session.commit()
    token = create_access_token(data={"sub": admin.id})
    return token

@pytest.fixture(scope="function")
def auth_headers(auth_token: str):
    """Create authentication headers for API requests."""
    return {"Authorization": f"Bearer {auth_token}"}

@pytest.fixture(scope="function")
def admin_headers(admin_token: str):
    """Create admin authentication headers."""
    return {"Authorization": f"Bearer {admin_token}"}
```

### Chaos Engineering Helpers

**Location:** `backend/tests/chaos/chaos_helpers.py`

Provides failure simulation and chaos testing utilities.

#### FailureSimulator

```python
from tests.chaos.chaos_helpers import FailureSimulator

simulator = FailureSimulator()

# Inject failures
simulator.inject_failure('timeout', duration_ms=5000)
simulator.inject_failure('connection_error')
simulator.inject_failure('rate_limit', rate_limit_num=429)
simulator.inject_failure('data_corruption', data={"key": "value"})

# Check failure counts
count = simulator.get_failure_count('timeout')
```

**Supported Failure Types:**

| Type | Description | Parameters |
|------|-------------|-------------|
| `timeout` | Request timeout | `duration_ms` |
| `connection_error` | Connection lost | None |
| `dns_failure` | DNS resolution failed | None |
| `rate_limit` | Rate limit exceeded | `rate_limit_num` |
| `server_error` | 5xx server error | `status_code` |
| `network_partition` | Network partitioned | None |
| `cache_corruption` | Cache data corrupted | `data` |
| `data_corruption` | Data corrupted | `data` |

#### ChaosTestHelper

```python
from tests.chaos.chaos_helpers import ChaosTestHelper

helper = ChaosTestHelper()

# Simulate failures
helper.simulate_database_failure(duration_seconds=5)
helper.simulate_cache_failure(corruption_probability=0.5)
helper.simulate_api_timeout(endpoint="/api/test", timeout_ms=5000)
helper.simulate_network_partition(duration_seconds=5)
helper.simulate_dns_failure(domain="example.com")
helper.simulate_rate_limit()

# Measure recovery time
result, recovery_time = helper.measure_recovery_time(
    some_function, arg1, arg2
)

# Verify no data loss
no_loss = helper.verify_no_data_loss(before_data, after_data)
```

#### NetworkChaosSimulator

```python
from tests.chaos.chaos_helpers import NetworkChaosSimulator

# Network partition
with NetworkChaosSimulator.partition(duration_seconds=5):
    # Code executed during partition
    make_api_request()

# Add latency
with NetworkChaosSimulator.latency_addition(min_delay_ms=100, max_delay_ms=500):
    # Code executed with latency
    make_api_request()

# Packet loss
with NetworkChaosSimulator.packet_loss(loss_probability=0.1):
    # 10% packet loss
    make_api_request()
```

#### DatabaseChaosSimulator

```python
from tests.chaos.chaos_helpers import DatabaseChaosSimulator

# Connection loss
with DatabaseChaosSimulator.connection_loss(duration_seconds=5):
    # DB unavailable during this block
    query_database()

# Transaction deadlock
with DatabaseChaosSimulator.transaction_deadlock():
    # Deadlock scenario
    execute_transaction()

# Slow query
with DatabaseChaosSimulator.slow_query(min_delay_ms=1000, max_delay_ms=5000):
    # Query latency simulated
    execute_query()
```

#### CacheChaosSimulator

```python
from tests.chaos.chaos_helpers import CacheChaosSimulator

# Corrupt cache data
cache = {"key1": "value1", "key2": "value2"}
corrupted = CacheChaosSimulator.corrupt_cache_data(
    cache, corruption_probability=0.5
)

# Cache expiry
with CacheChaosSimulator.cache_expiry(ttl_seconds=60):
    # Cache expires after TTL
    access_cache()
```

#### PerformanceMonitor

```python
from tests.chaos.chaos_helpers import PerformanceMonitor

monitor = PerformanceMonitor()

# Track metric duration
with monitor.track_metric("api_call_duration"):
    make_api_request()

# Get metric data
metric = monitor.get_metric("api_call_duration")
print(f"Duration: {metric['duration']}s")
```

### Fuzzing Helpers

**Location:** `backend/tests/fuzzy_tests/fuzz_helpers.py`

Provides Atheris fuzzing test utilities.

```python
from tests.fuzzy_tests.fuzz_helpers import setup_fuzzer, run_fuzzer

def test_fuzz(data: bytes):
    """Fuzz test function."""
    # Parse input
    # Test with data
    pass

# Setup and run fuzzer
setup_fuzzer(test_fuzz)
run_fuzz()
```

**Decorators:**

```python
from tests.fuzzy_tests.fuzz_helpers import with_expected_exceptions

@with_expected_exceptions(ValueError, TypeError)
def test_fuzz(data):
    # Expected exceptions are caught during fuzzing
    pass
```

### Utility Functions

```python
# Sanitize bytes to string
from tests.fuzzy_tests.fuzz_helpers import sanitize_bytes
safe_str = sanitize_bytes(b"invalid utf-8 \xff")

# Truncate string for safety
from tests.fuzzy_tests.fuzz_helpers import truncate_string
safe = truncate_string(very_long_string, max_length=1000)

# Inject random failure
from tests.chaos.chaos_helpers import inject_random_failure

@inject_random_failure(['timeout', 'connection_error'], probability=0.1)
def risky_operation():
    # 10% chance of injected failure
    pass

# Verify resilience
from tests.chaos.chaos_helpers import verify_resilience_requirement
verify_resilience_requirement(
    recovery_time_seconds=3.2,
    max_acceptable_time=5.0,
    no_data_loss=True
)

# Measure stability
from tests.chaos.chaos_helpers import measure_system_stability
is_stable = measure_system_stability(
    operations_completed=95,
    operations_failed=5,
    min_completion_rate=0.95
)
```

---

## Test Environment Configuration

### Backend (Python/pytest)

#### Configuration Files

| File | Purpose |
|------|---------|
| `backend/tests/conftest.py` | Root pytest configuration |
| `backend/tests/property_tests/conftest.py` | Property test fixtures |
| `backend/tests/integration/conftest.py` | API integration fixtures |

#### Running Tests

```bash
# All tests
cd backend
pytest tests/ -v

# Specific test file
pytest tests/test_governance_performance.py -v

# With coverage
pytest tests/ --cov=core --cov-report=html

# Property tests only
pytest tests/property_tests/ -v

# Integration tests only
pytest tests/integration/ -v

# Chaos tests
pytest tests/chaos/ -v

# Parallel execution (requires pytest-xdist)
pytest tests/ -n auto

# Loadscope scheduling (groups tests by scope)
pytest tests/ -n auto --dist=loadscope
```

#### pytest Options

- `-v`: Verbose output
- `--cov=core`: Coverage for core module
- `--cov-report=html`: HTML coverage report
- `--cov-report=json`: JSON coverage report
- `-n auto`: Parallel execution with all CPUs
- `--dist=loadscope`: Group tests by scope for isolation
- `-k "test_name"`: Run tests matching pattern
- `-x`: Stop on first failure
- `--tb=short`: Shorter tracebacks

### Mobile (React Native/Jest)

#### Configuration Files

| File | Purpose |
|------|---------|
| `mobile/jest.config.js` | Jest configuration |
| `mobile/jest.setup.js` | Global mocks and setup |

#### Jest Configuration

```javascript
module.exports = {
  preset: 'jest-expo',
  setupFilesAfterEnv: ['./jest.setup.js'],
  transformIgnorePatterns: [
    'node_modules/(?!(jest-)?react-native|@react-native(-community)?|expo(nent)?|...)'
  ],
  testMatch: [
    '**/__tests__/**/*.[jt]s?(x)',
    '**/?(*.)+(spec|test).[jt]s?(x)'
  ],
  collectCoverageFrom: [
    'src/**/*.{ts,tsx}',
    '!src/**/*.d.ts',
    '!src/types/**'
  ],
  coverageReporters: ['json', 'lcov', 'text', 'html'],
  coverageDirectory: 'coverage',
  coverageThreshold: {
    global: {
      branches: 80,
      functions: 80,
      lines: 80,
      statements: 80
    }
  }
};
```

#### Global Mocks (jest.setup.js)

| Module | Mock Purpose |
|--------|-------------|
| `expo-camera` | Camera permissions and capture |
| `expo-location` | Location permissions and position |
| `expo-notifications` | Push notifications |
| `expo-local-authentication` | Biometric auth |
| `expo-secure-store` | Secure key-value storage |
| `@react-native-async-storage/async-storage` | Async storage |
| `expo-constants` | App configuration |
| `expo-device` | Device information |
| `react-native-mmkv` | Fast key-value storage |
| `@react-native-community/netinfo` | Network status |

#### Running Tests

```bash
# All tests
cd mobile
npm test

# With coverage
npm test -- --coverage

# Watch mode
npm test -- --watch

# Specific test file
npm test -- AuthService.test.tsx

# Update snapshots
npm test -- -u

# Coverage report
open coverage/index.html
```

### Desktop (Rust/Tauri)

#### Test Structure

```
frontend-nextjs/src-tauri/
├── tests/
│   ├── main.rs.test.rs    # Unit tests
│   ├── commands.rs.test.rs
│   ├── menu.rs.test.rs
│   └── websocket.rs.test.rs
└── coverage.sh           # Coverage script
```

#### Running Tests

```bash
# Unit tests
cd frontend-nextjs/src-tauri
cargo test

# With output
cargo test -- --nocapture

# Coverage (x86_64 only)
./coverage.sh

# Specific test
cargo test test_camera_command
```

#### Coverage Tool

Uses `cargo-tarpaulin` for Rust coverage:

```bash
#!/bin/bash
cargo tarpaulin --out Json \
  --output-dir coverage \
  --workspace \
  --timeout 120 \
  --exclude-files "*/src-tauri/*"
```

---

## Coverage Tracking Setup

### Coverage Reports Location

```
backend/tests/coverage_reports/
├── README.md                    # Coverage documentation
├── aggregate_coverage.py         # Aggregation script
├── coverage_trend.json          # Historical trends
├── desktop_coverage.json         # Desktop coverage
├── metrics/
│   └── coverage.json           # Backend coverage (pytest-cov)
├── html/                      # HTML coverage report
│   └── index.html
└── trends/                     # Trend analysis data
```

### Backend Coverage (pytest-cov)

#### Generate Coverage

```bash
# HTML report
pytest tests/ --cov=core --cov-report=html

# JSON report
pytest tests/ --cov=core --cov-report=json

# Terminal report
pytest tests/ --cov=core --cov-report=term-missing

# All formats
pytest tests/ --cov=core --cov-report=html --cov-report=json --cov-report=term
```

#### Coverage JSON Format

```json
{
  "meta": {
    "format": 3,
    "version": "7.12.0",
    "timestamp": "2026-02-11T16:09:59.696227"
  },
  "files": {
    "api/ab_testing.py": {
      "summary": {
        "covered_lines": 50,
        "num_statements": 79,
        "percent_covered": 63.29
      },
      "missing_lines": [17, 18, 19, ...]
    }
  },
  "totals": {
    "covered_lines": 15234,
    "num_statements": 19845,
    "percent_covered": 76.75
  }
}
```

### Mobile Coverage (Jest)

#### Generate Coverage

```bash
cd mobile
npm test -- --coverage
```

#### Coverage Files

| File | Purpose |
|------|---------|
| `coverage/coverage-summary.json` | Machine-readable metrics |
| `coverage/lcov.info` | LCOV format for CI/CD |
| `coverage/index.html` | HTML report |

#### Coverage Summary Format

```json
{
  "total": {
    "lines": { "total": 1234, "covered": 1050, "pct": 85.1 },
    "functions": { "total": 234, "covered": 198, "pct": 84.6 },
    "branches": { "total": 456, "covered": 378, "pct": 82.9 },
    "statements": { "total": 1456, "covered": 1256, "pct": 86.3 }
  }
}
```

### Desktop Coverage (cargo-tarpaulin)

#### Generate Coverage

```bash
cd frontend-nextjs/src-tauri
./coverage.sh
```

#### Coverage JSON

```json
{
  "desktop_percent": 74.0,
  "files": [
    {"path": "src/main.rs", "coverage": 75.0},
    {"path": "src/commands.rs", "coverage": 70.0}
  ]
}
```

**Note:** cargo-tarpaulin only works on x86_64. ARM Macs (M1/M2/M3) must use CI/CD or x86_64 runners.

### Aggregated Coverage

#### Aggregate Script

**Location:** `backend/tests/coverage_reports/aggregate_coverage.py`

```bash
cd backend/tests/coverage_reports
python aggregate_coverage.py
```

#### Output: coverage_trend.json

```json
{
  "backend_percent": 76.8,
  "mobile_percent": 85.1,
  "desktop_percent": 74.0,
  "overall_percent": 78.6,
  "last_updated": "2026-02-11T16:15:00.000Z",
  "history": [
    {
      "date": "2026-02-11",
      "timestamp": "2026-02-11T16:15:00.000Z",
      "backend_percent": 76.8,
      "mobile_percent": 85.1,
      "desktop_percent": 74.0,
      "overall_percent": 78.6,
      "meets_target": false
    }
  ]
}
```

#### Coverage Formula

```
Overall Coverage = (Backend + Mobile + Desktop) / 3
```

#### Coverage Targets

| Platform | Target | Current |
|----------|--------|---------|
| Backend (Python) | 80% | 76.8% |
| Mobile (React Native) | 80% | 85.1% |
| Desktop (Rust) | 80% | 74.0% |
| **Overall** | **80%** | **78.6%** |

### Quality Gates

#### Assertion Density

**Location:** `backend/tests/conftest.py`

Checks for 0.15 assertions per line threshold (15 assertions per 100 lines).

```python
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Display quality metrics after test run."""
    min_density = 0.15
    # Warn if density < threshold
    if density < min_density:
        terminalreporter.write_line(
            f"Low assertion density: {density:.3f} (target: {min_density})",
            red=True
        )
```

#### Coverage Thresholds

**Backend:** pytest-cov with `--cov-fail-under` (Phase 5 decision: removed from config, tracked separately)

**Mobile:** Jest coverage threshold in `jest.config.js`

```javascript
coverageThreshold: {
  global: {
    branches: 80,
    functions: 80,
    lines: 80,
    statements: 80
  }
}
```

**Desktop:** No automatic threshold, tracked via `aggregate_coverage.py`

---

## Platform-Specific Testing

### Backend Testing Patterns

#### Property-Based Testing (Hypothesis)

```python
from hypothesis import given, strategies as st
from tests.property_tests.conftest import db_session

@given(st.lists(st.integers(min_value=0, max_value=100), min_size=0, max_size=10))
def test_agent_confidence_range(scores):
    """Agent confidence scores always in [0, 1]."""
    for score in scores:
        agent = AgentFactory(confidence_score=score / 100.0)
        assert 0.0 <= agent.confidence_score <= 1.0
```

#### Integration Testing

```python
from tests.integration.conftest import client, auth_headers

def test_protected_endpoint(client, auth_headers):
    """Test authenticated API endpoint."""
    response = client.get(
        "/api/agents",
        headers=auth_headers
    )
    assert response.status_code == 200
    assert len(response.json()) > 0
```

#### Chaos Testing

```python
from tests.chaos.chaos_helpers import ChaosTestHelper

def test_database_recovery():
    """System recovers from database connection loss."""
    helper = ChaosTestHelper()
    recovery_time = helper.simulate_database_failure(duration_seconds=5)
    assert recovery_time < 5.0
```

### Mobile Testing Patterns

#### Component Testing

```typescript
import { render, screen } from '@testing-library/react-native';
import AuthContext from '../contexts/AuthContext';

describe('AuthContext', () => {
  it('provides authentication state', () => {
    render(<AuthContext><TestComponent /></AuthContext>);
    expect(screen.getByText('Login')).toBeTruthy();
  });
});
```

#### Mock Usage

```typescript
// Use mocked expo modules
import * as SecureStore from 'expo-secure-store';

jest.mock('expo-secure-store');

SecureStore.setItemAsync.mockResolvedValue(undefined);
SecureStore.getItemAsync.mockResolvedValue('token-value');
```

### Desktop Testing Patterns

#### Unit Testing

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_camera_permission() {
        assert_eq!(check_camera_permission(), true);
    }
}
```

---

## Best Practices

### Test Data Management

1. **Use Factories for All Test Data**
   - Never hardcode test data
   - Use `Factory.create()` or `Factory.create_batch()`
   - Leverage Faker for dynamic values

2. **Isolate Test Data**
   - Each test gets fresh `db_session` fixture
   - Use `unique_resource_name` for parallel execution
   - Clean up resources in `finally` blocks

3. **Use Lazy Attributes**
   - Defer expensive computations until needed
   - Example: `completed_at = LazyAttribute(lambda o: o.started_at + hours(1))`

### Test Organization

1. **Directory Structure**
   ```
   tests/
   ├── property_tests/      # Hypothesis property tests
   ├── integration/         # API integration tests
   ├── security/           # Security tests
   ├── chaos/              # Chaos engineering
   ├── fuzzy_tests/        # Fuzzing tests
   ├── e2e/               # End-to-end tests
   └── unit/               # Unit tests
   ```

2. **Naming Conventions**
   - Test files: `test_<module>.py`
   - Test classes: `Test<ClassName>`
   - Test functions: `test_<behavior>`

3. **Documentation**
   - Docstrings for all tests
   - Comments for complex test scenarios
   - Scenario references (e.g., "AUTH-001: User Login")

### Parallel Execution

1. **Use pytest-xdist**
   ```bash
   pytest tests/ -n auto --dist=loadscope
   ```

2. **Avoid State Sharing**
   - Each test gets unique `db_session`
   - Use `unique_resource_name` fixture
   - Don't use global mutable state

3. **Test Isolation**
   - Transaction rollback after each test
   - Fresh database for each test
   - Clean up temp files

### Coverage Targets

1. **80% Overall Coverage**
   - Backend: pytest-cov
   - Mobile: Jest
   - Desktop: cargo-tarpaulin

2. **Track Trends**
   - Run `aggregate_coverage.py` after tests
   - Monitor `coverage_trend.json`
   - HTML reports for detailed analysis

3. **Critical Path Coverage**
   - Authentication: 100%
   - Agent governance: 90%+
   - Payment processing: 100%

### Error Handling

1. **Expected Exceptions**
   ```python
   with pytest.raises(ValueError):
       AgentFactory(confidence_score=2.0)  # Invalid
   ```

2. **Timeout Handling**
   ```python
   with pytest.raises(TimeoutError):
       call_with_timeout(api_request, timeout_ms=5000)
   ```

3. **Chaos Recovery**
   ```python
   try:
       helper.simulate_database_failure()
   except ConnectionError:
       pass  # Expected
   finally:
       verify_data_integrity()
   ```

---

## Appendix: Quick Reference

### Common Factory Patterns

| Pattern | Example |
|----------|----------|
| Single object | `agent = AgentFactory()` |
| Batch creation | `agents = AgentFactory.create_batch(10)` |
| With params | `agent = AgentFactory(name="Test")` |
| With session | `agent = AgentFactory(_session=db)` |
| Specific maturity | `agent = StudentAgentFactory()` |

### Common Fixtures

| Fixture | Purpose | Location |
|----------|---------|----------|
| `db_session` | In-memory database | `property_tests/conftest.py` |
| `test_agent` | Single test agent | `property_tests/conftest.py` |
| `client` | FastAPI TestClient | `integration/conftest.py` |
| `auth_token` | JWT for user | `integration/conftest.py` |
| `admin_token` | JWT for admin | `integration/conftest.py` |
| `auth_headers` | Auth headers dict | `integration/conftest.py` |
| `unique_resource_name` | Unique test identifier | `conftest.py` |

### Common Test Commands

| Command | Purpose |
|----------|---------|
| `pytest tests/ -v` | All backend tests |
| `pytest tests/ --cov=core` | Backend coverage |
| `pytest tests/property_tests/` | Property tests only |
| `npm test -- --coverage` | Mobile coverage |
| `cargo test` | Desktop tests |
| `python aggregate_coverage.py` | Aggregate coverage |

### Failure Simulation

| Failure Type | Function |
|-------------|----------|
| Timeout | `simulator.inject_failure('timeout', duration_ms=5000)` |
| Connection error | `simulator.inject_failure('connection_error')` |
| Network partition | `NetworkChaosSimulator.partition(duration_seconds=5)` |
| DB connection loss | `DatabaseChaosSimulator.connection_loss(5)` |
| Cache corruption | `CacheChaosSimulator.corrupt_cache_data(cache, 0.5)` |

---

**End of Document**

For test scenario documentation, see: `.planning/phases/250-comprehensive-testing/SCENARIOS.md`
For testing execution results, see: `.planning/phases/250-comprehensive-testing/250-01-SUMMARY.md`
