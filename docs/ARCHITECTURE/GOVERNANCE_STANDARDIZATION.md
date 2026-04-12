# Governance Checks Standardization

**Date**: February 5, 2026
**Status**: ✅ Documented (infrastructure already exists)

---

## Executive Summary

Atom has comprehensive governance infrastructure via `ServiceFactory` and `AgentGovernanceService`. This document standardizes governance check patterns and provides helper functions.

**Key Finding**: Governance infrastructure is solid. The issue is **mixed instantiation patterns** (ServiceFactory vs direct instantiation).

---

## Standard Patterns

### Pattern 1: Get Governance Service (Recommended)

**Use for**: All governance checks in tools and services

```python
from core.service_factory import ServiceFactory
from core.database import get_db_session

def perform_action(agent_id: str, action: str):
    with get_db_session() as db:
        # Get governance service via factory
        governance = ServiceFactory.get_governance_service(db)

        # Check permissions
        if not governance.can_execute_action(agent_id, action_complexity=3):
            raise PermissionDeniedError("Agent not permitted for this action")

        # Perform action
        ...
```

### Pattern 2: Governance Helper Function (New)

**Use for**: Common permission checks with consistent error handling

```python
from core.governance_helpers import check_agent_permission

def perform_action(agent_id: str, action: str):
    with get_db_session() as db:
        # Single-line permission check with automatic error handling
        check_agent_permission(db, agent_id, "update_agent", complexity=3)

        # Perform action
        ...
```

### Pattern 3: Tool-Level Governance (Recommended)

**Use for**: Tools that need persistent governance service**

```python
from core.service_factory import ServiceFactory

class CanvasTool:
    def __init__(self, db: Session):
        # Get governance service via factory
        self.governance = ServiceFactory.get_governance_service(db)
        self.db = db

    def present_chart(self, agent_id: str, chart_data: dict):
        # Use cached governance service
        if not self.governance.can_execute_action(agent_id, action_complexity=2):
            raise PermissionDeniedError("Agent cannot present charts")

        # Present chart
        ...
```

---

## Anti-Patterns to Avoid

### ❌ Direct Instantiation in Methods
```python
def perform_action(agent_id: str, action: str):
    with get_db_session() as db:
        governance = AgentGovernanceService(db)  # ❌ Not recommended

        if not governance.can_execute_action(...):
            ...
```

**Why**: ServiceFactory provides caching, logging, and consistency.

**Instead**:
```python
def perform_action(agent_id: str, action: str):
    with get_db_session() as db:
        governance = ServiceFactory.get_governance_service(db)  # ✅ Recommended

        if not governance.can_execute_action(...):
            ...
```

### ❌ Inconsistent Error Handling
```python
if not governance.can_execute_action(agent_id, 3):
    return {"error": "Not allowed"}  # ❌ Inconsistent error format

if not governance.can_execute_action(agent_id, 3):
    raise Exception("Not allowed")  # ❌ Wrong exception type

if not governance.can_execute_action(agent_id, 3):
    pass  # ❌ Silent failure - security risk!
```

**Instead**:
```python
check_agent_permission(db, agent_id, "action", complexity=3)  # ✅ Consistent
```

---

## Current State Analysis

### Files Using ServiceFactory ✅ (Recommended)
- `tools/canvas_tool.py` - Uses `ServiceFactory.get_governance_service(db)`
- Most new code follows this pattern

### Files Using Direct Instantiation ⚠️ (Review Needed)
1. `tools/agent_guidance_canvas_tool.py` - Constructor instantiation
2. `core/agent_context_resolver.py` - Constructor instantiation
3. `core/agent_execution_service.py` - Method-level instantiation
4. `core/agent_integration_gateway.py` - Method-level instantiation
5. `core/agent_request_manager.py` - Constructor instantiation
6. `core/api_governance.py` - Method-level instantiation
7. `core/atom_agent_endpoints.py` - Multiple instantiations

### Impact Assessment
- **Functional Impact**: None (both patterns work)
- **Consistency Impact**: Medium (mixed patterns)
- **Performance Impact**: Minimal (ServiceFactory has caching)
- **Security Impact**: None (both check permissions correctly)

---

## Helper Function

### Implementation

Add to `core/governance_helpers.py`:

```python
from core.service_factory import ServiceFactory
from core.base_routes import BaseAPIRouter

def check_agent_permission(
    db: Session,
    agent_id: str,
    action: str,
    complexity: int,
    raise_on_denied: bool = True
) -> bool:
    """
    Standardized permission check with consistent error handling.

    Args:
        db: Database session
        agent_id: Agent ID to check
        action: Action name (for error messages)
        complexity: Action complexity level (1-4)
        raise_on_denied: If True, raise exception on denial; if False, return bool

    Returns:
        True if permitted, False if denied (only when raise_on_denied=False)

    Raises:
        PermissionDeniedError: If agent not permitted and raise_on_denied=True

    Example:
        # Automatic error handling
        check_agent_permission(db, "agent123", "update_agent", complexity=3)

        # Manual handling
        if not check_agent_permission(db, "agent123", "update_agent", 3, raise_on_denied=False):
            return {"error": "Not allowed"}
    """
    governance = ServiceFactory.get_governance_service(db)

    if not governance.can_execute_action(agent_id, complexity):
        if raise_on_denied:
            router = BaseAPIRouter()
            required_maturity = governance.get_required_maturity(complexity)

            raise router.permission_denied_error(
                action=action,
                resource=f"agent:{agent_id}",
                details={
                    "current_maturity": governance.get_agent_maturity(agent_id),
                    "required_maturity": required_maturity,
                    "complexity": complexity
                }
            )
        return False

    return True
```

---

## Migration Guide

### For Tool Classes

#### Before (Direct Instantiation)
```python
class SomeTool:
    def __init__(self, db: Session):
        from core.agent_governance_service import AgentGovernanceService

        self.governance = AgentGovernanceService(db)
        self.db = db
```

#### After (ServiceFactory)
```python
class SomeTool:
    def __init__(self, db: Session):
        from core.service_factory import ServiceFactory

        self.governance = ServiceFactory.get_governance_service(db)
        self.db = db
```

### For Function-Level Checks

#### Before (Verbose)
```python
def perform_action(agent_id: str, action: str, db: Session):
    from core.service_factory import ServiceFactory

    governance = ServiceFactory.get_governance_service(db)

    if not governance.can_execute_action(agent_id, action_complexity=3):
        raise router.permission_denied_error(action, f"agent:{agent_id}")

    # Perform action
    ...
```

#### After (Helper Function)
```python
def perform_action(agent_id: str, action: str, db: Session):
    from core.governance_helpers import check_agent_permission

    check_agent_permission(db, agent_id, action, complexity=3)

    # Perform action
    ...
```

---

## Files Requiring Updates

### Priority 1: High-Usage Files
1. `core/atom_agent_endpoints.py` - Multiple instantiations
2. `core/agent_execution_service.py` - Core service
3. `tools/agent_guidance_canvas_tool.py` - Tool class

### Priority 2: Medium-Usage Files
4. `core/api_governance.py` - API governance
5. `core/agent_integration_gateway.py` - Gateway service
6. `core/agent_request_manager.py` - Request manager

### Priority 3: Lower-Usage Files
7. `core/agent_context_resolver.py` - Context resolver
8. Other files with direct instantiation

---

## Benefits of Standardization

### 1. Consistent Error Messages
All permission denied errors follow the same format:
```json
{
  "error": {
    "code": "PERMISSION_DENIED",
    "message": "Agent does not have permission for update_agent",
    "action": "update_agent",
    "resource": "agent:agent123",
    "details": {
      "current_maturity": "INTERN",
      "required_maturity": "SUPERVISED",
      "complexity": 3
    }
  }
}
```

### 2. Better Caching
ServiceFactory provides caching for governance service instances:
```python
# Subsequent calls return cached instance
governance1 = ServiceFactory.get_governance_service(db)
governance2 = ServiceFactory.get_governance_service(db)
# governance1 is governance2 (cached)
```

### 3. Easier Testing
Mock ServiceFactory instead of individual services:
```python
# Mock once
with patch('core.service_factory.ServiceFactory.get_governance_service') as mock_gov:
    mock_gov.return_value = mock_governance_service

    # All governance checks use the mock
    check_agent_permission(db, agent_id, action, 3)
```

### 4. Centralized Configuration
Change governance behavior in one place (ServiceFactory):
```python
# ServiceFactory can apply global config
governance = ServiceFactory.get_governance_service(db)
# Applies caching, logging, feature flags automatically
```

