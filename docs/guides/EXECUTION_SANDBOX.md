# Execution Sandbox Layer — Concept Guide

> **Purpose**: Understand how Atom bounds blast radius for every agent action.
> **Audience**: Security engineers, architects, admins
> **Read time**: ~15 minutes

---

## Why This Exists

> **Tier is routing, not security.**

An agent's maturity tier (STUDENT → AUTONOMOUS) decides what it's *normally allowed to do* based on past clean runs. It does **not** bound blast radius — a prompt-injected agent at any tier acts at that tier's full scope.

**Real security requires a deterministic, policy-enforced layer** that:
- Runs on **every** tool call (not just agent loop)
- Enforces **filesystem scope**, **tool whitelist**, **resource caps**
- Is **default-on** (since P9, Aug 2026) for all dispatch paths
- Has **kill switches** for instant rollback

---

## Five-Phase Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  TOOL CALL (from agent loop, workflow, fleet, business agent)  │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE A: POLICY + AUDIT                                       │
│  • Load SandboxPolicy (tenant override?)                       │
│  • Create audit row (SandboxAudit) — ALWAYS                    │
│  • Decision: ALLOW / PROPOSAL / DENY                           │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE B: FILESYSTEM SCOPE                                     │
│  • Allowlist: ./data/agent_workspace/{agent_id}/               │
│  • Denylist: /etc, /root, ~/.ssh, /proc, /sys, etc.           │
│  • Symlink resolution (no escape)                              │
│  • Violation → audit + DENY                                    │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE C: TRIPWIRES + CAPS + KILLRUN                          │
│  • Tool whitelist (capability intersection)                    │
│  • Regex tripwires (secrets, private keys, megafiles)          │
│  • Resource caps:                                              │
│      - MAX_TOOL_CALLS=200                                       │
│      - MAX_EXEC_SECONDS=600                                     │
│      - MAX_BYTES_WRITTEN=100MB                                  │
│      - MAX_COST_USD=5.0                                         │
│  • KillRun: hard process termination on violation              │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE D: RUNTIME + EGRESS (Opt-in)                            │
│  • Docker (default) / Firecracker / E2B                        │
│  • Egress proxy: allowlist domains only                        │
│  • Network namespace isolation                                 │
│  • VM specs: 256MB / 1 vCPU / 5s boot                          │
└──────────────────────────────┬──────────────────────────────────┘
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│  PHASE E: PROVENANCE + ACTIONJUDGE                             │
│  • Tag all context with provenance (tool, agent, policy)       │
│  • LLM ActionJudge (opt-in): reviews irreversible actions      │
│  • Circuit breaker: 5 failures → 120s cooldown                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Dispatch Paths Covered

The sandbox gate is **shared** at `integrations/mcp_service.call_tool`, so it covers:

| Path | Entry Point | Covered? |
|------|-------------|----------|
| Agent loop | `generic_agent.py` → `call_tool` | ✅ |
| Workflow execution | `workflow_executor.py` → `call_tool` | ✅ |
| Fleet Admiral | `fleet_admiral.py` → `call_tool` | ✅ |
| Business agents | `business_agent.py` → `call_tool` | ✅ |
| Meta-agent | `atom_meta_agent.py` → `call_tool` | ✅ |
| Canvas actions | `canvas_tool.py` → `call_tool` | ✅ |
| **Direct MCP** | `mcp_service.call_tool` | ✅ (shared gate) |

---

## Configuration (Kill Switches)

All flags default **ON** (enforcing). Set any to `false` for instant rollback.

