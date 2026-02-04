# Error Handling Guidelines for Atom

## Overview

This document defines standardized error handling patterns for the Atom codebase. Consistent error handling improves debugging, monitoring, and user experience.

## Standards

### Service Layer Error Handling

**Location**: `backend/core/services/`, `backend/integrations/`, `backend/accounting/`

**Pattern**: Return structured response dict

```python
async def my_service_function(param: str) -> Dict[str, Any]:
    """
    Service function with standardized error handling.

    Returns:
        {
            "success": bool,
            "data": Any,  # Present if success=True
            "error": {   # Present if success=False
                "code": str,
                "message": str,
                "details": Optional[Dict]
            }
        }
    """
    try:
        # Perform operation
        result = do_something(param)

        return {
            "success": True,
            "data": result
        }

    except ValueError as e:
        logger.error(f"Invalid parameter: {e}")
        return {
            "success": False,
            "error": {
                "code": "INVALID_PARAMETER",
                "message": str(e),
                "details": {"param": param}
            }
        }

    except Exception as e:
        logger.error(f"Unexpected error in my_service_function: {e}")
        return {
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "details": {"error": str(e)}
            }
        }
```

### API Layer Error Handling

**Location**: `backend/api/`

**Pattern**: Use `BaseAPIRouter` for all responses

```python
from core.base_routes import BaseAPIRouter
from fastapi import HTTPException

router = BaseAPIRouter(prefix="/api/v1/myresource", tags=["myresource"])

@router.post("/items")
async def create_item(item: ItemCreate, db: Session = Depends(get_db)):
    """Create item with standardized error handling"""
    try:
        # Call service layer
        result = await my_service.create_item(item)

        if not result.get("success"):
            # Handle service error
            error = result.get("error", {})
            raise router.error_response(
                error_code=error.get("code", "UNKNOWN_ERROR"),
                message=error.get("message", "An error occurred"),
                details=error.get("details"),
                status_code=400
            )

        # Return success response
        return router.success_response(
            data=result.get("data"),
            message="Item created successfully"
        )

    except HTTPException:
        raise  # Re-raise HTTPException as-is

    except Exception as e:
        logger.error(f"Unexpected error in create_item: {e}")
        raise router.internal_error(
            message="Failed to create item",
            details={"error": str(e)}
        )
```

## Error Codes

### Standard Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid input data |
| `INVALID_PARAMETER` | 400 | Invalid parameter value |
| `MISSING_PARAMETER` | 400 | Required parameter missing |
| `NOT_FOUND` | 404 | Resource not found |
| `ALREADY_EXISTS` | 409 | Resource already exists |
| `CONFLICT` | 409 | Conflict with existing state |
| `UNAUTHORIZED` | 401 | Authentication required |
| `PERMISSION_DENIED` | 403 | Insufficient permissions |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `INTERNAL_ERROR` | 500 | Unexpected server error |
| `SERVICE_UNAVAILABLE` | 503 | Service temporarily unavailable |

### Domain-Specific Error Codes

Accounting:
- `ACCOUNT_NOT_FOUND` (404)
- `INSUFFICIENT_FUNDS` (400)
- `TRANSACTION_FAILED` (500)

Integrations:
- `INTEGRATION_NOT_CONFIGURED` (400)
- `EXTERNAL_API_ERROR` (502)
- `RATE_LIMIT_EXCEEDED` (429)

Agents:
- `AGENT_NOT_FOUND` (404)
- `AGENT_EXECUTION_FAILED` (500)
- `GOVERNANCE_DENIED` (403)

## Migration Steps

### Step 1: Audit Current Code

Find files using non-standard error handling:

```bash
# Find files using HTTPException in service layer
grep -r "raise HTTPException" backend/integrations/ backend/accounting/

# Find files returning empty lists on error
grep -r "return \[\]" backend/integrations/ backend/accounting/

# Find API routes not using BaseAPIRouter
grep -r "class.*Router.*APIRouter" backend/api/ | grep -v BaseAPIRouter
```

### Step 2: Update Service Layer

