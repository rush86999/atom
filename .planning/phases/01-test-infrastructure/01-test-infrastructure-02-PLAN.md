---
phase: 01-test-infrastructure
plan: 02
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/tests/factories/__init__.py
  - backend/tests/factories/agent_factory.py
  - backend/tests/factories/user_factory.py
  - backend/tests/factories/episode_factory.py
  - backend/tests/factories/execution_factory.py
  - backend/tests/factories/canvas_factory.py
autonomous: true

must_haves:
  truths:
    - "Test suite creates isolated test data using factory_boy patterns with no hardcoded IDs"
    - "Developer can create test agents with `AgentFactory.create()` and get dynamic UUIDs"
    - "Test factories support relationships (Agent -> Executions -> Feedback)"
    - "Factories use Faker for realistic test data (names, emails, etc.)"
  artifacts:
    - path: "backend/tests/factories/__init__.py"
      provides: "BaseFactory with SQLAlchemy session"
    - path: "backend/tests/factories/agent_factory.py"
      provides: "AgentRegistry factory"
      exports: ["AgentFactory"]
    - path: "backend/tests/factories/user_factory.py"
      provides: "User factory"
      exports: ["UserFactory"]
    - path: "backend/tests/factories/episode_factory.py"
      provides: "Episode/EpisodeSegment factories"
      exports: ["EpisodeFactory", "EpisodeSegmentFactory"]
    - path: "backend/tests/factories/execution_factory.py"
      provides: "AgentExecution factory"
      exports: ["AgentExecutionFactory"]
    - path: "backend/tests/factories/canvas_factory.py"
      provides: "CanvasAudit factory"
      exports: ["CanvasAuditFactory"]
  key_links:
    - from: "AgentFactory"
      to: "core.models.AgentRegistry"
      via: "SQLAlchemyModelFactory"
      pattern: "class AgentFactory\\(.*SQLAlchemyModelFactory"
    - from: "factories"
      to: "database session"
      via: "BaseFactory sqlalchemy_session"
      pattern: "sqlalchemy_session_persistence = \"commit\""
---

<objective>
Create test data factories using factory_boy for all core models, eliminating hardcoded IDs and enabling isolated, dynamic test data generation.

Purpose: Replace hardcoded test IDs with dynamic factory-generated data, ensuring test isolation and preventing shared state issues.
Output: Factory classes for AgentRegistry, User, Episode, EpisodeSegment, AgentExecution, CanvasAudit
</objective>

<execution_context>
@/Users/rushiparikh/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/01-test-infrastructure/01-RESEARCH.md
@backend/core/models.py
@backend/tests/property_tests/conftest.py
@backend/requirements-testing.txt
</context>

<tasks>

<task type="auto">
  <name>Create base factory with SQLAlchemy session integration</name>
  <files>backend/tests/factories/__init__.py</files>
  <action>
    Create backend/tests/factories/__init__.py with BaseFactory:

    ```python
    """
    Test data factories for Atom platform.

    Uses factory_boy for dynamic, isolated test data generation.
    All factories inherit from BaseFactory which manages SQLAlchemy sessions.
    """

    import factory
    from factory.alchemy import SQLAlchemyModelFactory
    from sqlalchemy.orm import Session

    # Import at runtime to avoid import errors
    def get_session():
        from core.database import SessionLocal
        return SessionLocal()

    class BaseFactory(SQLAlchemyModelFactory):
        """
        Base factory for all test data factories.

        Uses a SQLAlchemy session for persistence.
        Each test gets a fresh session via dependency injection.
        """

        class Meta:
            abstract = True  # Don't create a model for BaseFactory
            sqlalchemy_session = None  # Set dynamically
            sqlalchemy_session_persistence = "commit"

        @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override to handle session injection."""
        session = kwargs.pop('_session', None)
        if session:
            # Use provided session (from test fixture)
            cls._meta.sqlalchemy_session = session
        else:
            # Use default session
            if cls._meta.sqlalchemy_session is None:
                cls._meta.sqlalchemy_session = get_session()
        return super()._create(model_class, *args, **kwargs)
    ```

    Ensure the directory exists: `backend/tests/factories/`
  </action>
  <verify>python -c "from tests.factories import BaseFactory; print('BaseFactory imported successfully')"</verify>
  <done>BaseFactory is importable and provides SQLAlchemy session management</done>
