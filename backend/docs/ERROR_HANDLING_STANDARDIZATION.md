# Error Handling Standardization Guide

**Date**: February 5, 2026
**Status**: ✅ Documented (infrastructure already exists)

---

## Executive Summary

Atom already has comprehensive error handling infrastructure. This document standardizes the usage patterns across all API routes.

**Key Finding**: Error handling middleware is already production-ready. The issue is **inconsistent adoption**, not missing functionality.

---

## Existing Infrastructure

### 1. Error Handling Middleware
**File**: `middleware/error_handling.py` (299 lines)
**Also**: `core/error_middleware.py` (duplicate - needs consolidation)

#### Components
- ✅ `ErrorHandlingMiddleware` - Global exception handler
- ✅ `ValidationErrorMiddleware` - Pydantic validation errors
- ✅ `CircuitBreakerMiddleware` - Circuit breaker pattern

#### Features
- Request ID tracking (`X-Request-ID` header)
- Performance logging (>2s requests)
- Detailed error responses with timestamps
- Debug mode for development
- Automatic 5xx error handling
- Graceful degradation

### 2. BaseAPIRouter Error Methods
**File**: `core/base_routes.py`

#### Available Methods
```python
router.error_response(error_code, message, details, status_code)
router.validation_error(field, message, details)
router.not_found_error(resource, resource_id, details)
router.permission_denied_error(action, resource, details)
router.unauthorized_error(message, details)
router.conflict_error(message, conflicting_resource, details)
router.rate_limit_error(retry_after, details)
router.internal_error(message, details)
router.governance_denied_error(agent_id, action, maturity_level, required_level, details)
```

### 3. Database Operation Decorator
**File**: `core/base_routes.py` (line 562)

```python
@safe_db_operation
def update_agent(agent_id: str, **kwargs):
    with SessionLocal() as db:
        agent = db.query(AgentRegistry).filter(...).first()
        agent.name = kwargs.get("name")
        db.commit()
        return agent
```

---

## Standard Patterns

### Pattern 1: API Routes (Recommended)

**For simple routes**, rely on middleware:

```python
@router.post("/endpoint")
async def create_resource(data: ResourceCreate, db: Session = Depends(get_db)):
    # Business logic
    resource = create_resource(data)
    return router.success_response(data=resource, message="Created")
```

**Middleware will automatically**:
- Catch unexpected exceptions
- Log errors with request ID
- Return standardized error response
- Handle 4xx and 5xx errors

### Pattern 2: Expected Errors (Use BaseAPIRouter Methods)

**For known error conditions**, use BaseAPIRouter methods:

```python
@router.post("/agents/{agent_id}")
async def update_agent(agent_id: str, data: AgentUpdate, db: Session = Depends(get_db)):
    agent = db.query(AgentRegistry).filter_by(id=agent_id).first()

    if not agent:
        raise router.not_found_error("Agent", agent_id)

    if not can_update(agent):
        raise router.permission_denied_error("update", "agent")

    # ... update logic

    return router.success_response(data=agent, message="Updated")
```

### Pattern 3: Manual Error Handling (Use Sparingly)

**Only use try/catch for specific recovery logic**:

```python
@router.post("/upload")
async def upload_document(file: UploadFile):
    try:
        content = await parse_pdf(file)
    except PDFParseError as e:
        # Specific handling for PDF errors
        logger.warning(f"PDF parsing failed: {e}")
        return router.error_response(
            error_code="PDF_PARSE_ERROR",
            message="Could not parse PDF file",
            details={"filename": file.filename},
            status_code=400
        )

    # Continue processing
    return router.success_response(data=content)
```

**Don't use** try/catch just to re-raise as `router.internal_error()`. Let middleware handle it.

---

## Anti-Patterns to Avoid

### ❌ Manual Try/Catch Without Recovery
```python
@router.post("/endpoint")
async def endpoint(data: Data):
    try:
        result = process(data)
        return result
    except Exception as e:
        logger.error(f"Error: {e}")
        raise router.internal_error(detail=str(e))  # ❌ Redundant!
```

**Why**: Middleware already does this. You're duplicating effort.

**Instead**:
```python
@router.post("/endpoint")
async def endpoint(data: Data):
    result = process(data)
    return result  # ✅ Let middleware handle exceptions
```

### ❌ Inconsistent Error Response Formats
```python
# Some routes return:
{"error": "Not found"}

# Others return:
{"success": False, "message": "Not found"}

# Others return:
{"detail": "Not found"}
```

**Instead**: Use BaseAPIRouter methods for consistency:
```python
raise router.not_found_error("Agent", agent_id)
# Returns standardized format:
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Agent not found",
    "resource": "Agent",
    "resource_id": "123",
    ...
  }
}
```

### ❌ Direct HTTPException
```python
from fastapi import HTTPException

raise HTTPException(status_code=404, detail="Not found")  # ❌ Inconsistent
```

**Instead**:
```python
raise router.not_found_error("Agent", agent_id)  # ✅ Consistent
```

---

## Error Response Standards

### Success Response
```json
{
  "success": true,
  "data": {...},
  "message": "Operation completed successfully"
}
```

