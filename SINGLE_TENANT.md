# Single-Tenant Architecture

## Overview

Atom-upstream is designed for single-tenant deployment, unlike atom-saas which supports multi-tenancy. This document explains the key differences and architectural decisions.

**Ported from:** rush86999/atom-saas@6c5f4e3d4
**Changes:** Removed billing, quota, and tenant isolation features.

## Key Differences from SaaS Version

### 1. User Management & Isolation
- **SaaS (Multi-Tenant)**: `tenant_id` isolates users across organizations. Row-Level Security (RLS) is enforced in PostgreSQL.
- **Upstream (Single-Tenant)**: `user_id` identifies individual users. There is no tenant isolation; one deployment serves one organization.
- **Impact**: Simpler database queries and direct table access without mandatory tenant filtering or RLS overhead.

### 2. Billing & Quotas
- **SaaS**: Includes `BudgetEnforcementService`, plan-based quotas (Free/Solo/Team), and feature gating.
- **Upstream**: No billing system or quota enforcement. Usage is unlimited and gated only by system resources.
- **Impact**: Fleet recruitment has no budget checks, and agent creation is unlimited.

### 3. Fleet Recruitment
- **SaaS**: Budget checks are performed before recruiting specialists. Quotas limit the maximum fleet size.
- **Upstream**: No budget checks. Fleet size is limited only by hardware capacity.
- **Code Change**: `RecruitmentIntelligenceService.budget` parameter is optional and defaults to `None`.

### 4. Governance & Graduation
- **Identical in Both**: `AgentGovernanceService` enforces maturity-based permissions (STUDENT → INTERN → SUPERVISED → AUTONOMOUS).
- **Identical in Both**: Audit logging and graduation gates (Queen, Admiral) work exactly the same way.

### 5. Meta-Agent Routing
- **Identical in Both**: CHAT/WORKFLOW/TASK intent classification and auto-takeover proposal mode.
- **Difference**: Upstream uses `user_id` where SaaS uses `tenant_id` in API signatures.

---

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Single-Tenant Deployment                 │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Next.js    │  │  FastAPI     │  │   PostgreSQL │      │
│  │  (Frontend)  │  │  (Backend)   │  │  (Database)  │      │
│  │              │  │              │  │              │      │
│  │ Port: 3000   │  │ Port: 8000   │  │ Port: 5432   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│         │                 │                  │              │
│         └─────────────────┴──────────────────┘              │
│                     Shared Resources                         │
│                                                               │
│  - Single database instance (no tenant isolation)            │
│  - Single Redis instance (no tenant key prefixing)           │
│  - No billing/subscription system                            │
│  - All users share same agent pool                           │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Code Patterns & Migration

### Parameter Mapping
| SaaS Parameter | Upstream Parameter | Notes |
|----------------|-------------------|-------|
| `tenant_id: str` | `user_id: str` | Core identifier for ownership |
| `BudgetEnforcementService` | `None` | Service is removed in Upstream |
| `tenant_id` SQL Filter | No Filter | Queries are direct |

### Example Migration (SaaS → Upstream)

**Database Queries:**
```python
# Before (SaaS)
agents = db.query(Agent).filter(Agent.tenant_id == tenant_id).all()

# After (Upstream)
agents = db.query(Agent).all()  # No tenant filtering enforced by RLS
```

**Service Initialization:**
```python
# Before (SaaS)
self.budget = BudgetEnforcementService(db)
can_execute = await self.budget.check_limit(tenant_id, "executions")

# After (Upstream)
self.budget = None  # No budget enforcement
can_execute = True  # Always allowed
```

---

## Benefits of Single-Tenant Upstream
1. **Performance**: No RLS overhead or complex JOINs for tenant isolation.
2. **Simplicity**: Reduced code complexity and fewer moving parts (no billing/quotas).
3. **Self-Hosted**: Full control over data and zero subscription maintenance.
4. **Maintenance**: Easier debugging and simpler deployment cycles.

## Limitations
1. **One Org Only**: Cannot host multiple distinct organizations on a single instance.
2. **Manual Monitoring**: Admin must monitor hardware resources as there are no software-enforced quotas.

## Conclusion
Atom-upstream provides the same core AI capabilities as the SaaS platform but is optimized for private, high-performance, single-tenant environments. All advances in the "graduation" and "governance" frameworks are shared across both repositories.

**See Also:**
- `ROADMAP.md` - Feature roadmap and porting notes
- `README.md` - General platform documentation
- `CLAUDE.md` - Development guidelines
