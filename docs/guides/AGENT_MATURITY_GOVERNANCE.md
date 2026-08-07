# Agent Maturity & Governance — Concept Guide

> **Purpose**: Understand how Atom controls what agents can do, and how they earn more autonomy over time.
> **Audience**: New users, admins, architects
> **Read time**: ~10 minutes

---

## The Core Insight: Tier ≠ Security

> ⚠️ **Critical**: An agent's *maturity tier* (STUDENT → AUTONOMOUS) is a **routing hint**, not a security boundary. A prompt-injected agent at any tier acts at that tier's full scope.

**Real security** comes from the **Execution Sandbox Layer** (default-on since Aug 2026):
- Filesystem scope limits
- Tool whitelists
- Resource caps (CPU, memory, time, cost)
- Network egress control (opt-in)
- Provenance tagging + LLM ActionJudge

See: [Trust vs Sandbox](../security/TRUST_VS_SANDBOX.md) | [Sandbox Layer](../architecture/SANDBOX_LAYER.md)

---

## Four Maturity Tiers

| Tier | Confidence | Capabilities | Governance | Typical Use |
|------|------------|--------------|------------|-------------|
| **STUDENT** | < 0.5 | Read-only | BLOCKED → training data | New agents, untrusted code |
| **INTERN** | 0.5 – 0.7 | Streaming, forms, browser | PROPOSAL → human approval | Assistants, research |
| **SUPERVISED** | 0.7 – 0.9 | State changes (CRUD) | Supervised execution | Trusted workflows |
| **AUTONOMOUS** | > 0.9 | All actions, deletions | Self-governed | Proven agents only |

**Confidence** = historical success rate (clean executions / total executions). Agents graduate automatically at thresholds.

---

## Action Complexity Levels

Every tool/action has a complexity rating (1–4). Tier determines max allowed:

| Complexity | Level | Examples | Min Tier |
|------------|-------|----------|----------|
| **LOW** | 1 | Presentations, charts, reading files | STUDENT+ |
| **MODERATE** | 2 | Streaming, forms, browser automation | INTERN+ |
| **HIGH** | 3 | State changes (write DB, send email) | SUPERVISED+ |
| **CRITICAL** | 4 | Deletions, admin ops, infra changes | AUTONOMOUS only |

---

## Governance Flow

```
User Request
     ↓
AgentContextResolver (who, what tier, what caps)
     ↓
GovernanceCache (<1ms cached check)
     ↓
AgentGovernanceService (can_execute?)
     ↓
┌─────────────────────────────────────┐
│  ALLOWED → Execute                  │
│  PROPOSAL → Create Proposal → HITL  │
│  BLOCKED → Log + Training Data      │
└─────────────────────────────────────┘
```

### Proposal Service (HITL)

When an action needs approval:
1. **Proposal created** with full context (agent, action, params, risk)
2. **Notification sent** to supervisors (WebSocket + email)
3. **Human reviews** → Approve / Reject / Modify
4. **Audit trail** recorded regardless of outcome

---

## Capability Bindings (Per-Agent Zero-Trust)

> **New in P2 (Aug 2026)**: Each agent declares `capabilities: string[]` in `AgentRegistry`. At dispatch time, the system intersects:
> ```
> allowed = agent.capabilities ∩ tier_floor_capabilities ∩ sandbox_policy
> ```
> - `[]` or `["*"]` = unrestricted (legacy default)
> - Explicit list = only those tools allowed
> - Enforced at **`integrations/mcp_service.call_tool`** — covers agent loop, workflows, fleet, business agents

---

## Graduation System

Agents earn autonomy through **clean execution history**:

| Milestone | Episodes | Graduation |
|-----------|----------|------------|
| **Bronze** | 10 clean | STUDENT → INTERN |
| **Silver** | 25 clean | INTERN → SUPERVISED |
| **Gold** | 50 clean | SUPERVISED → AUTONOMOUS |

