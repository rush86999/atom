# Governance System

Agent maturity levels, permissions, and governance controls with 2026 enhancements.

## 📚 Quick Navigation

- **[Governance Quick Reference](GOVERNANCE_QUICK_REFERENCE.md)** - Quick reference guide
- **Validation Metrics** - Performance validation framework

## 🎯 Maturity Levels (Foundation)

### 4-Tier Agent Governance

| Level | Confidence | Automated Triggers | Capabilities |
|-------|-----------|-------------------|--------------|
| **STUDENT** | <0.5 | **BLOCKED** | Read-only (charts, markdown) |
| **INTERN** | 0.5-0.7 | **PROPOSAL ONLY** | Streaming, form presentation |
| **SUPERVISED** | 0.7-0.9 | **RUN UNDER SUPERVISION** | Form submissions, state changes |
| **AUTONOMOUS** | >0.9 | **FULL EXECUTION** | Full autonomy, all actions |

### Action Complexity

| Complexity | Examples | Required Maturity |
|------------|----------|-------------------|
| 1 (LOW) | Presentations, read operations | STUDENT+ |
| 2 (MODERATE) | Streaming, API calls | INTERN+ |
| 3 (HIGH) | State changes, deletions | SUPERVISED+ |
| 4 (CRITICAL) | Critical operations | AUTONOMOUS only |

---

## 🆕 2026 Enhanced Governance

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

---

## 🔒 Core Governance Features

### Trigger Interceptor
- **Maturity Routing**: Routes triggers based on agent maturity
- **Proposal Workflow**: INTERN agents propose actions for approval
- **Supervision Mode**: SUPERVISED agents run under real-time monitoring
- **Full Autonomy**: AUTONOMOUS agents execute without oversight

### Agent Governance
- **Permissions**: Maturity-based access control
- **Audit Trail**: All actions logged and attributable
- **Performance Monitoring**: Sub-millisecond governance checks (<1ms P99)
- **Cache Layer**: High-performance governance cache with >90% hit rate

### Training System
- **AI-Powered Training**: LLM-based training duration estimation
- **Intervention Tracking**: Track human interventions
- **Graduation Criteria**: Constitutional compliance validation
- **Promotion Workflow**: Move agents through maturity levels

---

## 📊 Performance Metrics

### Foundation (Original)

| Metric | Target | Current |
|--------|--------|---------|
| Governance check (cached) | <10ms | 0.027ms P99 ✅ |
| Agent resolution | <50ms | 0.084ms avg ✅ |
| Cache hit rate | >90% | 95% ✅ |
| Cache throughput | >5k ops/s | 616k ops/s ✅ |

### Enhanced (2026)

| Metric | Target | Status |
|--------|--------|--------|
| Decision Latency P50 | <10ms | ✅ Tests passing |
| Decision Latency P95 | <50ms | ✅ Tests passing |
| Human Intervention Rate | <5% operational | ✅ Framework ready |
| Policy Evaluation | <100ms | ✅ Tests passing |

See VALIDATION_METRICS.md for complete validation framework.

---

## 🔧 Quick Start

### Foundation (Original Approach)

```python
from core.agent_governance_service import AgentGovernanceService

governance = AgentGovernanceService()

# Check agent permissions
can_execute = governance.can_execute_action(
    agent_id="agent_123",
    action="submit_form",
    complexity=3
)

# Get maturity level
maturity = governance.get_agent_maturity("agent_123")
```

### Enhanced (2026 Approach)

```python
# Three-layer governance
from core.governance.dynamic_governance import DynamicGovernanceManager

manager = DynamicGovernanceManager()
decision = manager.decide(
    agent_id="agent_123",
    action="submit_form",
    context={"maturity": "SUPERVISED"}
)

# Policy-based evaluation
from core.governance.policy_engine import get_policy_engine

engine = get_policy_engine()
result = engine.evaluate(
    agent_id="agent_123",
    action="submit_form",
    layer="operational",
    context={"resource": "form_data"}
)

# Governance-as-a-Service
from core.governance.governance_service import get_governance_service

service = get_governance_service()
response = service.check_permission(
    tenant_id="tenant_123",
    user_id="user_456",
    agent_id="agent_123",
    action="submit_form",
    resource="form_data"
)
```

---

## 🔄 Migration Notes

### From Original to Enhanced

1. **Original governance still works** - No breaking changes
2. **Enhanced features opt-in** - Use new modules when needed
3. **Three-layer architecture** - Add for complex multi-tenant scenarios
4. **Policy engine** - Replace hardcoded action complexity
5. **Governance-as-a-Service** - Use for multi-tenant API exposure

### When to Use Each Approach

| Scenario | Recommended Approach |
|----------|---------------------|
| Single-tenant, simple governance | Original `AgentGovernanceService` |
| Multi-tenant with policies | `GovernanceAsAService` |
| Complex decision layers | `DynamicGovernanceManager` |
| Policy-based evaluation | `PolicyEngine` |
| Production validation | See `VALIDATION_METRICS.md` |

---

## 📖 Related Documentation

### Core Governance
- **[Agent Graduation](../agents/graduation.md)** - Promotion framework
- **[Agent Training](../agents/training.md)** - Training workflow
- **[Agent System](../agents/README.md)** - Complete agent documentation

### Enhanced Features
- **VALIDATION_METRICS.md** - Performance validation
- **[ATOM_ENHANCEMENT_PLAN.md](../../ATOM_ENHANCEMENT_PLAN.md)** - Research-based enhancements
- **[Federation Identity](../guides/FEDERATION_INSTANCE_IDENTITY.md)** - Zero-trust identity

### Architecture
- **[Orchestration Patterns](../workflow_automation/README.md)** - Conductor agent, state machine
- **[Cognitive Tier System](../architecture/COGNITIVE_TIER_SYSTEM.md)** - LLM routing enhancements

---

**Last Updated**: June 18, 2026
**Version**: 2.0 (Enhanced Governance)
**Status**: ✅ Foundation Stable | ✅ Enhanced Features Complete (92 tests passing)
