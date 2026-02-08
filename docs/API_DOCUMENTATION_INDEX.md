# API Documentation Index

**Last Updated**: February 4, 2026

Comprehensive index of all API endpoints in the Atom platform.

---

## API Base URL

```
Development: http://localhost:8000
Production: https://api.atom-platform.com
```

---

## API Categories

### Core APIs
- [Agent APIs](#agent-apis) - Agent management, execution, and governance
- [Canvas APIs](#canvas-apis) - Canvas presentations and forms
- [Workflow APIs](#workflow-apis) - Workflow execution and management
- [Chat APIs](#chat-apis) - Chat sessions and streaming responses

### Integration APIs
- [OAuth APIs](#oauth-apis) - OAuth authentication for third-party services
- [Integration Health APIs](#integration-health-apis) - Health checks for integrations
- [Browser Automation APIs](#browser-automation-apis) - Browser automation via CDP
- [Device Capabilities APIs](#device-capabilities-apis) - Camera, screen recording, location

### Admin APIs
- [Admin Routes](#admin-routes) - Administrative operations
- [System Health APIs](#system-health-apis) - System health monitoring
- [Monitoring APIs](#monitoring-apis) - Performance monitoring

### Feature APIs
- [Feedback APIs](#feedback-apis) - User feedback and analytics
- [Deep Link APIs](#deep-link-apis) - Deep linking for external apps
- [Custom Component APIs](#custom-component-apis) - Custom canvas components

---

## Agent APIs

### Agent Management

#### List Agents
```http
GET /api/agents
```

**Response**:
```json
{
  "ok": true,
  "agents": [
    {
      "id": "agent_123",
      "name": "Research Agent",
      "description": "Conducts research tasks",
      "maturity_level": "AUTONOMOUS",
      "confidence_score": 0.95,
      "status": "active"
    }
  ]
}
```

#### Get Agent
```http
GET /api/agents/{agent_id}
```

#### Create Agent
```http
POST /api/agents
```

**Request Body**:
```json
{
  "name": "New Agent",
  "description": "Agent description",
  "maturity_level": "INTERN",
  "capabilities": ["streaming", "form_presentation"]
}
```

#### Update Agent
```http
PUT /api/agents/{agent_id}
```

#### Delete Agent
```http
DELETE /api/agents/{agent_id}
```

---

### Agent Execution

#### Execute Agent
```http
POST /api/agents/{agent_id}/execute
```

**Request Body**:
```json
{
  "input": "User request or task",
  "context": {
    "user_id": "user_123",
    "session_id": "session_456"
  }
}
```

**Response**:
```json
{
  "ok": true,
  "execution_id": "exec_789",
  "status": "running",
  "agent_id": "agent_123",
  "started_at": "2026-02-04T12:00:00Z"
}
```

#### Get Execution Status
```http
GET /api/agents/executions/{execution_id}
```

#### List Agent Executions
```http
GET /api/agents/{agent_id}/executions
```

---

### Agent Governance

#### Get Agent Maturity
```http
GET /api/agents/{agent_id}/maturity
```

**Response**:
```json
{
  "ok": true,
  "agent_id": "agent_123",
  "maturity_level": "SUPERVISED",
  "confidence_score": 0.85,
  "can_execute_triggers": true,
  "can_stream": true,
  "can_present_forms": true
}
```

#### Update Agent Maturity
```http
PUT /api/agents/{agent_id}/maturity
```

#### Check Agent Permissions
```http
POST /api/agents/{agent_id}/check-permissions
```

**Request Body**:
```json
{
  "action": "browser_automation",
  "complexity": 3
}
```

**Response**:
```json
{
  "ok": true,
  "allowed": true,
  "reason": "Agent maturity level allows this action",
  "requirements": ["SUPERVISED", "human_approval"]
}
```

---

## Canvas APIs

### Canvas Management

#### Create Canvas
```http
POST /api/canvas
```

**Request Body**:
```json
{
  "title": "Sales Report",
  "description": "Q1 2026 Sales Dashboard",
  "layout": "grid",
  "components": [
    {
      "type": "chart",
      "chart_type": "bar",
      "data": {...}
    }
  ]
}
```

#### Get Canvas
```http
GET /api/canvas/{canvas_id}
```

#### List Canvases
```http
GET /api/canvas
```

#### Update Canvas
```http
PUT /api/canvas/{canvas_id}
```

#### Delete Canvas
```http
DELETE /api/canvas/{canvas_id}
```

---

### Canvas Components

#### Add Component
```http
POST /api/canvas/{canvas_id}/components
```

**Request Body**:
```json
{
  "type": "form",
  "title": "User Feedback",
  "fields": [
    {
      "name": "rating",
      "type": "rating",
      "label": "Rate your experience",
      "required": true
    }
  ]
}
```

#### Update Component
```http
PUT /api/canvas/{canvas_id}/components/{component_id}
```

#### Delete Component
```http
DELETE /api/canvas/{canvas_id}/components/{component_id}
```

---

## Workflow APIs

### Workflow Execution

#### Create Workflow Execution
```http
POST /api/workflows/execute
```

**Request Body**:
```json
{
  "workflow_id": "workflow_123",
  "input_data": {
    "param1": "value1",
    "param2": "value2"
  }
}
```

#### Get Execution State
```http
GET /api/workflows/executions/{execution_id}
```

**Response**:
```json
{
  "ok": true,
  "execution_id": "exec_456",
  "workflow_id": "workflow_123",
  "status": "running",
  "current_step": "step_2",
  "input_data": {...},
  "output_data": {...},
  "created_at": "2026-02-04T12:00:00Z",
  "updated_at": "2026-02-04T12:05:00Z"
}
```

#### Update Execution Status
```http
PUT /api/workflows/executions/{execution_id}/status
```

**Request Body**:
```json
{
  "status": "completed",
  "output": {...}
}
```

---

## Chat APIs

### Chat Sessions

#### Create Chat Session
```http
POST /api/chat/sessions
```

**Request Body**:
```json
{
  "user_id": "user_123",
  "agent_id": "agent_456",
  "title": "Customer Support Chat"
}
```

#### Get Chat Session
```http
GET /api/chat/sessions/{session_id}
```

#### List Chat Sessions
```http
GET /api/chat/sessions
```

#### Delete Chat Session
```http
DELETE /api/chat/sessions/{session_id}
```

---

### Chat Messages

#### Send Message
```http
POST /api/chat/sessions/{session_id}/messages
```

**Request Body**:
```json
{
  "content": "Hello, I need help with...",
  "role": "user"
}
```

**Response** (Streaming):
```
data: {"type": "token", "content": "Hello"}
data: {"type": "token", "content": "! I"}
data: {"type": "token", "content": " can"}
data: {"type": "done", "full_response": "Hello! I can help you with..."}
```

#### Get Messages
```http
GET /api/chat/sessions/{session_id}/messages
```

---

## OAuth APIs

### OAuth 2.0 Services

#### Initiate OAuth Flow
```http
GET /api/auth/{service}/initiate?user_id={user_id}
```

**Services**: `google`, `notion`, `github`, `asana`, `dropbox`

**Response**:
```json
{
  "ok": true,
  "service": "notion",
  "auth_url": "https://api.notion.com/v1/oauth/authorize?...",
  "state": "notion_oauth_user_123"
}
```

#### OAuth Callback (GET)
```http
GET /api/auth/{service}/callback?code={code}&state={state}
```

**Services**: `google`, `notion`, `github`

#### OAuth Callback (POST)
```http
POST /api/auth/{service}/callback
```

**Services**: `asana`, `dropbox`

**Request Body**:
```json
{
  "code": "...",
  "state": "..."
}
```

#### Check OAuth Status
```http
GET /api/auth/{service}/status?user_id={user_id}
```

**Response**:
```json
{
  "ok": true,
  "service": "notion",
  "configured": true,
  "authorized": true,
  "message": "Notion OAuth is configured and authorized"
}
```

#### Refresh Token
```http
POST /api/auth/{service}/refresh
```

**Request Body**:
```json
{
  "refresh_token": "..."
}
```

---

### OAuth 1.0a Services

#### Initiate OAuth Flow
```http
GET /api/auth/trello/initiate?user_id={user_id}
```

#### OAuth Callback
```http
GET /api/auth/trello/callback?oauth_token={token}&oauth_verifier={verifier}
```

---

### OAuth Health

#### Check All OAuth Services
```http
GET /api/auth/health
```

**Response**:
```json
{
  "ok": true,
  "overall_status": "healthy",
  "services": {
    "google": {
      "configured": true,
      "status": "ok",
      "message": "Google OAuth is configured"
    },
    "notion": {
      "configured": true,
      "status": "ok",
      "message": "Notion OAuth is configured"
    }
  },
  "total_services": 6,
  "configured_services": 6,
  "unconfigured_services": 0
}
```

---

## Integration Health APIs

### Check Service Health

#### Single Service Health
```http
GET /api/{service}/health
```

**Services**: `zoom`, `notion`, `trello`, `stripe`, `quickbooks`, `github`, `salesforce`, `googledrive`, `dropbox`, `slack`

**Response**:
```json
{
  "ok": true,
  "status": "healthy",
  "service": "zoom",
  "timestamp": "2026-02-04T12:00:00Z",
  "is_mock": false,
  "configured": true,
  "message": "Zoom integration is operational",
  "checks": {
    "configuration": {
      "status": "pass",
      "required_env_vars": ["ZOOM_API_KEY", "ZOOM_API_SECRET"],
      "present_env_vars": ["ZOOM_API_KEY", "ZOOM_API_SECRET"],
      "missing_env_vars": []
    },
    "api_access": {
      "status": "pass",
      "message": "Successfully connected to Zoom API"
    }
  }
}
```

#### All Services Health
```http
GET /api/integrations/health
```

#### Configuration Status
```http
GET /api/integrations/config
```

---

## Browser Automation APIs

### Browser Sessions

#### Start Browser Session
```http
POST /api/browser/sessions
```

**Request Body**:
```json
{
  "user_id": "user_123",
  "headless": true,
  "viewport": {"width": 1920, "height": 1080}
}
```

**Response**:
```json
{
  "ok": true,
  "session_id": "browser_session_456",
  "status": "active",
  "browser": "chromium",
  "started_at": "2026-02-04T12:00:00Z"
}
```

#### Get Browser Session
```http
GET /api/browser/sessions/{session_id}
```

#### Close Browser Session
```http
DELETE /api/browser/sessions/{session_id}
```

---

### Browser Actions

#### Navigate to URL
```http
POST /api/browser/sessions/{session_id}/navigate
```

**Request Body**:
```json
{
  "url": "https://example.com"
}
```

#### Take Screenshot
```http
POST /api/browser/sessions/{session_id}/screenshot
```

#### Execute Script
```http
POST /api/browser/sessions/{session_id}/execute
```

**Request Body**:
```json
{
  "script": "document.querySelector('button').click()"
}
```

#### Fill Form
```http
POST /api/browser/sessions/{session_id}/fill
```

**Request Body**:
```json
{
  "selector": "#username",
  "value": "john@example.com"
}
```

---

## Device Capabilities APIs

### Camera

#### Request Camera Access
```http
POST /api/device/camera/request
```

**Request Body**:
```json
{
  "user_id": "user_123",
  "purpose": "Identity verification"
}
```

#### Capture Photo
```http
POST /api/device/camera/capture
```

**Request Body**:
```json
{
  "session_id": "device_session_456"
}
```

**Response**:
```json
{
  "ok": true,
  "image_url": "https://cdn.atom.com/photos/...",
  "captured_at": "2026-02-04T12:00:00Z"
}
```

---

### Screen Recording

#### Start Recording
```http
POST /api/device/recording/start
```

**Request Body**:
```json
{
  "user_id": "user_123",
  "purpose": "Task demonstration"
}
```

#### Stop Recording
```http
POST /api/device/recording/stop
```

---

### Location

#### Request Location
```http
POST /api/device/location/request
```

**Response**:
```json
{
  "ok": true,
  "latitude": 37.7749,
  "longitude": -122.4194,
  "accuracy": 10.5,
  "timestamp": "2026-02-04T12:00:00Z"
}
```

---

## Feedback APIs

### Submit Feedback

#### Thumbs Up/Down
```http
POST /api/feedback/thumbs
```

**Request Body**:
```json
{
  "agent_id": "agent_123",
  "execution_id": "exec_456",
  "feedback_type": "thumbs_up",
  "user_id": "user_789"
}
```

#### Star Rating
```http
POST /api/feedback/rating
```

**Request Body**:
```json
{
  "agent_id": "agent_123",
  "execution_id": "exec_456",
  "rating": 5,
  "user_id": "user_789"
}
```

#### Correction Feedback
```http
POST /api/feedback/correction
```

**Request Body**:
```json
{
  "agent_id": "agent_123",
  "execution_id": "exec_456",
  "original_output": "...",
  "corrected_output": "...",
  "user_id": "user_789"
}
```

---

### Feedback Analytics

#### Get Agent Feedback
```http
GET /api/feedback/agents/{agent_id}
```

#### Get Feedback Summary
```http
GET /api/feedback/summary
```

**Query Parameters**: `start_date`, `end_date`, `agent_id`

---

## Deep Link APIs

### Create Deep Link

```http
POST /api/deeplinks
```

**Request Body**:
```json
{
  "type": "agent",
  "resource_id": "agent_123",
  "action": "execute",
  "params": {...}
}
```

**Response**:
```json
{
  "ok": true,
  "deeplink": "atom://agent/agent_123?action=execute",
  "type": "agent",
  "created_at": "2026-02-04T12:00:00Z"
}
```

### Resolve Deep Link

```http
GET /api/deeplinks/resolve?url={deeplink_url}
```

---

## Custom Component APIs

### Create Custom Component

```http
POST /api/custom-components
```

**Request Body**:
```json
{
  "name": "CustomChart",
  "type": "chart",
  "html": "<div id='chart'></div>",
  "css": "#chart { width: 100%; }",
  "javascript": "renderChart(data);"
}
```

### List Custom Components

```http
GET /api/custom-components
```

### Get Custom Component

```http
GET /api/custom-components/{component_id}
```

### Update Custom Component

```http
PUT /api/custom-components/{component_id}
```

### Delete Custom Component

```http
DELETE /api/custom-components/{component_id}
```

---

## Admin APIs

### System Status

```http
GET /api/admin/status
```

### Database Statistics

```http
GET /api/admin/database/stats
```

### User Management

```http
GET /api/admin/users
```

```http
POST /api/admin/users
```

---

## Error Handling

### Standard Error Response

```json
{
  "ok": false,
  "error": "Error type",
  "message": "Human-readable error message",
  "details": {...}
}
```

### Common HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 422 | Validation Error |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

---

## Rate Limiting

API requests are rate limited:

- **Authenticated Users**: 1000 requests per hour
- **Unauthenticated Users**: 100 requests per hour

Rate limit headers are included in responses:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1738689600
```

---

## Authentication

### API Key Authentication

Include your API key in the request header:

```http
Authorization: Bearer YOUR_API_KEY
```

### OAuth Authentication

Use OAuth token obtained from OAuth flows:

```http
Authorization: Bearer OAUTH_TOKEN
```

---

## Pagination

List endpoints support pagination:

```
GET /api/agents?page=1&limit=20
```

**Response**:
```json
{
  "ok": true,
  "data": [...],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 150,
    "pages": 8
  }
}
```

---

## Webhooks

### Configure Webhook

```http
POST /api/webhooks
```

**Request Body**:
```json
{
  "url": "https://your-app.com/webhook",
  "events": ["agent.execution.completed", "workflow.failed"]
}
```

### Webhook Events

| Event | Description |
|-------|-------------|
| `agent.execution.completed` | Agent execution completed |
| `agent.execution.failed` | Agent execution failed |
| `workflow.completed` | Workflow completed |
| `canvas.submitted` | Canvas form submitted |

---

## SDKs

### Python SDK

```python
from atom_client import AtomClient

client = AtomClient(api_key="your_api_key")

# Execute agent
result = client.agents.execute("agent_123", input="Hello")

# Get canvas
canvas = client.canvas.get("canvas_456")
```

### JavaScript SDK

```javascript
import { AtomClient } from '@atom-platform/sdk';

const client = new AtomClient({ apiKey: 'your_api_key' });

// Execute agent
const result = await client.agents.execute('agent_123', { input: 'Hello' });

// Get canvas
const canvas = await client.canvas.get('canvas_456');
```

---

## Changelog

### February 2026
- ✅ Added OAuth endpoints for Trello, Asana, Notion, GitHub, Dropbox
- ✅ Implemented real health checks for 10+ integration services
- ✅ Standardized API route patterns across all endpoints
- ✅ Migrated from `database_manager` to SQLAlchemy ORM

---

## Support

- **Documentation**: https://docs.atom-platform.com
- **Issues**: https://github.com/atom-platform/atom/issues
- **Email**: support@atom-platform.com

---

*Last updated: February 4, 2026*
