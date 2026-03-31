-- ATOM Upstream Schema Optimizations
-- Ported from atom-saas with all tenant isolation, RLS, billing, and quota enforcement removed
-- Single-tenant architecture for open-source deployment

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- Core Tables (Single-Tenant - No tenant_id columns)
-- ============================================================================

-- Users table (single-tenant - no tenant_id)
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    onboarding_completed BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tasks table (single-tenant - no tenant_id)
CREATE TABLE IF NOT EXISTS tasks (
    id VARCHAR(36) PRIMARY KEY DEFAULT (uuid_generate_v4())::text,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    priority VARCHAR(20) DEFAULT 'medium',
    due_date TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Workflows table (single-tenant - no tenant_id)
CREATE TABLE IF NOT EXISTS workflows (
    id VARCHAR(36) PRIMARY KEY DEFAULT (uuid_generate_v4())::text,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    trigger_type VARCHAR(50) DEFAULT 'manual',
    trigger_config JSONB DEFAULT '{}',
    steps JSONB DEFAULT '[]',
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Workflow runs for execution tracking
CREATE TABLE IF NOT EXISTS workflow_runs (
    id VARCHAR(36) PRIMARY KEY DEFAULT (uuid_generate_v4())::text,
    workflow_id VARCHAR(36) NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    input JSONB,
    output JSONB,
    error TEXT,
    current_step INTEGER DEFAULT 0,
    step_results JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Documents table (single-tenant - no tenant_id)
CREATE TABLE IF NOT EXISTS documents (
    id VARCHAR(36) PRIMARY KEY DEFAULT (uuid_generate_v4())::text,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    content TEXT,
    file_path VARCHAR(1000),
    file_size_bytes BIGINT,
    mime_type VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Calendar events (single-tenant - no tenant_id)
CREATE TABLE IF NOT EXISTS calendar_events (
    id VARCHAR(36) PRIMARY KEY DEFAULT (uuid_generate_v4())::text,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE NOT NULL,
    location VARCHAR(500),
    attendees TEXT[],
    external_id VARCHAR(255),
    external_source VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- AI Conversations (single-tenant - no tenant_id)
CREATE TABLE IF NOT EXISTS ai_conversations (
    id VARCHAR(36) PRIMARY KEY DEFAULT (uuid_generate_v4())::text,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255),
    model_name VARCHAR(100),
    metadata_json JSONB DEFAULT '{}',
    message_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Chat Messages table
CREATE TABLE IF NOT EXISTS chat_messages (
    id VARCHAR(36) PRIMARY KEY DEFAULT (uuid_generate_v4())::text,
    conversation_id VARCHAR(36) NOT NULL,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    model_used VARCHAR(100),
    tokens_used INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- Agent Registry (Single-Tenant - No tenant_id)
-- ============================================================================

CREATE TABLE IF NOT EXISTS agent_registry (
    id VARCHAR(36) PRIMARY KEY DEFAULT (uuid_generate_v4())::text,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    category VARCHAR(50),
    confidence_score DECIMAL(3, 2) DEFAULT 0.5,
    maturity_level VARCHAR(20) DEFAULT 'student',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Agent Task Planning
CREATE TABLE IF NOT EXISTS agent_task_lists (
    id VARCHAR(36) PRIMARY KEY DEFAULT (uuid_generate_v4())::text,
    agent_id VARCHAR(36) NOT NULL REFERENCES agent_registry(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    description TEXT,
    status VARCHAR(50) DEFAULT 'active',
    progress FLOAT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_tasks (
    id VARCHAR(36) PRIMARY KEY DEFAULT (uuid_generate_v4())::text,
    list_id VARCHAR(36) NOT NULL REFERENCES agent_task_lists(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    priority VARCHAR(20) DEFAULT 'medium',
    position INTEGER DEFAULT 0,
    result_summary TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Agent Executions & Traces
CREATE TABLE IF NOT EXISTS agent_executions (
    id VARCHAR(36) PRIMARY KEY DEFAULT (gen_random_uuid())::text,
    agent_id VARCHAR(36) NOT NULL REFERENCES agent_registry(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
    input_summary TEXT,
    result_summary TEXT,
    started_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    triggered_by VARCHAR(50) DEFAULT 'manual',
    metadata JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS agent_trace_steps (
    id VARCHAR(36) PRIMARY KEY DEFAULT (gen_random_uuid())::text,
    execution_id VARCHAR(36) NOT NULL REFERENCES agent_executions(id) ON DELETE CASCADE,
    step_number INTEGER NOT NULL,
    thought TEXT,
    action JSONB,
    observation TEXT,
    final_answer TEXT,
    status VARCHAR(50) DEFAULT 'success',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- Memory and Learning (Single-Tenant - No tenant_id)
-- ============================================================================

CREATE TABLE IF NOT EXISTS memories (
    id VARCHAR(36) PRIMARY KEY DEFAULT (uuid_generate_v4())::text,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE,
    type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    embedding TEXT,
    metadata JSONB NOT NULL DEFAULT '{}',
    platform VARCHAR(20) DEFAULT 'open-source',
    expires TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Learning Models
CREATE TABLE IF NOT EXISTS learning_models (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    domain TEXT NOT NULL,
    algorithm TEXT NOT NULL,
    architecture JSONB,
    parameters JSONB,
    performance JSONB,
    data_stats JSONB,
    version TEXT,
    last_trained_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_model_metrics (
    id VARCHAR(36) PRIMARY KEY DEFAULT (uuid_generate_v4())::text,
    model_id TEXT NOT NULL,
    agent_id VARCHAR(36) NOT NULL REFERENCES agent_registry(id) ON DELETE CASCADE,
    success_rate FLOAT DEFAULT 0,
    total_executions INTEGER DEFAULT 0,
    avg_duration_ms INTEGER DEFAULT 0,
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- OAuth and Integrations (Single-Tenant - No tenant_id)
-- ============================================================================

CREATE TABLE IF NOT EXISTS oauth_tokens (
    id VARCHAR(36) PRIMARY KEY DEFAULT (uuid_generate_v4())::text,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at TIMESTAMP WITH TIME ZONE,
    scopes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, provider)
);

-- Integration OAuth tokens
CREATE TABLE IF NOT EXISTS integration_tokens (
    id VARCHAR(36) PRIMARY KEY DEFAULT (uuid_generate_v4())::text,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    instance_url TEXT,
    expires_at TIMESTAMP WITH TIME ZONE,
    scopes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, provider)
);

-- OAuth state for CSRF protection
CREATE TABLE IF NOT EXISTS oauth_states (
    id VARCHAR(36) PRIMARY KEY DEFAULT (uuid_generate_v4())::text,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,
    state VARCHAR(255) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, provider)
);

-- ============================================================================
-- Desktop Client Tables (Single-Tenant - No tenant_id)
-- ============================================================================

CREATE TABLE IF NOT EXISTS desktop_sessions (
    id VARCHAR(36) PRIMARY KEY DEFAULT (uuid_generate_v4())::text,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE,
    device_id VARCHAR(255) NOT NULL,
    platform VARCHAR(50),
    last_active TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, device_id)
);

CREATE TABLE IF NOT EXISTS desktop_actions (
    id VARCHAR(36) PRIMARY KEY DEFAULT (uuid_generate_v4())::text,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE,
    session_id VARCHAR(36) REFERENCES desktop_sessions(id),
    action_type VARCHAR(50) NOT NULL,
    action_name VARCHAR(255) NOT NULL,
    metadata JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    success BOOLEAN DEFAULT true,
    duration_ms INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================================
-- Media Playlists (Single-Tenant - No tenant_id)
-- ============================================================================

CREATE TABLE IF NOT EXISTS media_playlists (
    id VARCHAR(36) PRIMARY KEY DEFAULT (uuid_generate_v4())::text,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(20) NOT NULL,
    external_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    is_public BOOLEAN DEFAULT false,
    track_count INTEGER DEFAULT 0,
    snapshot_id VARCHAR(255),
    artwork_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, provider, external_id)
);

CREATE TABLE IF NOT EXISTS media_playlist_tracks (
    id VARCHAR(36) PRIMARY KEY DEFAULT (uuid_generate_v4())::text,
    playlist_id VARCHAR(36) NOT NULL REFERENCES media_playlists(id) ON DELETE CASCADE,
    track_uri VARCHAR(500) NOT NULL,
    track_name VARCHAR(255) NOT NULL,
    artist_names TEXT[],
    album_name VARCHAR(255),
    duration_ms INTEGER,
    position INTEGER NOT NULL,
    added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(playlist_id, track_uri)
);

CREATE TABLE IF NOT EXISTS media_recommendations (
    id VARCHAR(36) PRIMARY KEY DEFAULT (uuid_generate_v4())::text,
    user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE,
    seed_track_uri VARCHAR(500),
    seed_artist_names TEXT[],
    recommended_track_uris TEXT[] NOT NULL,
    provider VARCHAR(20) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    feedback_score INTEGER,
    source VARCHAR(50),
    metadata JSONB
);

-- ============================================================================
-- Optimizations (Ported from SaaS, adapted for single-tenant)
-- ============================================================================

-- User indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_created ON users(created_at DESC);

-- Task indexes
CREATE INDEX idx_tasks_user ON tasks(user_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_due_date ON tasks(due_date);

-- Workflow indexes
CREATE INDEX idx_workflows_user ON workflows(user_id);
CREATE INDEX idx_workflows_enabled ON workflows(enabled);
CREATE INDEX idx_workflow_runs_workflow ON workflow_runs(workflow_id);
CREATE INDEX idx_workflow_runs_status ON workflow_runs(status);
CREATE INDEX idx_workflow_runs_created ON workflow_runs(created_at DESC);

-- Document indexes
CREATE INDEX idx_documents_user ON documents(user_id);
CREATE INDEX idx_documents_created ON documents(created_at DESC);

-- Calendar indexes
CREATE INDEX idx_calendar_events_user ON calendar_events(user_id);
CREATE INDEX idx_calendar_events_time ON calendar_events(start_time, end_time);

-- Chat indexes
CREATE INDEX idx_ai_conversations_user ON ai_conversations(user_id);
CREATE INDEX idx_chat_messages_conversation ON chat_messages(conversation_id);
CREATE INDEX idx_chat_messages_created ON chat_messages(created_at DESC);

-- Agent indexes (Governance Optimization: Fast lookup for confidence and maturity)
CREATE INDEX idx_agents_user ON agent_registry(user_id);
CREATE INDEX idx_agents_governance_composite ON agent_registry(user_id, confidence_score, maturity_level) INCLUDE (name);
CREATE INDEX idx_agents_status ON agent_registry(status);

-- Agent task indexes
CREATE INDEX idx_agent_task_lists_agent ON agent_task_lists(agent_id);
CREATE INDEX idx_agent_tasks_list ON agent_tasks(list_id);
CREATE INDEX idx_agent_tasks_status ON agent_tasks(status);

-- Agent execution indexes
CREATE INDEX idx_agent_executions_agent ON agent_executions(agent_id);
CREATE INDEX idx_agent_executions_status ON agent_executions(status);
CREATE INDEX idx_agent_executions_started ON agent_executions(started_at DESC);
CREATE INDEX idx_agent_trace_steps_execution ON agent_trace_steps(execution_id);

-- Memory indexes
CREATE INDEX idx_memories_user_type ON memories(user_id, type);
CREATE INDEX idx_memories_created_at ON memories(created_at DESC);

-- Learning indexes
CREATE INDEX idx_agent_model_metrics_agent ON agent_model_metrics(agent_id);
CREATE INDEX idx_agent_model_metrics_model ON agent_model_metrics(model_id);

-- OAuth indexes
CREATE INDEX idx_oauth_tokens_user ON oauth_tokens(user_id);
CREATE INDEX idx_integration_tokens_user ON integration_tokens(user_id);
CREATE INDEX idx_integration_tokens_provider ON integration_tokens(provider);

-- Desktop indexes
CREATE INDEX idx_desktop_sessions_user ON desktop_sessions(user_id);
CREATE INDEX idx_desktop_sessions_active ON desktop_sessions(last_active DESC);
CREATE INDEX idx_desktop_actions_user ON desktop_actions(user_id);
CREATE INDEX idx_desktop_actions_type ON desktop_actions(action_type);
CREATE INDEX idx_desktop_actions_timestamp ON desktop_actions(timestamp DESC);

-- Media indexes
CREATE INDEX idx_media_playlists_user ON media_playlists(user_id);
CREATE INDEX idx_media_playlists_provider ON media_playlists(provider);
CREATE INDEX idx_media_playlist_tracks_playlist ON media_playlist_tracks(playlist_id);
CREATE INDEX idx_media_recommendations_user ON media_recommendations(user_id);
CREATE INDEX idx_media_recommendations_created ON media_recommendations(created_at DESC);
CREATE INDEX idx_media_recommendations_feedback ON media_recommendations(feedback_score);

-- ============================================================================
-- Triggers (No tenant-specific triggers needed)
-- ============================================================================

-- Trigger to update timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply timestamp triggers to tables with updated_at
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_tasks_updated_at BEFORE UPDATE ON tasks FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_workflows_updated_at BEFORE UPDATE ON workflows FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_calendar_events_updated_at BEFORE UPDATE ON calendar_events FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_ai_conversations_updated_at BEFORE UPDATE ON ai_conversations FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_agents_updated_at BEFORE UPDATE ON agent_registry FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_agent_task_lists_updated_at BEFORE UPDATE ON agent_task_lists FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_agent_tasks_updated_at BEFORE UPDATE ON agent_tasks FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_memories_updated_at BEFORE UPDATE ON memories FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_learning_models_updated_at BEFORE UPDATE ON learning_models FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_oauth_tokens_updated_at BEFORE UPDATE ON oauth_tokens FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_integration_tokens_updated_at BEFORE UPDATE ON integration_tokens FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_media_playlists_updated_at BEFORE UPDATE ON media_playlists FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Notes on SaaS Optimizations Ported
-- ============================================================================

-- This schema includes optimizations from atom-saas/database/multitenancy_schema.sql:
-- 1. Composite indexes for governance (idx_agents_governance_composite)
-- 2. Covering indexes with INCLUDE clause (PostgreSQL 11+)
-- 3. Time-series indexes with DESC ordering (created_at, started_at)
-- 4. Multi-column indexes for common query patterns (user_id, status)
--
-- SaaS-specific patterns REMOVED:
-- - All tenant_id columns and foreign keys
-- - All ROW LEVEL SECURITY (RLS) policies
-- - All tenant isolation functions (set_tenant_context, is_super_admin)
-- - All tenant-scoped indexes (adapted to user_id-scoped)
-- - All billing/quota tables and columns
-- - All Stripe integration columns
-- - All usage tracking tables
--
-- This schema is suitable for single-tenant deployments only.
