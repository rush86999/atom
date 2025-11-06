-- Google Drive Integration Database Schema
-- PostgreSQL schema for Google Drive integration

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable pg_trgm for text search
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Enable unaccent for diacritic removal
CREATE EXTENSION IF NOT EXISTS "unaccent";

-- ===========================================
-- GOOGLE DRIVE AUTHENTICATION TABLES
-- ===========================================

-- Google Drive OAuth tokens
CREATE TABLE IF NOT EXISTS google_drive_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    token_type VARCHAR(50) DEFAULT 'Bearer',
    expires_at TIMESTAMP WITH TIME ZONE,
    scope TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    
    CONSTRAINT google_drive_tokens_user_id_unique UNIQUE (user_id)
);

-- Google Drive user profiles
CREATE TABLE IF NOT EXISTS google_drive_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    google_drive_id VARCHAR(255) NOT NULL UNIQUE,
    user_id VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    avatar_url TEXT,
    locale VARCHAR(10),
    timezone VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_sync_at TIMESTAMP WITH TIME ZONE,
    sync_status VARCHAR(20) DEFAULT 'pending',
    sync_error TEXT,
    metadata JSONB DEFAULT '{}',
    
    CONSTRAINT google_drive_users_google_drive_id_unique UNIQUE (google_drive_id),
    CONSTRAINT google_drive_users_user_id_unique UNIQUE (user_id)
);

-- ===========================================
-- GOOGLE DRIVE FILE METADATA TABLES
-- ===========================================

-- Google Drive files and folders
CREATE TABLE IF NOT EXISTS google_drive_files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id VARCHAR(255) NOT NULL UNIQUE,
    user_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    mime_type VARCHAR(255),
    size BIGINT DEFAULT 0,
    created_time TIMESTAMP WITH TIME ZONE,
    modified_time TIMESTAMP WITH TIME ZONE,
    viewed_time TIMESTAMP WITH TIME ZONE,
    description TEXT,
    checksum VARCHAR(255),
    version VARCHAR(50),
    web_view_link TEXT,
    web_content_link TEXT,
    thumbnail_link TEXT,
    file_extension VARCHAR(10),
    is_folder BOOLEAN DEFAULT FALSE,
    is_shared BOOLEAN DEFAULT FALSE,
    is_starred BOOLEAN DEFAULT FALSE,
    is_trashed BOOLEAN DEFAULT FALSE,
    parents TEXT[],
    permissions JSONB DEFAULT '[]',
    owners JSONB DEFAULT '[]',
    last_modified_by VARCHAR(255),
    quota_used BIGINT DEFAULT 0,
    checksum_md5 VARCHAR(32),
    checksum_sha1 VARCHAR(40),
    checksum_sha256 VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    indexed_at TIMESTAMP WITH TIME ZONE,
    content_status VARCHAR(20) DEFAULT 'pending',
    sync_status VARCHAR(20) DEFAULT 'pending',
    sync_error TEXT,
    metadata JSONB DEFAULT '{}',
    
    CONSTRAINT google_drive_files_user_id_idx FOREIGN KEY (user_id) REFERENCES google_drive_users(user_id) ON DELETE CASCADE
);

-- Google Drive file content
CREATE TABLE IF NOT EXISTS google_drive_file_content (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id UUID NOT NULL,
    extracted_text TEXT,
    extracted_metadata JSONB DEFAULT '{}',
    extraction_method VARCHAR(50) DEFAULT 'automatic',
    extraction_status VARCHAR(20) DEFAULT 'pending',
    extraction_error TEXT,
    word_count INTEGER DEFAULT 0,
    character_count INTEGER DEFAULT 0,
    page_count INTEGER DEFAULT 0,
    language VARCHAR(10),
    processed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT google_drive_file_content_file_id_fkey FOREIGN KEY (file_id) REFERENCES google_drive_files(id) ON DELETE CASCADE,
    CONSTRAINT google_drive_file_content_file_id_unique UNIQUE (file_id)
);

