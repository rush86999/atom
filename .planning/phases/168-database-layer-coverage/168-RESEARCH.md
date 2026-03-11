# Phase 168: Database Layer Coverage - Research

**Researched:** March 11, 2026
**Domain:** SQLAlchemy ORM Testing with SQLite In-Memory Databases
**Confidence:** HIGH

## Summary

Phase 168 focuses on achieving 80%+ line coverage on database models through comprehensive testing of CRUD operations, relationships, constraints, and cascading behaviors. The codebase contains **235 database models** across 10 model modules (core, accounting, sales, service_delivery, analytics, ecommerce, intelligence, marketing, saas, atom_security). Current testing infrastructure exists but needs significant expansion to cover all models.

**Primary challenges:**
1. Massive model count (235 models) requiring systematic test organization
2. Complex relationship types (one-to-many, many-to-many, self-referential)
3. Cascade delete behaviors need explicit testing
4. SQLite in-memory databases for test isolation
5. Existing factories cover ~15% of models

**Primary recommendation:** Use a phased approach organized by model module, starting with high-value core models (AgentRegistry, User, Workspace, Episode) then expanding to domain-specific modules (accounting, sales, service_delivery). Leverage existing factory pattern and db_session fixture.

## Standard Stack

### Core Testing Libraries

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | ^7.4.0 | Test runner | De facto standard for Python testing |
| SQLAlchemy | 2.0+ | ORM testing | Official SQLAlchemy test patterns |
| sqlite3 | (stdlib) | In-memory test database | Fast, isolated test database |
| factory_boy | ^3.3.0 | Test data generation | Standard factory pattern for SQLAlchemy |
| Faker | ^19.0+ | Realistic test data | Complements factories with fake data |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-cov | ^4.1.0 | Coverage reporting | Coverage metrics for 80% target |
| pytest-xdist | ^3.5.0 | Parallel test execution | For large test suites (1000+ tests) |
| freezegun | ^1.4.0 | Time freezing | Timestamp-dependent model tests |

### Existing Infrastructure (Already Standard)

| Component | Location | Purpose |
|-----------|----------|---------|
| `db_session` fixture | `tests/conftest.py` | SQLite in-memory database per test |
| `test_agent_*` fixtures | `tests/conftest.py` | Pre-configured agent maturity levels |
| Factory classes | `tests/factories/` | Model creation helpers |
| Base test classes | `tests/test_models_coverage.py` | ORM testing patterns |

**Installation:**
```bash
# All dependencies already present in requirements.txt
pip install pytest pytest-cov factory_boy faker freezegun pytest-xdist
```

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| sqlite3 (in-memory) | postgresql-test-db | SQLite is 10x faster, PostgreSQL better for FK constraint testing |
| factory_boy | Model Mama | Factory Boy has better SQLAlchemy integration |
| pytest | unittest | pytest has superior fixture system and parametrization |

## Architecture Patterns

### Recommended Project Structure

```
backend/tests/
├── database/                          # Database layer tests
│   ├── test_core_models.py           # Core models (Agent, User, Workspace, Episode)
│   ├── test_accounting_models.py     # Accounting models (Account, Transaction, JournalEntry)
│   ├── test_sales_models.py          # Sales models (Lead, Deal, Commission)
│   ├── test_service_models.py        # Service delivery (Contract, Project, Milestone)
│   ├── test_relationships.py         # Cross-model relationship tests
│   ├── test_constraints.py           # FK, unique, not null constraints
│   ├── test_cascades.py              # Cascade delete behaviors
│   └── test_special_fields.py        # JSON, encrypted, computed fields
├── factories/                         # Test data factories
│   ├── accounting_factory.py         # NEW: Accounting model factories
│   ├── sales_factory.py              # NEW: Sales model factories
│   ├── service_factory.py            # NEW: Service delivery factories
│   └── ...existing factories...
└── conftest.py                        # Shared fixtures (db_session already exists)
```

### Pattern 1: SQLite In-Memory Database Fixture

**What:** Function-scoped fixture creating fresh SQLite database for each test.

**When to use:** All database model tests requiring isolation.

