# Agent Governance System

**Last Updated**: June 18, 2026

---

## Overview

The Agent Governance System is a comprehensive framework that ensures all AI agent actions are attributable, governable, and auditable. It provides multi-tiered maturity levels, permission checks, complete audit trails, and integration with real-time monitoring through Canvas Hub.

### 🆕 2026 Enhanced Governance

Atom's governance system now includes **advanced three-layer governance architecture** based on enterprise workflow research:

- **Three-Layer Governance** - OPERATIONAL, TACTICAL, and STRATEGIC decision layers
- **Policy Engine** - Context-aware policy evaluation with priority resolution
- **Governance-as-a-Service** - Multi-tenant governance API with caching

**Usage:**
```python
from core.governance.dynamic_governance import DynamicGovernanceManager, GovernanceLayer

manager = DynamicGovernanceManager()

# Operational layer (fast, automated)
decision = manager.decide(
    agent_id="agent_123",
    action="read_chart",
    layer=GovernanceLayer.OPERATIONAL
)
```

See [Enhanced Governance](#enhanced-governance-2026) section for details.

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
9. [Enhanced Governance (2026)](#enhanced-governance-2026)
10. [Configuration](#configuration)
11. [Best Practices](#best-practices)

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

> ⚠️ **Scope warning — tier is routing, not security.**
> The maturity system decides what an agent is *normally allowed* to do based
> on its past clean-execution history. It is **not** a security boundary: it
> does not bound the blast radius of a compromised run, and a prompt-injected
> agent at any tier will use the full scope that tier permits on the very next
> call. For blast-radius defense (filesystem scope, tool whitelist, egress
> allowlist, resource caps, tripwires) — now **shipped (Rounds 43-47)** — see
> [`docs/architecture/SANDBOX_LAYER.md`](../architecture/SANDBOX_LAYER.md)
> (authoritative implementation doc),
> [`docs/security/TRUST_VS_SANDBOX.md`](../security/TRUST_VS_SANDBOX.md)
> (why this layer is necessary), and
> [`docs/security/PROMPT_INJECTION_DEFENSE_PLAN.md`](../security/PROMPT_INJECTION_DEFENSE_PLAN.md)
> (original engineering plan, status: implemented).
> **Tier gates permission; sandbox gates capability. Both are required.**

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

Note: "Required Maturity" gates **which agents may attempt** the action — it
does not bound **what an agent attempting it can reach**. A hijacked
AUTONOMOUS agent has every Level-4 action available to it on every call.
Bounding blast radius is the job of the sandbox layer, not the complexity
table.

### Pre-Action Match-Confidence Gating (June 2026)

The maturity system above routes actions by an agent's **historical** clean
executions. It does not look at **current-call certainty**. A prompt-injected
AUTONOMOUS agent at 0.95 confidence can still click an ambiguous selector
directly — maturity gating alone can't catch that.

The **[Pre-Action Match-Confidence Layer](../architecture/MATCH_CONFIDENCE.md)**
is a complementary gate that runs at action time, not graduation time:

- `browser_click` / `browser_fill_form` resolve the selector via
  `page.locator()` and score it: `high` / `partial` / `ambiguous`.
- When `MATCH_CONFIDENCE_FORCE_PROPOSAL=true` AND level ∈ {partial, ambiguous},
  the action routes through `ProposalService.create_action_proposal` instead
  of executing — **including for AUTONOMOUS-tier agents**.
- Shadow mode is the default (`FORCE_PROPOSAL=false`): computation and audit
  always on, gating off. See the rollout plan in
  **[MATCH_CONFIDENCE.md § Rollout](../architecture/MATCH_CONFIDENCE.md#rollout-plan)**.

Per-agent opt-out column on `AgentRegistry.match_confidence_gating_enabled`
(migration `20260628_add_match_confidence_gating_flag`) — `NULL` falls
through to the global flag, `TRUE`/`FALSE` overrides per row.

**Same caveat applies**: match-confidence is not a sandbox. An action that
resolves `high` still executes directly with full tier scope. See
[`docs/security/TRUST_VS_SANDBOX.md`](../security/TRUST_VS_SANDBOX.md).

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

**Arbor Framework Integration**: For code generation and skill optimization, the governance system integrates with Arbor's Hypothesis Tree Refinement:

```python
from core.hypothesis_tree import CodeHypothesisNode, HypothesisTree

# Agent generates skill proposal with Arbor validation
tree = HypothesisTree(
    task_description="Generate skill for API retry logic",
    tier="solo"
)

# Arbor validates code quality before skill approval
node = CodeHypothesisNode(
    code_diff=proposed_skill_code,
    language="python",
    cyclomatic_complexity=5,
    code_coverage=0.85,
    security_vulnerabilities=0
)

# Only skills passing Arbor checks are approved
if node.calculate_promise_score() > 0.8:
    approve_skill_proposal()
```

**Governance Benefits**:
- **Quality Gates**: Arbor validates code before governance approval
- **Security**: Prunes skills with vulnerabilities or complexity violations
- **Cost Control**: Respects budget limits for skill generation
- **Learning**: Negative constraints prevent repeated failure patterns

**See Also**: Arbor Framework - Complete HTR documentation

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

## Enhanced Governance (2026)

### Three-Layer Governance Architecture

Based on [Governance-as-a-Service: Multi-Agent Framework](https://arxiv.org/html/2508.18765v1)

| Layer | Scope | Response Time | Human Involvement |
|-------|-------|---------------|-------------------|
| **OPERATIONAL** | Fast, routine decisions | <10ms | Fully automated |
| **TACTICAL** | Adaptive, performance-based | <100ms | Minimal (<5%) |
| **STRATEGIC** | Policy, cross-tenant decisions | Variable | Human-in-the-loop |

**Usage:**
```python
from core.governance.dynamic_governance import DynamicGovernanceManager, GovernanceLayer

manager = DynamicGovernanceManager()

# Operational layer (fast, automated)
decision = manager.decide(
    agent_id="agent_123",
    action="read_chart",
    layer=GovernanceLayer.OPERATIONAL
)

# Strategic layer (human-in-the-loop for policy changes)
decision = manager.decide(
    agent_id="agent_123",
    action="delete_database",
    layer=GovernanceLayer.STRATEGIC
)
```

### Policy Engine

Context-aware policy evaluation with priority-based resolution:

```python
from core.governance.policy_engine import PolicyEngine, GovernancePolicy

engine = PolicyEngine()

# Register policy with priority
policy = GovernancePolicy(
    policy_id="data_access_policy",
    priority=PolicyPriority.HIGH,
    condition="action.startswith('delete_')",
    effect="DENY",
    layer="operational"
)

engine.register_policy(policy)

# Evaluate request
result = engine.evaluate(
    agent_id="agent_123",
    action="delete_user_data",
    layer="operational",
    context={"resource_type": "user"}
)
```

### Governance-as-a-Service

Multi-tenant governance API with caching and rate limiting:

```python
from core.governance.governance_service import GovernanceAsAService

service = GovernanceAsAService()

# Multi-tenant permission check
response = service.check_permission(
    tenant_id="tenant_123",
    user_id="user_456",
    agent_id="agent_789",
    action="submit_form",
    resource="customer_data"
)
```

### Performance Metrics (Enhanced)

| Metric | Target | Status |
|--------|--------|--------|
| Decision Latency P50 | <10ms | ✅ Tests passing |
| Decision Latency P95 | <50ms | ✅ Tests passing |
| Human Intervention Rate | <5% operational | ✅ Framework ready |
| Policy Evaluation | <100ms | ✅ Tests passing |

See [VALIDATION_METRICS.md](../../backend/docs/VALIDATION_METRICS.md) for complete validation framework.

### Migration Notes

**From Original to Enhanced:**
1. **Original governance still works** - No breaking changes
2. **Enhanced features opt-in** - Use new modules when needed
3. **Three-layer architecture** - Add for complex multi-tenant scenarios
4. **Policy engine** - Replace hardcoded action complexity
5. **Governance-as-a-Service** - Use for multi-tenant API exposure

**When to Use Each Approach:**

| Scenario | Recommended Approach |
|----------|---------------------|
| Single-tenant, simple governance | Original `AgentGovernanceService` |
| Multi-tenant with policies | `GovernanceAsAService` |
| Complex decision layers | `DynamicGovernanceManager` |
| Policy-based evaluation | `PolicyEngine` |
| Production validation | See `VALIDATION_METRICS.md` |

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
- **[Arbor Framework](../architecture/ARBOR_FRAMEWORK.md)** - Hypothesis Tree Refinement for optimization learning

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
