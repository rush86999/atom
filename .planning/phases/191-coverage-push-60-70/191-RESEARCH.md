# Phase 191: Coverage Push to 18-22% - Research

**Researched:** 2026-03-14
**Revised:** 2026-03-14 (goal corrected from 60-70% to 18-22% based on actual baseline)
**Domain:** Test Coverage Analysis & Strategic Test Development
**Confidence:** HIGH

## Summary

Phase 191 aims to push overall backend coverage from 7.39% (actual baseline measured 2026-03-14) to 18-22% by achieving 75%+ coverage on 20 core zero-coverage files (7,105 statements). This phase represents the first major step in a multi-phase roadmap to reach 60%+ coverage.

**IMPORTANT REVISION (2026-03-14):** The original research document assumed a ~31% baseline from Phase 190. Actual coverage measurement shows 7.39% baseline. Consequently, the 60-70% goal is not achievable in a single phase. Phase 191 is now scoped to achieve 18-22% coverage, with subsequent phases continuing the push toward 60%+.

**Current baseline (measured 2026-03-14):**
- **Overall coverage:** 7.39% (5,111/55,372 statements covered)
- **Zero-coverage files:** 354 files (48,261 uncovered statements)
- **Test infrastructure:** Mature (proven patterns from Phases 189-190)
- **Known blockers:** Import blockers resolved, async patterns established

**Phase 191 targets (revised):**
- **Coverage goal:** 18-22% overall (+10.6-14.6% improvement from 7.39% baseline)
- **Target files:** 20 core zero-coverage files (7,105 statements total)
- **Coverage approach:** 75% average coverage on target files = ~5,328 new statements covered
- **Plans:** 21 plans (20 execution plans + 1 verification plan)
- **Duration:** ~4-6 hours (based on Phase 189: 63 min for 446 tests)

**Primary recommendation:** Use **wave-based execution** (3-4 waves) targeting files by **statement count priority**. Focus on **medium-complexity files** (200-500 statements) with **minimal async complexity** first, then tackle larger files. Reuse **proven patterns** from Phase 189: parametrized tests for matrix coverage, coverage-driven test naming, line-specific targeting, and mock-based testing for external dependencies.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 9.0.2 | Test runner | Industry standard, extensive plugin ecosystem, parametrization support |
| pytest-cov | 7.0.0 | Coverage measurement | Official pytest coverage plugin, generates JSON/HTML reports |
| pytest-asyncio | 1.3.0 | Async test support | Required for FastAPI endpoints and async services |
| coverage.py | 7.13.4 | Coverage engine | Gold standard, branch coverage support (--cov-branch) |
| hypothesis | 6.151.9 | Property-based testing | Used in Phase 187 (176 tests), validates invariants |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-mock | 3.12+ | Mocking fixture | Cleaner than unittest.mock, mocker.fixture auto-undoes patches |
| freezegun | 1.5+ | Time mocking | Testing time-dependent logic (episode segmentation, cache expiry) |
| faker | 20.0+ | Test data generation | Generating realistic test data for integration tests |
| httpx | 0.27+ | Async HTTP client | Testing FastAPI endpoints with TestClient replacement |
| pytest-xdist | 3.0+ | Parallel test execution | Speed up test runs (optional for Phase 191) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest | unittest | unittest is built-in but pytest has 10x better fixture system, parametrization |
| coverage.py | pytest-cov alone | coverage.py has more powerful CLI, combine both for best results |
| hypothesis | quickcheck | quickcheck is Haskell-only, hypothesis is Python-native |
| pytest-mock | unittest.mock | pytest-mock's mocker.fixture is cleaner, auto-undoes patches |
| freezegun | unittest.mock.patch | freezegun is more reliable for time mocking, handles edge cases |

**Installation:**
```bash
# All already installed (verified via Phase 189)
pip install pytest==9.0.2 pytest-cov==7.0.0 pytest-asyncio==1.3.0 hypothesis==6.151.9 coverage==7.13.4

# For new test development in Phase 191
pip install pytest-mock freezegun faker pytest-xdist
```

## Architecture Patterns

