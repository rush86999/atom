# Phase 111: Phase 101 Fixes - Research

**Researched:** 2026-03-01
**Domain:** Python Testing Infrastructure (pytest, pytest-cov, unittest.mock)
**Confidence:** HIGH

## Summary

Phase 101 attempted to add 182 unit tests across 6 backend services but achieved only partial success (5/6 services at 60%+ coverage) due to two critical blockers: **mock configuration issues** and **coverage module import failures**. Phase 111 must resolve these technical debt items before v5.1 can proceed with expansion work.

The blockers are well-documented with clear solutions already attempted in Phase 101. The completion report shows that mock fixes were applied successfully, achieving 5/6 services meeting target. However, v5.1 requirements still mark FIX-01 and FIX-02 as pending, suggesting either incomplete fixes or regression requiring re-verification.

**Primary recommendation:** Re-verify and stabilize the fixes from Phase 101, ensure all 66 canvas tests pass with proper mock configuration, and confirm coverage.py accurately measures all 6 target backend services before proceeding to expansion phases.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | 7.4+ | Test framework | De facto standard for Python testing, superior to unittest |
| **pytest-cov** | 4.1+ | Coverage plugin | Coverage.py integration for pytest, industry standard |
| **coverage.py** | 7.3+ | Coverage measurement | Gold standard for Python code coverage |
| **unittest.mock** | Built-in | Mocking framework | Python standard library mocking, no dependencies needed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pytest-asyncio** | 0.21+ | Async test support | Required for testing async/await code (WebSocket, DB) |
| **pytest-rerunfailures** | 12.0+ | Flaky test detection | Auto-retry failed tests up to 2 times (configured in pytest.ini) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| unittest.mock | mock (external) | unittest.mock is stdlib, no advantage to external package |
| pytest-cov | coverage.py CLI | pytest-cov integrates better with pytest, automatic collection |
| pytest | nose2 | nose2 is deprecated, pytest has larger ecosystem |

**Installation:**
```bash
pip install pytest pytest-cov pytest-asyncio pytest-rerunfailures
```

## Architecture Patterns

### Recommended Mock Configuration Strategy

**What:** Use spec-based Mock objects with all required attributes pre-configured

**When to use:** All unit tests that interact with database models or external services

**Example:**
```python
# Source: Phase 101 successful fixes in test_canvas_tool_coverage.py

from core.models import AgentRegistry, AgentStatus
from unittest.mock import Mock, MagicMock

@pytest.fixture
def mock_agent():
    """Mock agent registry with ALL required attributes."""
    agent = Mock(spec=AgentRegistry)  # Enforces interface
    agent.id = "test-agent-1"
    agent.name = "TestAgent"
    agent.status = AgentStatus.AUTONOMOUS.value
    agent.workspace_id = "default"
    agent.confidence_score = 0.95  # Float: 0.0 to 1.0 (CRITICAL: was missing)
    agent.category = "Testing"
    agent.module_path = "test.test_agent"
    agent.class_name = "TestAgent"
    agent.user_id = "test-user-1"
    agent.required_role_for_autonomy = "team_lead"
    return agent
```

**Key insight:** Mock objects must have ALL attributes that production code accesses. Missing attributes cause `TypeError: '>=' not supported between instances of 'Mock' and 'float'` when production code compares `agent.confidence_score >= 0.9`.

### Pattern 2: Enum-like Mock Return Values

**What:** Mock functions that return enum-like types must include `.value` attribute

**When to use:** Mocking `get_min_maturity()` or similar enum-returning functions

**Example:**
```python
# Source: Phase 101 test_canvas_tool_coverage.py lines 133-145

@pytest.fixture(autouse=True)
def mock_canvas_type_registry():
    """Mock canvas type registry with maturity requirements."""
    with patch('tools.canvas_tool.canvas_type_registry') as mock_registry:

        # Mock get_min_maturity to return maturity levels
        def mock_get_min_maturity(canvas_type):
            maturity_requirements = {
                "generic": "student",
                "sheets": "student",
                "docs": "student",
                # ... map all canvas types to maturity levels
            }
            return maturity_requirements.get(canvas_type, "student")

        mock_registry.get_min_maturity = Mock(side_effect=mock_get_min_maturity)
        yield mock_registry
```

