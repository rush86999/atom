# Test Data Factories

This directory contains factory_boy factories for generating isolated, dynamic test data.

## Why Factories?

**Problem:** Hardcoded test data causes coupling and flaky tests.

```python
# BAD: Hardcoded ID
agent_id = "test-agent-123"
# Fails if another test uses same ID

# GOOD: Factory-generated ID
agent = AgentFactory.create()
# Each test gets unique UUID
```

**Benefits:**
- Unique IDs every time (no collisions)
- Realistic data via Faker
- Relationship handling (SubFactory)
- Easy to override specific values

## CRITICAL: Test Isolation

**ALL factory calls in test environment MUST include `_session` parameter.**

Test environment is detected by `PYTEST_XDIST_WORKER_ID` environment variable (set by pytest-xdist during parallel execution). When this is set, `BaseFactory._create()` enforces that `_session` parameter is provided.

### BAD: Missing _session parameter

```python
def test_agent_creation():
    agent = AgentFactory.create()  # RuntimeError in test environment!
    # Error: AgentFactory.create() requires _session parameter in test environment.
    #        Usage: AgentFactory.create(_session=db_session, ...)
```

### GOOD: With _session parameter

```python
def test_agent_creation(db_session):
    agent = AgentFactory.create(_session=db_session)
    # Uses test fixture session with transaction rollback
    # Automatic cleanup, no shared state between tests
```

### Why Is This Required?

1. **Transaction Rollback Isolation**: Each test gets a fresh database transaction that's rolled back after the test completes. This ensures zero shared state between parallel tests.

2. **Parallel Execution Safety**: pytest-xdist runs tests on multiple workers (gw0, gw1, gw2, gw3). Without explicit session injection, tests might share database connections, causing data collisions.

3. **Enforcement Prevents Bugs**: Forgetting `_session=db_session` causes intermittent test failures that are hard to debug. The enforcement makes the error explicit and guides you to the correct pattern.

### Available Factories

### AgentFactory

Creates AgentRegistry instances with valid governance data.

```python
from tests.factories import AgentFactory

def test_agent_usage(db_session):
    # Basic usage
    agent = AgentFactory.create(_session=db_session)

    # Override specific fields
    student_agent = AgentFactory.create(
        _session=db_session,
        status="STUDENT",
        confidence=0.4
    )

    # Use maturity-specific factories
    from tests.factories.agent_factory import (
        StudentAgentFactory,
        AutonomousAgentFactory
    )
    autonomous = AutonomousAgentFactory.create(_session=db_session)
```

### UserFactory

Creates User instances with authentication data.

```python
from tests.factories import UserFactory

def test_user_usage(db_session):
    user = UserFactory.create(
        _session=db_session,
        email="test@example.com",  # Override
        role="member"
    )

    # Admin user
    from tests.factories.user_factory import AdminUserFactory
    admin = AdminUserFactory.create(_session=db_session)
```

### EpisodeFactory / EpisodeSegmentFactory

Creates episodic memory test data with relationships.

```python
from tests.factories import EpisodeFactory, EpisodeSegmentFactory

def test_episode_usage(db_session):
    # Create an episode
    episode = EpisodeFactory.create(
        _session=db_session,
        agent_id="agent-123",
        title="Test Episode"
    )

    # Create segments linked to episode
    segment = EpisodeSegmentFactory.create(
        _session=db_session,
        episode_id=episode.id,
        segment_type="task"
    )
```

### AgentExecutionFactory

Creates execution records with timing and governance metadata.

```python
from tests.factories.execution_factory import AgentExecutionFactory

def test_execution_usage(db_session):
    execution = AgentExecutionFactory.create(
        _session=db_session,
        agent_id="agent-123",
        status="completed",
        tokens_used=1500
    )
```

### CanvasAuditFactory

Creates canvas interaction records.

```python
from tests.factories.canvas_factory import CanvasAuditFactory

def test_canvas_usage(db_session):
    canvas = CanvasAuditFactory.create(
        _session=db_session,
        canvas_type="sheets",
        action="present"
    )
```

## Factory Patterns

### Building (no persistence)

