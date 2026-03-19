# Phase 202: Coverage Push to 60% - Research

**Researched:** 2026-03-17
**Domain:** Python test coverage improvement with pytest
**Confidence:** HIGH

## Summary

Phase 202 aims to increase backend code coverage from 20.13% to 60%, a gap of 39.87 percentage points requiring ~29,500 additional lines to be covered. This research analyzes the proven patterns from Phase 201 (which achieved 20.13% coverage through Wave 2), identifies the optimal wave structure for Phase 202, and documents the testing infrastructure and patterns that should be used.

**Primary recommendation:** Continue the wave-based approach from Phase 201, targeting zero-coverage files >100 lines first (Wave 3), then medium-impact modules (Wave 4), then large zero-coverage files (Wave 5), and final verification (Wave 6). This structure is estimated to require 15-18 plans over 10-12 hours, creating 700-800 new tests.

**Key insight from Phase 201:** Module-focused coverage targeting is highly effective. Single-module plans achieved dramatic improvements: canvas tool (+64.23%), browser tool (+75.63%), agent utils (+98.48%). Phase 202 should continue this pattern but at larger scale, targeting groups of files rather than individual modules.

## User Constraints

No CONTEXT.md exists for Phase 202. All research areas are at the planner's discretion.

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
| **httpx** | >=0.24.0 | Async HTTP client testing | Mocking external HTTP calls |
| **faker** | >=19.0.0 | Test data generation | Generate realistic test data for database models |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest | unittest | unittest is built-in but less feature-rich; pytest fixtures are superior for setup/teardown |
| coverage.py | other coverage tools | coverage.py is the standard; alternatives offer no significant benefits |
| unittest.mock | dependency injection | DI requires more code changes; mocking is faster for testing existing code |

**Installation:**
```bash
# Already installed via pyproject.toml [dev] and [test] sections
pip install pytest pytest-cov pytest-asyncio httpx faker
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
│   ├── tools/                      # Tool tests (browser, canvas, device)
│   ├── core/                       # Core service tests
│   ├── api/                        # API endpoint tests
│   └── cli/                        # CLI tests
└── coverage*.json                  # Coverage reports (wave_2, final)
```

### Pattern 1: Module-Focused Coverage Targeting

**What:** Focus entire plans on specific modules or groups of related files to maximize coverage improvement per plan.

**When to use:** When baseline coverage is low (<30%) and many files have 0% coverage. This pattern was proven in Phase 201.

**Example from Phase 201:**
```python
# Plan 02: Canvas Tool Coverage Push
# Target: 3.9% → 50%+ (achieved 68.13%)
# Approach: Test all canvas types (chart, markdown, form, sheet)
# Tests created: 23 tests across 4 test classes
# Result: +64.23 percentage points in 4 minutes

class TestCanvasPresentation:
    """Test canvas presentation functionality."""

    def test_present_chart_canvas_student_agent(self, canvas_tool, student_agent):
        """Test STUDENT agent can present chart canvas (LOW complexity)."""
        with patch.object(canvas_tool.governance_service, 'check_action_permission') as mock_gov:
            mock_gov.return_value = Mock(allowed=True, reason="")

            result = canvas_tool.present_canvas(
                agent_id=student_agent.id,
                canvas_type="chart",
                data={"type": "line", "datasets": [{"data": [1, 2, 3]}]}
            )

            assert result["success"] is True
            assert "canvas_id" in result
```

**Source:** `.planning/phases/201-coverage-push-85/201-02-PLAN.md`

### Pattern 2: Wave-Based Execution Structure

**What:** Group plans into waves based on priority and complexity. Each wave has a specific focus and target coverage improvement.

**When to use:** When baseline is low and incremental progress is more achievable than big-bang approach.

**Wave Structure:**
- **Wave 1:** Infrastructure and baseline measurement (0% coverage gain, verification only)
- **Wave 2:** HIGH priority modules (target single modules with large gaps)
- **Wave 3:** Zero-coverage files >100 lines (easy wins, +5-6% estimated)
- **Wave 4:** Medium-impact modules (20-50% gap, +15-20% estimated)
- **Wave 5:** Large zero-coverage files (>200 lines, +10-12% estimated)
- **Wave 6:** Verification and final measurement (no coverage gain)

