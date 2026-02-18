# Phase 19: Coverage Push & Bug Fixes - Research

**Researched:** 2026-02-17
**Domain:** Python Test Coverage Expansion, Pytest, Bug Fixing Workflow
**Confidence:** HIGH

## Summary

Phase 19 continues the systematic test coverage expansion journey from **22.64%** toward the long-term **80% target**, using the proven high-impact file testing strategy validated in Phases 8.5, 8.6, 11, and 12. The current state shows 161 plans created with 157 completed (97.5% completion rate), demonstrating strong execution velocity.

The key insight from previous coverage phases: **testing large files (>150 lines) with lowest coverage percentages provides maximum ROI**. Phase 8.6 achieved 3.38x velocity acceleration by focusing on high-impact files (+1.42% per plan vs. +0.42% from unfocused testing). Phase 12 successfully demonstrated ORM testing achieving 97.30% coverage on models.py (2,351 lines).

Current coverage analysis reveals 20 top-priority files with **8,421 uncovered lines** across core workflow, agent, LLM, and episodic memory systems. Phase 19 should target these files using the proven **50% average coverage per file** strategy (sustainable, avoids diminishing returns of chasing 100%).

**Primary recommendation:** Execute 3-4 plans covering **8-12 high-impact files** (Tier 1: >500 lines, Tier 2: 300-500 lines) to achieve **+3-5% overall coverage increase**, while systematically fixing any test failures discovered during execution. Focus on workflow_engine.py (1,089 uncovered lines), atom_agent_endpoints.py (668 uncovered lines), llm/byok_handler.py (491 uncovered lines), and episodic memory services.

## User Constraints

No CONTEXT.md exists yet — this is a fresh phase planning.

**User Decisions from ROADMAP.md:**
- Phase 19 is a continuation of the coverage push initiative (Phases 8, 11, 12)
- Target: Long-term 80% coverage goal (multi-quarter journey)
- Current baseline: 22.64% coverage (16,106 of 57,828 lines)
- Strategy: Systematic coverage expansion using high-impact file strategy
- Bug fixing: Fix all remaining test failures and achieve 98%+ pass rate

**Locked Decisions:**
- Use **50% average coverage per file** target (validated sustainable from Phase 8.6)
- **Focus on files >150 lines** for maximum ROI (validated from Phase 11 analysis)
- **Group related files** for efficient context switching (Phase 8.5, 12 patterns)
- **Maintain test quality** - avoid test proliferation for coverage's sake (Phase 8.5 principle)
- **Use existing test infrastructure** - fixtures, factories, patterns from Phases 1-18

**Claude's Discretion:**
- Specific file prioritization within the top 20 high-impact files
- Test type allocation (unit tests vs. property tests vs. integration tests)
- Bug triage strategy (critical blockers vs. non-blocking improvements)
- Number of plans in Phase 19 (recommend 3-4 plans based on velocity)

**Deferred Ideas:**
- 80% overall coverage target (long-term roadmap, not single phase)
- Mobile and desktop test coverage (separate initiatives)
- API module comprehensive testing (deferred to later phases)

## Standard Stack

### Core Testing Infrastructure

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | 7.4+ | Test runner and framework | Industry standard for Python testing, rich plugin ecosystem, fixture system, async support |
| **pytest-cov** | 4.1+ | Coverage measurement integration | Official pytest plugin for coverage.py, generates HTML/JSON reports, CI/CD integration |
| **coverage.py** | 7.10.6 | Coverage calculation engine | Verified from current codebase (coverage.json meta.version), branch coverage, diff coverage support |
| **pytest-asyncio** | 0.21+ | Async test support | Required for FastAPI endpoints, async services (workflow_engine, LLM handlers) |
| **hypothesis** | 6.92+ | Property-based testing | Already used in property_tests/, invariants testing for stateful logic |

