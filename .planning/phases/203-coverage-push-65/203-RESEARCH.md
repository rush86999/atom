# Phase 203: Coverage Push to 65% - Research

**Researched:** 2026-03-17
**Domain:** Python test coverage improvement with pytest
**Confidence:** HIGH

## Summary

Phase 203 aims to increase backend code coverage from the Phase 202 baseline (5.21% or 20.13% depending on measurement scope) to 65%, building on the wave-based approach proven in Phases 201 and 202. This research analyzes the current state, architectural blockers, remaining zero-coverage files, and optimal strategies for achieving the 65% target.

**Current State Analysis:**
- Phase 202 completed 13/13 plans testing 26 zero-coverage files (~700 tests created)
- Two collection errors persist (SQLAlchemy table conflicts in debug_routes, workflow_versioning_endpoints)
- 210 zero-coverage files >100 lines identified (top 30 account for 10,000+ statements)
- Architectural debt: missing canvas_context_provider module, missing DebugEvent/DebugInsight models
- Final Phase 202 coverage: 5.21% overall (4,684/72,885 lines) - limited by test isolation issues

**Primary recommendation:** Fix architectural blockers first (Wave 1), then target remaining zero-coverage files grouped by complexity (Wave 2-3), and complete with integration test gap closure (Wave 4). This structure prioritizes quality over quantity, addressing test isolation issues that prevented accurate coverage measurement in Phase 202. Estimated 12-15 plans over 8-10 hours, creating 500-600 new tests to achieve 65% target.

**Key insight from Phase 202:** The wave-based approach works well (80.95% coverage on agent_execution_service, 85.98% on analytics_engine), but test collection errors and SQLAlchemy metadata conflicts prevent aggregate coverage measurement. Phase 203 must prioritize infrastructure fixes alongside coverage improvements.

## User Constraints

No CONTEXT.md exists for Phase 203. All research areas are at the planner's discretion.

**Requirements from ROADMAP.md:**
- COV-01: Achieve 65% overall line coverage
- COV-02: Maintain zero collection errors
- COV-03: Focus on HIGH priority files first
- COV-04: Create tests for uncovered lines (not fixing excluded tests)
- COV-05: Verify no regressions

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
| **factory_boy** | >=3.2.0 | Test data factories | Create complex test data with relationships (Episode, Canvas, Feedback models) |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest | unittest | unittest is built-in but less feature-rich; pytest fixtures are superior for setup/teardown |
| coverage.py | other coverage tools | coverage.py is the standard; alternatives offer no significant benefits |
| unittest.mock | dependency injection | DI requires more code changes; mocking is faster for testing existing code |
| factory_boy | manual model creation | factory_boy handles relationships and sequences automatically; manual creation is error-prone |

**Installation:**
```bash
# Already installed via pyproject.toml [dev] and [test] sections
pip install pytest pytest-cov pytest-asyncio httpx faker factory_boy
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
│   │   ├── model_fixtures.py       # Factory Boy factories for models
│   │   └── api_fixtures.py         # TestClient setup, request builders
│   ├── error_paths/                # Dedicated error handling tests (Phase 186 pattern)
│   ├── tools/                      # Tool tests (browser, canvas, device)
│   ├── core/                       # Core service tests
│   ├── api/                        # API endpoint tests
│   └── cli/                        # CLI tests
└── coverage*.json                  # Coverage reports (wave_2, final)
```

### Pattern 1: Architectural Debt Resolution Before Coverage

**What:** Fix import errors, missing modules, and SQLAlchemy metadata conflicts before writing new tests.

**When to use:** When collection errors prevent test execution or accurate coverage measurement. Phase 202 had 2 collection errors that blocked aggregate coverage measurement.

**Example from Phase 202 (Rule 4 architectural issue):**
```python
# Issue: communication_service.py imports missing module
# File: core/communication_service.py
from core.canvas_context_provider import get_canvas_provider  # MODULE DOESN'T EXIST

# Impact: 35 tests blocked by import error
# Tests created: tests/core/test_communication_service_coverage.py (35 tests)
# Status: Cannot execute tests until module is created or import removed

# Proposed Fix (Phase 203 Wave 1):
# Option 1: Create canvas_context_provider module with get_canvas_provider function
# Option 2: Remove import and refactor communication_service to not depend on canvas context
# Option 3: Mock canvas_context_provider in tests with sys.modules hack
```