</task>

<task type="auto">
  <name>Create AgentFactory for AgentRegistry model</name>
  <files>backend/tests/factories/agent_factory.py</files>
  <action>
    Create backend/tests/factories/agent_factory.py:

    ```python
    """
    Factory for AgentRegistry model.
    """

    import factory
    from factory import fuzzy
    from tests.factories import BaseFactory
    from core.models import AgentRegistry, AgentStatus


    class AgentFactory(BaseFactory):
        """Factory for creating AgentRegistry instances."""

        class Meta:
            model = AgentRegistry

        # Required fields with dynamic values
        id = factory.Faker('uuid4')
        name = factory.Faker('company')
        category = factory.Iterator(['testing', 'automation', 'integration', 'workflow'])
        module_path = "test.module"
        class_name = "TestClass"

        # Status with fuzzy choice
        status = fuzzy.FuzzyChoice([s.value for s in AgentStatus])

        # Confidence score in valid range
        confidence = fuzzy.FuzzyFloat(0.0, 1.0)

        # Capabilities as list
        capabilities = factory.List([
            factory.Faker('word') for _ in range(3)
        ])

        # Optional fields
        description = factory.Faker('text', max_nb_chars=200)
        version = factory.Faker('numerify', text='#.##.##')
        created_at = factory.Faker('date_time_this_year')


    class StudentAgentFactory(AgentFactory):
        """Factory for STUDENT maturity agents."""

        status = AgentStatus.STUDENT.value
        confidence = fuzzy.FuzzyFloat(0.0, 0.5)


    class InternAgentFactory(AgentFactory):
        """Factory for INTERN maturity agents."""

        status = AgentStatus.INTERN.value
        confidence = fuzzy.FuzzyFloat(0.5, 0.7)


    class SupervisedAgentFactory(AgentFactory):
        """Factory for SUPERVISED maturity agents."""

        status = AgentStatus.SUPERVISED.value
        confidence = fuzzy.FuzzyFloat(0.7, 0.9)


    class AutonomousAgentFactory(AgentFactory):
        """Factory for AUTONOMOUS maturity agents."""

        status = AgentStatus.AUTONOMOUS.value
        confidence = fuzzy.FuzzyFloat(0.9, 1.0)
    ```

    Reference core/models.py AgentRegistry model for fields (lines ~447-470).
  </action>
  <verify>python -c "from tests.factories.agent_factory import AgentFactory; a = AgentFactory.build(); print(a.id, a.status)"</verify>
  <done>AgentFactory creates agents with dynamic UUIDs and valid field values</done>
</task>

<task type="auto">
  <name>Create UserFactory for User model</name>
  <files>backend/tests/factories/user_factory.py</files>
  <action>
    Create backend/tests/factories/user_factory.py:

    ```python
    """
    Factory for User model.
    """

    import factory
    from factory import fuzzy
    from tests.factories import BaseFactory
    from core.models import User, UserRole, UserStatus


    class UserFactory(BaseFactory):
        """Factory for creating User instances."""

        class Meta:
            model = User

        # Required fields
        id = factory.Faker('uuid4')
        email = factory.Faker('email')
        password_hash = factory.Faker('password')  # In tests, use fake hash
        first_name = factory.Faker('first_name')
        last_name = factory.Faker('last_name')

        # Role and status
        role = fuzzy.FuzzyChoice([r.value for r in UserRole])
        status = fuzzy.FuzzyChoice([s.value for s in UserStatus])

        # Optional fields
        phone = factory.Faker('phone_number')
        avatar_url = factory.Faker('image_url')
        created_at = factory.Faker('date_time_this_year')


    class AdminUserFactory(UserFactory):
        """Factory for admin users."""

        role = UserRole.SUPER_ADMIN.value


    class MemberUserFactory(UserFactory):
        """Factory for regular members."""

        role = UserRole.MEMBER.value
        status = UserStatus.ACTIVE.value
    ```

    Reference core/models.py User model for fields (lines ~194-230).
  </action>
  <verify>python -c "from tests.factories.user_factory import UserFactory; u = UserFactory.build(); print(u.email, u.role)"</verify>
  <done>UserFactory creates users with dynamic emails and valid roles</done>