**Example:**
```python
# Source: tests/conftest.py (lines 199-258)
@pytest.fixture(scope="function")
def db_session():
    """
    Standardized database session fixture for all tests.
    Creates a fresh in-memory SQLite database for each test function.
    """
    from core.database import Base

    # Use file-based temp SQLite for better compatibility
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        echo=False
    )

    # Create tables with graceful handling of missing FKs
    Base.metadata.create_all(engine, checkfirst=True)

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    yield session

    # Cleanup
    session.close()
    engine.dispose()
    os.unlink(db_path)
```

### Pattern 2: Factory Boy for Test Data

**What:** Declarative test data generation with SQLAlchemy integration.

**When to use:** Creating model instances with default values for tests.

**Example:**
```python
# Source: tests/factories/agent_factory.py
import factory
from factory.alchemy import SQLAlchemyModelFactory
from core.models import AgentRegistry

class AgentFactory(SQLAlchemyModelFactory):
    class Meta:
        model = AgentRegistry
        sqlalchemy_session_persistence = "commit"

    id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    name = factory.Sequence(lambda n: f"TestAgent{n}")
    category = "testing"
    module_path = "test.module"
    class_name = "TestAgent"
    status = AgentStatus.STUDENT.value
    confidence_score = 0.5

# Usage in tests
def test_agent_creation(db_session):
    agent = AgentFactory(_session=db_session)
    assert agent.name == "TestAgent0"
```

### Pattern 3: Relationship Testing Class

**What:** Test class grouping relationship tests by type (one-to-many, many-to-many, self-referential).

**When to use:** Testing complex model relationships.

**Example:**
```python
# Source: tests/database/test_database_models.py (lines 58-338)
class TestRelationships:
    """Test all model relationship types."""

    def test_user_workspace_many_to_many_relationship(self, db_session):
        """Test User-Workspace many-to-many relationship via user_workspaces table."""
        workspace = WorkspaceFactory(_session=db_session)
        db_session.commit()

        user1 = UserFactory(email="user1@test.com", _session=db_session)
        user2 = UserFactory(email="user2@test.com", _session=db_session)

        workspace.users.append(user1)
        workspace.users.append(user2)
        db_session.commit()

        assert len(workspace.users) == 2

    def test_agent_execution_one_to_many_relationship(self, db_session):
        """Test Agent has many executions (one-to-many)."""
        agent = AgentFactory(_session=db_session)
        execution1 = AgentExecutionFactory(agent_id=agent.id, _session=db_session)
        execution2 = AgentExecutionFactory(agent_id=agent.id, _session=db_session)
        db_session.commit()

        executions = db_session.query(AgentExecution).filter(
            AgentExecution.agent_id == agent.id
        ).all()
        assert len(executions) == 2
```

### Pattern 4: Cascade Testing

**What:** Test cascade delete and nullify behaviors when parent models are deleted.

**When to use:** Models with cascade delete configurations.

**Example:**
```python
# Source: tests/database/test_database_models.py (lines 746-810)
class TestCascades:
    """Test cascade delete and update operations."""

    def test_cascade_delete_episode_to_segments(self, db_session):
        """Test deleting episode removes segments (cascade configured)."""
        agent = AgentFactory(_session=db_session)
        episode = EpisodeFactory(agent_id=agent.id, _session=db_session)

        # Create 10 segments
        segments = []
        for i in range(10):
            segment = EpisodeSegment(
                episode_id=episode.id,
                segment_type="conversation",
                sequence_order=i + 1,
                content=f"Segment {i}",
                source_type="chat_message"
            )
            segments.append(segment)

        db_session.add_all(segments)
        db_session.commit()

        # Delete episode
        db_session.delete(episode)
        db_session.commit()

        # Verify segments are cascade deleted
        remaining_segments = db_session.query(EpisodeSegment).filter(
            EpisodeSegment.episode_id == episode.id
        ).all()
        assert len(remaining_segments) == 0
```

### Anti-Patterns to Avoid

