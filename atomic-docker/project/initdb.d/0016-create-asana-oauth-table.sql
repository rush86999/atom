-- Create the user_asana_oauth_tokens table to store encrypted OAuth tokens for Asana integration.
CREATE TABLE IF NOT EXISTS public.user_asana_oauth_tokens (
    user_id VARCHAR(255) PRIMARY KEY,
    encrypted_access_token BYTEA NOT NULL,
    encrypted_refresh_token BYTEA,
    expires_at TIMESTAMPTZ,
    scope TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Optional: Add a trigger to automatically update the updated_at timestamp on row modification.
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
   NEW.updated_at = NOW();
   RETURN NEW;
END;
$$ language 'plpgsql';

-- Drop the trigger if it already exists on the table to avoid errors on re-run
DROP TRIGGER IF EXISTS set_timestamp ON public.user_asana_oauth_tokens;

-- Create the trigger
CREATE TRIGGER set_timestamp
BEFORE UPDATE ON public.user_asana_oauth_tokens
FOR EACH ROW
EXECUTE PROCEDURE update_updated_at_column();

-- Add comments to the columns for clarity
COMMENT ON TABLE public.user_asana_oauth_tokens IS 'Stores encrypted OAuth2 tokens for user connections to Asana.';
COMMENT ON COLUMN public.user_asana_oauth_tokens.user_id IS 'The unique identifier for the user in our system.';
COMMENT ON COLUMN public.user_asana_oauth_tokens.encrypted_access_token IS 'The encrypted OAuth2 access token.';
COMMENT ON COLUMN public.user_asana_oauth_tokens.encrypted_refresh_token IS 'The encrypted OAuth2 refresh token, used to obtain new access tokens.';
COMMENT ON COLUMN public.user_asana_oauth_tokens.expires_at IS 'The timestamp indicating when the current access token expires.';
COMMENT ON COLUMN public.user_asana_oauth_tokens.scope IS 'A space-separated string of scopes the user has granted.';
COMMENT ON COLUMN public.user_asana_oauth_tokens.created_at IS 'Timestamp of when the record was first created.';
COMMENT ON COLUMN public.user_asana_oauth_tokens.updated_at IS 'Timestamp of when the record was last updated.';
