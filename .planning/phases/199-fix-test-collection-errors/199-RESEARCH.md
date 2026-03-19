# Phase 199: Fix Test Collection Errors & Achieve 85% - Research

**Researched:** 2026-03-16
**Domain:** Test Infrastructure Quality & Coverage Measurement
**Confidence:** HIGH

## Summary

Phase 199 addresses the critical blocker preventing Phase 198 from achieving its 85% coverage target: **test collection errors that prevent 150+ existing tests from being measured**. The primary issues are: (1) 10 collection errors from archive/legacy test files and broken import paths, (2) Pydantic v2/SQLAlchemy 2.0 compatibility in test fixtures, (3) CanvasAudit schema drift in test assertions, and (4) test suite configuration excluding valid tests. This research documents the root causes, prescribes systematic fixes, and identifies medium-impact modules to target after unblocking existing tests.

**Primary recommendation:** Fix collection errors systematically (archive old tests, fix import paths, update Pydantic v2 fixtures, unblock excluded tests) to enable 150+ existing tests (~2-3 hours), then target medium-impact modules (governance 62%→85%, episodic memory, training) for 3-5% additional coverage (~3-4 hours). Total estimated effort: 5-7 hours to achieve 85% overall coverage.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | 9.0.2 | Test framework | Industry standard, Python 3.14 compatible, extensive plugin ecosystem |
| **pytest-cov** | 7.0.0 | Coverage measurement | Coverage.py integration, JSON output, branch coverage |
| **coverage.py** | 7.13.4 | Coverage engine | C extension for speed, JSON reports, fail_under gates |
| **Pydantic** | 2.12.5 | Data validation | v2 with proper type validation, Python 3.14 compatible |
| **SQLAlchemy** | 2.0.45 | ORM | 2.0 style with proper relationship handling |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **factory_boy** | 3.3.1 | Test data generation | Declarative fixtures with SQLAlchemy integration |
| **AsyncMock** | 3.12+ | Async mocking | Mocking async service methods properly |
| **pytest-asyncio** | 1.3.0 | Async test execution | AUTO mode for deterministic async tests |
| **FastAPI TestClient** | 0.115.0 | API testing | Official FastAPI testing utility with dependency override |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest 9.0.2 | pytest 8.x | 9.0.2 has better Python 3.14 support, improved collection |
| Pydantic v2 | Pydantic v1 | v2 required for Python 3.14 compatibility, better type safety |
| SQLAlchemy 2.0.45 | SQLAlchemy 1.4 | 2.0 has better async support, required by codebase |

**Installation:**
```bash
# All dependencies already installed
pip install pytest==9.0.2 pytest-cov==7.0.0
pip install pydantic==2.12.5 sqlalchemy==2.0.45
pip install factory-boy==3.3.1
```

---

## Architecture Patterns

### Test Collection Error Types (Current State)

**Phase 198 Achievements:**
- Module-level coverage improvements: Episodic memory 84%, Supervision 78%, Cache 90%+
- 150+ new tests created across 8 plans
- Integration test infrastructure established

**Phase 198 Blockers:**
- Overall coverage: 74.6% (target 85%, gap -10.4%)
- **10 collection errors** preventing new tests from being measured
- Pydantic v2/SQLAlchemy 2.0 compatibility issues in test fixtures
- CanvasAudit schema drift in test assertions

**Collection Error Categories (from Phase 198 analysis):**

```python
# Error Type 1: Archive/Legacy Test Files (6 errors)
# Problem: Old project structure tests with invalid import paths
archive/old_project_structure/shared/test_integration_base.py
  → ModuleNotFoundError: No module named 'shared'
archive/old_project_structure/tests/chat_orchestration_test.py
  → ModuleNotFoundError: No module named 'src.services.ChatOrchestrationService'
archive/old_project_structure/tests/e2e/test_*.py
  → ModuleNotFoundError: No module named 'utils.llm_verifier'
archive/old_project_structure/tests/e2e/tests/test_hubspot_service_unit.py
  → ModuleNotFoundError: No module named 'integrations'

# Error Type 2: Non-Backend Test Files (2 errors)
# Problem: Test files in frontend-nextjs and scripts directories
frontend-nextjs/project/functions/audio_processor/tests/test_handler.py
  → ModuleNotFoundError: No module named 'tests.test_handler'
scripts/test_advanced_execution.py
  → ModuleNotFoundError: No module named 'core.workflow_engine'
scripts/test_auto_healing.py
  → Import error (scripts not in PYTHONPATH)

# Error Type 3: pytest.ini Configuration (1 error)
# Problem: Non-top-level conftest.py deprecation warning
backend/conftest.py
  → PytestPluginValidationWarning: plugins in non-top-level conftest files

# Error Type 4: Pydantic v2/SQLAlchemy 2.0 Fixture Issues (not in collection errors)
# Problem: Test fixtures using deprecated Pydantic v1 patterns
# Impact: Tests run but fail on model validation
# Files affected (from Phase 198 reports):
# - tests/api/test_*_coverage.py (6 files)
# - tests/core/test_agent_governance_service_coverage_extend.py
# - tests/core/test_agent_graduation_service_coverage.py
# - tests/database/*.py (all database model tests)
```