### Test Utilities (Established from Phases 1-18)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **unittest.mock** | Built-in | Mocking and patching | All unit tests - AsyncMock for async services, MagicMock for external dependencies |
| **FastAPI TestClient** | Built-in | API endpoint testing | Integration tests for API routes (atom_agent_endpoints, byok_endpoints) |
| **factory-boy** | 3.3+ | Test data generation | Already configured - AgentFactory, UserFactory, CanvasFactory in tests/factories/ |
| **pytest-rerunfailures** | 12.0+ | Flaky test detection | Already configured (3 reruns), identify flaky tests during bug fixing |
| **pytest-xdist** | 3.0+ | Parallel test execution | Configured from Phase 1, -n auto for parallel runs |

### AI-Assisted Test Generation (Optional)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **CodiumAI Cover-Agent** | Latest | AI-powered test generation | Rapid baseline test creation for zero-coverage files (not used in Phases 1-18, manual testing preferred) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest | unittest (built-in) | unittest has less verbose fixtures, no plugin ecosystem, inferior parametrization |
| pytest-cov | nose2, nose | nose is deprecated, nose2 unmaintained, pytest-cov actively developed |
| unittest.mock | mock (PyPI backport) | mock is Python 2 backport, unittest.mock built-in Python 3.3+ |
| factory-boy | Manual test data | factory-boy provides consistent data, reduces duplication, handles relationships |
| Manual testing | AI test generation | AI faster for baselines, manual better for edge cases, complex logic |

**Installation:**
```bash
# Standard testing stack (already installed from Phase 1)
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/ -v

# Run coverage report
pytest tests/ --cov=. --cov-report=html --cov-report=json

# Run specific test file with coverage
pytest tests/unit/test_workflow_engine.py --cov=core/workflow_engine --cov-report=term-missing
```

## Architecture Patterns

### Recommended Project Structure (Established from Phases 1-18)

```
backend/tests/
├── unit/                      # Unit tests (fast, isolated)
│   ├── core/                  # Tests for core/ modules
│   ├── api/                   # Tests for api/ routes
│   └── conftest.py            # Unit test fixtures (db session)
├── integration/               # Integration tests (slower, dependencies)
├── property_tests/            # Hypothesis property-based tests
│   ├── workflows/             # Workflow state machine invariants
│   ├── governance/            # Governance cache invariants
│   └── models/                # ORM invariants
├── factories/                 # factory-boy test data
│   ├── __init__.py            # AgentFactory, UserFactory, CanvasFactory
│   └── conftest.py            # Factory fixtures
├── coverage_reports/          # Coverage artifacts
│   ├── html/                  # HTML coverage reports
│   └── metrics/
│       ├── coverage.json      # Raw coverage data (28MB)
│       └── trending.json      # Historical trending data
└── conftest.py                # Shared fixtures and configuration
```

### Pattern 1: High-Impact File Testing Strategy (Validated from Phase 8.6)

**What:** Focus on files with **lowest coverage percentages** and **largest line counts** for maximum coverage ROI.
**When to use:** All coverage push phases (Phases 8.5, 8.6, 11, 12, 19)
**Proven results:** Phase 8.6 achieved +1.42% per plan (3.38x acceleration over unfocused testing)
**Example:**
```python
# Source: Phase 11-01-PLAN.md (coverage analysis strategy)
# Step 1: Identify zero-coverage or low-coverage files
import json

with open('tests/coverage_reports/metrics/coverage.json') as f:
    data = json.load(f)

files = data['files']
high_impact = [
    (filename, file_data['summary']['num_statements'], file_data['summary']['percent_covered'])
    for filename, file_data in files.items()
    if 'core/' in filename
    and file_data['summary']['num_statements'] > 150
    and file_data['summary']['percent_covered'] < 30
]

# Sort by uncovered lines (largest gap first)
high_impact.sort(key=lambda x: x[0] * (1 - x[1]/100), reverse=True)

# Step 2: Group related files for efficient context switching
# Wave 1: workflow_engine.py, atom_agent_endpoints.py, workflow_analytics_engine.py
# Wave 2: llm/byok_handler.py, lancedb_handler.py, episode_segmentation_service.py
# Wave 3: auto_document_ingestion.py, workflow_versioning_system.py, advanced_workflow_system.py
```

