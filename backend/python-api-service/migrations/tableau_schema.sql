-- Tableau OAuth Integration Database Schema
-- Complete schema for Tableau authentication and data caching

-- Create encryption extension if not exists
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Tableau OAuth tokens table
CREATE TABLE IF NOT EXISTS tableau_oauth_tokens (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_type VARCHAR(50) DEFAULT 'Bearer',
    expires_at TIMESTAMP WITH TIME ZONE,
    scope TEXT DEFAULT 'https://online.tableau.com/auth/sites',
    site_id TEXT,
    site_name TEXT,
    site_content_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    encrypted_tokens TEXT NOT NULL,
    UNIQUE(user_id)
);

-- Tableau workbooks cache
CREATE TABLE IF NOT EXISTS tableau_workbooks_cache (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    workbook_id VARCHAR(255) NOT NULL,
    workbook_data JSONB,
    workbook_name TEXT,
    project_id TEXT,
    project_name TEXT,
    owner_id TEXT,
    owner_name TEXT,
    view_count INTEGER DEFAULT 0,
    size_bytes BIGINT DEFAULT 0,
    is_embedded BOOLEAN DEFAULT FALSE,
    tags TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, workbook_id)
);

-- Tableau projects cache
CREATE TABLE IF NOT EXISTS tableau_projects_cache (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    project_id VARCHAR(255) NOT NULL,
    project_data JSONB,
    project_name TEXT,
    parent_project_id TEXT,
    owner_id TEXT,
    owner_name TEXT,
    workbook_count INTEGER DEFAULT 0,
    datasource_count INTEGER DEFAULT 0,
    is_hidden BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, project_id)
);

-- Tableau data sources cache
CREATE TABLE IF NOT EXISTS tableau_datasources_cache (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    datasource_id VARCHAR(255) NOT NULL,
    datasource_data JSONB,
    datasource_name TEXT,
    datasource_type TEXT,
    project_id TEXT,
    project_name TEXT,
    connection_count INTEGER DEFAULT 0,
    is_extract BOOLEAN DEFAULT FALSE,
    is_certified BOOLEAN DEFAULT FALSE,
    last_refresh TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, datasource_id)
);

-- Tableau views cache
CREATE TABLE IF NOT EXISTS tableau_views_cache (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    view_id VARCHAR(255) NOT NULL,
    view_data JSONB,
    view_name TEXT,
    workbook_id TEXT,
    workbook_name TEXT,
    sheet_id TEXT,
    sheet_name TEXT,
    project_id TEXT,
    project_name TEXT,
    owner_id TEXT,
    owner_name TEXT,
    is_hidden BOOLEAN DEFAULT FALSE,
    view_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, view_id)
);

-- Tableau users cache
CREATE TABLE IF NOT EXISTS tableau_users_cache (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    tableau_user_id VARCHAR(255) NOT NULL,
    user_data JSONB,
    display_name TEXT,
    email TEXT,
    role TEXT,
    site_role TEXT,
    auth_setting TEXT,
    locale TEXT,
    time_zone TEXT,
    workbook_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    last_login TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, tableau_user_id)
);

