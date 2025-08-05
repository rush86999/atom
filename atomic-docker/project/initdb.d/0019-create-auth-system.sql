-- Create auth system for user management
BEGIN;

-- Create auth users table with proper foreign key to users
CREATE TABLE IF NOT EXISTS auth.users (
    id uuid PRIMARY KEY,
    email citext NOT NULL UNIQUE,
    email_verified boolean DEFAULT false,
    encrypted_password varchar(255) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    last_sign_in_at timestamptz,
    disabled boolean DEFAULT false,
    email_verified_at timestamptz,
    phone_number varchar(255),
    phone_verified boolean DEFAULT false,
    metadata jsonb DEFAULT '{}',
    CONSTRAINT fk_user_account FOREIGN KEY(id) REFERENCES public."User"(id) ON DELETE CASCADE
);

-- Create user sessions table
CREATE TABLE IF NOT EXISTS auth.sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    refresh_token varchar(255) NOT NULL UNIQUE,
    ip_address inet,
    user_agent text,
    metadata jsonb DEFAULT '{}'
);

-- Create refresh tokens table
CREATE TABLE IF NOT EXISTS auth.refresh_tokens (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id uuid NOT NULL REFERENCES auth.sessions(id) ON DELETE CASCADE,
    user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    token varchar(255) NOT NULL UNIQUE,
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    revoked boolean DEFAULT false
);

-- Create user roles table
CREATE TABLE IF NOT EXISTS auth.roles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role_name varchar(50) NOT NULL CHECK (role_name IN ('user', 'admin', 'super_admin')),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(user_id, role_name)
);

-- Create JWT secrets table
CREATE TABLE IF NOT EXISTS auth.jwt_secrets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    secret text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz,
    is_active boolean DEFAULT true
);

-- Create OAuth providers table
CREATE TABLE IF NOT EXISTS auth.providers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_name varchar(50) NOT NULL NOT NULL,
    user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    provider_user_id varchar(255) NOT NULL,
    provider_email varchar(255),
    access_token text,
    refresh_token text,
    expires_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(provider_name, provider_user_id)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_auth_users_email ON auth.users(email);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id ON auth.sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires_at ON auth.sessions(expires_at);
CREATE INDEX IF NOT EXISTS idx_auth_refresh_tokens_token ON auth.refresh_tokens(token);
CREATE INDEX IF NOT EXISTS idx_auth_refresh_tokens_user_id ON auth.refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_roles_user_id ON auth.roles(user_id);
CREATE INDEX IF NOT EXISTS idx_auth_providers_user_id ON auth.providers(user_id);

-- Updated trigger function to keep timestamps updated
CREATE OR REPLACE FUNCTION auth.set_current_timestamp_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers
CREATE TRIGGER set_updated_at_auth_users BEFORE UPDATE ON auth.users FOR EACH ROW EXECUTE FUNCTION auth.set_current_timestamp_updated_at();
CREATE TRIGGER set_updated_at_auth_sessions BEFORE UPDATE ON auth.sessions FOR EACH ROW EXECUTE FUNCTION auth.set_current_timestamp_updated_at();
CREATE TRIGGER set_updated_at_auth_refresh_tokens BEFORE UPDATE ON auth.refresh_tokens FOR EACH ROW EXECUTE FUNCTION auth.set_current_timestamp_updated_at();
CREATE TRIGGER set_updated_at_auth_providers BEFORE UPDATE ON auth.providers FOR EACH ROW EXECUTE FUNCTION auth.set_current_timestamp_updated_at();

-- Insert default admin role for existing users
INSERT INTO auth.roles (user_id, role_name)
SELECT id, 'user'
FROM public."User"
WHERE id NOT IN (SELECT user_id FROM auth.roles);

-- Create view for connected user accounts
CREATE OR REPLACE VIEW auth.user_accounts AS
SELECT
    u.id,
    u.email,
    u.name,
    a.encrypted_password IS NOT NULL as password_enabled,
    COALESCE(json_agg(DISTINCT jsonb_build_object(
        'provider', p.provider_name,
        'email', p.provider_email
    )) FILTER (WHERE p.provider_name IS NOT NULL), '[]') as connected_providers,
    r.role_name as current_role
FROM public."User" u
LEFT JOIN auth.users a ON u.id = a.id
LEFT JOIN auth.roles r ON u.id = r.user_id AND r.role_name = 'user'
LEFT JOIN auth.providers p ON u.id = p.user_id
GROUP BY u.id, u.email, u.name, a.encrypted_password, r.role_name;

COMMIT;