</task>

<task type="auto">
  <name>Create Episode and EpisodeSegment factories</name>
  <files>backend/tests/factories/episode_factory.py</files>
  <action>
    Create backend/tests/factories/episode_factory.py:

    ```python
    """
    Factories for Episode and EpisodeSegment models.
    """

    import factory
    from factory import fuzzy
    from datetime import datetime, timedelta
    from tests.factories import BaseFactory
    from tests.factories.agent_factory import AgentFactory
    from core.models import Episode, EpisodeSegment, EpisodeType


    class EpisodeFactory(BaseFactory):
        """Factory for creating Episode instances."""

        class Meta:
            model = Episode

        # Required fields
        id = factory.Faker('uuid4')
        agent_id = factory.Faker('uuid4')
        title = factory.Faker('sentence', nb_words=4)
        summary = factory.Faker('text', max_nb_chars=500)

        # Episode metadata
        episode_type = fuzzy.FuzzyChoice([t.value for t in EpisodeType])
        maturity_at_start = fuzzy.FuzzyChoice(['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'])
        maturity_at_end = fuzzy.FuzzyChoice(['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'])

        # Timing
        started_at = factory.Faker('date_time_this_year')
        ended_at = factory.LazyAttribute(
            lambda o: o.started_at + timedelta(hours=fuzzy.FuzzyInteger(1, 24).fuzz())
        )

        # Intervention tracking
        intervention_count = fuzzy.FuzzyInteger(0, 10)
        constitutional_score = fuzzy.FuzzyFloat(0.0, 1.0)

        # Decay and lifecycle
        decay_factor = fuzzy.FuzzyFloat(0.0, 1.0)
        last_accessed_at = factory.LazyAttribute(lambda o: o.ended_at)
        access_count = fuzzy.FuzzyInteger(1, 100)

        # Consolidation
        is_consolidated = fuzzy.FuzzyChoice([True, False])
        consolidated_into_id = None


    class EpisodeSegmentFactory(BaseFactory):
        """Factory for creating EpisodeSegment instances."""

        class Meta:
            model = EpisodeSegment

        # Required fields
        id = factory.Faker('uuid4')
        episode_id = factory.Faker('uuid4')  # Link to episode
        segment_type = fuzzy.FuzzyChoice(['task', 'interaction', 'observation', 'outcome'])
        sequence_order = fuzzy.FuzzyInteger(0, 100)

        # Content
        content_summary = factory.Faker('text', max_nb_chars=300)
        metadata = factory.LambdaFunction(lambda: {})

        # Timing
        started_at = factory.Faker('date_time_this_year')
        ended_at = factory.LazyAttribute(
            lambda o: o.started_at + timedelta(minutes=fuzzy.FuzzyInteger(1, 60).fuzz())
        )

        # Context
        agent_maturity = fuzzy.FuzzyChoice(['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'])
        confidence_score = fuzzy.FuzzyFloat(0.0, 1.0)
    ```

    Reference core/models.py Episode/EpisodeSegment models.
  </action>
  <verify>python -c "from tests.factories.episode_factory import EpisodeFactory; e = EpisodeFactory.build(); print(e.id, e.title[:30])"</verify>
  <done>EpisodeFactory creates episodes with dynamic IDs and valid field values</done>
</task>

