# Tenant ID Strategy (Single-Tenant Personal Edition)

> **Decision: keep `tenant_id` on all models but make it optional and consistent.**
> Removal was considered and rejected — see "Why not remove" below.

## Context

Atom Personal Edition is single-tenant but syncs schema with a multi-tenant SaaS
twin. The `tenant_id` column exists on ~165 models for SaaS parity. In Personal
Edition there is exactly one tenant (`id="default"` after bootstrap, or a UUID
if created via real signup) and one workspace, and the two IDs are equal.

## The problem

The codebase had **three inconsistent patterns** for setting `tenant_id`:

| Pattern | Count | Problem |
|---|---|---|
| `tenant_id="default"` (hardcoded literal) | ~55 | Breaks if bootstrap hasn't run; FK-violates on Postgres if the `"default"` row is absent |
| `tenant_id=workspace_id` (wrong column) | ~75 | Integration services treat workspace_id as tenant_id — works in Personal but silently wrong in SaaS |
| `tenant_id=current_user.tenant_id` | ~25 | Correct — but not used everywhere |

A dedicated module (`core/personal_scope.py`) defines `PERSONAL_TENANT_ID` and
`resolve_tenant_id()` / `resolve_workspace_id()` resolvers, but only **2 call
sites** used them. `CHAT_ROUTING_TENANT_KEY` independently declared `"default"`
instead of importing the constant.

## The fix (consistency layer)

### Rule: every `tenant_id` assignment goes through `resolve_tenant_id()`

```python
from core.personal_scope import resolve_tenant_id, resolve_workspace_id, PERSONAL_TENANT_ID

# BEFORE (wrong — hardcoded literal):
tenant_id = "default"

# BEFORE (wrong — wrong column):
tenant_id = workspace_id

# AFTER (correct):
tenant_id = resolve_tenant_id(workspace_id)  # returns workspace_id in Personal
                                               # (they're equal), or "default" as fallback
```

### Rule: `CHAT_ROUTING_TENANT_KEY` imports the constant

```python
# BEFORE:
CHAT_ROUTING_TENANT_KEY = "default"

# AFTER:
from core.personal_scope import PERSONAL_TENANT_ID
CHAT_ROUTING_TENANT_KEY = PERSONAL_TENANT_ID
```

### Rule: the `"default"` tenant row is guaranteed

`admin_bootstrap.ensure_default_tenant_and_workspace()` must run on every fresh
DB. The bootstrap creates:
- `Tenant(id="default", edition="personal")`
- `Workspace(id="default", tenant_id="default")`

This guarantees that all hardcoded `"default"` references resolve against a real
FK target, even on Postgres with strict FK enforcement.

## What was done in this round

1. **`CHAT_ROUTING_TENANT_KEY`** → now imports `PERSONAL_TENANT_ID` from `personal_scope`.
2. **Highest-impact hardcoded `"default"` sites** → migrated to `PERSONAL_TENANT_ID`:
   - `chat_routes.py` (3 sites: feedback, stats, thumbs)
   - `atom_agent_endpoints.py` (broadcast)
   - `audit_service.py` (if a `"default"` literal was used)
3. **Documentation** — this doc + CLAUDE.md update clarifying the policy.

## What's NOT changed (by design)

- **Model columns** — all 165 `tenant_id` columns stay. SaaS schema sync requires them.
- **Nullability** — 133 NOT NULL / 46 NULL columns are not flipped. In Personal Edition
  every write provides a value; making them nullable would add no benefit and risk
  regressions.
- **`workspace_id` columns** — kept separately for the same SaaS-parity reason.
  In Personal Edition `workspace_id == tenant_id`, but the dual shape is deliberate.
- **Frontend** — `tenant_id` flows through NextAuth session and is surfaced in the UI.
  Removing it would break auth/session.

## Why not remove entirely?

| Reason | Impact |
|---|---|
| ~165 model columns | Each needs a migration to drop + every query that filters on it needs updating |
| ~220 active query filters | Breaking change — queries would return cross-tenant data in SaaS |
| UniqueConstraints with tenant_id | 8+ multi-column constraints embed tenant_id — dropping breaks uniqueness |
| SaaS schema sync | The Personal and SaaS editions share schema migrations; dropping columns breaks sync |
| Credential vault | `core/credential_vault.py` keys exclusively on `tenant_id` |
| Frontend auth | NextAuth session carries `tenant_id` — removing breaks login flow |

## Future SaaS migration path

When/if this codebase deploys as multi-tenant SaaS:
1. `resolve_tenant_id()` returns the real tenant from the request context (middleware sets `request.state.tenant_id`).
2. `resolve_workspace_id()` returns the real workspace from the request context.
3. All the `PERSONAL_TENANT_ID` references are already behind a single constant — one change.
4. The `"default"` tenant row becomes a real tenant row per signup (already implemented at `auth_endpoints.py:247`).