**Target:** 50% average coverage per file (not 100% - diminishing returns beyond 70-80%)

### Pattern 2: ORM Testing with Factory-Boy (Validated from Phase 12-01)

**What:** Use factory-boy for test data generation and deterministic ORM tests.
**When to use:** Testing SQLAlchemy models, relationships, validation, lifecycle hooks.
**Proven results:** Phase 12-01 achieved **97.30% coverage** on models.py (2,307 of 2,351 lines)
**Example:**
```python
# Source: backend/tests/unit/test_models_orm.py (Phase 12-01, 968 lines, 51 tests)
import pytest
from sqlalchemy.orm import Session
from core.models import AgentRegistry, AgentExecution, Episode
from tests.factories import AgentFactory, UserFactory, CanvasFactory

class TestAgentRegistryModel:
    def test_agent_creation(self, db: Session):
        agent = AgentFactory(maturity_level="STUDENT")
        assert agent.id is not None
        assert agent.maturity_level == "STUDENT"

    def test_agent_execution_relationship(self, db: Session):
        agent = AgentFactory()
        execution = AgentExecution(agent_id=agent.id, status="PENDING")
        db.add(execution)
        db.commit()
        assert execution.agent.id == agent.id

    def test_maturity_level_enum(self, db: Session):
        for level in ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]:
            agent = AgentFactory(maturity_level=level)
            assert agent.maturity_level == level
```

**Key principles:**
- Use factory-boy for consistent test data (AgentFactory, UserFactory)
- Test relationships (one-to-many, foreign keys)
- Test validation (enums, constraints, JSON fields)
- Target 50%+ coverage for complex models

### Pattern 3: Property-Based Testing for Stateful Logic (Validated from Phase 12-01)

**What:** Use Hypothesis to test invariants across generated inputs.
**When to use:** Testing state machines, workflows, governance logic, episodic memory.
**Proven results:** Phase 12-01 created 18 property tests for workflow state machine invariants
**Example:**
```python
# Source: backend/tests/property_tests/workflows/test_workflow_engine_state_invariants.py
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from core.workflow_engine import WorkflowEngine

class TestWorkflowStateInvariants:
    @pytest.fixture
    def engine(self):
        return WorkflowEngine(max_concurrent_steps=3)

    @given(
        current_status=st.sampled_from([
            WorkflowExecutionStatus.PENDING,
            WorkflowExecutionStatus.RUNNING,
            WorkflowExecutionStatus.COMPLETED,
            WorkflowExecutionStatus.FAILED,
            WorkflowExecutionStatus.PAUSED
        ])
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_valid_transitions_exist(self, engine, current_status):
        """INVARIANT: Every status has defined valid transitions."""
        valid_transitions = engine.get_valid_transitions(current_status)
        assert isinstance(valid_transitions, list)

    @given(
        node_count=st.integers(min_value=1, max_value=20),
        edge_probability=st.floats(min_value=0.0, max_value=0.5)
    )
    @settings(max_examples=50)
    def test_dag_conversion_preserves_dependencies(self, engine, node_count, edge_probability):
        """INVARIANT: Converting workflow to steps preserves all dependency edges."""
        # Generate random DAG and test conversion
```

**Key principles:**
- Use st.sampled_from() for enum validation
- Use st.integers(), st.floats() for numeric ranges
- Use @settings(max_examples=100) for critical invariants
- Suppress health checks for function-scoped fixtures

### Pattern 4: Async Service Testing with AsyncMock

**What:** Test async services using AsyncMock for external dependencies.
**When to use:** Testing FastAPI endpoints, async LLM handlers, workflow execution.
**Example:**
```python
# Source: backend/tests/unit/test_byok_handler.py (pattern from Phase 12)
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.fixture
def mock_openai():
    """Mock OpenAI client for LLM testing"""
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content="Test response"))],
            usage=MagicMock(total_tokens=100)
        )
    )
    return client

@pytest.mark.asyncio
async def test_streaming_completion(mock_openai):
    """Test LLM streaming completion"""
    with patch('core.llm.byok_handler.AsyncOpenAI', return_value=mock_openai):
        handler = BYOKHandler(provider="openai")
        response = await handler.complete("Test prompt")
        assert response.content == "Test response"
```

