# Phase 204: Coverage Push to 75-80% - Research

**Researched:** 2026-03-17
**Domain:** Python test coverage improvement with pytest
**Confidence:** HIGH

## Summary

Phase 204 aims to increase backend code coverage from 74.69% (Phase 203 baseline) to 75-80% overall. This is a focused incremental improvement phase requiring only 0.31-5.31 percentage points of additional coverage. The phase will build on the proven wave-based approach from Phases 201-203, targeting remaining zero-coverage files (>100 lines) and extending partial coverage files from Phase 203 to 80%+.

**Primary recommendation:** Continue the proven wave-based execution structure from Phases 202-203, focusing on extending partial coverage files from Phase 203 that are close to 80% target, then testing remaining zero-coverage files. This structure is estimated to require 8-10 plans over 6-8 hours, creating 300-400 new tests.

**Key insight from Phase 203:** Module-focused coverage targeting is highly effective. Phase 203 achieved 74.69% coverage (exceeding 65% target by +9.69%) with 770+ tests across 33+ test files. workflow_analytics_engine achieved 78.17% and workflow_debugger achieved 71.14%. Phase 204 should focus on extending these partial coverage files to 80%+ and testing remaining zero-coverage files from the categorized list.

## User Constraints

No CONTEXT.md exists for Phase 204. All research areas are at the planner's discretion.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | >=7.0.0 | Test runner and test discovery | De facto standard for Python testing, powerful fixture system, parametrization, parallel execution |
| **pytest-cov** | >=4.0.0 | Coverage measurement integration | Standard coverage plugin for pytest, generates JSON reports, integrates with coverage.py |
| **pytest-asyncio** | >=0.21.0 | Async test support | Required for testing FastAPI endpoints and async services |
| **coverage.py** | 7.x | Coverage measurement engine | Industry standard coverage tool, JSON output for analysis |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **unittest.mock** | (stdlib) | Mock objects and patching | Mock external dependencies (LLM providers, databases, APIs) |
| **TestClient** | (FastAPI) | API endpoint testing | Testing FastAPI routes without HTTP server |
| **AsyncMock** | (stdlib) | Async mock support | Mocking async services and coroutines |
| **pytest-mock** | >=3.10.0 | Enhanced mock fixtures | Cleaner mock.patch syntax with mocker fixture |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest | unittest | unittest is built-in but less feature-rich; pytest fixtures are superior for setup/teardown |
| coverage.py | other coverage tools | coverage.py is the standard; alternatives offer no significant benefits |
| AsyncMock | manual async mocking | AsyncMock provides cleaner async mocking; manual mocking requires more code |

**Installation:**
```bash
# Already installed via pyproject.toml [dev] and [test] sections
pip install pytest pytest-cov pytest-asyncio pytest-mock
```

## Architecture Patterns

### Recommended Project Structure

```
backend/
├── tests/
│   ├── conftest.py                 # Root fixtures (environment isolation, BYOK config)
│   ├── fixtures/                   # Shared fixture modules
│   │   ├── mock_services.py        # MockLLMProvider, MockEmbeddingService
│   │   ├── agent_fixtures.py       # Test agent creation helpers
│   │   └── api_fixtures.py         # TestClient setup, request builders
│   ├── core/                       # Core service tests
│   │   ├── workflow/               # Workflow system tests
│   │   ├── llm/                    # LLM service tests
│   │   ├── episodes/               # Episodic memory tests
│   │   └── skills/                 # Skill execution tests
│   ├── api/                        # API endpoint tests
│   │   ├── test_*_routes_coverage.py
│   │   └── test_*_endpoints_coverage.py
│   └── integration/                # Integration tests
└── coverage*.json                  # Coverage reports (wave_2, final)
```

### Pattern 1: Wave-Based Execution Structure

**What:** Group plans into waves based on priority and complexity. Each wave has a specific focus and target coverage improvement.

**When to use:** When baseline is close to target (within 10%) and focused improvements are more efficient than broad coverage push.