**Alternative (if enum has .value):**
```python
# If get_min_maturity() returns MaturityLevel enum with .value attribute
mock_maturity = Mock()
mock_maturity.value = "student"  # Enum-like return value
mock_registry.get_min_maturity.return_value = mock_maturity
```

**Key insight:** Returning string `"student"` works if production code compares strings. Returning `Mock(value="student")` works if production code accesses `.value` attribute. Know which pattern your production code uses.

### Pattern 3: Coverage.py Module Path Configuration

**What:** Use Python module paths (dot notation) not file paths in `--cov` parameter

**When to use:** Running pytest with coverage measurement

**Example:**
```python
# CORRECT - Module paths (Python import notation)
pytest --cov=core.agent_governance_service --cov=core.episode_segmentation_service

# WRONG - File paths
pytest --cov=backend/core/agent_governance_service.py

# WRONG - File paths without .py extension
pytest --cov=backend/core/agent_governance_service
```

**Why:** Coverage.py imports modules to measure execution. File paths don't work with Python's import system.

### Pattern 4: Patch Location for WebSocket Managers

**What:** Patch at import location, not definition location

**When to use:** Mocking ws_manager or other globally imported singletons

**Example:**
```python
# Source: Phase 101 test_canvas_tool_coverage.py lines 102-106

@pytest.fixture
def mock_ws_manager():
    """Mock WebSocket manager.

    Patch at import location (tools.canvas_tool.ws_manager) not definition location.
    """
    with patch('tools.canvas_tool.ws_manager') as mock_mgr:
        mock_mgr.broadcast = AsyncMock()
        yield mock_mgr
```

**Why:** `tools.canvas_tool.py` imports `ws_manager` at module level. Patching `core.websocket.ws_manager` (definition) doesn't affect the already-imported reference in `canvas_tool.py`.

### Anti-Patterns to Avoid

- **Mock without spec:** `Mock()` without `spec=AgentRegistry` allows arbitrary attribute access, hiding missing attributes
- **Incomplete fixtures:** Mock objects missing production-required attributes (e.g., `confidence_score`)
- **File paths in --cov:** Coverage.py needs module paths, not file paths
- **Wrong patch location:** Patching definition instead of import location for singleton objects
- **Return Mock objects for floats:** Functions returning numeric values should return actual numbers, not Mock objects

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Mock object creation | Manual Mock() setup with repetitive attribute assignment | Fixtures with `spec=` parameter | `spec=AgentRegistry` enforces interface at mock creation time, failing early if attributes don't match |
| Coverage configuration | Custom .coveragerc from scratch | Start with pytest-cov defaults + pytest.ini | pytest-cov works out of the box with standard configuration |
| Database test isolation | Manual transaction rollback | `pytest-autofixture` with session scoping | Prevents test pollution automatically |

**Key insight:** Phase 101 showed that manual mock setup is error-prone. Use `spec=` parameter to let Python enforce interface compliance.

## Common Pitfalls

### Pitfall 1: Mock Objects Missing Numeric Attributes

**What goes wrong:** Production code compares `agent.confidence_score >= 0.9`, but mock's `confidence_score` is a Mock object, not a float. Python raises `TypeError: '>=' not supported between instances of 'Mock' and 'float'`.

**Why it happens:** Mock() creates a generic object that accepts any attribute assignment (`mock.confidence_score = anything`), but the attribute value is still a Mock, not the assigned type.

**How to avoid:** Always set numeric attributes to actual numbers, not Mock objects:
```python
agent.confidence_score = 0.95  # Float, not Mock
agent.total_steps = 10  # Integer, not Mock
```

**Warning signs:** TypeError with "not supported between instances of 'Mock' and" in test output.

### Pitfall 2: Coverage.py "Module Never Imported" Warning

**What goes wrong:** Coverage.py warns `CoverageWarning: Module backend/core/X was never imported` and coverage reports show 0% despite tests running.

**Why it happens:** Using file paths instead of module paths in `--cov` parameter. Coverage.py tries to import `backend/core/agent_governance_service` as a module name (which has slashes), but Python import system uses dots.

**How to avoid:** Use Python module paths (dot notation):
```bash
# CORRECT
pytest --cov=core.agent_governance_service tests/unit/governance/

# WRONG
pytest --cov=backend/core/agent_governance_service tests/unit/governance/
```