**Source:** `.planning/phases/202-coverage-push-60/202-PHASE-SUMMARY.md` (Architectural Issues section)

### Pattern 2: SQLAlchemy Metadata Conflict Resolution

**What:** Fix "Table already defined" errors by using separate metadata instances or `extend_existing=True`.

**When to use:** When multiple test files define the same SQLAlchemy models, causing collection errors.

**Example from Phase 202 collection errors:**
```python
# ERROR collecting tests/api/test_debug_routes_coverage.py
# sqlalchemy.exc.InvalidRequestError: Table 'team_members' is already defined

# Root Cause: Multiple test files import models from core/models.py
# Each import creates new Base.metadata with duplicate table definitions

# Fix Pattern 1: Use shared metadata (recommended)
# File: tests/conftest.py
from core.models import Base
@pytest.fixture(scope="session")
def db_metadata():
    """Shared metadata instance for all tests."""
    return Base.metadata

# Fix Pattern 2: extend_existing=True (legacy code)
# File: core/models.py
__table_args__ = {'extend_existing': True}

# Fix Pattern 3: Separate test models (cleanest for new code)
# File: tests/test_models.py
from sqlalchemy.ext.declarative import declarative_base
TestBase = declarative_base()
```

**Source:** Phase 202 collection error logs

### Pattern 3: Factory Boy for Complex Model Relationships

**What:** Use Factory Boy factories to create test data with complex relationships (Episode → EpisodeSegment, CanvasAudit, AgentFeedback).

**When to use:** When testing services that require related models (episodic memory, canvas integration, feedback aggregation).

**Example from Phase 191 (Episode models):**
```python
# File: tests/fixtures/model_fixtures.py
import factory
from core.models import Episode, EpisodeSegment, CanvasAudit, AgentFeedback

class EpisodeFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for Episode model."""
    class Meta:
        model = Episode
        sqlalchemy_session_persistence = "commit"

    id = factory.Sequence(lambda n: f"episode-{n}")
    agent_id = "test-agent"
    tenant_id = "test-tenant"
    status = EpisodeStatus.ACTIVE
    start_time = factory.LazyFunction(datetime.now(timezone.utc))
    summary = factory.Faker("text")

class EpisodeSegmentFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for EpisodeSegment model."""
    class Meta:
        model = EpisodeSegment
        sqlalchemy_session_persistence = "commit"

    id = factory.Sequence(lambda n: f"segment-{n}")
    episode = factory.SubFactory(EpisodeFactory)
    segment_type = "action"
    content = factory.Faker("text")
    timestamp = factory.LazyFunction(datetime.now(timezone.utc))

# Usage in tests
def test_episode_segmentation_service(db_session):
    """Test episode segmentation with related models."""
    episode = EpisodeFactory.create(summary="Test episode")
    segment1 = EpisodeSegmentFactory.create(episode=episode, content="Action 1")
    segment2 = EpisodeSegmentFactory.create(episode=episode, content="Action 2")

    # Test segmentation logic
    segments = service.get_episode_segments(episode.id)
    assert len(segments) == 2
```

**Source:** Phase 191 documented need for factory_boy fixtures

### Pattern 4: Zero-Coverage File Grouping by Complexity

**What:** Group zero-coverage files by complexity (HIGH: >500 stmts, MEDIUM: 200-500 stmts, LOW: 100-200 stmts) for efficient plan creation.

**When to use:** When 200+ zero-coverage files exist and need systematic prioritization.