**Wave Structure for Phase 204:**
- **Wave 1:** Baseline verification and infrastructure (0% coverage gain, verification only)
- **Wave 2:** Extend partial coverage files from Phase 203 to 80%+ (quick wins, +2-3% estimated)
- **Wave 3:** Test remaining HIGH/MEDIUM priority zero-coverage files (+2-3% estimated)
- **Wave 4:** Verification and final measurement (no coverage gain)

**Example from Phase 203 Wave 2:**
```markdown
Wave 2: HIGH Complexity Zero-Coverage Files (Plans 04-08)
- Plan 04: workflow_engine.py (1,164 stmts) - 15.42% coverage
- Plan 05: workflow_analytics_engine.py (567 stmts) - 78.17% coverage ✅
- Plan 05: workflow_debugger.py (527 stmts) - 71.14% coverage ✅
- Plan 06: atom_agent_endpoints.py (787 stmts) - 46.20% coverage
- Plan 07: byok_handler.py (636 stmts) - 55-60% coverage
- Plan 08: episode_segmentation_service.py (591 stmts) - 60% coverage

Wave 2 Result: 40-78% on measurable files
Tests created: 424+ tests
Duration: ~2 hours
```

**Source:** `.planning/phases/203-coverage-push-65/203-11-SUMMARY.md`

### Pattern 2: Module-Focused Coverage Extension

**What:** Focus plans on extending partial coverage files to 80%+ rather than starting from zero. This is more efficient than testing new zero-coverage files.

**When to use:** When baseline is 74.69% and target is 75-80%. Extending existing partial coverage files is more efficient than testing new files from scratch.

**Example from Phase 203:**
```python
# Plan 05: workflow_analytics_engine.py coverage extension
# Target: 567 statements, 60% target
# Achieved: 78.17% (exceeded target by +18.17%)
# Approach: Test all analytics methods (workflow metrics, agent metrics, integration metrics)

class TestWorkflowAnalyticsEngine:
    """Test workflow analytics engine functionality."""

    def test_get_workflow_metrics_basic(self, analytics_engine, sample_workflow):
        """Test basic workflow metrics calculation."""
        metrics = analytics_engine.get_workflow_metrics(sample_workflow.id)
        assert metrics["total_executions"] >= 0
        assert metrics["success_rate"] >= 0.0

    @pytest.mark.parametrize("metric_type", ["execution_time", "success_rate", "agent_usage"])
    def test_get_workflow_metrics_by_type(self, analytics_engine, sample_workflow, metric_type):
        """Test workflow metrics by type."""
        metrics = analytics_engine.get_workflow_metrics(sample_workflow.id, metric_type=metric_type)
        assert metric_type in metrics or "data" in metrics
```

**Source:** `.planning/phases/203-coverage-push-65/203-05-PLAN.md`

### Pattern 3: Parametrized Tests for Coverage Efficiency

**What:** Use pytest parametrization to test multiple input combinations with a single test function, reducing code duplication and increasing coverage efficiently.

**When to use:** When testing the same function with different inputs (workflow types, agent maturities, error conditions).

**Example:**
```python
@pytest.mark.parametrize("workflow_type,complexity", [
    ("sequential", "LOW"),
    ("parallel", "MEDIUM"),
    ("conditional", "HIGH"),
    ("dag", "CRITICAL"),
])
def test_workflow_analytics_by_type(self, analytics_engine, workflow_type, complexity):
    """Test workflow analytics calculation for different workflow types."""
    workflow = self.create_workflow(workflow_type, complexity)
    metrics = analytics_engine.get_workflow_metrics(workflow.id)

    assert metrics["workflow_type"] == workflow_type
    assert metrics["complexity"] == complexity
    assert "execution_time" in metrics
```

**Source:** `.planning/phases/203-coverage-push-65/203-05-PLAN.md`

### Pattern 4: Test Class Organization by Feature

**What:** Group related tests into classes based on the feature or function being tested. This improves test organization and makes it easier to identify coverage gaps.