- **Direct model instantiation in tests:** Always use factories or fixtures for consistency
- **Shared database state:** Never use class-scoped db_session - causes test pollution
- **Testing SQLAlchemy internals:** Focus on your model logic, not SQLAlchemy's ORM
- **Missing rollback on errors:** Always use try/except with db_session.rollback() in test setup
- **Hardcoded timestamps:** Use frozen_time fixture or datetime.utcnow() for reproducibility

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Test data generation | Custom model creation functions | factory_boy | Handles relationships, sequences, lazy evaluation |
| Database isolation | Manual database setup/teardown | pytest fixtures | Automatic cleanup, function-scoped isolation |
| Time-dependent tests | Manual timestamp calculations | freezegun.freeze_time | Deterministic tests, no race conditions |
| Test data randomness | Hardcoded values | Faker | Realistic data, prevents hardcoded assumptions |
| Constraint testing | Manual IntegrityError catching | pytest.raises(IntegrityError) | Standard pytest exception testing pattern |

**Key insight:** Building custom test infrastructure duplicates existing solutions. The codebase already has db_session fixture and factory pattern - extend these rather than rebuilding.

## Common Pitfalls

### Pitfall 1: Missing Foreign Key Handling

**What goes wrong:** Tests fail because SQLite doesn't enforce FK constraints by default, while PostgreSQL does.

**Why it happens:** SQLite PRAGMA foreign_keys must be enabled for FK testing.

**How to avoid:**
```python
# Enable FK constraints in test database
engine = create_engine(
    f"sqlite:///{db_path}",
    connect_args={
        "check_same_thread": False,
        # Critical for FK constraint testing
        "foreign_keys": "ON"  # Enable FK enforcement
    }
)
```

**Warning signs:** Tests pass locally but fail in CI with PostgreSQL.

### Pitfall 2: Session Leaks Between Tests

**What goes wrong:** Tests interfere with each other's data, causing flaky failures.

**Why it happens:** Using class-scoped db_session or not closing sessions properly.

**How to avoid:**
```python
# Always use function-scoped db_session fixture
@pytest.fixture(scope="function")  # NOT scope="class" or "module"
def db_session():
    # ... setup ...
    yield session
    # Cleanup happens automatically
    session.close()
    engine.dispose()
```

**Warning signs:** Flaky tests that pass individually but fail in suite runs.

### Pitfall 3: Cascade Test Assumptions

**What goes wrong:** Cascade tests assume behavior that differs between SQLite and PostgreSQL.

**Why it happens:** Cascade behaviors are database-specific and model-dependent.

**How to avoid:**
```python
# Test actual cascade behavior, not assumptions
def test_cascade_delete_agent_to_executions(self, db_session):
    """Test deleting agent requires deleting executions first (no cascade configured)."""
    agent = AgentFactory(_session=db_session)
    execution1 = AgentExecutionFactory(agent_id=agent.id, _session=db_session)

    # Delete executions first (FK constraint prevents direct agent deletion)
    for execution in agent.executions:
        db_session.delete(execution)
    db_session.commit()

    # Now delete agent
    db_session.delete(agent)
    db_session.commit()

    # Verify both are deleted
```

**Warning signs:** Tests that need manual cleanup order to avoid FK violations.

### Pitfall 4: Missing Relationship Back-Populates

**What goes wrong:** Relationship queries return empty or stale data.

**Why it happens:** SQLAlchemy relationships need explicit back_populates configuration.

**How to avoid:**
```python
# Model configuration
class Agent(Base):
    executions = relationship("AgentExecution", back_populates="agent")

class AgentExecution(Base):
    agent = relationship("Agent", back_populates="executions")

# Test verifies relationship in both directions
def test_bidirectional_relationship(self, db_session):
    agent = AgentFactory(_session=db_session)
    execution = AgentExecutionFactory(agent_id=agent.id, _session=db_session)
    db_session.commit()

    # Forward direction
    assert execution.agent.id == agent.id
    # Reverse direction
    assert execution in agent.executions
```

**Warning signs:** Need to refresh models after relationship changes.

### Pitfall 5: JSON Field Serialization

**What goes wrong:** JSON field tests fail with type errors or serialization issues.