**Clean** = no governance violations, no sandbox trips, verified outcomes.

Graduation is **automatic** but can be **accelerated** by supervisors via `/api/agents/{id}/graduate`.

---

## Agent Types & Intent Classification

| Type | Intent | Handler | Use Case |
|------|--------|---------|----------|
| **Queen Agent** | `WORKFLOW` | Structured blueprints | Repeatable, scheduled automation |
| **Fleet Admiral** | `TASK` | Dynamic recruitment | Open-ended, multi-step problems |
| **Generic Agent** | `CHAT` | Direct LLM + tools | Conversation, Q&A |
| **Business Agent** | Domain-specific | Pre-built skills | Sales, support, finance |

**Intent classification** happens automatically via `intent_classifier.py` → routes to right handler.

---

## Configuration for Admins

```bash
# Governance toggles (backend/.env)
STREAMING_GOVERNANCE_ENABLED=true   # Stream governance decisions
CANVAS_GOVERNANCE_ENABLED=true      # Canvas action governance
FORM_GOVERNANCE_ENABLED=true        # Form submission governance
BROWSER_GOVERNANCE_ENABLED=true     # Browser automation governance
EMERGENCY_GOVERNANCE_BYPASS=false   # Emergency override (audit logged)

# Sandbox (default-on, kill switches)
ATOM_SANDBOX_ENABLED=true
ATOM_SANDBOX_FORCE_ENFORCE=true     # false = shadow mode (audit only)
ATOM_SANDBOX_FS_ENABLED=true
ATOM_SANDBOX_WHITELIST_ENABLED=true
ATOM_SANDBOX_CAPS_ENABLED=true
ATOM_SANDBOX_EGRESS_ENABLED=false   # Opt-in network isolation
```

---

## Common Patterns

### For New Users
1. Start agents at **STUDENT** (default)
2. Use **Queen Agent** for structured workflows
3. Review proposals in the UI → builds training data
4. Agents graduate naturally as you approve good work

### For Power Users
1. Pre-define `capabilities` on agent creation
2. Use `x-atom-tier` header to force routing tier
3. Monitor `/api/agents/{id}/governance` for real-time decisions
4. Set up webhook notifications for proposals

### For Admins
1. Audit `CanvasAudit` and `AgentExecution` tables weekly
2. Review graduation pipeline: `GET /api/agents?status=graduation_pending`
3. Tune sandbox caps per workload: `ATOM_SANDBOX_MAX_COST_USD=5.0`
4. Enable `ATOM_SANDBOX_JUDGE_ENABLED=true` for irreversible actions

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Agent stuck at STUDENT | No clean executions | Run simple read-only tasks; approve proposals |
| "Proposal required" for simple action | Tier too low | Check action complexity; upgrade tier or add capability |
| Agent executes but changes don't persist | Sandbox FS scope | Check `ATOM_SANDBOX_FS_ENABLED` and path allowlist |
| "Capability denied" error | Missing from agent.capabilities | Add to `AgentRegistry.capabilities` or use `["*"]` |
| Graduation not happening | Unverified outcomes | Ensure `outcome_verified=true` on executions |

---

## Related Documentation

- [Agent Overview](../agents/overview.md) — System + intent types
- [Agent Governance](../agents/governance.md) — API reference
- [Governance Quick Reference](../governance/GOVERNANCE_QUICK_REFERENCE.md) — Permissions matrix
- [Student Training](../guides/AGENT_MATURITY_GOVERNANCE.md) — Training workflow (this guide)
- [Agent Graduation](../agents/graduation.md) — Promotion criteria
- [Sandbox Layer](../architecture/SANDBOX_LAYER.md) — Real security boundary
- [Trust vs Sandbox](../security/TRUST_VS_SANDBOX.md) — Conceptual foundation
- [Execution Sandbox Gate](../core/sandbox_gate.py) — Code reference

---

*Last Updated: August 2026*