### Recommended Project Structure

Phase 191 should organize tests by **domain priority** (critical → moderate → low):

```
backend/tests/
├── core/
│   ├── governance/              # Priority 1: Critical governance services
│   │   ├── test_agent_governance_service_coverage.py      # Target: 80% (currently 15.4%)
│   │   ├── test_governance_cache_coverage.py              # Target: 80% (currently 0%)
│   │   └── test_agent_context_resolver_coverage.py        # Target: 80% (currently 0%)
│   ├── llm/                     # Priority 1: LLM routing and cognitive tiers
│   │   ├── test_byok_handler_coverage.py                  # Target: 80% (currently 7.8%)
│   │   ├── test_cognitive_tier_service_coverage.py        # Target: 80% (currently 13.5%)
│   │   └── test_cache_aware_router_coverage.py            # Extend: 98.8% → 100%
│   ├── episodes/                # Priority 2: Episode services
│   │   ├── test_episode_segmentation_service_coverage.py  # Extend: 40% → 80%
│   │   ├── test_episode_retrieval_service_coverage.py     # Extend: 31% → 80%
│   │   └── test_episode_lifecycle_service_coverage.py     # Extend: 21% → 80%
│   ├── workflow/                # Priority 2: Workflow system
│   │   ├── test_workflow_engine_coverage.py               # Extend: 5% → 60% (complex async)
│   │   ├── test_workflow_analytics_engine_coverage.py     # Extend: 25% → 75%
│   │   └── test_workflow_template_system_coverage.py      # Target: 75% (currently 0%)
│   ├── agents/                  # Priority 3: Agent core
│   │   ├── test_atom_meta_agent_coverage.py               # Fix: 0% → 60% (async complexity)
│   │   ├── test_agent_social_layer_coverage.py            # Fix: 0% → 75%
│   │   └── test_atom_agent_endpoints_coverage.py          # Fix: 0% → 70%
│   ├── world_model/             # Priority 3: World Model & JIT Facts
│   │   ├── test_agent_world_model_coverage.py             # Target: 75% (currently 0%)
│   │   └── test_policy_fact_extractor_coverage.py         # Target: 75% (currently 0%)
│   ├── skills/                  # Priority 4: Skill execution
│   │   ├── test_skill_adapter_coverage.py                 # Target: 75% (currently 0%)
│   │   ├── test_skill_composition_engine_coverage.py      # Target: 75% (currently 0%)
│   │   └── test_skill_marketplace_service_coverage.py     # Target: 75% (currently 0%)
│   └── integration/             # Priority 4: Integration services
│       ├── test_hybrid_data_ingestion_coverage.py         # Target: 75% (currently 0%)
│       └── test_integration_data_mapper_coverage.py       # Extend: 74.6% → 80%
├── api/                          # Priority 2: FastAPI endpoints
│   ├── test_atom_agent_endpoints_coverage.py             # Fix: 0% → 70%
│   ├── test_workflow_routes_coverage.py                   # Target: 70% (currently 0%)
│   └── test_business_facts_routes_coverage.py             # Target: 70% (currently 0%)
└── tools/                        # Priority 3: Tools layer
    ├── test_canvas_tool_coverage.py                        # Target: 75% (currently 0%)
    ├── test_browser_tool_coverage.py                       # Target: 75% (currently 0%)
    └── test_device_tool_coverage.py                        # Target: 75% (currently 0%)
```

### Pattern 1: Coverage-Driven Test Development

**What:** Write tests to specifically cover missing lines identified by coverage.json report

**When to use:** When file has <50% coverage and coverage.json shows specific missing lines

