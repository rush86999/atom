-- Zendesk Integration Database Schema
-- PostgreSQL schema for Zendesk OAuth tokens and user data

-- OAuth tokens table for storing authentication credentials
CREATE TABLE IF NOT EXISTS zendesk_oauth_tokens (
    user_id TEXT PRIMARY KEY,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    token_type TEXT DEFAULT 'Bearer',
    expires_in INTEGER DEFAULT 3600,
    scope TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User data table for storing Zendesk user information
CREATE TABLE IF NOT EXISTS zendesk_user_data (
    user_id TEXT PRIMARY KEY,
    zendesk_user_id INTEGER,
    email TEXT,
    name TEXT,
    role TEXT,
    phone TEXT,
    organization_id INTEGER,
    photo_url TEXT,
    time_zone TEXT,
    subdomain TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_zendesk_oauth_tokens_updated_at ON zendesk_oauth_tokens(updated_at);
CREATE INDEX IF NOT EXISTS idx_zendesk_oauth_tokens_user_id ON zendesk_oauth_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_zendesk_user_data_zendesk_user_id ON zendesk_user_data(zendesk_user_id);
CREATE INDEX IF NOT EXISTS idx_zendesk_user_data_email ON zendesk_user_data(email);
CREATE INDEX IF NOT EXISTS idx_zendesk_user_data_subdomain ON zendesk_user_data(subdomain);
CREATE INDEX IF NOT EXISTS idx_zendesk_user_data_updated_at ON zendesk_user_data(updated_at);

-- Triggers to automatically update updated_at timestamps
CREATE OR REPLACE FUNCTION update_zendesk_oauth_tokens_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE OR REPLACE FUNCTION update_zendesk_user_data_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers
DROP TRIGGER IF EXISTS trigger_update_zendesk_oauth_tokens_updated_at ON zendesk_oauth_tokens;
CREATE TRIGGER trigger_update_zendesk_oauth_tokens_updated_at
    BEFORE UPDATE ON zendesk_oauth_tokens
    FOR EACH ROW
    EXECUTE FUNCTION update_zendesk_oauth_tokens_updated_at();

DROP TRIGGER IF EXISTS trigger_update_zendesk_user_data_updated_at ON zendesk_user_data;
CREATE TRIGGER trigger_update_zendesk_user_data_updated_at
    BEFORE UPDATE ON zendesk_user_data
    FOR EACH ROW
    EXECUTE FUNCTION update_zendesk_user_data_updated_at();

-- Row Level Security (RLS) for multi-tenant applications
-- Uncomment if using RLS in your PostgreSQL setup

-- ALTER TABLE zendesk_oauth_tokens ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE zendesk_user_data ENABLE ROW LEVEL SECURITY;

-- Policy examples (adjust based on your authentication system)
-- CREATE POLICY zendesk_oauth_tokens_user_policy ON zendesk_oauth_tokens
--     FOR ALL TO authenticated_users
--     USING (user_id = current_user_id());

-- CREATE POLICY zendesk_user_data_user_policy ON zendesk_user_data
--     FOR ALL TO authenticated_users
--     USING (user_id = current_user_id());

-- Comments for documentation
COMMENT ON TABLE zendesk_oauth_tokens IS 'Stores OAuth tokens for Zendesk API authentication';
COMMENT ON TABLE zendesk_user_data IS 'Stores user data from Zendesk integration';

COMMENT ON COLUMN zendesk_oauth_tokens.user_id IS 'ATOM user identifier';
COMMENT ON COLUMN zendesk_oauth_tokens.access_token IS 'Zendesk OAuth access token';
COMMENT ON COLUMN zendesk_oauth_tokens.refresh_token IS 'Zendesk OAuth refresh token (optional)';
COMMENT ON COLUMN zendesk_oauth_tokens.token_type IS 'Token type, usually Bearer';
COMMENT ON COLUMN zendesk_oauth_tokens.expires_in IS 'Token expiration time in seconds';
COMMENT ON COLUMN zendesk_oauth_tokens.scope IS 'OAuth scopes granted to the token';
COMMENT ON COLUMN zendesk_oauth_tokens.created_at IS 'Token creation timestamp';
COMMENT ON COLUMN zendesk_oauth_tokens.updated_at IS 'Token last update timestamp';

COMMENT ON COLUMN zendesk_user_data.user_id IS 'ATOM user identifier';
COMMENT ON COLUMN zendesk_user_data.zendesk_user_id IS 'Zendesk user ID';
COMMENT ON COLUMN zendesk_user_data.email IS 'Zendesk user email';
COMMENT ON COLUMN zendesk_user_data.name IS 'Zendesk user full name';
COMMENT ON COLUMN zendesk_user_data.role IS 'Zendesk user role (agent, admin, end-user)';
COMMENT ON COLUMN zendesk_user_data.phone IS 'Zendesk user phone number';
COMMENT ON COLUMN zendesk_user_data.organization_id IS 'Zendesk organization ID';
COMMENT ON COLUMN zendesk_user_data.photo_url IS 'Profile photo URL';
COMMENT ON COLUMN zendesk_user_data.time_zone IS 'User time zone';
COMMENT ON COLUMN zendesk_user_data.subdomain IS 'Zendesk subdomain for multi-instance support';
COMMENT ON COLUMN zendesk_user_data.metadata IS 'Additional user metadata in JSON format';
COMMENT ON COLUMN zendesk_user_data.created_at IS 'User data creation timestamp';
COMMENT ON COLUMN zendesk_user_data.updated_at IS 'User data last update timestamp';