# API Response Format Standardization

**Date**: February 5, 2026
**Status**: ✅ Documented (infrastructure already exists)

---

## Executive Summary

Atom already has standardized response methods in BaseAPIRouter. This document documents the standard patterns for consistency across all API routes.

**Key Finding**: Response infrastructure already exists. The issue is **inconsistent adoption**, not missing functionality.

---

## Standard Response Patterns

### Pattern 1: Success Response (Recommended)

**Use for**: All successful API responses

```python
from core.base_routes import BaseAPIRouter

router = BaseAPIRouter(prefix="/api/resources")

@router.post("/resource")
async def create_resource(data: ResourceCreate, db: Session = Depends(get_db)):
    resource = create_resource(data)

    return router.success_response(
        data=resource,
        message="Resource created successfully"
    )
```

**Response Format**:
```json
{
  "success": true,
  "data": {
    "id": "123",
    "name": "Resource Name"
  },
  "message": "Resource created successfully",
  "timestamp": "2026-02-05T21:00:00.000000Z"
}
```

### Pattern 2: Success Response with Metadata

**Use for**: Paginated responses, or responses with additional context

```python
@router.get("/resources")
async def list_resources(
    page: int = 1,
    limit: int = 10,
    db: Session = Depends(get_db)
):
    resources, total = get_resources(db, page, limit)

    return router.success_response(
        data=resources,
        message=f"Retrieved {len(resources)} resources",
        metadata={
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit
            }
        }
    )
```

**Response Format**:
```json
{
  "success": true,
  "data": [...],
  "message": "Retrieved 10 resources",
  "timestamp": "2026-02-05T21:00:00.000000Z",
  "metadata": {
    "pagination": {
      "page": 1,
      "limit": 10,
      "total": 100,
      "pages": 10
    }
  }
}
```

### Pattern 3: Error Responses (Use BaseAPIRouter Methods)

**Use for**: Expected error conditions

```python
@router.get("/resources/{resource_id}")
async def get_resource(resource_id: str, db: Session = Depends(get_db)):
    resource = db.query(Resource).filter_by(id=resource_id).first()

    if not resource:
        raise router.not_found_error("Resource", resource_id)

    return router.success_response(data=resource)
```

## Response Methods Available

### Success Response
```python
router.success_response(
    data: Any = None,
    message: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    status_code: int = 200
) -> Dict[str, Any]
```

### Error Responses
```python
router.error_response(
    error_code: str,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    status_code: int = 400
)

router.validation_error(
    field: str,
    message: str,
    details: Optional[Dict[str, Any]] = None
)

router.not_found_error(
    resource: str,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
)

router.permission_denied_error(
    action: str,
    resource: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
)
```

---

## Current State Analysis

### Routes Using Standard Pattern ✅
- `api/canvas_routes.py` - Reference implementation
- Most new routes follow the pattern

### Routes Using Direct Pydantic Models ⚠️
- `api/document_routes.py` - Returns `DocumentResponse` directly
- `api/artifact_routes.py` - Returns models directly
- `api/business_facts_routes.py` - Returns models directly

### Impact Assessment
- **Functional Impact**: None (clients work with both formats)
- **Consistency Impact**: Medium (mixed response formats)
- **Effort to Fix**: Medium (~20 route files)

---

## Migration Strategy

### Phase 1: High-Traffic Routes (Priority)

Update these files first:
1. `api/document_routes.py` - High usage
2. `api/agent_routes.py` - Critical endpoints
3. `api/workflow_routes.py` - Core functionality

### Phase 2: Medium-Traffic Routes
- `api/artifact_routes.py`
- `api/business_facts_routes.py`
- Other route files

### Phase 3: Low-Traffic Routes
- Update as time permits
- Lower priority

---

## Migration Example

### Before (Direct Pydantic Model)
```python
@router.post("/ingest", response_model=DocumentResponse)
async def ingest_document(
    request: DocumentIngestRequest,
    current_user: User = Depends(get_current_user)
):
    try:
        doc_id = str(uuid.uuid4())
        # ... process document ...

        return DocumentResponse(
            id=doc_id,
            title=title,
            type=doc_type,
            metadata=doc.get("metadata", {}),
            ingested_at=doc["ingested_at"],
            chunk_count=doc["chunk_count"]
        )
    except Exception as e:
        logger.error(f"Document ingestion failed: {e}")
        raise router.internal_error(detail=str(e))
```

### After (Standard Response)
```python
@router.post("/ingest")
async def ingest_document(
    request: DocumentIngestRequest,
    current_user: User = Depends(get_current_user)
):
    try:
        doc_id = str(uuid.uuid4())
        # ... process document ...

        return router.success_response(
            data={
                "id": doc_id,
                "title": title,
                "type": doc_type,
                "metadata": doc.get("metadata", {}),
                "ingested_at": doc["ingested_at"],
                "chunk_count": doc["chunk_count"]
            },
            message="Document ingested successfully"
        )
    except Exception as e:
        logger.error(f"Document ingestion failed: {e}")
        raise router.internal_error(detail=str(e))
```

