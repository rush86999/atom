-- DDL for user_github_oauth_tokens table
-- Used to store GitHub OAuth tokens for users.

CREATE TABLE IF NOT EXISTS user_github_oauth_tokens (
    user_id VARCHAR(255) PRIMARY KEY,
    github_user_id VARCHAR(255) NOT NULL,
    github_username VARCHAR(255) NOT NULL,
    access_token TEXT NOT NULL,
    refresh_token TEXT,
    expiry_timestamp_ms BIGINT,
    scopes_granted TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

-- Trigger function to automatically update last_updated_at on row update
CREATE OR REPLACE FUNCTION update_github_last_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
   NEW.last_updated_at = NOW() AT TIME ZONE 'UTC';
   RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER trg_user_github_oauth_tokens_last_updated
BEFORE UPDATE ON user_github_oauth_tokens
FOR EACH ROW
EXECUTE FUNCTION update_github_last_updated_at_column();

COMMENT ON TABLE user_github_oauth_tokens IS 'Stores GitHub OAuth tokens for users.';
COMMENT ON COLUMN user_github_oauth_tokens.user_id IS 'The unique identifier of the application user.';
COMMENT ON COLUMN user_github_oauth_tokens.github_user_id IS 'The GitHub user ID.';
COMMENT ON COLUMN user_github_oauth_tokens.github_username IS 'The GitHub username.';
COMMENT ON COLUMN user_github_oauth_tokens.access_token IS 'The GitHub access token.';
COMMENT ON COLUMN user_github_oauth_tokens.refresh_token IS 'The GitHub refresh token (if available).';
COMMENT ON COLUMN user_github_oauth_tokens.expiry_timestamp_ms IS 'Timestamp (milliseconds since epoch UTC) when the access token expires.';
COMMENT ON COLUMN user_github_oauth_tokens.scopes_granted IS 'Space-separated or JSON array string of OAuth scopes granted.';
COMMENT ON COLUMN user_github_oauth_tokens.created_at IS 'Timestamp when the record was created.';
COMMENT ON COLUMN user_github_oauth_tokens.last_updated_at IS 'Timestamp when the record was last updated.';