-- Google Drive file embeddings
CREATE TABLE IF NOT EXISTS google_drive_file_embeddings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id UUID NOT NULL,
    embedding_model VARCHAR(100) NOT NULL,
    embedding_dimension INTEGER NOT NULL,
    embedding_vector VECTOR(384), -- Using pgvector extension
    embedding_text TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT google_drive_file_embeddings_file_id_fkey FOREIGN KEY (file_id) REFERENCES google_drive_files(id) ON DELETE CASCADE,
    CONSTRAINT google_drive_file_embeddings_file_id_model_unique UNIQUE (file_id, embedding_model)
);

-- ===========================================
-- GOOGLE DRIVE SYNC TABLES
-- ===========================================

-- Google Drive sync subscriptions
CREATE TABLE IF NOT EXISTS google_drive_sync_subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL,
    subscription_id VARCHAR(255) NOT NULL UNIQUE,
    resource_id VARCHAR(255) NOT NULL,
    resource_type VARCHAR(50) NOT NULL, -- 'file', 'folder', 'drive'
    channel_id VARCHAR(255),
    channel_type VARCHAR(50) DEFAULT 'web_hook',
    channel_address TEXT,
    channel_expiration TIMESTAMP WITH TIME ZONE,
    events TEXT[], -- ['add', 'remove', 'update', 'trash', 'untrash', 'change']
    webhook_url TEXT,
    webhook_secret VARCHAR(255),
    include_subfolders BOOLEAN DEFAULT TRUE,
    file_types TEXT[], -- Filter by file types
    sync_interval INTEGER DEFAULT 30, -- seconds
    last_sync_at TIMESTAMP WITH TIME ZONE,
    next_sync_at TIMESTAMP WITH TIME ZONE,
    sync_status VARCHAR(20) DEFAULT 'active',
    sync_error TEXT,
    total_files_synced INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    
    CONSTRAINT google_drive_sync_subscriptions_user_id_fkey FOREIGN KEY (user_id) REFERENCES google_drive_users(user_id) ON DELETE CASCADE
);

-- Google Drive sync events
CREATE TABLE IF NOT EXISTS google_drive_sync_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id VARCHAR(255) UNIQUE,
    subscription_id UUID NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    event_type VARCHAR(50) NOT NULL, -- 'add', 'remove', 'update', 'trash', 'untrash', 'change'
    file_id VARCHAR(255),
    file_name VARCHAR(255),
    mime_type VARCHAR(255),
    size BIGINT,
    created_time TIMESTAMP WITH TIME ZONE,
    modified_time TIMESTAMP WITH TIME ZONE,
    old_parent_ids TEXT[],
    new_parent_ids TEXT[],
    old_name VARCHAR(255),
    new_name VARCHAR(255),
    old_shared BOOLEAN,
    new_shared BOOLEAN,
    content_hash VARCHAR(255),
    change_id VARCHAR(255),
    processing_status VARCHAR(20) DEFAULT 'pending',
    processing_started_at TIMESTAMP WITH TIME ZONE,
    processing_completed_at TIMESTAMP WITH TIME ZONE,
    processing_duration FLOAT,
    processing_error TEXT,
    memory_updated BOOLEAN DEFAULT FALSE,
    webhook_sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    
    CONSTRAINT google_drive_sync_events_subscription_id_fkey FOREIGN KEY (subscription_id) REFERENCES google_drive_sync_subscriptions(id) ON DELETE CASCADE,
    CONSTRAINT google_drive_sync_events_user_id_fkey FOREIGN KEY (user_id) REFERENCES google_drive_users(user_id) ON DELETE CASCADE
);

-- ===========================================
-- GOOGLE DRIVE WORKFLOW AUTOMATION TABLES
-- ===========================================

-- Automation workflows
CREATE TABLE IF NOT EXISTS google_drive_workflows (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    triggers JSONB DEFAULT '[]',
    actions JSONB DEFAULT '[]',
    enabled BOOLEAN DEFAULT TRUE,
    run_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    last_run TIMESTAMP WITH TIME ZONE,
    last_success TIMESTAMP WITH TIME ZONE,
    last_error TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    
    CONSTRAINT google_drive_workflows_user_id_fkey FOREIGN KEY (user_id) REFERENCES google_drive_users(user_id) ON DELETE CASCADE
);

