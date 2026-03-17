# Phase 205: Coverage Quality & Target Achievement - Research

**Researched:** 2026-03-17
**Domain:** Test Coverage Quality, Async Mocking Patterns, Schema Alignment
**Confidence:** HIGH

## Summary

Phase 205 focuses on resolving the technical blockers that prevented Phase 204 from achieving the 75% coverage target. The three priority areas are: (1) Fix async service mocking for creative/productivity routes (11 failing tests), (2) Align workflow_debugger schema (10 blocked tests), and (3) Address 10 collection errors (import file mismatches, deprecated pytest_plugins). Based on Phase 204 completion data, these fixes combined should unlock enough coverage to achieve the 75% target (0.31pp gap from 74.69%).

**Primary recommendation:** Execute a quality-first blocker resolution phase with 3-4 focused plans addressing async mocking, schema alignment, and collection errors in priority order, then measure final coverage.

## User Constraints

No CONTEXT.md exists for this phase. The following constraints are derived from Phase 204 completion summary and STATE.md decisions:

### Locked Decisions (from Phase 204)
- Quality-first approach validated in Phase 203-204 - maintain this standard
- Fix blockers before new coverage work (test infrastructure stability critical)
- Module-focused testing approach works well - continue this pattern
- Wave-based execution pattern validated - use for this phase
- Realistic targets accepted for complex orchestration - maintain this mindset

### Claude's Discretion
- Priority order: async mocking → schema alignment → collection errors → coverage measurement
- Whether to fix all blockers or focus on highest-impact items first
- Whether to create new tests after fixing blockers or measure existing test coverage
- Target: 75% overall (achievable) vs 80% (may require additional new tests)

### Deferred Ideas (from Phase 204)
- Comprehensive schema audit across all models (out of scope - focus on workflow_debugger only)
- Rewrite test infrastructure (out of scope - existing patterns work well)

## Standard Stack

### Core Testing Libraries
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | 7.4+ | Test framework and test discovery | Industry standard for Python testing, mature ecosystem |
| **pytest-cov** | 4.1+ | Coverage measurement plugin | Official pytest coverage plugin, integrates with coverage.py |
| **pytest-asyncio** | 0.21+ | Async test support | Standard for testing async/await code, auto mode enabled |
| **unittest.mock** | (stdlib) | Mocking library (AsyncMock, MagicMock) | Python stdlib, AsyncMock for async coroutine mocking |
| **FastAPI TestClient** | (fastapi) | API endpoint testing | Official FastAPI testing utility, handles async routes |

### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pytest-mock** | 3.10+ | Mock fixture (mocker) | When mocker fixture provides cleaner syntax than patch |
| **factory_boy** | (installed) | Test data factories | For complex model creation (already in project) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| unittest.mock.AsyncMock | Manual async mocking | AsyncMock handles coroutines, async iteration, context managers correctly; manual requires more code |
| TestClient (sync wrapper) | httpx.AsyncClient | TestClient simpler for route testing, AsyncClient requires more setup |
| Schema alignment | Workarounds in tests | Schema fix permanent solution, workarrows create technical debt |

**Installation:**
```bash
# All dependencies already installed (from Phase 204)
pip install pytest pytest-cov pytest-asyncio pytest-mock
# FastAPI TestClient comes with fastapi
```

## Architecture Patterns

### Recommended Project Structure (Test Organization)
```
backend/tests/
├── api/                          # API route tests
│   ├── test_smarthome_routes_coverage.py     # ✅ Working pattern (100% pass)
│   ├── test_creative_routes_coverage.py      # ⚠️ Needs async mock fix
│   └── test_productivity_routes_coverage.py  # ⚠️ Needs NotionService mock fix
├── core/                         # Core service tests
│   ├── test_workflow_debugger_coverage.py    # ⚠️ Needs schema alignment
│   └── test_debug_alerting_coverage.py       # ⚠️ Import issues
└── coverage/                     # Coverage aggregation
    └── test_coverage_aggregation.py          # ✅ Verification tests
```

### Pattern 1: AsyncMock for Async Service Instance Mocking

**What:** Mock async service methods that are called within route handlers using AsyncMock from unittest.mock. This provides cleaner async mocking than manual async mocking.

**When to use:** Route handlers call `service = get_ffmpeg_service()` then await methods on the service instance.