```python
# Build without saving to database
agent = AgentFactory.build()
# agent.id is set but not in DB
```

### Creating (with persistence)

```python
# Create and save to database
agent = AgentFactory.create()
# agent is in database
```

### Batch Creation

```python
# Create multiple instances
agents = AgentFactory.create_batch(5)
# Returns list of 5 agents
```

### Relationships

```python
# Episode with segments (using SubFactory in EpisodeSegmentFactory)
episode = EpisodeFactory.create()
segment = EpisodeSegmentFactory.create(episode_id=episode.id)
```

### Faker Integration

Factories use Faker for realistic data:

```python
# Names, emails, phone numbers
user = UserFactory.create()
# user.email = "john.doe@example.com"
# user.first_name = "John"

# Company names, UUIDs
agent = AgentFactory.create()
# agent.name = "Acme Corp"
# agent.id = "a1b2c3d4-e5f6..."
```

## Session Handling

**CRITICAL**: All factory calls in test environment MUST include `_session` parameter.

The `db_session` fixture provides an isolated database transaction that's rolled back after each test. This ensures:
- Zero shared state between parallel tests
- Instant cleanup (no manual DELETE queries)
- Consistent test results

### Correct Usage

```python
def test_agent_creation(db_session):
    agent = AgentFactory.create(_session=db_session)
    # Uses test fixture session with transaction rollback

def test_batch_creation(db_session):
    agents = AgentFactory.create_batch(5, _session=db_session)
    # All agents use same session
```

## Best Practices

1. **Always use factories** - Never hardcode IDs
2. **Use specific factories** - StudentAgentFactory, not AgentFactory with status override
3. **Build when possible** - Use `.build()` for read-only tests (faster)
4. **Clean up in fixtures** - Use function-scoped db_session with rollback
5. **Document custom values** - Comment why you're overriding defaults

## Anti-Patterns

```python
# BAD: Hardcoded ID
agent_id = "test-123"
agent = db.query(AgentRegistry).get(agent_id)

# GOOD: Factory
agent = AgentFactory.create()
agent_id = agent.id

# BAD: Manual object creation
agent = AgentRegistry(
    id="123",
    name="Test",
    # ... many fields ...
)

# GOOD: Factory
agent = AgentFactory.create(name="Test")
```

## Troubleshooting

### RuntimeError: requires _session parameter

**Error**:
```
RuntimeError: AgentFactory.create() requires _session parameter in test environment.
Usage: AgentFactory.create(_session=db_session, ...)
```

**Cause**: Factory called without `_session` parameter in test environment (detected by `PYTEST_XDIST_WORKER_ID`).

**Solution**: Add `_session=db_session` to factory call:
```python
# BAD
agent = AgentFactory.create()

# GOOD
agent = AgentFactory.create(_session=db_session)
```

### IntegrityError: duplicate key

**Error**:
```
sqlalchemy.exc.IntegrityError: (sqlite3.IntegrityError) UNIQUE constraint failed: agent_registry.id
```

**Cause**: Using hardcoded IDs or not using `unique_resource_name` fixture.

**Solution**: Use `unique_resource_name` fixture for unique IDs:
```python
def test_agent_creation(unique_resource_name, db_session):
    agent = AgentFactory.create(
        _session=db_session,
        id=unique_resource_name  # "test_gw0_a1b2c3d4"
    )
```

### Data not visible in test

**Error**: Test data created but not visible in same test.

**Cause**: Using different sessions or not committing/flushing.

**Solution**: Ensure same session used throughout test:
```python
def test_agent_visibility(db_session):
    agent = AgentFactory.create(_session=db_session)

    # Data visible immediately (flush mode)
    retrieved = db_session.query(AgentRegistry).filter_by(id=agent.id).first()
    assert retrieved is not None
```

## See Also

- [factory_boy Documentation](https://factoryboy.readthedocs.io/)
- [Faker Documentation](https://faker.readthedocs.io/)
- [TESTING_GUIDE.md](../TESTING_GUIDE.md)
- [TEST_ISOLATION_PATTERNS.md](./docs/TEST_ISOLATION_PATTERNS.md) - Complete isolation patterns guide