**Phase 203 zero-coverage analysis (210 files >100 lines):**
```python
# HIGH Complexity (>500 statements) - 30 files, ~15,000 statements
1. workflow_engine.py (1164 stmts)
2. atom_agent_endpoints.py (787 stmts)
3. lancedb_handler.py (709 stmts)
4. byok_handler.py (636 stmts)
5. episode_segmentation_service.py (591 stmts)
6. workflow_analytics_engine.py (567 stmts)
7. workflow_debugger.py (527 stmts)
8. advanced_workflow_system.py (499 stmts)
# ... 22 more files

# MEDIUM Complexity (200-500 statements) - ~80 files, ~24,000 statements
# LOW Complexity (100-200 statements) - ~100 files, ~12,000 statements

# Total potential coverage gain: 51,000 statements (69.8% of total code)
# To reach 65% target from 5.21% baseline: Need 43,684 additional statements
# Feasibility: HIGH (51,000 stmts available vs 43,684 stmts needed)
```

**Source:** Coverage analysis of backend/coverage.json (210 zero-coverage files identified)

### Pattern 5: Wave-Based Execution with Infrastructure First

**What:** Structure Phase 203 in 4 waves: Infrastructure fixes → HIGH complexity → MEDIUM/LOW complexity → Integration gap closure.

**When to use:** When architectural debt prevents accurate coverage measurement and test execution.

**Wave Structure for Phase 203:**
```markdown
Wave 1: Infrastructure & Architectural Debt (Plans 01-03)
- Plan 01: Fix SQLAlchemy metadata conflicts (debug_routes, workflow_versioning_endpoints)
- Plan 02: Create missing canvas_context_provider module or remove import
- Plan 03: Define missing DebugEvent/DebugInsight models or refactor debug_alerting
- Target: 0% coverage gain (infrastructure only)
- Duration: ~60 minutes

Wave 2: HIGH Complexity Zero-Coverage Files (Plans 04-08)
- Plan 04: Workflow system coverage (workflow_engine, workflow_analytics_engine, workflow_debugger)
- Plan 05: Agent endpoints coverage (atom_agent_endpoints, byok_endpoints)
- Plan 06: LLM and episode coverage (byok_handler, episode_segmentation_service)
- Plan 07: Advanced workflow system and document ingestion
- Plan 08: Meta agent and social layer coverage
- Target: +20-25 percentage points
- Duration: ~180 minutes

Wave 3: MEDIUM/LOW Complexity Files (Plans 09-12)
- Plan 09: Integration and ingestion services (8-10 files, 200-400 stmts each)
- Plan 10: API routes coverage (smarthome, creative, productivity, debug endpoints)
- Plan 11: Enterprise and auth services (enterprise_auth, auth_endpoints, jwt_verifier)
- Plan 12: Workflow templates and marketplace coverage
- Target: +15-20 percentage points
- Duration: ~180 minutes

Wave 4: Integration Gap Closure & Verification (Plans 13-14)
- Plan 13: Integration test gap closure (cross-service workflows, E2E scenarios)
- Plan 14: Final coverage measurement, aggregate analysis, phase summary
- Target: +5-10 percentage points
- Duration: ~90 minutes

Total: 14 plans, 8-10 hours, +40-55 percentage points (5.21% → 65%)
```

**Source:** Phase 202 recommendations (Wave 6-8 structure adapted for Phase 203)

### Pattern 6: Test Isolation with Database Session Scoping

**What:** Use proper database session scoping to prevent "already exists" errors and state leakage between tests.

**When to use:** When tests fail due to database conflicts or shared state. Phase 202 documented 10% test failures from isolation issues.

**Example from Phase 202 (workflow_versioning tests):**
```python
# Problem: Tests share state causing "already exists" errors
def test_create_workflow_version(db_session):
    version = WorkflowVersion(id="v1", ...)
    db_session.add(version)
    db_session.commit()
    # Test passes

def test_create_workflow_version_duplicate(db_session):
    version = WorkflowVersion(id="v1", ...)  # Same ID!
    db_session.add(version)
    db_session.commit()
    # FAILS: IntegrityError: already exists

# Solution 1: Unique IDs with faker
@pytest.fixture
def workflow_version_data():
    return {
        "id": f"version-{uuid.uuid4()}",
        "workflow_id": f"workflow-{uuid.uuid4()}",
        ...
    }

# Solution 2: Transaction rollback per test
@pytest.fixture(autouse=True)
def rollback_transaction(db_session):
    """Rollback transaction after each test."""
    transaction = db_session.begin_nested()
    yield
    transaction.rollback()

# Solution 3: Separate database per test (expensive but clean)
@pytest.fixture(scope="function")
def isolated_db():
    """Create isolated database for each test."""
    # Create new SQLite DB in temp file
    # Run migrations
    # Yield session
    # Cleanup temp file
```