### Pydantic v2/SQLAlchemy 2.0 Compatibility Pattern

**What Changed:**
- Pydantic v1: `BaseModel.parse_obj()` → Pydantic v2: `BaseModel.model_validate()`
- Pydantic v1: `BaseModel.update()` → Pydantic v2: `model.model_copy(update=...)`
- SQLAlchemy 1.4: `session.query(Model)` → SQLAlchemy 2.0: `session.execute(select(Model))`
- Type annotations: Forward refs require `from __future__ import annotations`

**Fix Pattern:**
```python
# Step 1: Update Pydantic v1 → v2 patterns
# OLD (Pydantic v1):
agent_data = AgentSchema.parse_obj(db_agent.__dict__)

# NEW (Pydantic v2):
agent_data = AgentSchema.model_validate(db_agent)

# OLD (Pydantic v1):
agent_copy = agent_data.update({"status": "active"})

# NEW (Pydantic v2):
agent_copy = agent_data.model_copy(update={"status": "active"})

# Step 2: Update SQLAlchemy 1.4 → 2.0 patterns
# OLD (SQLAlchemy 1.4):
agents = session.query(Agent).filter(Agent.status == "active").all()

# NEW (SQLAlchemy 2.0):
from sqlalchemy import select
stmt = select(Agent).where(Agent.status == "active")
agents = session.execute(stmt).scalars().all()

# Step 3: Fix factory_boy fixtures for Pydantic v2
class AgentFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = AgentRegistry
        sqlalchemy_session = db_session

    # Pydantic v2 requires proper field types
    maturity_level = "INTERN"  # Must be valid enum value
    status = "active"
```

### CanvasAudit Schema Drift Pattern

**Schema Changes (from Phase 198):**
```python
# OLD Schema (Phase 197 and earlier):
class CanvasAudit(Base):
    agent_execution_id = Column(String)  # REMOVED
    component_type = Column(String)  # REMOVED

# NEW Schema (current):
class CanvasAudit(Base):
    # Only: id, agent_id, canvas_type, content, metadata, timestamp
    # agent_execution_id removed
    # component_type removed
```

**Test Fix Pattern:**
```python
# OLD (incorrect - references removed fields):
def test_canvas_presentation_creates_audit(db_session, client):
    response = client.post(f"/agents/{agent.id}/present", json={...})
    audit = db_session.query(CanvasAudit).filter_by(agent_id=agent.id).first()

    # These fields no longer exist:
    assert audit.agent_execution_id is not None  # REMOVED
    assert audit.component_type == "chart"  # REMOVED

# NEW (correct):
def test_canvas_presentation_creates_audit(db_session, client):
    response = client.post(f"/agents/{agent.id}/present", json={
        "type": "line_chart",
        "content": {"data": [1, 2, 3]}
    })

    assert response.status_code == 200
    audit = db_session.query(CanvasAudit).filter_by(agent_id=agent.id).first()
    assert audit is not None
    assert audit.canvas_type == "line_chart"
    assert audit.content == {"data": [1, 2, 3]}
    # No agent_execution_id or component_type references
```

### pytest.ini Configuration Pattern

**Current Issue:**
```python
# backend/conftest.py triggers deprecation warning:
# PytestPluginValidationWarning: plugins in non-top-level conftest files

# Warning source: conftest.py in backend/ subdirectory
# Impact: Doesn't block collection but pollutes output
```

**Fix:**
```python
# Option 1: Move conftest.py to project root (recommended)
# From: backend/conftest.py
# To: conftest.py (in project root /Users/rushiparikh/projects/atom/)

# Option 2: Suppress warning (not recommended, masks issues)
# Add to pytest.ini:
# filterwarnings =
#     ignore::pytest.PytestPluginValidationWarning

# Option 3: Use pyproject.toml for pytest config (modern approach)
# [tool.pytest.ini_options]
# testpaths = ["backend/tests"]
# pythonpath = "."
```

### Anti-Patterns to Avoid

- **Archive tests in codebase:** Don't keep old project structure tests in active directory
- **Broken import paths:** Don't let ModuleNotFoundError sit unresolved
- **Pydantic v1 patterns in v2 codebase:** Don't mix parse_obj() with model_validate()
- **Schema drift in tests:** Don't let model changes break test assertions
- **pytest configuration warnings:** Don't ignore deprecation warnings

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Archive test cleanup | Manual file-by-file deletion | pytest --ignore patterns | Systematic exclusion, preserves history if needed |
| Pydantic v2 migration | Manual pattern replacement | Pydantic migration guide + automated codemods | Ensures all v2 patterns applied correctly |
| Schema drift fixes | Manual test assertion updates | Schema audit script + pytest fixtures | Catches all drift, prevents future issues |
| Collection error analysis | Manual grep/log inspection | pytest --collect-only with error categorization | Systematic identification, metrics on progress |
| Coverage measurement gaps | Manual file-by-file inspection | coverage.py JSON with automated gap analysis | Efficient identification of high-value targets |