### Error Response (4xx Client Errors)
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Agent not found",
    "resource": "Agent",
    "resource_id": "abc123",
    "request_id": "req-xyz-789",
    "timestamp": "2026-02-05T21:00:00Z",
    "path": "/api/agents/abc123",
    "method": "GET"
  }
}
```

### Error Response (5xx Server Errors)
```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "Internal server error occurred",
    "request_id": "req-xyz-789",
    "timestamp": "2026-02-05T21:00:00Z",
    "path": "/api/agents/abc123",
    "method": "GET"
  },
  "debug": {  # Only in development
    "exception": "...",
    "traceback": ["..."]
  }
}
```

---

## Migration Guide

### For New Routes
1. Use `BaseAPIRouter` (not `APIRouter`)
2. Return `router.success_response()` for success
3. Use `router.not_found_error()` for 404s
4. Use `router.permission_denied_error()` for 403s
5. **Don't** add try/catch unless you have specific recovery logic

### For Existing Routes

#### Priority 1: High-Traffic Routes
Update these files first:
- `api/canvas_routes.py` ✅ (already compliant)
- `api/document_routes.py` - Remove redundant try/catch
- `api/auth_routes.py` - Use consistent error methods
- `api/agent_routes.py` - Standardize error responses

#### Priority 2: Medium-Traffic Routes
- `api/artifact_routes.py`
- `api/business_facts_routes.py`
- All other route files

#### Priority 3: Low-Traffic Routes
- Update as time permits
- Less critical for consistency

---

## Consolidation Needed

### Issue: Duplicate Error Middleware
Two files with similar functionality:
1. `middleware/error_handling.py` (299 lines)
2. `core/error_middleware.py` (duplicate)

### Recommendation
**Consolidate to single file**: `middleware/error_handling.py`

**Action Items**:
1. ✅ Keep `middleware/error_handling.py` (more complete)
2. ❌ Deprecate `core/error_middleware.py` (duplicate)
3. Update all imports from `core.error_middleware` to `middleware.error_handling`
4. Update documentation to reference canonical location

**Files to Update**:
- `main.py` (if importing from old location)
- Any route files importing error middleware
- Documentation files

---

## Testing

### Manual Testing Steps
1. Trigger expected errors (404, 403, 422)
2. Verify consistent error response format
3. Check request ID is present in all error responses
4. Verify errors are logged with request ID
5. Test debug mode (development) vs production

### Automated Testing
```python
def test_error_response_format():
    """Test that errors follow standard format"""
    response = client.get("/api/agents/nonexistent")
    assert response.status_code == 404

    error = response.json()
    assert "error" in error
    assert "code" in error["error"]
    assert "message" in error["error"]
    assert "request_id" in error["error"]
    assert "timestamp" in error["error"]
```

---

## Performance Considerations

### Middleware Overhead
- **Request ID generation**: ~0.001ms (UUID)
- **Performance logging**: ~0.01ms (datetime)
- **Error response formatting**: ~0.1ms (JSON)

**Total overhead**: <1ms per request (acceptable)

### Slow Request Logging
Requests >2s are logged as warnings. This is configurable:

```python
# In ErrorHandlingMiddleware.log_performance()
if duration > 2.0:  # Configurable threshold
    performance_logger.warning(...)
```

---

## Configuration

### Environment Variables
```bash
# Enable debug mode (adds stack traces to error responses)
DEBUG=true

# Circuit breaker settings
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_TIMEOUT=60
```

### Middleware Setup
```python
from middleware.error_handling import setup_error_middleware

# In main.py
app = FastAPI()
setup_error_middleware(app, debug=os.getenv("DEBUG", "false").lower() == "true")
```

---

## Monitoring

### Key Metrics
1. **Error rate**: Percentage of requests ending in errors
2. **Error types**: Distribution of 4xx vs 5xx
3. **Slow requests**: Requests >2s
4. **Circuit breaker trips**: Endpoints exceeding failure threshold

### Logging Locations
- Errors: `logs/errors.log`
- Performance: `logs/performance.log`
- Standard: `logs/atom.log` (via structured logger)

---

## Summary

### Current State
- ✅ Comprehensive error middleware exists
- ✅ BaseAPIRouter has standardized error methods
- ✅ Request ID tracking implemented
- ❌ Inconsistent adoption across routes
- ❌ Duplicate error middleware files

### Recommendations
1. **Document standard patterns** (this document) ✅
2. **Consolidate duplicate middleware** (high priority)
3. **Update high-traffic routes** to use consistent patterns
4. **Add error response tests** to prevent regressions
5. **Monitor error rates** in production

### Priority Matrix

| Task | Impact | Effort | Priority |
|------|--------|--------|----------|
| Document patterns | High | Low | ✅ Done |
| Consolidate middleware | High | Medium | High |
| Update high-traffic routes | Medium | Medium | Medium |
| Add error tests | Medium | Medium | Medium |
| Update low-traffic routes | Low | High | Low |

---

## References

- **Error Middleware**: `middleware/error_handling.py`
- **BaseAPIRouter**: `core/base_routes.py`
- **Setup Function**: `setup_error_middleware(app, debug=False)`
- **Related Docs**: `IMPLEMENTATION_COMPLETE.md`, `FINAL_VERIFICATION.md`

**Author**: Claude Sonnet 4.5
**Status**: Documented (infrastructure production-ready)
**Next Step**: Consolidate duplicate middleware files