**Why it happens:** SQLite stores JSON as TEXT, requiring explicit serialization.

**How to avoid:**
```python
def test_json_field_handling(self, db_session):
    """Test JSON field serialization/deserialization."""
    config_data = {
        "nested": {"data": [1, 2, 3]},
        "boolean": True,
        "number": 42.5
    }

    agent = AgentFactory(
        configuration=config_data,
        _session=db_session
    )
    db_session.commit()

    # Verify JSON is deserialized correctly
    assert isinstance(agent.configuration, dict)
    assert agent.configuration["nested"]["data"] == [1, 2, 3]
```

**Warning signs:** JSON fields return strings instead of dicts, or vice versa.

## Code Examples

Verified patterns from existing codebase:

### Example 1: Model Creation with Defaults

```python
# Source: tests/test_models_coverage.py (lines 41-58)
def test_agent_registry_create_with_defaults(self, db_session):
    """Test AgentRegistry creation with default values."""
    agent = AgentRegistry(
        name="TestAgent",
        category="testing",
        module_path="test.module",
        class_name="TestClass",
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)

    assert agent.id is not None
    assert agent.name == "TestAgent"
    assert agent.status == AgentStatus.STUDENT.value  # Default status
    assert agent.confidence_score == 0.5  # Default confidence
    assert agent.created_at is not None
```

### Example 2: Unique Constraint Testing

```python
# Source: tests/database/test_database_models.py (lines 426-438)
def test_unique_constraint_user_email(self, db_session):
    """Test User.email must be unique (IntegrityError on duplicate)."""
    user1 = UserFactory(email="unique@test.com", _session=db_session)
    db_session.commit()

    # Try to create second user with same email - should raise IntegrityError
    with pytest.raises(IntegrityError):
        user2 = User(email="unique@test.com", first_name="User", last_name="Two")
        db_session.add(user2)
        db_session.commit()

    db_session.rollback()
```

### Example 3: ORM Query Testing

```python
# Source: tests/database/test_database_models.py (lines 819-833)
def test_filter_agents_by_status(self, db_session):
    """Test Filter agents by status."""
    student = AgentFactory(status=AgentStatus.STUDENT.value, _session=db_session)
    intern = AgentFactory(status=AgentStatus.INTERN.value, _session=db_session)
    autonomous = AgentFactory(status=AgentStatus.AUTONOMOUS.value, _session=db_session)
    db_session.commit()

    # Filter by STUDENT status
    student_agents = db_session.query(AgentRegistry).filter(
        AgentRegistry.status == AgentStatus.STUDENT.value
    ).all()
    assert len(student_agents) == 1
    assert student_agents[0].id == student.id
```

### Example 4: Many-to-Many Relationship Testing

```python
# Source: tests/database/test_database_models.py (lines 107-134)
def test_team_membership_many_to_many_relationship(self, db_session):
    """Test User-Team many-to-many relationship via team_members table."""
    workspace = WorkspaceFactory(_session=db_session)
    team = TeamFactory(workspace_id=workspace.id, _session=db_session)
    db_session.commit()

    user1 = UserFactory(email="member1@test.com", _session=db_session)
    user2 = UserFactory(email="member2@test.com", _session=db_session)

    team.members.append(user1)
    team.members.append(user2)
    db_session.commit()

    # Verify team members
    retrieved_team = db_session.query(Team).filter(Team.id == team.id).first()
    assert len(retrieved_team.members) == 2

    # Verify user teams
    retrieved_user1 = db_session.query(User).filter(User.id == user1.id).first()
    assert len(retrieved_user1.teams) == 1
```

### Example 5: Property and Computed Field Testing

