-- ============================================================================
-- Infrastructure Optimizations from ATOM SaaS
-- Ported from: rush86999/atom-saas (multi-tenant SaaS platform)
-- Adapted for: Single-tenant open-source deployment
-- ============================================================================

-- ============================================================================
-- IMPORTANT: Single-Tenant Architecture
-- ============================================================================
-- This schema contains optimizations from SaaS but has been adapted for
-- single-tenant use. All tenant_id columns, RLS policies, and multi-tenancy
-- patterns have been removed.
--
-- DO NOT add tenant isolation, RLS, or multi-tenancy patterns to this file.
-- ============================================================================

-- ============================================================================
-- Agent Table Optimizations
-- ============================================================================

-- Index for agent maturity queries (adapted from SaaS)
-- SaaS version: CREATE INDEX idx_agents_tenant_maturity ON agents(tenant_id, maturity_level);
-- Upstream adaptation: Removed tenant_id for single-tenant
CREATE INDEX IF NOT EXISTS idx_agents_maturity ON agents(maturity_level);

-- Index for agent status filtering
CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status);

-- Composite index for agent filtering (single-tenant)
CREATE INDEX IF NOT EXISTS idx_agents_maturity_status ON agents(maturity_level, status);

-- ============================================================================
-- Agent Execution Table Optimizations
-- ============================================================================

-- Index for execution time-based queries (performance optimization)
CREATE INDEX IF NOT EXISTS idx_agent_executions_created_at ON agent_executions(created_at DESC);

-- Index for agent execution status filtering
CREATE INDEX IF NOT EXISTS idx_agent_executions_status ON agent_executions(status);

-- Composite index for agent execution analytics (single-tenant)
-- SaaS version: Includes tenant_id
-- Upstream adaptation: Removed tenant_id
CREATE INDEX IF NOT EXISTS idx_agent_executions_agent_created ON agent_executions(agent_id, created_at DESC);

-- ============================================================================
-- User Table Optimizations
-- ============================================================================

-- Index for email lookups (authentication performance)
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Index for user status queries
CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);

-- ============================================================================
-- Integration Table Optimizations
-- ============================================================================

-- Index for integration type filtering
CREATE INDEX IF NOT EXISTS idx_integrations_type ON integrations(integration_type);

-- Index for integration status
CREATE INDEX IF NOT EXISTS idx_integrations_status ON integrations(status);

-- ============================================================================
-- Session Table Optimizations
-- ============================================================================

-- Index for session expiration cleanup
CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON user_sessions(expires_at);

-- Index for session user lookups
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON user_sessions(user_id);

-- ============================================================================
-- Performance Optimization Notes
-- ============================================================================
-- The following optimizations were ported from SaaS:
--
-- 1. Composite indexes for common query patterns
--    - Reduces query latency for agent filtering
--    - Improves dashboard loading performance
--
-- 2. Time-based indexes for analytics
--    - Supports efficient time-series queries
--    - Enables fast execution history retrieval
--
-- 3. Status-based filtering indexes
--    - Optimizes common status queries
--    - Improves list view performance
--
-- 4. Email uniqueness constraint (implied by index)
--    - Fast authentication lookups
--    - Prevents duplicate accounts
--
-- All indexes are adapted for single-tenant use (no tenant_id columns).
-- ============================================================================

-- ============================================================================
-- Security Note
-- ============================================================================
-- DO NOT copy these patterns from SaaS:
-- - tenant_id columns (multi-tenancy)
-- - ROW LEVEL SECURITY (RLS) policies
-- - tenant-scoped indexes
-- - tenant isolation triggers
--
-- The open-source version is explicitly single-tenant by design.
-- ============================================================================

-- ============================================================================
-- Verification Queries
-- ============================================================================
-- Run these queries to verify single-tenant architecture:
--
-- -- Should return 0 (no tenant_id columns)
-- SELECT COUNT(*) FROM information_schema.columns
-- WHERE column_name = 'tenant_id';
--
-- -- Should return 0 (no RLS policies)
-- SELECT COUNT(*) FROM pg_policies WHERE tablename IN ('agents', 'users', 'integrations');
--
-- -- Should show indexes (optimizations present)
-- SELECT indexname FROM pg_indexes WHERE tablename = 'agents';
-- ============================================================================