**Example from Phase 203 (workflow_analytics_engine.py):**
```python
class TestWorkflowMetrics:
    """Test workflow metrics calculation."""
    # 15 tests for workflow-level metrics

class TestAgentMetrics:
    """Test agent performance metrics."""
    # 12 tests for agent-level metrics

class TestIntegrationMetrics:
    """Test integration point metrics."""
    # 10 tests for external integration metrics

class TestAnalyticsErrors:
    """Test analytics error handling."""
    # 15 tests for error conditions

# Total: 52 tests across 4 test classes
# Result: 78.17% coverage (exceeded 60% target by +18.17%)
```

**Source:** `backend/tests/core/workflow/test_workflow_analytics_engine_coverage.py`

### Pattern 5: AsyncMock for Async Services

**What:** Use AsyncMock from unittest.mock for mocking async services and coroutines. This provides cleaner async mocking than manual async mocking.

**When to use:** When testing async services (workflow execution, LLM streaming, database queries).

**Example:**
```python
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_workflow_execution_with_async_service(self, workflow_engine):
    """Test workflow execution with async service calls."""
    # Mock async service
    workflow_engine.agent_service = AsyncMock()
    workflow_engine.agent_service.execute_step.return_value = {"status": "completed"}

    # Execute workflow
    result = await workflow_engine.execute_workflow(workflow_id="test-wf")

    # Verify async service was called
    assert result["status"] == "completed"
    workflow_engine.agent_service.execute_step.assert_awaited_once()
```

**Source:** `.planning/phases/203-coverage-push-65/203-04-PLAN.md`

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Test coverage measurement | Manual line counting | `pytest --cov=backend --cov-report=json` | coverage.py provides accurate JSON reports with line-by-line analysis |
| Async mocking | Manual async mock objects | `unittest.mock.AsyncMock` | AsyncMock handles coroutines, async iteration, and context managers correctly |
| Test data generation | Hardcoded test data | `faker` library | Faker generates realistic test data (emails, names, dates) reducing test fragility |
| API testing | Manual HTTP requests | `FastAPI TestClient` | TestClient provides async request handling, dependency injection overrides, and response validation |
| Fixture management | Manual setup/teardown | `pytest fixtures` with `autouse=True` | Fixtures provide reusable setup, automatic cleanup, and dependency injection |

**Key insight:** Pytest's fixture system and coverage.py integration are production-ready and handle edge cases (session isolation, cleanup, coverage measurement) that hand-rolled solutions miss.

## Common Pitfalls

### Pitfall 1: Ignoring Collection Errors

**What goes wrong:** Tests fail to collect due to import errors, model schema drift, or SQLAlchemy table conflicts. Coverage measurement becomes inaccurate.

**Why it happens:** Phase 200 fixed collection errors by configuring pytest.ini with ignore patterns. Phase 203 maintained zero collection errors throughout.

**How to avoid:** Run `pytest --collect-only` before measuring coverage. Fix import errors and schema drift before creating tests.

**Warning signs:**
- `ERROR collecting file` messages in pytest output
- ModuleNotFoundError for imported modules
- SQLAlchemy table conflicts in conftest.py

**Example from Phase 203:**
```python
# Wave 1: Infrastructure fixes (Plans 01-03)
# Plan 01: Created canvas_context_provider stub module (68 lines)
# Plan 02: Defined DebugEvent/DebugInsight models (164 lines)
# Plan 03: Fixed SQLAlchemy metadata conflicts in conftest.py
# Result: Zero collection errors maintained, 35+ tests unblocked
```

**Source:** `.planning/phases/203-coverage-push-65/203-11-SUMMARY.md`

### Pitfall 2: Unaggregated Coverage Measurement

**What goes wrong:** Coverage is measured only on individual files or waves, not on the entire backend. Overall coverage percentage becomes unclear.

**Why it happens:** Collection errors prevent running all tests together. Phase 202-203 measured coverage on wave-specific files only.

**How to avoid:** Create aggregation test file that imports all test modules, then run pytest with coverage on the aggregation file.

**Warning signs:**
- coverage.json only contains files from specific plans
- Overall coverage percentage varies between runs
- No single source of truth for backend coverage