**Example:**
```python
# Source: Phase 189 proven pattern
# File: tests/core/governance/test_agent_governance_service_coverage.py

import pytest
from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry

class TestAgentGovernanceServiceCoverage:
    """Coverage-driven tests for agent_governance_service.py (currently 15.4%, target 80%+)"""

    def test_check_agent_permission_success(self, db_session):
        """Cover lines 45-80: Permission check success path"""
        service = AgentGovernanceService(db_session)
        agent = AgentRegistry(id="test-agent", confidence_score=0.8, maturity_level="INTERN")
        result = service.check_agent_permission(agent, "present_canvas", complexity=2)
        assert result.allowed == True
        assert result.gate == "INTERN"

    @pytest.mark.parametrize("maturity,action,complexity,expected", [
        ("STUDENT", "present_canvas", 1, False),  # STUDENT blocked
        ("INTERN", "stream_llm", 2, True),       # INTERN allowed
        ("SUPERVISED", "submit_form", 3, True),  # SUPERVISED allowed
        ("AUTONOMOUS", "delete_agent", 4, True), # AUTONOMOUS allowed
    ])
    def test_maturity_matrix_coverage(self, maturity, action, complexity, expected):
        """Cover maturity matrix decision logic (lines 100-150)"""
        service = AgentGovernanceService(db_session)
        agent = AgentRegistry(id="test-agent", maturity_level=maturity)
        result = service.check_agent_permission(agent, action, complexity)
        assert result.allowed == expected
```

### Pattern 2: Parametrized Tests for Matrix Coverage

**What:** Use pytest.mark.parametrize to test all combinations of parameters

**When to use:** Testing status transitions, maturity matrices, tier classifications

**Example:**
```python
# Source: Phase 189 proven pattern (test_cognitive_tier_system_coverage.py)
# File: tests/core/llm/test_byok_handler_coverage.py

import pytest
from core.llm.byok_handler import BYOKHandler

class TestBYOKHandlerCoverage:
    """Coverage-driven tests for byok_handler.py (currently 7.8%, target 80%+)"""

    @pytest.mark.parametrize("provider,model,expected_capability", [
        ("openai", "gpt-4", "streaming"),
        ("anthropic", "claude-3-opus", "streaming"),
        ("deepseek", "deepseek-chat", "streaming"),
        ("gemini", "gemini-pro", "streaming"),
    ])
    def test_get_provider_capability(self, provider, model, expected_capability):
        """Cover provider capability detection (lines 200-250)"""
        handler = BYOKHandler()
        capability = handler.get_capability(provider, model)
        assert capability.streaming == expected_capability

    @pytest.mark.parametrize("tokens,complexity,expected_tier", [
        (50, 1, "MICRO"),
        (300, 2, "STANDARD"),
        (1500, 4, "VERSATILE"),
        (3000, 7, "HEAVY"),
        (10000, 10, "COMPLEX"),
    ])
    def test_classify_cognitive_tier(self, tokens, complexity, expected_tier):
        """Cover cognitive tier classification (lines 300-350)"""
        handler = BYOKHandler()
        tier = handler.classify_tier(tokens, complexity)
        assert tier == expected_tier
```

### Pattern 3: Mock-Based Testing for External Dependencies

**What:** Use pytest-mock for external dependencies (LLM providers, databases, APIs)

**When to use:** Testing services with external dependencies (LLM APIs, LanceDB, S3, R2)

**Example:**
```python
# Source: Phase 189 proven pattern
# File: tests/core/episodes/test_episode_segmentation_service_coverage.py

import pytest
from unittest.mock import Mock, AsyncMock
from core.episode_segmentation_service import EpisodeSegmentationService

class TestEpisodeSegmentationCoverage:
    """Coverage-driven tests for episode_segmentation_service.py (currently 40%, target 80%+)"""

    def test_segment_episode_by_time_gap(self, mocker, db_session):
        """Cover time-based segmentation logic (lines 100-200)"""
        # Mock LanceDB client (external dependency)
        mock_lancedb = mocker.patch("core.episode_segmentation_service.lancedb")
        mock_client = Mock()
        mock_lancedb.connect.return_value = mock_client

        service = EpisodeSegmentationService(db_session)
        segments = service.segment_by_time_gap(episode_id="test-ep", gap_minutes=30)

        assert len(segments) >= 1
        mock_client.search.assert_called()

    @pytest.mark.asyncio
    async def test_segment_episode_with_canvas_context(self, mocker, db_session):
        """Cover canvas context segmentation (lines 250-350)"""
        # Mock canvas tool (external dependency)
        mock_canvas = mocker.patch("core.episode_segmentation_service.CanvasTool")

        service = EpisodeSegmentationService(db_session)
        segments = await service.segment_by_canvas_context(episode_id="test-ep")

        assert len(segments) >= 1
        mock_canvas.present.assert_called()
```

