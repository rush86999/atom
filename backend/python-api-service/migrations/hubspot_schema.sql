-- HubSpot Integration Database Schema
-- PostgreSQL schema for HubSpot OAuth tokens and user/company data

-- OAuth tokens table for storing authentication credentials
CREATE TABLE IF NOT EXISTS hubspot_oauth_tokens (
    user_id TEXT PRIMARY KEY,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_type TEXT DEFAULT 'Bearer',
    expires_in INTEGER DEFAULT 3600,
    hub_id TEXT,
    hub_domain TEXT,
    app_id TEXT,
    scopes TEXT[] DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User/account data table for storing HubSpot user information
CREATE TABLE IF NOT EXISTS hubspot_user_data (
    user_id TEXT PRIMARY KEY,
    hub_id TEXT NOT NULL,
    user_email TEXT,
    user_name TEXT,
    first_name TEXT,
    last_name TEXT,
    portal_id TEXT,
    account_type TEXT,
    time_zone TEXT,
    currency TEXT,
    super_admin BOOLEAN,
    is_super_admin BOOLEAN,
    is_primary_user BOOLEAN,
    role_id INTEGER,
    role_name TEXT,
    user_teams JSONB DEFAULT '[]',
    permissions JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Portal/company data table for storing HubSpot portal information
CREATE TABLE IF NOT EXISTS hubspot_portal_data (
    user_id TEXT PRIMARY KEY,
    portal_id TEXT NOT NULL,
    company_name TEXT,
    domain TEXT,
    currency TEXT,
    time_zone TEXT,
    portal_type TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_hubspot_oauth_tokens_updated_at ON hubspot_oauth_tokens(updated_at);
CREATE INDEX IF NOT EXISTS idx_hubspot_oauth_tokens_user_id ON hubspot_oauth_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_hubspot_oauth_tokens_hub_id ON hubspot_oauth_tokens(hub_id);
CREATE INDEX IF NOT EXISTS idx_hubspot_oauth_tokens_scopes ON hubspot_oauth_tokens USING GIN(scopes);
CREATE INDEX IF NOT EXISTS idx_hubspot_user_data_hub_id ON hubspot_user_data(hub_id);
CREATE INDEX IF NOT EXISTS idx_hubspot_user_data_portal_id ON hubspot_user_data(portal_id);
CREATE INDEX IF NOT EXISTS idx_hubspot_user_data_user_email ON hubspot_user_data(user_email);
CREATE INDEX IF NOT EXISTS idx_hubspot_user_data_is_super_admin ON hubspot_user_data(is_super_admin);
CREATE INDEX IF NOT EXISTS idx_hubspot_user_data_updated_at ON hubspot_user_data(updated_at);
CREATE INDEX IF NOT EXISTS idx_hubspot_portal_data_portal_id ON hubspot_portal_data(portal_id);
CREATE INDEX IF NOT EXISTS idx_hubspot_portal_data_company_name ON hubspot_portal_data(company_name);
CREATE INDEX IF NOT EXISTS idx_hubspot_portal_data_domain ON hubspot_portal_data(domain);
CREATE INDEX IF NOT EXISTS idx_hubspot_portal_data_updated_at ON hubspot_portal_data(updated_at);

-- Triggers to automatically update updated_at timestamps
CREATE OR REPLACE FUNCTION update_hubspot_oauth_tokens_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE OR REPLACE FUNCTION update_hubspot_user_data_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE OR REPLACE FUNCTION update_hubspot_portal_data_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers
DROP TRIGGER IF EXISTS trigger_update_hubspot_oauth_tokens_updated_at ON hubspot_oauth_tokens;
CREATE TRIGGER trigger_update_hubspot_oauth_tokens_updated_at
    BEFORE UPDATE ON hubspot_oauth_tokens
    FOR EACH ROW
    EXECUTE FUNCTION update_hubspot_oauth_tokens_updated_at();

DROP TRIGGER IF EXISTS trigger_update_hubspot_user_data_updated_at ON hubspot_user_data;
CREATE TRIGGER trigger_update_hubspot_user_data_updated_at
    BEFORE UPDATE ON hubspot_user_data
    FOR EACH ROW
    EXECUTE FUNCTION update_hubspot_user_data_updated_at();

DROP TRIGGER IF EXISTS trigger_update_hubspot_portal_data_updated_at ON hubspot_portal_data;
CREATE TRIGGER trigger_update_hubspot_portal_data_updated_at
    BEFORE UPDATE ON hubspot_portal_data
    FOR EACH ROW
    EXECUTE FUNCTION update_hubspot_portal_data_updated_at();

-- Row Level Security (RLS) for multi-tenant applications
-- Uncomment if using RLS in your PostgreSQL setup

-- ALTER TABLE hubspot_oauth_tokens ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE hubspot_user_data ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE hubspot_portal_data ENABLE ROW LEVEL SECURITY;

-- Policy examples (adjust based on your authentication system)
-- CREATE POLICY hubspot_oauth_tokens_user_policy ON hubspot_oauth_tokens
--     FOR ALL TO authenticated_users
--     USING (user_id = current_user_id());

-- CREATE POLICY hubspot_user_data_user_policy ON hubspot_user_data
--     FOR ALL TO authenticated_users
--     USING (user_id = current_user_id());

-- CREATE POLICY hubspot_portal_data_user_policy ON hubspot_portal_data
--     FOR ALL TO authenticated_users
--     USING (user_id = current_user_id());

-- Comments for documentation
COMMENT ON TABLE hubspot_oauth_tokens IS 'Stores OAuth tokens for HubSpot API authentication';
COMMENT ON TABLE hubspot_user_data IS 'Stores HubSpot user and account data';
COMMENT ON TABLE hubspot_portal_data IS 'Stores HubSpot portal/company data';

COMMENT ON COLUMN hubspot_oauth_tokens.user_id IS 'ATOM user identifier';
COMMENT ON COLUMN hubspot_oauth_tokens.access_token IS 'HubSpot OAuth access token';
COMMENT ON COLUMN hubspot_oauth_tokens.refresh_token IS 'HubSpot OAuth refresh token (optional)';
COMMENT ON COLUMN hubspot_oauth_tokens.token_type IS 'Token type, usually Bearer';
COMMENT ON COLUMN hubspot_oauth_tokens.expires_in IS 'Token expiration time in seconds';
COMMENT ON COLUMN hubspot_oauth_tokens.hub_id IS 'HubSpot portal/hub identifier';
COMMENT ON COLUMN hubspot_oauth_tokens.hub_domain IS 'HubSpot portal domain';
COMMENT ON COLUMN hubspot_oauth_tokens.app_id IS 'HubSpot application identifier';
COMMENT ON COLUMN hubspot_oauth_tokens.scopes IS 'OAuth scopes granted to the token';
COMMENT ON COLUMN hubspot_oauth_tokens.created_at IS 'Token creation timestamp';
COMMENT ON COLUMN hubspot_oauth_tokens.updated_at IS 'Token last update timestamp';

COMMENT ON COLUMN hubspot_user_data.user_id IS 'ATOM user identifier';
COMMENT ON COLUMN hubspot_user_data.hub_id IS 'HubSpot portal/hub identifier';
COMMENT ON COLUMN hubspot_user_data.user_email IS 'HubSpot user email address';
COMMENT ON COLUMN hubspot_user_data.user_name IS 'HubSpot user full name';
COMMENT ON COLUMN hubspot_user_data.first_name IS 'HubSpot user first name';
COMMENT ON COLUMN hubspot_user_data.last_name IS 'HubSpot user last name';
COMMENT ON COLUMN hubspot_user_data.portal_id IS 'HubSpot portal identifier';
COMMENT ON COLUMN hubspot_user_data.account_type IS 'HubSpot account type';
COMMENT ON COLUMN hubspot_user_data.time_zone IS 'User time zone';
COMMENT ON COLUMN hubspot_user_data.currency IS 'Portal currency';
COMMENT ON COLUMN hubspot_user_data.super_admin IS 'Legacy super admin flag';
COMMENT ON COLUMN hubspot_user_data.is_super_admin IS 'Super admin status';
COMMENT ON COLUMN hubspot_user_data.is_primary_user IS 'Primary user status';
COMMENT ON COLUMN hubspot_user_data.role_id IS 'HubSpot role identifier';
COMMENT ON COLUMN hubspot_user_data.role_name IS 'HubSpot role name';
COMMENT ON COLUMN hubspot_user_data.user_teams IS 'HubSpot user teams';
COMMENT ON COLUMN hubspot_user_data.permissions IS 'User permissions in JSON format';
COMMENT ON COLUMN hubspot_user_data.metadata IS 'Additional user metadata in JSON format';
COMMENT ON COLUMN hubspot_user_data.created_at IS 'User data creation timestamp';
COMMENT ON COLUMN hubspot_user_data.updated_at IS 'User data last update timestamp';

COMMENT ON COLUMN hubspot_portal_data.user_id IS 'ATOM user identifier';
COMMENT ON COLUMN hubspot_portal_data.portal_id IS 'HubSpot portal identifier';
COMMENT ON COLUMN hubspot_portal_data.company_name IS 'Company name';
COMMENT ON COLUMN hubspot_portal_data.domain IS 'Company domain';
COMMENT ON COLUMN hubspot_portal_data.currency IS 'Portal currency';
COMMENT ON COLUMN hubspot_portal_data.time_zone IS 'Portal time zone';
COMMENT ON COLUMN hubspot_portal_data.portal_type IS 'Portal type or category';
COMMENT ON COLUMN hubspot_portal_data.created_at IS 'Portal data creation timestamp';
COMMENT ON COLUMN hubspot_portal_data.updated_at IS 'Portal data last update timestamp';

-- HubSpot marketing data tracking tables (optional for advanced features)
-- Uncomment if you want to track marketing data locally

-- Contact sync cache table
-- CREATE TABLE IF NOT EXISTS hubspot_contact_cache (
--     id SERIAL PRIMARY KEY,
--     user_id TEXT NOT NULL REFERENCES hubspot_user_data(user_id),
--     hub_id TEXT NOT NULL,
--     contact_id TEXT NOT NULL,
--     contact_data JSONB,
--     sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     UNIQUE(hub_id, contact_id)
-- );

-- Company sync cache table
-- CREATE TABLE IF NOT EXISTS hubspot_company_cache (
--     id SERIAL PRIMARY KEY,
--     user_id TEXT NOT NULL REFERENCES hubspot_user_data(user_id),
--     hub_id TEXT NOT NULL,
--     company_id TEXT NOT NULL,
--     company_data JSONB,
--     sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     UNIQUE(hub_id, company_id)
-- );

-- Deal sync cache table
-- CREATE TABLE IF NOT EXISTS hubspot_deal_cache (
--     id SERIAL PRIMARY KEY,
--     user_id TEXT NOT NULL REFERENCES hubspot_user_data(user_id),
--     hub_id TEXT NOT NULL,
--     deal_id TEXT NOT NULL,
--     deal_data JSONB,
--     sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     UNIQUE(hub_id, deal_id)
-- );

-- Campaign sync cache table
-- CREATE TABLE IF NOT EXISTS hubspot_campaign_cache (
--     id SERIAL PRIMARY KEY,
--     user_id TEXT NOT NULL REFERENCES hubspot_user_data(user_id),
--     hub_id TEXT NOT NULL,
--     campaign_id TEXT NOT NULL,
--     campaign_data JSONB,
--     sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     UNIQUE(hub_id, campaign_id)
-- );

-- Analytics cache table for performance
-- CREATE TABLE IF NOT EXISTS hubspot_analytics_cache (
--     id SERIAL PRIMARY KEY,
--     user_id TEXT NOT NULL REFERENCES hubspot_user_data(user_id),
--     hub_id TEXT NOT NULL,
--     analytics_type TEXT NOT NULL,
--     analytics_parameters JSONB,
--     analytics_data JSONB,
--     sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     expires_at TIMESTAMP,
--     UNIQUE(hub_id, analytics_type, md5(analytics_parameters::text))
-- );

-- Lead list membership cache table
-- CREATE TABLE IF NOT EXISTS hubspot_list_membership_cache (
--     id SERIAL PRIMARY KEY,
--     user_id TEXT NOT NULL REFERENCES hubspot_user_data(user_id),
--     hub_id TEXT NOT NULL,
--     list_id TEXT NOT NULL,
--     contact_id TEXT NOT NULL,
--     membership_data JSONB,
--     sync_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
--     UNIQUE(hub_id, list_id, contact_id)
-- );

-- Indexes for cache tables
-- CREATE INDEX IF NOT EXISTS idx_hubspot_contact_cache_hub_contact ON hubspot_contact_cache(hub_id, contact_id);
-- CREATE INDEX IF NOT EXISTS idx_hubspot_contact_cache_sync_time ON hubspot_contact_cache(sync_time);
-- CREATE INDEX IF NOT EXISTS idx_hubspot_company_cache_hub_company ON hubspot_company_cache(hub_id, company_id);
-- CREATE INDEX IF NOT EXISTS idx_hubspot_company_cache_sync_time ON hubspot_company_cache(sync_time);
-- CREATE INDEX IF NOT EXISTS idx_hubspot_deal_cache_hub_deal ON hubspot_deal_cache(hub_id, deal_id);
-- CREATE INDEX IF NOT EXISTS idx_hubspot_deal_cache_sync_time ON hubspot_deal_cache(sync_time);
-- CREATE INDEX IF NOT EXISTS idx_hubspot_campaign_cache_hub_campaign ON hubspot_campaign_cache(hub_id, campaign_id);
-- CREATE INDEX IF NOT EXISTS idx_hubspot_campaign_cache_sync_time ON hubspot_campaign_cache(sync_time);
-- CREATE INDEX IF NOT EXISTS idx_hubspot_analytics_cache_type ON hubspot_analytics_cache(analytics_type);
-- CREATE INDEX IF NOT EXISTS idx_hubspot_analytics_cache_expires ON hubspot_analytics_cache(expires_at);
-- CREATE INDEX IF NOT EXISTS idx_hubspot_list_membership_cache_list_contact ON hubspot_list_membership_cache(list_id, contact_id);

-- Partitioning for large datasets (uncomment if needed)
-- CREATE TABLE hubspot_contact_cache_partitioned (
--     LIKE hubspot_contact_cache INCLUDING ALL
-- ) PARTITION BY RANGE (sync_time);

-- CREATE TABLE hubspot_contact_cache_2024 PARTITION OF hubspot_contact_cache_partitioned
--     FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');

-- Functions for data cleanup
CREATE OR REPLACE FUNCTION cleanup_expired_tokens()
RETURNS void AS $$
BEGIN
    DELETE FROM hubspot_oauth_tokens 
    WHERE updated_at < NOW() - INTERVAL '90 days'
    AND user_id NOT IN (
        SELECT DISTINCT user_id FROM hubspot_user_data 
        WHERE updated_at > NOW() - INTERVAL '90 days'
    );
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION cleanup_old_cache_data()
RETURNS void AS $$
BEGIN
    -- Clean up expired analytics cache data
    DELETE FROM hubspot_analytics_cache 
    WHERE expires_at < NOW();
    
    -- Clean up old sync data (if cache tables exist)
    -- DELETE FROM hubspot_contact_cache WHERE sync_time < NOW() - INTERVAL '30 days';
    -- DELETE FROM hubspot_company_cache WHERE sync_time < NOW() - INTERVAL '30 days';
    -- DELETE FROM hubspot_deal_cache WHERE sync_time < NOW() - INTERVAL '30 days';
    -- DELETE FROM hubspot_campaign_cache WHERE sync_time < NOW() - INTERVAL '30 days';
    -- DELETE FROM hubspot_list_membership_cache WHERE sync_time < NOW() - INTERVAL '30 days';
END;
$$ LANGUAGE plpgsql;

-- Schedule cleanup jobs (requires pg_cron extension)
-- Uncomment if you have pg_cron installed
-- SELECT cron.schedule('cleanup-hubspot-data', '0 2 * * *', 'SELECT cleanup_expired_tokens(); SELECT cleanup_old_cache_data();');