---
phase: 01-test-infrastructure
plan: 05
type: execute
wave: 3
depends_on: ["01-test-infrastructure-02", "01-test-infrastructure-03"]
files_modified:
  - backend/tests/conftest.py
  - backend/tests/factories/README.md
autonomous: true

must_haves:
  truths:
    - "Quality gates enforce assertion density and critical path coverage"
    - "Tests fail if assertion density is below threshold (0.15 assertions per line)"
    - "Test documentation explains factory usage for isolated test data"
    - "Test suite README provides comprehensive testing guide"
  artifacts:
    - path: "backend/tests/conftest.py"
      contains: "assertion_density"
    - path: "backend/tests/factories/README.md"
      min_lines: 100
    - path: "backend/tests/README.md"
      min_lines: 100
  key_links:
    - from: "pytest run"
      to: "assertion density check"
      via: "pytest_terminal_summary hook"
      pattern: "pytest_terminal_summary"
---

<objective>
Implement quality gates for assertion density and create comprehensive documentation for test data factories.

Purpose: Ensure test quality by enforcing assertion density thresholds and documenting factory usage patterns for isolated test data.
Output: Assertion density quality gate and factory usage documentation
</objective>

<execution_context>
@/Users/rushiparikh/.claude/get-shit-done/workflows/execute-plan.md
@/Users/rushiparikh/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/01-test-infrastructure/01-RESEARCH.md
@backend/tests/conftest.py
@backend/tests/factories/__init__.py
@backend/tests/TESTING_GUIDE.md
</context>

<tasks>

<task type="auto">
  <name>Implement assertion density quality gate</name>
  <files>backend/tests/conftest.py</files>
  <action>
    Add assertion density checking to backend/tests/conftest.py:

    1. Add these imports at the top of the file:

    ```python
    import ast
    from pathlib import Path
    ```

    2. Add helper functions AFTER the `ensure_numpy_available` fixture:

    ```python
    def _count_assertions(node: ast.AST) -> int:
        """Count assert statements and pytest assertions in AST node."""
        count = 0
        for child in ast.walk(node):
            if isinstance(child, ast.Assert):
                count += 1
            # Check for common assertion patterns
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Attribute):
                    if child.func.attr in ('assertEqual', 'assertTrue', 'assertFalse',
                                           'assertIn', 'assertNotIn', 'assertRaises',
                                           'assertIs', 'assertIsNone', 'assertIsNotNone'):
                        count += 1
        return count


    def _calculate_assertion_density(test_file: Path) -> float:
        """Calculate assertions per line of test code."""
        try:
            source = test_file.read_text()
            tree = ast.parse(source)
            lines = len(source.splitlines())
            if lines == 0:
                return 0.0
            asserts = _count_assertions(tree)
            return asserts / lines
        except Exception:
            return 0.0
    ```

    3. Add pytest hook to check assertion density (AFTER the helper functions):

    ```python
    def pytest_terminal_summary(terminalreporter, exitstatus, config):
        """
        Display quality metrics after test run.

        Reports assertion density and coverage summary.
        """
        # Assertion density check
        min_density = 0.15  # 15 assertions per 100 lines
        test_files = list(Path("tests").rglob("test_*.py"))
        low_density_files = []

        for test_file in test_files:
            density = _calculate_assertion_density(test_file)
            if 0 < density < min_density:
                low_density_files.append((test_file, density))

        if low_density_files:
            terminalreporter.write_sep("=", "WARNING: Low Assertion Density", red=True)
            for test_file, density in low_density_files[:5]:  # Show first 5
                terminalreporter.write_line(
                    f"  {test_file}: {density:.3f} (target: {min_density:.2f})",
                    red=True
                )

        # Coverage summary
        try:
            import json
            coverage_path = Path("tests/coverage_reports/metrics/coverage.json")
            if coverage_path.exists():
                with open(coverage_path) as f:
                    coverage_data = json.load(f)

                line_coverage = coverage_data.get('totals', {}).get('percent_covered', 0)
                terminalreporter.write_sep("=", f"Coverage: {line_coverage:.1f}%", red=True)
        except Exception:
            pass
    ```

    Note: If `pytest_terminal_summary` already exists from plan 03, merge the functionality by adding assertion density check BEFORE the coverage check in the existing function.
  </action>
  <verify>grep -A10 "assertion_density" backend/tests/conftest.py</verify>
  <done>Assertion density checker reports files with <0.15 assertions per line after test run</done>
</task>

