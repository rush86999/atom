# Error Handling Patterns in Atom

This document describes the error handling patterns used across the Atom codebase.

## Standard Patterns

### 1. API Routes (FastAPI Endpoints)
**Pattern**: Raise `HTTPException` for errors

```python
from fastapi import HTTPException

@router.get("/users/{user_id}")
async def get_user(user_id: str):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
```

**Used in**:
- `api/token_routes.py`
- `core/auth_endpoints.py`
- Most API route files

### 2. Service Layer Functions
**Pattern**: Return structured dicts with `success` boolean

```python
def some_service_function() -> Dict[str, Any]:
    try:
        # ... operation ...
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        return {"success": False, "error": str(e)}
```

**Used in**:
- `core/canvas_coding_service.py`
- `core/canvas_sheets_service.py`
- Other service layer functions

### 3. Special Cases
**Pattern**: Use `JSONResponse` for specific response requirements

```python
from fastapi.responses import JSONResponse

if requires_2fa:
    return JSONResponse(
        status_code=200,
        content={"two_factor_required": True, "user_id": user.id}
    )
```

**Used in**:
- `core/auth_endpoints.py` (2FA flow)
- Other special response cases

## Guidelines

### When to use HTTPException (API Routes)
- Client errors (4xx): Invalid input, not found, unauthorized
- Server errors (5xx): Internal errors, service unavailable
- All FastAPI route handlers

### When to use Structured Responses (Service Layer)
- Service functions called by other services
- Background tasks
- Functions that need to signal success/failure without raising
- Internal API calls

### When to use JSONResponse
- Non-standard status codes with custom response format
- Special response requirements (e.g., 2FA flow)
- Compatibility with existing clients

## Current Status

✅ **Consistent**: The codebase already follows these patterns reasonably well.
- API routes use HTTPException
- Service layer uses structured responses
- Special cases use JSONResponse appropriately

## Recommendations

1. **Maintain current patterns** - The existing separation is good
2. **Add type hints** - Improve with proper response models
3. **Document patterns** - This file serves as documentation
4. **No refactoring needed** - Current patterns are appropriate for their contexts

---

*Generated: 2026-02-03*
