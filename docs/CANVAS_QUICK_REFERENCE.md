# Canvas System Quick Reference

**Version**: 1.2.0 (February 2026)
**Status**: Production Ready

---

## Quick Start

### Basic Usage

```python
from tools.canvas_tool import present_chart, present_markdown, present_form, update_canvas

# Present a chart
await present_chart(
    user_id="user-1",
    chart_type="line_chart",
    data=[{"x": "Jan", "y": 100}, {"x": "Feb", "y": 150}],
    title="Sales Trend"
)

# Update chart data (NEW!)
await update_canvas(
    user_id="user-1",
    canvas_id="canvas-abc123",
    updates={"data": [{"x": "Jan", "y": 100}, {"x": "Feb", "y": 200}]}
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
    session_id: str = None, # Optional: Session ID (NEW!)
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
    session_id: str = None  # NEW!
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
    session_id: str = None  # NEW!
)
```

**Complexity**: 2 (MODERATE)
**Maturity**: INTERN+

### update_canvas (NEW!)
```python
await update_canvas(
    user_id: str,
    canvas_id: str,         # Existing canvas ID
    updates: Dict,          # Update data
    agent_id: str = None,
    session_id: str = None
)
```

**Complexity**: 2 (MODERATE)
**Maturity**: INTERN+

**Examples**:
```python
# Update data
await update_canvas(user_id="user-1", canvas_id="abc", updates={"data": [...]})

# Update title
await update_canvas(user_id="user-1", canvas_id="abc", updates={"title": "New Title"})

# Update multiple fields
await update_canvas(
    user_id="user-1",
    canvas_id="abc",
    updates={"title": "New", "data": [...], "color": "#FF0000"}
)
```

---

## Tool Registry (NEW!)

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

---

## Governance

### Action Complexity

| Level | Actions | Maturity Required |
|-------|---------|-------------------|
| 1 (LOW) | present_chart, present_markdown | STUDENT+ |
| 2 (MODERATE) | present_form, update_canvas, browser_navigate, device_camera_snap | INTERN+ |
| 3 (HIGH) | submit_form, device_screen_record_start, device_screen_record_stop | SUPERVISED+ |
| 4 (CRITICAL) | device_execute_command, delete, execute | AUTONOMOUS |

### Maturity Levels

| Level | Confidence | Capabilities |
|-------|-----------|--------------|
| STUDENT | <0.5 | Read-only (charts, markdown) |
| INTERN | 0.5-0.7 | Streaming, form presentation, **canvas updates** |
| SUPERVISED | 0.7-0.9 | Form submissions, screen recording |
| AUTONOMOUS | >0.9 | Full autonomy, command execution |

---

## WebSocket Events

### Canvas Events

```javascript
// Client-side WebSocket handling

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);

  switch(message.type) {
    case "canvas:update":
      const { action, component, canvas_id, session_id, data } = message.data;

      if (action === "present") {
        // Present new component
        renderComponent(component, data, canvas_id);
      } else if (action === "update") {
        // Update existing component (NEW!)
        updateComponent(canvas_id, data);
      } else if (action === "close") {
        // Close canvas
        closeCanvas();
      }
      break;
  }
};
```

### Event Types

- `canvas:present` - New component presented
- `canvas:update` - Component updated (NEW!)
- `canvas:close` - Canvas closed
- `canvas:delete` - Component deleted

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