-- Tableau usage metrics
CREATE TABLE IF NOT EXISTS tableau_usage_metrics (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    workbook_id VARCHAR(255),
    view_id VARCHAR(255),
    metric_type VARCHAR(50) NOT NULL, -- 'view_count', 'unique_viewers', 'duration', 'downloads'
    metric_value NUMERIC,
    metric_date DATE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tableau activity logs
CREATE TABLE IF NOT EXISTS tableau_activity_logs (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    action VARCHAR(255) NOT NULL,
    action_details JSONB,
    status VARCHAR(50) DEFAULT 'success',
    error_message TEXT,
    workbook_id VARCHAR(255),
    view_id VARCHAR(255),
    project_id VARCHAR(255),
    datasource_id VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tableau refresh schedules
CREATE TABLE IF NOT EXISTS tableau_refresh_schedules (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    workbook_id VARCHAR(255),
    datasource_id VARCHAR(255),
    schedule_name TEXT NOT NULL,
    schedule_type VARCHAR(50) NOT NULL, -- 'extract', 'subscription'
    frequency VARCHAR(50), -- 'hourly', 'daily', 'weekly', 'monthly'
    next_run TIMESTAMP WITH TIME ZONE,
    last_run TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_tableau_oauth_user_id ON tableau_oauth_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_tableau_oauth_email ON tableau_oauth_tokens(email);
CREATE INDEX IF NOT EXISTS idx_tableau_oauth_updated_at ON tableau_oauth_tokens(updated_at);

CREATE INDEX IF NOT EXISTS idx_tableau_workbooks_user_id ON tableau_workbooks_cache(user_id);
CREATE INDEX IF NOT EXISTS idx_tableau_workbooks_workbook_id ON tableau_workbooks_cache(workbook_id);
CREATE INDEX IF NOT EXISTS idx_tableau_workbooks_project_id ON tableau_workbooks_cache(project_id);
CREATE INDEX IF NOT EXISTS idx_tableau_workbooks_owner_id ON tableau_workbooks_cache(owner_id);
CREATE INDEX IF NOT EXISTS idx_tableau_workbooks_name ON tableau_workbooks_cache(workbook_name);
CREATE INDEX IF NOT EXISTS idx_tableau_workbooks_updated_at ON tableau_workbooks_cache(updated_at);

CREATE INDEX IF NOT EXISTS idx_tableau_projects_user_id ON tableau_projects_cache(user_id);
CREATE INDEX IF NOT EXISTS idx_tableau_projects_project_id ON tableau_projects_cache(project_id);
CREATE INDEX IF NOT EXISTS idx_tableau_projects_parent_id ON tableau_projects_cache(parent_project_id);
CREATE INDEX IF NOT EXISTS idx_tableau_projects_name ON tableau_projects_cache(project_name);

CREATE INDEX IF NOT EXISTS idx_tableau_datasources_user_id ON tableau_datasources_cache(user_id);
CREATE INDEX IF NOT EXISTS idx_tableau_datasources_datasource_id ON tableau_datasources_cache(datasource_id);
CREATE INDEX IF NOT EXISTS idx_tableau_datasources_project_id ON tableau_datasources_cache(project_id);
CREATE INDEX IF NOT EXISTS idx_tableau_datasources_type ON tableau_datasources_cache(datasource_type);

CREATE INDEX IF NOT EXISTS idx_tableau_views_user_id ON tableau_views_cache(user_id);
CREATE INDEX IF NOT EXISTS idx_tableau_views_view_id ON tableau_views_cache(view_id);
CREATE INDEX IF NOT EXISTS idx_tableau_views_workbook_id ON tableau_views_cache(workbook_id);
CREATE INDEX IF NOT EXISTS idx_tableau_views_project_id ON tableau_views_cache(project_id);
CREATE INDEX IF NOT EXISTS idx_tableau_views_name ON tableau_views_cache(view_name);

CREATE INDEX IF NOT EXISTS idx_tableau_users_user_id ON tableau_users_cache(user_id);
CREATE INDEX IF NOT EXISTS idx_tableau_users_tableau_user_id ON tableau_users_cache(tableau_user_id);
CREATE INDEX IF NOT EXISTS idx_tableau_users_email ON tableau_users_cache(email);
CREATE INDEX IF NOT EXISTS idx_tableau_users_role ON tableau_users_cache(site_role);

CREATE INDEX IF NOT EXISTS idx_tableau_usage_user_id ON tableau_usage_metrics(user_id);
CREATE INDEX IF NOT EXISTS idx_tableau_usage_workbook_id ON tableau_usage_metrics(workbook_id);
CREATE INDEX IF NOT EXISTS idx_tableau_usage_view_id ON tableau_usage_metrics(view_id);
CREATE INDEX IF NOT EXISTS idx_tableau_usage_type_date ON tableau_usage_metrics(metric_type, metric_date);

CREATE INDEX IF NOT EXISTS idx_tableau_activity_user_id ON tableau_activity_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_tableau_activity_action ON tableau_activity_logs(action);
CREATE INDEX IF NOT EXISTS idx_tableau_activity_workbook_id ON tableau_activity_logs(workbook_id);
CREATE INDEX IF NOT EXISTS idx_tableau_activity_created_at ON tableau_activity_logs(created_at);

CREATE INDEX IF NOT EXISTS idx_tableau_refresh_user_id ON tableau_refresh_schedules(user_id);
CREATE INDEX IF NOT EXISTS idx_tableau_refresh_workbook_id ON tableau_refresh_schedules(workbook_id);
CREATE INDEX IF NOT EXISTS idx_tableau_refresh_datasource_id ON tableau_refresh_schedules(datasource_id);
CREATE INDEX IF NOT EXISTS idx_tableau_refresh_next_run ON tableau_refresh_schedules(next_run);

-- Functions for token management
CREATE OR REPLACE FUNCTION refresh_tableau_tokens(
    p_user_id VARCHAR(255),
    p_new_access_token TEXT,
    p_new_refresh_token TEXT,
    p_expires_at TIMESTAMP WITH TIME ZONE
) RETURNS BOOLEAN AS $$
BEGIN
    UPDATE tableau_oauth_tokens
    SET 
        access_token = p_new_access_token,
        refresh_token = COALESCE(p_new_refresh_token, refresh_token),
        expires_at = p_expires_at,
        updated_at = CURRENT_TIMESTAMP
    WHERE user_id = p_user_id;
    
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION is_tableau_token_expired(
    p_user_id VARCHAR(255)
) RETURNS BOOLEAN AS $$
DECLARE
    v_expires_at TIMESTAMP WITH TIME ZONE;
BEGIN
    SELECT expires_at INTO v_expires_at
    FROM tableau_oauth_tokens
    WHERE user_id = p_user_id AND is_active = TRUE;
    
    RETURN v_expires_at IS NULL OR v_expires_at < CURRENT_TIMESTAMP - INTERVAL '5 minutes';
END;
$$ LANGUAGE plpgsql;

-- Functions for cache management
CREATE OR REPLACE FUNCTION cleanup_tableau_cache(
    p_user_id VARCHAR(255),
    p_days_old INTEGER DEFAULT 30
) RETURNS INTEGER AS $$
DECLARE
    v_deleted_count INTEGER;
BEGIN
    -- Clean up old activity logs
    DELETE FROM tableau_activity_logs
    WHERE user_id = p_user_id
    AND created_at < CURRENT_TIMESTAMP - INTERVAL '1 day';
    
    GET DIAGNOSTICS v_deleted_count = ROW_COUNT;
    
    -- Clean up old usage metrics
    DELETE FROM tableau_usage_metrics
    WHERE user_id = p_user_id
    AND metric_date < CURRENT_TIMESTAMP - INTERVAL '90 days';
    
    RETURN v_deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Trigger for updated_at timestamp
CREATE OR REPLACE FUNCTION update_tableau_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply triggers
CREATE TRIGGER tr_tableau_oauth_tokens_updated
    BEFORE UPDATE ON tableau_oauth_tokens
    FOR EACH ROW
    EXECUTE FUNCTION update_tableau_updated_at();

CREATE TRIGGER tr_tableau_workbooks_updated
    BEFORE UPDATE ON tableau_workbooks_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_tableau_updated_at();

CREATE TRIGGER tr_tableau_projects_updated
    BEFORE UPDATE ON tableau_projects_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_tableau_updated_at();

CREATE TRIGGER tr_tableau_datasources_updated
    BEFORE UPDATE ON tableau_datasources_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_tableau_updated_at();

CREATE TRIGGER tr_tableau_views_updated
    BEFORE UPDATE ON tableau_views_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_tableau_updated_at();

CREATE TRIGGER tr_tableau_users_updated
    BEFORE UPDATE ON tableau_users_cache
    FOR EACH ROW
    EXECUTE FUNCTION update_tableau_updated_at();

CREATE TRIGGER tr_tableau_refresh_updated
    BEFORE UPDATE ON tableau_refresh_schedules
    FOR EACH ROW
    EXECUTE FUNCTION update_tableau_updated_at();

-- Row Level Security (RLS)
ALTER TABLE tableau_oauth_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE tableau_workbooks_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE tableau_projects_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE tableau_datasources_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE tableau_views_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE tableau_users_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE tableau_usage_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE tableau_activity_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE tableau_refresh_schedules ENABLE ROW LEVEL SECURITY;

-- RLS Policies
CREATE POLICY tableau_oauth_tokens_user_policy ON tableau_oauth_tokens
    FOR ALL
    TO authenticated_users
    USING (user_id = current_setting('app.current_user_id')::TEXT);

CREATE POLICY tableau_workbooks_user_policy ON tableau_workbooks_cache
    FOR ALL
    TO authenticated_users
    USING (user_id = current_setting('app.current_user_id')::TEXT);

CREATE POLICY tableau_projects_user_policy ON tableau_projects_cache
    FOR ALL
    TO authenticated_users
    USING (user_id = current_setting('app.current_user_id')::TEXT);

CREATE POLICY tableau_datasources_user_policy ON tableau_datasources_cache
    FOR ALL
    TO authenticated_users
    USING (user_id = current_setting('app.current_user_id')::TEXT);

CREATE POLICY tableau_views_user_policy ON tableau_views_cache
    FOR ALL
    TO authenticated_users
    USING (user_id = current_setting('app.current_user_id')::TEXT);

CREATE POLICY tableau_users_user_policy ON tableau_users_cache
    FOR ALL
    TO authenticated_users
    USING (user_id = current_setting('app.current_user_id')::TEXT);

CREATE POLICY tableau_usage_user_policy ON tableau_usage_metrics
    FOR ALL
    TO authenticated_users
    USING (user_id = current_setting('app.current_user_id')::TEXT);

CREATE POLICY tableau_activity_user_policy ON tableau_activity_logs
    FOR ALL
    TO authenticated_users
    USING (user_id = current_setting('app.current_user_id')::TEXT);

CREATE POLICY tableau_refresh_user_policy ON tableau_refresh_schedules
    FOR ALL
    TO authenticated_users
    USING (user_id = current_setting('app.current_user_id')::TEXT);

COMMIT;