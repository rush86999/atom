# Agent Governance & Learning Integration with Canvas Hub

**Date**: February 2, 2026
**Related**: Canvas Real-Time Agent Guidance System

---

## Overview

The Canvas Hub acts as the central transparency layer for agent governance, enabling:
1. **Real-time governance monitoring** - See what agents are doing live
2. **Attribution tracking** - Every action is attributable to an agent
3. **Learning feedback loops** - User responses improve agent confidence
4. **Audit trail enrichment** - Canvas operations provide context for governance

---

## Integration Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Canvas Hub                                │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              Real-Time Operation Display                  │  │
│  │  • What agent is doing (plain English)                    │  │
│  │  • Why agent is doing it (justification)                  │  │
│  │  • Progress tracking (step X of Y)                        │  │
│  │  • Live operation log                                     │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                   Agent Governance System                       │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │  Agent Context   │  │  Governance      │  │  Maturity    │  │
│  │  Resolver        │  │  Cache (<1ms)    │  │  Levels      │  │
│  └──────────────────┘  └──────────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                   Agent Learning System                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐  │
│  │  Confidence      │  │  Error           │  │  User        │  │
│  │  Scoring         │  │  Resolution      │  │  Feedback    │  │
│  │                  │  │  Learning        │  │  Integration │  │
│  └──────────────────┘  └──────────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Governance Integration

### Real-Time Governance Monitoring

Every canvas operation includes governance metadata:

```typescript
// Canvas operation display
{
  operation_id: "op_123",
  agent_id: "agent_456",
  agent_name: "Integration Assistant",
  agent_maturity: "INTERN",  // ← Governance level displayed
  governance_check: {
    allowed: true,
    permission: "present_canvas",
    complexity: 2,  // MODERATE
    required_maturity: "INTERN+",
    actual_maturity: "INTERN"  // ✅ Passed
  },
  operation: {
    type: "integration_connect",
    what: "Connecting to Slack",
    why: "To enable automated workflows",
    progress: 60
  }
}
```

### Governance Enforcement at Canvas Level

```python
# tools/agent_guidance_canvas_tool.py

async def start_operation(user_id, agent_id, operation_type, context):
    # 1. Resolve agent context
    agent = resolver.resolve_agent(agent_id)

    # 2. Check maturity level
    if agent.maturity < AgentMaturity.INTERN:
        logger.warning(f"Agent {agent_id} not mature enough for canvas operations")
        return None  # Block operation

    # 3. Check specific permission
    governance_check = await governance.check_action_permission(
        agent_id=agent_id,
        action="present_canvas",
        action_complexity=2  # MODERATE
    )

    if not governance_check["allowed"]:
        # Governance failure - log and block
        await create_audit(
            action="start_operation",
            governance_check_passed=False,
            reason=governance_check["reason"]
        )
        return None

    # 4. Proceed with operation
    operation_id = await broadcast_to_canvas(...)
```

### Maturity-Based Capabilities

| Maturity | Canvas Capabilities | Governance Requirements |
|----------|---------------------|------------------------|
| **STUDENT** | View operations (read-only) | Attribution required |
| **INTERN** | Present operations, switch views | Permission checks |
| **SUPERVISED** | Handle errors, process responses | State change tracking |
| **AUTONOMOUS** | Multi-view orchestration, auto-fix | Full audit trail |

---

## 2. Learning Integration

### Confidence Scoring from Canvas Interactions

User responses to agent requests feed directly into confidence scoring:

```python
# core/agent_request_manager.py

async def handle_response(user_id, request_id, response):
    # Log the response
    request_log = user_response = response
    request_log.responded_at = datetime.utcnow()
    request_log.response_time_seconds = (
        datetime.utcnow() - request_log.created_at
    ).total_seconds()

    # 🎯 LEARNING: Update agent confidence
    if response.get("action") == "approve":
        # User approved → increase confidence
        await confidence_scorer.record_positive_outcome(
            agent_id=request_log.agent_id,
            operation_type=request_log.request_type,
            user_response=response
        )
    elif response.get("action") == "deny":
        # User denied → decrease confidence
        await confidence_scorer.record_negative_outcome(
            agent_id=request_log.agent_id,
            operation_type=request_log.request_type,
            reason=response.get("reason")
        )

    # Trigger event
    self._pending_requests[request_id].set()
```

### Error Resolution Learning

```python
# core/error_guidance_engine.py

async def track_resolution(
    error_type,
    resolution_attempted,
    success,
    user_feedback
):
    # Save resolution outcome
    resolution = OperationErrorResolution(
        error_type=error_type,
        resolution_attempted=resolution_attempted,
        success=success,
        user_feedback=user_feedback,
        agent_suggested=True
    )
    db.add(resolution)

    # 🎯 LEARNING: Update agent confidence based on error handling
    if success:
        await confidence_scorer.record_error_resolution_success(
            error_type=error_type,
            resolution=resolution_attempted
        )
    else:
        await confidence_scorer.record_error_resolution_failure(
            error_type=error_type,
            resolution=resolution_attempted,
            feedback=user_feedback
        )
```

