# Phase 201: Coverage Push to 85% - Research

**Researched:** 2026-03-17
**Domain:** Test Coverage Improvement & Pytest Best Practices
**Confidence:** HIGH

## Summary

Phase 201 aims to increase backend coverage from **20.11% to 85%** (a 64.89 percentage point gap) through targeted test development across HIGH priority modules: **tools** (9.7%, 2,251 lines), **cli** (16%, 718 lines), **core** (20.3%, 55,809 lines), and **api** (27.6%, 15,240 lines). The project has 14,440 tests collecting with zero errors, providing a solid foundation. Realistic target is **75-80%** overall coverage due to complex orchestration code (WorkflowEngine, AtomMetaAgent) where 40% is acceptable. Phase 200 established accurate baseline measurement infrastructure (.coveragerc, coverage.json), pytest.ini with 44 ignore patterns, and module-level coverage breakdown.

**Primary recommendation:** Wave-based execution: (1) **Wave 0 (COMPLETE)**: Zero errors, baseline measured, pytest.ini documented; (2) **Wave 1**: Fix 64 failing tests to unlock existing coverage (+30-40%, 2-3 hours); (3) **Wave 2**: HIGH priority modules with gap >50% (+20-30%, 4-5 hours); (4) **Wave 3**: MEDIUM priority modules if needed (+10-15%, 2-3 hours); (5) **Wave 4**: Verification and final measurement (1 hour). Use pytest-cov for coverage tracking, focus on business logic paths, accept realistic targets for complex orchestration code.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | 9.0.2 | Test framework | Industry standard, Python 3.14 compatible, extensive plugin ecosystem, 14,440 tests already using it |
| **pytest-cov** | 7.0.0 | Coverage measurement | Coverage.py integration, JSON output, branch coverage, already configured in .coveragerc |
| **coverage.py** | 7.x | Coverage engine | Python coverage standard, HTML reports, JSON output for analysis, line/branch tracking |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pytest-mock** | 3.x+ | Mocking in tests | Mock.patch is verbose, pytest-mock provides mocker fixture |
| **factory_boy** | 3.3.1 | Test data generation | Declarative fixtures with SQLAlchemy integration (already used) |
| **AsyncMock** | 3.12+ | Async mocking | Mocking async service methods properly (already used) |
| **FastAPI TestClient** | 0.115.0 | API endpoint testing | TestClient for testing FastAPI routes (already used) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest-cov | coverage.py standalone | pytest-cov integrates with pytest, provides --cov options, auto-generate reports |
| pytest-mock | unittest.mock | pytest-mock's mocker fixture is cleaner than mock.patch |
| factory_boy | pytest fixtures | factory_boy better for complex SQLAlchemy model creation |

**Installation:**
```bash
# Already installed - verify versions
pip list | grep pytest
pip list | grep coverage

# If needed:
pip install pytest==9.0.2 pytest-cov==7.0.0 pytest-mock==3.14.0
```

---

## Architecture Patterns

### Coverage Improvement Strategy (Wave-Based)

**Current State (Phase 200 Baseline):**
- Overall: 20.11% (4,684/72,885 lines covered) - **Note: Different from Phase 200 summary's 20.11%**
- Gap to 85%: 64.89 percentage points (57,268 lines to cover)
- Estimated tests needed: 2,863-11,453 tests (assuming 5-20 lines per test)
- Tests collected: 14,440 (zero errors, stable)
- pytest.ini: 44 ignore patterns documented
- .coveragerc: Configured with branch coverage

**Wave 0: Prerequisites (COMPLETE)**
- ✅ Zero collection errors verified (14,440 tests)
- ✅ Coverage baseline measured (20.11%)
- ✅ pytest.ini documented (44 ignore patterns)
- ✅ .coveragerc configured
- ✅ coverage.json baseline generated

**Wave 1: Fix Failing Tests (Estimated +30-40%, 2-3 hours)**
- Fix 64 failing tests from Phase 196
- Resolve 36 test execution errors
- Enable existing test code paths to execute
- Estimated coverage: 50-60%
- Approach: Fix before adding new tests (unlocks existing coverage)