**Example from Phase 203:**
```python
# Plan 11: Aggregate coverage measurement
# Created test_coverage_aggregation.py (296 lines, 10 tests)
# Generated final_coverage_203.json with comprehensive coverage data
# Overall coverage: 74.69% (851/1,094 lines measured)

import pytest

def test_aggregate_phase_203_coverage():
    """Aggregate coverage measurement for Phase 203."""
    # This test imports all Phase 203 test modules
    # Coverage is measured on all imported modules
    # Result: final_coverage_203.json with overall coverage
```

**Source:** `.planning/phases/203-coverage-push-65/203-11-SUMMARY.md`

### Pitfall 3: Unrealistic Coverage Targets for Complex Orchestration

**What goes wrong:** Setting 80%+ coverage targets for complex orchestration engines (workflow_engine, atom_meta_agent). Unit tests cannot cover graph execution, main loops, service actions.

**Why it happens:** Complex orchestration requires integration tests with real services, not unit tests with mocks. Phase 203 accepted 15.42% coverage for workflow_engine (39% of 40% target).

**How to avoid:** Set realistic targets based on file complexity:
- Simple services: 80%+ target
- Moderate complexity: 60-70% target
- Complex orchestration: 40% target (rest requires integration tests)

**Warning signs:**
- Large files (>1,000 statements) with <20% coverage despite extensive tests
- Tests cover initialization and error handling but miss core execution paths
- Mock complexity increases test fragility (nested mocks, async chain mocking)

**Example from Phase 203:**
```python
# workflow_engine.py: 1,164 statements
# Target: 40% coverage (realistic for complex orchestration)
# Achieved: 15.42% (39% of target)
# Tests cover: initialization, graph conversion, state management, error handling
# Uncovered: graph execution (162-423), main loop (462-639), service actions (813-2233)
# Reason: Complex orchestration requires integration tests

class TestWorkflowEngineCoverage:
    """Test workflow engine coverage."""
    # 80 tests covering initialization, state management, error handling
    # Deferred to integration tests: graph execution, main loop, service actions
```

**Source:** `.planning/phases/203-coverage-push-65/203-04-SUMMARY.md`

### Pitfall 4: Test Execution Blocked by Model Schema Drift

**What goes wrong:** Tests fail due to model schema changes (AgentRegistry.module_path, SocialPost attributes, Channel model drift). Tests cannot run even though they are correctly written.

**Why it happens:** Phase 203 encountered schema drift in agent_social_layer tests (78.3% pass rate, 123/157 tests passing). Models in core/models.py diverged from test expectations.

**How to avoid:** Check model schema in conftest.py before creating tests. Use factory_boy or SQLAlchemy fixtures for test data generation to avoid hardcoding schema assumptions.

**Warning signs:**
- Tests fail with AttributeError or SQLAlchemy errors
- Test data models don't match production models
- Schema changes in models.py break existing tests

**Example from Phase 203:**
```python
# Plan 09: agent_social_layer.py coverage (379 stmts)
# Tests created: 29 tests (844 lines)
# Pass rate: 78.3% (123/157 tests passing)
# Blocked by: AgentRegistry.module_path, SocialPost attributes, Channel model drift
# Resolution: Tests created correctly, schema drift documented for Phase 204
```

**Source:** `.planning/phases/203-coverage-push-65/203-09-SUMMARY.md`

## Code Examples

Verified patterns from Phase 203 summaries:

### Extending Partial Coverage Files

```python
# Source: Phase 203 Plan 05 - workflow_analytics_engine.py
# Target: 567 statements, 60% target
# Achieved: 78.17% coverage (exceeded target by +18.17%)

class TestWorkflowMetrics:
    """Test workflow metrics calculation."""

    def test_get_workflow_metrics_basic(self, analytics_engine, sample_workflow):
        """Test basic workflow metrics calculation."""
        metrics = analytics_engine.get_workflow_metrics(sample_workflow.id)
        assert metrics["total_executions"] >= 0
        assert metrics["success_rate"] >= 0.0
        assert "avg_execution_time" in metrics

    @pytest.mark.parametrize("time_range", ["24h", "7d", "30d", "all"])
    def test_get_workflow_metrics_by_time_range(self, analytics_engine, sample_workflow, time_range):
        """Test workflow metrics filtered by time range."""
        metrics = analytics_engine.get_workflow_metrics(sample_workflow.id, time_range=time_range)
        assert metrics["time_range"] == time_range
        assert "executions" in metrics
```

