# Phase 218: Fix Test Collection Errors - Research

**Researched:** 2026-03-21
**Domain:** Python test collection, import errors, optional dependencies
**Confidence:** HIGH

## Summary

Phase 218 addresses two critical test collection errors blocking the entire test suite. The research reveals that both issues stem from mismatches between test expectations and actual implementation:

1. **TimeExpressionParser**: Tests expect a class-based API (`TimeExpressionParser`, `TimeUnit` enum) but the module only exports functions (`parse_time_expression`, `parse_with_patterns`)
2. **TraceValidator**: Tests import `core.trajectory` which has a hard dependency on `aiofiles` (not in requirements.txt), blocking collection

**Primary recommendation**: Fix imports to match actual exports for #1, make `aiofiles` optional with try/except pattern for #2 (standard practice in this codebase).

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 7.4+ | Test collection/execution | Industry standard Python testing |
| Python 3 | 3.11+ | Runtime | Project requirement |

### Optional Dependencies Pattern
| Pattern | Purpose | When to Use |
|---------|---------|-------------|
| `try: import X except ImportError: FLAG=False` | Graceful degradation | Feature enhancement, not core functionality |
| `pytest.importorskip()` | Skip tests if module missing | Test-level dependency handling |

**Installation:**
```bash
# No new dependencies needed - use existing patterns
# aiofiles can be made optional using existing codebase patterns
```

## Architecture Patterns

### Pattern 1: Optional Dependency Import (Codebase Standard)
**What:** Try/except import with availability flag
**When to use:** Non-critical dependencies that enhance functionality
**Example:**
```python
# Source: core/media/sonos_service.py (existing codebase pattern)
try:
    import soco
    SOCOS_AVAILABLE = True
    logger.info("SoCo library available - Sonos control enabled")
except ImportError:
    SOCOS_AVAILABLE = False
    logger.warning("SoCo library not installed - Sonos functions will fail")
```

**Why this pattern:**
- Provides clear feedback about availability
- Allows graceful degradation
- Matches existing codebase conventions (see: `tools/device_tool.py`, `core/media/__init__.py`)

### Pattern 2: Test-Time Import Skipping (pytest Standard)
**What:** Use `pytest.importorskip()` to skip tests requiring missing modules
**When to use:** Test files that depend on optional production modules
**Example:**
```python
# Source: pytest documentation
def test_something():
    aiofiles = pytest.importorskip("aiofiles")
    # test code using aiofiles
```

### Pattern 3: Import-at-Use (Lazy Import)
**What:** Import inside function/method that uses the module
**When to use:** Module only needed in specific code paths
**Example:**
```python
# Source: tests/unit/dto/test_pydantic_validators.py (existing workaround)
class TestTraceValidator:
    def test_trace_metrics_structure(self):
        from core.trajectory import ExecutionTrace, TraceStep, TraceStepType
        # Use ExecutionTrace here
```

**Why:** Delays import error until test execution, not collection (but still fails)

### Anti-Patterns to Avoid
- **Hard dependency on optional packages**: Don't make core modules unimportable due to missing optional features
- **Silent failures**: Always log when optional dependency is missing (use logger.warning)
- **Inconsistent patterns**: Follow established codebase conventions (10+ examples found)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Optional import handling | Custom try/except without flags | Codebase pattern (FLAG_AVAILABLE) | Provides visibility, matches 10+ existing files |
| Test skipping for missing deps | Custom skip logic | `pytest.importorskip()` | Built-in, standard pytest feature |
| Async file I/O | Custom async wrapper | `aiofiles` (optional) or make `save()` sync | Correctly handles async file operations |

**Key insight:** The codebase already has established patterns for optional dependencies. Use them instead of inventing new approaches.

## Common Pitfalls