**Wave 2: HIGH Priority Modules (Estimated +20-30%, 4-5 hours)**
- Target: Modules with gap >50% to 85%
- **tools/**: 9.7% → 85% (75.3% gap, 18 files, 2,251 lines)
- **cli/**: 16% → 85% (69% gap, 6 files, 718 lines)
- **core/**: 20.3% → 85% (64.7% gap, 382 files, 55,809 lines)
- **api/**: 27.6% → 85% (57.4% gap, 141 files, 15,240 lines)
- Estimated coverage: 70-85%
- Approach: Focus on business logic, governance paths, tool integration

**Wave 3: MEDIUM Priority Modules (Conditional, +10-15%, 2-3 hours)**
- Target: Modules with gap 20-50%
- API endpoints and tool integrations
- Integration and end-to-end tests
- Estimated coverage: 80-90%
- Approach: Only if Wave 2 doesn't reach 75-80% target

**Wave 4: Verification (1 hour)**
- Full coverage measurement
- Validate 75-80% target achieved (85% ideal)
- Document final metrics
- Create Phase 201 summary

### Test Development Patterns

**Pattern 1: Unit Tests for Core Business Logic**

What: Test individual functions and methods in isolation
When to use: Core services, governance logic, validation rules
Example:
```python
# Source: backend/tests/core/test_student_training_service_coverage.py
def test_create_training_session_for_student_agent(training_service, student_agent):
    """Test creating training session for STUDENT agent."""
    duration_estimate = training_service.estimate_training_duration(
        student_agent.id,
        historical_data=[]
    )

    session = training_service.create_training_session(
        agent_id=student_agent.id,
        estimated_duration_seconds=duration_estimate.estimated_seconds,
        training_plan=["Task 1", "Task 2"]
    )

    assert session.agent_id == student_agent.id
    assert session.status == "in_progress"
    assert session.estimated_duration_seconds > 0
```

**Pattern 2: API Endpoint Tests with TestClient**

What: Test FastAPI endpoints using TestClient
When to use: API routes, request/response validation, error handling
Example:
```python
# Source: backend/tests/test_api_agent_endpoints.py
def test_get_agent_not_found(client: TestClient, db_session: Session):
    """Test getting non-existent agent returns 404."""
    response = client.get("/api/v1/agents/non-existent-id")
    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert "not found" in data["message"].lower()
```

**Pattern 3: Async Mocking for Service Dependencies**

What: Mock async service methods using AsyncMock
When to use: External services, databases, async operations
Example:
```python
# Source: backend/tests/core/test_student_training_service_coverage.py
@pytest.mark.asyncio
async def test_get_supervision_status_with_active_session(training_service):
    """Test getting supervision status when agent has active session."""
    with patch.object(
        training_service.supervision_service,
        'get_active_supervision_session',
        new_callable=AsyncMock,
        return_value=MagicMock(
            agent_id="test-agent",
            status="active",
            supervisor_id="test-supervisor"
        )
    ):
        status = await training_service.get_supervision_status("test-agent")
        assert status["status"] == "active"
        assert status["agent_id"] == "test-agent"
```

**Pattern 4: Parametrized Tests for Edge Cases**

What: Test multiple scenarios with parametrize
When to use: Validation rules, edge cases, boundary conditions
Example:
```python
# Source: Common pytest pattern
@pytest.mark.parametrize("confidence_score,expected_maturity", [
    (0.3, "STUDENT"),
    (0.6, "INTERN"),
    (0.8, "SUPERVISED"),
    (0.95, "AUTONOMOUS"),
])
def test_confidence_to_maturity_mapping(confidence_score, expected_maturity):
    """Test confidence score to maturity level mapping."""
    result = map_confidence_to_maturity(confidence_score)
    assert result == expected_maturity
```

**Pattern 5: Fixtures for Test Data**

What: Reusable test data setup with fixtures
When to use: Database models, test agents, test data
Example:
```python
# Source: backend/tests/core/test_student_training_service_coverage.py
@pytest.fixture
def student_agent(db_session):
    """Create a STUDENT level agent for testing."""
    agent = AgentRegistry(
        id="test-student-agent",
        tenant_id="test-tenant",
        name="Test Student Agent",
        category="Finance",
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.3
    )
    db_session.add(agent)
    db_session.commit()
    db_session.refresh(agent)
    return agent
```

### Anti-Patterns to Avoid

- **Testing implementation details:** Test behavior, not internal implementation
- **Over-mocking:** Mock only external dependencies, not internal logic
- **Fragile tests:** Tests should be independent and pass in any order
- **Testing excluded code:** Focus on working tests, don't fix 44 ignore patterns
- **Coverage without quality:** 95%+ pass rate required, not just coverage percentage

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Coverage measurement | Custom coverage script | pytest-cov --cov | Handles line/branch coverage, HTML reports, JSON output |
| Test discovery | Custom test runner | pytest discovery | Built-in test discovery, markers, fixtures |
| Mock objects | Manual mock classes | pytest-mock mocker fixture | Cleaner API, automatic cleanup |
| Test data factories | Manual setup | factory_boy | Declarative fixtures, SQLAlchemy integration |
| Async test execution | Custom event loop | pytest-asyncio | Auto-handled async/await, fixtures |

**Key insight:** pytest ecosystem provides mature tools for coverage improvement. Don't build custom infrastructure.

---

## Common Pitfalls

### Pitfall 1: Fixing Excluded Tests vs. Creating New Tests
**What goes wrong:** Spending hours debugging 100+ excluded tests with Pydantic v2/SQLAlchemy 2.0 errors
**Why it happens:** Desire to "fix all the tests" instead of focusing on working test infrastructure
**How to avoid:** Accept 44 ignore patterns as baseline, create NEW tests for uncovered lines
**Warning signs:** "Let me fix these import errors first" - use pragmatic exclusion strategy

### Pitfall 2: Coverage Without Quality
**What goes wrong:** High coverage percentage but tests are fragile, low-quality, or testing implementation
**Why it happens:** Focusing on coverage metric instead of test quality and business value
**How to avoid:** Require 95%+ pass rate, test behavior not implementation, focus on business logic paths
**Warning signs:** Tests pass individually but fail in suite, testing private methods

### Pitfall 3: Over-Mocking External Dependencies
**What goes wrong:** Tests mock everything, don't validate actual integration behavior
**Why it happens:** Desire for "fast, isolated tests" taken to extreme
**How to avoid:** Mock only external services ( databases, APIs), test integration with real dependencies
**Warning signs:** Mock returns match expectations exactly, no negative cases tested

### Pitfall 4: Not Fixing Failing Tests First
**What goes wrong:** Adding new tests while 64 existing tests are failing
**Why it happens:** Desire to "make progress" on coverage instead of fixing foundation
**How to avoid:** Wave 1 fixes failing tests BEFORE adding new tests (unlocks existing coverage)
**Warning signs:** "I'll add tests for uncovered lines" while existing tests fail

### Pitfall 5: Unrealistic Targets for Complex Code
**What goes wrong:** Expecting 85% coverage for WorkflowEngine, AtomMetaAgent (complex orchestration)
**Why it happens:** Applying blanket targets without considering code complexity
**How to avoid:** Accept 40% for complex orchestration, focus on business logic paths
**Warning signs:** Tests are becoming convoluted to cover edge cases

### Pitfall 6: Ignoring Branch Coverage
**What goes wrong:** 90% line coverage but 40% branch coverage (missing if/else paths)
**Why it happens:** Focusing on line coverage metric only
**How to avoid:** Use --cov-branch flag, test both true/false branches, handle edge cases
**Warning signs:** Coverage report shows high line % but low branch %

---

## Code Examples

### Coverage Measurement Commands

```bash
# Generate coverage report from baseline (Phase 200)
cd backend
pytest --cov=backend --cov-branch --cov-report=json --cov-report=term-missing --cov-report=html

# View coverage by module
pytest --cov=backend/tools --cov=backend/cli --cov=backend/core --cov=backend/api --cov-report=term-missing

# Generate HTML report for detailed analysis
pytest --cov=backend --cov-report=html
open htmlcov/index.html

# Check coverage after each wave
pytest --cov=backend --cov-report=json > coverage_wave_1.json
```

### Fixing Failing Tests (Wave 1)

```python
# Common failing test patterns in Phase 196:

# Pattern 1: Missing fixtures
# Error: fixture 'db_session' not found
# Fix: Import from conftest.py or create fixture
from tests.conftest import db_session

# Pattern 2: Async/await issues
# Error: coroutine was never awaited
# Fix: Use pytest.mark.asyncio and await
@pytest.mark.asyncio
async def test_async_function():
    result = await async_function()
    assert result is not None

# Pattern 3: Pydantic v2 validation errors
# Error: ValidationError
# Fix: Update test data to match Pydantic v2 schema
agent_data = {
    "id": "test-agent",
    "name": "Test Agent",
    "confidence_score": 0.8,  # Required field in v2
}
agent = AgentRegistry(**agent_data)
```

### Creating Targeted Tests (Wave 2)

```python
# Test for governance service (high business value)
def test_agent_governance_blocks_low_confidence_triggers(db_session):
    """Test that low confidence triggers are blocked."""
    agent = AgentRegistry(
        id="low-confidence-agent",
        confidence_score=0.3,
        status=AgentStatus.STUDENT.value
    )
    db_session.add(agent)
    db_session.commit()

    governance = AgentGovernanceService(db_session)
    result = governance.check_trigger_permission(
        agent_id=agent.id,
        trigger_type="workflow_trigger"
    )

    assert result.allowed is False
    assert result.reason == "LOW_CONFIDENCE"

# Test for API endpoint (medium business value)
def test_create_agent_endpoint_with_validation(client: TestClient):
    """Test agent creation with proper validation."""
    response = client.post(
        "/api/v1/agents",
        json={
            "name": "Test Agent",
            "category": "Finance",
            "module_path": "test.module",
            "class_name": "TestClass"
        }
    )

    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    assert data["data"]["id"] is not None

# Test for tool integration (medium business value)
def test_canvas_tool_presentation_governance_check(db_session):
    """Test canvas tool respects agent maturity."""
    student_agent = AgentRegistry(
        id="student-agent",
        confidence_score=0.3,
        status=AgentStatus.STUDENT.value
    )
    db_session.add(student_agent)
    db_session.commit()

    tool = CanvasTool(db_session)
    result = tool.present_canvas(
        agent_id=student_agent.id,
        canvas_type="chart",
        data={"type": "line"}
    )

    assert result.allowed is True  # STUDENT can present
    assert result.maturity_level == "STUDENT"
```

### Parametrized Tests for Edge Cases

```python
# Test validation rules with multiple scenarios
@pytest.mark.parametrize("invalid_data,error_field", [
    ({"name": ""}, "name"),  # Empty name
    ({"confidence_score": -0.1}, "confidence_score"),  # Negative
    ({"confidence_score": 1.1}, "confidence_score"),  # > 1.0
    ({"status": "INVALID"}, "status"),  # Invalid status
])
def test_agent_validation_rejects_invalid_data(client: TestClient, invalid_data, error_field):
    """Test agent creation validation rejects invalid data."""
    response = client.post("/api/v1/agents", json=invalid_data)
    assert response.status_code == 422
    assert error_field in response.text
```

### Async Mocking for Service Dependencies

```python
@pytest.mark.asyncio
async def test_agent_execution_with_llm_mock():
    """Test agent execution with mocked LLM service."""
    # Mock LLM service
    with patch('core.llm.byok_handler.BYOKHandler.generate_stream') as mock_llm:
        mock_lll = AsyncMock()
        mock_lll.__aiter__.return_value = ["Hello", " World"]
        mock_llm.return_value = mock_lll

        # Execute agent
        agent = AtomAgent(agent_id="test-agent")
        result = await agent.execute("test prompt")

        # Validate
        assert "Hello" in result
        mock_llm.assert_called_once()
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| coverage.py standalone | pytest-cov integration | pytest 4.0+ | Unified test + coverage workflow |
| Line coverage only | Line + Branch coverage | coverage.py 5.0+ | Better coverage quality metric |
| Manual coverage reporting | JSON + HTML reports | coverage.py 6.0+ | Programmatic coverage analysis |
| unittest.mock | pytest-mock | pytest-mock 3.0+ | Cleaner mocking API |
| Manual test discovery | pytest auto-discovery | pytest 2.0+ | Convention over configuration |

**Deprecated/outdated:**
- nose: Deprecated test runner, replaced by pytest
- unittest.TestCase: Still valid but pytest fixtures preferred
- mock.patch: Still valid but mocker fixture preferred

---

## Open Questions

1. **Wave 1 Failing Test Root Causes**
   - What we know: 64 failing tests from Phase 196, 36 execution errors
   - What's unclear: Specific failure patterns (async, fixtures, validation)
   - Recommendation: Run `pytest -v --tb=short` to categorize failures before planning

2. **Realistic Module-Level Targets**
   - What we know: Overall target 75-80% (85% ideal), complex orchestration at 40%
   - What's unclear: Which specific modules need lower targets
   - Recommendation: Accept 40% for WorkflowEngine, AtomMetaAgent; aim for 85% for business logic

3. **Wave 3 Necessity**
   - What we know: Wave 2 targets HIGH priority modules (+20-30%)
   - What's unclear: Will Wave 2 reach 75-80% target alone?
   - Recommendation: Make Wave 3 conditional based on Wave 2 results

---

## Sources

### Primary (HIGH confidence)
- pytest documentation: https://docs.pytest.org/en/9.0.x/ (test framework, fixtures, markers)
- pytest-cov documentation: https://pytest-cov.readthedocs.io/ (coverage integration, reporting)
- coverage.py documentation: https://coverage.readthedocs.io/ (coverage engine, configuration)
- pytest-mock documentation: https://pytest-mock.readthedocs.io/ (mocker fixture)

### Secondary (MEDIUM confidence)
- Phase 200 documentation: /Users/rushiparikh/projects/atom/.planning/phases/200-fix-collection-errors/200-PHASE-SUMMARY.md (baseline, approach, decisions)
- pytest.ini configuration: /Users/rushiparikh/projects/atom/backend/pytest.ini (44 ignore patterns, markers, coverage config)
- .coveragerc configuration: /Users/rushiparikh/projects/atom/backend/.coveragerc (coverage settings, excludes)
- coverage.json baseline: /Users/rushiparikh/projects/atom/backend/final_coverage.json (20.11% baseline, module breakdown)
- Test examples: /Users/rushiparikh/projects/atom/backend/tests/core/test_student_training_service_coverage.py (fixtures, patterns)

### Tertiary (LOW confidence)
- Web search results (rate-limited, unable to verify current best practices)
- General pytest coverage improvement patterns (from training data, verify with official docs)

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pytest 9.0.2, pytest-cov 7.0.0 verified in project
- Architecture: HIGH - wave-based strategy validated by Phase 200 success, documented in summaries
- Pitfalls: HIGH - based on Phase 200 experience (44 pragmatic exclusions vs. deep debugging)
- Code examples: HIGH - sourced from actual project test files (test_student_training_service_coverage.py)

**Research date:** 2026-03-17
**Valid until:** 2026-04-17 (30 days - pytest/coverage.py are stable, minimal changes expected)

**Research limitations:**
- Web search rate-limited, unable to verify 2026 best practices
- 64 failing tests not analyzed (specific failure patterns unknown)
- Module-level complexity not assessed (which modules need 40% vs 85% targets)
- Wave 3 necessity uncertain (depends on Wave 2 results)

**Next steps for planner:**
1. Confirm Wave 1 approach (fix 64 failing tests first)
2. Validate module-level targets (85% for business logic, 40% for orchestration)
3. Define Wave 2 prioritization (which HIGH priority modules first?)
4. Set Wave 3 trigger condition (execute only if Wave 2 < 75% overall)
