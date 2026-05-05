# Atom Upstream Tenancy Architecture

This document clarifies the tenancy model for **Atom Upstream** and provides guidance for developers porting features from the SaaS platform.

## Single-Tenant Philosophy

**Atom Upstream is strictly single-tenant.**

The Upstream repository is the core "operating system" for Atom, optimized for local execution, self-hosting, and private enterprise deployments. Unlike the SaaS platform (which handles thousands of isolated customers), Upstream assumes it is running in an environment dedicated to one organization.

### Key Differences

| Feature | Atom SaaS | Atom Upstream |
|---------|-----------|---------------|
| **Multi-Tenancy** | Enforced (Shared Database) | **Disabled (Dedicated Instance)** |
| **Isolation** | Workspace + Tenant IDs | Default Workspace only |
| **API Keys** | Tenant-scoped (BYOK) | Instance-scoped (Platform keys) |
| **Authentication** | JWT with Tenant claims | Session-based or Single-User |
| **Service Init** | `Service(tenant_id=...)` | `Service()` (Uses default) |

---

## Developer Guidelines: Porting from SaaS

When bringing new features or bug fixes from the SaaS codebase to Upstream, follow these "De-Tenanting" rules:

### 1. Simplify Constructors
SaaS services often require `tenant_id` and `workspace_id` in their `__init__`. In Upstream, these should be optional or removed.

**❌ SaaS Pattern:**
```python
class MyService:
    def __init__(self, tenant_id: str, workspace_id: str, db: Session):
        self.tenant_id = tenant_id
        self.workspace_id = workspace_id
        self.db = db
```

**✅ Upstream Pattern:**
```python
class MyService:
    def __init__(self, db: Optional[Session] = None):
        self.db = db or SessionLocal()
        # Defaults to system-wide context
```

### 2. Database Queries
Remove `tenant_id` filters from standard queries. While the `tenant_id` column might still exist in `models.py` (for future-proofing or legacy compatibility), it should generally default to a single system-wide value.

**❌ SaaS Pattern:**
```python
nodes = db.query(GraphNode).filter(GraphNode.tenant_id == tenant_id).all()
```

**✅ Upstream Pattern:**
```python
nodes = db.query(GraphNode).all()
```

### 3. Model Definitions
Upstream models should avoid mandatory `ForeignKey` constraints to a `Tenants` table unless that table is also ported and populated with a single "Default" record.

---

## Why keep `tenant_id` columns at all?

You may notice `tenant_id` columns still present in some Upstream `models.py` files. This is maintained to:
1.  **Facilitate "Up-porting"**: Making it easier to push Upstream improvements back into SaaS.
2.  **Schema Parity**: Keeping migration scripts somewhat aligned.
3.  **Future-proofing**: Allowing an Upstream instance to eventually support multiple "departments" without a full rewrite.

**However, logically, the code should treat the environment as single-tenant.**

---

## Common Mistakes to Avoid

1.  **Hard-requiring `tenant_id` in CLI commands**: User should not have to provide a UUID to run a local sync.
2.  **Complex RLS (Row Level Security)**: Unnecessary overhead for single-tenant deployments.
3.  **Subdomain Routing**: Upstream usually runs on `localhost` or a single IP.

If you find yourself passing `tenant_id="default"` everywhere, consider refactoring the service to handle the default context internally.