```python
# Source: tests/test_models_coverage.py (lines 426-431)
def test_agent_registry_repr(self, db_session):
    """Test AgentRegistry __repr__ method."""
    agent = AgentFactory(
        name="TestAgent",
        status=AgentStatus.SUPERVISED.value,
        confidence_score=0.75,
        _session=db_session
    )
    db_session.commit()

    repr_str = repr(agent)
    assert "AgentRegistry" in repr_str
    assert agent.name in repr_str
    assert AgentStatus.SUPERVISED.value in repr_str
    assert "0.75" in repr_str
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual model creation | Factory Boy factories | Phase 164 (Feb 2026) | 3x faster test writing, consistent data |
| Shared test database | Function-scoped SQLite temp DB | Phase 164 (Feb 2026) | Zero test pollution, parallel execution safe |
| Hardcoded test data | Faker-generated data | Phase 164 (Feb 2026) | More realistic test scenarios |
| Coverage by service module | Coverage by model module | Phase 168 (current) | Systematic model coverage tracking |

**Deprecated/outdated:**
- Manual `db = SessionLocal()` pattern: Use `db_session` fixture instead
- Class-scoped database fixtures: Use function-scoped for isolation
- Direct `Model(**kwargs)` instantiation: Use factories for consistency

## Database Models Inventory

### Model Counts by Module

| Module | Model Count | Test Coverage Target | Priority |
|--------|-------------|---------------------|----------|
| core/models.py | 215 models | 80%+ | HIGH ( foundational models) |
| accounting/models.py | 12 models | 80%+ | HIGH (financial integrity) |
| sales/models.py | 5 models | 80%+ | MEDIUM |
| service_delivery/models.py | 6 models | 80%+ | MEDIUM |
| analytics/models.py | ~10 models | 70%+ | MEDIUM |
| ecommerce/models.py | ~8 models | 70%+ | LOW |
| intelligence/models.py | ~15 models | 70%+ | LOW |
| marketing/models.py | ~8 models | 70%+ | LOW |
| saas/models.py | ~10 models | 70%+ | LOW |
| atom_security/models.py | ~5 models | 70%+ | LOW |

**Total: ~235 models across 10 modules**

### High-Value Core Models (Priority Testing)

**Must-cover models (top 20 by usage):**
1. AgentRegistry - Agent configuration and governance
2. AgentExecution - Agent execution tracking
3. AgentFeedback - User feedback on agents
4. User - User accounts and authentication
5. Workspace - Workspace isolation
6. Episode - Agent episodic memory
7. EpisodeSegment - Episode content segmentation
8. CanvasAudit - Canvas presentation tracking
9. ChatSession - Chat conversation tracking
10. ChatMessage - Individual message tracking
11. OAuthToken - OAuth integration
12. WorkflowExecution - Workflow execution tracking
13. Team - Team collaboration
14. Tenant - Multi-tenancy support
15. BlockedTriggerContext - Student agent trigger blocking
16. AgentProposal - INTERN agent action proposals
17. SupervisionSession - SUPERVISED agent monitoring
18. TrainingSession - Agent training tracking
19. AgentOperationTracker - Agent operation metrics
20. AgentRequestLog - Agent request logging

### Relationship Types to Test

**One-to-Many Relationships:**
- Agent → AgentExecution (1:N)
- Agent → AgentFeedback (1:N)
- Episode → EpisodeSegment (1:N)
- Workspace → Teams (1:N)
- User → OAuthToken (1:N)
- Contract → Projects (1:N)
- Project → Milestones (1:N)
- Milestone → ProjectTasks (1:N)
- Deal → Commissions (1:N)
- Deal → CallTranscripts (1:N)

**Many-to-Many Relationships:**
- User ↔ Workspace (via user_workspaces)
- User ↔ Team (via team_members)
- Episode ↔ Feedback (via feedback_ids array)
- Episode ↔ Canvas (via canvas_ids array)

**Self-Referential Relationships:**
- Account → Account (parent_id for hierarchical chart of accounts)
- User → User (manager_id for organizational hierarchy)

**Polymorphic Relationships:**
- CanvasAudit → agent OR user (optional foreign keys)
- EpisodeSegment → multiple source types (chat_message, agent_execution, manual)

### Complex Cascade Behaviors

**Cascade Delete Configured:**
- Episode → EpisodeSegment (all, delete-orphan)
- AgentExecution → canvas_audits (relationship may cascade)

**No Cascade (Manual Cleanup Required):**
- Agent → AgentExecution (must delete executions first)
- Agent → AgentFeedback (must delete feedback first)
- Workspace → Teams (must handle team members)
- User → UserAccount (must delete accounts first)

**Nullify Cascades:**
- User.current_workspace_id → set to NULL on workspace delete
- Team.workspace_id → set to NULL on workspace delete

## Coverage Gaps Analysis

### Current Model Testing Coverage

**Existing Tests:**
- `tests/database/test_database_models.py` - 1,370 lines, covers core models
- `tests/test_models_coverage.py` - 1,548 lines, covers model properties
- `tests/unit/test_models_orm.py` - ORM query tests
- `tests/property_tests/models/` - Property-based model tests

**Models with Existing Tests:**
✅ AgentRegistry (relationships, CRUD, queries)
✅ AgentExecution (relationships, cascades)
✅ AgentFeedback (relationships, constraints)
✅ User (relationships, unique constraints)
✅ Workspace (relationships)
✅ Team (many-to-many relationships)
✅ Episode (CRUD, relationships)
✅ EpisodeSegment (ordering, cascade)
✅ CanvasAudit (relationships, JSON fields)
✅ OAuthToken (encryption, relationships)
✅ WorkflowExecution (basic CRUD)

**Models with ZERO or Low Coverage:**
❌ All accounting models (Account, Transaction, JournalEntry, Bill, Invoice, etc.)
❌ All sales models (Lead, Deal, CommissionEntry, CallTranscript, FollowUpTask)
❌ All service delivery models (Contract, Project, Milestone, ProjectTask, Appointment)
❌ Most analytics models (AttributionEvent, ClientHealthScore, CapacityPlan)
❌ Most ecommerce models (EcommerceOrder, EcommerceCustomer, Subscription)
❌ Most intelligence models (BusinessScenario, CapacityPlan, ResourceRole)
❌ Most marketing models (AdSpendEntry, MarketingChannel)
❌ Most saas models (UsageEvent, SaaSTier, SubscriptionAudit)
❌ Low-priority atom_security models

**Estimated Untested Models: ~200 out of 235 (85%)**

### Technical Challenges

1. **Model Count:** 235 models is too many for single test file - need modular approach
2. **Relationship Complexity:** Many models have 5+ relationships requiring dedicated tests
3. **Cascade Testing:** Each cascade needs explicit delete verification
4. **Constraint Testing:** Unique constraints require IntegrityError testing
5. **JSON Field Testing:** Models with JSON fields need serialization testing
6. **Enum Validation:** Each enum field needs valid/invalid value testing
7. **Timestamp Fields:** created_at, updated_at need auto-generation testing
8. **Computed Properties:** Model properties need getter/setter testing

## Test Organization Strategy

### Phase 1: Core Models (Plans 01-03)

**Focus:** Foundational models used across the application.

**File: `tests/database/test_core_models.py`**

**Test Classes:**
- `TestAgentRegistryModels` - AgentRegistry, AgentExecution, AgentFeedback
- `TestUserModels` - User, UserAccount, UserSession
- `TestWorkspaceModels` - Workspace, Team, Tenant
- `TestEpisodeModels` - Episode, EpisodeSegment, EpisodeAccessLog
- `TestCanvasModels` - CanvasAudit, Canvas, CanvasComponent
- `TestChatModels` - ChatSession, ChatMessage, ChatProcess

**Coverage Target:** 85%+ for 50 core models

### Phase 2: Accounting Models (Plan 04)

**Focus:** Financial integrity models.

**File: `tests/database/test_accounting_models.py`**

**Test Classes:**
- `TestAccountModels` - Account, Entity
- `TestTransactionModels` - Transaction, JournalEntry
-TestBillingModels` - Bill, Invoice, Document
- `TestTaxModels` - TaxNexus, FinancialClose
- `TestBudgetModels` - Budget, CategorizationRule, CategorizationProposal