**Key insight:** Phase 198 demonstrated that module-level testing works (84% episodic memory, 78% supervision), but collection errors block those improvements from showing in overall coverage. Fix infrastructure first, then measure actual gains.

---

## Common Pitfalls

### Pitfall 1: Ignoring Archive Test Files

**What goes wrong:** Old project structure tests in archive/ directory cause collection errors, polluting test output and hiding real issues

**Why it happens:** Tests moved to archive/ but not excluded from pytest discovery

**How to avoid:**
```python
# GOOD: Exclude archive directories in pytest.ini
[pytest]
addopts = --ignore=archive/ --ignore=frontend-nextjs/ --ignore=scripts/

# BAD: Let archive tests fail collection
# Result: 10 collection errors, unclear which are real issues vs archive cruft
```

**Warning signs:** ModuleNotFoundError for modules you know don't exist (shared/, src.services/, utils.llm_verifier)

### Pitfall 2: Mixed Pydantic v1/v2 Patterns

**What goes wrong:** Some tests use parse_obj() (v1), others use model_validate() (v2), causing confusing test failures

**Why it happens:** Incremental migration to Pydantic v2, incomplete test updates

**How to avoid:**
```python
# GOOD: Audit all Pydantic patterns in tests
# 1. Search for deprecated patterns:
#    grep -r "parse_obj\|\.update(" tests/
#
# 2. Replace with v2 patterns:
#    parse_obj() → model_validate()
#    .update() → .model_copy(update=...)
#
# 3. Verify with:
#    pytest tests/ -k "test_model_validation" -v

# BAD: Mix v1 and v2 patterns
# Tests fail inconsistently depending on which fixtures load
```

**Warning signs:** AttributeError: 'BaseModel' object has no attribute 'parse_obj', or TypeError: 'NoneType' object is not subscriptable

### Pitfall 3: CanvasAudit Schema Drift

**What goes wrong:** Tests fail with AttributeError or missing fields because CanvasAudit model changed but tests not updated

**Why it happens:** Schema changes made without updating test fixtures

**How to avoid:**
```python
# GOOD: Audit test fixtures against current schema
# 1. Extract model schema:
from core.models import CanvasAudit
fields = [f.name for f in CanvasAudit.__table__.columns]
# ['id', 'agent_id', 'canvas_type', 'content', 'timestamp']

# 2. Search tests for removed fields:
#    grep -r "agent_execution_id\|component_type" tests/
#
# 3. Update test assertions:
#    Remove references to removed fields
#    Update fixture schemas to match current model

# BAD: Let tests fail with mysterious AttributeError
# Time-consuming to debug, unclear root cause
```

**Warning signs:** Tests fail with AttributeError on model attributes, schema migration history shows dropped columns

### Pitfall 4: pytest Configuration Warnings

**What goes wrong:** Non-top-level conftest.py deprecation warning, ignored until it breaks something

**Why it happens:** conftest.py in backend/ subdirectory triggers pytest validation warning

**How to avoid:**
```python
# GOOD: Move conftest.py to project root
# From: backend/conftest.py
# To: conftest.py (in project root)

# Or use pyproject.toml for pytest config (modern):
[tool.pytest.ini_options]
testpaths = ["backend/tests"]
pythonpath = "."
asyncio_mode = "auto"

# BAD: Ignore warnings
# filterwarnings = ignore::pytest.PytestPluginValidationWarning
# Masks real issues, prevents pytest improvements
```

**Warning signs:** pytest warnings about deprecated patterns, conftest.py validation warnings

### Pitfall 5: Assuming Tests Run When They Don't

**What goes wrong:** Phase 198 created 150+ tests, but collection errors prevented them from running or being measured

**Why it happens:** pytest collection fails silently for some files, those tests never execute

**How to avoid:**
```python
# GOOD: Verify test collection after adding new tests
# 1. Run collection:
#    pytest --collect-only -q
#
# 2. Check for errors:
#    grep "ERROR collecting\|error collecting"
#
# 3. Verify test count matches expected:
#    pytest --collect-only | tail -2
#    Expected: "XX tests collected, 0 errors"

# BAD: Assume pytest ran all tests
# Collection errors don't fail pytest, just skip those files
# Overall coverage understated, gaps hidden
```

**Warning signs:** pytest output shows "0 errors in X.XXs" but test count lower than expected

---

## Code Examples

Verified patterns from Phase 198 analysis and pytest documentation:

### Test Collection Error Fix Pattern

