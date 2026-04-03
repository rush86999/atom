# Single-Tenant Architecture

## Overview

Atom-upstream is designed for single-tenant deployment, unlike atom-saas which supports multi-tenancy. This document explains the key differences and architectural decisions.

## Key Differences from SaaS Version

### User Management

- **SaaS**: tenant_id isolates users, row-level security (RLS) on all queries
- **Upstream**: user_id identifies users, no tenant isolation
- **Impact**: Simpler database queries, no tenant filtering required

### Billing & Quota

- **SaaS**: BudgetEnforcementService, quota limits, plan-based feature gating
- **Upstream**: No billing system, unlimited usage, self-hosted
- **Impact**: Fleet recruitment has no budget checks, unlimited agent creation

### Fleet Recruitment

- **SaaS**: Budget checks before fleet recruitment, quota limits on fleet size
- **Upstream**: No budget checks, fleet size limited by system resources only
- **Impact**: RecruitmentIntelligenceService.budget parameter is optional (None in upstream)

### Governance

- **Same in both**: AgentGovernanceService enforces maturity-based permissions
- **Same in both**: Audit logging for all routing decisions
- **Same in both**: Graduation gates (Queen, Admiral) work identically

### Meta-Agent Routing

- **Same in both**: CHAT/WORKFLOW/TASK intent classification
- **Same in both**: Governance checks before routing
- **Same in both**: Auto-takeover proposal mode
- **Difference**: user_id instead of tenant_id

## Deployment

### Architecture

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

### Database Schema

**SaaS Version:**
```sql
-- All tables have tenant_id
CREATE TABLE agents (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,  -- Multi-tenant isolation
    name VARCHAR(255),
    -- RLS policies enforce tenant_id filtering
);

-- Queries always filter by tenant_id
SELECT * FROM agents WHERE tenant_id = ?;
```

**Upstream Version:**
```sql
-- No tenant_id column
CREATE TABLE agents (
    id UUID PRIMARY KEY,
    user_id UUID,  -- Optional user reference
    name VARCHAR(255)
    -- No RLS policies
);

-- Simple queries
SELECT * FROM agents;
```

### API Differences

**SaaS Version:**
```python
# Always extract tenant from request
tenant = await getTenantFromRequest(request)
result = await fleet_admiral.recruit_and_execute(
    task=task,
    tenant_id=tenant.id  # Multi-tenant
)
```

**Upstream Version:**
```python
# Use user_id directly
result = await fleet_admiral.recruit_and_execute(
    task=task,
    user_id=user_id  # Single-tenant
)
```

## Code Patterns

### Parameter Replacement

| SaaS Parameter | Upstream Parameter | Example Usage |
|----------------|-------------------|---------------|
| `tenant_id: str` | `user_id: str` | Database queries, API calls |
| `tenant_id` filter | No filtering | `WHERE agent_id = ?` |
| `BudgetEnforcementService` | `None` | Optional parameter |
| RLS policies | No policies | Direct table access |

### Service Initialization

**SaaS Version:**
```python
from core.budget_enforcement_service import BudgetEnforcementService

recruitment_intelligence = RecruitmentIntelligenceService(
    db=db,
    llm=llm,
    governance=governance,
    budget=BudgetEnforcementService(db)  # Required in SaaS
)
```

**Upstream Version:**
```python
# No BudgetEnforcementService import
recruitment_intelligence = RecruitmentIntelligenceService(
    db=db,
    llm=llm,
    governance=governance,
    budget=None  # Optional, always None in upstream
)
```

### Database Queries

**SaaS Version:**
```python
# Always filter by tenant_id
agents = db.query(AgentRegistry).filter(
    AgentRegistry.tenant_id == tenant_id,
    AgentRegistry.category == "Finance"
).all()
```

**Upstream Version:**
```python
# No tenant filtering
agents = db.query(AgentRegistry).filter(
    AgentRegistry.category == "Finance"
).all()
```

## Migration from SaaS

When porting features from SaaS to upstream, follow these steps:

1. **Remove tenant_id filtering**
   - Remove `WHERE tenant_id = ?` from database queries
   - Remove tenant_id parameters from function signatures
   - Remove RLS policy references

2. **Remove BudgetEnforcementService dependencies**
   - Remove budget parameter from service initialization
   - Make budget parameter optional with default `None`
   - Remove quota enforcement logic

3. **Replace tenant_id with user_id**
   - Update API signatures: `tenant_id: str` → `user_id: str`
   - Update docstrings to reflect single-tenant deployment
   - Update variable names in function bodies

4. **Remove SaaS middleware**
   - Remove tenant extraction middleware
   - Remove RLS policy enforcement
   - Remove billing/quota checks

5. **Update documentation**
   - Add single-tenant architecture notes
   - Document differences from SaaS version
   - Update deployment guides

## Feature Comparison

| Feature | SaaS Version | Upstream Version | Notes |
|---------|--------------|------------------|-------|
| Multi-tenancy | ✅ | ❌ | Upstream is single-tenant |
| Billing & Quota | ✅ | ❌ | Upstream is unlimited |
| Agent Governance | ✅ | ✅ | Same implementation |
| Graduation System | ✅ | ✅ | Same implementation |
| Meta-Agent Routing | ✅ | ✅ | Same logic, user_id instead of tenant_id |
| Fleet Recruitment | ✅ | ✅ | No budget checks in upstream |
| QueenAgent Workflows | ✅ | ✅ | Same implementation |
| World Model | ✅ | ✅ | Same implementation |
| MCP Integrations | ✅ | ✅ | Same implementation |

## Deployment Considerations

### Resource Limits

**SaaS Version:**
- Per-tenant quotas limit resource usage
- Plan-based agent limits (Free: 3, Solo: 10, Team: 25, Enterprise: Unlimited)
- Budget enforcement prevents runaway costs

**Upstream Version:**
- No quota limits (self-hosted)
- Resource limits based on hardware only
- Admin must monitor system resources

### Security

**SaaS Version:**
- Tenant isolation via RLS
- Per-tenant API keys
- Multi-tenant data segregation

**Upstream Version:**
- User-level permissions only
- Single API key for deployment
- All users share same data pool

### Scalability

**SaaS Version:**
- Horizontal scaling via tenant sharding
- Per-tenant database connections
- Load balancing by tenant

**Upstream Version:**
- Vertical scaling only
- Single database connection pool
- Load balancing by request

## Conclusion

The upstream version provides the same core AI agent capabilities as the SaaS version, but simplified for single-tenant self-hosted deployment. The main differences are:

1. **No multi-tenancy**: Simpler architecture, no tenant isolation
2. **No billing**: Unlimited usage, no quota enforcement
3. **user_id instead of tenant_id**: Simpler API signatures
4. **No SaaS infrastructure**: Self-hosted deployment only

All core AI features (governance, graduation, routing, fleet recruitment) work identically in both versions.