**Coverage Target:** 80%+ for 12 accounting models

### Phase 3: Sales & Service Models (Plans 05-06)

**Focus:** CRM and project management models.

**File: `tests/database/test_sales_models.py`**

**Test Classes:**
- `TestLeadModels` - Lead
- `TestDealModels` - Deal, CommissionEntry
- `TestCommunicationModels` - CallTranscript, FollowUpTask

**File: `tests/database/test_service_models.py`**

**Test Classes:**
- `TestContractModels` - Contract
- `TestProjectModels` - Project, Milestone, ProjectTask
- `TestAppointmentModels` - Appointment

**Coverage Target:** 80%+ for 11 models

### Phase 4: Relationship & Constraint Tests (Plan 07)

**Focus:** Cross-cutting relationship and constraint testing.

**File: `tests/database/test_relationships.py`**

**Test Classes:**
- `TestOneToManyRelationships` - All 1:N relationships
- `TestManyToManyRelationships` - All M:N relationships
- `TestSelfReferentialRelationships` - Parent/child relationships
- `TestPolymorphicRelationships` - Optional FK relationships

**File: `tests/database/test_constraints.py`**

**Test Classes:**
- `TestUniqueConstraints` - Email, external_id uniqueness
- `TestNotNullConstraints` - Required field validation
- `TestForeignKeyConstraints` - FK reference validation
- `TestCheckConstraints` - Enum value validation
- `TestIndexConstraints` - Index creation and usage

