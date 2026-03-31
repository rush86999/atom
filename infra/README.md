# Infrastructure Optimizations

**Purpose:** Database schema optimizations and infrastructure patterns from ATOM SaaS, adapted for single-tenant open-source deployment.

**Scope:** Single-tenant architecture (no tenant isolation, no RLS, no multi-tenancy patterns)

## Contents

- `multitenancy_schema.sql` - Schema optimizations from SaaS (adapted for single-tenant)
- `migrations/` - Optional migration guides (future use)

## Origin

These infrastructure improvements were ported from `rush86999/atom-saas` (multi-tenant SaaS platform) and adapted for single-tenant use in the open-source version.

**Key adaptations:**
- Removed all `tenant_id` columns
- Removed all Row Level Security (RLS) policies
- Removed all tenant-scoped indexes
- Kept core optimizations (index improvements, constraint optimizations)
- Kept query performance improvements

## Usage

This directory is for **reference only**. The open-source version of ATOM uses a single-tenant architecture, so multi-tenancy patterns have been removed.

Review these files to understand:
- How SaaS optimizes database queries
- Index strategies for agent operations
- Schema patterns for high-performance AI workloads

## Security Note

**DO NOT** copy tenant isolation, RLS policies, or multi-tenancy patterns from SaaS to this repository. The open-source version is explicitly single-tenant by design.

For SaaS multi-tenancy patterns, see: `rush86999/atom-saas/backend-saas/database/`
