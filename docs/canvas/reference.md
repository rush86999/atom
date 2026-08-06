# Canvas System Quick Reference

**Version**: 2.0.0 (August 2026)
**Status**: Production Ready — **Full CRUD + Integration Support**

---

## Quick Start

### Basic Usage

```python
from tools.canvas_tool import present_chart, present_markdown, present_form, update_canvas
from tools.canvas_crud_tool import read_canvas, update_canvas_content, delete_canvas, list_canvases

# Present a chart (CREATE)
await present_chart(
    user_id="user-1",
    chart_type="line_chart",
    data=[{"x": "Jan", "y": 100}, {"x": "Feb", "y": 150}],
    title="Sales Trend"
)

# Read canvas (READ)
await read_canvas(
    user_id="user-1",
    canvas_id="canvas-abc123"
)

# Update chart data (UPDATE)
await update_canvas_content(
    user_id="user-1",
    canvas_id="canvas-abc123",
    content={"data": [{"x": "Jan", "y": 100}, {"x": "Feb", "y": 200}]},
    canvas_type="charts"
)

# Delete canvas (DELETE)
await delete_canvas(
    user_id="user-1",
    canvas_id="canvas-abc123"
)

# List canvases (LIST)
await list_canvases(
    user_id="user-1",
    canvas_type="charts"
)
```

### Session Isolation (NEW!)

```python
# Session A
await present_chart(
    user_id="user-1",
    chart_type="line_chart",
    data=[...],
    session_id="session-a"  # Isolated canvas
)

# Session B (different canvas, no collision)
await present_markdown(
    user_id="user-1",
    content="# Report",
    session_id="session-b"  # Separate canvas
)
```

---

## Canvas Functions

### present_chart
```python
await present_chart(
    user_id: str,           # Required: User ID
    chart_type: str,        # Required: "line_chart", "bar_chart", "pie_chart"
    data: List[Dict],       # Required: Chart data
    title: str = None,      # Optional: Chart title
    agent_id: str = None,   # Optional: Agent ID (for governance)
    session_id: str = None, # Optional: Session ID
    **kwargs                # Additional chart options
)
```

**Complexity**: 1 (LOW)
**Maturity**: STUDENT+

### present_markdown
```python
await present_markdown(
    user_id: str,
    content: str,           # Markdown content
    title: str = None,
    agent_id: str = None,
    session_id: str = None
)
```

**Complexity**: 1 (LOW)
**Maturity**: STUDENT+

### present_form
```python
await present_form(
    user_id: str,
    form_schema: Dict,      # Form schema with fields
    title: str = None,
    agent_id: str = None,
    session_id: str = None
)
```

**Complexity**: 2 (MODERATE)
**Maturity**: INTERN+

### present_sheet
```python
await present_sheet(
    user_id: str,
    data: List[Dict],       # Sheet data (rows)
    columns: List[Dict],    # Column definitions
    title: str = None,
    agent_id: str = None,
    session_id: str = None
)
```

**Complexity**: 2 (MODERATE)
**Maturity**: INTERN+

---

## Canvas CRUD Functions (NEW — Aug 2026)

### read_canvas
```python
await read_canvas(
    user_id: str,           # Required: User ID
    canvas_id: str,         # Required: Canvas ID from present_* call
) -> Dict[str, Any]
```

Returns current content, canvas_type, title, action_type, created_at. Reads latest `CanvasAudit` row (audit trail is source of truth). IDOR-guarded (owner only).

**Complexity**: 1 (LOW)
**Maturity**: STUDENT+
**Cacheable**: Yes (idempotent read)

### update_canvas_content
```python
await update_canvas_content(
    user_id: str,           # Required: User ID
    canvas_id: str,         # Required: Canvas ID to update
    content: Any,           # Required: New content (type depends on canvas_type)
    canvas_type: str = "generic",  # Optional: Canvas type
    title: str = None,      # Optional: New title
) -> Dict[str, Any]
```

Reads latest `CanvasAudit`, merges new content, appends new audit row with `action_type="update"`. Broadcasts WS `canvas:update`. Works for ALL canvas types (generalizes docs-only pattern). IDOR-guarded.

**Complexity**: 2 (MODERATE)
**Maturity**: INTERN+
**Dependencies**: websockets