<task type="auto">
  <name>Create AgentExecution and CanvasAudit factories</name>
  <files>backend/tests/factories/execution_factory.py backend/tests/factories/canvas_factory.py</files>
  <action>
    Create two factory files:

    1. backend/tests/factories/execution_factory.py:

    ```python
    """
    Factory for AgentExecution model.
    """

    import factory
    from factory import fuzzy
    from datetime import datetime, timedelta
    from tests.factories import BaseFactory
    from core.models import AgentExecution, ExecutionStatus


    class AgentExecutionFactory(BaseFactory):
        """Factory for creating AgentExecution instances."""

        class Meta:
            model = AgentExecution

        # Required fields
        id = factory.Faker('uuid4')
        agent_id = factory.Faker('uuid4')
        user_request = factory.Faker('text', max_nb_chars=200)

        # Execution metadata
        status = fuzzy.FuzzyChoice([s.value for s in ExecutionStatus])
        trigger_source = fuzzy.FuzzyChoice(['manual', 'webhook', 'scheduled', 'api'])

        # Timing
        started_at = factory.Faker('date_time_this_year')
        completed_at = factory.LazyAttribute(
            lambda o: o.started_at + timedelta(seconds=fuzzy.FuzzyInteger(1, 300).fuzz())
            if o.status in ['completed', 'failed'] else None
        )

        # Results
        response_summary = factory.LazyAttribute(
            lambda o: factory.Faker('text', max_nb_chars=500).generate() if o.status == 'completed' else None
        )
        error_message = factory.LazyAttribute(
            lambda o: factory.Faker('sentence') if o.status == 'failed' else None
        )

        # Resource tracking
        tokens_used = fuzzy.FuzzyInteger(0, 10000)
        duration_ms = fuzzy.FuzzyInteger(100, 300000)

        # Governance
        maturity_at_execution = fuzzy.FuzzyChoice(['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'])
        supervision_session_id = None
    ```

    2. backend/tests/factories/canvas_factory.py:

    ```python
    """
    Factory for CanvasAudit model.
    """

    import factory
    from factory import fuzzy
    from tests.factories import BaseFactory
    from core.models import CanvasAudit


    class CanvasAuditFactory(BaseFactory):
        """Factory for creating CanvasAudit instances."""

        class Meta:
            model = CanvasAudit

        # Required fields
        id = factory.Faker('uuid4')
        agent_id = factory.Faker('uuid4')
        canvas_type = fuzzy.FuzzyChoice(['generic', 'docs', 'email', 'sheets', 'orchestration', 'terminal', 'coding'])

        # Action
        action = fuzzy.FuzzyChoice(['present', 'submit', 'close', 'update', 'execute'])

        # Content
        canvas_data = factory.LambdaFunction(lambda: {
            "title": factory.Faker('sentence').generate(),
            "components": []
        })

        # User interaction
        user_id = factory.Faker('uuid4')
        interaction_summary = factory.Faker('text', max_nb_chars=300)

        # Timing
        presented_at = factory.Faker('date_time_this_year')
        closed_at = factory.LazyAttribute(
            lambda o: o.presented_at + timedelta(seconds=fuzzy.FuzzyInteger(5, 300).fuzz())
        )

        # Results
        result_status = fuzzy.FuzzyChoice(['success', 'cancelled', 'error'])
        error_details = None
    ```
  </action>
  <verify>
    python -c "from tests.factories.execution_factory import AgentExecutionFactory; from tests.factories.canvas_factory import CanvasAuditFactory; print('Factories imported')"
  </verify>
  <done>AgentExecutionFactory and CanvasAuditFactory create valid test data</done>
</task>

</tasks>

<verification>
1. Run `python -c "from tests.factories import AgentFactory, UserFactory; print('Factories imported successfully')"`
2. Run `pytest tests/property_tests/conftest.py -v -k test_agent` to verify factories work with existing tests
3. Verify factory-generated objects have unique UUIDs (no hardcoded IDs)
4. Test relationship factories: Agent with Executions, Episode with Segments
</verification>

<success_criteria>
- All 6 factory files created with proper inheritance from BaseFactory
- Factories generate dynamic UUIDs (no hardcoded IDs)
- Factories use Faker for realistic data
- Factories can be imported and used in tests
- Relationship factories work correctly (SubFactory pattern)
</success_criteria>

<output>
After completion, create `.planning/phases/01-test-infrastructure/01-test-infrastructure-02-SUMMARY.md`
</output>