**Key Changes**:
1. Removed `response_model=DocumentResponse` from decorator
2. Changed `return DocumentResponse(...)` to `return router.success_response(data={...})`
3. Added success message

---

## Benefits of Standardization

### 1. Consistent Client Experience
All responses follow the same structure, making client code simpler:
```python
# Client code
response = await api.call("/endpoint")

if response["success"]:
    data = response["data"]
    message = response.get("message")
else:
    error = response["error"]
```

### 2. Easier Error Handling
Standardized error responses across all endpoints:
```python
# All errors follow this format
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Resource not found",
    ...
  }
}
```

### 3. Better Observability
All responses include timestamps, making debugging easier:
```json
{
  "success": true,
  "data": {...},
  "timestamp": "2026-02-05T21:00:00.000000Z"
}
```

### 4. Metadata Support
Built-in support for pagination, timing, and other metadata:
```json
{
  "success": true,
  "data": [...],
  "metadata": {
    "pagination": {...},
    "timing": {...}
  }
}
```

---

## Backward Compatibility

### Breaking Changes
⚠️ **Yes**, changing response formats is a breaking change for existing clients.

### Mitigation Strategies

#### Option 1: Versioned Routes (Recommended)
```python
# v1 (old format)
@router_v1.post("/documents/ingest")
async def ingest_document_v1(...):
    return DocumentResponse(...)

# v2 (new format)
@router_v2.post("/documents/ingest")
async def ingest_document_v2(...):
    return router.success_response(data={...})
```

#### Option 2: Feature Flag
```python
USE_STANDARD_RESPONSES = os.getenv("USE_STANDARD_RESPONSES", "false") == "true"

@router.post("/documents/ingest")
async def ingest_document(...):
    if USE_STANDARD_RESPONSES:
        return router.success_response(data={...})
    else:
        return DocumentResponse(...)
```

#### Option 3: Gradual Migration
- Document the deprecation timeline
- Communicate with API consumers
- Provide migration guide
- Update in phases

---

## Testing

### Unit Tests
```python
def test_standard_response_format():
    """Test that responses follow standard format"""
    response = client.post("/api/resources", json={"name": "Test"})

    assert response.status_code == 200
    data = response.json()

    # Standard fields
    assert "success" in data
    assert "data" in data
    assert "timestamp" in data
    assert data["success"] is True

def test_error_response_format():
    """Test that errors follow standard format"""
    response = client.get("/api/resources/nonexistent")

    assert response.status_code == 404
    data = response.json()

    # Standard error format
    assert "error" in data
    assert "code" in data["error"]
    assert "message" in data["error"]
```

### Integration Tests
```python
def test_response_consistency():
    """Test that all endpoints use standard response"""
    endpoints = [
        "/api/resources",
        "/api/agents",
        "/api/workflows",
    ]

    for endpoint in endpoints:
        response = client.get(endpoint)
        data = response.json()

        # All should have standard fields
        assert "success" in data
        assert "timestamp" in data
```

---

## Monitoring

### Key Metrics
1. **Response format adoption**: % of routes using standard format
2. **Client compatibility**: Errors from breaking changes
3. **Response size**: Overhead of wrapper (should be minimal)
4. **Performance**: No degradation

### Logging
- Log non-standard responses
- Track adoption over time
- Monitor client errors

---

## Configuration

### Environment Variables
```bash
# Enable standard responses (feature flag)
USE_STANDARD_RESPONSES=true

# Deprecation timeline
STANDARD_RESPONSES_DEADLINE=2026-03-01
```

---

## Summary

### Current State
- ✅ BaseAPIRouter has standardized response methods
- ✅ Canvas routes use standard pattern (reference implementation)
- ⚠️ Some routes return direct Pydantic models (inconsistent)

### Recommendations
1. **Document standard patterns** (this document) ✅
2. **Update high-traffic routes** to use standard pattern
3. **Add versioned routes** for backward compatibility
4. **Communicate with API consumers** about changes
5. **Monitor adoption** and client compatibility

### Priority Matrix

| Task | Impact | Effort | Priority |
|------|--------|--------|----------|
| Document patterns | High | Low | ✅ Done |
| Update high-traffic routes | Medium | Medium | High |
| Add versioned routes | High | High | Medium |
| Update low-traffic routes | Low | High | Low |

---

## References

- **BaseAPIRouter**: `core/base_routes.py`
- **Canvas Routes**: `api/canvas_routes.py` (reference implementation)
- **Response Methods**: `success_response()`, `error_response()`, etc.

**Author**: Claude Sonnet 4.5
**Status**: Documented (infrastructure production-ready)
**Next Step**: Update high-traffic routes to use standard pattern