### delete_canvas
```python
await delete_canvas(
    user_id: str,           # Required: User ID
    canvas_id: str,         # Required: Canvas ID to delete
) -> Dict[str, Any]
```

Writes `CanvasAudit` with `action_type="delete"`, broadcasts WS close. Append-only trail preserved (history recoverable). Targets specific canvas_id (unlike old close_canvas which closed ALL). IDOR-guarded.

**Complexity**: 1 (LOW)
**Maturity**: STUDENT+
**Dependencies**: websockets

### list_canvases
```python
await list_canvases(
    user_id: str,                    # Required: User ID
    canvas_type: str = None,         # Optional: Filter by type (e.g. "sheets", "email")
    include_deleted: bool = False,   # Optional: Include deleted canvases
) -> Dict[str, Any]
```

Returns latest state of each unique `canvas_id` from audit trail. Groups by canvas_id, takes latest per ID. Filterable by type.

**Complexity**: 1 (LOW)
**Maturity**: STUDENT+
**Cacheable**: Yes (idempotent list)

---

## Tool Registry (Aug 2026 — Full CRUD Registered)

All canvas tools are registered in the unified Action Registry (`core/action_registry.py`), auto-exposed to:
- **Agent MCP loop** via `integrations/mcp_service.get_all_tools()`
- **Frontend RPC** via `api/rpc_routes.py` (`POST /api/rpc/{action}`)

### Canvas Tools Registered

| Tool | Category | Complexity | Maturity | Cacheable | Description |
|------|----------|------------|----------|-----------|-------------|
| `present_chart` | canvas | 1 (LOW) | STUDENT+ | No | Create chart canvas |
| `present_markdown` | canvas | 1 (LOW) | STUDENT+ | No | Create markdown canvas |
| `present_form` | canvas | 2 (MODERATE) | INTERN+ | No | Create form canvas |
| `present_sheet` | canvas | 2 (MODERATE) | INTERN+ | No | Create sheet canvas |
| `read_canvas` | canvas | 1 (LOW) | STUDENT+ | **Yes** | Read canvas by ID |
| `update_canvas_content` | canvas | 2 (MODERATE) | INTERN+ | No | Update canvas content |
| `delete_canvas` | canvas | 1 (LOW) | STUDENT+ | No | Delete canvas by ID |
| `list_canvases` | canvas | 1 (LOW) | STUDENT+ | **Yes** | List user's canvases |

### Discover Tools

```python
from tools.registry import get_tool_registry

registry = get_tool_registry()

# List all tools
tools = registry.list_all()

# List by category
canvas_tools = registry.list_by_category("canvas")

# List by maturity level
intern_tools = registry.list_by_maturity("INTERN")

# Search
results = registry.search("chart")

# Get metadata
metadata = registry.get("present_chart")
print(metadata.description)
print(metadata.complexity)
print(metadata.maturity_required)
```

### API Endpoints

```bash
# List all tools
GET /api/tools

# Filter by category
GET /api/tools?category=canvas

# Filter by maturity
GET /api/tools?maturity=INTERN

# Get tool details
GET /api/tools/present_chart

# Search tools
GET /api/tools/search?query=chart

# Get statistics
GET /api/tools/stats

# List categories
GET /api/tools/categories
```

### Integration Notes

- **Governance enforced** at dispatch: `AgentGovernanceService.can_execute_action()` checks maturity + capability bindings
- **Sandbox gate** (P9 default-on): Every call flows through `integrations/mcp_service.call_tool` → `core/sandbox_gate.evaluate_tool_call`
- **Audit trail**: Every CRUD op writes `CanvasAudit` row (append-only, IDOR-guarded via `Canvas.created_by`)
- **WebSocket broadcast**: Update/delete ops broadcast `canvas:update` to `user:{user_id}` channel
- **Session isolation**: `session_id` parameter on create ops for parallel workflow channels

---

## Governance

### Action Complexity

| Level | Actions | Maturity Required |
|-------|---------|-------------------|
| 1 (LOW) | present_chart, present_markdown, present_sheet, read_canvas, delete_canvas, list_canvases | STUDENT+ |
| 2 (MODERATE) | present_form, update_canvas_content, browser_navigate, device_camera_snap | INTERN+ |
| 3 (HIGH) | submit_form, device_screen_record_start, device_screen_record_stop | SUPERVISED+ |
| 4 (CRITICAL) | device_execute_command, delete, execute | AUTONOMOUS |