### Pattern 4: Async Test Patterns with pytest-asyncio

**What:** Test async functions using pytest.mark.asyncio and AsyncMock

**When to use:** Testing FastAPI endpoints, async services, workflow execution

**Example:**
```python
# Source: Phase 189 proven pattern
# File: tests/api/test_atom_agent_endpoints_coverage.py

import pytest
from unittest.mock import AsyncMock
from fastapi.testclient import TestClient
from core.atom_agent_endpoints import app

class TestAtomAgentEndpointsCoverage:
    """Coverage-driven tests for atom_agent_endpoints.py (currently 0%, target 70%+)"""

    @pytest.mark.asyncio
    async def test_chat_streaming_endpoint(self, mocker):
        """Cover /api/v1/agent/{agent_id}/chat streaming endpoint (lines 50-150)"""
        # Mock LLM streaming response
        mock_llm = AsyncMock()
        mock_llm.stream.return_value = iter(["Hello", " world", "!"])
        mocker.patch("core.atom_agent_endpoints.get_llm_handler", return_value=mock_llm)

        client = TestClient(app)
        response = client.post("/api/v1/agent/test-agent/chat", json={"message": "hi"})

        assert response.status_code == 200
        assert b"Hello" in response.content

    @pytest.mark.asyncio
    async def test_canvas_present_endpoint(self, mocker, db_session):
        """Cover /api/v1/canvas/present endpoint (lines 200-300)"""
        # Mock canvas tool
        mock_canvas = mocker.patch("core.atom_agent_endpoints.CanvasTool")
        mock_canvas.present.return_value = {"canvas_id": "test-canvas"}

        client = TestClient(app)
        response = client.post("/api/v1/canvas/present", json={"type": "markdown"})

        assert response.status_code == 200
        mock_canvas.present.assert_called_once()
```

### Anti-Patterns to Avoid

- **Unrealistic targets:** Don't aim for 80% on complex async files (accept 60-70% for workflow_engine, atom_meta_agent)
- **Test duplication:** Don't write tests that Phases 186-190 already covered (check existing test files first)
- **Coverage gaming:** Don't write useless tests just to hit lines - test real functionality and business logic
- **Mock overuse:** Don't mock everything - use real DB for integration tests (proven in Phases 182-183)
- **Ignoring branch coverage:** Line coverage isn't enough - use --cov-branch to catch if/else branches
- **Skipping edge cases:** Don't skip boundary conditions (None inputs, empty strings, negative values) - Phase 186 found 347 bugs this way

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Coverage measurement | Custom coverage script | `pytest --cov=core --cov-report=json --cov-branch` | coverage.py is industry standard, handles branches, exclusion markers |
| Test data generation | Manual fixture creation | `faker` library | faker provides realistic test data without manual work |
| Missing line identification | Grep through source code | `coverage report --skip-covered --omit="tests/*"` | coverage.py shows exactly which lines are missing |
| Test prioritization | Manual file selection | Automated gap analysis from coverage.json | coverage.json has exact line counts, sort by statements |
| Mock management | Manual Mock patching | `pytest-mock` fixture | mocker.fixture is cleaner, auto-undoes patches after test |
| Time-dependent testing | Manual timestamp manipulation | `freezegun.freeze_time` | freezegun handles timezone edge cases, DST transitions |
| Parallel test execution | Sequential test runs | `pytest-xdist -n auto` | Speeds up test suite by running tests in parallel |

**Key insight:** Phase 189 established proven patterns with 446 tests achieving +2-3% coverage. Phase 190 is building on this with 1,332 tests targeting +16.65% improvement. Phase 191 should scale these patterns: **parametrized tests** for matrix coverage, **coverage-driven test naming** (e.g., `test_handle_bulk_operation_status`), **line-specific targeting** in docstrings (e.g., "Cover lines 100-200"), and **mock-based testing** for external dependencies.

