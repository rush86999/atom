# API Endpoint Standards

This document defines the coding standards and conventions for all API endpoints in the Atom platform.

## Framework Convention

### FastAPI (Standard)
All production APIs **MUST** use FastAPI with `APIRouter`:

```python
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/feature", tags=["feature"])

class FeatureRequest(BaseModel):
    name: str
    value: int

@router.post("/")
async def create_feature(request: FeatureRequest):
    """Create a new feature."""
    try:
        # Implementation
        return {"ok": True, "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### Flask (Legacy)
Flask routes are **DEPRECATED**. All new endpoints must use FastAPI.

Existing Flask routes should be migrated to FastAPI with the following priority:
1. High-traffic endpoints (P0)
2. Authentication and security endpoints (P0)
3. Integration endpoints (P1)
4. Utility endpoints (P2)

---

## Versioning Strategy

### Current Version
- **Current**: `/api/v1/`
- All new endpoints MUST include version prefix

### Breaking Changes
Breaking changes require a new version:
- Rename path: `/api/v1/resource` → `/api/v2/resource`
- Change response structure significantly
- Remove required fields
- Change authentication method

### Backward Compatibility
- Maintain old endpoints for at least one major version
- Add deprecation warnings to old endpoints
- Document migration path in changelog

---

## Endpoint Patterns

### CRUD Operations

**List Resources**
```
GET /api/v1/resources
Query Params: ?limit=100&offset=0&sort=created_at&order=desc
Response: {"ok": true, "data": [...], "total": 150}
```

**Get Single Resource**
```
GET /api/v1/resources/{id}
Response: {"ok": true, "data": {...}}
```

**Create Resource**
```
POST /api/v1/resources
Body: {resource_data}
Response: {"ok": true, "data": {...}, "id": "new-id"}
```

**Update Resource**
```
PUT /api/v1/resources/{id}
Body: {updated_data}
Response: {"ok": true, "data": {...}}
```

**Delete Resource**
```
DELETE /api/v1/resources/{id}
Response: {"ok": true, "deleted": true}
```

**Partial Update**
```
PATCH /api/v1/resources/{id}
Body: {partial_data}
Response: {"ok": true, "data": {...}}
```

### Action Endpoints
```
POST /api/v1/resources/{id}/actions/{action}
Examples:
- POST /api/v1/agents/{id}/actions/execute
- POST /api/v1/canvases/{id}/actions/publish
- POST /api/v1/workflows/{id}/actions/activate
```

### Batch Operations
```
POST /api/v1/resources/batch
Body: {"action": "delete", "ids": ["id1", "id2"]}
Response: {"ok": true, "results": [...]}
```

---

## Response Format Standards

### Success Response
```json
{
  "ok": true,
  "data": {
    "id": "123",
    "name": "Example"
  }
}
```

### Success with Metadata
```json
{
  "ok": true,
  "data": [...],
  "meta": {
    "total": 150,
    "limit": 100,
    "offset": 0,
    "has_more": true
  }
}
```

### Error Response
```json
{
  "ok": false,
  "error": "error_code",
  "message": "Human-readable error message",
  "details": {
    "field": "additional_context"
  }
}
```

### Common Error Codes
- `validation_error` - Invalid input data
- `not_found` - Resource not found
- `unauthorized` - Authentication required
- `forbidden` - Insufficient permissions
- `conflict` - Resource state conflict
- `rate_limit_exceeded` - Too many requests
- `internal_error` - Server error

---

## Authentication & Authorization

### Bearer Token (Standard)
```python
from fastapi import Security, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()

@router.get("/protected")
async def protected_endpoint(
    credentials: HTTPAuthorizationCredentials = Security(security)
):
    token = credentials.credentials
    # Validate token
    user = await validate_token(token)
    return {"ok": true, "data": user}
```

### API Key
```python
@router.get("/api-key-protected")
async def api_key_endpoint(api_key: str = Header(..., alias="X-API-Key")):
    # Validate API key
    if not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    # Process request
```

### Governance Checks (Atom-Specific)
```python
from core.governance_helper import check_agent_permissions

