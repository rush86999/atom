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

## Available Factories

### AgentFactory

Creates AgentRegistry instances with valid governance data.

```python
from tests.factories import AgentFactory

# Basic usage
agent = AgentFactory.create()

# Override specific fields
student_agent = AgentFactory.create(
    status="STUDENT",
    confidence=0.4
)

# Use maturity-specific factories
from tests.factories.agent_factory import (
    StudentAgentFactory,
    AutonomousAgentFactory
)
autonomous = AutonomousAgentFactory.create()
```

### UserFactory

Creates User instances with authentication data.

```python
from tests.factories import UserFactory

user = UserFactory.create(
    email="test@example.com",  # Override
    role="member"
)

# Admin user
from tests.factories.user_factory import AdminUserFactory
admin = AdminUserFactory.create()
```

### EpisodeFactory / EpisodeSegmentFactory

Creates episodic memory test data with relationships.

```python
from tests.factories import EpisodeFactory, EpisodeSegmentFactory

# Create an episode
episode = EpisodeFactory.create(
    agent_id="agent-123",
    title="Test Episode"
)

# Create segments linked to episode
segment = EpisodeSegmentFactory.create(
    episode_id=episode.id,
    segment_type="task"
)
```

### AgentExecutionFactory

Creates execution records with timing and governance metadata.

```python
from tests.factories.execution_factory import AgentExecutionFactory

execution = AgentExecutionFactory.create(
    agent_id="agent-123",
    status="completed",
    tokens_used=1500
)
```

### CanvasAuditFactory

Creates canvas interaction records.

```python
from tests.factories.canvas_factory import CanvasAuditFactory

canvas = CanvasAuditFactory.create(
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

Factories require a database session. Inject via `_session` parameter:

```python
def test_agent_creation(db_session):
    agent = AgentFactory.create(_session=db_session)
    # Uses test fixture session
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

## See Also

- [factory_boy Documentation](https://factoryboy.readthedocs.io/)
- [Faker Documentation](https://faker.readthedocs.io/)
- [TESTING_GUIDE.md](../TESTING_GUIDE.md)