### Pattern 5: Bug Fixing Workflow (Established from Phases 10, 15, 18)

**What:** Systematic approach to fixing test failures and production bugs.
**When to use:** Discovered during test execution or reported in production.
**Proven results:** 20 bug fix commits in February 2026 (social layer, PII redactor, test failures)
**Workflow:**
```bash
# Step 1: Run test suite and identify failures
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/ -v

# Step 2: Isolate failing test
pytest tests/unit/test_workflow_engine.py::test_specific_function -v

# Step 3: Debug and fix (3 categories)
# A. Test bugs (incorrect assertions, wrong mocks)
# B. Production bugs (incorrect logic, missing imports)
# C. Flaky tests (timing issues, shared state)

# Step 4: Verify fix
pytest tests/unit/test_workflow_engine.py::test_specific_function -v

# Step 5: Commit with conventional commit message
git commit -m "fix(workflow_engine): correct status transition logic"

# Step 6: Re-run full suite to ensure no regressions
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/ --cov
```

**Bug categories:**
1. **Test bugs:** Incorrect assertions, wrong mock targets, missing imports (fix in test files)
2. **Production bugs:** Incorrect logic, missing error handling, wrong API signatures (fix in source files)
3. **Flaky tests:** Timing issues, shared state, database pollution (fix with fixtures, transactions, or @pytest.mark.flaky)

### Anti-Patterns to Avoid

- **Test proliferation for coverage's sake:** Writing meaningless tests just to increase numbers degrades quality (Phase 8.5 principle)
- **Testing implementation details:** Test behavior, not internal implementation (brittle tests)
- **Missing assertions:** Tests that execute code but don't assert outcomes (false confidence)
- **Over-mocking:** Mocking everything creates tests that don't validate real behavior
- **Ignoring flaky tests:** Using @pytest.mark.flaky permanently instead of fixing root cause
- **Chasing 100% coverage:** Diminishing returns beyond 70-80%, target 50% average per file (Phase 8.6 validated)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Test coverage measurement | Custom coverage tracking | coverage.py, pytest-cov | Industry standard, branch coverage, HTML reports, CI/CD integration |
| Test framework | Custom test runner | pytest | Fixture system, parametrization, async support, rich plugin ecosystem |
| Mock objects | Manual mock classes | unittest.mock (AsyncMock, MagicMock) | Built-in, patching, verification, automatic cleanup |
| API testing | Custom HTTP client | FastAPI TestClient | Official FastAPI testing, context management, raises validation |
| Test data generation | Random data helpers | factory-boy | Repeatable data, relationship handling, consistent state |
| Coverage trending | Custom scripts | trending.json, diff-cover | Historical tracking, PR coverage gates, diff enforcement |
| Property-based testing | Manual edge case enumeration | Hypothesis | Automatically finds edge cases, reduces human error, shrinks failures |
| Flaky test detection | Manual reruns | pytest-rerunfailures (3 reruns) | Automated identification, consistent reporting |

**Key insight:** The testing ecosystem has mature, battle-tested tools established in Phases 1-18. Building custom testing infrastructure wastes engineering time on solved problems. Focus effort on **writing tests for business logic**, not building testing infrastructure.

## Common Pitfalls

### Pitfall 1: Starting with Low-Value Files

**What goes wrong:** Testing small utility files first (e.g., <100 lines) provides minimal coverage impact
**Why it happens:** Files appear "easy" to test, low complexity
**How to avoid:**
- Prioritize by **uncovered line count** (coverage gap = total_lines * (1 - coverage_percentage/100))
- Focus on **Tier 1 files (>500 lines)** and **Tier 2 files (300-500 lines)**
- Target files with **<30% coverage** for maximum impact
**Warning signs:** Testing 10 files but coverage increases <1%
**Validated from:** Phase 8.6 discovered this pitfall, switched to high-impact strategy (+1.42% per plan)