### Pitfall 1: Import Errors Block Test Collection
**What goes wrong:** `ModuleNotFoundError` or `ImportError` during test collection prevents entire suite from running
**Why it happens:** pytest imports test modules at collection time (before execution)
**How to avoid:** Use optional import pattern or `pytest.importorskip()`
**Warning signs:** `pytest --collect-only` shows ERROR before any tests run

### Pitfall 2: Test Expectations Don't Match Implementation
**What goes wrong:** Tests import classes/functions that don't exist in the module
**Why it happens:** Tests written for planned API but implementation differs
**How to avoid:** Always verify module exports with `python3 -c "print(dir(module))"` before writing tests
**Warning signs:** `ImportError: cannot import name 'X' from 'module'`

### Pitfall 3: Hard Dependencies on Optional Packages
**What goes wrong:** Core module imports optional package at top level, making module unusable without it
**Why it happens:** Developer adds optional import without making it optional
**How to avoid:** Use try/except pattern with availability flag
**Warning signs:** Module unusable when feature enhancement package missing

## Code Examples

Verified patterns from the codebase:

### Optional Import with Availability Flag
```python
# Source: core/media/sonos_service.py
try:
    import soco
    SOCOS_AVAILABLE = True
    logger.info("SoCo library available - Sonos control enabled")
except ImportError:
    SOCOS_AVAILABLE = False
    logger.warning("SoCo library not installed - Sonos functions will fail")

class SonosService:
    def __init__(self):
        if not SOCOS_AVAILABLE:
            raise ImportError("SoCo library is required for SonosService")
```

### Applying to trajectory.py
```python
# Current (blocking):
import aiofiles  # Line 7 - hard dependency

# Fixed (optional):
try:
    import aiofiles
    AIOFILES_AVAILABLE = True
except ImportError:
    AIOFILES_AVAILABLE = False
    logger.warning("aiofiles not available - async file saving will fail")

# In save() method:
async def save(self, directory: str = "logs/traces"):
    if not AIOFILES_AVAILABLE:
        raise ImportError("aiofiles is required for async file saving. Install with: pip install aiofiles")
    # Rest of method...
```

### Test Skip for Missing Module
```python
# Source: pytest documentation
import pytest

def test_trace_validator():
    aiofiles = pytest.importorskip("aiofiles")
    # Test code requiring aiofiles
```

