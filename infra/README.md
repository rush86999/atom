# ATOM Upstream Infrastructure

**Purpose:** Infrastructure optimizations and schemas for open-source ATOM platform.

**Scope:** Single-tenant architecture (no tenant isolation, no billing, no quota enforcement).

## Contents

- `multitenancy_schema.sql` - Schema optimizations ported from SaaS (adapted for single-tenant)
- `migrations/` - Future migration scripts (optional)

## Architecture Notes

### Single-Tenant Design

This repository is designed for single-tenant deployments:

- **No tenant_id columns** - All tables are global (no row-level security)
- **No RLS policies** - No row-level security needed for single-tenant
- **No billing/quota** - No payment processing, quota checks, or usage tracking
- **Simplified indexes** - Adapted from SaaS multi-tenant indexes

### Schema Optimizations

Schema files in this directory benefit from optimizations developed in the SaaS version:

- Composite indexes for query performance
- Covering indexes to reduce table lookups
- Constraint optimizations for data integrity

All SaaS-specific patterns (tenant isolation, RLS, billing) have been removed.

## SaaS vs Upstream

| Feature               | SaaS (atom-saas)          | Upstream (atom-upstream) |
| --------------------- | ------------------------- | ------------------------ |
| Tenant isolation      | Multi-tenant (tenant_id)  | Single-tenant (global)   |
| Row-level security    | Enabled (RLS policies)    | Disabled                 |
| Billing enforcement   | Stripe + quota checks     | None                     |
| Payment processing    | Yes                       | No                       |
| Database indexes      | tenant-scoped             | Global                   |
| Redis keys            | `tenant:{tenant_id}:...`  | Global keys              |
| S3 paths              | `{tenant_id}/...`         | Global paths             |

## Usage

### Apply Schema

```bash
psql -U postgres -d atom_upstream -f infra/multitenancy_schema.sql
```

### Verify Single-Tenant

```bash
# Check for tenant_id (should return empty)
grep -n "tenant_id" infra/multitenancy_schema.sql

# Check for RLS (should return empty)
grep -n "ROW LEVEL SECURITY\|ENABLE ROW LEVEL SECURITY" infra/multitenancy_schema.sql
```

## Security

**Important:** This schema is for single-tenant deployments only. Do not add tenant isolation or multi-tenancy patterns to upstream.

For multi-tenant SaaS deployment, use the schema from `atom-saas/database/multitenancy_schema.sql`.

## References

- SaaS Schema: `atom-saas/database/multitenancy_schema.sql`
- Sync Patterns: `.planning/phases/232-ai-orchestration-alignment/SYNC-PATTERNS.md`
- Verification: `.planning/phases/232-ai-orchestration-alignment/SYNC-VERIFICATION.md`