**Source:** `.planning/phases/202-coverage-push-60/202-PHASE-SUMMARY.md` (Test Isolation Issues)

### Anti-Patterns to Avoid

- **Testing excluded code:** Phase 202 documented schema drift issues that blocked tests. Don't try to test code excluded with `# pragma: no cover`.
- **Over-mocking external dependencies:** Only mock LLM providers, databases, external APIs. Don't mock the code you're testing.
- **Complex integration tests in early waves:** Focus on unit-level tests first (Waves 2-3), defer E2E to Wave 4.
- **Ignoring collection errors:** Phase 202 had 2 collection errors that blocked aggregate coverage. Fix these first in Wave 1.
- **Full app initialization requirements:** Complex orchestration code (workflow_engine, atom_meta_agent) should target 40-50% coverage, not 80%.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Test runner | Custom test discovery | pytest | 986 tests already use pytest; superior fixture system |
| Mock objects | Manual mock classes | unittest.mock.Mock, AsyncMock | Handles method chaining, async mocking, call tracking automatically |
| Coverage measurement | Custom coverage scripts | pytest-cov with --cov-report=json | Generates JSON for analysis, integrates with pytest |
| Test data with relationships | Manual model creation | factory_boy | Handles foreign keys, sequences, related objects automatically |
| Database isolation | Manual cleanup | pytest fixtures with rollback | Automatic cleanup, prevents state leakage |
| Async test handling | Custom event loops | pytest-asyncio with @pytest.mark.asyncio | Handles async fixture setup, test isolation |

**Key insight:** Phase 202 achieved 80.95% coverage on agent_execution_service and 85.98% on analytics_engine using only standard pytest tools. No custom tooling was required. The existing fixture system (conftest.py, mock_services.py) is sufficient for Phase 203, but architectural debt must be resolved first.

## Common Pitfalls

### Pitfall 1: SQLAlchemy Metadata Conflicts Blocking Collection

**What goes wrong:** pytest collection fails with "Table 'X' is already defined for this MetaData instance" errors. Phase 202 had 2 collection errors from this issue.

**Why it happens:** Multiple test files import the same SQLAlchemy models, each creating a new Base.metadata instance with duplicate table definitions.

**How to avoid:**
1. Use shared metadata instance in conftest.py (recommended)
2. Set `extend_existing=True` on `__table_args__` for legacy models
3. Scope fixtures to "session" to prevent repeated model definitions
4. Use `pytest --collect-only -q` before running full test suite to detect conflicts early

**Warning signs:** `pytest --collect-only` shows `ERROR collecting tests/...` with `sqlalchemy.exc.InvalidRequestError`

**Source:** Phase 202 collection error logs (2 errors in debug_routes, workflow_versioning_endpoints)

### Pitfall 2: Missing Modules Blocking Test Execution

**What goes wrong:** Tests fail with `ModuleNotFoundError: No module named 'canvas_context_provider'`. Phase 202 had 35 tests blocked by this issue.

**Why it happens:** Production code imports modules that don't exist (architectural debt), blocking test execution.