### Maturity Levels

| Level | Confidence | Capabilities |
|-------|-----------|--------------|
| STUDENT | <0.5 | Read-only (charts, markdown, sheets), read/list/delete canvases |
| INTERN | 0.5-0.7 | Streaming, form presentation, canvas updates, canvas create |
| SUPERVISED | 0.7-0.9 | Form submissions, screen recording |
| AUTONOMOUS | >0.9 | Full autonomy, command execution |

### Capability Bindings (P2 — Per-Agent Zero-Trust)

Each agent declares `capabilities: string[]` in `AgentRegistry`. At dispatch:
```
effective = agent.capabilities ∩ tier_floor ∩ sandbox_policy
```

Canvas tools require capabilities:
- `canvas_present` — create canvases
- `canvas_read` — read_canvas, list_canvases
- `canvas_update` — update_canvas_content
- `canvas_delete` — delete_canvas
- `canvas_list` — list_canvases

### Sandbox Gate (P9 — Default-On)

Every canvas tool call flows through:
```
integrations/mcp_service.call_tool
  → core/sandbox_gate.evaluate_tool_call
    → Phase A: Policy + Audit
    → Phase B: Filesystem scope
    → Phase C: Tripwires + Caps + KillRun
    → Phase D: Firecracker microVM (optional)
    → Phase E: Provenance + ActionJudge (opt-in)
```

Kill switch: `ATOM_SANDBOX_FORCE_ENFORCE=false` (restores shadow mode)

---

## WebSocket Events

### Canvas Events

```javascript
// Client-side WebSocket handling

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);

  switch(message.type) {
    case "canvas:update":
      const { action, component, canvas_id, session_id, data, title } = message.data;

      if (action === "present") {
        // Present new component
        renderComponent(component, data, canvas_id);
      } else if (action === "update") {
        // Update existing component
        updateComponent(canvas_id, data);
      } else if (action === "close") {
        // Close canvas (from delete_canvas)
        closeCanvas(canvas_id);
      } else if (action === "delete") {
        // Explicit delete event
        removeCanvas(canvas_id);
      }
      break;
  }
};
```

### Event Types

- `canvas:present` — New component presented
- `canvas:update` — Component updated (content/title)
- `canvas:close` — Canvas closed (from delete_canvas)
- `canvas:delete` — Explicit delete (future use)

### Broadcast Details

| Operation | Broadcast Action | Channel | Payload |
|-----------|------------------|---------|---------|
| `present_*` | `"present"` | `user:{user_id}` | component, canvas_id, data, title, session_id |
| `update_canvas_content` | `"update"` | `user:{user_id}` | component, canvas_id, data, title |
| `delete_canvas` | `"close"` | `user:{user_id}` | canvas_id |

---

## Integration Support (Aug 2026)

### Action Registry Integration

All canvas tools are registered in the unified **Action Registry** (`core/action_registry.py`):

```python
# Auto-exposed to agent MCP loop
from integrations.mcp_service import get_all_tools
tools = get_all_tools()  # Includes all canvas CRUD tools

# Auto-exposed to frontend RPC
# POST /api/rpc/read_canvas
# POST /api/rpc/update_canvas_content
# POST /api/rpc/delete_canvas
# POST /api/rpc/list_canvases
```

### Governance Enforcement

```
User Request
    ↓
AgentContextResolver (tier, caps, context)
    ↓
GovernanceCache (<1ms cached check)
    ↓
AgentGovernanceService.can_execute_action()
    ↓
ALLOWED → core/sandbox_gate.evaluate_tool_call → execute
PROPOSAL → ProposalService (HITL approval)
BLOCKED → Audit + Training data
```

### Sandbox Gate (P9 Default-On)

Every canvas tool call flows through the shared sandbox gate:
```python
integrations/mcp_service.call_tool
  → core/sandbox_gate.evaluate_tool_call
```

Phases enforced:
- **A**: Policy + Audit (always)
- **B**: Filesystem scope (`ATOM_SANDBOX_FS_ENABLED`)
- **C**: Tripwires + Caps + KillRun (`ATOM_SANDBOX_CAPS_ENABLED`, `ATOM_SANDBOX_TRIPWIRES_ENABLED`, `ATOM_SANDBOX_WHITELIST_ENABLED`)
- **D**: Firecracker microVM (opt-in, `ATOM_SANDBOX_RUNTIME=firecracker`)
- **E**: Provenance + ActionJudge (opt-in, `ATOM_SANDBOX_JUDGE_ENABLED`)

