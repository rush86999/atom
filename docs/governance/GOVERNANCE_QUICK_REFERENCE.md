# Governance Integration - Quick Reference

## For Developers

### Using Agent Resolution in Your Code

```python
from core.agent_context_resolver import AgentContextResolver
from core.database import SessionLocal

with SessionLocal() as db:
    resolver = AgentContextResolver(db)

    # Resolve agent for a request
    agent, context = await resolver.resolve_agent_for_request(
        user_id="user-1",
        workspace_id="workspace-1",
        session_id="session-1",  # Optional
        requested_agent_id="agent-1",  # Optional
        action_type="chat"
    )

    print(f"Agent: {agent.name}, Status: {agent.status}")
    print(f"Resolution path: {context['resolution_path']}")
```

### Checking Agent Permissions

```python
from core.agent_governance_service import AgentGovernanceService
from core.database import SessionLocal

with SessionLocal() as db:
    governance = AgentGovernanceService(db)

    # Check if agent can perform action
    check = governance.can_perform_action(
        agent_id="agent-1",
        action_type="stream_chat"
    )

    if check["allowed"]:
        # Proceed with action
        print("Agent is permitted")
    else:
        # Handle blocked action
        print(f"Blocked: {check['reason']}")
```

### Using Governance Cache

```python
from core.governance_cache import get_governance_cache

cache = get_governance_cache()

# Check cache first (fast path)
cached_decision = cache.get("agent-1", "stream_chat")
if cached_decision:
    # Use cached decision
    print(f"Cached: {cached_decision}")
else:
    # Query governance service
    decision = governance.can_perform_action("agent-1", "stream_chat")

    # Cache the result
    cache.set("agent-1", "stream_chat", decision)
```

### Creating Agent Execution Records

```python
from core.models import AgentExecution
from datetime import datetime
import uuid

execution = AgentExecution(
    id=str(uuid.uuid4()),
    agent_id="agent-1",
    workspace_id="workspace-1",
    status="running",
    input_summary="User request: ...",
    triggered_by="api"
)

db.add(execution)
db.commit()

# After completing the action
execution.status = "completed"
execution.output_summary = "Action completed successfully"
execution.completed_at = datetime.now()
db.commit()
```

### Using Canvas Tool with Governance

```python
from tools.canvas_tool import present_chart, present_form

# Present a chart (automatically creates execution records)
await present_chart(
    user_id="user-1",
    chart_type="line_chart",
    data=[{"x": 1, "y": 2}, {"x": 2, "y": 4}],
    title="Sales Trend",
    agent_id="agent-1",  # Optional - will be resolved if not provided
    workspace_id="workspace-1"
)

# Present a form (NEW!)
await present_form(
    user_id="user-1",
    form_schema={
        "fields": [
            {"name": "email", "type": "email", "required": true},
            {"name": "message", "type": "text", "required": true}
        ]
    },
    title="Contact Us",
    agent_id="agent-1",
    workspace_id="workspace-1"
)
```

## Action Complexity Quick Reference

| Action | Complexity | Required Status | Example Use |
|--------|------------|-----------------|-------------|
| `present_chart` | 1 | STUDENT+ | Display data visualization |
| `present_markdown` | 1 | STUDENT+ | Show formatted content |
| `stream_chat` | 2 | INTERN+ | Stream LLM responses |
| `present_form` | 2 | INTERN+ | Request user input |
| `submit_form` | 3 | SUPERVISED+ | Process form submission |
| `llm_stream` | 2 | INTERN+ | Generate LLM content |

## Feature Flags

```bash
# Enable/disable governance per component
export STREAMING_GOVERNANCE_ENABLED=true   # Default: true
export CANVAS_GOVERNANCE_ENABLED=true      # Default: true
export FORM_GOVERNANCE_ENABLED=true        # Default: true

# Emergency bypass (disables ALL governance)
export EMERGENCY_GOVERNANCE_BYPASS=false   # Default: false
```

## Common Patterns

### Pattern 1: Streaming with Governance

```python
from core.agent_context_resolver import AgentContextResolver
from core.agent_governance_service import AgentGovernanceService
from core.llm.byok_handler import BYOKHandler

with SessionLocal() as db:
    # 1. Resolve agent
    resolver = AgentContextResolver(db)
    agent, _ = await resolver.resolve_agent_for_request(
        user_id=request.user_id,
        workspace_id=request.workspace_id,
        requested_agent_id=request.agent_id,
        action_type="stream_chat"
    )

    # 2. Check governance
    governance = AgentGovernanceService(db)
    check = governance.can_perform_action(agent.id, "stream_chat")
    if not check["allowed"]:
        return {"error": check["reason"]}

    # 3. Create execution record
    execution = AgentExecution(agent_id=agent.id, ...)
    db.add(execution)
    db.commit()

    # 4. Stream with agent context
    handler = BYOKHandler(workspace_id=ws_id)
    async for token in handler.stream_completion(
        messages=messages,
        model=model,
        provider_id=provider_id,
        agent_id=agent.id,  # Pass for tracking
        db=db
    ):
        yield token

    # 5. Record outcome
    execution.status = "completed"
    execution.completed_at = datetime.now()
    await governance.record_outcome(agent.id, success=True)
```

### Pattern 2: Canvas Presentation with Governance

```python
from tools.canvas_tool import present_chart

# Automatically handles:
# - Agent resolution
# - Governance checks
# - Execution records
# - Canvas audit entries

await present_chart(
    user_id=user_id,
    chart_type="bar_chart",
    data=data,
    title=title,
    agent_id=agent_id,  # Optional
    workspace_id=workspace_id
)
```