**Coverage Target:** 90%+ for all constraint types

### Phase 5: Cascade & Transaction Tests (Plan 08)

**Focus:** Cascade delete and transaction rollback testing.

**File: `tests/database/test_cascades.py`**

**Test Classes:**
- `TestCascadeDelete` - All cascade delete behaviors
- `TestCascadeNullify` - Nullify cascade behaviors
- `TestManualCascade` - Models requiring manual cleanup
- `TestCascadePerformance` - Cascade performance with large datasets

**File: `tests/database/test_transactions.py`**

**Test Classes:**
- `TestTransactionRollback` - Rollback on error
- `TestTransactionCommit` - Commit behavior
- `TestTransactionIsolation` - Session isolation between tests
- `TestTransactionPerformance` - Transaction overhead

**Coverage Target:** 85%+ for all cascade behaviors

## Best Practices for Database Testing

### Session Management

**DO:** Use function-scoped db_session fixture
```python
def test_model_crud(db_session):  # Function scope
    model = MyModelFactory(_session=db_session)
    db_session.commit()
    # Session auto-closed after test
```

**DON'T:** Use class-scoped sessions
```python
@pytest.fixture(scope="class")  # BAD: causes pollution
def db_session():
    # ...
```

### Factory Usage

**DO:** Use factories for consistent test data
```python
agent = AgentFactory(
    name="TestAgent",
    status=AgentStatus.STUDENT.value,
    _session=db_session
)
```

**DON'T:** Manually instantiate models
```python
agent = AgentRegistry(  # BAD: inconsistent with other tests
    id=str(uuid.uuid4()),
    name="TestAgent",
    status="student",
    created_at=datetime.utcnow()
)
```

### Test Isolation

**DO:** Create fresh data per test
```python
def test_agent_query(db_session):
    agent = AgentFactory(_session=db_session)  # Fresh data
    results = db_session.query(AgentRegistry).all()
    assert len(results) == 1
```

**DON'T:** Share data across tests
```python
@pytest.fixture(scope="module")  # BAD: shared state
def sample_agent(db_session):
    return AgentFactory(_session=db_session)
```

### Relationship Testing

**DO:** Test relationships in both directions
```python
def test_bidirectional_relationship(db_session):
    agent = AgentFactory(_session=db_session)
    execution = AgentExecutionFactory(agent_id=agent.id, _session=db_session)
    db_session.commit()

    # Forward direction
    assert execution.agent.id == agent.id
    # Reverse direction
    assert execution in agent.executions
```

**DON'T:** Test only one direction
```python
def test_unidirectional_relationship(db_session):  # INCOMPLETE
    agent = AgentFactory(_session=db_session)
    execution = AgentExecutionFactory(agent_id=agent.id, _session=db_session)
    assert execution.agent.id == agent.id
    # Missing reverse direction test!
```

### Cascade Testing

