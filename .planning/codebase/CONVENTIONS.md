# Coding Conventions

**Analysis Date:** 2026-02-10

## Naming Patterns

**Files:**
- Modules: `snake_case.py` (e.g., `agent_governance_service.py`)
- Tests: `test_*.py` for unit tests, `test_*_invariants.py` for property tests
- Config: `*.ini`, `*.toml`, `*.json` as appropriate
- Documentation: `README.md`, `GUIDE.md`, `IMPLEMENTATION_*.md`

**Classes:**
- `PascalCase` for all classes (e.g., `AgentGovernanceService`, `CanvasAudit`)
- Exception classes: `AtomError` prefix (e.g., `AtomValidationError`)
- Service classes: `*Service` suffix (e.g., `RBACService`)
- Model classes: No specific suffix, inherit from `Base`

**Functions:**
- `snake_case` for all functions (e.g., `submit_feedback`, `can_perform_action`)
- Private functions: `_prefix` (e.g., `_get_fernet_for_token`)
- Async functions: `async def` prefix
- Method names: `snake_case` (e.g., `register_or_update_agent`)

**Variables:**
- `snake_case` for all variables (e.g., `user_id`, `confidence_score`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `DATABASE_URL`)
- Class attributes: `snake_case` with `self.` prefix
- Loop variables: `snake_case` (e.g., `agent_id`, `session_id`)

**Types:**
- Type hints required for all function signatures
- `Optional[X]` for nullable values
- `List[X]`, `Dict[X, Y]` for generic types
- `Union[X, Y]` for multiple types

## Code Style

**Formatting:**
- Tool: Black (auto-formatter)
- Line length: 88 characters (Black default)
- Indentation: 4 spaces
- Trailing commas: In multi-line constructs
- Quote style: Double quotes (`"`)

**Linting:**
- Tool: Ruff (linter + formatter)
- Rules: Enforce PEP 8, import sorting
- Disabled: Unused imports (selective enabling)
- Import order:
  ```python
  # 1. Standard library
  import os
  from datetime import datetime

  # 2. Third-party
  from fastapi import FastAPI
  from sqlalchemy.orm import Session

  # 3. Local imports
  from core.agent_governance_service import AgentGovernanceService
  from core.models import AgentRegistry
  ```

## Import Organization

**Order:**
1. Standard library imports
2. Third-party imports
3. Local imports (relative imports preferred)

**Path Aliases:**
- Relative imports: `from .models import AgentRegistry`
- Absolute imports: `from core.models import AgentRegistry`
- No wildcard imports: `import *` forbidden
- Type imports: `from typing import Optional, List`

## Error Handling

**Patterns:**
```python
# Standardized error handling
try:
    # Database operations
    with SessionLocal() as db:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        db.add(agent)
        db.commit()
except Exception as e:
    logger.error(f"Operation failed: {e}")
    raise api_error(
        ErrorCode.DATABASE_ERROR,
        "Database operation failed",
        {"error": str(e)}
    )

# FastAPI exception handling
@router.get("/agents/{agent_id}")
def get_agent(
    agent_id: str,
    db: Session = Depends(get_db)
):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(
            status_code=404,
            detail=f"Agent with ID '{agent_id}' not found"
        )
    return agent
```

**Error Codes:**
- Centralized error codes in `core/error_handlers.py`
- Categorized error codes (AUTH, VALIDATION, RESOURCE, BUSINESS, EXTERNAL, SYSTEM)
- Structured error responses with `ErrorResponse` model

## Logging

**Framework:** Python `logging` with structured logging
**Patterns:**
```python
import logging
from core.structured_logger import get_logger

logger = get_logger(__name__)

# Info logging
logger.info(f"Registered new agent: {name}")

# Error logging with context
logger.error(
    f"Failed to create canvas audit: {e}",
    extra={"canvas_id": canvas_id, "user_id": user_id}
)
```

**When to Log:**
- Info: User actions, successful operations
- Error: Exceptions, failed operations
- Debug: Detailed operation flow
- Warning: Non-critical issues

## Comments

**When to Comment:**
- Complex business logic
- API endpoints with complex parameters
- Critical system invariants
- TODO items with clear justification
- Performance-critical sections

**JSDoc/TSDoc:**
- Required for all public functions and classes
- Format:
```python
def submit_feedback(
    self,
    agent_id: str,
    user_id: str,
    original_output: str,
    user_correction: str,
    input_context: Optional[str] = None
) -> AgentFeedback:
    """
    Submit user feedback for an agent's action.
    Triggers AI adjudication to check if the user is correct.

    Args:
        agent_id: ID of the agent receiving feedback
        user_id: ID of the user submitting feedback
        original_output: Original agent output
        user_correction: User's correction
        input_context: Original input context

    Returns:
        AgentFeedback: Created feedback record

    Raises:
        AtomValidationError: If validation fails
        AtomNotFoundError: If agent not found
    """
```

## Function Design

**Size:**
- Functions should be < 50 lines
- Single responsibility principle
- Max 3-4 parameters (use dataclasses for complex parameters)

**Parameters:**
- Required parameters first
- Optional parameters with defaults last
- Use `Optional[X]` for nullable parameters
- Type hints for all parameters

**Return Values:**
- Single return type (Union for multiple)
- `None` for void functions
- Use dataclasses for complex return types
- Consistent return types within modules

## Module Design

**Exports:**
- Explicit `__all__` list for public APIs
- No private exports (all functions should be documented)
- Use `from .module import specific_function`

**Barrel Files:**
- `__init__.py` exports public APIs
- No circular imports
- Type hints for all exported functions
- Import re-exports for clean imports

## Database Patterns

**Session Management:**
```python
# Context Manager (Service Layer)
with get_db_session() as db:
    agent = db.query(Agent).filter(Agent.id == agent_id).first()

# Dependency Injection (API Routes)
@app.get("/agents/{agent_id}")
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    return db.query(Agent).filter(Agent.id == agent_id).first()
```

**Model Definitions:**
- All models inherit from `Base`
- Use `Column` for all fields
- Add `__tablename__` class attribute
- Use `__repr__` for debugging
- Indexes for frequently queried fields

**Transaction Management:**
- Use context managers for transactions
- Auto-commit on success, auto-rollback on exception
- Explicit transactions for multi-table operations

## API Design

**Response Standards:**
```python
# Success Response
{
    "success": True,
    "data": {...},
    "message": "Operation successful",
    "timestamp": "2026-02-10T10:30:00.000Z"
}

# Error Response
{
    "success": False,
    "error_code": "AGENT_NOT_FOUND",
    "message": "Agent with ID 'abc123' not found",
    "details": {"agent_id": "abc123"},
    "timestamp": "2026-02-10T10:30:00.000Z"
}
```

**Route Patterns:**
- Use `BaseAPIRouter` for standardized routes
- Include `@handle_errors` decorator
- Type hints for all parameters and return values
- Document all endpoints with docstrings

---

*Convention analysis: 2026-02-10*