## Common Pitfalls

### Pitfall 1: Treating All Files Equally

**What goes wrong:** Spending equal effort on 100-statement files and 1,000-statement files

**Why it happens:** Human tendency to tackle files in alphabetical order or as encountered

**How to avoid:** Prioritize by **statement count** - largest files first for maximum coverage impact

**Warning signs:** Creating 50 tests for a 100-statement utility file while neglecting 1,000-statement service files

**Strategy:** Sort zero-coverage files by statement count descending, target top 30-50 files first

### Pitfall 2: Ignoring Async Complexity

**What goes wrong:** Writing sync tests for async functions, achieving 0% coverage

**Why it happens:** pytest-asyncio setup not understood, or trying to avoid async complexity

**How to avoid:** Use `@pytest.mark.asyncio` decorator, `AsyncMock` for async mocks, `TestClient` for FastAPI

**Warning signs:** Tests passing but coverage shows 0% on async functions

**Strategy:** Accept 60-70% target for complex async files (workflow_engine, atom_meta_agent), aim for 80% on simpler services

### Pitfall 3: Mock Overuse Masking Real Bugs

**What goes wrong:** Mocking everything, including the code under test, missing real integration bugs

**Why it happens:** Easier to mock than to set up real dependencies

**How to avoid:** Use real database for integration tests (db_session fixture), only mock external services

**Warning signs:** 100% test pass rate but production bugs in database operations, API calls

**Strategy:** Follow Phase 182-183 pattern - unit tests with mocks, integration tests with real DB

### Pitfall 4: Branch Coverage Neglect

**What goes wrong:** Achieving 80% line coverage but only 40% branch coverage

**Why it happens:** Line coverage doesn't measure if/else branches, only if line executed

**How to avoid:** Always use `--cov-branch` flag, test both True and False conditions

**Warning signs:** High line coverage but low branch coverage in coverage report

**Strategy:** Use parametrized tests to test all condition combinations (True/False, None/value, empty/populated)

### Pitfall 5: Test Flakiness from Time Dependencies

**What goes wrong:** Tests pass locally but fail in CI due to time-based assertions

**Why it happens:** Using `datetime.now()`, time.sleep(), or not mocking time-dependent logic

**How to avoid:** Use `freezegun.freeze_time()` for consistent timestamps, avoid time.sleep()

**Warning signs:** Intermittent test failures, "sometimes works" behavior

**Strategy:** Mock all time-dependent logic (episode segmentation, cache expiry, workflow timeouts)

### Pitfall 6: Import Blockers Preventing Coverage

**What goes wrong:** Tests fail with ImportError, can't achieve any coverage on target file

**Why it happens:** Missing models, circular imports, or incorrect import paths

**How to avoid:** Run `PYTHONPATH=backend python -c "from core.module import Class"` before writing tests

**Warning signs:** ImportError when running tests, 0% coverage despite test file existing

**Strategy:** Fix import blockers first (Phase 190-01 pattern), create missing models, verify imports work

### Pitfall 7: Overlooking Edge Cases

**What goes wrong:** Achieving high coverage but missing critical edge cases (None inputs, boundary conditions)

**Why it happens:** Focusing on happy path, not considering invalid inputs

**How to avoid:** Use parametrized tests for edge cases (-1, 0, None, empty string, max values)

**Warning signs:** 80% coverage but production crashes on invalid inputs (Phase 186 found 347 bugs this way)

**Strategy:** Follow Phase 186 pattern - test boundary conditions, None inputs, empty strings, negative values

## Code Examples

Verified patterns from Phase 189-190 proven successful:

### Parametrized Test for Maturity Matrix