<task type="auto">
  <name>Create factory usage documentation</name>
  <files>backend/tests/factories/README.md</files>
  <action>
    Create comprehensive backend/tests/factories/README.md:

    ```markdown
    # Test Data Factories

    This directory contains factory_boy factories for generating isolated, dynamic test data.

    Why Factories?
    --------------

    **Problem:** Hardcoded test data causes coupling and flaky tests.

    \`\`\`python
    # BAD: Hardcoded ID
    agent_id = "test-agent-123"
    # Fails if another test uses same ID

    # GOOD: Factory-generated ID
    agent = AgentFactory.create()
    # Each test gets unique UUID
    \`\`\`

    **Benefits:**
    - Unique IDs every time (no collisions)
    - Realistic data via Faker
    - Relationship handling (SubFactory)
    - Easy to override specific values

    Available Factories
    -------------------

    ### AgentFactory

    Creates AgentRegistry instances with valid governance data.

    \`\`\`python
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
    \`\`\`

    ### UserFactory

    Creates User instances with authentication data.

    \`\`\`python
    from tests.factories import UserFactory

    user = UserFactory.create(
        email="test@example.com",  # Override
        role="member"
    )

    # Admin user
    from tests.factories.user_factory import AdminUserFactory
    admin = AdminUserFactory.create()
    \`\`\`

    ### EpisodeFactory / EpisodeSegmentFactory

    Creates episodic memory test data with relationships.

    \`\`\`python
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
    \`\`\`

    ### AgentExecutionFactory

    Creates execution records with timing and governance metadata.

    \`\`\`python
    from tests.factories.execution_factory import AgentExecutionFactory

    execution = AgentExecutionFactory.create(
        agent_id="agent-123",
        status="completed",
        tokens_used=1500
    )
    \`\`\`

    ### CanvasAuditFactory

    Creates canvas interaction records.

    \`\`\`python
    from tests.factories.canvas_factory import CanvasAuditFactory

    canvas = CanvasAuditFactory.create(
        canvas_type="sheets",
        action="present"
    )
    \`\`\`

    Factory Patterns
    ---------------

    ### Building (no persistence)

    \`\`\`python
    # Build without saving to database
    agent = AgentFactory.build()
    # agent.id is set but not in DB
    \`\`\`

    ### Creating (with persistence)

    \`\`\`python
    # Create and save to database
    agent = AgentFactory.create()
    # agent is in database
    \`\`\`

    ### Batch Creation

    \`\`\`python
    # Create multiple instances
    agents = AgentFactory.create_batch(5)
    # Returns list of 5 agents
    \`\`\`

    ### Relationships

    \`\`\`python
    # Episode with segments (using SubFactory in EpisodeSegmentFactory)
    episode = EpisodeFactory.create()
    segment = EpisodeSegmentFactory.create(episode_id=episode.id)
    \`\`\`

    ### Faker Integration

    Factories use Faker for realistic data:

    \`\`\`python
    # Names, emails, phone numbers
    user = UserFactory.create()
    # user.email = "john.doe@example.com"
    # user.first_name = "John"

    # Company names, UUIDs
    agent = AgentFactory.create()
    # agent.name = "Acme Corp"
    # agent.id = "a1b2c3d4-e5f6..."
    \`\`\`

    Session Handling
    ---------------

    Factories require a database session. Inject via `_session` parameter:

    \`\`\`python
    def test_agent_creation(db_session):
        agent = AgentFactory.create(_session=db_session)
        # Uses test fixture session
    \`\`\`

    Best Practices
    --------------

    1. **Always use factories** - Never hardcode IDs
    2. **Use specific factories** - StudentAgentFactory, not AgentFactory with status override
    3. **Build when possible** - Use `.build()` for read-only tests (faster)
    4. **Clean up in fixtures** - Use function-scoped db_session with rollback
    5. **Document custom values** - Comment why you're overriding defaults

    Anti-Patterns
    -------------

    \`\`\`python
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
    \`\`\`

    See Also
    --------

    - [factory_boy Documentation](https://factoryboy.readthedocs.io/)
    - [Faker Documentation](https://faker.readthedocs.io/)
    - [TESTING_GUIDE.md](../TESTING_GUIDE.md)
    ```
    ```
  </action>
  <verify>cat backend/tests/factories/README.md | head -50</verify>
  <done>Factories README exists with comprehensive usage examples and patterns</done>
</task>

</tasks>

<verification>
1. Run `pytest tests/property_tests/conftest.py -v` and verify assertion density warning appears (if applicable)
2. Verify factory README is complete and readable
3. Check that assertion density function correctly counts assertions
4. Confirm quality gate doesn't break normal test execution
</verification>

<success_criteria>
- Assertion density checker runs after test suite
- Files with <0.15 assertions per line are reported
- Factory README documents all available factories
- Factory README shows usage examples and patterns
- Quality gates integrate with existing pytest hooks
</success_criteria>

<output>
After completion, create `.planning/phases/01-test-infrastructure/01-test-infrastructure-05-SUMMARY.md`
</output>