```bash
# Master switches
ATOM_SANDBOX_ENABLED=true              # Phase A+ — layer on/off
ATOM_SANDBOX_FORCE_ENFORCE=true        # Enforce vs shadow (audit only)

# Phase B: Filesystem
ATOM_SANDBOX_FS_ENABLED=true

# Phase C: Tripwires + Caps
ATOM_SANDBOX_WHITELIST_ENABLED=true
ATOM_SANDBOX_TRIPWIRES_ENABLED=true
ATOM_SANDBOX_CAPS_ENABLED=true

# Caps (tunable)
ATOM_SANDBOX_MAX_TOOL_CALLS=200
ATOM_SANDBOX_MAX_EXEC_SECONDS=600
ATOM_SANDBOX_MAX_BYTES_WRITTEN=104857600  # 100MB
ATOM_SANDBOX_MAX_COST_USD=5.0

# Phase D: Runtime + Egress
ATOM_SANDBOX_RUNTIME=docker              # docker | firecracker | e2b
ATOM_SANDBOX_EGRESS_ENABLED=false        # Opt-in network isolation
ATOM_SANDBOX_VM_MEM_MB=256
ATOM_SANDBOX_VM_VCPUS=1
ATOM_SANDBOX_VM_BOOT_TIMEOUT_SECONDS=5

# Phase E: Provenance + Judge
ATOM_SANDBOX_PROVENANCE_ENABLED=true
ATOM_SANDBOX_JUDGE_ENABLED=false         # Opt-in LLM review
ATOM_SANDBOX_JUDGE_TIMEOUT_SECONDS=2.0
ATOM_SANDBOX_JUDGE_CIRCUIT_THRESHOLD=5
ATOM_SANDBOX_JUDGE_CIRCUIT_COOLDOWN_SECONDS=120

# Fastest kill switch (restores shadow mode):
ATOM_SANDBOX_FORCE_ENFORCE=false
```

---

## Policy Model

```python
# core/sandbox_policy.py
class SandboxPolicy:
    # Filesystem
    fs_allowlist: List[str]           # Globs allowed
    fs_denylist: List[str]            # Globs blocked (always wins)
    
    # Tool whitelist (intersected with agent.capabilities)
    tool_allowlist: List[str]         # Tool IDs allowed
    
    # Tripwires (regex patterns → DENY)
    tripwires: List[TripwireRule]
    
    # Resource caps
    max_tool_calls: int
    max_exec_seconds: int
    max_bytes_written: int
    max_cost_usd: float
    
    # Runtime
    runtime: Literal["docker", "firecracker", "e2b"]
    egress_allowlist: List[str]       # Domains allowed (if egress enabled)
    
    # Tenant override (opt-in)
    tenant_override_allowed: bool
```

**Tenant override** (`ATOM_SANDBOX_POLICY_TENANT_OVERRIDE=true`): Tenants can provide `metadata_json.sandbox_policy` to relax (not tighten) defaults.

---

## Capability Bindings + Sandbox

> **New in P2/P9**: Two-layer defense

```
allowed_tools = agent.capabilities ∩ tier_floor ∩ sandbox_policy.tool_allowlist
```

- `agent.capabilities` — Per-agent declaration (e.g., `["browser_navigate", "file_read"]`)
- `tier_floor` — Minimum capabilities for agent's maturity tier
- `sandbox_policy.tool_allowlist` — Global policy (e.g., block `shell_exec` for all)

**Default**: `[]` or `["*"]` = unrestricted (legacy compat). **Explicit list = zero-trust.**

---

## Audit & Observability

Every tool call creates a `SandboxAudit` row:

```sql
CREATE TABLE sandbox_audit (
    id UUID PRIMARY KEY,
    agent_id UUID REFERENCES agent_registry(id),
    tool_name VARCHAR(255),
    tool_args JSONB,
    phase_reached VARCHAR(50),    -- 'policy', 'fs', 'tripwire', 'caps', 'runtime', 'provenance', 'judge'
    decision VARCHAR(20),         -- 'allow', 'proposal', 'deny'
    violation_type VARCHAR(50),   -- 'fs_escape', 'tripwire_secret', 'cap_exceeded', etc.
    violation_detail JSONB,
    provenance_tags JSONB,        -- Phase E tags
    judge_verdict JSONB,          -- Phase E LLM review
    created_at TIMESTAMPTZ DEFAULT now()
);
```

### Query Patterns