@router.post("/agent-action")
async def agent_action(
    agent_id: str,
    action: str,
    db: Session = Depends(get_db)
):
    # Check agent maturity and permissions
    governance_result = check_agent_permissions(db, agent_id, action)
    if not governance_result["allowed"]:
        raise HTTPException(
            status_code=403,
            detail=f"Agent not permitted: {governance_result['reason']}"
        )
    # Execute action
```

---

## Error Handling

### HTTP Exceptions (FastAPI)
```python
from fastapi import HTTPException

# Standard errors
raise HTTPException(status_code=404, detail="Resource not found")
raise HTTPException(status_code=403, detail="Insufficient permissions")
raise HTTPException(status_code=500, detail="Internal server error")

# With headers
raise HTTPException(
    status_code=401,
    detail="Token expired",
    headers={"WWW-Authenticate": "Bearer"}
)
```

### Custom Exception Handlers
```python
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(CustomException)
async def custom_exception_handler(request: Request, exc: CustomException):
    return JSONResponse(
        status_code=400,
        content={
            "ok": False,
            "error": exc.error_code,
            "message": str(exc)
        }
    )
```

### Service Layer Pattern
```python
# Service layer returns structured dicts
def create_agent_service(db: Session, agent_data: dict) -> dict:
    try:
        agent = Agent(**agent_data)
        db.add(agent)
        db.commit()
        return {"success": True, "data": agent}
    except Exception as e:
        logger.error(f"Failed to create agent: {e}")
        return {"success": False, "error": str(e)}

# API route handles HTTP conversion
@router.post("/agents")
async def create_agent(agent_data: AgentCreate, db: Session = Depends(get_db)):
    result = create_agent_service(db, agent_data.dict())
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"ok": True, "data": result["data"]}
```

---

## Database Operations

### Session Management
```python
from sqlalchemy.orm import Session
from core.database import SessionLocal

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### Query Patterns
```python
# Single record
agent = db.query(Agent).filter(Agent.id == agent_id).first()

# List with pagination
agents = db.query(Agent)\
    .order_by(Agent.created_at.desc())\
    .limit(limit)\
    .offset(offset)\
    .all()

# Count
total = db.query(Agent).filter(Agent.status == "active").count()

# Join with filtering
results = db.query(Agent, Workspace)\
    .join(Workspace, Agent.workspace_id == Workspace.id)\
    .filter(Workspace.is_active == True)\
    .all()
```

### Transaction Management
```python
@router.post("/complex-operation")
async def complex_operation(data: ComplexRequest, db: Session = Depends(get_db)):
    try:
        # Multiple operations in transaction
        agent = Agent(**data.agent_data)
        db.add(agent)

        execution = AgentExecution(**data.execution_data)
        db.add(execution)

        db.commit()
        db.refresh(agent)

        return {"ok": True, "data": agent}
    except Exception as e:
        db.rollback()
        logger.error(f"Transaction failed: {e}")
        raise HTTPException(status_code=500, detail="Operation failed")
```

---

## Validation

### Pydantic Models
```python
from pydantic import BaseModel, Field, validator

class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    maturity: str = Field("STUDENT", regex="^(STUDENT|INTERN|SUPERVISED|AUTONOMOUS)$")
    description: Optional[str] = None

    @validator('name')
    def name_must_not_contain_special_chars(cls, v):
        if not v.replace(' ', '').isalnum():
            raise ValueError('Name must be alphanumeric')
        return v

    class Config:
        schema_extra = {
            "example": {
                "name": "My Agent",
                "maturity": "INTERN",
                "description": "An example agent"
            }
        }
```

### Request Validation
```python
from fastapi import Query, Path

@router.get("/search")
async def search(
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    # Query parameters automatically validated
    results = search_service(q, limit, offset)
    return {"ok": True, "data": results}
```

---

## Documentation

### OpenAPI Schema
FastAPI automatically generates OpenAPI documentation. Enhance it with:

```python
@router.post(
    "/agents",
    summary="Create a new agent",
    description="Creates a new AI agent with the specified configuration",
    response_description="The created agent object",
    responses={
        200: {"description": "Agent created successfully"},
        400: {"description": "Invalid input data"},
        403: {"description": "Insufficient permissions"}
    },
    tags=["agents"]
)
async def create_agent(agent: AgentCreate):
    """
    Create a new AI agent.

    - **name**: Agent name (1-100 characters)
    - **maturity**: Maturity level (STUDENT, INTERN, SUPERVISED, AUTONOMOUS)
    - **description**: Optional description

    Returns the created agent object with system-generated ID.
    """
    return agent
```

### Docstring Format
```python
def complex_function(param1: str, param2: int) -> dict:
    """
    Brief description of the function.

    Longer description explaining what the function does,
    any edge cases, and important behavior notes.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Dictionary with keys:
        - 'success': bool indicating operation outcome
        - 'data': resulting data if successful

    Raises:
        ValueError: If param1 is invalid
        DatabaseError: If database operation fails

    Example:
        >>> complex_function("test", 42)
        {'success': True, 'data': {...}}
    """
    pass
```

---

## Migration from Flask

### Step-by-Step Process

1. **Create FastAPI Router**
```python
# new_routes.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/feature", tags=["feature"])
```

2. **Port Route Handlers**
```python
# Flask (old)
@app.route('/api/feature', methods=['POST'])
def create_feature():
    data = request.get_json()
    return jsonify({"ok": True, "data": data})

# FastAPI (new)
@router.post("/")
async def create_feature(request: Request):
    data = await request.json()
    return {"ok": True, "data": data}
```

3. **Add Deprecation Notice to Old Route**
```python
# Flask (old) - Add deprecation warning
@app.route('/api/feature', methods=['POST'])
def create_feature():
    """
    DEPRECATED: This endpoint is deprecated.
    Use /api/v1/feature instead.
    Will be removed in version 2.0.
    """
    logger.warning("Deprecated endpoint called: /api/feature")
    # ... existing implementation
```

4. **Update Imports**
```python
# main.py
from integrations.feature.routes import router as feature_router

app.include_router(feature_router)
```

5. **Test Both Versions**
- Verify old routes still work
- Test new routes thoroughly
- Compare responses match

6. **Communicate Deprecation**
- Update API documentation
- Add deprecation timeline to changelog
- Notify API consumers

7. **Remove Old Routes** (After one major version)
- Remove Flask Blueprint
- Clean up imports
- Update tests

---

## WebSocket Standards

### Connection Management
```python
from fastapi import WebSocket, WebSocketDisconnect

@router.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            # Process data
            await websocket.send_json({"ok": True, "data": response})
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close(code=1011, reason=str(e))
```

### Heartbeat Pattern
```python
@router.websocket("/ws/agent-stream")
async def agent_stream(websocket: WebSocket, agent_id: str):
    await websocket.accept()
    last_ping = time.time()

    try:
        while True:
            # Check for timeout
            if time.time() - last_ping > 30:
                await websocket.close(code=1000, reason="Timeout")
                break

            # Send heartbeat
            await websocket.send_json({"type": "ping", "timestamp": time.time()})

            # Wait for pong
            try:
                message = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=5.0
                )
                if message == "pong":
                    last_ping = time.time()
            except asyncio.TimeoutError:
                continue

            # Process actual data
            # ... streaming logic

    except WebSocketDisconnect:
        logger.info(f"Agent {agent_id} disconnected")
```

---

## Performance Guidelines

### Response Time Targets
- Simple CRUD: < 100ms
- Complex queries: < 500ms
- Streaming: First token < 200ms
- File uploads: Progress updates every 1s

### Caching Strategy
```python
from fastapi import Response
from core.governance_cache import GovernanceCache

cache = GovernanceCache()

@router.get("/agents/{agent_id}")
async def get_agent(agent_id: str, response: Response):
    # Check cache
    cached = cache.get(f"agent:{agent_id}")
    if cached:
        response.headers["X-Cache"] = "HIT"
        return {"ok": True, "data": cached}

    # Fetch from database
    agent = db.query(Agent).filter(Agent.id == agent_id).first()

    # Cache result
    cache.set(f"agent:{agent_id}", agent, ttl=300)
    response.headers["X-Cache"] = "MISS"

    return {"ok": True, "data": agent}
```

