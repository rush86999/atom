# Infrastructure Optimizations

**Purpose:** Database schema optimizations and infrastructure patterns adapted for single-tenant open-source deployment.

**Scope:** Single-tenant architecture (no tenant isolation, no RLS, no multi-tenancy patterns)

## Contents

- `multitenancy_schema.sql` - Schema optimizations from SaaS (adapted for single-tenant)
- `migrations/` - Optional migration guides (future use)

## Origin

Infrastructure improvements adapted for single-tenant open-source deployment.

**Key adaptations:**
- Removed all `tenant_id` columns
- Removed all Row Level Security (RLS) policies
- Removed all tenant-scoped indexes
- Kept core optimizations (index improvements, constraint optimizations)
- Kept query performance improvements

## Usage

This directory is for **reference only**. The open-source version of ATOM uses a single-tenant architecture.

Review these files to understand:
- Database query optimizations
- Index strategies for agent operations
- Schema patterns for high-performance AI workloads

## Security Note

**DO NOT** copy tenant isolation, RLS policies, or multi-tenancy patterns. The open-source version is explicitly single-tenant by design.