**How to avoid:**
1. Document architectural issues when found (don't fix in coverage phase unless critical)
2. Create stub modules with NotImplementedError for missing functionality
3. Use `sys.modules` hack to mock missing modules in conftest.py
4. Prioritize fixing missing module imports in Wave 1

**Warning signs:** Tests fail during import with `ModuleNotFoundError` or `ImportError`

**Source:** `.planning/phases/202-coverage-push-60/202-PHASE-SUMMARY.md` (Missing Module for Communication Service)

### Pitfall 3: Missing Database Models Blocking Tests

**What goes wrong:** Tests fail with `AttributeError: module 'core.models' has no attribute 'DebugEvent'`. Phase 202 had debug_alerting tests blocked by missing models.

**Why it happens:** Tests reference models that haven't been defined in core/models.py yet (incomplete schema).

**How to avoid:**
1. Check core/models.py before writing tests to verify model existence
2. Document missing models as Rule 4 architectural issues
3. Use generic models (AuditEvent) instead of specialized models (DebugEvent) where possible
4. Skip tests for missing models with `@pytest.mark.skip(reason="Model not defined")`

**Warning signs:** Tests fail with `AttributeError` or `ImportError` when importing from core.models

**Source:** `.planning/phases/202-coverage-push-60/202-PHASE-SUMMARY.md` (Missing Database Models for Debug Alerting)

### Pitfall 4: Test Isolation Issues Causing Flaky Tests

**What goes wrong:** Tests pass individually but fail when run together due to shared state. Phase 202 documented 10% test failures from isolation issues.

**Why it happens:** Database sessions aren't rolled back, test data persists between tests, fixtures aren't scoped correctly.

**How to avoid:**
1. Use `@pytest.fixture(autouse=True)` with transaction rollback
2. Create unique test data with UUID sequences or faker
3. Scope fixtures to "function" (not "session" or "module")
4. Run tests with `pytest --forked` to isolate processes (last resort)

**Warning signs:** Tests pass when run individually (`pytest test_file.py::test_func`) but fail in full suite (`pytest`)

**Source:** `.planning/phases/202-coverage-push-60/202-PHASE-SUMMARY.md` (Test Isolation Issues)

### Pitfall 5: Coverage Measurement Challenges from pytest.ini

**What goes wrong:** `pytest.ini` `--maxfail=10` stops execution early, preventing coverage.json generation. Phase 202 had to override config to measure coverage.

**Why it happens:** pytest.ini configuration is optimized for fast feedback during development, not coverage measurement.

**How to avoid:**
1. Create separate `pytest-coverage.ini` for coverage runs without `--maxfail`
2. Override config with `-o addopts=""` when measuring coverage
3. Use `pytest --cov -x` to stop on first failure (for development)
4. Use `pytest --cov` (no `-x`) for coverage measurement (for CI)

**Warning signs:** Coverage report is missing or incomplete after test run

**Source:** `.planning/phases/202-coverage-push-60/202-PHASE-SUMMARY.md` (Coverage Measurement Challenges)

## Code Examples

Verified patterns from Phase 202 test files:

### SQLAlchemy Metadata Conflict Fix

```python
# File: tests/conftest.py
"""
Shared fixtures for backend tests.
"""
from sqlalchemy.ext.declarative import declarative_base
from core.models import Base as CoreBase

# Create shared metadata for all tests
TestBase = declarative_base()

@pytest.fixture(scope="session")
def shared_metadata():
    """
    Shared metadata instance to prevent 'Table already defined' errors.

    Usage in test files:
        from tests.conftest import shared_metadata
        from sqlalchemy import Column, String, Integer
        from sqlalchemy.ext.declarative import declarative_base

        Base = declarative_base(metadata=shared_metadata)
    """
    return CoreBase.metadata

# Alternative: Extend existing tables
@pytest.fixture(scope="session")
def extend_existing_tables():
    """
    Allow extending existing table definitions.

    Usage in model definitions:
        __table_args__ = {'extend_existing': True}
    """
    # Set global flag for models
    original_extend = getattr(CoreBase, '__table_args__', {})
    CoreBase.__table_args__ = {'extend_existing': True}
    yield
    CoreBase.__table_args__ = original_extend
```

**Source:** Phase 202 collection error resolution pattern

### Missing Module Mock Pattern

```python
# File: tests/conftest.py
"""
Mock missing modules to enable test execution.
"""
import sys
from unittest.mock import MagicMock

# Mock canvas_context_provider (missing module)
sys.modules['core.canvas_context_provider'] = MagicMock()

# Mock ai_enhanced_service (missing module)
sys.modules['ai_enhanced_service'] = MagicMock()

@pytest.fixture(autouse=True)
def mock_missing_modules():
    """
    Auto-apply missing module mocks for all tests.

    This allows tests to run even when production code imports
    modules that don't exist yet (architectural debt).
    """
    # Canvas context provider
    canvas_provider = MagicMock()
    canvas_provider.get_canvas_provider.return_value = MagicMock()
    sys.modules['core.canvas_context_provider'] = canvas_provider

    yield

    # Cleanup
    if 'core.canvas_context_provider' in sys.modules:
        del sys.modules['core.canvas_context_provider']
```

**Source:** Phase 202 missing module workaround pattern

### Factory Boy Pattern for Episode Models

```python
# File: tests/fixtures/model_fixtures.py
"""
Factory Boy fixtures for complex model relationships.
"""
import factory
from datetime import datetime, timezone
from core.models import Episode, EpisodeSegment, CanvasAudit, AgentFeedback

class EpisodeFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for Episode model."""
    class Meta:
        model = Episode
        sqlalchemy_session_persistence = "commit"

    id = factory.Sequence(lambda n: f"episode-{n}")
    agent_id = "test-agent"
    tenant_id = "test-tenant"
    status = "active"
    start_time = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    end_time = None
    summary = factory.Faker("text")
    metadata = {}

class EpisodeSegmentFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for EpisodeSegment model."""
    class Meta:
        model = EpisodeSegment
        sqlalchemy_session_persistence = "commit"

    id = factory.Sequence(lambda n: f"segment-{n}")
    episode = factory.SubFactory(EpisodeFactory)
    segment_type = "action"
    content = factory.Faker("text")
    timestamp = factory.LazyFunction(lambda: datetime.now(timezone.utc))
    metadata = {}

class CanvasAuditFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for CanvasAudit model."""
    class Meta:
        model = CanvasAudit
        sqlalchemy_session_persistence = "commit"

    id = factory.Sequence(lambda n: f"canvas-{n}")
    agent_id = "test-agent"
    canvas_type = "chart"
    data = {}
    status = "presented"
    timestamp = factory.LazyFunction(lambda: datetime.now(timezone.utc))

# Usage in tests
def test_episode_retrieval_with_canvas_context(db_session):
    """Test episode retrieval includes canvas context."""
    episode = EpisodeFactory.create(summary="Test episode")
    segment = EpisodeSegmentFactory.create(episode=episode, content="Action")
    canvas = CanvasAuditFactory.create(agent_id=episode.agent_id)

    # Retrieve episode
    result = episode_service.get_episode(episode.id, include_canvas=True)

    assert result["summary"] == "Test episode"
    assert len(result["segments"]) == 1
    assert result["canvas_context"] is not None
    assert result["canvas_context"]["canvas_id"] == canvas.id
```

**Source:** Phase 191 documented need for factory_boy fixtures (not yet implemented)

### Coverage Measurement Script

```bash
#!/bin/bash
# File: scripts/measure_coverage.sh

# Run full test suite with coverage
cd backend
python3 -m pytest \
    --cov=backend \
    --cov-branch \
    --cov-report=json \
    --cov-report=term-missing \
    --cov-report=html \
    -o addopts="" \
    -q

# Parse coverage JSON for analysis
python3 << 'EOF'
import json
from pathlib import Path

# Read coverage report
coverage_file = Path("backend/coverage.json")
if not coverage_file.exists():
    print("ERROR: coverage.json not found")
    exit(1)

with open(coverage_file) as f:
    data = json.load(f)

# Overall coverage
totals = data['totals']
print(f"=== OVERALL COVERAGE ===")
print(f"Coverage: {totals['percent_covered']:.2f}%")
print(f"Lines: {totals['covered_lines']:,} / {totals['num_statements']:,}")
print(f"Missing: {totals['missing_lines']:,}")
print(f"Branches: {totals['covered_branches']:,} / {totals['num_branches']:,}")
print()

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
    elif '/integrations/' in path:
        module = 'integrations'
    else:
        continue

    if module not in modules:
        modules[module] = {'covered': 0, 'total': 0, 'files': 0}

    modules[module]['covered'] += info['summary']['covered_lines']
    modules[module]['total'] += info['summary']['num_statements']
    modules[module]['files'] += 1

print(f"=== MODULE BREAKDOWN ===")
for module, stats in sorted(modules.items()):
    pct = (stats['covered'] / stats['total'] * 100) if stats['total'] > 0 else 0
    print(f"{module:15s}: {pct:5.2f}% ({stats['covered']:,}/{stats['total']:,}) in {stats['files']} files")

# Zero-coverage files >100 lines
zero_coverage = []
for path, info in data['files'].items():
    stmts = info['summary']['num_statements']
    covered = info['summary']['covered_lines']
    if stmts > 100 and covered == 0:
        zero_coverage.append({
            'path': path,
            'statements': stmts
        })

zero_coverage.sort(key=lambda x: x['statements'], reverse=True)

print(f"\n=== ZERO-COVERAGE FILES >100 LINES ===")
print(f"Total: {len(zero_coverage)} files")
for i, f in enumerate(zero_coverage[:20], 1):
    path = f['path'].split('/')[-1]
    print(f"{i:2d}. {path:45s} ({f['statements']:4d} stmts)")
EOF
```

**Source:** Phase 202 coverage measurement pattern (adapted from Phase 201)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Service-level coverage estimates | Line-level coverage with coverage.py | Phase 200 | Precise measurement of untested code |
| Random test writing | Wave-based prioritization (HIGH → MEDIUM → LOW) | Phase 201 | Efficient use of testing time |
| Single-module testing | Module-focused plans with grouping | Phase 201 | +64-98% coverage improvements per plan |
| Manual test data generation | Faker + fixtures | Phase 201 | Faster test creation, realistic data |
| Ignoring collection errors | Fix collection errors first (Wave 1) | Phase 200 | Accurate coverage measurement |
| Ad-hoc mocking | MockLLMProvider, MockEmbeddingService fixtures | Phase 200 | Consistent mock behavior across tests |
| Missing model relationships | Factory Boy for complex models | Phase 203 (planned) | Handle Episode/Canvas/Feedback relationships |

**Deprecated/outdated:**
- ** unittest.TestCase**: pytest fixtures are superior; use pytest instead
- **nose**: Test runner is deprecated; use pytest
- **coverage.py CLI**: Use pytest-cov integration instead
- **Manual model creation**: Use factory_boy for models with relationships

## Open Questions

1. **Question:** Should Phase 203 target 65% from 5.21% baseline or use a different baseline?
   - **What we know:** Phase 202 final coverage measured 5.21% (4,684/72,885 lines). Phase 201 Wave 2 measured 20.13% (18,476/74,018 lines). The difference is due to measurement scope (backend-wide vs specific modules).
   - **What's unclear:** Which baseline is accurate for Phase 203 planning.
   - **Recommendation:** Use 5.21% as conservative baseline (backend-wide coverage). Target 65% = need 43,021 additional lines. With 51,000 statements available in zero-coverage files, target is achievable with realistic testing pace.

2. **Question:** How to handle the 2 collection errors from Phase 202?
   - **What we know:** debug_routes and workflow_versioning_endpoints tests have SQLAlchemy metadata conflicts. Tests exist but can't be collected.
   - **What's unclear:** Whether to fix conflicts or exclude these tests.
   - **Recommendation:** Fix conflicts in Wave 1 using shared metadata pattern. This unblocks existing tests and prevents future conflicts. Estimated fix time: 20-30 minutes.

3. **Question:** Should Phase 203 create missing modules (canvas_context_provider, DebugEvent/DebugInsight models)?
   - **What we know:** 35 communication_service tests are blocked by missing canvas_context_provider. Debug alerting tests are blocked by missing models.
   - **What's unclear:** Whether creating these modules is in scope for coverage phase.
   - **Recommendation:** Create stub modules with NotImplementedError in Wave 1. This allows tests to run without implementing full functionality. Mark as technical debt for future implementation phases.

4. **Question:** What's the optimal plan size for Phase 203 given 210 zero-coverage files?
   - **What we know:** Phase 202 averaged 1.2 commits per plan (13 plans, 26 files). Single-task plans worked well for focused modules (agent_execution_service: 80.95% in 40 min).
   - **What's unclear:** Whether to group multiple files into single plans or single-file plans.
   - **Recommendation:** Mixed approach. HIGH complexity files (>500 stmts) get single-file plans. MEDIUM/LOW complexity files (100-500 stmts) get grouped into plans by module (3-5 files per plan). Estimated 12-15 plans total.

5. **Question:** Should Phase 203 implement factory_boy fixtures for Episode/Canvas/Feedback models?
   - **What we know:** Phase 191 documented need for factory_boy but didn't implement. Episode services require related models (EpisodeSegment, CanvasAudit, AgentFeedback).
   - **What's unclear:** Whether to implement factory_boy in Wave 1 or defer to later phase.
   - **Recommendation:** Implement factory_boy in Wave 1 (infrastructure). This enables better episode/canvas/feedback testing in Waves 2-3. Estimated implementation time: 60-90 minutes for 4-5 factories.

## Sources

### Primary (HIGH confidence)

- **pytest 7.0+ documentation** - Test discovery, fixtures, parametrization, async testing
- **pytest-cov 4.0+ documentation** - Coverage integration, JSON report generation
- **coverage.py 7.x documentation** - Line vs branch coverage, report formats
- **FastAPI TestClient documentation** - API endpoint testing patterns
- **Phase 202 comprehensive summary** - `.planning/phases/202-coverage-push-60/202-PHASE-SUMMARY.md` (409 lines)
- **Phase 202 research** - `.planning/phases/202-coverage-push-60/202-RESEARCH.md` (609 lines)
- **Phase 201 comprehensive summary** - `.planning/phases/201-coverage-push-85/201-PHASE-SUMMARY.md` (766 lines)
- **backend/coverage.json** - 210 zero-coverage files >100 lines identified
- **backend/final_coverage.json** - 5.21% overall coverage baseline

### Secondary (MEDIUM confidence)

- **Phase 200 summary** - Collection error fixes and baseline measurement
- **backend/pyproject.toml** - Testing dependencies (pytest, pytest-cov, pytest-asyncio, factory-boy)
- **Phase 202 collection error logs** - SQLAlchemy metadata conflict patterns
- **REQUIREMENTS.md** - Coverage requirements (COV-01 through GAP-05)

### Tertiary (LOW confidence)

- **factory_boy documentation** - Test data factories (not yet implemented in codebase, planned for Phase 203)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All tools are industry standards with extensive documentation
- Architecture: HIGH - Patterns are proven in Phases 201-202 with measurable results
- Pitfalls: HIGH - All pitfalls documented from actual Phase 202 deviations
- Wave structure: MEDIUM - Estimates based on Phase 202 efficiency (54 tests/hour) but Phase 203 scope is larger with infrastructure fixes
- Factory Boy recommendations: MEDIUM - Not yet implemented in codebase, standard pattern but needs validation

**Research date:** 2026-03-17
**Valid until:** 2026-04-17 (30 days - coverage improvement strategies are stable)

**Phase 203 estimates:**
- Baseline coverage: 5.21% (4,684/72,885 lines) - conservative backend-wide baseline
- Target coverage: 65.00%
- Gap: 59.79 percentage points (43,021 lines)
- Zero-coverage files available: 210 files >100 lines (51,000 statements)
- Estimated plans: 12-15
- Estimated duration: 8-10 hours
- Estimated tests: 500-600
- Efficiency: 55 tests/hour (vs Phase 202: 54 tests/hour)

**Key recommendation:** Prioritize infrastructure fixes in Wave 1 (SQLAlchemy conflicts, missing modules, factory_boy implementation) before writing coverage tests. This addresses Phase 202 blockers and enables accurate coverage measurement. Wave structure: Wave 1 (infrastructure, 0% gain), Wave 2 (HIGH complexity, +20-25%), Wave 3 (MEDIUM/LOW complexity, +15-20%), Wave 4 (integration gaps, +5-10%). Total: +40-55 percentage points (5.21% → 65%).
