# Governance System

Agent maturity levels, permissions, and governance controls.

## 📚 Quick Navigation

- **[Governance Quick Reference](GOVERNANCE_QUICK_REFERENCE.md)** - Quick reference guide

## 🎯 Maturity Levels

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

## 🔒 Governance Features

### Trigger Interceptor
- **Maturity Routing**: Routes triggers based on agent maturity
- **Proposal Workflow**: INTERN agents propose actions for approval
- **Supervision Mode**: SUPERVISED agents run under real-time monitoring
- **Full Autonomy**: AUTONOMOUS agents execute without oversight

### Agent Governance
- **Permissions**: Maturity-based access control
- **Audit Trail**: All actions logged and attributable
- **Performance Monitoring**: Sub-millisecond governance checks (<1ms P99)
- **Cache Layer**: High-performance governance cache

### Training System
- **AI-Powered Training**: LLM-based training duration estimation
- **Intervention Tracking**: Track human interventions
- **Graduation Criteria**: Constitutional compliance validation
- **Promotion Workflow**: Move agents through maturity levels

## 📊 Performance Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Governance check (cached) | <10ms | 0.027ms P99 |
| Agent resolution | <50ms | 0.084ms avg |
| Cache hit rate | >90% | 95% |
| Cache throughput | >5k ops/s | 616k ops/s |

## 🔧 Quick Start

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

## 📖 Related Documentation

- **[Agent Graduation](../agents/graduation.md)** - Promotion framework
- **[Agent Training](../agents/training.md)** - Training workflow
- **[Agent System](../agents/README.md)** - Complete agent documentation

---

*Last Updated: April 12, 2026*