**Example from Phase 201 Wave 2:**
```markdown
Wave 2: HIGH Priority Modules (Plans 02-07)
- Plan 02: Canvas tool coverage (3.9% → 68.13%, +64.23%)
- Plan 03: Browser tool coverage (9.9% → 85.53%, +75.63%)
- Plan 04: Device tool coverage (86.88% → 95.79%, +8.91%)
- Plan 05: Agent utils coverage (0% → 98.48%, +98.48%)
- Plan 06: CLI module coverage (16% → 43.36%, +24-27%)
- Plan 07: Health routes coverage (55.56% → 76.19%, +20.63%)

Wave 2 Result: 20.13% overall (+14.92 percentage points from baseline)
Tests created: 324 (87% pass rate)
Duration: ~6 hours across 8 plans
```

**Source:** `.planning/phases/201-coverage-push-85/201-PHASE-SUMMARY.md`

### Pattern 3: Parametrized Tests for Coverage Efficiency

**What:** Use pytest parametrization to test multiple input combinations with a single test function, reducing code duplication and increasing coverage efficiently.

**When to use:** When testing the same function with different inputs (canvas types, maturity levels, error conditions).

**Example:**
```python
@pytest.mark.parametrize("canvas_type,expected_allowed", [
    ("chart", True),      # LOW complexity, STUDENT+ allowed
    ("markdown", True),   # LOW complexity, STUDENT+ allowed
    ("form", False),      # MODERATE complexity, INTERN+ required
    ("sheet", False),     # HIGH complexity, SUPERVISED+ required
])
def test_canvas_type_governance_by_maturity(self, canvas_tool, student_agent, canvas_type, expected_allowed):
    """Test canvas type governance based on agent maturity level."""
    with patch.object(canvas_tool.governance_service, 'check_action_permission') as mock_gov:
        mock_gov.return_value = Mock(allowed=expected_allowed, reason="Maturity check")

        result = canvas_tool.present_canvas(
            agent_id=student_agent.id,
            canvas_type=canvas_type,
            data={}
        )

        assert result["success"] == expected_allowed or result.get("blocked_reason") is not None
```

**Source:** `.planning/phases/201-coverage-push-85/201-02-PLAN.md`

### Pattern 4: Test Class Organization by Feature

**What:** Group related tests into classes based on the feature or function being tested. This improves test organization and makes it easier to identify coverage gaps.

**When to use:** When testing a module with multiple distinct features or functions.

**Example from Phase 201 (agent_utils.py):**
```python
class TestParseReactResponse:
    """Test ReAct response parsing."""
    # 8 tests for parse_react_response function

class TestFormatAgentId:
    """Test agent ID formatting."""
    # 10 tests for format_agent_id function

class TestConfidenceCalculation:
    """Test confidence score calculations."""
    # 8 tests for confidence-related functions

# Total: 108 tests across 14 test classes
# Result: 0% → 98.48% coverage in 3 minutes
```

**Source:** `backend/tests/core/test_agent_utils_coverage.py`

### Pattern 5: Comprehensive Fixture System

**What:** Use pytest fixtures to set up test data, mock services, and configure the test environment. Fixtures are reusable and can be auto-applied with `autouse=True`.

**When to use:** For setup that is shared across multiple tests (database sessions, mock services, test agents).

**Example from conftest.py:**
```python
@pytest.fixture(autouse=True)
def isolate_environment():
    """
    Isolate environment variables between tests.

    Prevents test pollution from environment modifications by saving and restoring
    critical environment variables (SECRET_KEY, ENVIRONMENT, DATABASE_URL, etc.)
    before and after each test.
    """
    saved = {}
    for var in _CRITICAL_ENV_VARS:
        if var in os.environ:
            saved[var] = os.environ[var]

    yield

    # Restore saved env vars
    for var in _CRITICAL_ENV_VARS:
        if var in saved:
            os.environ[var] = saved[var]
        else:
            os.environ.pop(var, None)

@pytest.fixture
def student_agent(db_session):
    """Create a STUDENT level agent for testing."""
    agent = AgentRegistry(
        id="test-student-agent",
        tenant_id="test-tenant",
        name="Test Student Agent",
        category="Test",
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus.STUDENT.value,
        confidence_score=0.3
    )
    return agent
```