**Configuration fix:** Update `.coveragerc` or pytest.ini:
```ini
[coverage:run]
source = core  # Package name, not directory path
omit =
    */tests/*
    */__pycache__/*
```

**Warning signs:** Coverage reports all zeros, "module never imported" warnings in pytest output.

### Pitfall 3: Patching Definition Instead of Import Location

**What goes wrong:** Mocking `core.websocket.ws_manager` (definition) but `tools.canvas_tool` already imported `ws_manager` at module load time. Mock has no effect.

**Why it happens:** Python imports execute once at module load. Patching definition location doesn't update already-imported references in other modules.

**How to avoid:** Patch at import location:
```python
# CORRECT - Patch where canvas_tool imports it
with patch('tools.canvas_tool.ws_manager') as mock_mgr:
    pass

# WRONG - Patch where ws_manager is defined
with patch('core.websocket.ws_manager') as mock_mgr:
    pass
```

**How to find import location:** Open `tools/canvas_tool.py`, search for `import ws_manager` or `from ... import ws_manager`. Use that path.

**Warning signs:** Mock doesn't affect behavior, test executes real code (e.g., real WebSocket connection attempts).

### Pitfall 4: Enum Comparison Mismatches

**What goes wrong:** Production code compares `agent.status == AgentStatus.AUTONOMOUS` but mock returns string `"autonomous"`. Comparison fails, tests don't execute expected branches.

**Why it happens:** Inconsistent mock return values. Some tests use enum values, some use strings.

**How to avoid:** Be consistent with enum comparison pattern:
```python
# Pattern 1: Compare enum values
agent.status = AgentStatus.AUTONOMOUS.value  # String: "autonomous"
assert agent.status == "autonomous"

# Pattern 2: Compare enum objects (requires full enum mock)
agent.status = Mock(spec=AgentStatus)
agent.status.value = "autonomous"
```

**Warning signs:** Governance checks fail unexpectedly, maturity routing not working in tests.

## Code Examples

Verified patterns from Phase 101 successful fixes:

### Mock Agent Registry with All Attributes

```python
# Source: backend/tests/unit/canvas/test_canvas_tool_coverage.py (lines 52-65)

from core.models import AgentRegistry, AgentStatus
from unittest.mock import Mock

@pytest.fixture
def mock_agent():
    """Mock agent registry."""
    agent = Mock(spec=AgentRegistry)  # Enforce interface
    agent.id = "test-agent-1"
    agent.name = "TestAgent"
    agent.status = AgentStatus.AUTONOMOUS.value  # Enum value as string
    agent.workspace_id = "default"
    agent.confidence_score = 0.95  # Float, not Mock
    agent.category = "Testing"
    agent.module_path = "test.test_agent"
    agent.class_name = "TestAgent"
    agent.user_id = "test-user-1"
    agent.required_role_for_autonomy = "team_lead"
    return agent
```

### Mock Database Session with Query Chain

```python
# Source: backend/tests/unit/canvas/test_agent_guidance_canvas_coverage.py (lines 36-50)

from sqlalchemy.orm import Session
from unittest.mock import Mock

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock(spec=Session)
    db.add = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    db.rollback = Mock()

    # Mock query chain
    mock_query = Mock()
    db.query = Mock(return_value=mock_query)
    mock_query.filter = Mock(return_value=mock_query)
    mock_query.first = Mock(return_value=None)

    return db
```

### Coverage Command with Module Paths

```python
# Source: Phase 101 blocker resolution documentation

# CORRECT - Module paths (dot notation)
pytest tests/unit/governance/ \
    --cov=core.agent_governance_service \
    --cov=core.agent_context_resolver \
    --cov=core.governance_cache \
    --cov-report=term-missing \
    --cov-report=html

# WRONG - File paths (causes "module never imported" warnings)
pytest tests/unit/governance/ \
    --cov=backend/core/agent_governance_service \
    --cov=backend/core/agent_context_resolver
```

### Enum-Like Mock Return Values