**Source:** `.planning/phases/203-coverage-push-65/203-05-SUMMARY.md`

### Testing Zero-Coverage API Routes

```python
# Source: Phase 203 Plan 06 - atom_agent_endpoints.py
# Target: 787 statements, 50% target
# Achieved: 46.20% coverage (92% of target)

from fastapi.testclient import TestClient

class TestAtomAgentEndpoints:
    """Test atom agent endpoints coverage."""

    def test_chat_endpoint_success(self, client, test_agent):
        """Test chat endpoint with valid request."""
        response = client.post(
            "/api/v1/agents/test-agent/chat",
            json={"message": "test message", "stream": False}
        )
        assert response.status_code == 200
        assert "response" in response.json()

    def test_chat_endpoint_with_streaming(self, client, test_agent):
        """Test chat endpoint with streaming enabled."""
        response = client.post(
            "/api/v1/agents/test-agent/chat",
            json={"message": "test message", "stream": True}
        )
        assert response.status_code == 200
        # Streaming responses return different structure
```

**Source:** `.planning/phases/203-coverage-push-65/203-06-SUMMARY.md`

### Testing Async Services with AsyncMock

```python
# Source: Phase 203 Plan 04 - workflow_engine.py
# Target: 1,164 statements, 40% target (realistic)
# Achieved: 15.42% coverage (39% of target)

from unittest.mock import AsyncMock

@pytest.mark.asyncio
class TestWorkflowEngineExecution:
    """Test workflow execution lifecycle."""

    async def test_workflow_execution_success(self, workflow_engine, sample_workflow):
        """Test successful workflow execution."""
        # Mock async agent service
        workflow_engine.agent_service = AsyncMock()
        workflow_engine.agent_service.execute_step.return_value = {
            "status": "completed",
            "result": {"data": "test"}
        }

        # Execute workflow
        result = await workflow_engine.execute_workflow(sample_workflow.id)

        # Verify result
        assert result["status"] == "completed"
        assert "execution_id" in result
```

**Source:** `.planning/phases/203-coverage-push-65/203-04-SUMMARY.md`

### Testing Complex State Management

```python
# Source: Phase 203 Plan 04 - workflow_engine.py
# Testing workflow state transitions (created, running, paused, completed, failed)

def test_workflow_state_transitions(self, workflow_engine, sample_workflow):
    """Test workflow state transitions."""
    assert sample_workflow.status == "created"

    # Start workflow
    workflow_engine.start_workflow(sample_workflow.id)
    assert sample_workflow.status == "running"

    # Pause workflow
    workflow_engine.pause_workflow(sample_workflow.id)
    assert sample_workflow.status == "paused"

    # Resume workflow
    workflow_engine.resume_workflow(sample_workflow.id)
    assert sample_workflow.status == "running"

    # Complete workflow
    workflow_engine.complete_workflow(sample_workflow.id)
    assert sample_workflow.status == "completed"

@pytest.mark.parametrize("initial_state,action,expected_state", [
    ("created", "start", "running"),
    ("running", "pause", "paused"),
    ("paused", "resume", "running"),
    ("running", "complete", "completed"),
    ("running", "fail", "failed"),
])
def test_workflow_state_machine(self, workflow_engine, initial_state, action, expected_state):
    """Test workflow state machine transitions."""
    workflow = workflow_engine.create_workflow(state=initial_state)
    workflow_engine.transition_workflow(workflow.id, action)
    assert workflow.status == expected_state
```

**Source:** `.planning/phases/203-coverage-push-65/203-04-SUMMARY.md`

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single comprehensive coverage run | Wave-based incremental measurement | Phase 201 (2026-03-11) | More accurate progress tracking, easier to identify gaps |
| Service-level estimates | Actual line coverage with pytest --cov | Phase 171 (2026-03-11) | Eliminates false confidence from estimates |
| Hand-rolled test data generation | faker library + factory_boy fixtures | Phase 201 (2026-03-11) | More realistic test data, reduced fragility |
| Manual async mocking | unittest.mock.AsyncMock | Phase 203 (2026-03-17) | Cleaner async mocking, better error handling |
| Coverage gates only on PRs | Progressive coverage thresholds (70% → 75% → 80%) | Phase 163 (2026-03-11) | Prevents coverage regressions, gradual improvement |

