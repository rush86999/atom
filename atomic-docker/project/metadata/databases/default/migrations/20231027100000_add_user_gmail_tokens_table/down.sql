ALTER TABLE public.user_gmail_tokens DROP CONSTRAINT IF EXISTS user_gmail_tokens_user_id_key;
DROP TRIGGER IF EXISTS set_public_user_gmail_tokens_updated_at ON public.user_gmail_tokens;
DROP TABLE IF EXISTS public.user_gmail_tokens;
