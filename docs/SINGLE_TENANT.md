# Single-Tenant Architecture

## Overview

Atom is designed for **self-hosted, single-tenant deployment**. This document explains the architectural decisions and design patterns.

## Architecture Principles

### 1. User Management & Isolation
- **Single Organization**: One deployment serves one organization
- **User Identification**: `user_id` identifies individual users
- **Legacy tenant_id**: Database models still have `tenant_id` columns (nullable, defaults to NULL)
- **No Multi-Tenancy**: No tenant isolation, `tenant_id` columns are legacy and unused
- **Impact**: Simpler database queries without tenant filtering

### 2. Resource Management
- **No Billing System**: No subscription management or payment processing
- **No Quotas**: Usage is unlimited and gated only by system resources
- **Hardware-Based Limits**: Fleet size and agent creation limited by hardware capacity
- **Admin Monitoring**: System administrators monitor hardware resources directly

### 3. Fleet Recruitment
- **No Budget Checks**: FleetAdmiral recruits specialists without budget enforcement
- **Resource-Aware**: Fleet size limited by available system resources
- **Code Pattern**: `RecruitmentIntelligenceService.budget` parameter is `None`

### 4. Governance & Graduation
- **4-Tier Maturity**: `AgentGovernanceService` enforces permissions (STUDENT → INTERN → SUPERVISED → AUTONOMOUS)
- **Audit Logging**: All routing decisions logged and traceable
- **Graduation Gates**: Queen and Admiral gates work identically

### 5. Meta-Agent Routing
- **Intent Classification**: CHAT/WORKFLOW/TASK categorization
- **Auto-Takeover**: Propose alternatives when governance denies actions
- **User-Based Routing**: Uses `user_id` for request ownership

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

## Code Patterns

### Parameter Conventions
| Parameter | Type | Purpose |
|-----------|------|---------|
| `user_id: str` | Required | Core identifier for user ownership |
| `tenant_id` | Optional | Legacy field (nullable in DB, unused in single-tenant) |
| `budget` | None | No budget enforcement (always `None`) |

### Database Query Pattern
```python
# Direct queries - no tenant filtering
agents = db.query(Agent).filter(Agent.category == "Finance").all()
```

### Service Initialization Pattern
```python
# FleetAdmiral - no budget checks
recruitment_intelligence = RecruitmentIntelligenceService(
    db=db,
    llm=llm,
    governance=governance,
    budget=None  # No budget enforcement
)
```

---

## Benefits

1. **Performance**: No overhead for tenant isolation or complex JOINs
2. **Simplicity**: Reduced code complexity without billing/quotas
3. **Self-Hosted**: Full control over data and infrastructure
4. **Maintenance**: Easier debugging and simpler deployment

## Considerations

1. **Single Organization**: One deployment serves one organization
2. **Resource Monitoring**: Admin must monitor hardware resources
3. **User Management**: Built-in user authentication and permissions

## Legacy Code & tenant_id

The codebase contains `tenant_id` as a **legacy field** that doesn't break the app:

### Database Schema
- **`tenant_id` columns exist** in many tables (User, Workspace, etc.)
- **All are `nullable=True`** - can be NULL without breaking constraints
- **`Tenant` table exists** but is not used for tenant isolation
- **Foreign keys to `tenants.id`** are nullable and cascade on delete

### Code Behavior
- **New functions use `user_id`** for user identification
- **Legacy functions may accept `tenant_id`** parameter but default to `"default"` or `None`
- **No tenant filtering** in queries (direct table access)

**Example:**
```python
# Database model (tenant_id is nullable)
class User(Base):
    id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=True)  # Can be NULL
    email = Column(String, nullable=False)

# Function signature (tenant_id optional)
def some_function(user_id: str, tenant_id: Optional[str] = None):
    tenant_id = tenant_id or "default"  # Defaults if not provided
```

These `tenant_id` references are **harmless legacy** from the SaaS codebase and can be cleaned up incrementally.

## Conclusion

Atom provides comprehensive AI agent capabilities optimized for self-hosted, single-tenant environments. All core features (governance, graduation, routing, fleet recruitment) work without complexity of multi-tenancy or billing systems.

**See Also:**
- [ROADMAP.md](../ROADMAP.md) - Feature roadmap
- [README.md](../README.md) - Platform overview
- [CLAUDE.md](../CLAUDE.md) - Development guidelines