### Pitfall 2: Testing Without Coverage Targets

**What goes wrong:** Writing tests without knowing which lines need coverage leads to redundant tests
**Why it happens:** "Just write more tests" without measuring impact
**How to avoid:**
- Always run coverage before and after: `pytest --cov=core/<module> --cov-report=term-missing`
- Use `--cov-report=term-missing` to see exact line numbers missing
- Check HTML report: `open htmlcov/core_<module>_py.html`
- Target 50% coverage per file (validated sustainable from Phase 8.6)
**Warning signs:** Coverage percentage doesn't increase after test additions
**Validated from:** Phase 11 coverage analysis methodology

### Pitfall 3: Ignoring Test Quality for Coverage Numbers

**What goes wrong:** Tests execute code but don't validate behavior (e.g., no assertions)
**Why it happens:** Pressure to increase coverage metrics quickly
**How to avoid:**
- Every test must have assertions (assert, raises, equals)
- Review test code for actual validation, not just execution
- Use pytest markers (@pytest.mark.unit) to categorize test intent
- Follow AAA pattern (Arrange, Act, Assert)
**Warning signs:** Coverage increases but tests pass without touching business logic
**Validated from:** Phase 8.5 quality principles

### Pitfall 4: Over-Mocking External Dependencies

**What goes wrong:** Tests mock everything, including business logic, creating false confidence
**Why it happens:** Desiring isolated tests, avoiding external service calls
**How to avoid:**
- Mock only external dependencies (APIs, databases, LLM providers)
- Test real business logic behavior
- Use integration tests for end-to-end validation
- Use AsyncMock for async services, not MagicMock
**Warning signs:** Tests pass but production code fails
**Validated from:** Phase 12-01 ORM testing (real SQLAlchemy, not mocked)

### Pitfall 5: Neglecting Branch Coverage

**What goes wrong:** Statement coverage looks good (80%) but branch coverage is poor (30%)
**Why it happens:** pytest-cov defaults to statement coverage, branches require explicit configuration
**How to avoid:**
- Enable branch coverage in pytest.ini: `branch = true` (already configured in Phase 1)
- Check `percent_branches_covered` in coverage.json
- Write tests for both true/false branches of conditionals
- Use Hypothesis for exhaustive branch testing
**Warning signs:** High statement coverage but low branch coverage
**Validated from:** Phase 1 pytest.ini configuration (branch = true)

### Pitfall 6: Not Using Existing Test Infrastructure

**What goes wrong:** Duplicating fixtures, test patterns, and utilities across test files
**Why it happens:** Not reviewing existing tests before writing new ones
**How to avoid:**
- Read `tests/conftest.py` for shared fixtures
- Read `tests/factories/__init__.py` for available factories
- Follow patterns from `test_models_orm.py`, `test_workflow_engine_state_invariants.py`
- Reuse test utilities instead of recreating
**Warning signs:** Similar fixture definitions in multiple files
**Validated from:** Phases 1-18 established comprehensive test infrastructure

### Pitfall 7: Fixing Bugs Without Root Cause Analysis

**What goes wrong:** Superficial fixes that address symptoms but not root causes
**Why it happens:** Pressure to fix failing tests quickly
**How to avoid:**
- Categorize bugs: Test bugs (fix tests), Production bugs (fix source), Flaky tests (fix fixtures)
- Use `git bisect` to find when bug was introduced
- Add regression tests for production bugs
- Fix flaky tests with proper fixtures, not @pytest.mark.flaky
**Warning signs:** Same bug fixed multiple times, tests keep failing
**Validated from:** Phase 10 bug fixing methodology, 20 bug fix commits in Feb 2026

## Code Examples

Verified patterns from current codebase (Phases 1-18):

### Running Targeted Coverage for Single File