### Operation Completion Learning

```python
# tools/agent_guidance_canvas_tool.py

async def complete_operation(user_id, operation_id, status):
    tracker = db.query(AgentOperationTracker).filter(
        AgentOperationTracker.operation_id == operation_id
    ).first()

    tracker.status = status
    tracker.completed_at = datetime.utcnow()

    # 🎯 LEARNING: Update agent confidence
    if status == "completed":
        await confidence_scorer.record_operation_success(
            agent_id=tracker.agent_id,
            operation_type=tracker.operation_type
        )
    elif status == "failed":
        await confidence_scorer.record_operation_failure(
            agent_id=tracker.agent_id,
            operation_type=tracker.operation_type
        )
```

---

## 3. Attribution & Audit Trail

### Complete Attribution Chain

Every canvas operation is fully attributable:

```sql
-- Canvas audit entry
CREATE TABLE canvas_audit (
    id VARCHAR PRIMARY KEY,
    workspace_id VARCHAR,
    agent_id VARCHAR,                    -- ✅ Attributable
    agent_execution_id VARCHAR,           -- ✅ Linked to execution
    user_id VARCHAR NOT NULL,
    canvas_id VARCHAR,
    session_id VARCHAR,                   -- ✅ Session isolation
    component_type VARCHAR NOT NULL,
    component_name VARCHAR,
    action VARCHAR NOT NULL,
    audit_metadata JSON,
    governance_check_passed BOOLEAN,      -- ✅ Governance outcome
    created_at DATETIME
);

-- Operation tracker
CREATE TABLE agent_operation_tracker (
    id VARCHAR PRIMARY KEY,
    agent_id VARCHAR NOT NULL,            -- ✅ Attributable
    user_id VARCHAR NOT NULL,
    operation_type VARCHAR NOT NULL,
    operation_id VARCHAR UNIQUE NOT NULL,
    status VARCHAR,
    what_explanation TEXT,                -- ✅ Plain English
    why_explanation TEXT,                 -- ✅ Justification
    started_at DATETIME,
    completed_at DATETIME
);

-- Request log
CREATE TABLE agent_request_log (
    id VARCHAR PRIMARY KEY,
    agent_id VARCHAR NOT NULL,            -- ✅ Attributable
    user_id VARCHAR NOT NULL,
    request_id VARCHAR UNIQUE NOT NULL,
    request_type VARCHAR NOT NULL,
    request_data JSON NOT NULL,
    user_response JSON,                   -- ✅ User decision
    response_time_seconds FLOAT,          -- ✅ Response latency
    created_at DATETIME,
    responded_at DATETIME,
    revoked BOOLEAN
);
```

### Audit Query Example

```python
# Get full attribution for an agent's canvas operations

def get_agent_canvas_attribution(agent_id, time_range):
    """Get complete canvas attribution for agent."""

    # 1. Get all operations
    operations = db.query(AgentOperationTracker).filter(
        AgentOperationTracker.agent_id == agent_id,
        AgentOperationTracker.started_at >= time_range.start
    ).all()

    # 2. Get all requests
    requests = db.query(AgentRequestLog).filter(
        AgentRequestLog.agent_id == agent_id,
        AgentRequestLog.created_at >= time_range.start
    ).all()

    # 3. Get audit entries
    audits = db.query(CanvasAudit).filter(
        CanvasAudit.agent_id == agent_id,
        CanvasAudit.created_at >= time_range.start
    ).all()

    return {
        "agent_id": agent_id,
        "operations": [
            {
                "operation_id": op.operation_id,
                "type": op.operation_type,
                "status": op.status,
                "what": op.what_explanation,
                "why": op.why_explanation,
                "duration": (op.completed_at - op.started_at).total_seconds()
            }
            for op in operations
        ],
        "requests": [
            {
                "request_id": req.request_id,
                "type": req.request_type,
                "user_response": req.user_response,
                "response_time": req.response_time_seconds
            }
            for req in requests
        ],
        "governance_outcomes": [
            {
                "action": audit.action,
                "passed": audit.governance_check_passed
            }
            for audit in audits
        ]
    }
```

---

## 4. Feedback Loops

### User Feedback → Agent Confidence

```python
# User thumbs up on canvas operation
{
  type: "canvas:feedback",
  data: {
    operation_id: "op_123",
    feedback_type: "thumbs_up",
    user_comment: "Great explanation, very clear!"
  }
}

↓

# Automatically updates agent confidence
await confidence_scorer.record_user_feedback(
    agent_id="agent_456",
    feedback_type="positive",
    comment="Great explanation, very clear!",
    context={"operation_type": "integration_connect"}
)
```

### Error Resolution → Learning