### Audit Trail

Every CRUD operation writes a `CanvasAudit` row (append-only, recoverable):
- **IDOR protection**: Owner verification via `Canvas.created_by`
- **Tenant isolation**: `tenant_id` carried from latest audit row
- **Session tracking**: `session_id` for parallel workflow isolation

### Capability Requirements

| Tool | Required Capability |
|------|---------------------|
| `present_*` | `canvas_present` |
| `read_canvas` | `canvas_read` |
| `list_canvases` | `canvas_list` |
| `update_canvas_content` | `canvas_update` |
| `delete_canvas` | `canvas_delete` |

Agents declare capabilities in `AgentRegistry.capabilities`. Effective = `agent.capabilities ∩ tier_floor ∩ sandbox_policy`.

---

## Session Isolation

### WebSocket Channels

```python
# Default channel (no session)
channel = f"user:{user_id}"  # "user:user-1"

# Session-specific channel (NEW!)
channel = f"user:{user_id}:session:{session_id}"  # "user:user-1:session:abc"
```

### Database Schema

```sql
CREATE TABLE canvas_audit (
    id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    canvas_id VARCHAR,
    session_id VARCHAR,  -- NEW!
    component_type VARCHAR NOT NULL,
    action VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Audit Trail

All canvas actions are logged:

```python
from core.models import CanvasAudit
from core.database import SessionLocal

db = SessionLocal()

# Query canvas audit for a user
audits = db.query(CanvasAudit).filter(
    CanvasAudit.user_id == "user-1"
).order_by(CanvasAudit.created_at.desc()).limit(10).all()

for audit in audits:
    print(f"{audit.action} {audit.component_type} - {audit.created_at}")
    print(f"  Session: {audit.session_id}")  # NEW!
    print(f"  Agent: {audit.agent_id}")
```

---

## Testing

### Run Tests

```bash
# Canvas update tests
pytest tests/test_canvas_updates.py -v

# Session isolation tests
pytest tests/test_canvas_sessions.py -v

# Tool registry tests
pytest tests/test_tool_registry.py -v

# All canvas tests
pytest tests/test_canvas*.py tests/test_tool_registry.py -v
```

### Test Results

```
36 passed in 0.60s
```

---

## Migration

### Apply Migration

```bash
cd backend
alembic upgrade head
```

### Verify Migration

```bash
alembic current
# Output: 3552e6844c1d (add session_id to canvas_audit)
```

---

## Common Patterns

### Dynamic Dashboard

```python
# Initial presentation
result = await present_chart(
    user_id="user-1",
    chart_type="line_chart",
    data=[{"x": 1, "y": 10}],
    title="Live Dashboard"
)
canvas_id = result["canvas_id"]

# Real-time updates
while True:
    new_data = fetch_latest_data()
    await update_canvas(
        user_id="user-1",
        canvas_id=canvas_id,
        updates={"data": new_data}
    )
    await asyncio.sleep(5)
```

### Multi-Agent Workflow

```python
# Agent A: Sales data
await present_chart(
    user_id="user-1",
    chart_type="line_chart",
    data=sales_data,
    session_id="sales-session",
    agent_id="agent-sales"
)

# Agent B: Marketing data (concurrent, no collision)
await present_chart(
    user_id="user-1",
    chart_type="bar_chart",
    data=marketing_data,
    session_id="marketing-session",
    agent_id="agent-marketing"
)
```

### Tool Discovery

```python
from tools.registry import get_tool_registry

registry = get_tool_registry()

# Find tools an agent can use
agent_tools = registry.list_by_maturity("INTERN")

print(f"Agent has access to {len(agent_tools)} tools:")
for tool_name in agent_tools:
    metadata = registry.get(tool_name)
    print(f"  - {metadata.name}: {metadata.description}")
```

---

## Error Handling

### Update Nonexistent Canvas

```python
result = await update_canvas(
    user_id="user-1",
    canvas_id="nonexistent",
    updates={"title": "New"}
)

