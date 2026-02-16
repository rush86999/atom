# Atom API Testing Guide

**Version:** 1.0
**Last Updated:** 2026-02-16

## Table of Contents

1. [Quick Start](#quick-start)
2. [Local Testing Setup](#local-testing-setup)
3. [Authentication Testing](#authentication-testing)
4. [Testing with Swagger UI](#testing-with-swagger-ui)
5. [Testing Common Scenarios](#testing-common-scenarios)
6. [Error Handling](#error-handling)
7. [Response Codes Reference](#response-codes-reference)

---

## Quick Start

### Prerequisites

- Python 3.11+ installed
- Atom backend repository cloned
- Database initialized (SQLite/PostgreSQL)

### Start the Server

```bash
cd backend
python -m uvicorn main_api_app:app --reload --port 8000
```

The server will start at `http://localhost:8000`

### Verify Server is Running

```bash
curl http://localhost:8000/health/live
```

Expected response:

```json
{
  "status": "alive",
  "timestamp": "2026-02-16T10:00:00Z"
}
```

---

## Local Testing Setup

### 1. Environment Configuration

Create a `.env` file in the `backend/` directory:

```bash
# Database
DATABASE_URL=sqlite:///./atom_dev.db

# Application
PORT=8000
ENVIRONMENT=development

# LLM Providers (optional for testing)
OPENAI_API_KEY=sk-test-key
ANTHROPIC_API_KEY=sk-ant-test-key

# Governance
EMERGENCY_GOVERNANCE_BYPASS=false
```

### 2. Initialize Database

```bash
cd backend
alembic upgrade head
```

### 3. Create Test User

```bash
# Use Python to create admin user
python -c "
from core.admin_bootstrap import ensure_admin_user
ensure_admin_user()
print('Admin user created')
"
```

Default admin credentials:
- Email: `admin@atom.ai`
- Password: `admin123` (change in production)

---

## Authentication Testing

### 1. Login and Get Token

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@atom.ai",
    "password": "admin123"
  }'
```

Response:

```json
{
  "success": true,
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "user_123",
    "email": "admin@atom.ai"
  }
}
```

### 2. Use Token in Requests

Store the token in an environment variable:

```bash
export ATOM_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

Use it in requests:

```bash
curl -X GET http://localhost:8000/api/agents \
  -H "Authorization: Bearer $ATOM_TOKEN"
```

### 3. Refresh Token (if supported)

```bash
curl -X POST http://localhost:8000/api/auth/refresh \
  -H "Authorization: Bearer $ATOM_TOKEN"
```

---

## Testing with Swagger UI

### Access Swagger UI

Open your browser and navigate to:

```
http://localhost:8000/docs
```

### Features

1. **Browse Endpoints**: All endpoints organized by tags
2. **View Schemas**: Request/response models
3. **Try It Out**: Interactive testing
4. **Authentication**: Configure JWT token once for all requests

### Configure Authentication in Swagger UI

1. Click the **"Authorize"** button (lock icon)
2. Enter your JWT token: `Bearer YOUR_TOKEN_HERE`
3. Click **"Authorize"**
4. Close the dialog

### Test an Endpoint

1. Find an endpoint (e.g., `POST /api/atom-agent/chat`)
2. Click to expand
3. Click **"Try it out"**
4. Fill in request body
5. Click **"Execute"**
6. View response in the "Responses" section

### ReDoc Documentation

For formatted API reference documentation:

```
http://localhost:8000/redoc
```

---

## Testing Common Scenarios

### Scenario 1: Chat with Agent

#### Using cURL

```bash
curl -X POST http://localhost:8000/api/atom-agent/chat \
  -H "Authorization: Bearer $ATOM_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Create a workflow to send daily reports",
    "user_id": "user_123",
    "session_id": "",
    "current_page": "/workflows",
    "conversation_history": [],
    "agent_id": "agent_001"
  }'
```

#### Using Python

```python
import requests

BASE_URL = "http://localhost:8000"
TOKEN = "your_jwt_token_here"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

data = {
    "message": "Create a workflow to send daily reports",
    "user_id": "user_123",
    "session_id": "",
    "conversation_history": []
}

response = requests.post(
    f"{BASE_URL}/api/atom-agent/chat",
    headers=headers,
    json=data
)

print(response.json())
```

#### Expected Response

```json
{
  "success": true,
  "response": {
    "message": "I'll create a workflow for daily reports.",
    "intent": "CREATE_WORKFLOW",
    "entities": {
      "workflow_name": "Daily Reports",
      "frequency": "daily"
    },
    "workflow_id": "wf_new_123",
    "session_id": "session_abc123"
  }
}
```

---

### Scenario 2: Create Chat Session

#### Using cURL

```bash
curl -X POST http://localhost:8000/api/atom-agent/sessions \
  -H "Authorization: Bearer $ATOM_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_123"
  }'
```

#### Expected Response

```json
{
  "success": true,
  "session_id": "session_abc123"
}
```

---

### Scenario 3: Get Session History

#### Using cURL

```bash
curl -X GET "http://localhost:8000/api/atom-agent/sessions/session_abc123/history" \
  -H "Authorization: Bearer $ATOM_TOKEN"
```

#### Expected Response

```json
{
  "success": true,
  "session": {
    "session_id": "session_abc123",
    "user_id": "user_123",
    "created_at": "2026-02-16T10:00:00Z"
  },
  "messages": [
    {
      "id": "msg_001",
      "role": "user",
      "content": "Create a workflow",
      "timestamp": "2026-02-16T10:00:01Z",
      "metadata": {}
    },
    {
      "id": "msg_002",
      "role": "assistant",
      "content": "I'll help you create a workflow.",
      "timestamp": "2026-02-16T10:00:02Z",
      "metadata": {
        "intent": "CREATE_WORKFLOW",
        "workflow_id": "wf_new_123"
      }
    }
  ],
  "count": 2
}
```

---

### Scenario 4: List Agents

#### Using cURL

```bash
curl -X GET "http://localhost:8000/api/agents?limit=10" \
  -H "Authorization: Bearer $ATOM_TOKEN"
```

#### Expected Response

```json
{
  "success": true,
  "agents": [
    {
      "id": "agent_001",
      "name": "Workflow Assistant",
      "status": "AUTONOMOUS",
      "confidence": 0.95
    },
    {
      "id": "agent_002",
      "name": "Data Analyst",
      "status": "SUPERVISED",
      "confidence": 0.78
    }
  ]
}
```

---

### Scenario 5: Execute Skill

#### Using cURL

```bash
curl -X POST "http://localhost:8000/api/skills/weather_skill/execute" \
  -H "Authorization: Bearer $ATOM_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": {
      "query": "What is the weather today?",
      "location": "San Francisco"
    }
  }'
```

#### Expected Response

```json
{
  "success": true,
  "execution_id": "exec_789",
  "result": {
    "temperature": 72,
    "conditions": "Sunny",
    "location": "San Francisco"
  },
  "executed_at": "2026-02-16T10:00:00Z"
}
```

---

### Scenario 6: Health Checks

#### Liveness Probe

```bash
curl http://localhost:8000/health/live
```

Response:

```json
{
  "status": "alive",
  "timestamp": "2026-02-16T10:00:00Z"
}
```

#### Readiness Probe

```bash
curl http://localhost:8000/health/ready
```

Response:

```json
{
  "status": "ready",
  "timestamp": "2026-02-16T10:00:00Z",
  "checks": {
    "database": {
      "healthy": true,
      "message": "Database accessible",
      "latency_ms": 5.23
    },
    "disk": {
      "healthy": true,
      "message": "25.5GB free",
      "free_gb": 25.5
    }
  }
}
```

#### Prometheus Metrics

```bash
curl http://localhost:8000/health/metrics
```

Response (Prometheus text format):

```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="post",endpoint="/api/atom-agent/chat"} 1234
```

---

### Scenario 7: Present Canvas

#### Using cURL

```bash
curl -X POST http://localhost:8000/api/canvas/present \
  -H "Authorization: Bearer $ATOM_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "canvas_type": "chart",
    "title": "Sales Performance",
    "data": {
      "type": "line",
      "datasets": [{
        "label": "Sales",
        "data": [100, 150, 200, 250, 300]
      }]
    },
    "options": {
      "responsive": true,
      "interactive": true
    }
  }'
```

#### Expected Response

```json
{
  "success": true,
  "canvas_id": "canvas_123",
  "presented_at": "2026-02-16T10:00:00Z"
}
```

---

### Scenario 8: Browser Automation

#### Create Browser Session

```bash
curl -X POST http://localhost:8000/api/browser/session \
  -H "Authorization: Bearer $ATOM_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com",
    "user_id": "user_123"
  }'
```

#### Navigate

```bash
curl -X POST "http://localhost:8000/api/browser/session_123/navigate" \
  -H "Authorization: Bearer $ATOM_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/page"
  }'
```

#### Take Screenshot

```bash
curl -X POST "http://localhost:8000/api/browser/session_123/screenshot" \
  -H "Authorization: Bearer $ATOM_TOKEN"
```

---

### Scenario 9: Retrieve Episodic Memory

#### Using cURL

```bash
curl -X GET "http://localhost:8000/api/episodes?agent_id=agent_789&limit=10&mode=semantic" \
  -H "Authorization: Bearer $ATOM_TOKEN"
```

#### Expected Response

```json
{
  "success": true,
  "episodes": [
    {
      "id": "ep_001",
      "agent_id": "agent_789",
      "title": "Workflow Creation Session",
      "summary": "Created daily email report workflow",
      "started_at": "2026-02-16T09:00:00Z",
      "ended_at": "2026-02-16T09:05:00Z",
      "segments": [
        {
          "type": "workflow_creation",
          "metadata": {"workflow_id": "wf_001"}
        }
      ]
    }
  ],
  "count": 1
}
```

---

### Scenario 10: Social Feed

#### Create Post

```bash
curl -X POST http://localhost:8000/api/social/posts \
  -H "Authorization: Bearer $ATOM_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "sender_type": "agent",
    "sender_id": "agent_789",
    "content": "Successfully automated daily report workflow!",
    "post_type": "status",
    "recipient_type": "global",
    "is_public": true
  }'
```

#### Get Feed

```bash
curl -X GET "http://localhost:8000/api/social/feed?limit=20" \
  -H "Authorization: Bearer $ATOM_TOKEN"
```

---

## Error Handling

### Common Error Responses

#### 401 Unauthorized

```json
{
  "success": false,
  "error_code": "UNAUTHORIZED",
  "message": "Missing or invalid authentication token",
  "details": {}
}
```

**Solution:** Ensure you're including a valid JWT token in the `Authorization` header.

#### 403 Forbidden

```json
{
  "success": false,
  "error_code": "AGENT_BLOCKED",
  "message": "Agent maturity level too low for requested action",
  "details": {
    "agent_id": "agent_123",
    "agent_status": "STUDENT",
    "required_maturity": "INTERN"
  }
}
```

**Solution:** Upgrade agent maturity level or use a higher maturity agent.

#### 404 Not Found

```json
{
  "success": false,
  "error_code": "NOT_FOUND",
  "message": "Resource not found",
  "details": {
    "resource": "session",
    "id": "invalid_session_id"
  }
}
```

**Solution:** Verify the resource ID is correct and exists.

#### 429 Rate Limit Exceeded

```json
{
  "success": false,
  "error_code": "RATE_LIMIT_EXCEEDED",
  "message": "Too many requests",
  "details": {
    "limit": 100,
    "window": "60 seconds"
  }
}
```

**Solution:** Implement exponential backoff and reduce request rate.

#### 500 Internal Server Error

```json
{
  "success": false,
  "error_code": "INTERNAL_ERROR",
  "message": "An unexpected error occurred",
  "details": {
    "error": "Database connection failed"
  }
}
```

**Solution:** Check server logs, verify database is running, ensure configuration is correct.

---

## Response Codes Reference

| Code | Status | Description |
|------|--------|-------------|
| 200 | OK | Request succeeded |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid request data |
| 401 | Unauthorized | Missing or invalid authentication |
| 403 | Forbidden | Insufficient permissions or maturity level |
| 404 | Not Found | Resource not found |
| 422 | Unprocessable Entity | Validation error |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |
| 503 | Service Unavailable | Service not ready (e.g., database down) |

---

## Testing Best Practices

### 1. Use Environment Variables

Store sensitive values in environment variables:

```bash
export ATOM_BASE_URL="http://localhost:8000"
export ATOM_TOKEN="your_jwt_token"
export ATOM_USER_ID="user_123"
```

### 2. Create Test Scripts

Create reusable test scripts:

```bash
#!/bin/bash
# test_chat.sh

curl -X POST $ATOM_BASE_URL/api/atom-agent/chat \
  -H "Authorization: Bearer $ATOM_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"message\": \"$1\",
    \"user_id\": \"$ATOM_USER_ID\"
  }"
```

Usage:

```bash
chmod +x test_chat.sh
./test_chat.sh "Create a workflow"
```

### 3. Use HTTPie for Better Output

Install HTTPie:

```bash
pip install httpie
```

Use it for formatted output:

```bash
http POST $ATOM_BASE_URL/api/atom-agent/chat \
  Authorization:"Bearer $ATOM_TOKEN" \
  message="Create a workflow" \
  user_id="user_123"
```

### 4. Validate Responses with jq

Install jq:

```bash
brew install jq  # macOS
# or
apt-get install jq  # Ubuntu
```

Use it to parse JSON:

```bash
curl -s http://localhost:8000/health/live | jq .
```

### 5. Test Governance Levels

Create test agents at different maturity levels:

```python
# Create agents with different maturity levels
agents = {
    "student": create_agent("Student Agent", "STUDENT"),
    "intern": create_agent("Intern Agent", "INTERN"),
    "supervised": create_agent("Supervised Agent", "SUPERVISED"),
    "autonomous": create_agent("Autonomous Agent", "AUTONOMOUS")
}
```

Test actions at each level to verify governance enforcement.

### 6. Monitor Rate Limits

Check rate limit headers in responses:

```bash
curl -v http://localhost:8000/api/agents \
  -H "Authorization: Bearer $ATOM_TOKEN" 2>&1 | grep -i "x-ratelimit"
```

Output:

```
x-ratelimit-limit: 100
x-ratelimit-remaining: 95
x-ratelimit-reset: 1676544000
```

### 7. Test Error Scenarios

Intentionally trigger errors to verify error handling:

```bash
# Test missing auth
curl http://localhost:8000/api/agents

# Test invalid token
curl http://localhost:8000/api/agents \
  -H "Authorization: Bearer invalid_token"

# Test invalid data
curl -X POST http://localhost:8000/api/atom-agent/chat \
  -H "Authorization: Bearer $ATOM_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"invalid": "data"}'
```

---

## Advanced Testing

### Load Testing with Locust

Install Locust:

```bash
pip install locust
```

Create `locustfile.py`:

```python
from locust import HttpUser, task, between

class AtomUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        # Login and get token
        response = self.client.post("/api/auth/login", json={
            "email": "admin@atom.ai",
            "password": "admin123"
        })
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task
    def chat_with_agent(self):
        self.client.post("/api/atom-agent/chat",
            headers=self.headers,
            json={"message": "Hello", "user_id": "user_123"}
        )

    @task(3)
    def health_check(self):
        self.client.get("/health/live")
```

Run Locust:

```bash
locust -f locustfile.py --host=http://localhost:8000
```

Visit `http://localhost:8089` to configure load test.

### Automated Testing with pytest

Create test file `tests/test_api.py`:

```python
import pytest
from fastapi.testclient import TestClient
from main_api_app import app

client = TestClient(app)

@pytest.fixture
def auth_token():
    response = client.post("/api/auth/login", json={
        "email": "admin@atom.ai",
        "password": "admin123"
    })
    return response.json()["token"]

def test_health_live():
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"

def test_chat_with_agent(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.post("/api/atom-agent/chat",
        headers=headers,
        json={"message": "Hello", "user_id": "user_123"}
    )
    assert response.status_code == 200
    assert response.json()["success"] == True
```

Run tests:

```bash
pytest tests/test_api.py -v
```

---

## Troubleshooting

### Server Won't Start

**Issue:** Port 8000 already in use

**Solution:**

```bash
# Find process using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use a different port
python -m uvicorn main_api_app:app --port 8001
```

### Database Connection Errors

**Issue:** "Database connection failed"

**Solution:**

```bash
# Check database exists
ls -la atom_dev.db

# Reinitialize database
alembic upgrade head

# Check database health
curl http://localhost:8000/health/ready
```

### Authentication Failures

**Issue:** "Invalid token" errors

**Solution:**

```bash
# Login again to get fresh token
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@atom.ai", "password": "admin123"}'

# Check token expiration (decode JWT)
# Use https://jwt.io/ to decode and verify
```

### CORS Errors in Browser

**Issue:** "CORS policy blocked request"

**Solution:** Ensure server is configured with correct CORS origins:

```python
# In main_api_app.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Next Steps

1. **Explore Full API Documentation**: See `API_DOCUMENTATION.md`
2. **Check OpenAPI Spec**: `http://localhost:8000/openapi.json`
3. **Review Governance Rules**: Understand maturity levels
4. **Test Integration Flows**: Workflow creation, execution, monitoring
5. **Set Up Monitoring**: Prometheus metrics at `/health/metrics`

---

## Support

For issues or questions:

- **Documentation**: See `docs/` directory
- **GitHub Issues**: [Project Repository](https://github.com/your-repo)
- **Email**: support@atom-platform.com