**Example:**
```python
# Source: Phase 204 Plan 05 summary (smart home routes working pattern)

from unittest.mock import AsyncMock, patch

def test_trim_video_success(client):
    """Test video trimming endpoint with successful response."""
    request_data = {
        "input_path": "/videos/input.mp4",
        "output_path": "/videos/output.mp4",
        "start_time": "00:01:00",
        "duration": "00:00:30"
    }

    # Mock FFmpegService instance and its async methods
    with patch("api.creative_routes.FFmpegService") as MockFFmpeg:
        mock_instance = Mock()
        mock_instance.validate_path = Mock(return_value=True)
        mock_instance.trim_video = AsyncMock(return_value={
            "job_id": "job-123",
            "status": "pending"
        })
        MockFFmpeg.return_value = mock_instance

        response = client.post("/creative/video/trim", json=request_data)

        assert response.status_code == 200
        assert response.json()["job_id"] == "job-123"
        assert response.json()["status"] == "pending"
```

**Key insight:** Route creates service instance via `get_ffmpeg_service()`, so patch the constructor and return a mock instance with AsyncMock methods.

### Pattern 2: AsyncMock for Class Method Mocking (NotionService)

**What:** Mock async class methods using `AsyncMock` when the service is instantiated with user_id and class methods are called.

**When to use:** Routes call `service = NotionService(current_user.id)` then await class methods.

**Example:**
```python
# Source: Phase 204 Plan 05 summary (productivity routes pattern)

def test_get_authorization_url_success(client):
    """Test getting Notion OAuth authorization URL."""
    with patch("api.productivity_routes.NotionService") as MockNotion:
        mock_instance = Mock()
        mock_instance.get_authorization_url = AsyncMock(
            return_value="https://notion.so/authorize?client_id=..."
        )
        MockNotion.return_value = mock_instance

        response = client.get(
            "/productivity/integrations/notion/authorize",
            params={"user_id": "test-user-123"}
        )

        assert response.status_code == 200
        assert "notion.so/authorize" in response.json()["authorization_url"]
```

**Key insight:** NotionService is instantiated with user_id, then class methods are awaited. Patch the class and return a mock instance with AsyncMock methods.

### Pattern 3: TestClient with Dependency Override

**What:** Use FastAPI's TestClient with dependency overrides for authentication mocking. This avoids real authentication while testing route logic.

**When to use:** All API routes require `get_current_user` dependency for authentication.

**Example:**
```python
# Source: backend/tests/api/test_smarthome_routes_coverage.py (working pattern)

from fastapi import FastAPI
from fastapi.testclient import TestClient

@pytest.fixture
def client():
    """Create FastAPI TestClient for smart home routes."""
    app = FastAPI()
    app.include_router(router)

    # Mock get_current_user dependency
    async def get_current_user_override():
        return Mock(id="test-user-123", username="testuser")

    from core.security_dependencies import get_current_user
    app.dependency_overrides[get_current_user] = get_current_user_override

    return TestClient(app)
```

**Key insight:** Dependency overrides happen at app level, not per request. Clean up overrides in fixture teardown if needed.

### Pattern 4: Schema Alignment for Workflow Debugger

**What:** Align test expectations with actual model schema in core/models.py to fix AttributeError issues. Tests expect attributes that don't exist on models.

**When to use:** Tests fail with `AttributeError: type object 'WorkflowBreakpoint' has no attribute 'node_id'`.

**Current Schema (from models.py):**
```python
class WorkflowBreakpoint(Base):
    id = Column(String, primary_key=True)
    workflow_id = Column(String, nullable=False)
    step_id = Column(String(255), nullable=False)  # ✅ Exists
    condition = Column(Text, nullable=True)
    enabled = Column(Boolean, default=True)  # ✅ Exists
    hit_count = Column(Integer, default=0)
    created_by = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # ❌ No 'node_id' attribute
    # ❌ No 'is_active' attribute
    # ❌ No 'debug_session_id' attribute
```

**Test expectations (from test_workflow_debugger_coverage.py):**
```python
# Tests create breakpoints with these attributes:
breakpoint = WorkflowBreakpoint(
    workflow_id="wf-1",
    step_id="step-1",  # ✅ Matches
    node_id="node-1",  # ❌ DOESN'T EXIST
    is_active=True,    # ❌ Should be 'enabled'
    debug_session_id="session-1"  # ❌ DOESN'T EXIST
)
```

**Fix options:**
1. **Update tests to match schema** (recommended, lower risk)
   - Change `node_id` → `step_id`
   - Change `is_active` → `enabled`
   - Remove `debug_session_id` from WorkflowBreakpoint

2. **Update schema to match tests** (higher risk, affects production code)
   - Add `node_id` column to WorkflowBreakpoint
   - Add `debug_session_id` column
   - Rename `enabled` → `is_active`

**Recommendation:** Update tests to match schema (Option 1). Schema changes require migrations and affect production code.

### Anti-Patterns to Avoid