### Pagination Best Practices
```python
@router.get("/agents")
async def list_agents(
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    sort: str = Query("created_at", description="Field to sort by"),
    order: str = Query("desc", regex="^(asc|desc)$")
):
    query = db.query(Agent)

    # Apply sorting
    sort_field = getattr(Agent, sort, None)
    if sort_field:
        order_fn = asc if order == "asc" else desc
        query = query.order_by(order_fn(sort_field))

    # Get total count before pagination
    total = query.count()

    # Apply pagination
    results = query.limit(limit).offset(offset).all()

    return {
        "ok": True,
        "data": results,
        "meta": {
            "total": total,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total
        }
    }
```

---

## Security Standards

### Input Sanitization
```python
import html
from markdown import markdown

def sanitize_markdown(text: str) -> str:
    """Sanitize markdown input to prevent XSS."""
    # Escape HTML
    clean = html.escape(text)
    # Parse markdown safely
    return markdown(clean)
```

### Rate Limiting
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@router.post("/sensitive-operation")
@limiter.limit("10/minute")
async def sensitive_operation(request: Request):
    # Rate limited to 10 requests per minute per IP
    pass
```

### CORS Configuration
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://atom.example.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Testing Standards

### Unit Tests
```python
import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_create_agent():
    response = client.post(
        "/api/v1/agents",
        json={"name": "Test Agent", "maturity": "INTERN"}
    )
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert "id" in response.json()["data"]

def test_create_agent_invalid_maturity():
    response = client.post(
        "/api/v1/agents",
        json={"name": "Test", "maturity": "INVALID"}
    )
    assert response.status_code == 422  # Validation error
```

### Integration Tests
```python
@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()

def test_agent_creation_integration(db_session):
    agent = Agent(name="Test", maturity="INTERN")
    db_session.add(agent)
    db_session.commit()

    result = client.get(f"/api/v1/agents/{agent.id}")
    assert result.status_code == 200
    assert result.json()["data"]["name"] == "Test"
```

---

## Checklist for New Endpoints

Before merging a new endpoint, verify:

- [ ] Uses FastAPI with `APIRouter`
- [ ] Has `/api/v1/` prefix
- [ ] Returns consistent response format (`{"ok": bool, "data": ...}`)
- [ ] Includes error handling with appropriate HTTP status codes
- [ ] Has Pydantic models for request/response validation
- [ ] Includes OpenAPI documentation (summary, description, tags)
- [ ] Has unit tests with >80% coverage
- [ ] Handles database transactions properly (commit/rollback)
- [ ] Logs errors appropriately
- [ ] Includes governance checks if applicable
- [ ] Rate limited if resource-intensive
- [ ] Returns appropriate CORS headers
- [ ] Documented in API documentation

---

## Common Patterns

### Streaming Response
```python
from fastapi.responses import StreamingResponse

async def generate_stream(agent_id: str):
    async for chunk in stream_agent_response(agent_id):
        yield f"data: {chunk}\n\n"

@router.get("/agents/{id}/stream")
async def stream_agent(id: str):
    return StreamingResponse(
        generate_stream(id),
        media_type="text/event-stream"
    )
```

### File Upload
```python
from fastapi import UploadFile, File

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    contents = await file.read()
    # Process file
    return {"ok": True, "filename": file.filename}
```

### Batch Operations
```python
@router.post("/agents/batch")
async def batch_create_agents(agents: List[AgentCreate]):
    results = []
    for agent_data in agents:
        result = create_agent_service(db, agent_data.dict())
        results.append(result)

    return {
        "ok": True,
        "data": results,
        "summary": {
            "total": len(agents),
            "successful": sum(1 for r in results if r["success"]),
            "failed": sum(1 for r in results if not r["success"])
        }
    }
```

---

*Last Updated: February 3, 2026*