```python
# Source: backend/tests/unit/canvas/test_canvas_tool_coverage.py (lines 133-145)

@pytest.fixture(autoute=True)
def mock_canvas_type_registry():
    """Mock canvas type registry with maturity requirements."""
    with patch('tools.canvas_tool.canvas_type_registry') as mock_registry:
        # Mock get_min_maturity to return string values
        def mock_get_min_maturity(canvas_type):
            return {
                "generic": "student",
                "sheets": "student",
                "docs": "student",
                "email": "student",
                "orchestration": "student",
                "terminal": "student",
                "coding": "student"
            }.get(canvas_type, "student")

        mock_registry.get_min_maturity = Mock(side_effect=mock_get_min_maturity)
        yield mock_registry
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| unittest.TestCase classes | pytest function-based tests | 2018+ | pytest has superior fixtures, parametrization, plugins |
| Manual mock setup | Mock with spec= parameter | 2020+ | spec enforces interface compliance |
| Coverage.py CLI separate | pytest-cov integration | 2019+ | Automatic coverage collection during test runs |
| File paths in --cov | Module paths (dot notation) | Always | Coverage.py requires importable module names |

**Deprecated/outdated:**
- **unittest.TestCase**: Still works, but pytest fixtures are more composable
- **nosetests**: Deprecated, use pytest instead
- **mock (external package)**: Use `unittest.mock` from stdlib (Python 3.3+)

## Open Questions

1. **What is the current state of Phase 101 fixes?**
   - What we know: Phase 101 completion report claims 5/6 services at 60%+, blockers resolved
   - What's unclear: v5.1 requirements still mark FIX-01 and FIX-02 as pending
   - Recommendation: Re-verify Phase 101 fixes, check for regressions, confirm current test pass rates

2. **Are all 66 canvas tests passing now?**
   - What we know: Phase 101 fixed mock configuration, test pass rate improved to 100% for canvas_tool
   - What's unclear: Whether fixes persisted, whether tests still pass in current codebase
   - Recommendation: Run `pytest tests/unit/canvas/ -v` to verify current state

3. **Is coverage measurement working accurately?**
   - What we know: Phase 101 documented correct module path usage (`core.agent_governance_service`)
   - What's unclear: Whether coverage commands use correct paths, whether baseline is accurate
   - Recommendation: Run coverage with correct module paths, compare to baseline

## Sources

### Primary (HIGH confidence)
- **Phase 101 Completion Report** - `.planning/phases/101-backend-core-services-unit-tests/101-COMPLETION-REPORT.md` (2026-02-27)
- **Phase 101 Blocker Resolution** - `.planning/phases/101-backend-core-services-unit-tests/101-BLOCKER-RESOLUTION.md` (2026-02-27)
- **Phase 101 Verification Report** - `backend/tests/coverage_reports/PHASE_101_VERIFICATION.md` (2026-02-27)
- **pytest.ini** - Backend test configuration with coverage settings
- **test_canvas_tool_coverage.py** - Working mock fixtures (lines 52-65, 133-145)
- **test_agent_guidance_canvas_coverage.py** - Working mock fixtures (lines 36-82)

### Secondary (MEDIUM confidence)
- **Python unittest.mock documentation** - https://docs.python.org/3/library/unittest.mock.html (Mock spec parameter, patch locations)
- **pytest-cov documentation** - https://pytest-cov.readthedocs.io/ (coverage configuration, module paths)
- **coverage.py documentation** - https://coverage.readthedocs.io/ (source configuration, omit patterns)

### Tertiary (LOW confidence)
- None (WebSearch at limit, relying on official docs and existing codebase)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pytest, pytest-cov, unittest.mock are industry standards, verified in pytest.ini
- Architecture: HIGH - Patterns extracted from working Phase 101 code with proven results (5/6 services at 60%+)
- Pitfalls: HIGH - All pitfalls documented in Phase 101 verification report with specific error messages and solutions

**Research date:** 2026-03-01
**Valid until:** 2026-06-01 (3 months - pytest, coverage.py, and unittest.mock are stable libraries with slow API evolution)

**Key insight for planning:** Phase 101 already solved these problems. Phase 111 is primarily a **re-verification and stabilization** effort, not new implementation. The fixes are documented and proven. Focus on:
1. Re-running tests to confirm fixes still work
2. Checking for any regressions since Phase 101
3. Updating documentation if needed
4. Ensuring v5.1 requirements (FIX-01, FIX-02) are properly marked complete