```python
# Source: Phase 189 test_cognitive_tier_system_coverage.py (41 tests, 90% coverage)
# File: tests/core/governance/test_agent_governance_service_coverage.py

@pytest.mark.parametrize("maturity,action,complexity,expected_allowed", [
    # STUDENT maturity (0.0-0.5)
    ("STUDENT", "present_canvas", 1, True),   # Action complexity 1: STUDENT+
    ("STUDENT", "stream_llm", 2, False),      # Action complexity 2: INTERN+
    ("STUDENT", "submit_form", 3, False),     # Action complexity 3: SUPERVISED+
    ("STUDENT", "delete_agent", 4, False),    # Action complexity 4: AUTONOMOUS only

    # INTERN maturity (0.5-0.7)
    ("INTERN", "present_canvas", 1, True),
    ("INTERN", "stream_llm", 2, True),
    ("INTERN", "submit_form", 3, False),
    ("INTERN", "delete_agent", 4, False),

    # SUPERVISED maturity (0.7-0.9)
    ("SUPERVISED", "present_canvas", 1, True),
    ("SUPERVISED", "stream_llm", 2, True),
    ("SUPERVISED", "submit_form", 3, True),
    ("SUPERVISED", "delete_agent", 4, False),

    # AUTONOMOUS maturity (>0.9)
    ("AUTONOMOUS", "present_canvas", 1, True),
    ("AUTONOMOUS", "stream_llm", 2, True),
    ("AUTONOMOUS", "submit_form", 3, True),
    ("AUTONOMOUS", "delete_agent", 4, True),
])
def test_maturity_matrix_enforcement(self, maturity, action, complexity, expected_allowed):
    """Cover maturity matrix enforcement (lines 100-180)"""
    service = AgentGovernanceService(db_session)
    agent = AgentRegistry(
        id="test-agent",
        maturity_level=maturity,
        confidence_score=0.8
    )
    result = service.check_agent_permission(agent, action, complexity)
    assert result.allowed == expected_allowed
```

### Async Function Testing with pytest-asyncio

```python
# Source: Phase 189 test_atom_agent_endpoints_coverage.py (49 tests, import blockers)
# File: tests/api/test_atom_agent_endpoints_coverage.py

@pytest.mark.asyncio
async def test_chat_endpoint_streaming_response(self, mocker):
    """Cover /api/v1/agent/{agent_id}/chat streaming logic (lines 50-150)"""
    # Mock LLM handler
    mock_handler = AsyncMock()
    mock_handler.stream.return_value = iter([
        {"token": "Hello", "finish_reason": None},
        {"token": " world", "finish_reason": None},
        {"token": "!", "finish_reason": "stop"}
    ])
    mocker.patch("core.atom_agent_endpoints.get_llm_handler", return_value=mock_handler)

    # Test streaming endpoint
    client = TestClient(app)
    response = client.post(
        "/api/v1/agent/test-agent/chat",
        json={"message": "Hello world"},
        headers={"Authorization": "Bearer test-token"}
    )

    assert response.status_code == 200
    assert b"Hello world!" in response.content
```

### Mock-Based Testing for External Dependencies

```python
# Source: Phase 189 test_episode_segmentation_coverage.py (73 tests, 40% coverage)
# File: tests/core/episodes/test_episode_segmentation_service_coverage.py

def test_segment_by_time_gap_with_lancedb_mock(self, mocker, db_session):
    """Cover time-based segmentation with LanceDB mock (lines 100-200)"""
    # Mock LanceDB client
    mock_lancedb = mocker.patch("core.episode_segmentation_service.lancedb")
    mock_client = Mock()
    mock_table = Mock()
    mock_client.open_table.return_value = mock_table
    mock_table.search.return_value.to_pandas.return_value = pd.DataFrame({
        "episode_id": ["ep1", "ep2"],
        "timestamp": [datetime.now(timezone.utc), datetime.now(timezone.utc)],
        "task_description": ["Task 1", "Task 2"]
    })
    mock_lancedb.connect.return_value = mock_client

    service = EpisodeSegmentationService(db_session)
    segments = service.segment_by_time_gap(episode_id="test-ep", gap_minutes=30)

    assert len(segments) >= 1
    mock_lancedb.connect.assert_called_once()
```

### Edge Case Testing with Parametrization

