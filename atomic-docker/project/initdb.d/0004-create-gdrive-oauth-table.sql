-- DDL for user_gdrive_oauth_tokens table
-- Used to store Google Drive OAuth tokens for users.

CREATE TABLE IF NOT EXISTS user_gdrive_oauth_tokens (
    user_id VARCHAR(255) PRIMARY KEY,
    gdrive_user_email VARCHAR(255) NOT NULL,
    access_token_encrypted TEXT NOT NULL,
    refresh_token_encrypted TEXT, -- Refresh tokens are not always provided (e.g., for some grant types or re-auths)
    expiry_timestamp_ms BIGINT NOT NULL, -- Stores token expiry time in milliseconds since epoch
    scopes_granted TEXT, -- Comma-separated string of granted scopes, or JSON array string
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    last_updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC')
);

-- Optional: Add an index on gdrive_user_email if lookups by email are frequent, though user_id is primary.
-- CREATE INDEX IF NOT EXISTS idx_gdrive_user_email ON user_gdrive_oauth_tokens(gdrive_user_email);

-- Trigger function to automatically update last_updated_at on row update
CREATE OR REPLACE FUNCTION update_last_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
   NEW.last_updated_at = NOW() AT TIME ZONE 'UTC';
   RETURN NEW;
END;
$$ language 'plpgsql';

CREATE OR REPLACE TRIGGER trg_user_gdrive_oauth_tokens_last_updated
BEFORE UPDATE ON user_gdrive_oauth_tokens
FOR EACH ROW
EXECUTE FUNCTION update_last_updated_at_column();

COMMENT ON TABLE user_gdrive_oauth_tokens IS 'Stores encrypted Google Drive OAuth tokens for users.';
COMMENT ON COLUMN user_gdrive_oauth_tokens.user_id IS 'The unique identifier of the application user.';
COMMENT ON COLUMN user_gdrive_oauth_tokens.gdrive_user_email IS 'The email address of the Google account associated with the tokens.';
COMMENT ON COLUMN user_gdrive_oauth_tokens.access_token_encrypted IS 'Fernet-encrypted Google Drive access token.';
COMMENT ON COLUMN user_gdrive_oauth_tokens.refresh_token_encrypted IS 'Fernet-encrypted Google Drive refresh token (if available).';
COMMENT ON COLUMN user_gdrive_oauth_tokens.expiry_timestamp_ms IS 'Timestamp (milliseconds since epoch UTC) when the access token expires.';
COMMENT ON COLUMN user_gdrive_oauth_tokens.scopes_granted IS 'Space-separated or JSON array string of OAuth scopes granted.';
COMMENT ON COLUMN user_gdrive_oauth_tokens.created_at IS 'Timestamp when the record was created.';
COMMENT ON COLUMN user_gdrive_oauth_tokens.last_updated_at IS 'Timestamp when the record was last updated.';

-- Note: The UPSERT logic in db_oauth_gdrive.py handles the ON CONFLICT (user_id) DO UPDATE SET ...
-- which also updates last_updated_at = NOW() AT TIME ZONE 'UTC'.
-- The trigger above is a belt-and-suspenders approach for any other direct UPDATE statements
-- that might be run on the table outside of that specific UPSERT.
-- If all writes go through the UPSERT, the trigger's update to last_updated_at might be redundant
-- for those specific operations but ensures it for other direct updates.
-- The UPSERT's explicit setting of last_updated_at will take precedence for that statement.
-- If only UPSERT is used, the trigger could be simplified or removed if the UPSERT always sets it.
-- Keeping it for robustness against other update paths.
```