---

## Testing

### Unit Tests
```python
def test_check_agent_permission_granted():
    """Test permission check when agent is permitted"""
    with patch('core.service_factory.ServiceFactory.get_governance_service') as mock:
        mock_gov = MagicMock()
        mock_gov.can_execute_action.return_value = True
        mock.return_value = mock_gov

        # Should not raise
        result = check_agent_permission(db, "agent123", "action", 3)
        assert result is True

def test_check_agent_permission_denied():
    """Test permission check when agent is not permitted"""
    with patch('core.service_factory.ServiceFactory.get_governance_service') as mock:
        mock_gov = MagicMock()
        mock_gov.can_execute_action.return_value = False
        mock_gov.get_required_maturity.return_value = "SUPERVISED"
        mock.return_value = mock_gov

        # Should raise
        with pytest.raises(HTTPException) as exc:
            check_agent_permission(db, "agent123", "action", 3)

        assert exc.value.status_code == 403
```

---

## Monitoring

### Key Metrics
1. **Governance check rate**: Checks per second
2. **Permission denied rate**: % of checks denied
3. **Cache hit rate**: % of cache hits in ServiceFactory
4. **Maturity distribution**: Agent maturity levels

### Logging
```python
# Log all permission checks
logger.info(f"Governance check: agent={agent_id}, action={action}, permitted={result}")

# Log denials with details
logger.warning(
    f"Permission denied: agent={agent_id}, "
    f"current={current_maturity}, required={required_maturity}"
)
```

---

## Configuration

### Environment Variables
```bash
# Governance enforcement
GOVERNANCE_ENABLED=true

# Emergency bypass
EMERGENCY_GOVERNANCE_BYPASS=false

# Cache settings
GOVERNANCE_CACHE_ENABLED=true
GOVERNANCE_CACHE_TTL=300
```

---

## Security Considerations

### 1. Always Check Permissions
```python
# ❌ Don't skip checks!
if agent_id == "admin":  # Security risk!
    perform_admin_action()

# ✅ Always use governance
check_agent_permission(db, agent_id, "admin_action", complexity=4)
```

### 2. Check Complexity Correctly
```python
# Complexity levels:
# 1 = LOW (read-only, presentations)
# 2 = MODERATE (streaming, moderate actions)
# 3 = HIGH (state changes, submissions)
# 4 = CRITICAL (deletions, payments)

# ✅ Use appropriate complexity
check_agent_permission(db, agent_id, "delete_resource", complexity=4)  # Critical
check_agent_permission(db, agent_id, "view_chart", complexity=1)  # Low
```

### 3. Never Bypass Checks
```python
# ❌ Never do this
if bypass_governance:  # Security hole!
    perform_action_without_check()

# ✅ Use emergency bypass properly
if os.getenv("EMERGENCY_GOVERNANCE_BYPASS") == "true":
    logger.critical("EMERGENCY BYPASS ACTIVE - action bypassed")
else:
    check_agent_permission(db, agent_id, action, complexity)
```

---

## Summary

### Current State
- ✅ ServiceFactory provides governance service access
- ✅ AgentGovernanceService handles permission checks
- ⚠️ Mixed instantiation patterns (ServiceFactory vs direct)
- ✅ Permission checks are consistent and secure

### Recommendations
1. **Document standard patterns** (this document) ✅
2. **Add helper function** to `core/governance_helpers.py`
3. **Update high-priority files** to use ServiceFactory
4. **Add linter rule** to prevent direct instantiation
5. **Monitor governance metrics** in production

### Priority Matrix

| Task | Impact | Effort | Priority |
|------|--------|--------|----------|
| Document patterns | High | Low | ✅ Done |
| Add helper function | Medium | Low | High |
| Update high-priority files | Medium | Medium | High |
| Update low-priority files | Low | High | Low |
| Add linter rule | Medium | Low | Medium |

---

## References

- **ServiceFactory**: `core/service_factory.py`
- **AgentGovernanceService**: `core/agent_governance_service.py`
- **AgentContextResolver**: `core/agent_context_resolver.py`
- **Tools Using Governance**: `tools/canvas_tool.py`, `tools/browser_tool.py`

**Author**: Claude Sonnet 4.5
**Status**: Documented (infrastructure production-ready)
**Next Step**: Add helper function and update high-priority files
