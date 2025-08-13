-- Create the user_gmail_tokens table to store encrypted OAuth tokens for Gmail integration.
CREATE TABLE IF NOT EXISTS public.user_gmail_tokens (
    user_id VARCHAR(255) PRIMARY KEY,
    encrypted_access_token BYTEA NOT NULL,
    encrypted_refresh_token BYTEA,
    token_expiry_timestamp TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- This assumes the `update_updated_at_column` function is available from a previous migration.

-- Drop the trigger if it already exists on the table to avoid errors on re-run
DROP TRIGGER IF EXISTS set_timestamp ON public.user_gmail_tokens;

-- Create the trigger to automatically update the updated_at timestamp
CREATE TRIGGER set_timestamp
BEFORE UPDATE ON public.user_gmail_tokens
FOR EACH ROW
EXECUTE PROCEDURE update_updated_at_column();

-- Add comments to the columns for clarity
COMMENT ON TABLE public.user_gmail_tokens IS 'Stores encrypted OAuth2 tokens for user connections to Gmail.';
COMMENT ON COLUMN public.user_gmail_tokens.user_id IS 'The unique identifier for the user in our system.';
COMMENT ON COLUMN public.user_gmail_tokens.encrypted_access_token IS 'The encrypted OAuth2 access token.';
COMMENT ON COLUMN public.user_gmail_tokens.encrypted_refresh_token IS 'The encrypted OAuth2 refresh token, used to obtain new access tokens.';
COMMENT ON COLUMN public.user_gmail_tokens.token_expiry_timestamp IS 'The timestamp indicating when the current access token expires.';
COMMENT ON COLUMN public.user_gmail_tokens.created_at IS 'Timestamp of when the record was first created.';
COMMENT ON COLUMN public.user_gmail_tokens.updated_at IS 'Timestamp of when the record was last updated.';
