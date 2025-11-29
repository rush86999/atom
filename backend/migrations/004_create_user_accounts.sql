-- User Accounts Table
-- Stores linked authentication providers for each user
-- Allows users to sign in with multiple methods (Google, GitHub, Email/Password)

CREATE TABLE IF NOT EXISTS user_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL, -- 'google', 'github', 'credentials'
    provider_account_id VARCHAR(255), -- OAuth provider's user ID
    access_token TEXT, -- OAuth access token (encrypted in production)
    refresh_token TEXT, -- OAuth refresh token (encrypted in production)
    expires_at TIMESTAMP, -- Token expiration
    token_type VARCHAR(50), -- 'Bearer', etc.
    scope TEXT, -- OAuth scopes granted
    id_token TEXT, -- OpenID Connect ID token
    session_state TEXT, -- OAuth session state
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Ensure one provider account per user
    UNIQUE(provider, provider_account_id),
    -- Ensure user can only link one account per provider type
    UNIQUE(user_id, provider)
);

-- Indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_user_accounts_user_id ON user_accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_user_accounts_provider ON user_accounts(provider, provider_account_id);

-- Update timestamp trigger
CREATE TRIGGER update_user_accounts_updated_at BEFORE UPDATE ON user_accounts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Comments for documentation
COMMENT ON TABLE user_accounts IS 'Linked authentication providers for users';
COMMENT ON COLUMN user_accounts.provider IS 'Authentication provider: google, github, credentials';
COMMENT ON COLUMN user_accounts.provider_account_id IS 'Unique identifier from the OAuth provider';