# Result: {"success": True, ...}
# Note: Update will be broadcast but client may ignore if canvas_id not found
```

### Governance Blocked

```python
# STUDENT agent tries to update canvas
result = await update_canvas(
    user_id="user-1",
    canvas_id="canvas-123",
    updates={"data": [...]},
    agent_id="student-agent"
)

# Result: {"success": False, "error": "Agent not permitted to update canvas"}
```

---

## Performance

| Operation | Latency | Notes |
|-----------|---------|-------|
| present_chart | ~1ms | + governance |
| update_canvas | ~1-2ms | + governance + audit |
| Tool discovery | <1ms | In-memory lookup |
| Session isolation | <0.1ms | Channel multiplexing |

---

## Best Practices

1. **Always use session_id** for parallel workflows
2. **Update canvas** instead of re-presenting for dynamic data
3. **Use tool registry** for tool discovery
4. **Check audit trail** for debugging
5. **Test governance** with different agent maturity levels

---

## Troubleshooting

### Canvas Not Updating

```python
# Check canvas_id exists
# Check user_id matches
# Check WebSocket connection

# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Session Collision

```python
# Use unique session IDs
session_id = f"{agent_id}-{workflow_id}-{timestamp}"

# Or use UUID
import uuid
session_id = str(uuid.uuid4())
```

### Tool Not Found

```python
# Check tool registry
registry = get_tool_registry()
metadata = registry.get("tool_name")

if not metadata:
    print("Tool not registered")

# Check module imports
import tools.canvas_tool
print(dir(tools.canvas_tool))
```

---

## Further Reading

- **Full Documentation**: `docs/CANVAS_ENHANCEMENTS_COMPLETE.md`
- **Original Analysis**: Gap analysis document
- **Test Suite**: `tests/test_canvas*.py`
- **Implementation**: `tools/canvas_tool.py`, `tools/registry.py`

---

**Last Updated**: February 1, 2026
**Version**: 1.2.0
# Canvas State API

## Overview

The Canvas State API enables AI agents to programmatically access canvas component state without OCR. All canvas components expose structured state via:

1. **Hidden accessibility trees** - DOM elements with `role="log"` and `data-canvas-state` attributes
2. **JavaScript API** - Global `window.atom.canvas` object
3. **WebSocket events** - Real-time state change broadcasts

## Access Methods

### Method 1: Hidden Accessibility Trees (Recommended for AI Agents)

Query the DOM for hidden state elements:

```javascript
// Get all canvas state elements
const canvasStates = document.querySelectorAll('[data-canvas-state]');

// Get specific canvas state
const operationState = document.querySelector('[data-canvas-state="agent_operation_tracker"]');

// Parse state JSON
const state = JSON.parse(operationState.textContent);
```

**Attributes:**
- `data-canvas-state` - Component identifier (e.g., "agent_operation_tracker", "view_orchestrator")
- `data-canvas-type` - Canvas type (generic, docs, email, sheets, orchestration, terminal, coding)
- `role` - ARIA role ("log" for state, "alert" for errors)

### Method 2: JavaScript API

```javascript
// Get specific canvas state
const state = window.atom.canvas.getState('canvas-id');

// Get all canvas states
const allStates = window.atom.canvas.getAllStates();

// Subscribe to state changes
const unsubscribe = window.atom.canvas.subscribe('canvas-id', (state) => {
  console.log('State changed:', state);
});

// Unsubscribe when done
unsubscribe();

// Subscribe to all canvas changes
const unsubAll = window.atom.canvas.subscribeAll((event) => {
  console.log('Canvas changed:', event.canvas_id, event.state);
});
```

### Method 3: WebSocket Events

Subscribe to canvas state changes via WebSocket:

```javascript
socket.addEventListener('message', (event) => {
  const message = JSON.parse(event.data);

  if (message.type === 'canvas:state_change') {
    console.log('Canvas state changed:', message.canvas_id);
    console.log('New state:', message.state);
  }
});
```

## Canvas State Schemas

### AgentOperationTracker

```typescript
{
  canvas_type: 'generic',
  component: 'agent_operation_tracker',
  operation_id: string,
  agent_id: string,
  agent_name: string,
  operation_type: string,
  status: 'running' | 'waiting' | 'completed' | 'failed',
  current_step: string,
  current_step_index: number,
  total_steps?: number,
  progress: number,  // 0-100
  context: {
    what?: string,
    why?: string,
    next?: string
  },
  logs_count: number,
  started_at: string,
  completed_at?: string
}
```