```sql
-- All violations for an agent
SELECT * FROM sandbox_audit 
WHERE agent_id = '...' AND decision = 'deny'
ORDER BY created_at DESC;

-- Tripwire hits by type
SELECT violation_type, COUNT(*) 
FROM sandbox_audit 
WHERE violation_type LIKE 'tripwire_%'
GROUP BY violation_type;

-- Resource cap trends
SELECT date_trunc('hour', created_at) AS hour,
       COUNT(*) FILTER (WHERE violation_type = 'cap_exceeded') AS cap_violations
FROM sandbox_audit
GROUP BY hour;
```

---

## Shadow Mode vs Enforcement

| Mode | `FORCE_ENFORCE` | Behavior |
|------|-----------------|----------|
| **Shadow** | `false` | All phases compute + audit, **nothing blocked** |
| **Enforce** | `true` (default) | Violations → DENY (or PROPOSAL for partial) |

**Migration path**:
1. Deploy with `FORCE_ENFORCE=false` (shadow)
2. Monitor `/api/sandbox/audit` for false positives
3. Tune policy (allowlist, caps, tripwires)
4. Flip `FORCE_ENFORCE=true`
5. Keep `ENABLED=true` — kill switch always available

---

## Common Tripwires (Built-in)

| Pattern | Type | Action |
|---------|------|--------|
| `-----BEGIN (RSA|EC|OPENSSH) PRIVATE KEY-----` | Secret | DENY |
| `sk-[a-zA-Z0-9]{32,}` | API key | DENY |
| `aws_secret_access_key\s*=` | AWS cred | DENY |
| `password\s*[:=]\s*\S{8,}` | Password | DENY |
| File > 10MB written | Megafile | DENY |
| ≥5 edits to same file/loop | Megafile | DENY |
| `curl http://169.254.169.254` | Metadata SSRF | DENY |

**Custom tripwires**: Add to `SandboxPolicy.tripwires` via tenant override or code.

---

## Troubleshooting

| Symptom | Diagnosis | Fix |
|---------|-----------|-----|
| "Tool denied: fs_escape" | Path outside allowlist | Add to `fs_allowlist` or use workspace path |
| "Tool denied: tripwire_secret" | Secret detected in args | Redact secrets; use credential manager |
| "Tool denied: cap_exceeded" | Resource limit hit | Increase cap or optimize tool |
| "KillRun triggered" | Hard violation | Check audit row for `violation_type` |
| ActionJudge timeout | LLM review too slow | Increase `JUDGE_TIMEOUT` or disable |
| Proposals for everything | Policy too strict | Relax `tool_allowlist` or add capabilities |

---

## Testing the Sandbox

```bash
# Unit tests (166 tests)
pytest tests/unit/core/test_sandbox_*.py -v

# Integration test: try to escape
curl -X POST http://localhost:8000/api/agent/route \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"request": "Read /etc/passwd"}'
# → Should DENY with fs_escape

# View audit trail
curl http://localhost:8000/api/sandbox/audit?agent_id=... | jq

# Shadow mode test
export ATOM_SANDBOX_FORCE_ENFORCE=false
# Run same test → audit logged, but ALLOWED
```

---

## Related Documentation

- [Sandbox Layer](../architecture/SANDBOX_LAYER.md) — Full architecture
- [Trust vs Sandbox](../security/TRUST_VS_SANDBOX.md) — Conceptual foundation
- [Prompt Injection Defense](../security/PROMPT_INJECTION_DEFENSE_PLAN.md) — Threat model
- [Sandbox Policy](../core/sandbox_policy.py) — Code reference
- [Sandbox Gate](../core/sandbox_gate.py) — Enforcement entry point
- [Sandbox FS](../core/sandbox_fs.py) — Filesystem scope
- [Sandbox Tripwires](../core/sandbox_tripwire.py) — Pattern detection
- [Sandbox Caps](../core/sandbox_caps.py) — Resource limits
- [Sandbox Runtime](../core/sandbox_runtime/) — Docker/Firecracker/E2B
- [Provenance](../core/provenance.py) — Context tagging
- [Action Judge](../core/llm/action_judge.py) — LLM review

---

*Last Updated: August 2026*