### Alternative: Make save() Method Sync
```python
# Replace aiofiles with built-in async support (Python 3.11+)
def save(self, directory: str = "logs/traces"):  # Remove async
    """Save trace to a JSON file (synchronous version)"""
    import asyncio
    # Use asyncio.to_thread() or just regular I/O
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hard dependencies only | Optional dependencies with flags | Python 3.6+ | Libraries can work with reduced feature sets |
| Test fails if dep missing | `pytest.importorskip()` skips gracefully | pytest 3.0+ | Test suite runs even with optional deps missing |
| Manual async file I/O | `aiofiles` library | 2019+ | Cleaner async file operations |

**Deprecated/outdated:**
- Synchronous file operations in async contexts: Use `aiofiles` or `asyncio.to_thread()` (Python 3.9+)
- ImportError without logging: Always log missing optional dependencies for debugging

## Open Questions

### Q1: Should aiofiles be added to requirements.txt or made optional?
**What we know:**
- `aiofiles` used in 1 place: `TrajectoryRecorder.save()` method
- Not in requirements.txt currently
- Only used for async file writing (enhancement, not core functionality)
- Codebase has 10+ examples of optional dependencies with flags

**What's unclear:**
- Is `TrajectoryRecorder.save()` used in production code or just development?
- Are other parts of the codebase calling `.save()` and expecting it to work?

**Recommendation:** Make `aiofiles` optional with try/except pattern (matches codebase conventions). If `.save()` is critical, add clear error message directing users to install it.

### Q2: Should TimeExpressionParser be implemented as a class or are functions sufficient?
**What we know:**
- Tests expect: `TimeExpressionParser` class, `TimeUnit` enum, `parse_time_expression()` function
- Current exports: `parse_time_expression()` function, `parse_with_patterns()` function
- Current implementation is functional (not class-based)

**What's unclear:**
- Is the class-based API planned for future implementation?
- Are the tests forward-looking (for planned features) or outdated (from old design)?

**Recommendation:** Check if TimeExpressionParser class is in requirements/docs. If not, tests are wrong - fix imports to match current implementation. If yes, implement the class.

### Q3: What's the acceptance criteria for "tests collect successfully"?
**What we know:**
- `pytest --collect-only` should return 0 errors
- Tests can still fail during execution, but must be collectable

**What's unclear:**
- Should tests actually run and pass? Or just collect?

**Recommendation:** "Collect successfully" = 0 errors during collection phase. Tests can be skipped or fail during execution.

## Sources

### Primary (HIGH confidence)
- **Codebase inspection** - `core/trajectory.py`, `core/time_expression_parser.py` (actual implementation)
- **Test files** - `tests/core/test_*.py` (test expectations)
- **Codebase patterns** - `core/media/sonos_service.py`, `tools/device_tool.py` (10+ examples of optional imports)
- **pytest documentation** - `pytest.importorskip()` usage (verified in test output)

### Secondary (MEDIUM confidence)
- **Python ImportError handling** - Standard practice with try/except
- **pytest collection behavior** - Imports happen at collection time (verified from test output)

### Tertiary (LOW confidence)
- **WebSearch results** - Rate limited, not accessible (relied on codebase inspection instead)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - verified from codebase and pytest documentation
- Architecture: HIGH - based on 10+ existing examples in codebase
- Pitfalls: HIGH - confirmed by actual test collection errors

**Research date:** 2026-03-21
**Valid until:** 2026-04-21 (30 days - stable domain)

---

## Implementation Guidance

Based on research findings, the phase should:

### Task 1: Fix test_time_expression_parser.py
**Root cause:** Tests expect `TimeExpressionParser` class and `TimeUnit` enum that don't exist
**Solution options:**
1. **Option A (recommended):** Update test imports to match actual exports
   - Change: `from core.time_expression_parser import TimeExpressionParser, parse_time_expression, TimeUnit`
   - To: `from core.time_expression_parser import parse_time_expression, parse_with_patterns`
   - Rewrite tests to use function-based API instead of class-based API

2. **Option B:** Implement missing classes in `core/time_expression_parser.py`
   - Add `TimeExpressionParser` class wrapping existing functions
   - Add `TimeUnit` enum
   - Only if this is planned functionality (check requirements/docs)

**Decision point:** Check if TimeExpressionParser class is in requirements before choosing

### Task 2: Fix test_trace_validator.py
**Root cause:** `core/trajectory.py` has hard dependency on `aiofiles` (not installed)
**Solution options:**
1. **Option A (recommended):** Make `aiofiles` optional in `core/trajectory.py`
   - Add try/except import pattern with `AIOFILES_AVAILABLE` flag
   - Check availability in `save()` method, raise clear error if missing
   - Add to requirements.txt as optional dependency or document in docs

2. **Option B:** Use `pytest.importorskip()` in test file
   - Add `aiofiles = pytest.importorskip("aiofiles")` at top of test file
   - Skips tests gracefully if aiofiles not installed
   - Doesn't fix production code issue

3. **Option C:** Replace `aiofiles` with standard library
   - Use `asyncio.to_thread()` with regular `open()` (Python 3.9+)
   - Or make `save()` synchronous (remove async)
   - Removes dependency entirely

**Decision point:** Check if `TrajectoryRecorder.save()` is used in production or just development

### Verification Commands
```bash
# After fixes, verify collection succeeds
pytest tests/core/test_time_expression_parser.py --collect-only
pytest tests/core/test_trace_validator.py --collect-only
pytest tests/ --collect-only 2>&1 | grep -E "collected|error|ERROR"

# Expected: All tests collect, 0 errors
```