```python
# Error resolution success
await error_engine.track_resolution(
    error_type="auth_expired",
    resolution_attempted="Let Agent Reconnect",
    success=True,
    user_feedback="Worked perfectly!"
)

↓

# 1. Increases agent confidence in error handling
confidence_scorer.update_confidence(
    agent_id=agent_id,
    dimension="error_resolution",
    delta=+0.05
)

# 2. Learns which resolution works best
error_engine.update_resolution_success_rate(
    error_type="auth_expired",
    resolution="Let Agent Reconnect",
    success_rate+=1
)

# 3. Suggests this resolution first next time
next_suggestion = error_engine.get_suggested_resolution("auth_expired")
# Returns: "Let Agent Reconnect" (highest success rate)
```

### Operation Completion → Maturity Progression

```python
# Successful operation completion
await guidance.complete_operation(
    user_id=user_id,
    operation_id=operation_id,
    status="completed"
)

↓

# Checks if agent is ready for maturity promotion
if agent.total_successful_operations > 100:
    if agent.confidence_score > 0.7:
        # Promote from INTERN to SUPERVISED
        await governance_service.promote_agent(
            agent_id=agent_id,
            new_maturity=AgentMaturity.SUPERVISED,
            reason="Consistent successful operations with high confidence"
        )
```

---

## 5. Real-Time Governance Dashboard

Canvas Hub can display real-time governance metrics:

```typescript
// Governance Dashboard Component
{
  agent_id: "agent_456",
  agent_name: "Integration Assistant",
  current_maturity: "INTERN",
  confidence_score: 0.68,  // → 0.70 to promote to SUPERVISED

  governance_metrics: {
    total_operations: 47,
    successful_operations: 42,  // 89% success rate
    failed_operations: 5,

    user_requests: 12,
    approvals: 10,  // 83% approval rate
    denials: 2,

    error_resolutions: 8,
    successful_resolutions: 7  // 88% success rate
  },

  maturity_progress: {
    current: "INTERN",
    next: "SUPERVISED",
    progress_to_next: 0.68,  // 68% of the way there
    requirements: {
      confidence_needed: 0.70,
      operations_needed: 50,
      current_operations: 47
    }
  },

  recent_operations: [
    {
      type: "integration_connect",
      status: "completed",
      governance_check: "passed",
      user_feedback: "thumbs_up"
    },
    // ... more operations
  ]
}
```

---

## 6. Privacy & Security

### Session Isolation

Each canvas operation is session-isolated:

```python
# Start operation with session ID
await guidance.start_operation(
    user_id=user_id,
    agent_id=agent_id,
    operation_type="task",
    session_id=session_id  # ✅ Isolates to specific session
)

# Audit includes session
audit = CanvasAudit(
    session_id=session_id,  # ✅ Full traceability
    agent_id=agent_id,
    user_id=user_id,
    action="start_operation"
)
```

### Data Visibility

Canvas respects existing data visibility controls:

```python
# Check data visibility before presenting
if not data_visibility.can_present_to_user(
    agent_id=agent_id,
    user_id=user_id,
    data_type=operation_data
):
    logger.warning(f"Agent {agent_id} not allowed to present data to user {user_id}")
    return None
```

---

## 7. Integration Points

### With Agent Governance Service

```python
# Agent checks governance before presenting
governance_check = await governance.check_action_permission(
    agent_id=agent_id,
    action="present_canvas",
    action_complexity=2
)

if governance_check["allowed"]:
    await guidance.start_operation(...)
else:
    logger.warning(f"Governance check failed: {governance_check['reason']}")
```

### With Agent Context Resolver

```python
# Resolve agent context for attribution
agent = resolver.resolve_agent(agent_id)

tracker = AgentOperationTracker(
    agent_id=agent.id,
    agent_name=agent.name,
    agent_maturity=agent.maturity,  # ✅ For display
    workspace_id=agent.workspace_id
)
```

### With Confidence Scoring

```python
# Operation completion updates confidence
await confidence_scorer.record_operation_success(
    agent_id=agent_id,
    operation_type="integration_connect",
    user_engagement="high",  # User watched entire operation
    feedback="thumbs_up"
)
```

---

## Summary

The Canvas Hub provides:

1. **Real-Time Governance Visibility**
   - See what agents are doing live
   - Display maturity level and permissions
   - Show governance check outcomes

2. **Attribution & Audit Trail**
   - Every operation attributable to agent
   - Complete session isolation
   - Full audit history

3. **Learning Feedback Loops**
   - User responses → confidence updates
   - Error resolutions → learning
   - Operation outcomes → maturity progression

4. **Transparency & Trust**
   - Plain English explanations
   - Justification for actions
   - User control through requests

This creates a **virtuous cycle**: Better visibility → More trust → More autonomy → Better learning.

---

**Related Documentation**:
- [Agent Guidance Implementation](./AGENT_GUIDANCE_IMPLEMENTATION.md)
- [Agent Governance Service](../backend/core/agent_governance_service.py)
- [Confidence Scoring](../backend/core/confidence_scorer.py)
