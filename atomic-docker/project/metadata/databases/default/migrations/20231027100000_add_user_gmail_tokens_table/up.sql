CREATE TABLE public.user_gmail_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    encrypted_access_token TEXT NOT NULL,
    encrypted_refresh_token TEXT,
    token_expiry_timestamp TIMESTAMPTZ,
    scopes JSONB, -- Storing as JSONB is flexible for multiple scopes
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    CONSTRAINT fk_user_gmail_tokens_user_id
        FOREIGN KEY(user_id)
        REFERENCES public."User"(id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

CREATE TRIGGER set_public_user_gmail_tokens_updated_at
BEFORE UPDATE ON public.user_gmail_tokens
FOR EACH ROW
EXECUTE PROCEDURE public."set_current_timestamp_updatedAt"();

COMMENT ON TABLE public.user_gmail_tokens IS 'Stores encrypted Gmail API tokens for users, enabling Gmail integration features.';
COMMENT ON COLUMN public.user_gmail_tokens.user_id IS 'References the ID of the user in the public."User" table.';
COMMENT ON COLUMN public.user_gmail_tokens.encrypted_access_token IS 'Gmail access token, encrypted at rest using AES-256-GCM with GMAIL_TOKEN_ENCRYPTION_KEY.';
COMMENT ON COLUMN public.user_gmail_tokens.encrypted_refresh_token IS 'Gmail refresh token, encrypted at rest using AES-256-GCM with GMAIL_TOKEN_ENCRYPTION_KEY. Used to obtain new access tokens.';
COMMENT ON COLUMN public.user_gmail_tokens.token_expiry_timestamp IS 'Timestamp indicating when the current access token expires.';
COMMENT ON COLUMN public.user_gmail_tokens.scopes IS 'JSON array of scopes granted by the user for this token (e.g., ["https://www.googleapis.com/auth/gmail.readonly"]).';

CREATE INDEX IF NOT EXISTS idx_user_gmail_tokens_user_id ON public.user_gmail_tokens(user_id);

ALTER TABLE public.user_gmail_tokens ADD CONSTRAINT user_gmail_tokens_user_id_key UNIQUE (user_id);
COMMENT ON CONSTRAINT user_gmail_tokens_user_id_key ON public.user_gmail_tokens IS 'Ensures each user can only have one set of Gmail tokens.';