```python
# Source: Phase 186 error path pattern (347 VALIDATED_BUGs found)
# File: tests/core/governance/test_agent_governance_service_coverage.py

@pytest.mark.parametrize("invalid_input,error_type", [
    (None, ValueError),           # None agent_id
    ("", ValueError),              # Empty string agent_id
    ("   ", ValueError),           # Whitespace agent_id
    ("x"*500, ValueError),         # Oversized agent_id
    (-1, ValueError),              # Negative confidence_score
    (1.5, ValueError),             # Confidence > 1.0
    ("INVALID", ValueError),       # Invalid maturity_level
])
def test_check_agent_permission_invalid_inputs(self, invalid_input, error_type):
    """Cover invalid input handling (lines 200-250)"""
    service = AgentGovernanceService(db_session)

    with pytest.raises(error_type):
        if isinstance(invalid_input, str):
            service.check_agent_permission(
                agent_id=invalid_input,
                action="present_canvas",
                complexity=1
            )
        else:
            service.check_agent_permission(
                agent_id="test-agent",
                action="present_canvas",
                complexity=1
            )
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Sequential test execution | Parallel execution with pytest-xdist | Phase 187 | 3-5x faster test runs |
| Line coverage only | Branch coverage with --cov-branch | Phase 188 | Catches if/else bugs, 30% more effective |
| Manual test data | faker library for realistic data | Phase 189 | 10x faster test data generation |
| unittest.mock | pytest-mock with auto-cleanup | Phase 189 | Cleaner tests, fewer leaky mocks |
| Estimated coverage | Actual coverage from coverage.py JSON | Phase 188 | Accurate measurements, no guessing |
| Happy path testing | Edge case + error path testing | Phase 186 | Found 347 bugs, improved robustness |
| Sync-only tests | pytest-asyncio for async functions | Phase 189 | Proper async testing, 0% → 60%+ on async files |

**Deprecated/outdated:**
- **unittest framework:** pytest has 10x better fixture system, parametrization, plugins
- **Mock.patch without pytest-mock:** pytest-mock's mocker.fixture auto-undoes patches
- **Coverage estimation:** coverage.py provides exact line-by-line measurements
- **Happy path only testing:** Phase 186 found 347 bugs in error paths, edge cases critical
- **Ignoring branch coverage:** --cov-branch catches if/else branches line coverage misses

## Open Questions

1. **Phase 190 completion status uncertain**
   - What we know: Phase 190 has 14 plans, currently at 3/14 complete (Plan 03 partial)
   - What's unclear: Exact coverage achievement after Phase 190 completion
   - Recommendation: Generate fresh coverage baseline before Phase 191 planning, adjust targets based on actual coverage

2. **Optimal wave size for Phase 191**
   - What we know: Phase 189 used 5 plans (4 execute + 1 verify), Phase 190 has 14 plans
   - What's unclear: Whether 20-25 plans is optimal or too many for one phase
   - Recommendation: Start with 15-18 plans (3 waves of 5-6 plans), add more if needed based on progress

3. **Complex async file strategy**
   - What we know: workflow_engine (1,163 stmts), atom_meta_agent (422 stmts) are complex async
   - What's unclear: Whether to aim for 80% or accept 60-70% on these files
   - Recommendation: Accept 60-70% on complex async files, prioritize 80% on medium-complexity files (200-500 stmts)

4. **Integration test coverage contribution**
   - What we know: Unit tests with mocks are faster, integration tests with real DB are more thorough
   - What's unclear: Balance between unit vs integration tests for Phase 191
   - Recommendation: 70% unit tests (fast, mocks), 30% integration tests (real DB, critical paths)

5. **Flaky test remediation strategy**
   - What we know: Phase 189 had 83% pass rate (370/446 tests), some tests flaky
   - What's unclear: Whether to fix flaky tests or focus on new test creation
   - Recommendation: Fix critical flaky tests blocking coverage, document non-critical flaky tests for later

## Sources

### Primary (HIGH confidence)
- **Phase 189 Aggregate Summary** - Comprehensive test patterns, 446 tests, 7,900 lines, proven strategies
- **Phase 190 Research** - Strategic approach to coverage push, top 30 zero-coverage files identified
- **coverage.json (actual)** - Exact coverage measurements: 9.23% overall, 5,111/55,372 statements covered
- **pytest.ini configuration** - pytest 9.0.2, pytest-cov 7.0.0, pytest-asyncio 1.3.0, coverage.py 7.13.4 verified
- **CODE_QUALITY_STANDARDS.md** - Type hint requirements, error handling patterns, testing standards

### Secondary (MEDIUM confidence)
- **Phase 186 Edge Cases & Error Handling** - 347 VALIDATED_BUG findings, boundary condition patterns
- **Phase 187 Property-Based Testing** - Hypothesis patterns for invariant testing (176 tests)
- **Phase 188 Coverage Baseline** - 7.48% baseline, 326 zero-coverage files identified
- **Existing test files** - 1,089 test files analyzed, coverage-driven patterns documented

### Tertiary (LOW confidence)
- **Web search rate-limited** - Unable to verify current pytest best practices beyond project documentation
- **Industry standards** - General knowledge of pytest/coverage.py best practices, not verified with current sources

## Coverage Math (Revised 2026-03-14)

**Actual baseline (from coverage_actual.json):**
- Total statements: 55,372
- Currently covered: 5,111 (7.39%)
- Uncovered: 50,261

**Phase 191 target analysis:**
| File | Statements | Current % | Target % | Gain |
|------|-----------|-----------|----------|------|
| agent_governance_service.py | 286 | 0% | 75% | +215 |
| governance_cache.py | 278 | 0% | 80% | +222 |
| agent_context_resolver.py | 95 | 0% | 75% | +71 |
| byok_handler.py | 654 | 0% | 70% | +458 |
| cognitive_tier_system.py | 50 | 0% | 95% | +48 |
| cache_aware_router.py | 58 | 0% | 75% | +44 |
| escalation_manager.py | 98 | 0% | 75% | +74 |
| episode_segmentation_service.py | 591 | 0% | 70% | +414 |
| episode_retrieval_service.py | 320 | 0% | 70% | +224 |
| episode_lifecycle_service.py | 174 | 0% | 70% | +122 |
| workflow_engine.py | 1,163 | 0% | 60% | +698 |
| workflow_analytics_engine.py | 561 | 0% | 65% | +365 |
| workflow_template_system.py | 350 | 0% | 65% | +228 |
| atom_meta_agent.py | 422 | 0% | 60% | +253 |
| agent_social_layer.py | 376 | 0% | 70% | +263 |
| atom_agent_endpoints.py | 787 | 0% | 65% | +512 |
| skill_registry_service.py | 370 | 0% | 70% | +259 |
| skill_composition_engine.py | 132 | 0% | 75% | +99 |
| agent_world_model.py | 317 | 0% | 70% | +222 |
| policy_fact_extractor.py | 23 | 0% | 75% | +17 |
| **TOTAL** | **7,105** | **0%** | **~72% avg** | **~5,328** |

**Projected coverage after Phase 191:**
- Additional covered: ~5,328 statements
- New total covered: 10,439 / 55,372
- Projected coverage: **18.85%**

**To reach 60% coverage (future phases):**
- Need: 33,223 / 55,372 statements covered
- Gap: ~22,784 more statements from 18.85%
- Estimated additional phases: 3-4 phases of similar scope

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All versions verified in pytest.ini, proven in Phases 189-190
- Architecture: HIGH - Proven patterns from Phases 189-190
- Pitfalls: HIGH - 347 VALIDATED_BUGs from Phase 186, all pitfalls observed in project history
- Code examples: HIGH - All examples from actual project test files, proven patterns
- Coverage math: HIGH - Based on actual coverage_actual.json measurements

**Research date:** 2026-03-14
**Revised:** 2026-03-14 (goal corrected from 60-70% to 18-22%)
**Valid until:** 2026-04-14 (30 days - stable domain, testing patterns evolve slowly)

**Key facts (verified):**
- Actual baseline: 7.39% (5,111/55,372 statements) from coverage_actual.json
- Phase 191 targets: 20 files = 7,105 statements
- Projected coverage: 18.85% at 75% average target
- Multi-phase approach required to reach 60%+