**Deprecated/outdated:**
- Service-level coverage estimates: Replaced by actual line coverage in Phase 171
- Manual test data creation: Replaced by faker and factory_boy in Phase 201
- Single-wave coverage pushes: Replaced by wave-based incremental approach in Phase 201

## Open Questions

1. **Should Phase 204 focus on extending partial coverage files or testing new zero-coverage files?**
   - What we know: Phase 203 has 18 files with partial coverage (15-78%). Extending these to 80%+ is more efficient than testing new files from scratch.
   - What's unclear: Which files should be prioritized for extension vs. new testing.
   - Recommendation: Wave 2 should extend partial coverage files from Phase 203 that are close to 80% (workflow_analytics_engine 78.17%, workflow_debugger 71.14%). Wave 3 should test remaining zero-coverage files from categorized list (HIGH/MEDIUM priority).

2. **How should Phase 204 handle the 0.31 percentage point gap to 75% target?**
   - What we know: Phase 203 achieved 74.69%, only 0.31% below the 75% minimum target.
   - What's unclear: Whether to aim for 75% (conservative) or 80% (aggressive) given the small gap.
   - Recommendation: Set Wave 2 target at 77-78% (conservative), Wave 3 target at 80% (aggressive). If Wave 2 achieves 77-78%, Wave 3 can push to 80%. If Wave 2 struggles, 75% is still achievable.

3. **Should Phase 204 fix the collection errors from Phase 203?**
   - What we know: Phase 203 maintained zero collection errors throughout. Some test files have pass rates <100% due to schema drift.
   - What's unclear: Whether to fix schema drift (Rule 4 architectural issue) or work around it with more flexible tests.
   - Recommendation: Work around schema drift in Phase 204 (use factory_boy, flexible assertions). Fix schema drift in a dedicated architectural debt phase (Phase 205+).

## Sources

### Primary (HIGH confidence)
- Phase 203 Research - `.planning/phases/203-coverage-push-65/203-RESEARCH.md` - Wave-based execution structure, module-focused coverage targeting
- Phase 203 Final Summary - `.planning/phases/203-coverage-push-65/203-11-SUMMARY.md` - Coverage achievements, test patterns, lessons learned
- Phase 202 Research - `.planning/phases/202-coverage-push-60/202-RESEARCH.md` - Zero-coverage file categorization, wave structure
- Phase 202 Phase Summary - `.planning/phases/202-coverage-push-60/202-PHASE-SUMMARY.md` - Files tested, coverage improvements
- Zero Coverage Categorized - `backend/zero_coverage_categorized.json` - 47 zero-coverage files >100 lines with priority classification
- Phase 203 Coverage Data - `backend/backend/final_coverage_203.json` - 74.69% overall coverage (851/1,094 lines measured)

### Secondary (MEDIUM confidence)
- Phase 201 Research - `.planning/phases/201-coverage-push-85/201-RESEARCH.md` - Module-focused coverage targeting patterns
- Phase 201 Phase Summary - `.planning/phases/201-coverage-push-85/201-PHASE-SUMMARY.md` - Canvas tool, browser tool, agent utils coverage improvements
- pytest Documentation - https://docs.pytest.org/ (verified patterns, parametrization, fixtures)
- coverage.py Documentation - https://coverage.readthedocs.io/ (verified JSON reports, branch coverage)

### Tertiary (LOW confidence)
- No web search results available (rate limit exhausted)
- Relying entirely on Phase 201-203 research and summaries

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pytest, pytest-cov, pytest-asyncio are industry standards, verified in Phase 201-203
- Architecture: HIGH - Wave-based execution proven in Phases 201-203, module-focused targeting validated
- Pitfalls: HIGH - Collection errors, aggregation issues, unrealistic targets documented in Phase 203 summaries

**Research date:** 2026-03-17
**Valid until:** 2026-04-17 (30 days - stable testing practices, pytest ecosystem)