-- Workflow executions
CREATE TABLE IF NOT EXISTS google_drive_workflow_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_id UUID NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    trigger_type VARCHAR(50) NOT NULL,
    trigger_data JSONB DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'running', 'completed', 'failed', 'cancelled'
    started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration FLOAT,
    input_data JSONB DEFAULT '{}',
    output_data JSONB DEFAULT '{}',
    error_message TEXT,
    actions_executed TEXT[],
    logs TEXT[],
    variables JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT google_drive_workflow_executions_workflow_id_fkey FOREIGN KEY (workflow_id) REFERENCES google_drive_workflows(id) ON DELETE CASCADE,
    CONSTRAINT google_drive_workflow_executions_user_id_fkey FOREIGN KEY (user_id) REFERENCES google_drive_users(user_id) ON DELETE CASCADE
);

-- Workflow templates
CREATE TABLE IF NOT EXISTS google_drive_workflow_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100) NOT NULL,
    triggers JSONB DEFAULT '[]',
    actions JSONB DEFAULT '[]',
    variables JSONB DEFAULT '[]',
    icon VARCHAR(10) DEFAULT '🤖',
    tags TEXT[] DEFAULT '{}',
    public BOOLEAN DEFAULT FALSE,
    created_by VARCHAR(255),
    usage_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'
);

-- ===========================================
-- GOOGLE DRIVE SEARCH & ANALYTICS TABLES
-- ===========================================

-- Search history
CREATE TABLE IF NOT EXISTS google_drive_search_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL,
    query TEXT NOT NULL,
    search_type VARCHAR(50) DEFAULT 'semantic',
    filters JSONB DEFAULT '{}',
    results_count INTEGER DEFAULT 0,
    execution_time FLOAT,
    clicked_result_id UUID,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    
    CONSTRAINT google_drive_search_history_user_id_fkey FOREIGN KEY (user_id) REFERENCES google_drive_users(user_id) ON DELETE CASCADE
);

-- Search analytics
CREATE TABLE IF NOT EXISTS google_drive_search_analytics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL,
    date DATE NOT NULL,
    total_searches INTEGER DEFAULT 0,
    unique_queries INTEGER DEFAULT 0,
    average_results FLOAT DEFAULT 0,
    average_execution_time FLOAT DEFAULT 0,
    popular_queries JSONB DEFAULT '{}',
    search_types JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT google_drive_search_analytics_user_id_date_unique UNIQUE (user_id, date)
);

-- File access logs
CREATE TABLE IF NOT EXISTS google_drive_file_access (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_id UUID NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    access_type VARCHAR(50) NOT NULL, -- 'view', 'download', 'share', 'edit'
    access_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ip_address INET,
    user_agent TEXT,
    referrer TEXT,
    session_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    
    CONSTRAINT google_drive_file_access_file_id_fkey FOREIGN KEY (file_id) REFERENCES google_drive_files(id) ON DELETE CASCADE,
    CONSTRAINT google_drive_file_access_user_id_fkey FOREIGN KEY (user_id) REFERENCES google_drive_users(user_id) ON DELETE CASCADE
);

-- ===========================================
-- INDEXES FOR PERFORMANCE
-- ===========================================

-- Google Drive files indexes
CREATE INDEX IF NOT EXISTS idx_google_drive_files_user_id ON google_drive_files(user_id);
CREATE INDEX IF NOT EXISTS idx_google_drive_files_file_id ON google_drive_files(file_id);
CREATE INDEX IF NOT EXISTS idx_google_drive_files_mime_type ON google_drive_files(mime_type);
CREATE INDEX IF NOT EXISTS idx_google_drive_files_modified_time ON google_drive_files(modified_time DESC);
CREATE INDEX IF NOT EXISTS idx_google_drive_files_name ON google_drive_files(name);
CREATE INDEX IF NOT EXISTS idx_google_drive_files_parents ON google_drive_files USING GIN(parents);
CREATE INDEX IF NOT EXISTS idx_google_drive_files_is_folder ON google_drive_files(is_folder);
CREATE INDEX IF NOT EXISTS idx_google_drive_files_is_shared ON google_drive_files(is_shared);
CREATE INDEX IF NOT EXISTS idx_google_drive_files_sync_status ON google_drive_files(sync_status);
CREATE INDEX IF NOT EXISTS idx_google_drive_files_content_status ON google_drive_files(content_status);