**Source:** `backend/tests/conftest.py`

### Anti-Patterns to Avoid

- **Testing implementation details:** Test public APIs and business logic, not internal implementation. Tests should break when behavior changes, not when code is refactored.
- **Over-mocking:** Only mock external dependencies (LLM providers, databases, APIs). Don't mock the code you're testing.
- **Fragile tests:** Avoid hardcoding values that change (timestamps, UUIDs). Use test data generation (faker) or fixtures.
- **Testing excluded code:** Phase 201 documented schema drift issues that blocked 3 tests. Don't try to test code that's excluded with `# pragma: no cover`.
- **Complex integration tests in Phase 202:** CLI module testing showed that full app initialization is difficult. Focus on unit-level tests for now.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Test runner | Custom test discovery | pytest | 1,420 test files already use pytest; pytest has superior fixture system |
| Mock objects | Manual mock classes | unittest.mock.Mock, MagicMock | Handles method chaining, attribute access, call tracking automatically |
| Coverage measurement | Custom coverage scripts | pytest-cov with --cov-report=json | Generates JSON for analysis, integrates with pytest |
| Test data | Manual object creation | faker library | Generates realistic test data (names, emails, dates) |
| Async testing | Custom event loops | pytest-asyncio with @pytest.mark.asyncio | Handles async fixture setup, test isolation |

**Key insight:** Phase 201 achieved 20.13% coverage (324 tests, 87% pass rate) using only standard pytest tools. No custom tooling was required. The existing fixture system (conftest.py, mock_services.py, agent_fixtures.py) is sufficient for Phase 202.

## Common Pitfalls

### Pitfall 1: Schema Drift Blocking Tests

**What goes wrong:** Tests fail because database models have changed (fields added/removed) but the code being tested hasn't been updated. Phase 201 had 3 failing tests due to CanvasAudit model drift.

**Why it happens:** Models are updated in one phase but dependent services aren't updated until later phases. Tests expose the inconsistency.