### ViewOrchestrator

```typescript
{
  canvas_type: 'generic',
  component: 'view_orchestrator',
  layout: 'split_horizontal' | 'split_vertical' | 'grid' | 'tabs',
  current_view: string,
  active_views: [{
    view_id: string,
    view_type: 'canvas' | 'browser' | 'terminal' | 'app',
    title: string,
    status: 'active' | 'background' | 'closed',
    url?: string,
    command?: string
  }],
  canvas_guidance?: {
    agent_id: string,
    message: string,
    what_youre_seeing: string,
    controls: Array<{ label: string; action: string }>
  }
}
```

### Chart (LineChart, BarChart, PieChart)

```typescript
{
  canvas_type: 'generic',
  component: 'line_chart' | 'bar_chart' | 'pie_chart',
  chart_type: 'line' | 'bar' | 'pie',
  data_points: Array<{
    x: string | number,
    y: number,
    label?: string
  }>,
  axes_labels?: {
    x?: string,
    y?: string
  },
  title?: string,
  legend?: boolean
}
```

### Form (InteractiveForm)

```typescript
{
  canvas_type: 'generic',
  component: 'form',
  form_schema: {
    fields: Array<{
      name: string,
      type: string,
      label: string,
      required: boolean
    }>
  },
  form_data: Record<string, any>,
  validation_errors: Array<{
    field: string,
    message: string
  }>,
  submit_enabled: boolean,
  submitted?: boolean
}
```

## Usage Examples

### Example 1: AI Agent Reads Operation Progress

```javascript
// Agent wants to check operation progress
const operationDiv = document.querySelector('[data-canvas-state="agent_operation_tracker"]');
const operation = JSON.parse(operationDiv.textContent);

if (operation.status === 'completed') {
  console.log('Operation completed:', operation.progress + '%');
} else {
  console.log('Current step:', operation.current_step);
  console.log('Progress:', operation.progress + '%');
}
```

### Example 2: AI Agent Monitors Form State

```javascript
// Agent monitors form for submission
const formState = window.atom.canvas.getState('form-workflow-approval');

if (formState.submitted) {
  console.log('Form submitted with data:', formState.form_data);
} else if (formState.validation_errors.length > 0) {
  console.log('Form has errors:', formState.validation_errors);
}
```

### Example 3: Subscribe to Canvas Changes

```javascript
// Agent subscribes to all canvas state changes
const unsubscribe = window.atom.canvas.subscribeAll((event) => {
  console.log('Canvas changed:', event.canvas_type);
  console.log('New state:', event.state);

  // Agent decision logic based on state
  if (event.state.status === 'completed') {
    console.log('Operation completed, proceeding to next step...');
  }
});
```

## Performance Considerations

- State serialization overhead: <10ms per canvas render
- Use getState for one-time queries (faster than DOM parsing)
- Use subscribe for real-time monitoring (WebSocket events)
- Accessibility tree is always available (no JavaScript execution required)

## Canvas Type Reference

| Canvas Type | Component | State Fields |
|-------------|-----------|--------------|
| generic | agent_operation_tracker | operation_id, status, progress, context |
| generic | view_orchestrator | layout, active_views, canvas_guidance |
| generic | line_chart | data_points, axes_labels, chart_type |
| generic | bar_chart | data_points, axes_labels, chart_type |
| generic | pie_chart | data_points, legend |
| generic | form | form_data, validation_errors, submit_enabled |
| orchestration | workflow_canvas | tasks, nodes, connections |
| terminal | terminal_canvas | lines, cursor_pos, working_dir |

## See Also

- [Agent Guidance System](../agents/guidance-system.md) - Real-time agent monitoring
- [Episodic Memory Integration](../intelligence/episodic-memory.md) - Agent learning system
- [Canvas AI Accessibility](../canvas/ai-accessibility.md) - AI-readable canvas state
- [Pre-Action Match-Confidence Layer](../architecture/MATCH_CONFIDENCE.md) - Reviewer UI uses canvas state hooks (`useCanvasState.getMatchConfidence`); surfaces selector certainty before browser clicks (June 2026)