-- Full-text search index
CREATE INDEX IF NOT EXISTS idx_google_drive_files_name_fts ON google_drive_files USING GIN(to_tsvector('english', unaccent(name)));

-- File content indexes
CREATE INDEX IF NOT EXISTS idx_google_drive_file_content_file_id ON google_drive_file_content(file_id);
CREATE INDEX IF NOT EXISTS idx_google_drive_file_content_extraction_status ON google_drive_file_content(extraction_status);

-- Embeddings indexes
CREATE INDEX IF NOT EXISTS idx_google_drive_file_embeddings_file_id ON google_drive_file_embeddings(file_id);
CREATE INDEX IF NOT EXISTS idx_google_drive_file_embeddings_model ON google_drive_file_embeddings(embedding_model);

-- Vector similarity index (if using pgvector)
CREATE INDEX IF NOT EXISTS idx_google_drive_file_embeddings_vector ON google_drive_file_embeddings USING ivfflat (embedding_vector vector_cosine_ops) WITH (lists = 100);

-- Sync events indexes
CREATE INDEX IF NOT EXISTS idx_google_drive_sync_events_subscription_id ON google_drive_sync_events(subscription_id);
CREATE INDEX IF NOT EXISTS idx_google_drive_sync_events_user_id ON google_drive_sync_events(user_id);
CREATE INDEX IF NOT EXISTS idx_google_drive_sync_events_event_type ON google_drive_sync_events(event_type);
CREATE INDEX IF NOT EXISTS idx_google_drive_sync_events_processing_status ON google_drive_sync_events(processing_status);
CREATE INDEX IF NOT EXISTS idx_google_drive_sync_events_created_at ON google_drive_sync_events(created_at DESC);

-- Workflow indexes
CREATE INDEX IF NOT EXISTS idx_google_drive_workflows_user_id ON google_drive_workflows(user_id);
CREATE INDEX IF NOT EXISTS idx_google_drive_workflows_enabled ON google_drive_workflows(enabled);
CREATE INDEX IF NOT EXISTS idx_google_drive_workflows_last_run ON google_drive_workflows(last_run DESC);

-- Workflow executions indexes
CREATE INDEX IF NOT EXISTS idx_google_drive_workflow_executions_workflow_id ON google_drive_workflow_executions(workflow_id);
CREATE INDEX IF NOT EXISTS idx_google_drive_workflow_executions_user_id ON google_drive_workflow_executions(user_id);
CREATE INDEX IF NOT EXISTS idx_google_drive_workflow_executions_status ON google_drive_workflow_executions(status);
CREATE INDEX IF NOT EXISTS idx_google_drive_workflow_executions_started_at ON google_drive_workflow_executions(started_at DESC);

-- Search history indexes
CREATE INDEX IF NOT EXISTS idx_google_drive_search_history_user_id ON google_drive_search_history(user_id);
CREATE INDEX IF NOT EXISTS idx_google_drive_search_history_query ON google_drive_search_history(query);
CREATE INDEX IF NOT EXISTS idx_google_drive_search_history_created_at ON google_drive_search_history(created_at DESC);

-- Search analytics indexes
CREATE INDEX IF NOT EXISTS idx_google_drive_search_analytics_user_id ON google_drive_search_analytics(user_id);
CREATE INDEX IF NOT EXISTS idx_google_drive_search_analytics_date ON google_drive_search_analytics(date);

-- File access indexes
CREATE INDEX IF NOT EXISTS idx_google_drive_file_access_file_id ON google_drive_file_access(file_id);
CREATE INDEX IF NOT EXISTS idx_google_drive_file_access_user_id ON google_drive_file_access(user_id);
CREATE INDEX IF NOT EXISTS idx_google_drive_file_access_access_type ON google_drive_file_access(access_type);
CREATE INDEX IF NOT EXISTS idx_google_drive_file_access_access_time ON google_drive_file_access(access_time DESC);

-- ===========================================
-- TRIGGERS FOR UPDATED_AT FIELDS
-- ===========================================