- **Direct import mocking** - Don't mock `from core.creative.ffmpeg_service import FFmpegService` at module level; patch where it's used
- **Synchronous mock for async methods** - Don't use `Mock()` for async methods, use `AsyncMock()` or tests will fail
- **Hardcoded mock returns** - Avoid returning same data for all tests; use `side_effect` for different scenarios
- **Missing dependency cleanup** - Always clean up `app.dependency_overrides = {}` in fixture teardown if modifying at app level

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async coroutine mocking | Manual async wrapper | `unittest.mock.AsyncMock` | Handles coroutines, async iteration, context managers correctly |
| Route testing | Custom HTTP client | `FastAPI TestClient` | Handles async routes, dependency injection, request validation |
| Service mocking | Custom mock classes | `unittest.mock.Mock` + `AsyncMock` | Standard library, well-documented, flexible |
| Schema migration | Manual schema updates | Alembic migrations | Version-controlled, reversible, production-safe |

**Key insight:** AsyncMock is part of Python stdlib (3.8+), specifically designed for mocking async code. Don't reinvent async mocking with custom coroutines or futures.

## Common Pitfalls

### Pitfall 1: Mock Patch Location Incorrect

**What goes wrong:** Patch at import location instead of usage location causes mock to not apply.

**Why it happens:** Routes import `FFmpegService` at module level (`from core.creative.ffmpeg_service import FFmpegService`), so patching the full module path fails.

**How to avoid:** Patch where the name is used, not where it's defined.
```python
# ❌ WRONG - patches definition, not usage
with patch("core.creative.ffmpeg_service.FFmpegService"):

# ✅ CORRECT - patches import location in route file
with patch("api.creative_routes.FFmpegService"):
```

**Warning signs:** Mock appears to not affect code, no errors but original code executes.

### Pitfall 2: Not Using AsyncMock for Async Methods

**What goes wrong:** Using regular `Mock()` for async methods causes tests to fail with coroutine-related errors.

**Why it happens:** Async methods return coroutines, which must be awaited. Regular Mock doesn't handle this.

**How to avoid:** Always use `AsyncMock` for async methods.
```python
# ❌ WRONG - regular Mock for async method
mock_service.trim_video = Mock(return_value={"job_id": "job-1"})

# ✅ CORRECT - AsyncMock for async method
from unittest.mock import AsyncMock
mock_service.trim_video = AsyncMock(return_value={"job_id": "job-1"})
```

**Warning signs:** Tests fail with "coroutine object is not iterable" or "TypeError: object MagicMock can't be used in 'await' expression".

### Pitfall 3: Import File Mismatch (Collection Errors)

**What goes wrong:** Pytest collection fails with "import file mismatch" errors when test files have same name in different directories.

**Why it happens:** Pytest imports test modules by filename, causing conflicts when `tests/core/test_workflow_debugger_coverage.py` and `tests/core/workflow/test_workflow_debugger_coverage.py` both exist.

**How to avoid:** Ensure unique test filenames or use explicit imports. Phase 204 has 10 collection errors from this issue.

**Current errors:**
- `tests/core/test_agent_social_layer_coverage.py` vs `tests/core/agents/test_agent_social_layer_coverage.py`
- `tests/core/test_skill_registry_service_coverage.py` vs `tests/core/skills/test_skill_registry_service_coverage.py`
- `tests/core/test_workflow_debugger_coverage.py` vs `tests/core/workflow/test_workflow_debugger_coverage.py`
- `tests/core/test_workflow_engine_coverage.py` vs `tests/core/workflow/test_workflow_engine_coverage.py`
- `tests/core/test_workflow_template_system_coverage.py` vs `tests/core/workflow/test_workflow_template_system_coverage.py`

**Fix:** Rename duplicate files or add to ignore patterns in pytest.ini.

### Pitfall 4: Pytest Plugins in Non-Top-Level Conftest

**What goes wrong:** ERROR: "Defining 'pytest_plugins' in a non-top-level conftest is no longer supported"

**Why it happens:** `backend/conftest.py` defines `pytest_plugins` at subdirectory level, deprecated in pytest 7.4+.

**How to avoid:** Move `pytest_plugins` to top-level conftest or use alternative plugin registration.

**Current issue:** `backend/conftest.py` has pytest_plugins definition causing collection error.

**Fix:** Move to root conftest (`/Users/rushiparikh/projects/atom/conftest.py`) or use `pytest_configure` hook.

### Pitfall 5: Schema Drift Between Tests and Models

**What goes wrong:** Tests fail with AttributeError because model schema doesn't match test expectations.

