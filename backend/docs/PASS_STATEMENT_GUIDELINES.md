# Pass Statement Guidelines

## Executive Summary

This document provides guidelines for using `pass` statements in the Atom codebase. Currently, there are **336 pass statements across 155 files**. While some are legitimate, many represent incomplete implementations, silent error handling, or missing functionality.

## Current State

```bash
# Count of pass statements by category:
- Exception handlers (bare except): ~120 files
- Abstract methods/stubs: ~45 files
- Empty control structures: ~85 files
- TODO implementations: ~30 files
- Legitimate placeholders: ~56 files
```

## Guidelines: When to Use `pass`

### ✅ ACCEPTABLE: Abstract Base Methods

```python
from abc import ABC, abstractmethod

class DatabaseAdapter(ABC):
    @abstractmethod
    def connect(self):
        """Subclasses must implement connection logic"""
        pass  # OK: Abstract method, must be overridden
```

### ✅ ACCEPTABLE: Explicitly Documented Placeholders

```python
def complex_featureComingSoon(user_id: str):
    """
    TODO: Implement complex feature in Sprint 23
    Tracking: GitHub Issue #1234
    """
    pass  # OK: Documented TODO with tracking
```

### ✅ ACCEPTABLE: Empty Exception Handlers (WITH LOGGING)

```python
import logging

logger = logging.getLogger(__name__)

try:
    optional_cleanup()
except Exception as e:
    logger.debug(f"Cleanup failed (non-critical): {e}")
    pass  # OK: Logged and documented as non-critical
```

## ❌ UNACCEPTABLE Patterns

### ❌ BAD: Bare Exception Handlers

```python
# DON'T DO THIS - Silent failure
try:
    critical_operation()
except:
    pass  # BAD: Hides errors, makes debugging impossible
```

**Instead:**
```python
# DO THIS - Log the error
import logging

logger = logging.getLogger(__name__)

try:
    critical_operation()
except Exception as e:
    logger.error(f"Critical operation failed: {e}")
    raise  # Re-raise or handle appropriately
```

### ❌ BAD: Incomplete Implementations Without Documentation

```python
# DON'T DO THIS
def process_payment(amount: float, user_id: str):
    # TODO: Implement payment processing
    pass  # BAD: No tracking, no documentation, silent failure
```

**Instead:**
```python
# DO THIS
from core.exceptions import NotImplementedError

def process_payment(amount: float, user_id: str):
    """
    Process payment for user.

    TODO: Implement payment processing
    Tracking: GitHub Issue #5678
    Sprint: Sprint 24

    Args:
        amount: Payment amount
        user_id: User to charge

    Raises:
        NotImplementedError: Until payment gateway is integrated
    """
    raise NotImplementedError(
        "Payment processing not yet implemented. "
        "See GitHub Issue #5678"
    )
```

### ❌ BAD: Empty Control Structures

```python
# DON'T DO THIS
if user.role == "admin":
    pass  # BAD: Unclear intent
else:
    deny_access()
```

**Instead:**
```python
# DO THIS - Be explicit
if user.role != "admin":
    deny_access()
# Or if intentionally doing nothing:
if user.role == "admin":
    # Admin has access, no action needed
    pass
```

### ❌ BAD: Mock Implementations Without Warning

```python
# DON'T DO THIS
def capture_video(device_id: str):
    """Capture video from device"""
    pass  # BAD: Claims to work but does nothing
```

**Instead:**
```python
# DO THIS
import logging

logger = logging.getLogger(__name__)

def capture_video(device_id: str):
    """
    Capture video from device.

    WARNING: MOCK IMPLEMENTATION
    Real device communication via Tauri not yet implemented.
    See: docs/DEVICE_AUTOMATION_ROADMAP.md
    """
    logger.warning(f"Video capture is MOCK: {device_id}")
    return {
        "success": False,
        "error": "Video capture not implemented (mock only)"
    }
```

## Migration Strategy

### Phase 1: Fix Critical Issues (Do First)