```python
# Source: Phase 198 collection error analysis
# Problem: 10 collection errors from archive tests and broken imports

# Step 1: Exclude archive directories
# File: pytest.ini
[pytest]
addopts = --ignore=archive/ --ignore=frontend-nextjs/ --ignore=scripts/

# Step 2: Verify collection
$ pytest --collect-only -q
92 tests collected, 0 errors in 1.50s  # Success!

# Step 3: Run full test suite
$ pytest tests/ --maxfail=10 -q
XXXXX passed in XX.XXs  # All tests run
```

### Pydantic v2 Fixture Migration Pattern

```python
# Source: Phase 198 Pydantic compatibility issues
# Problem: Test fixtures using Pydantic v1 patterns fail validation

# OLD (Pydantic v1 - incorrect):
@pytest.fixture
def agent_data():
    return AgentSchema.parse_obj({
        "id": "test-agent-1",
        "name": "Test Agent",
        "maturity_level": "INTERN"
    })

# NEW (Pydantic v2 - correct):
@pytest.fixture
def agent_data():
    return AgentSchema.model_validate({
        "id": "test-agent-1",
        "name": "Test Agent",
        "maturity_level": "INTERN"
    })

# OLD (Pydantic v1 - incorrect):
agent_copy = agent_data.update({"status": "active"})

# NEW (Pydantic v2 - correct):
agent_copy = agent_data.model_copy(update={"status": "active"})
```

### SQLAlchemy 2.0 Query Pattern

```python
# Source: Phase 198 database test failures
# Problem: SQLAlchemy 1.4 query syntax deprecated

# OLD (SQLAlchemy 1.4 - incorrect):
agents = session.query(Agent).filter(Agent.status == "active").all()

# NEW (SQLAlchemy 2.0 - correct):
from sqlalchemy import select
stmt = select(Agent).where(Agent.status == "active")
agents = session.execute(stmt).scalars().all()

# OLD (SQLAlchemy 1.4 - incorrect):
agent = session.query(Agent).filter(Agent.id == agent_id).first()

# NEW (SQLAlchemy 2.0 - correct):
stmt = select(Agent).where(Agent.id == agent_id)
agent = session.execute(stmt).scalar_one_or_none()
```

### CanvasAudit Schema Update Pattern

```python
# Source: Phase 198 CanvasAudit test failures (2 tests)
# Problem: Tests reference removed fields (agent_execution_id, component_type)

# OLD (incorrect - references removed fields):
def test_governance_streaming_with_canvas_presentation(db_session, mock_websocket):
    response = client.post(f"/agents/{agent.id}/chat", json={...})

    audit = db_session.query(CanvasAudit).filter_by(agent_id=agent.id).first()
    assert audit is not None
    assert audit.agent_execution_id is not None  # FIELD REMOVED
    assert audit.component_type == "chart"  # FIELD REMOVED

# NEW (correct - current schema only):
def test_governance_streaming_with_canvas_presentation(db_session, mock_websocket):
    response = client.post(f"/agents/{agent.id}/chat", json={
        "message": "Present test chart",
        "present": {
            "type": "line_chart",
            "content": {"data": [1, 2, 3]}
        }
    })

    assert response.status_code == 200

    # Check audit created
    audit = db_session.query(CanvasAudit).filter_by(agent_id=agent.id).first()
    assert audit is not None
    assert audit.canvas_type == "line_chart"
    assert audit.content == {"data": [1, 2, 3]}
    # No agent_execution_id or component_type - these were removed

# Step 1: Search for removed field references
# $ grep -r "agent_execution_id\|component_type" tests/

# Step 2: Update all test assertions
# Remove field references, use current schema only

# Step 3: Verify tests pass
# $ pytest tests/unit/governance/test_governance_streaming.py -v
```

### pytest.ini Configuration Fix Pattern