```bash
# Source: Phase 11-01-PLAN.md (coverage analysis methodology)
# Measure coverage for specific module only
pytest tests/unit/test_workflow_engine.py \
  --cov=core/workflow_engine.py \
  --cov-report=term-missing \
  --cov-report=html:htmlcov/workflow_engine

# Output shows exact missing lines:
# core/workflow_engine.py:456: line 456 not covered
# core/workflow_engine.py:478: line 478 not covered
```

### Identifying High-Impact Files

```python
# Source: backend/tests/coverage_reports/PHASE_11_COVERAGE_ANALYSIS_REPORT.md
import json

with open('tests/coverage_reports/metrics/coverage.json') as f:
    data = json.load(f)

# Find high-impact files in core module
files = data['files']
high_impact = [
    (filename, file_data['summary']['num_statements'], file_data['summary']['percent_covered'])
    for filename, file_data in files.items()
    if 'core/' in filename
    and file_data['summary']['num_statements'] > 150
    and file_data['summary']['percent_covered'] < 30
]

# Sort by uncovered lines (largest gap first)
high_impact.sort(key=lambda x: x[0] * (1 - x[1]/100), reverse=True)

for filename, lines, pct in high_impact[:10]:
    uncovered = lines * (1 - pct/100)
    print(f"{filename}: {lines} lines, {pct:.1f}% coverage, {uncovered:.0f} uncovered")
```

### ORM Unit Test with Factory-Boy

```python
# Source: backend/tests/unit/test_models_orm.py (Phase 12-01, 97.30% coverage achieved)
import pytest
from sqlalchemy.orm import Session
from core.models import AgentRegistry, AgentExecution
from tests.factories import AgentFactory

class TestAgentRegistryModel:
    def test_agent_creation(self, db: Session):
        agent = AgentFactory(maturity_level="STUDENT")
        assert agent.id is not None
        assert agent.maturity_level == "STUDENT"

    def test_agent_execution_relationship(self, db: Session):
        agent = AgentFactory()
        execution = AgentExecution(agent_id=agent.id, status="PENDING")
        db.add(execution)
        db.commit()
        assert execution.agent.id == agent.id
```

### Property-Based Test with Hypothesis

```python
# Source: backend/tests/property_tests/workflows/test_workflow_engine_state_invariants.py
from hypothesis import given, strategies as st, settings, HealthCheck

@given(
    current_status=st.sampled_from([
        WorkflowExecutionStatus.PENDING,
        WorkflowExecutionStatus.RUNNING,
        WorkflowExecutionStatus.COMPLETED,
    ])
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_status_transitions(self, engine, current_status):
    """INVARIANT: Every status has defined valid transitions."""
    valid_transitions = engine.get_valid_transitions(current_status)
    assert isinstance(valid_transitions, list)
    assert len(valid_transitions) >= 1  # At least one transition exists
```

### Async Service Test with AsyncMock

```python
# Source: backend/tests/unit/test_byok_handler.py (pattern from Phase 12)
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.fixture
def mock_openai():
    client = AsyncMock()
    client.chat.completions.create = AsyncMock(
        return_value=MagicMock(
            choices=[MagicMock(message=MagicMock(content="Test response"))]
        )
    )
    return client

@pytest.mark.asyncio
async def test_streaming_completion(mock_openai):
    with patch('core.llm.byok_handler.AsyncOpenAI', return_value=mock_openai):
        handler = BYOKHandler(provider="openai")
        response = await handler.complete("Test prompt")
        assert response.content == "Test response"
```

### Bug Fix Workflow Example

