CREATE TABLE IF NOT EXISTS shopify_oauth_tokens (
    user_id VARCHAR(255) PRIMARY KEY,
    access_token TEXT NOT NULL,
    scope VARCHAR(255) NOT NULL,
    shop_url VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
   NEW.updated_at = NOW();
   RETURN NEW;
END;
$$ language 'plpgsql';

DO $$
BEGIN
   IF NOT EXISTS (
       SELECT 1
       FROM pg_trigger
       WHERE tgname = 'update_shopify_oauth_tokens_updated_at'
   ) THEN
       CREATE TRIGGER update_shopify_oauth_tokens_updated_at
       BEFORE UPDATE ON shopify_oauth_tokens
       FOR EACH ROW
       EXECUTE FUNCTION update_updated_at_column();
   END IF;
END;
$$;