**Why it happens:** Code evolves but tests aren't updated, or tests were written against intended schema that was never implemented.

**How to avoid:** Align tests with actual schema from `core/models.py`, not intended schema.

**Current issue (workflow_debugger):**
- Tests expect `WorkflowBreakpoint.node_id` → schema has `step_id`
- Tests expect `WorkflowBreakpoint.is_active` → schema has `enabled`
- Tests expect `WorkflowBreakpoint.debug_session_id` → doesn't exist
- Tests expect `ExecutionTrace.workflow_id` → schema doesn't have it
- Tests expect `DebugVariable.trace_id` → schema doesn't have it

**Fix:** Update tests to use correct attribute names from actual schema.

## Code Examples

Verified patterns from Phase 204 working tests and standard library documentation:

### Example 1: Async Service Mocking (Creative Routes Fix)

```python
# Source: Phase 204 Plan 05 summary + unittest.mock docs

from unittest.mock import AsyncMock, patch

def test_trim_video_success(client, db_session):
    """Test video trimming with proper async service mocking."""
    request_data = {
        "input_path": "/videos/input.mp4",
        "output_path": "/videos/output.mp4",
        "start_time": "00:01:00",
        "duration": "00:00:30"
    }

    # Patch FFmpegService at usage location (api.creative_routes)
    with patch("api.creative_routes.FFmpegService") as MockFFmpeg:
        # Create mock instance with async methods
        mock_instance = Mock()
        mock_instance.validate_path = Mock(return_value=True)
        mock_instance.trim_video = AsyncMock(return_value={
            "job_id": "job-123",
            "status": "pending"
        })

        # Return mock instance when FFmpegService() is called
        MockFFmpeg.return_value = mock_instance

        # Call endpoint
        response = client.post("/creative/video/trim", json=request_data)

        # Assertions
        assert response.status_code == 200
        assert response.json()["job_id"] == "job-123"

        # Verify async method was called
        mock_instance.trim_video.assert_awaited_once_with(
            input_path="/videos/input.mp4",
            output_path="/videos/output.mp4",
            start_time="00:01:00",
            duration="00:00:30"
        )
```

### Example 2: Class Method Mocking (Productivity Routes Fix)

```python
# Source: Phase 204 Plan 05 summary

def test_get_authorization_url_success(client):
    """Test Notion OAuth URL generation with class method mocking."""
    with patch("api.productivity_routes.NotionService") as MockNotion:
        # Create mock instance
        mock_instance = Mock()

        # Mock async class method
        mock_instance.get_authorization_url = AsyncMock(
            return_value="https://notion.so/authorize?client_id=xxx&state=yyy"
        )

        # Return mock instance when NotionService(user_id) is called
        MockNotion.return_value = mock_instance

        # Call endpoint
        response = client.get(
            "/productivity/integrations/notion/authorize",
            params={"user_id": "test-user-123", "workspace_id": "workspace-1"}
        )

        # Assertions
        assert response.status_code == 200
        assert "notion.so/authorize" in response.json()["authorization_url"]
        assert response.json()["provider"] == "notion"

        # Verify class method was called
        mock_instance.get_authorization_url.assert_awaited_once()
```

### Example 3: Schema Alignment (Workflow Debugger Fix)

```python
# Source: Phase 204 Plan 03 summary + actual schema from models.py

def test_add_breakpoint_success(db_session):
    """Test adding breakpoint with correct schema attributes."""
    debugger = WorkflowDebugger(db=db_session)

    # ✅ CORRECT - Use actual schema attributes
    breakpoint = WorkflowBreakpoint(
        workflow_id="wf-1",
        step_id="step-1",  # ✅ step_id (not node_id)
        enabled=True,      # ✅ enabled (not is_active)
        condition="x > 10",
        created_by="user-1"
    )

    # ❌ WRONG - These attributes don't exist in schema
    # breakpoint = WorkflowBreakpoint(
    #     workflow_id="wf-1",
    #     node_id="node-1",        # ❌ Doesn't exist
    #     is_active=True,          # ❌ Should be 'enabled'
    #     debug_session_id="sess"  # ❌ Doesn't exist
    # )

    # Mock database operations
    mock_query_result = Mock()
    mock_query_result.first = Mock(return_value=None)
    db_session.query.return_value = mock_query_result

    result = debugger.add_breakpoint(
        workflow_id="wf-1",
        step_id="step-1",
        condition="x > 10"
    )

    assert result is not None
    assert result.step_id == "step-1"
    assert result.enabled == True
```

### Example 4: Collection Error Fix (pytest.ini Configuration)