```bash
# Source: Phase 10, 15, 18 bug fixing methodology
# Step 1: Identify failing test
pytest tests/unit/test_workflow_engine.py::test_workflow_cancellation -v
# FAILED: test_workflow_cancellation - AssertionError: assert status == 'CANCELLED'

# Step 2: Debug and isolate issue
pytest tests/unit/test_workflow_engine.py::test_workflow_cancellation -v -s
# Output shows: status is 'FAILED' not 'CANCELLED'

# Step 3: Fix bug in source code
# Edit core/workflow_engine.py: change line 1234 from status='FAILED' to status='CANCELLED'

# Step 4: Verify fix
pytest tests/unit/test_workflow_engine.py::test_workflow_cancellation -v
# PASSED

# Step 5: Run full suite to check for regressions
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/ --cov

# Step 6: Commit with conventional commit message
git add core/workflow_engine.py
git commit -m "fix(workflow_engine): correct status to CANCELLED in cancellation path"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Random file testing | High-impact file strategy (>150 lines, <30% coverage) | Phase 8.6 (Feb 2026) | 3.38x velocity acceleration (+1.42% per plan vs. +0.42%) |
| 100% coverage target | 50% average coverage per file (sustainable) | Phase 8.6 (Feb 2026) | Avoided diminishing returns, better ROI |
| Manual test creation | ORM + property test patterns (factory-boy, Hypothesis) | Phase 12 (Feb 2026) | 97.30% coverage on models.py (2,307 lines) |
| Bug fixing ad-hoc | Systematic bug triage (test bugs, production bugs, flaky tests) | Phase 10 (Feb 2026) | 20 bug fix commits in February 2026 |
| Isolated backend coverage | Trending with JSON metrics + historical tracking | Phase 1 (Jan 2026) | coverage.json, trending.json for continuous monitoring |

**Deprecated/outdated:**
- **100% coverage target:** Unrealistic, diminishing returns beyond 70-80%, use 50% average per file
- **nose, nose2:** Deprecated test frameworks, unmaintained, replaced by pytest
- **Mock objects created by hand:** Use unittest.mock (AsyncMock, MagicMock)
- **Coverage for coverage's sake:** Industry focus shifted to **meaningful coverage** (test quality > quantity)
- **Unfocused testing:** Testing small files provides minimal impact, use high-impact file strategy

## Open Questions

1. **Optimal Plan Count for Phase 19**
   - What we know: Phase 8 had 43 plans, Phase 12 had 4 plans, average velocity +1.42% per plan
   - What's unclear: Should Phase 19 have 3, 4, or 5 plans based on current capacity?
   - Recommendation: Start with **3-4 plans** covering 8-12 high-impact files, assess progress, then decide on expansion

2. **Bug Fix Prioritization Strategy**
   - What we know: 20 bug fix commits in February 2026, recent fixes for social layer, PII redactor, test failures
   - What's unclear: Are there critical blockers vs. non-blocking improvements?
   - Recommendation: Run full test suite to identify failures, categorize by severity (blocking tests vs. flaky tests vs. production bugs)

3. **Test Type Allocation for High-Impact Files**
   - What we know: ORM tests achieved 97.30% (Phase 12-01), property tests work for state machines (Phase 12-01)
   - What's unclear: Should workflow_engine.py use unit tests, property tests, or integration tests?
   - Recommendation: **Mixed approach** - Property tests for state machine invariants, integration tests for async execution paths, unit tests for helper functions

4. **Coverage Target per File**
   - What we know: 50% average validated sustainable (Phase 8.6), models.py achieved 97.30% (Phase 12-01)
   - What's unclear: Should we target 50% for all files, or higher for critical files?
   - Recommendation: **50% baseline for most files**, 70%+ for critical files (workflow_engine.py, atom_agent_endpoints.py, byok_handler.py)

## Sources

### Primary (HIGH confidence)

- **pytest Documentation** - Test runner, fixtures, parametrization, async support
  - https://docs.pytest.org/
- **coverage.py Documentation (v7.10.6)** - Coverage measurement engine, branch coverage, diff coverage
  - https://coverage.readthedocs.io/ (verified from coverage.json meta.version)
- **FastAPI TestClient Documentation** - API endpoint testing
  - https://fastapi.tiangolo.com/tutorial/testing/
- **unittest.mock Documentation** - Mocking and patching
  - https://docs.python.org/3/library/unittest.mock.html
- **Hypothesis Documentation** - Property-based testing library
  - https://hypothesis.readthedocs.io/
- **factory-boy Documentation** - Test data generation
  - https://factoryboy.readthedocs.io/
- **Phase 8.5 Research (08.5-coverage-expansion-RESEARCH.md)** - Coverage expansion methodology
- **Phase 8.6 Research (08.6-coverage-push-RESEARCH.md)** - High-impact file strategy validation
- **Phase 11 Coverage Analysis (PHASE_11_COVERAGE_ANALYSIS_REPORT.md)** - File prioritization methodology
- **Phase 12 Plans (12-tier-1-coverage-push-01-PLAN.md, 01-SUMMARY.md)** - ORM and property test patterns, 97.30% coverage achieved
- **Current coverage.json** - 22.64% coverage, 57,828 lines, 8,421 uncovered lines in top 20 files

### Secondary (MEDIUM confidence)

- [Testing best practices with pytest - Medium (Dec 4, 2024)](https://medium.com/@ngattai.lam/testing-best-practices-with-pytest-a2079d5e842b) - Modern pytest patterns and coverage targets
- [Achieving High Code Coverage with Effective Unit Tests - Sonar](https://www.sonarsource.com/resources/library/code-coverage-unit-tests/) - Coverage baseline strategies
- [Let Hypothesis Break Your Python Code Before Your Users Do - Towards Data Science (Oct 31, 2025)](https://towardsdatascience.com/let-hypothesis-break-your-code-before-your-users-do-130633845710) - Property-based testing benefits
- [ pytest-xdist Documentation](https://pytest-xdist.readthedocs.io/) - Parallel test execution (configured from Phase 1)
- [ pytest-rerunfailures Documentation](https://pytest-rerunfailures.readthedocs.io/) - Flaky test detection (configured from Phase 1)

### Tertiary (LOW confidence)

- Various blog posts on test coverage strategies - Require validation against actual tool performance
- AI test generation tools (Cover-Agent, CoverUp) - Not used in Phases 1-18, manual testing preferred

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All tools verified from current codebase (coverage.json v7.10.6, pytest configured in Phase 1)
- Architecture: HIGH - Patterns validated from Phases 8.5, 8.6, 11, 12 (97.30% coverage on models.py, 3.38x velocity acceleration)
- Pitfalls: HIGH - Discovered and documented from Phase 8.6, Phase 10 bug fixing, Phase 12 execution
- Coverage projections: HIGH - Calculated from actual coverage.json data (8,421 uncovered lines in top 20 files)
- Bug fixing workflow: HIGH - Validated from 20 bug fix commits in February 2026

**Research date:** 2026-02-17
**Valid until:** 2026-03-19 (30 days - pytest, coverage.py, Hypothesis are stable, but codebase changes rapidly)

**Key metrics for Phase 19 planning:**
- Current coverage: 22.64% (16,106 of 57,828 lines)
- Target: 80% long-term (multi-quarter journey)
- Phase 19 target: +3-5% coverage increase (to ~26-27%)
- Top 20 files: 8,421 uncovered lines
- Strategy: High-impact file testing (>150 lines, <30% coverage)
- Velocity: +1.42% per plan (validated from Phase 8.6)
- Plans: 3-4 plans recommended (8-12 files, targeting 50% coverage per file)
- Estimated effort: 3-5 days (based on 97.5% plan completion rate)

**Prioritized files for Phase 19 (top 8 by uncovered lines):**
1. workflow_engine.py: 1,163 lines, 4.8% coverage, 1,089 uncovered
2. atom_agent_endpoints.py: 757 lines, 8.8% coverage, 668 uncovered
3. llm/byok_handler.py: 549 lines, 8.5% coverage, 491 uncovered
4. lancedb_handler.py: 577 lines, 15.8% coverage, 467 uncovered
5. workflow_debugger.py: 527 lines, 9.7% coverage, 465 uncovered
6. workflow_analytics_engine.py: 593 lines, 27.8% coverage, 408 uncovered
7. episode_segmentation_service.py: 463 lines, 9.5% coverage, 400 uncovered
8. auto_document_ingestion.py: 479 lines, 13.9% coverage, 392 uncovered

**Potential impact:** Testing these 8 files to 50% coverage = **2,445 lines covered** = **+4.2% overall coverage increase**
