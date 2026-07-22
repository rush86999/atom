# Basic API Usage

Real curl recipes for the most common Atom operations. Copy-paste and run.

## Prerequisites

- Atom backend running on `http://localhost:8001`
- Swagger UI available at `http://localhost:8001/docs`

## Authentication

### Register a new user

```bash
curl -X POST http://localhost:8001/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "MySecurePass123!",
    "first_name": "Test",
    "last_name": "User"
  }'
```

### Login and get a token

```bash
curl -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "user@example.com",
    "password": "MySecurePass123!"
  }'
```

Response:
```json
{
  "access_token": "eyJhbGci...",
  "refresh_token": "eyJhbGci...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

Save the token:
```bash
export TOKEN="eyJhbGci..."
```

### Use the token in all requests

```bash
curl -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     http://localhost:8001/api/auth/me
```

## Chat

### Send a message

```bash
curl -X POST http://localhost:8001/api/chat/message \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What can you help me with?",
    "user_id": "default_user",
    "session_id": "new",
    "context": {}
  }'
```

Response includes `model` and `provider` (which model answered):
```json
{
  "success": true,
  "message": "I can help you with...",
  "session_id": "abc-123",
  "model": "gpt-4o",
  "provider": "openai"
}
```

### List chat sessions

```bash
curl -H "Authorization: Bearer $TOKEN" \
     "http://localhost:8001/api/chat/sessions?user_id=default_user"
```

### Load chat history

```bash
curl -H "Authorization: Bearer $TOKEN" \
     "http://localhost:8001/api/chat/history/SESSION_ID?user_id=default_user"
```

## Canvas CRUD

### List all canvases

```bash
curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8001/api/canvas/
```

### Read a canvas by ID

```bash
curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8001/api/canvas/CANVAS_ID
```

### Update canvas content

```bash
curl -X PUT http://localhost:8001/api/canvas/CANVAS_ID \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "Updated content here"}'
```

### Delete a canvas

```bash
curl -X DELETE http://localhost:8080/api/canvas/CANVAS_ID \
  -H "Authorization: Bearer $TOKEN"
```

### Get version history

```bash
curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8001/api/canvas/CANVAS_ID/history
```

## Office Automation

### Write an Excel cell (with formula evaluation)

```bash
curl -X POST http://localhost:8001/api/v1/office/excel \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "data/budget.xlsx",
    "cell_path": "/Sheet1/A1",
    "value": "=SUM(10, 20, 30)",
    "is_formula": true
  }'
```

Response includes the **computed value**:
```json
{
  "success": true,
  "value": 60,
  "formula": "=SUM(10, 20, 30)"
}
```

### Read an Excel range

```bash
curl "http://localhost:8001/api/v1/office/excel?file_path=data/budget.xlsx&cell_path=/Sheet1/A1:A10"
```

### Get a formula result (forces recalculation)

```bash
curl "http://localhost:8001/api/v1/office/excel/formula-result?file_path=data/budget.xlsx&cell_path=/Sheet1/A4"
```

## Learning Router

### Submit feedback (thumbs up/down)

```bash
curl -X POST http://localhost:8001/api/chat/feedback \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message_id": "msg-123",
    "feedback": "thumbs_down",
    "comment": "Response was incorrect",
    "model": "gpt-4o"
  }'
```

### Check routing statistics

```bash
curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8001/api/chat/routing-stats
```

Response:
```json
{
  "enabled": true,
  "stats": {
    "feedback_samples": 42,
    "model_success_rates": {
      "gpt-4o": 0.92,
      "deepseek-chat": 0.85
    }
  }
}
```

## Local Models

### Register an Ollama provider

```bash
curl -X POST http://localhost:8001/api/local-models \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Ollama",
    "provider_type": "ollama",
    "base_url": "http://localhost:11434/v1"
  }'
```

### Discover available models

```bash
curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8001/api/local-models/PROVIDER_ID/models
```

### Set model capabilities

```bash
curl -X POST http://localhost:8001/api/local-models/PROVIDER_ID/capabilities \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "model_id": "llama3:8b",
    "supports_tools": true,
    "supports_vision": false,
    "supports_reasoning": true,
    "quality_score": 0.7,
    "speed_score": 0.8,
    "context_window": 8192
  }'
```

## Federation (Zero-Trust)

### Create a DID

```bash
curl -X POST http://localhost:8001/api/federation/dids \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "entity_type": "agent",
    "entity_id": "my_agent_001"
  }'
```

### Issue a verifiable credential

```bash
curl -X POST http://localhost:8001/api/federation/credentials \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "issuer_did": "did:atom:agent:my_agent_001",
    "credential_type": "AgentIdentityCredential",
    "subject_did": "did:atom:agent:my_agent_001",
    "claims": {"name": "Test Agent", "tier": "supervised"}
  }'
```

### Verify a request

```bash
curl -X POST http://localhost:8001/api/federation/verify \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "method": "GET",
    "path": "/api/resource",
    "action": "read",
    "resource_type": "generic"
  }'
```

## Health

### Liveness check

```bash
curl http://localhost:8001/health/live
```

### Readiness check

```bash
curl http://localhost:8001/health/ready
```

### Database check

```bash
curl http://localhost:8001/health/db
```
