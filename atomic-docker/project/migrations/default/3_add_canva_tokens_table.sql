CREATE TABLE public.user_canva_tokens (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    user_id uuid NOT NULL,
    encrypted_access_token text NOT NULL,
    encrypted_refresh_token text,
    token_expiry_timestamp timestamptz,
    scopes jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (user_id) REFERENCES auth.users(id) ON UPDATE restrict ON DELETE cascade
);

ALTER TABLE public.user_canva_tokens ADD CONSTRAINT user_canva_tokens_user_id_key UNIQUE (user_id);

CREATE TRIGGER set_public_user_canva_tokens_updated_at BEFORE UPDATE ON public.user_canva_tokens FOR EACH ROW EXECUTE PROCEDURE public.set_current_timestamp_updated_at();
COMMENT ON TRIGGER set_public_user_canva_tokens_updated_at ON public.user_canva_tokens IS 'trigger to set value of column "updated_at" to current timestamp on row update';