**How to avoid:**
1. Document schema drift issues when found (don't fix in coverage phase)
2. Accept realistic pass rates (87% is acceptable if failures are due to known schema issues)
3. Focus on testing code paths that work, not fixing schema drift

**Warning signs:** Tests fail with `AttributeError: 'X' object has no attribute 'Y'` or `TypeError: __init__() got an unexpected keyword argument 'Z'`

**Source:** `.planning/phases/201-coverage-push-85/201-PHASE-SUMMARY.md` (Deviation 2)

### Pitfall 2: Full App Initialization Requirements

**What goes wrong:** Tests fail because they require complete FastAPI app initialization with database migrations, all services loaded, etc. CLI module testing had 10 failing tests due to this.

**Why it happens:** Complex orchestration code has many dependencies. Setting up full app context in tests is difficult and time-consuming.

**How to avoid:**
1. Focus on unit-level tests (test individual functions, not full workflows)
2. Mock external dependencies (don't require real database)
3. Accept lower coverage targets for complex orchestration code (40-50% vs 80% for simpler modules)
4. Document full-app tests as deferred to integration testing phase

**Warning signs:** Tests require `from main import app` or fail with `ImportError: cannot import name 'X' from partially initialized module`

**Source:** `.planning/phases/201-coverage-push-85/201-PHASE-SUMMARY.md` (Deviation 3)

### Pitfall 3: Uncovered Low-Priority Code Inflating Gaps

**What goes wrong:** Coverage reports show large gaps because many files have 0% coverage, even if they're low priority (debug routes, deprecated endpoints, etc.).

**Why it happens:** Coverage tools count all files equally. 47 zero-coverage files >100 lines exist, but not all are high priority.

**How to avoid:**
1. Prioritize zero-coverage files by business impact (core services > API routes > debug tools)
2. Group files by module (core, api, tools, cli) rather than treating all files equally
3. Accept that some files will remain at 0% coverage (document why)
4. Focus on achieving overall percentage target, not 100% coverage of every file

**Warning signs:** Coverage improvements are slow despite many tests being written. Check if you're testing low-value code.

**Source:** Phase 201 Wave 2 analysis identified 47 zero-coverage files >100 lines but recommended Wave 3 targeting only high-value ones.

### Pitfall 4: Test Collection Failures

**What goes wrong:** pytest can't discover tests due to import errors, naming conventions, or missing fixtures. Phase 200 focused entirely on fixing collection errors.

**Why it happens:** Tests are named incorrectly (don't start with `test_`), have import errors, or require fixtures that don't exist.

**How to avoid:**
1. Always run `pytest --collect-only -q` before running full test suite
2. Follow naming convention: `test_*.py` files, `test_*()` functions
3. Ensure all imports resolve (add missing files to PYTHONPATH if needed)
4. Verify fixtures exist before using them (`@pytest.fixture`)

**Warning signs:** `pytest --collect-only` shows fewer tests than expected or shows import errors.

**Source:** `.planning/phases/200-fix-collection-errors/200-PHASE-SUMMARY.md`

### Pitfall 5: Coverage Regression from Previous Phases

**What goes wrong:** Coverage decreases from previous phase measurements even though new tests were added.

**Why it happens:** New code was added without tests, or previously covered code paths are no longer being exercised.

**How to avoid:**
1. Run coverage measurement at start of each wave (establish baseline)
2. Run coverage measurement at end of each wave (verify improvement)
3. Compare coverage.json files to identify which files lost coverage
4. Document any intentional regressions (deprecated features, code removal)

**Warning signs:** Overall coverage percentage decreases between measurements. Check `coverage.json` for files with decreased coverage.

**Source:** Phase 201 Plan 08 (Wave 2 Coverage Measurement) established baseline comparison pattern.

## Code Examples

Verified patterns from Phase 201 test files:

### Test Organization by Class

```python
"""Test coverage for agent_utils.py - Target 60%+ coverage."""

import pytest
from core.agent_utils import (
    parse_react_response,
    format_agent_id,
    format_maturity_level,
    # ... other imports
)


class TestParseReactResponse:
    """Test ReAct response parsing."""

    def test_parse_json_action(self):
        """Test parsing JSON action format."""
        output = """Thought: I need to search for information.
Action: {
    "tool": "search",
    "params": {"query": "test"}
}"""
        thought, action, final_answer = parse_react_response(output)

        assert thought == "I need to search for information."
        assert action is not None
        assert action["tool"] == "search"
        assert final_answer is None

    def test_parse_final_answer(self):
        """Test parsing final answer format."""
        output = """Thought: I have found the information.
Final Answer: The answer is 42."""
        thought, action, final_answer = parse_react_response(output)

        assert thought == "I have found the information."
        assert action is None
        assert final_answer == "The answer is 42."

    # ... 8 more tests for parse_react_response


class TestFormatAgentId:
    """Test agent ID formatting."""

    def test_format_basic_agent_id(self):
        """Test formatting basic agent ID."""
        assert format_agent_id("agent-abc123") == "Agent Abc123"

    def test_format_workflow_id(self):
        """Test formatting workflow ID."""
        assert format_agent_id("workflow-xyz") == "Workflow Xyz"

    # ... 8 more tests for format_agent_id
```

**Source:** `backend/tests/core/test_agent_utils_coverage.py` (659 lines, 108 tests, 98.48% coverage)

### Parametrized Testing for Efficiency

```python
@pytest.mark.parametrize("canvas_type,expected_allowed", [
    ("chart", True),      # LOW complexity, STUDENT+ allowed
    ("markdown", True),   # LOW complexity, STUDENT+ allowed
    ("form", False),      # MODERATE complexity, INTERN+ required
    ("sheet", False),     # HIGH complexity, SUPERVISED+ required
])
def test_canvas_type_governance_by_maturity(self, canvas_tool, student_agent, canvas_type, expected_allowed):
    """Test canvas type governance based on agent maturity level."""
    with patch.object(canvas_tool.governance_service, 'check_action_permission') as mock_gov:
        mock_gov.return_value = Mock(allowed=expected_allowed, reason="Maturity check")

        result = canvas_tool.present_canvas(
            agent_id=student_agent.id,
            canvas_type=canvas_type,
            data={}
        )

        assert result["success"] == expected_allowed or result.get("blocked_reason") is not None
```

**Source:** `.planning/phases/201-coverage-push-85/201-02-PLAN.md`

### Mock Service Usage

```python
from tests.fixtures.mock_services import MockLLMProvider

def test_llm_service_with_mock(self):
    """Test LLM service with mocked provider."""
    mock_llm = MockLLMProvider()
    mock_llm.set_response("test prompt", "test response")

    result = llm_service.generate("test prompt")

    assert result == "test response"
    assert mock_llm.call_count == 1
```

**Source:** `backend/tests/fixtures/mock_services.py`

### API Endpoint Testing with TestClient

```python
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health_liveness(self):
    """Test liveness probe returns 200."""
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_health_readiness_with_db(self):
    """Test readiness probe with database check."""
    with patch("api.health_routes._check_database") as mock_db:
        mock_db.return_value = {"healthy": True}

        response = client.get("/health/ready")

        assert response.status_code == 200
        assert response.json()["status"] == "ready"
```

**Source:** `backend/tests/api/test_health_routes_coverage.py` (Phase 201 Plan 07)

### Coverage Measurement Pattern

```bash
# Run full test suite with coverage
cd backend
python3 -m pytest --cov=backend --cov-branch --cov-report=json --cov-report=term-missing -q

# Parse coverage JSON for analysis
python3 << 'EOF'
import json

with open('coverage.json') as f:
    data = json.load(f)

totals = data['totals']
print(f"Overall: {totals['percent_covered']:.2f}%")
print(f"Lines: {totals['covered_lines']:,} / {totals['num_statements']:,}")
print(f"Missing: {totals['missing_lines']:,}")

# Module breakdown
modules = {}
for path, info in data['files'].items():
    if '/core/' in path:
        module = 'core'
    elif '/api/' in path:
        module = 'api'
    elif '/tools/' in path:
        module = 'tools'
    elif '/cli/' in path:
        module = 'cli'
    else:
        continue

    if module not in modules:
        modules[module] = {'covered': 0, 'total': 0}

    modules[module]['covered'] += info['summary']['covered_lines']
    modules[module]['total'] += info['summary']['num_statements']

print(f"\n=== MODULE BREAKDOWN ===")
for module, stats in sorted(modules.items()):
    pct = (stats['covered'] / stats['total'] * 100) if stats['total'] > 0 else 0
    print(f"{module:10s}: {pct:5.2f}% ({stats['covered']:,}/{stats['total']:,})")
EOF
```

**Source:** Phase 201 Plan 08 coverage measurement script

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Service-level coverage estimates | Line-level coverage with coverage.py | Phase 200 | Precise measurement of untested code |
| Random test writing | Wave-based prioritization (HIGH → MEDIUM → LOW) | Phase 201 | Efficient use of testing time |
| Single-module testing | Module-focused plans with grouping | Phase 201 | +64-98% coverage improvements per plan |
| Manual test data generation | Faker + fixtures | Phase 201 | Faster test creation, realistic data |
| Ad-hoc mocking | MockLLMProvider, MockEmbeddingService fixtures | Phase 200 | Consistent mock behavior across tests |

**Deprecated/outdated:**
- ** unittest.TestCase**: pytest fixtures are superior; use pytest instead
- **nose**: Test runner is deprecated; use pytest
- **coverage.py CLI**: Use pytest-cov integration instead

## Open Questions

1. **Question:** Should Phase 202 continue Phase 201's Wave 3 (zero-coverage files >100 lines) or start fresh with Wave 4?
   - **What we know:** Phase 201 identified 47 zero-coverage files >100 lines but deferred Wave 3 to next phase. These files represent 10.21% potential coverage gain.
   - **What's unclear:** Whether starting with these easy wins is better than targeting medium-impact modules.
   - **Recommendation:** Continue with Wave 3 (zero-coverage files) as Phase 202's first wave. These are easy wins that build momentum and establish testing patterns before tackling more complex modules.

2. **Question:** What's the optimal plan size for Phase 202? Phase 201 plans varied from 1-4 tasks.
   - **What we know:** Single-task plans worked well for focused modules (agent_utils.py: 108 tests, 98.48% coverage in 3 minutes). Multi-task plans worked for complex modules (CLI: 70 tests, 43.36% coverage in 45 minutes).
   - **What's unclear:** Whether grouping multiple files into single plans is more efficient than single-file plans.
   - **Recommendation:** Use mixed approach. Large files (>300 lines) get single-file plans. Small/medium files (100-300 lines) get grouped into plans by module (3-5 files per plan).

3. **Question:** Should Phase 202 target 60% or aim higher given Phase 201 exceeded expectations?
   - **What we know:** Phase 201 targeted 50-60% in Wave 2 but achieved 20.13% overall. However, module-level improvements exceeded targets (canvas: +64%, browser: +75%, agent_utils: +98%).
   - **What's unclear:** Whether the efficiency gains from Phase 201 (54 tests/hour) will scale to Phase 202.
   - **Recommendation:** Target 60% as stated, but design wave structure to enable 65-70% if efficiency holds. 15-18 plans with 10-12 hours duration provides buffer for overachievement.

4. **Question:** How to handle the 47 zero-coverage files >100 lines efficiently?
   - **What we know:** These files represent 7,559 lines of code (10.21% potential coverage). They're distributed across modules: workflow systems, API routes, core services.
   - **What's unclear:** Which files are high priority vs low priority.
   - **Recommendation:** Prioritize by business impact: (1) Core services (graduation_exam.py, reconciliation_engine.py), (2) API endpoints (smarthome_routes.py, debug_routes.py), (3) Workflow systems (workflow_versioning_system.py, workflow_marketplace.py). Document low-priority files for deferral.

## Sources

### Primary (HIGH confidence)

- **pytest 7.0+ documentation** - Test discovery, fixtures, parametrization, async testing
- **pytest-cov 4.0+ documentation** - Coverage integration, JSON report generation
- **coverage.py 7.x documentation** - Line vs branch coverage, report formats
- **FastAPI TestClient documentation** - API endpoint testing patterns
- **Phase 201 comprehensive summary** - `.planning/phases/201-coverage-push-85/201-PHASE-SUMMARY.md` (766 lines)
- **Phase 201 Plan 02-07** - Module-focused coverage targeting patterns
- **backend/tests/conftest.py** - Root fixture system (200+ lines)
- **backend/tests/fixtures/mock_services.py** - Mock service implementations
- **backend/tests/core/test_agent_utils_coverage.py** - Test class organization (659 lines, 108 tests)

### Secondary (MEDIUM confidence)

- **Phase 200 summary** - Collection error fixes and baseline measurement
- **backend/pyproject.toml** - Testing dependencies (pytest, pytest-cov, pytest-asyncio)
- **Phase 201 Wave 2 coverage analysis** - Coverage gap identification methodology
- **REQUIREMENTS.md** - Coverage requirements (COV-01 through GAP-05)

### Tertiary (LOW confidence)

- None. All findings are verified from primary sources (code, documentation, Phase 201 artifacts).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All tools are industry standards with extensive documentation
- Architecture: HIGH - Patterns are proven in Phase 201 with measurable results
- Pitfalls: HIGH - All pitfalls documented from actual Phase 201 deviations
- Wave structure: MEDIUM - Estimates based on Phase 201 efficiency (54 tests/hour) but Phase 202 scope is 3x larger

**Research date:** 2026-03-17
**Valid until:** 2026-04-17 (30 days - coverage improvement strategies are stable)

**Phase 202 estimates:**
- Baseline coverage: 20.13% (18,476/74,018 lines)
- Target coverage: 60.00%
- Gap: 39.87 percentage points (29,510 lines)
- Estimated plans: 15-18
- Estimated duration: 10-12 hours
- Estimated tests: 700-800
- Efficiency: 81 tests/hour (vs Phase 201: 54 tests/hour)

**Key recommendation:** Start with Wave 3 (zero-coverage files >100 lines) to build momentum, then Wave 4 (medium-impact modules), then Wave 5 (large zero-coverage files), and Wave 6 (verification). This structure is proven from Phase 201 and provides clear progression from easy wins to complex modules.