-- Function to update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_google_drive_tokens_updated_at BEFORE UPDATE ON google_drive_tokens FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_google_drive_users_updated_at BEFORE UPDATE ON google_drive_users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_google_drive_files_updated_at BEFORE UPDATE ON google_drive_files FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_google_drive_file_content_updated_at BEFORE UPDATE ON google_drive_file_content FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_google_drive_file_embeddings_updated_at BEFORE UPDATE ON google_drive_file_embeddings FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_google_drive_sync_subscriptions_updated_at BEFORE UPDATE ON google_drive_sync_subscriptions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_google_drive_sync_events_updated_at BEFORE UPDATE ON google_drive_sync_events FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_google_drive_workflows_updated_at BEFORE UPDATE ON google_drive_workflows FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_google_drive_workflow_executions_updated_at BEFORE UPDATE ON google_drive_workflow_executions FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_google_drive_workflow_templates_updated_at BEFORE UPDATE ON google_drive_workflow_templates FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_google_drive_search_analytics_updated_at BEFORE UPDATE ON google_drive_search_analytics FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ===========================================
-- VIEWS FOR COMMON QUERIES
-- ===========================================

-- User dashboard view
CREATE OR REPLACE VIEW google_drive_user_dashboard AS
SELECT 
    u.user_id,
    u.email,
    u.name,
    u.last_sync_at,
    u.sync_status,
    COUNT(DISTINCT f.id) as total_files,
    COUNT(DISTINCT CASE WHEN f.is_folder = FALSE THEN f.id END) as file_count,
    COUNT(DISTINCT CASE WHEN f.is_folder = TRUE THEN f.id END) as folder_count,
    SUM(CASE WHEN f.is_folder = FALSE THEN f.size ELSE 0 END) as total_size_used,
    COUNT(DISTINCT CASE WHEN f.is_shared = TRUE THEN f.id END) as shared_files,
    COUNT(DISTINCT s.id) as active_subscriptions,
    COUNT(DISTINCT w.id) as active_workflows,
    MAX(f.modified_time) as last_file_activity
FROM google_drive_users u
LEFT JOIN google_drive_files f ON u.user_id = f.user_id AND f.is_trashed = FALSE
LEFT JOIN google_drive_sync_subscriptions s ON u.user_id = s.user_id AND s.sync_status = 'active'
LEFT JOIN google_drive_workflows w ON u.user_id = w.user_id AND w.enabled = TRUE
GROUP BY u.user_id, u.email, u.name, u.last_sync_at, u.sync_status;

-- Search analytics view
CREATE OR REPLACE VIEW google_drive_search_summary AS
SELECT 
    DATE_TRUNC('day', created_at) as search_date,
    user_id,
    COUNT(*) as total_searches,
    COUNT(DISTINCT query) as unique_queries,
    AVG(results_count) as avg_results,
    AVG(execution_time) as avg_execution_time,
    STRING_AGG(DISTINCT search_type, ',') as search_types_used
FROM google_drive_search_history
GROUP BY DATE_TRUNC('day', created_at), user_id
ORDER BY search_date DESC;

-- Workflow performance view
CREATE OR REPLACE VIEW google_drive_workflow_performance AS
SELECT 
    w.id,
    w.user_id,
    w.name,
    w.enabled,
    w.run_count,
    w.success_count,
    w.error_count,
    w.last_run,
    w.last_success,
    w.last_error,
    CASE 
        WHEN w.run_count > 0 THEN (w.success_count::FLOAT / w.run_count::FLOAT) * 100 
        ELSE 0 
    END as success_rate,
    AVG(e.duration) as avg_execution_time,
    MAX(e.duration) as max_execution_time,
    MIN(e.duration) as min_execution_time
FROM google_drive_workflows w
LEFT JOIN google_drive_workflow_executions e ON w.id = e.workflow_id AND e.status = 'completed'
GROUP BY w.id, w.user_id, w.name, w.enabled, w.run_count, w.success_count, w.error_count, w.last_run, w.last_success, w.last_error;

-- ===========================================
-- SAMPLE DATA (FOR DEVELOPMENT)
-- ===========================================

