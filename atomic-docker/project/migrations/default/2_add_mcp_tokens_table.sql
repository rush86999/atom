CREATE TABLE public.user_mcp_tokens (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    encrypted_access_token text NOT NULL,
    encrypted_refresh_token text,
    token_expiry_timestamp timestamptz,
    scopes jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (user_id) REFERENCES auth.users(id) ON UPDATE cascade ON DELETE cascade,
    UNIQUE (user_id)
);
