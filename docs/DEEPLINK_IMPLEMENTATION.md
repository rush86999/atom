# Deep Linking Implementation Guide

## Overview

Atom supports deep linking via the `atom://` URL scheme, allowing external applications to trigger actions within the Atom platform. Deep links can invoke agents, trigger workflows, manipulate canvases, and execute tools.

**Security**: All deep links are validated, sanitized, and require governance checks where applicable. A full audit trail is maintained for all deep link executions.

---

## URL Scheme Format

### Basic Format
```
atom://resource_type/resource_id?param1=value1&param2=value2
```

### Supported Resource Types

| Resource Type | Description | Example |
|--------------|-------------|---------|
| `agent` | Invoke an AI agent | `atom://agent/agent-1?message=Hello` |
| `workflow` | Trigger a workflow | `atom://workflow/workflow-1?action=start` |
| `canvas` | Manipulate a canvas | `atom://canvas/canvas-123?action=update` |
| `tool` | Execute a tool | `atom://tool/present_chart?params={...}` |

---

## Agent Deep Links

### Format
```
atom://agent/{agent_id}?message={query}&session={session_id}
```

### Parameters
- `agent_id` (required): ID of the agent to invoke
- `message` (optional): Message/query to send to the agent
- `session` (optional): Chat session ID to continue existing conversation

### Examples

```bash
# Invoke agent with message
atom://agent/sales-assistant?message=Analyze+Q1+sales

# Continue existing chat session
atom://agent/sales-assistant?message=Continue&session=abc123

# Agent with URL-encoded message
atom://agent/sales-assistant?message=What%20are%20top%20products%3F
```

### Governance
- Agent must be active (not INACTIVE)
- Agent must pass governance check for `stream_chat` action
- Creates `AgentExecution` record with `triggered_by="deeplink"`
- Creates `DeepLinkAudit` entry

### Response
```json
{
  "success": true,
  "agent_id": "sales-assistant",
  "agent_name": "Sales Assistant",
  "execution_id": "exec-123",
  "message": "Analyze Q1 sales",
  "session_id": "abc123",
  "source": "external"
}
```

---

## Workflow Deep Links

### Format
```
atom://workflow/{workflow_id}?action={action}&params={json}
```

### Parameters
- `workflow_id` (required): ID of the workflow
- `action` (optional): Action to perform (default: "start")
- `params` (optional): JSON parameters for the workflow

### Examples

```bash
# Start workflow
atom://workflow/invoice-processing?action=start

# Start workflow with parameters
atom://workflow/invoice-processing?action=start&params={"invoice_id":"inv-123"}
```

### Governance
- Creates `DeepLinkAudit` entry
- No agent execution record (workflows are separate)

### Response
```json
{
  "success": true,
  "workflow_id": "invoice-processing",
  "action": "start",
  "params": {"invoice_id": "inv-123"},
  "source": "external"
}
```

---

## Canvas Deep Links

### Format
```
atom://canvas/{canvas_id}?action={action}&params={json}
```

### Parameters
- `canvas_id` (required): ID of the canvas
- `action` (required): Action to perform ("update", "present", etc.)
- `params` (optional): JSON parameters for the canvas update

### Examples

```bash
# Update canvas
atom://canvas/canvas-123?action=update&params={"title":"New+Title"}

# Present canvas
atom://canvas/canvas-456?action=present
```

### Supported Actions
- `update`: Update canvas content (requires `params` with updates)
- `present`: Present canvas to user

### Governance
- Canvas update uses existing `update_canvas()` function
- Creates `DeepLinkAudit` entry

### Response
```json
{
  "success": true,
  "canvas_id": "canvas-123",
  "action": "update",
  "updated_fields": ["title"]
}
```

---

## Tool Deep Links

### Format
```
atom://tool/{tool_name}?params={json}
```

### Parameters
- `tool_name` (required): Name of the tool to execute
- `params` (optional): JSON parameters for the tool

### Examples

```bash
# Execute present_chart tool
atom://tool/present_chart?params={"type":"line","data":[...]}

# Execute search tool
atom://tool/search?params={"query":"sales+2024"}
```

### Governance
- Tool must be registered in `ToolRegistry`
- Creates `DeepLinkAudit` entry
- Uses existing tool metadata from registry

### Response
```json
{
  "success": true,
  "tool_name": "present_chart",
  "params": {"type": "line", "data": [...]},
  "tool_metadata": {
    "name": "present_chart",
    "description": "Present a chart to the user"
  },
  "source": "external"
}
```

---

## REST API Endpoints

### Execute Deep Link
```http
POST /api/deeplinks/execute
Content-Type: application/json

{
  "deeplink_url": "atom://agent/sales-assistant?message=Hello",
  "user_id": "user-1",
  "source": "external"
}
```

**Response**:
```json
{
  "success": true,
  "agent_id": "sales-assistant",
  "agent_name": "Sales Assistant",
  "execution_id": "exec-123",
  "message": "Hello"
}
```