-- Insert sample workflow templates
INSERT INTO google_drive_workflow_templates (name, description, category, triggers, actions, icon, tags, public) VALUES
(
    'File Backup',
    'Automatically backup files to a specific folder',
    'Backup',
    '[{"type": "file_created", "config": {}, "conditions": [{"field": "trigger_data.mime_type", "operator": "contains", "value": "application/pdf"}]}]',
    '[{"type": "copy_file", "config": {"file_id": "{{trigger_data.file_id}}", "new_name": "{{trigger_data.file_name}}_backup", "parent_ids": ["backup_folder_id"]}}]',
    '📁',
    ARRAY['backup', 'copy', 'automation'],
    TRUE
),
(
    'File Organization',
    'Automatically organize files into folders based on type',
    'Organization',
    '[{"type": "file_created", "config": {}, "conditions": []}]',
    '[{"type": "condition_check", "config": {"conditions": [{"field": "trigger_data.mime_type", "operator": "contains", "value": "image/"}], "logic": "and"}}, {"type": "move_file", "config": {"file_id": "{{trigger_data.file_id}}", "add_parents": ["images_folder_id"]}}]',
    '📂',
    ARRAY['organization', 'folders', 'automation'],
    TRUE
),
(
    'Document Processing',
    'Process uploaded documents and extract content',
    'Processing',
    '[{"type": "file_created", "config": {}, "conditions": [{"field": "trigger_data.mime_type", "operator": "in", "value": ["application/pdf", "application/msword", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]}]}]',
    '[{"type": "extract_text", "config": {"file_id": "{{trigger_data.file_id}}"}}, {"type": "update_database", "config": {"table": "documents", "data": {"file_id": "{{trigger_data.file_id}}", "file_name": "{{trigger_data.file_name}}", "extracted_text": "{{extracted_text}}"}}}]',
    '📄',
    ARRAY['processing', 'extraction', 'automation'],
    TRUE
);

-- ===========================================
-- PERFORMANCE OPTIMIZATION
-- ===========================================

-- Set table statistics for better query planning
ANALYZE google_drive_files;
ANALYZE google_drive_file_content;
ANALYZE google_drive_file_embeddings;
ANALYZE google_drive_sync_events;
ANALYZE google_drive_workflows;
ANALYZE google_drive_workflow_executions;

-- Configure vacuum settings for optimal performance
ALTER TABLE google_drive_files SET (autovacuum_vacuum_scale_factor = 0.1);
ALTER TABLE google_drive_file_content SET (autovacuum_vacuum_scale_factor = 0.1);
ALTER TABLE google_drive_sync_events SET (autovacuum_vacuum_scale_factor = 0.1);
ALTER TABLE google_drive_workflow_executions SET (autovacuum_vacuum_scale_factor = 0.1);

-- ===========================================
-- COMPLETION MESSAGE
-- ===========================================

DO $$
BEGIN
    RAISE NOTICE 'Google Drive database schema created successfully!';
    RAISE NOTICE '';
    RAISE NOTICE 'Tables created:';
    RAISE NOTICE '- google_drive_tokens (OAuth tokens)';
    RAISE NOTICE '- google_drive_users (User profiles)';
    RAISE NOTICE '- google_drive_files (File metadata)';
    RAISE NOTICE '- google_drive_file_content (Extracted content)';
    RAISE NOTICE '- google_drive_file_embeddings (Vector embeddings)';
    RAISE NOTICE '- google_drive_sync_subscriptions (Sync subscriptions)';
    RAISE NOTICE '- google_drive_sync_events (Change events)';
    RAISE NOTICE '- google_drive_workflows (Automation workflows)';
    RAISE NOTICE '- google_drive_workflow_executions (Workflow executions)';
    RAISE NOTICE '- google_drive_workflow_templates (Workflow templates)';
    RAISE NOTICE '- google_drive_search_history (Search analytics)';
    RAISE NOTICE '- google_drive_search_analytics (Search statistics)';
    RAISE NOTICE '- google_drive_file_access (Access logs)';
    RAISE NOTICE '';
    RAISE NOTICE 'Indexes created for optimal performance';
    RAISE NOTICE 'Views created for common queries';
    RAISE NOTICE 'Triggers created for updated_at columns';
    RAISE NOTICE 'Sample workflow templates inserted';
    RAISE NOTICE '';
    RAISE NOTICE 'Database is ready for Google Drive integration!';
END $$;