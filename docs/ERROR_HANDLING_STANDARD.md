# Standard Error Handling Pattern - Atom Platform

This document establishes the standard error handling pattern for all API endpoints and services in the Atom platform.

## Exception Hierarchy

All exceptions inherit from `AtomException`:

```python
from core.exceptions import (
    AtomException,
    AuthenticationError,
    UserNotFoundError,
    AgentNotFoundError,
    ValidationError,
    LLMProviderError,
    CanvasNotFoundError,
    # ... and more
)
```

## Standard Patterns

### 1. API Endpoint Error Handling

#### Validation Errors (422 Unprocessable Entity)

```python
from fastapi import HTTPException, status
from pydantic import ValidationError as PydanticValidationError
from core.exceptions import ValidationError

@router.post("/agents")
async def create_agent(
    agent_data: AgentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Validate agent data
        if not agent_data.name:
            raise ValidationError(
                message="Agent name is required",
                field="name",
                code=ErrorCode.VALIDATION_MISSING_FIELD
            )

        # Create agent
        agent = Agent(**agent_data.dict())
        db.add(agent)
        db.commit()
        return agent

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "validation_error",
                "message": str(e.message),
                "field": e.field,
                "code": e.code.value
            }
        )
```

#### Not Found Errors (404 Not Found)

```python
from core.exceptions import AgentNotFoundError

@router.get("/agents/{agent_id}")
async def get_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()

    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "message": f"Agent {agent_id} not found",
                "resource_type": "Agent",
                "resource_id": agent_id,
                "code": ErrorCode.AGENT_NOT_FOUND.value
            }
        )

    return agent
```

#### Permission Errors (403 Forbidden)

```python
from core.exceptions import WorkspaceAccessDeniedError

@router.delete("/workspaces/{workspace_id}")
async def delete_workspace(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()

    if workspace.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "permission_denied",
                "message": "You don't have permission to delete this workspace",
                "required_permission": "workspace:delete",
                "workspace_id": workspace_id,
                "code": ErrorCode.WORKSPACE_ACCESS_DENIED.value
            }
        )

    db.delete(workspace)
    db.commit()
    return {"success": True}
```

#### Authentication Errors (401 Unauthorized)

```python
from core.exceptions import AuthenticationError

@router.post("/auth/login")
async def login(credentials: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()

    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "authentication_failed",
                "message": "Invalid email or password",
                "code": ErrorCode.AUTH_INVALID_CREDENTIALS.value
            }
        )

    return {"access_token": create_access_token(user.id)}
```

### 2. Service Layer Error Handling

#### Using Custom Exceptions

```python
from core.exceptions import AgentExecutionError, LLMProviderError
import logging

logger = logging.getLogger(__name__)

class AgentService:
    async def execute_agent(self, agent_id: str, input_data: Dict) -> Dict:
        try:
            agent = self._get_agent(agent_id)
            if not agent:
                raise AgentNotFoundError(
                    message=f"Agent {agent_id} not found",
                    agent_id=agent_id
                )

            # Execute agent
            result = await self._run_agent(agent, input_data)
            return result

        except AgentNotFoundError as e:
            logger.warning(f"Agent execution failed: {e.message}")
            raise  # Re-raise for API layer to handle

        except LLMProviderError as e:
            logger.error(f"LLM provider error: {e.message}", exc_info=True)
            raise AgentExecutionError(
                message=f"Agent execution failed due to LLM error: {e.message}",
                agent_id=agent_id,
                original_error=str(e)
            )

        except Exception as e:
            logger.error(f"Unexpected error executing agent: {e}", exc_info=True)
            raise AgentExecutionError(
                message=f"Unexpected error executing agent {agent_id}",
                agent_id=agent_id,
                original_error=str(e)
            )
```

### 3. Database Error Handling

```python
from sqlalchemy.exc import IntegrityError, OperationalError
from core.exceptions import DatabaseError
import logging

logger = logging.getLogger(__name__)

async def create_workspace(workspace_data: Dict, db: Session):
    try:
        workspace = Workspace(**workspace_data)
        db.add(workspace)
        db.commit()
        return workspace

    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error: {e}")
        raise ValidationError(
            message="Workspace with this name already exists",
            field="name",
            code=ErrorCode.DATABASE_CONSTRAINT_VIOLATION
        )

    except OperationalError as e:
        db.rollback()
        logger.error(f"Database operational error: {e}", exc_info=True)
        raise DatabaseError(
            message="Database operation failed",
            original_error=str(e),
            code=ErrorCode.DATABASE_ERROR
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected database error: {e}", exc_info=True)
        raise DatabaseError(
            message="Unexpected database error",
            original_error=str(e)
        )
```