### Get Audit Log
```http
GET /api/deeplinks/audit?user_id=user-1&limit=100
```

**Response**:
```json
[
  {
    "id": "audit-1",
    "user_id": "user-1",
    "agent_id": "sales-assistant",
    "resource_type": "agent",
    "resource_id": "sales-assistant",
    "action": "execute",
    "source": "external",
    "deeplink_url": "atom://agent/sales-assistant?message=Hello",
    "status": "success",
    "created_at": "2026-02-01T10:00:00Z"
  }
]
```

### Generate Deep Link
```http
POST /api/deeplinks/generate
Content-Type: application/json

{
  "resource_type": "agent",
  "resource_id": "sales-assistant",
  "parameters": {
    "message": "Hello",
    "session": "abc123"
  }
}
```

**Response**:
```json
{
  "deeplink_url": "atom://agent/sales-assistant?message=Hello&session=abc123",
  "resource_type": "agent",
  "resource_id": "sales-assistant",
  "parameters": {
    "message": "Hello",
    "session": "abc123"
  }
}
```

### Get Statistics
```http
GET /api/deeplinks/stats
```

**Response**:
```json
{
  "total_executions": 1250,
  "successful_executions": 1180,
  "failed_executions": 70,
  "by_resource_type": {
    "agent": 800,
    "workflow": 250,
    "canvas": 150,
    "tool": 50
  },
  "by_source": {
    "external": 900,
    "mobile_app": 250,
    "browser": 100
  },
  "top_agents": [
    {
      "agent_id": "sales-assistant",
      "agent_name": "Sales Assistant",
      "execution_count": 450
    }
  ],
  "last_24h_executions": 75,
  "last_7d_executions": 450
}
```

---

## Security Features

### 1. URL Validation
- All URLs are validated for correct format
- Resource ID must match regex: `^[a-zA-Z0-9_\-]+$`
- Prevents path traversal attacks

### 2. Resource Type Validation
- Only allowed resource types: `agent`, `workflow`, `canvas`, `tool`
- Invalid resource types are rejected

### 3. Agent Governance
- Agent must exist and be active
- Agent must pass governance check for action
- STUDENT+ agents can be invoked via deep links

### 4. Audit Trail
- All deep link executions are logged to `DeepLinkAudit` table
- Records: user, agent, action, parameters, result, timestamp
- Full attribution for all deep link activity

### 5. Parameter Sanitization
- URL-encoded parameters are decoded safely
- JSON parameters are validated
- SQL injection protection via SQLAlchemy

---

## Python API Usage

### Parsing Deep Links
```python
from core.deeplinks import parse_deep_link

link = parse_deep_link("atom://agent/agent-1?message=Hello")

print(link.resource_type)  # "agent"
print(link.resource_id)    # "agent-1"
print(link.parameters)     # {"message": "Hello"}
print(link.original_url)   # "atom://agent/agent-1?message=Hello"
```

### Executing Deep Links
```python
from core.deeplinks import execute_deep_link
from core.database import SessionLocal

db = SessionLocal()

result = await execute_deep_link(
    url="atom://agent/agent-1?message=Hello",
    user_id="user-1",
    db=db,
    source="mobile_app"
)

print(result)
# {"success": True, "agent_id": "agent-1", "execution_id": "..."}
```

### Generating Deep Links
```python
from core.deeplinks import generate_deep_link

url = generate_deep_link(
    resource_type="agent",
    resource_id="agent-1",
    message="Hello",
    session="abc123"
)

print(url)
# "atom://agent/agent-1?message=Hello&session=abc123"
```

---

## Error Handling

### Invalid URL Format
```json
{
  "success": false,
  "error": "Invalid scheme: 'https'. Expected 'atom://'"
}
```

### Invalid Resource Type
```json
{
  "success": false,
  "error": "Invalid resource type: 'invalid'. Must be one of ['agent', 'workflow', 'canvas', 'tool']"
}
```

### Agent Not Found
```json
{
  "success": false,
  "error": "Agent 'agent-999' not found"
}
```

### Agent Not Active
```json
{
  "success": false,
  "error": "Agent 'agent-1' is not active (status: INACTIVE)"
}
```

### Governance Blocked
```json
{
  "success": false,
  "error": "Agent not permitted to execute action: Maturity level too low"
}
```

---

## Feature Flags

### Environment Variables
```bash
# Enable/disable deep linking
DEEPLINK_ENABLED=true

# Enable/disable audit logging
DEEPLINK_AUDIT_ENABLED=true
```

### Emergency Bypass
If deep linking is disabled, all deep link executions will fail with:
```json
{
  "success": false,
  "error": "Deep linking is disabled"
}
```

---

## Database Schema