**Before**:
```python
def get_transaction(txn_id: str):
    txn = db.query(Transaction).filter_by(id=txn_id).first()
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return txn
```

**After**:
```python
def get_transaction(txn_id: str) -> Dict[str, Any]:
    try:
        txn = db.query(Transaction).filter_by(id=txn_id).first()
        if not txn:
            return {
                "success": False,
                "error": {
                    "code": "NOT_FOUND",
                    "message": "Transaction not found",
                    "details": {"transaction_id": txn_id}
                }
            }
        return {
            "success": True,
            "data": txn
        }
    except Exception as e:
        logger.error(f"Error getting transaction: {e}")
        return {
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Failed to get transaction",
                "details": {"error": str(e)}
            }
        }
```

### Step 3: Update API Layer

**Before**:
```python
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/transactions")

@router.get("/{txn_id}")
async def get_transaction(txn_id: str, db: Session = Depends(get_db)):
    txn = get_transaction(db, txn_id)
    return txn
```

**After**:
```python
from core.base_routes import BaseAPIRouter

router = BaseAPIRouter(prefix="/api/v1/transactions", tags=["transactions"])

@router.get("/{txn_id}")
async def get_transaction(txn_id: str, db: Session = Depends(get_db)):
    result = get_transaction(db, txn_id)

    if not result.get("success"):
        error = result.get("error", {})
        raise router.not_found_error(
            resource="Transaction",
            resource_id=txn_id
        )

    return router.success_response(
        data=result.get("data"),
        message="Transaction retrieved successfully"
    )
```

## Logging Standards

### Error Logging

Always log errors with context:

```python
# Good
logger.error(
    f"Failed to process transaction {txn_id}: {error}",
    extra={"transaction_id": txn_id, "user_id": user_id, "amount": amount}
)

# Bad
logger.error(f"Error: {error}")
```

### Warning Logging

Log warnings for recoverable issues:

```python
logger.warning(
    f"Cache miss for agent {agent_id}, falling back to database",
    extra={"agent_id": agent_id}
)
```

### Info Logging

Log info for important operations:

```python
logger.info(
    f"Agent {agent_id} completed workflow {workflow_id} in {duration_ms}ms",
    extra={"agent_id": agent_id, "workflow_id": workflow_id, "duration_ms": duration_ms}
)
```

## Testing Error Handling

### Unit Tests

Test error paths explicitly:

```python
def test_get_transaction_not_found():
    """Test handling of non-existent transaction"""
    result = get_transaction(db, "nonexistent-id")

    assert result["success"] is False
    assert result["error"]["code"] == "NOT_FOUND"
    assert "Transaction not found" in result["error"]["message"]

def test_get_transaction_internal_error():
    """Test handling of database errors"""
    with patch.object(db, 'query') as mock_query:
        mock_query.side_effect(Exception("Database connection failed"))

        result = get_transaction(db, "txn123")

        assert result["success"] is False
        assert result["error"]["code"] == "INTERNAL_ERROR"
```

### Integration Tests

Test API error responses:

```python
def test_api_transaction_not_found(client):
    """Test API returns 404 for non-existent transaction"""
    response = client.get("/api/v1/transactions/nonexistent-id")

    assert response.status_code == 404
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "NOT_FOUND"
```

## Checklist

For each file being migrated:

- [ ] Service functions return `{"success": bool, "data": Any, "error": Optional[Dict]}`
- [ ] No `raise HTTPException` in service layer
- [ ] No `return []` on error (use structured error)
- [ ] API routes use `BaseAPIRouter`
- [ ] API routes use `router.success_response()` / `router.error_response()`
- [ ] All errors are logged with context
- [ ] Error codes are from standard list
- [ ] Tests cover error paths

## Related Documents

- `backend/core/base_routes.py` - BaseAPIRouter implementation
- `backend/core/error_handling.py` - Custom exception classes (if exists)
- `docs/API_STANDARDS.md` - API design guidelines

---

**Last Updated**: February 4, 2026
**Status**: Active