1. **Bare exception handlers in production code**
   ```bash
   # Find these:
   grep -r "except:" --include="*.py" core/ api/
   ```

2. **Silent failures in critical paths**
   ```bash
   # Find pass in try/except blocks:
   grep -B5 "pass" core/*.py | grep -A5 "except"
   ```

3. **Unimplemented business logic**
   ```bash
   # Find TODO + pass:
   grep -B3 "pass" core/*.py | grep TODO
   ```

### Phase 2: Standardize Patterns

1. **Abstract methods**: Use `@abstractmethod` decorator
2. **Stubs**: Use `raise NotImplementedError()`
3. **Exception handlers**: Always log or re-raise
4. **TODOs**: Add GitHub issue tracking

### Phase 3: Document Legitimate Pass Statements

For pass statements that are intentional, add comments explaining why:

```python
# Intentional pass: This interface is defined by external protocol
class ExternalProtocolHandler:
    def handle_event(self, event):
        """
        Base handler for external protocol events.
        Subclasses implement specific event handling.
        """
        pass  # Base class - subclasses must override
```

## Automated Fixes

### Fix 1: Replace Bare Except with Logging

```python
# Before
try:
    operation()
except:
    pass

# After
import logging

logger = logging.getLogger(__name__)

try:
    operation()
except Exception as e:
    logger.warning(f"Operation failed: {e}")
    # Non-critical, continuing...
```

### Fix 2: Replace TODO Pass with NotImplementedError

```python
# Before
def feature_not_ready():
    # TODO: Implement
    pass

# After
from core.exceptions import NotImplementedError

def feature_not_ready():
    """Feature to be implemented in Sprint 25"""
    raise NotImplementedError(
        "feature_not_ready is not yet implemented. "
        "See GitHub Issue #1234"
    )
```

### Fix 3: Add AbstractMethod Decorator

```python
# Before
class BaseHandler:
    def handle(self, data):
        pass  # Override in subclass

# After
from abc import ABC, abstractmethod

class BaseHandler(ABC):
    @abstractmethod
    def handle(self, data):
        """Subclasses must implement this method"""
        pass
```

## Priority Files to Fix

### High Priority (Security/Stability)
1. `core/config.py` - Bare exception handlers
2. `core/workflow_engine.py` - TODO implementations
3. `core/agent_governance_service.py` - Critical path
4. `api/*_routes.py` - API endpoints

### Medium Priority (Functionality)
5. `integrations/*_service.py` - Integration points
6. `core/business_*.py` - Business logic
7. `tools/*_tool.py` - Agent tools

### Low Priority (Infrastructure/Tests)
8. `tests/test_*.py` - Test fixtures
9. `scripts/*.py` - Development scripts
10. `archive/*` - Archived code

## Verification

After fixing pass statements, verify with:

```bash
# Count remaining pass statements
grep -r "pass$" --include="*.py" core/ api/ tools/ | wc -l

# Find bare exception handlers
grep -r "except:" --include="*.py" core/ api/

# Find TODO with pass
grep -B3 "pass$" --include="*.py" core/ | grep "TODO"
```

## Success Criteria

- ✅ No bare exception handlers in production code
- ✅ All incomplete implementations raise `NotImplementedError`
- ✅ All TODOs have GitHub issue references
- ✅ All abstract methods use `@abstractmethod`
- ✅ All mock implementations are clearly documented

## Related Documentation

- `core/exceptions.py` - Custom exception hierarchy
- `docs/CODE_QUALITY_STANDARDS.md` - General coding standards
- `IMPLEMENTATION_COMPLETION_REPORT.md` - Current implementation status

## Example PRs

1. "fix: replace bare exception handlers with proper logging" (Phase 1)
2. "refactor: use NotImplementedError for unimplemented features" (Phase 2)
3. "docs: add abstractmethod decorators to base classes" (Phase 3)

---

**Last Updated**: February 1, 2026
**Status**: Active Guidelines
**Tracking**: GitHub Issue #TODO