```python
# Source: pytest.ini Phase 204 configuration

# Fix 1: Add duplicate test files to ignore patterns
# --ignore=tests/core/test_agent_social_layer_coverage.py
# --ignore=tests/core/test_skill_registry_service_coverage.py
# --ignore=tests/core/test_workflow_debugger_coverage.py
# --ignore=tests/core/test_workflow_engine_coverage.py
# --ignore=tests/core/test_workflow_template_system_coverage.py

# Fix 2: Move pytest_plugins to top-level conftest
# Create /Users/rushiparikh/projects/atom/conftest.py:
"""
Root conftest for pytest plugin registration.
"""
import pytest

pytest_plugins = [
    "tests.e2e_ui.fixtures.auth_fixtures",
    "tests.e2e_ui.fixtures.database_fixtures",
    # ... other plugins
]

# Remove pytest_plugins from backend/conftest.py
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual async mocking | `unittest.mock.AsyncMock` | Python 3.8 | Cleaner async mocking, built-in support for coroutines |
| pytest_plugins in any conftest | Top-level only | pytest 7.4+ | Must move plugin registration to root conftest |
| Test file naming conflict | Unique names or ignore | Phase 200 | Collection errors require explicit ignores |

**Deprecated/outdated:**
- **Manual async mocking:** Creating async wrapper functions or using `asyncio.create_task` for mocking - AsyncMock (3.8+) handles this
- **pytest_plugins in subdirectory conftest:** No longer supported in pytest 7.4+, causes collection errors
- **Hardcoded schema in tests:** Tests should verify actual schema, not intended schema

## Open Questions

1. **Should Phase 205 fix all 3 blockers or prioritize highest-impact first?**
   - What we know: Async mocking (11 tests) + schema drift (10 tests) = 21 blocked tests. Collection errors (10) prevent clean test runs.
   - What's unclear: Whether to tackle all 3 in parallel or sequence. Sequencing may allow better measurement of each fix's impact.
   - Recommendation: Tackle in priority order (async mocking → schema → collection errors) to measure incremental coverage gains.

2. **Should Phase 205 aim for 75% or 80% overall coverage?**
   - What we know: Current baseline 74.69%, gap to 75% is 0.31pp (~8 lines), gap to 80% is 5.31pp (~58 lines).
   - What's unclear: Whether fixing blockers alone achieves 75%, or if additional new tests needed.
   - Recommendation: Aim for 75% as realistic target, measure after fixing blockers. If 75% achieved, assess effort for 80%.

3. **Schema alignment approach: Update tests or update models?**
   - What we know: Tests expect `node_id`, `is_active`, `debug_session_id` attributes. Schema has `step_id`, `enabled` instead.
   - What's unclear: Whether schema changes are production-critical or test-only.
   - Recommendation: Update tests to match schema (lower risk). Document desired schema changes for future migration.

## Sources

### Primary (HIGH confidence)
- **Python 3.11 unittest.mock documentation** - AsyncMock usage, patch location best practices
- **FastAPI 0.100+ TestClient documentation** - Testing async routes, dependency overrides
- **pytest 7.4+ documentation** - pytest_plugins deprecation, collection configuration
- **Phase 204 Plan 05 summary** - Working smart home routes pattern (100% pass rate)
- **Phase 204 Plan 03 summary** - Schema drift issues in workflow_debugger
- **backend/core/models.py** - Actual schema for WorkflowBreakpoint, WorkflowDebugSession, DebugEvent, ExecutionTrace, DebugVariable

### Secondary (MEDIUM confidence)
- **backend/tests/api/test_smarthome_routes_coverage.py** - Verified working AsyncMock pattern
- **backend/tests/api/test_creative_routes_coverage.py** - Current failing tests requiring fix
- **backend/tests/api/test_productivity_routes_coverage.py** - Current failing tests requiring fix
- **backend/tests/core/test_workflow_debugger_coverage.py** - Current failing tests requiring schema alignment
- **backend/pytest.ini** - Current collection error configuration (10 errors)
- **backend/conftest.py** - pytest_plugins configuration causing collection error

### Tertiary (LOW confidence)
- No web search sources (rate limit encountered)
- All findings based on code inspection and Phase 204 documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries are Python stdlib or project-verified from Phase 204
- Architecture: HIGH - Working patterns from Phase 204 smart home routes (100% pass rate)
- Pitfalls: HIGH - Collection errors and schema drift directly observed in current codebase
- Async mocking: HIGH - Based on Python 3.11 stdlib documentation and verified working examples
- Schema alignment: MEDIUM - Requires decision on test updates vs model changes

**Research date:** 2026-03-17
**Valid until:** 30 days (stable domain - testing patterns don't change frequently)
