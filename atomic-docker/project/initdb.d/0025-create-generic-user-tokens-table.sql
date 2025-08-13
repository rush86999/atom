-- Create a generic table to store OAuth tokens for all services.
-- This will eventually replace the individual `user_*_oauth_tokens` tables.
CREATE TABLE IF NOT EXISTS public.user_tokens (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    service VARCHAR(50) NOT NULL,
    encrypted_access_token BYTEA,
    encrypted_refresh_token BYTEA,
    token_expiry_timestamp TIMESTAMPTZ,
    metadata JSONB, -- For service-specific data like team_id, account_json, etc.
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, service)
);

-- This assumes the `update_updated_at_column` function is available from a previous migration.

-- Drop the trigger if it already exists on the table to avoid errors on re-run
DROP TRIGGER IF EXISTS set_timestamp ON public.user_tokens;

-- Create the trigger to automatically update the updated_at timestamp
CREATE TRIGGER set_timestamp
BEFORE UPDATE ON public.user_tokens
FOR EACH ROW
EXECUTE PROCEDURE update_updated_at_column();

-- Add comments to the columns for clarity
COMMENT ON TABLE public.user_tokens IS 'Stores encrypted OAuth2 tokens for user connections to various services.';
COMMENT ON COLUMN public.user_tokens.user_id IS 'The unique identifier for the user in our system.';
COMMENT ON COLUMN public.user_tokens.service IS 'The name of the service (e.g., ''slack'', ''msteams'', ''gmail'').';
COMMENT ON COLUMN public.user_tokens.encrypted_access_token IS 'The encrypted OAuth2 access token.';
COMMENT ON COLUMN public.user_tokens.encrypted_refresh_token IS 'The encrypted OAuth2 refresh token.';
COMMENT ON COLUMN public.user_tokens.token_expiry_timestamp IS 'The timestamp indicating when the current access token expires.';
COMMENT ON COLUMN public.user_tokens.metadata IS 'Service-specific metadata, e.g., Slack team_id or MSAL account_json.';
COMMENT ON COLUMN public.user_tokens.created_at IS 'Timestamp of when the record was first created.';
COMMENT ON COLUMN public.user_tokens.updated_at IS 'Timestamp of when the record was last updated.';