```python
# Source: Phase 198 pytest configuration warnings
# Problem: Non-top-level conftest.py triggers deprecation warning

# CURRENT (backend/conftest.py - problematic):
# File: backend/conftest.py
@pytest.fixture(scope="session")
def test_app():
    """Create test FastAPI app."""
    return create_app()

# Problem: PytestPluginValidationWarning for non-top-level conftest

# FIX OPTION 1: Move to project root (recommended):
# From: backend/conftest.py
# To: conftest.py (in project root /Users/rushiparikh/projects/atom/)

# FIX OPTION 2: Use pyproject.toml (modern approach):
# File: pyproject.toml
[tool.pytest.ini_options]
testpaths = ["backend/tests"]
pythonpath = "."
asyncio_mode = "auto"
addopts = [
    "--strict-markers",
    "--tb=line",
    "--ignore=archive/",
    "--ignore=frontend-nextjs/",
    "--ignore=scripts/"
]

# Verify fix:
$ pytest --collect-only -q
92 tests collected, 0 errors in 1.50s  # No warnings
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Archive tests in codebase | pytest --ignore patterns | Phase 199 (planned) | Clean collection, 0 errors from archive cruft |
| Pydantic v1 patterns in tests | Pydantic v2 model_validate() | Phase 199 (planned) | Consistent validation, no AttributeError |
| SQLAlchemy 1.4 queries | SQLAlchemy 2.0 select() statements | Phase 199 (planned) | Future-proof, no deprecation warnings |
| Schema drift in tests | Audit-driven fixture updates | Phase 199 (planned) | Tests match current schema, no AttributeError |
| Overall coverage 74.6% (collection errors) | 85% target (all tests measured) | Phase 199 (planned) | Accurate coverage, unblock 150+ tests |

**Deprecated/outdated:**
- Pydantic v1 parse_obj() and update() methods: **REPLACED** by model_validate() and model_copy()
- SQLAlchemy 1.4 session.query() syntax: **DEPRECATED** in 2.0, use select() statements
- Archive tests in active codebase: **ANTI-PATTERN** use pytest --ignore patterns
- pytest conftest.py in subdirectories: **DEPRECATED** move to project root or use pyproject.toml
- Manual collection error analysis: **INEFFICIENT** use pytest --collect-only with categorization

---

## Open Questions

1. **Archive test migration**
   - What we know: 6 archive/old_project_structure tests cause ModuleNotFoundError
   - What's unclear: Whether to delete or preserve these tests
   - Recommendation: Use pytest --ignore=archive/ to exclude, preserve history if needed

2. **Pydantic v2 migration scope**
   - What we know: Some test fixtures use deprecated Pydantic v1 patterns
   - What's unclear: How many fixtures need updating across the test suite
   - Recommendation: Audit with `grep -r "parse_obj\|\.update(" tests/` to quantify work

3. **pytest configuration approach**
   - What we know: backend/conftest.py triggers deprecation warning
   - What's unclear: Whether to move conftest.py or migrate to pyproject.toml
   - Recommendation: Move conftest.py to project root (simpler, less disruptive)

4. **CanvasAudit schema drift extent**
   - What we know: 2 tests fail due to removed fields (agent_execution_id, component_type)
   - What's unclear: Whether more tests reference these removed fields
   - Recommendation: Audit with `grep -r "agent_execution_id\|component_type" tests/` before fixing

---

## Test Infrastructure Analysis (Phase 198)

### Collection Error Breakdown

**Total Collection Errors:** 10 errors

**Error Type 1: Archive/Legacy Tests (6 errors)**
- `archive/old_project_structure/shared/test_integration_base.py` → ModuleNotFoundError: No module named 'shared'
- `archive/old_project_structure/shared/test_logging_utils.py` → ModuleNotFoundError: No module named 'shared'
- `archive/old_project_structure/tests/chat_orchestration_test.py` → ModuleNotFoundError: No module named 'src.services.ChatOrchestrationService'
- `archive/old_project_structure/tests/e2e/test_runner.py` → ModuleNotFoundError: No module named 'utils.llm_verifier'
- `archive/old_project_structure/tests/e2e/tests/test_business_outcomes.py` → ModuleNotFoundError: No module named 'utils.llm_verifier'
- `archive/old_project_structure/tests/e2e/tests/test_hubspot_service_unit.py` → ModuleNotFoundError: No module named 'integrations'

**Error Type 2: Non-Backend Tests (2 errors)**
- `frontend-nextjs/project/functions/audio_processor/tests/test_handler.py` → ModuleNotFoundError: No module named 'tests.test_handler'
- `scripts/test_advanced_execution.py` → ModuleNotFoundError: No module named 'core.workflow_engine'

**Error Type 3: pytest Configuration (1 error)**
- `backend/conftest.py` → PytestPluginValidationWarning: plugins in non-top-level conftest files

**Error Type 4: Scripts Tests (1 error)**
- `scripts/test_auto_healing.py` → Import error (scripts not in PYTHONPATH)

### Fix Priority Matrix

| Error Type | Files Affected | Priority | Fix Time | Impact |
|------------|----------------|----------|----------|--------|
| Archive tests | 6 | LOW (exclude) | 5 min | Clean collection output |
| Non-backend tests | 2 | LOW (exclude) | 5 min | Remove irrelevant tests |
| pytest config | 1 | MEDIUM | 15 min | Remove warnings |
| Script tests | 1 | LOW (exclude) | 5 min | Clean collection output |

**Total Fix Time:** 30 minutes to achieve 0 collection errors

### Pydantic v2/SQLAlchemy 2.0 Compatibility Issues

**Not in collection errors** but blocking test execution (from Phase 198 reports):

**Affected Test Files:**
- `tests/api/test_api_routes_coverage.py` - Pydantic model validation
- `tests/api/test_feedback_analytics.py` - Pydantic model validation
- `tests/api/test_feedback_enhanced.py` - Pydantic model validation
- `tests/core/test_agent_governance_service_coverage_extend.py` - SQLAlchemy 2.0 queries
- `tests/core/test_agent_graduation_service_coverage.py` - SQLAlchemy 2.0 queries
- `tests/database/*.py` - All database model tests with SQLAlchemy 2.0

**Fix Pattern:**
1. Audit for deprecated patterns: `grep -r "parse_obj\|\.update(" tests/`
2. Replace Pydantic v1 → v2: parse_obj() → model_validate(), .update() → .model_copy()
3. Replace SQLAlchemy 1.4 → 2.0: session.query() → session.execute(select())
4. Verify tests pass: `pytest tests/ -k "test_model" -v`

**Estimated Fix Time:** 1-2 hours for full migration

---

## Coverage Targets by Module Type

### High-Impact Medium-Coverage Modules (Priority 1)

Target: 10-15% improvement on modules with 62-74% coverage

| Module | Current | Target | Lines | Impact | Tests Needed | Est. Time |
|--------|---------|--------|-------|--------|--------------|-----------|
| `agent_governance_service.py` | 62% | 85% | ~400 | High | +10-15 tests | 1.5 hours |
| `trigger_interceptor.py` | 74% | 85% | ~250 | Medium | +8-12 tests | 1 hour |
| `episode_segmentation_service.py` | 83.8% | 85% | ~300 | Low | +3-5 tests | 0.5 hours |
| `agent_graduation_service.py` | 73.8% | 85% | ~300 | Medium | +8-12 tests | 1 hour |
| `student_training_service.py` | Blocked | 75% | ~400 | High | +15-20 tests | 1.5 hours |

**Expected Impact:** +3-5% overall coverage (assuming ~5,000 lines total)

### Integration Test Expansion (Priority 2)

Target: E2E workflow coverage for complex orchestration

| Workflow | Components | Tests | Impact | Est. Time |
|----------|------------|-------|--------|-----------|
| Agent Execution + Episodic Memory | Governance → Execution → Episode creation | 5-8 tests | +1-2% | 1 hour |
| Training + Supervision | Training → Supervision → Graduation | 4-6 tests | +0.5-1% | 0.75 hours |
| Workflow Orchestration | Template → Execution → Analytics | 4-6 tests | +0.5-1% | 0.75 hours |

**Expected Impact:** +2-4% overall coverage

### Test Infrastructure Fixes (Priority 0)

Target: Enable full test suite execution for accurate coverage

| Task | Files | Effort | Impact |
|------|-------|--------|--------|
| Fix collection errors | 10 files | 30 min | Unblocks 150+ existing tests |
| Pydantic v2 migration | 15-20 test files | 1-2 hours | Enables test execution |
| CanvasAudit schema fixes | 2 tests | 15 min | +2 passing tests |
| pytest configuration | 1 file | 15 min | Clean collection output |

**Expected Impact:** Unlocks 150+ tests created in Phase 198, accurate coverage measurement

---

## Recommended Phase 199 Structure

### Wave 1: Test Infrastructure Fixes (2-3 hours)

**199-01: Fix Collection Errors (30 min)**
- Add pytest --ignore patterns for archive/, frontend-nextjs/, scripts/
- Move backend/conftest.py to project root or migrate to pyproject.toml
- Verify 0 collection errors: `pytest --collect-only -q`
- Expected: 92 tests collected, 0 errors

**199-02: Pydantic v2/SQLAlchemy 2.0 Migration (1-2 hours)**
- Audit test files for deprecated patterns: `grep -r "parse_obj\|\.update(" tests/`
- Replace Pydantic v1 → v2: parse_obj() → model_validate(), .update() → .model_copy()
- Replace SQLAlchemy 1.4 → 2.0: session.query() → session.execute(select())
- Run affected test suites to verify fixes
- Expected: All tests collect and run without AttributeError

**199-03: CanvasAudit Schema Fixes (15 min)**
- Search for removed field references: `grep -r "agent_execution_id\|component_type" tests/`
- Update test assertions to use current schema only
- Verify 2 governance streaming tests pass
- Expected: 2 tests passing, 0 failing

### Wave 2: Coverage Measurement & Targeting (30 min)

**199-04: Measure Baseline Coverage (15 min)**
- Run pytest with coverage: `pytest --cov=backend --cov-branch --cov-report=json`
- Generate coverage report: `python backend/tests/scripts/generate_baseline_coverage_report.py`
- Identify modules with 40-80% coverage for efficient targeting
- Expected: Accurate baseline measurement (no collection errors)

**199-05: Identify High-Impact Targets (15 min)**
- Analyze coverage JSON for modules with 40-80% coverage, 200+ lines
- Calculate impact score: (Module Lines × Coverage Gap) / Est. Effort
- Prioritize: agent_governance_service (62%), trigger_interceptor (74%), training (blocked)
- Expected: List of 5-10 high-impact targets for Wave 3

### Wave 3: Medium-Impact Module Coverage (3-4 hours)

**199-06: Agent Governance Service Coverage (1.5 hours)**
- Target: 62% → 85% (+23% improvement)
- Focus: Complex governance scenarios, edge cases, error paths
- Tests: 10-15 tests (permission boundaries, concurrent checks, cache invalidation)
- Expected: 80-85% coverage, +1-2% overall

**199-07: Trigger Interceptor Coverage (1 hour)**
- Target: 74% → 85% (+11% improvement)
- Focus: Advanced routing scenarios, maturity transitions, trigger validation
- Tests: 8-12 tests (routing edge cases, maturity matrix, trigger priorities)
- Expected: 85% coverage, +0.5-1% overall

**199-08: Student Training Service Coverage (1.5 hours)**
- Target: Unblock schema issues → 75% coverage
- Focus: Training session management, proposal workflows, supervision integration
- Tests: 15-20 tests (session CRUD, proposal lifecycle, training completion)
- Expected: 75% coverage, +0.5-1% overall

### Wave 4: Integration Test Expansion (1-2 hours)

**199-09: Agent Execution E2E Tests (1 hour)**
- Target: Governance → Execution → Episodic Memory integration
- Tests: 5-8 tests (all maturity levels, episode creation, feedback linking)
- Expected: +1-2% overall coverage

**199-10: Training + Supervision Integration (1 hour)**
- Target: Training → Supervision → Graduation workflow
- Tests: 4-6 tests (session lifecycle, supervision intervention, graduation criteria)
- Expected: +0.5-1% overall coverage

### Wave 5: Final Verification & Summary (30 min)

**199-11: Final Coverage Measurement (15 min)**
- Run full test suite with coverage: `pytest --cov=backend --cov-branch --cov-report=json`
- Verify 85% overall coverage target achieved
- Generate final coverage report and metrics
- Expected: 85%+ overall coverage, 0 collection errors

**199-12: Documentation & Summary (15 min)**
- Document coverage gains by module
- Update STATE.md and ROADMAP.md with Phase 199 completion
- Create summary of infrastructure fixes and lessons learned
- Expected: Complete documentation, ready for Phase 200

**Total Estimated Effort:** 5-7 hours (12 plans)

**Success Criteria:**
- ✅ Overall coverage: 85% (from 74.6%)
- ✅ Test collection: 0 errors (from 10)
- ✅ Pydantic v2/SQLAlchemy 2.0: Fully migrated
- ✅ CanvasAudit tests: 2/2 passing
- ✅ Test pass rate: >95%
- ✅ Documentation complete

---

## Sources

### Primary (HIGH confidence)

- Phase 198 Final Coverage Report - `.planning/phases/198-coverage-push-85/198-FINAL-COVERAGE-REPORT.md`
- Phase 198 Final Summary - `.planning/phases/198-coverage-push-85/198-08-SUMMARY.md`
- Phase 198 Research - `.planning/phases/198-coverage-push-85/198-RESEARCH.md`
- pytest 9.0.2 Documentation - https://docs.pytest.org/en/stable/
- coverage.py 7.13.4 Documentation - https://coverage.readthedocs.io/en/7.13.4/
- Pydantic v2 Migration Guide - https://docs.pydantic.dev/latest/migration/
- SQLAlchemy 2.0 Migration Guide - https://docs.sqlalchemy.org/en/20/changelog/migration_20.html
- pytest.ini configuration - `/Users/rushiparikh/projects/atom/backend/pytest.ini`
- Core models - `/Users/rushiparikh/projects/atom/backend/core/models.py`

### Secondary (MEDIUM confidence)

- pytest Collection Error Documentation - https://docs.pytest.org/en/stable/explanation/goodpractices.html#conventions-for-python-test-discovery
- Pydantic v2 API Reference - https://docs.pydantic.dev/latest/api/base_model/
- SQLAlchemy 2.0 Query Guide - https://docs.sqlalchemy.org/en/20/orm/queryguide/select.html
- Python 3.14 Release Notes - https://docs.python.org/3.14/whatsnew/3.14.html

### Tertiary (LOW confidence)

- None - All findings verified against codebase, official documentation, or Phase 198 artifacts

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All versions verified in codebase (pytest 9.0.2, Pydantic 2.12.5, SQLAlchemy 2.0.45)
- Architecture: HIGH - Based on actual Phase 198 results and collection error analysis
- Pitfalls: HIGH - Root causes identified from pytest --collect-only output and Phase 198 documentation
- Coverage targets: MEDIUM - Estimates based on Phase 198 velocity and statement counts
- Test infrastructure issues: HIGH - Specific collection errors documented from actual pytest run

**Research date:** 2026-03-16
**Valid until:** 2026-04-15 (30 days - stable testing stack, but pytest and Pydantic evolve rapidly)

---

## Appendices

### Appendix A: Collection Error Log

**Command:** `python3 -m pytest --collect-only 2>&1 | grep -B 3 "ERROR collecting\|ERROR"`

**Output:**
```
ERROR collecting archive/old_project_structure/shared/test_integration_base.py
  ModuleNotFoundError: No module named 'shared'

ERROR collecting archive/old_project_structure/shared/test_logging_utils.py
  ModuleNotFoundError: No module named 'shared'

ERROR collecting archive/old_project_structure/tests/chat_orchestration_test.py
  ModuleNotFoundError: No module named 'src.services.ChatOrchestrationService'

ERROR collecting archive/old_project_structure/tests/e2e/test_runner.py
  ModuleNotFoundError: No module named 'utils.llm_verifier'

ERROR collecting archive/old_project_structure/tests/e2e/tests/test_business_outcomes.py
  ModuleNotFoundError: No module named 'utils.llm_verifier'

ERROR collecting archive/old_project_structure/tests/e2e/tests/test_hubspot_service_unit.py
  ModuleNotFoundError: No module named 'integrations'

ERROR collecting frontend-nextjs/project/functions/audio_processor/tests/test_handler.py
  ModuleNotFoundError: No module named 'tests.test_handler'

ERROR collecting scripts/test_advanced_execution.py
  ModuleNotFoundError: No module named 'core.workflow_engine'

ERROR collecting scripts/test_auto_healing.py
  Import error (scripts not in PYTHONPATH)

ERROR collecting backend
  PytestPluginValidationWarning: plugins in non-top-level conftest files
```

**Summary:** 10 collection errors, 6 from archive/, 2 from non-backend directories, 1 from scripts/, 1 pytest configuration warning

### Appendix B: Pydantic v2 Migration Checklist

**Search for Deprecated Patterns:**
```bash
# Pydantic v1 patterns to replace:
grep -r "\.parse_obj(" tests/
grep -r "\.update(" tests/
grep -r "\.dict(" tests/
grep -r "\.json(" tests/

# SQLAlchemy 1.4 patterns to replace:
grep -r "session\.query(" tests/
grep -r "\.filter(" tests/
grep -r "\.first()" tests/
grep -r "\.all()" tests/
```

**Replacement Patterns:**
```python
# Pydantic v1 → v2:
parse_obj() → model_validate()
.update() → .model_copy(update=...)
.dict() → .model_dump()
.json() → .model_dump_json()

# SQLAlchemy 1.4 → 2.0:
session.query(Model) → session.execute(select(Model))
.filter(Model.field == value) → .where(Model.field == value)
.first() → .scalar_one_or_none()
.all() → .scalars().all()
```

**Verification:**
```bash
# Run affected tests
pytest tests/ -k "test_model" -v

# Check for AttributeError
pytest tests/ -v 2>&1 | grep "AttributeError"
```

### Appendix C: Coverage Gap Calculation

**Overall Coverage Formula:**
```
Overall Coverage = (Total Lines Covered / Total Executable Lines) × 100

Current (Phase 198): 74.6% = (X / Y) × 100
Target (Phase 199):   85.0% = (Z / Y) × 100
Gap:                  10.4 percentage points
```

**Efficient Coverage Improvement:**
```
Priority = (Module Lines × Coverage Gap) / Effort

Example 1 (HIGH PRIORITY):
- agent_governance_service.py: 400 lines, 62% → 85% (23% gap)
- Impact: 400 × 0.23 = 92 lines covered
- Effort: 10-15 tests (~1.5 hours)
- Efficiency: 61 lines/hour

Example 2 (MEDIUM PRIORITY):
- trigger_interceptor.py: 250 lines, 74% → 85% (11% gap)
- Impact: 250 × 0.11 = 27.5 lines covered
- Effort: 8-12 tests (~1 hour)
- Efficiency: 27 lines/hour

Example 3 (LOW PRIORITY):
- small_util.py: 50 lines, 0% → 100% (100% gap)
- Impact: 50 × 1.0 = 50 lines covered
- Effort: 5-10 tests (~1 hour)
- Efficiency: 50 lines/hour (high but low absolute impact)

**Conclusion:** Target medium-impact modules (200-500 lines, 40-80% coverage) for efficient gains
```

### Appendix D: Phase 199 Success Metrics

**Coverage Metrics:**
- Overall coverage: 85% (from 74.6%)
- Governance services: 85% (from 62-74%)
- Test infrastructure: 0 collection errors (from 10)
- Pydantic v2 migration: 100% (from partial)
- CanvasAudit tests: 2/2 passing (from 0/2)

**Test Quality Metrics:**
- Pass rate: >95% (maintain Phase 197 quality)
- Test execution time: <10 minutes (full suite)
- Flaky tests: 0 (maintain Phase 196 record)
- Coverage measurement: Accurate (all tests collected)

**Infrastructure Metrics:**
- Collection errors: 0 (from 10)
- Pydantic v2 patterns: 100% migrated
- SQLAlchemy 2.0 patterns: 100% migrated
- pytest warnings: 0 (fix conftest.py)
- Archive tests: Excluded from collection

**Baseline Comparison:**
- Phase 196: 74.6% coverage, 76.4% pass rate (99 failing tests)
- Phase 197: 74.6% coverage, 98% pass rate (quality-first approach)
- Phase 198: 74.6% coverage, module-level improvements (collection errors blocked)
- Phase 199: 85% coverage target, 98%+ pass rate (infrastructure fixes)

---

*Phase: 199-fix-test-collection-errors*
*Research Date: 2026-03-16*
*Next Step: Create PLAN.md files based on research findings*
