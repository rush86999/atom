-- ATOM PostgreSQL Migration Script
-- Version: 3.0.0
-- Notion Integration OAuth Tokens Table

-- Create OAuth tokens table if not exists
CREATE TABLE IF NOT EXISTS user_oauth_tokens (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    service_name VARCHAR(50) NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expires_at TIMESTAMP WITH TIME ZONE,
    scope TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted BOOLEAN DEFAULT FALSE
);

-- Add unique constraint for user_id and service_name
ALTER TABLE user_oauth_tokens 
ADD CONSTRAINT user_oauth_tokens_unique 
UNIQUE (user_id, service_name);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_user_oauth_tokens_user_id 
ON user_oauth_tokens(user_id);

CREATE INDEX IF NOT EXISTS idx_user_oauth_tokens_service_name 
ON user_oauth_tokens(service_name);

CREATE INDEX IF NOT EXISTS idx_user_oauth_tokens_created_at 
ON user_oauth_tokens(created_at);

-- Create index for deleted flag
CREATE INDEX IF NOT EXISTS idx_user_oauth_tokens_deleted 
ON user_oauth_tokens(deleted);

-- Create trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_user_oauth_tokens_updated_at 
BEFORE UPDATE ON user_oauth_tokens 
FOR EACH ROW 
EXECUTE FUNCTION update_updated_at_column();

-- Insert Notion-specific table (for backwards compatibility)
CREATE TABLE IF NOT EXISTS user_notion_oauth_tokens (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) UNIQUE NOT NULL,
    encrypted_access_token TEXT NOT NULL,
    encrypted_refresh_token TEXT,
    bot_id VARCHAR(100),
    workspace_name VARCHAR(255),
    workspace_id VARCHAR(100),
    workspace_icon TEXT,
    owner_data JSONB,
    duplicated_template_id VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for Notion table
CREATE INDEX IF NOT EXISTS idx_user_notion_oauth_tokens_user_id 
ON user_notion_oauth_tokens(user_id);

-- Create trigger for Notion table
CREATE TRIGGER update_user_notion_oauth_tokens_updated_at 
BEFORE UPDATE ON user_notion_oauth_tokens 
FOR EACH ROW 
EXECUTE FUNCTION update_updated_at_column();

-- Add comments for documentation
COMMENT ON TABLE user_oauth_tokens IS 'Generic OAuth token storage for all services (GitHub, Slack, Notion, etc.)';
COMMENT ON TABLE user_notion_oauth_tokens IS 'Notion-specific OAuth token storage (legacy, use user_oauth_tokens instead)';

COMMENT ON COLUMN user_oauth_tokens.access_token IS 'Encrypted OAuth access token';
COMMENT ON COLUMN user_oauth_tokens.refresh_token IS 'Encrypted OAuth refresh token (if supported by service)';
COMMENT ON COLUMN user_oauth_tokens.expires_at IS 'Token expiration timestamp';
COMMENT ON COLUMN user_oauth_tokens.scope IS 'OAuth permission scopes';
COMMENT ON COLUMN user_oauth_tokens.metadata IS 'Additional service-specific metadata (JSON)';

-- Migration complete
SELECT 'Notion OAuth tables created successfully' AS migration_status;