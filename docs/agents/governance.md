# Agent Governance System

**Last Updated**: April 7, 2026

---

## Overview

The Agent Governance System is a comprehensive framework that ensures all AI agent actions are attributable, governable, and auditable. It provides multi-tiered maturity levels, permission checks, complete audit trails, and integration with real-time monitoring through Canvas Hub.

---

## Table of Contents

1. [Architecture](#architecture)
2. [Maturity Levels](#maturity-levels)
3. [Governance Checks](#governance-checks)
4. [Canvas Hub Integration](#canvas-hub-integration)
5. [Learning & Confidence Scoring](#learning--confidence-scoring)
6. [Audit Trails](#audit-trails)
7. [Capability Graduation](#capability-graduation)
8. [Performance & Caching](#performance--caching)
9. [Configuration](#configuration)
10. [Best Practices](#best-practices)

---

## Architecture

```
User Request → AgentContextResolver → GovernanceCache → AgentGovernanceService → Action Execution
                                                                         ↓
                                                                    Audit Logs
                                                                         ↓
                                                                    Canvas Hub
                                                              (Real-Time Monitoring)
```

### Core Components

1. **AgentContextResolver** (`core/agent_context_resolver.py`)
   - Multi-layer fallback to determine which agent governs a request
   - Fallback chain: explicit agent_id → session agent → workspace default → system default

2. **AgentGovernanceService** (`core/agent_governance_service.py`)
   - Manages agent lifecycle and permissions
   - Performs maturity-based action validation
   - Handles approval workflows

3. **GovernanceCache** (`core/governance_cache.py`)
   - High-performance caching for governance checks
   - Sub-millisecond lookup times
   - 95%+ cache hit rate

4. **Canvas Hub** (`tools/agent_guidance_canvas_tool.py`)
   - Real-time operation monitoring and display
   - User feedback collection for learning
   - Multi-view orchestration

---

## Maturity Levels

| Level | Confidence | Automated Triggers | Capabilities |
|-------|-----------|-------------------|--------------|
| **STUDENT** | <0.5 | **BLOCKED** → Route to Training | Read-only (charts, markdown) |
| **INTERN** | 0.5-0.7 | **PROPOSAL ONLY** → Human Approval Required | Streaming, form presentation |
| **SUPERVISED** | 0.7-0.9 | **RUN UNDER SUPERVISION** → Real-time Monitoring | Form submissions, state changes |
| **AUTONOMOUS** | >0.9 | **FULL EXECUTION** → No Oversight | Full autonomy, all actions |

### Maturity Progression

```
STUDENT → (10 episodes, 50% intervention rate, 0.70 constitutional score) → INTERN
  ↓
INTERN → (25 episodes, 20% intervention rate, 0.85 constitutional score) → SUPERVISED
  ↓
SUPERVISED → (50 episodes, 0% intervention rate, 0.95 constitutional score) → AUTONOMOUS
```

### Action Complexity Levels

| Level | Examples | Required Maturity |
|-------|----------|-------------------|
| **1 (LOW)** | Presentations, read-only | STUDENT+ |
| **2 (MODERATE)** | Streaming, moderate actions | INTERN+ |
| **3 (HIGH)** | State changes, submissions | SUPERVISED+ |
| **4 (CRITICAL)** | Deletions, payments | AUTONOMOUS only |

---

## Governance Checks

### Checking Permissions

```python
from core.agent_governance_service import AgentGovernanceService
from core.database import SessionLocal

db = SessionLocal()
governance = AgentGovernanceService(db)

# Check if agent can perform action
check = governance.can_perform_action(
    agent_id="agent_123",
    action_type="social_media_post"
)

if check["allowed"]:
    # Proceed with action
    pass
else:
    # Handle denial
    if check.get("requires_human_approval"):
        # Request approval
        pass
```

### Response Format

```python
{
    "allowed": bool,           # Whether action is permitted
    "requires_human_approval": bool,  # Whether approval is needed
    "reason": str,             # Explanation for decision
    "agent_maturity": str,     # Current maturity level
    "action_complexity": int   # Complexity of action (1-4)
}
```

### Agent Resolution

```python
from core.agent_context_resolver import AgentContextResolver

resolver = AgentContextResolver(db)

# Resolve agent for request
agent, context = await resolver.resolve_agent_for_request(
    user_id=str(user.id),
    requested_agent_id=agent_id,  # Optional explicit agent
    session_id=session_id,         # Optional session context
    action_type="chat"
)
```

**Resolution Path:**
```
1. Explicit agent_id (if provided)
   └─> Return agent or record "explicit_agent_id_not_found"

2. Session context agent
   └─> Return agent or record "no_session_agent"

3. System default "Chat Assistant"
   └─> Return agent or record "resolution_failed"
```

---

## Canvas Hub Integration

The Canvas Hub acts as the central transparency layer for agent governance.

### Real-Time Governance Monitoring

Every canvas operation includes governance metadata:

```typescript
{
  operation_id: "op_123",
  agent_id: "agent_456",
  agent_name: "Integration Assistant",
  agent_maturity: "INTERN",
  governance_check: {
    allowed: true,
    permission: "present_canvas",
    complexity: 2,
    required_maturity: "INTERN+",
    actual_maturity: "INTERN"
  },
  operation: {
    type: "integration_connect",
    what: "Connecting to Slack",
    why: "To enable automated workflows",
    progress: 60
  }
}
```

### Maturity-Based Capabilities

| Maturity | Canvas Capabilities | Governance Requirements |
|----------|---------------------|------------------------|
| **STUDENT** | View operations (read-only) | Attribution required |
| **INTERN** | Present operations, switch views | Permission checks |
| **SUPERVISED** | Handle errors, process responses | State change tracking |
| **AUTONOMOUS** | Multi-view orchestration, auto-fix | Full audit trail |

### Governance Enforcement

```python
async def start_operation(user_id, agent_id, operation_type, context):
    # 1. Resolve agent context
    agent = resolver.resolve_agent(agent_id)

    # 2. Check maturity level
    if agent.maturity < AgentMaturity.INTERN:
        logger.warning(f"Agent {agent_id} not mature enough for canvas operations")
        return None

    # 3. Check specific permission
    governance_check = await governance.check_action_permission(
        agent_id=agent_id,
        action="present_canvas",
        action_complexity=2
    )

    if not governance_check["allowed"]:
        await create_audit(
            action="start_operation",
            governance_check_passed=False,
            reason=governance_check["reason"]
        )
        return None

    # 4. Proceed with operation
    operation_id = await broadcast_to_canvas(...)
```

---

## Learning & Confidence Scoring

### Confidence Scoring from Canvas Interactions

User responses to agent requests feed directly into confidence scoring:

```python
async def handle_response(user_id, request_id, response):
    request_log.responded_at = datetime.utcnow()
    request_log.response_time_seconds = (
        datetime.utcnow() - request_log.created_at
    ).total_seconds()

    # Update agent confidence
    if response.get("action") == "approve":
        await confidence_scorer.record_positive_outcome(
            agent_id=request_log.agent_id,
            operation_type=request_log.request_type,
            user_response=response
        )
    elif response.get("action") == "deny":
        await confidence_scorer.record_negative_outcome(
            agent_id=request_log.agent_id,
            operation_type=request_log.request_type,
            reason=response.get("reason")
        )
```

### Error Resolution Learning

```python
async def track_resolution(
    error_type,
    resolution_attempted,
    success,
    user_feedback
):
    resolution = OperationErrorResolution(
        error_type=error_type,
        resolution_attempted=resolution_attempted,
        success=success,
        user_feedback=user_feedback,
        agent_suggested=True
    )
    db.add(resolution)

    if success:
        await confidence_scorer.record_error_resolution_success(
            error_type=error_type,
            resolution=resolution_attempted
        )
```

### GEA: Group-Evolving Skills (Self-Writing)

Atom uses **Group-Evolving Agents (GEA)** to collectively "write" its own skills via **Evolution Directives**.

```python
async def run_evolution_cycle(tenant_id):
    # 1. Experience Sharing
    pool = reflection_svc.gather_group_experience_pool(parent_ids)

    # 2. Reflection Module -> Generate "Evolution Directives"
    dirs = await reflection_svc.reflect_and_generate_directives(pool)

    # 3. Apply Directives
    evolved_config = await UpdatingModule.apply(dirs)

    # 4. Benchmark & Promote Winner
    if benchmark.passed(evolved_config):
        return promote_winner(evolved_config)
```

**Key Features:**
- **Collective Intelligence**: Agents share experience pools
- **Autonomous Directives**: Reflection Module generates behavior modifications
- **Sandboxed Evolution**: All configurations benchmarked before deployment

### On-the-Fly Skill Generation

Multi-layered skill creation mechanism:

| Layer | Mechanism | Application |
|-------|-----------|-------------|
| **Instructional Skills** | Natural language directives | System prompt modifications |
| **Functional Skills** | Python code written by agents | Runtime module loading & hot-reload |
| **Formal Skills** | Structured skill packaging | Stabilized packages for audit |

---

## Capability Graduation

Individual capabilities progress independently of overall agent maturity.

### Graduation Thresholds

| Capability Level | Successful Uses | Confidence | Permissions |
|-----------------|-----------------|------------|-------------|
| **STUDENT → INTERN** | 5 operations | >70% | Canvas presentation, basic tools |
| **INTERN → SUPERVISED** | 20 operations | >80% | Advanced integrations, error recovery |
| **SUPERVISED → AUTONOMOUS** | 50 operations | >90% | Shell access, self-writing skills |

### Implementation

```python
# Track capability usage
graduation_service.record_usage(
    agent_id="agent_123",
    capability_name="browser_automation",
    success=True
)

# Automatic progression
# 5 successes → STUDENT → INTERN
# 20 successes → INTERN → SUPERVISED
# 50 successes → SUPERVISED → AUTONOMOUS
```

### Storage

- **capability_stats**: Success/total counts per capability
- **capability_maturities**: Current maturity level per capability
- Stored in `AgentRegistry.properties` JSON field

---

## Audit Trails

All state-changing operations create comprehensive audit entries.

### Social Media Audit

```python
from core.models import SocialMediaAudit

audit = SocialMediaAudit(
    user_id=str(user.id),
    agent_id=agent_id,
    agent_execution_id=execution_id,
    platform="twitter",
    action_type="post",
    content=post_content,
    success=True,
    agent_maturity="SUPERVISED",
    governance_check_passed=True
)
```

### Financial Audit

```python
from core.models import FinancialAudit

audit = FinancialAudit(
    user_id=str(user.id),
    agent_id=agent_id,
    account_id=account_id,
    action_type="update",
    changes={"balance": {"old": "100.00", "new": "200.00"}},
    success=True,
    agent_maturity="AUTONOMOUS",
    governance_check_passed=True
)
```

### Canvas Audit

```python
audit = CanvasAudit(
    session_id=session_id,
    agent_id=agent_id,
    user_id=user_id,
    action="start_operation",
    governance_check_passed=True
)
```

### Complete Attribution Chain

Every canvas operation is fully attributable through:
- `AgentOperationTracker` - Operation tracking
- `AgentRequestLog` - User requests and responses
- `CanvasAudit` - Audit trail with governance outcomes

---

## Performance & Caching

### Governance Cache

```python
from core.governance_cache import get_governance_cache

cache = get_governance_cache()

# Cached check (<1ms)
allowed = cache.is_allowed(agent_id, action_type)
```

**Metrics:**
- Cache hit rate: 95%+
- Average lookup time: <1ms
- P99 latency: 0.027ms
- Throughput: 616k ops/s

---

## Configuration

### Environment Variables

```bash
# Governance Settings
STREAMING_GOVERNANCE_ENABLED=true
CANVAS_GOVERNANCE_ENABLED=true
FORM_GOVERNANCE_ENABLED=true
BROWSER_GOVERNANCE_ENABLED=true

# Emergency Bypass (NEVER enable in production)
EMERGENCY_GOVERNANCE_BYPASS=false
```

### Feature Flags

```python
from core.feature_flags import FeatureFlags

if FeatureFlags.should_enforce_governance('form'):
    # Perform governance check
    pass
```

---

## Best Practices

### 1. Always Resolve Agents

```python
# GOOD
resolver = AgentContextResolver(db)
agent, context = await resolver.resolve_agent_for_request(
    user_id=str(user.id),
    requested_agent_id=agent_id,
    action_type=action_type
)

# BAD - Skip agent resolution
agent = db.query(AgentRegistry).filter(
    AgentRegistry.id == agent_id
).first()
```

### 2. Always Create Audit Entries

```python
# GOOD
audit = SocialMediaAudit(
    user_id=str(user.id),
    agent_id=agent.id,
    platform=platform,
    action_type="post",
    content=content,
    success=result.get("success"),
    agent_maturity=agent.status,
    governance_check_passed=governance_check["allowed"]
)
db.add(audit)
db.commit()

# BAD - No audit trail
post_to_twitter(content)
```

### 3. Use Standard Error Handling

```python
# GOOD
if not governance_check["allowed"]:
    raise router.permission_denied_error(
        "social media",
        "post",
        details={"reason": governance_check["reason"]}
    )

# BAD
raise HTTPException(status_code=403, detail="Not allowed")
```

---

## Governance by Feature

### Social Media Posting
**Required Maturity**: SUPERVISED+

### Financial Operations
**Create/Update**: SUPERVISED+
**Delete**: AUTONOMOUS only

### Device Capabilities
**Camera/Location/Notifications**: INTERN+
**Screen Recording**: SUPERVISED+
**Command Execution**: AUTONOMOUS only

### Browser Automation
**Required Maturity**: INTERN+

### Canvas Operations
**Present**: STUDENT+
**Submit Form**: SUPERVISED+
**Execute Actions**: SUPERVISED+

---

## Related Documentation

- **[Agent Graduation Guide](./graduation.md)** - Learning and promotion framework
- **[Student Training](./training.md)** - Training workflow
- **[Agent Guidance System](./guidance-system.md)** - Real-time monitoring
- **[Episodic Memory](../intelligence/episodic-memory.md)** - Agent learning system
- **[Canvas Reference](../canvas/reference.md)** - Canvas operations

---

## Summary

The Agent Governance System provides:

✅ **Attribution**: Every action tracked to specific agent and user
✅ **Control**: Maturity-based permissions prevent unauthorized actions
✅ **Audit**: Complete audit trail for compliance and debugging
✅ **Performance**: Sub-millisecond governance checks via caching
✅ **Transparency**: Real-time monitoring through Canvas Hub
✅ **Learning**: Confidence scoring and capability graduation
✅ **Flexibility**: Configurable maturity levels and action complexity

**Key Principle**: All AI actions must be attributable, governable, and auditable.