### Pattern 3: Form Submission with Governance

```python
from core.models import CanvasAudit

# 1. Get originating execution
originating_exec = db.query(AgentExecution).filter(
    AgentExecution.id == submission.agent_execution_id
).first()

# 2. Check governance (submit_form = SUPERVISED+)
check = governance.can_perform_action(
    originating_exec.agent_id,
    "submit_form"
)

if not check["allowed"]:
    return {"error": check["reason"]}

# 3. Create submission execution
submission_exec = AgentExecution(
    agent_id=originating_exec.agent_id,
    status="running",
    triggered_by="form_submission"
)
db.add(submission_exec)
db.commit()

# 4. Create canvas audit
audit = CanvasAudit(
    agent_id=originating_exec.agent_id,
    agent_execution_id=submission_exec.id,
    action="submit",
    governance_check_passed=check["allowed"]
)
db.add(audit)

# 5. Process form data
# ... handle form ...

# 6. Mark completion
submission_exec.status = "completed"
```

## Testing

### Run Unit Tests
```bash
pytest backend/tests/test_governance_streaming.py -v
```

### Run Performance Tests
```bash
pytest backend/tests/test_governance_performance.py -v -s
```

### Manual Testing

1. Create test agents:
```python
from core.models import AgentRegistry, AgentStatus

student = AgentRegistry(
    name="Test Student",
    category="test",
    module_path="test",
    class_name="Student",
    status=AgentStatus.STUDENT.value
)

intern = AgentRegistry(
    name="Test Intern",
    category="test",
    module_path="test",
    class_name="Intern",
    status=AgentStatus.INTERN.value
)
```

2. Test streaming:
```bash
curl -X POST http://localhost:8000/api/atom-agent/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Hello",
    "user_id": "user-1",
    "agent_id": "student-agent-id"
  }'
```

3. Verify audit trail:
```sql
SELECT * FROM agent_executions WHERE agent_id = 'student-agent-id';
SELECT * FROM canvas_audit WHERE agent_id = 'student-agent-id';
```

## Troubleshooting

### Issue: "Agent not permitted" error

**Check**:
```python
governance = AgentGovernanceService(db)
check = governance.can_perform_action(agent_id, action_type)
print(check)  # See why it's blocked
```

**Common causes**:
- Agent maturity too low for action complexity
- Agent not found in registry
- Action not in ACTION_COMPLEXITY mapping

### Issue: Missing agent_executions

**Check**:
```sql
-- Verify execution records created
SELECT * FROM agent_executions
WHERE agent_id = 'your-agent-id'
ORDER BY created_at DESC LIMIT 10;
```

**Common causes**:
- Governance disabled (check feature flags)
- Agent resolution failed
- Database commit failed

### Issue: Low cache hit rate

**Check**:
```python
from core.governance_cache import get_governance_cache
cache = get_governance_cache()
print(cache.get_stats())
```

**Solutions**:
- Increase TTL: `GovernanceCache(ttl_seconds=120)`
- Increase max size: `GovernanceCache(max_size=2000)`
- Check cache invalidation logic

## Performance Targets

| Metric | Target | How to Check |
|--------|--------|--------------|
| Cached lookup | <10ms | `cache.get_stats()` |
| Cache hit rate | >90% | `cache.get_stats()['hit_rate']` |
| Streaming overhead | <50ms | Measure before/after governance |
| Agent resolution | <50ms | Measure resolution latency |

## Database Schema

### agent_executions
```sql
CREATE TABLE agent_executions (
    id VARCHAR PRIMARY KEY,
    agent_id VARCHAR NOT NULL,
    workspace_id VARCHAR NOT NULL,
    status VARCHAR DEFAULT 'running',
    input_summary TEXT,
    output_summary TEXT,
    triggered_by VARCHAR DEFAULT 'manual',
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds FLOAT DEFAULT 0.0,
    error_message TEXT
);

-- Indexes for performance
CREATE INDEX ix_agent_executions_agent_workspace ON agent_executions (agent_id, workspace_id);
CREATE INDEX ix_agent_executions_status ON agent_executions (status);
CREATE INDEX ix_agent_executions_started_at ON agent_executions (started_at);
```

### canvas_audit
```sql
CREATE TABLE canvas_audit (
    id VARCHAR PRIMARY KEY,
    workspace_id VARCHAR NOT NULL,
    agent_id VARCHAR,
    agent_execution_id VARCHAR,
    user_id VARCHAR NOT NULL,
    canvas_id VARCHAR,
    component_type VARCHAR NOT NULL,
    component_name VARCHAR,
    action VARCHAR NOT NULL,
    metadata JSON,
    governance_check_passed BOOLEAN,
    created_at TIMESTAMP
);
```

## Related Files

- `backend/core/agent_context_resolver.py` - Agent resolution logic
- `backend/core/governance_cache.py` - Performance cache
- `backend/core/agent_governance_service.py` - Governance checks
- `backend/core/atom_agent_endpoints.py` - Streaming endpoint
- `backend/tools/canvas_tool.py` - Canvas functions
- `backend/api/canvas_routes.py` - Form submission
- `backend/core/llm/byok_handler.py` - BYOK streaming

## Support

For issues or questions:
1. Check `GOVERNANCE_INTEGRATION_COMPLETE.md` for detailed documentation
2. Review test files for usage examples
3. Check logs for governance-related messages
4. Verify feature flags are set correctly