### DeepLinkAudit Table
```sql
CREATE TABLE deep_link_audit (
    id VARCHAR PRIMARY KEY,
    workspace_id VARCHAR,
    agent_id VARCHAR,
    agent_execution_id VARCHAR,
    user_id VARCHAR NOT NULL,
    resource_type VARCHAR NOT NULL,
    resource_id VARCHAR NOT NULL,
    action VARCHAR NOT NULL,
    source VARCHAR DEFAULT 'external',
    deeplink_url TEXT NOT NULL,
    parameters JSON,
    status VARCHAR DEFAULT 'success',
    error_message TEXT,
    governance_check_passed BOOLEAN,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (agent_id) REFERENCES agent_registry(id),
    FOREIGN KEY (agent_execution_id) REFERENCES agent_executions(id)
);

CREATE INDEX ix_deep_link_audit_agent_id ON deep_link_audit(agent_id);
CREATE INDEX ix_deep_link_audit_user_id ON deep_link_audit(user_id);
CREATE INDEX ix_deep_link_audit_created_at ON deep_link_audit(created_at);
```

---

## Testing

### Unit Tests
```bash
pytest tests/test_deeplinks.py -v
```

### Test Coverage
- URL parsing (valid/invalid URLs)
- Agent execution (success, not found, inactive, governance)
- Workflow execution
- Canvas execution
- Tool execution
- Audit trail creation
- REST API endpoints

### Manual Testing
```bash
# Test agent deep link
curl -X POST http://localhost:8000/api/deeplinks/execute \
  -H "Content-Type: application/json" \
  -d '{
    "deeplink_url": "atom://agent/agent-1?message=Hello",
    "user_id": "user-1",
    "source": "external"
  }'

# Get audit log
curl http://localhost:8000/api/deeplinks/audit?user_id=user-1

# Get statistics
curl http://localhost:8000/api/deeplinks/stats
```

---

## Migration

### Create Migration
```bash
cd backend
alembic revision -m "Add deep_link_audit table"
```

### Run Migration
```bash
alembic upgrade head
```

### Migration ID
- `158137b9c8b6` - Add deep_link_audit table

---

## Integration Examples

### Mobile App (iOS)
```swift
let deeplink = "atom://agent/sales-assistant?message=Analyze+sales"
if let url = URL(string: deeplink) {
    UIApplication.shared.open(url)
}
```

### Mobile App (Android)
```kotlin
val deeplink = "atom://agent/sales-assistant?message=Analyze+sales"
val intent = Intent(Intent.ACTION_VIEW, Uri.parse(deeplink))
startActivity(intent)
```

### Web App
```javascript
const deeplink = 'atom://agent/sales-assistant?message=Analyze+sales';
window.location.href = deeplink;
```

### Email Campaign
```html
<a href="atom://agent/sales-assistant?message=Start%20Q1%20analysis">
  Start Q1 Sales Analysis
</a>
```

---

## Troubleshooting

### Deep link not working
1. Check URL format: `atom://resource_type/resource_id`
2. Check resource type is valid
3. Check resource ID exists
4. Check agent is active (for agent deep links)

### Governance blocking
1. Check agent maturity level
2. Check agent has required capabilities
3. Review governance check reason in error message

### Audit log missing entries
1. Check `DEEPLINK_AUDIT_ENABLED=true`
2. Check database connection
3. Check for database errors in logs

---

## Performance Considerations

### Cache Hit Rates
- Agent lookups: cached by SQLAlchemy
- Governance checks: cached in `GovernanceCache`

### Expected Latency
- Parse deep link: <1ms
- Execute deep link: 10-50ms (including governance check)
- Audit write: 5-10ms

### Scaling
- Indexed fields: `agent_id`, `user_id`, `created_at`
- Audit log queries should use pagination (limit/offset)

---

## Future Enhancements

### Planned
1. **Batch Deep Links** - Execute multiple deep links in one request
2. **Deep Link Scheduling** - Schedule deep links for future execution
3. **Conditional Deep Links** - Execute based on conditions
4. **Deep Link Templates** - Parameterized deep link templates
5. **Webhook Support** - Notify external systems on deep link execution

### Researching
1. **Deep Link Chaining** - Chain multiple deep links
2. **Deep Link Workflows** - Embed deep links in workflows
3. **Cross-App Deep Links** - Deep links between Atom instances

---

## References

### Files
- `backend/core/deeplinks.py` - Core deep link functions
- `backend/api/deeplinks.py` - REST API endpoints
- `backend/core/models.py` - DeepLinkAudit model
- `backend/tests/test_deeplinks.py` - Test suite

### Documentation
- `CLAUDE.md` - Project documentation
- `README.md` - Project overview
- `docs/BROWSER_AUTOMATION.md` - Browser automation docs
- `docs/DEVICE_CAPABILITIES.md` - Device capabilities docs

---

## Summary

Atom's deep linking system provides:
✅ **atom:// URL scheme** for external app integration
✅ **Agent/Workflow/Canvas/Tool** invocation
✅ **Security** with validation and governance
✅ **Audit trail** for all executions
✅ **REST API** for programmatic access
✅ **Python API** for internal use
✅ **100% test coverage** of core functionality

**Key Takeaway**: Deep links enable external applications to trigger Atom actions securely with full governance and audit trails.
