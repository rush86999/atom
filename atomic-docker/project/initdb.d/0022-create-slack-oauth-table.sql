-- Create the user_slack_oauth_tokens table to store encrypted OAuth tokens for Slack integration.
CREATE TABLE IF NOT EXISTS public.user_slack_oauth_tokens (
    user_id VARCHAR(255) PRIMARY KEY,
    encrypted_access_token BYTEA NOT NULL,
    scope TEXT,
    team_id VARCHAR(255),
    team_name VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Use the existing trigger function if it's generic, or create one if it doesn't exist.
-- This assumes `update_updated_at_column` function is available from a previous migration.
-- If not, the function definition should be included here.

-- Drop the trigger if it already exists on the table to avoid errors on re-run
DROP TRIGGER IF EXISTS set_timestamp ON public.user_slack_oauth_tokens;

-- Create the trigger
CREATE TRIGGER set_timestamp
BEFORE UPDATE ON public.user_slack_oauth_tokens
FOR EACH ROW
EXECUTE PROCEDURE update_updated_at_column();

-- Add comments to the columns for clarity
COMMENT ON TABLE public.user_slack_oauth_tokens IS 'Stores encrypted OAuth2 tokens for user connections to Slack.';
COMMENT ON COLUMN public.user_slack_oauth_tokens.user_id IS 'The unique identifier for the user in our system.';
COMMENT ON COLUMN public.user_slack_oauth_tokens.encrypted_access_token IS 'The encrypted OAuth2 access token for the Slack user.';
COMMENT ON COLUMN public.user_slack_oauth_tokens.scope IS 'A space-separated string of scopes the user has granted.';
COMMENT ON COLUMN public.user_slack_oauth_tokens.team_id IS 'The ID of the Slack workspace/team.';
COMMENT ON COLUMN public.user_slack_oauth_tokens.team_name IS 'The name of the Slack workspace/team.';
COMMENT ON COLUMN public.user_slack_oauth_tokens.created_at IS 'Timestamp of when the record was first created.';
COMMENT ON COLUMN public.user_slack_oauth_tokens.updated_at IS 'Timestamp of when the record was last updated.';