**DO:** Verify cascade behavior explicitly
```python
def test_cascade_delete(db_session):
    agent = AgentFactory(_session=db_session)
    execution = AgentExecutionFactory(agent_id=agent.id, _session=db_session)
    db_session.commit()

    db_session.delete(agent)
    db_session.commit()

    # Verify execution was deleted
    remaining = db_session.query(AgentExecution).filter(
        AgentExecution.agent_id == agent.id
    ).first()
    assert remaining is None  # Explicitly verified
```

**DON'T:** Assume cascade works
```python
def test_cascade_delete(db_session):  # WEAK TEST
    agent = AgentFactory(_session=db_session)
    db_session.delete(agent)
    db_session.commit()
    # No verification - doesn't prove cascade worked!
```

### Error Testing

**DO:** Use pytest.raises for expected errors
```python
def test_unique_constraint(db_session):
    UserFactory(email="test@example.com", _session=db_session)
    db_session.commit()

    with pytest.raises(IntegrityError):
        UserFactory(email="test@example.com", _session=db_session)
        db_session.commit()
```

**DON'T:** Manually catch exceptions
```python
def test_unique_constraint(db_session):  # VERBOSE
    UserFactory(email="test@example.com", _session=db_session)
    db_session.commit()

    try:
        UserFactory(email="test@example.com", _session=db_session)
        db_session.commit()
        assert False, "Should have raised IntegrityError"
    except IntegrityError:
        pass  # Expected
```

## Open Questions

1. **Database-specific cascade testing**
   - What we know: SQLite doesn't enforce FK constraints by default
   - What's unclear: Should we test with PostgreSQL in CI for FK constraint validation?
   - Recommendation: Start with SQLite + FK pragma enabled, add PostgreSQL tests in CI if FK issues arise

2. **Large model count (235 models)**
   - What we know: Too many models for single test file
   - What's unclear: How to organize tests for maintainability?
   - Recommendation: Use module-based organization (test_core_models.py, test_accounting_models.py, etc.)

3. **Performance testing for cascades**
   - What we know: Some models have 1000+ related records
   - What's unclear: Should we test cascade performance with large datasets?
   - Recommendation: Skip performance testing in Phase 168, defer to performance testing phase

4. **Factory coverage for new models**
   - What we know: Factories exist for ~15% of models
   - What's unclear: Should we create factories for all 235 models?
   - Recommendation: Create factories only for models tested in each plan, don't pre-build all factories

5. **Relationship testing depth**
   - What we know: Models have 5-10 relationships each
   - What's unclear: Should we test every relationship combination?
   - Recommendation: Test representative relationships (1-2 per type), not every permutation

## Sources

### Primary (HIGH confidence)
- SQLAlchemy 2.0 Documentation - https://docs.sqlalchemy.org/en/20/orm/quickstart.html
- pytest Documentation - https://docs.pytest.org/en/7.4.x/
- factory_boy Documentation - https://factoryboy.readthedocs.io/
- Existing test patterns in `tests/database/test_database_models.py` (1,370 lines)
- Existing test patterns in `tests/test_models_coverage.py` (1,548 lines)

### Secondary (MEDIUM confidence)
- SQLite Foreign Key Support - https://www.sqlite.org/foreignkeys.html
- Faker Documentation - https://faker.readthedocs.io/
- freezegun Documentation - https://github.com/spulec/freezegun

### Tertiary (LOW confidence)
- Database testing best practices (general knowledge, needs verification)
- SQLAlchemy performance patterns (from training data, verify with official docs)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries are industry standards with official documentation
- Architecture: HIGH - Based on existing patterns in codebase with proven success
- Pitfalls: HIGH - Identified from actual test failures in existing test suite
- Model inventory: HIGH - Generated programmatically from actual model files

**Research date:** March 11, 2026
**Valid until:** April 10, 2026 (30 days - stable domain, library versions unlikely to change)

**Key findings requiring validation:**
1. Exact model count per module (verified programmatically: 235 models total)
2. Existing factory coverage (verified: 13 factory files for ~35 models)
3. Cascade configurations (needs manual verification per model)
4. FK constraint enablement in SQLite tests (verify in conftest.py)