## Standard Error Response Format

All error responses should follow this structure:

```json
{
  "error": "error_type_code",
  "message": "Human-readable error message",
  "code": "ERROR_CODE_1234",
  "details": {
    "field": "field_name",
    "resource_type": "Resource",
    "resource_id": "id123"
  },
  "timestamp": "2026-02-02T21:30:00Z"
}
```

## Error Codes by Category

### Authentication & Authorization (1000-1099)
- `AUTH_1001` - Invalid credentials
- `AUTH_1002` - Token expired
- `AUTH_1003` - Token invalid
- `AUTH_1004` - Unauthorized
- `AUTH_1005` - Forbidden

### User Management (1100-1199)
- `USER_1101` - User not found
- `USER_1102` - User already exists
- `USER_1103` - Invalid user status
- `USER_1104` - Insufficient permissions

### Agents & AI (2000-2099)
- `AGENT_2001` - Agent not found
- `AGENT_2002` - Agent execution failed
- `AGENT_2003` - Agent timeout
- `AGENT_2004` - Agent governance failed
- `AGENT_2005` - Insufficient maturity

### LLM & Streaming (2100-2199)
- `LLM_2101` - Provider error
- `LLM_2102` - Rate limited
- `LLM_2103` - Invalid response
- `LLM_2104` - Context too long

### Canvas & Presentations (3000-3099)
- `CANVAS_3001` - Canvas not found
- `CANVAS_3002` - Invalid component
- `CANVAS_3003` - Render failed
- `CANVAS_3004` - Audit failed

### Database (6000-6099)
- `DB_6001` - Database error
- `DB_6002` - Connection failed
- `DB_6003` - Constraint violation
- `DB_6004` - Query failed

### Validation (7000-7099)
- `VAL_7001` - Validation error
- `VAL_7002` - Missing field
- `VAL_7003` - Invalid type
- `VAL_7004` - Invalid format

## Logging Best Practices

### Error Levels

```python
# Debug - Detailed diagnostic information
logger.debug(f"Variable value: {variable}")

# Info - Confirmation things are working
logger.info(f"Processing request for {user_id}")

# Warning - Something unexpected but recoverable
logger.warning(f"Cache miss for key: {key}")

# Error - Serious problem
logger.error(f"Failed to save to database: {e}", exc_info=True)

# Critical - Serious error, program may not continue
logger.critical(f"Database connection lost: {e}")
```

### Always Include `exc_info=True` for Errors

```python
try:
    risky_operation()
except Exception as e:
    logger.error(f"Operation failed: {e}", exc_info=True)  # Includes stack trace
    raise
```

## Quick Reference

### Common Imports

```python
from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from core.exceptions import (
    AtomException,
    ValidationError,
    NotFoundError,
    AuthenticationError,
    PermissionDeniedError,
    DatabaseError,
    ErrorCode
)
import logging

logger = logging.getLogger(__name__)
```

### Raising HTTP Exceptions

```python
# Validation (422)
raise HTTPException(
    status_code=422,
    detail={"error": "validation_error", "message": "Invalid input", "code": "VAL_7001"}
)

# Not Found (404)
raise HTTPException(
    status_code=404,
    detail={"error": "not_found", "message": "Resource not found", "code": "AGENT_2001"}
)

# Forbidden (403)
raise HTTPException(
    status_code=403,
    detail={"error": "permission_denied", "message": "Access denied", "code": "AUTH_1005"}
)

# Unauthorized (401)
raise HTTPException(
    status_code=401,
    detail={"error": "unauthorized", "message": "Authentication required", "code": "AUTH_1004"}
)

# Server Error (500)
raise HTTPException(
    status_code=500,
    detail={"error": "server_error", "message": "Internal error", "code": "GEN_0001"}
)
```

## Migration Checklist

When updating existing code to use standard error handling:

- [ ] Replace generic `Exception` with specific exception types
- [ ] Add proper error codes from `ErrorCode` enum
- [ ] Include `exc_info=True` in all `logger.error()` calls
- [ ] Use consistent error response format
- [ ] Add proper HTTP status codes
- [ ] Include relevant details in error responses
- [ ] Log errors at appropriate levels (debug, info, warning, error, critical)

## Related Documents

- `backend/core/exceptions.py` - Full exception hierarchy
- `CLAUDE.md` - Project architecture and patterns
- API documentation for each endpoint
