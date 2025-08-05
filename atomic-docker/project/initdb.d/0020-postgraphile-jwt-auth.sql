-- PostGraphile JWT Authentication Extension
-- Provides JWT-based authentication integrated with the existing User table

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create authentication schema to hold auth-specific functions
CREATE SCHEMA IF NOT EXISTS app_private;
CREATE SCHEMA IF NOT EXISTS app_public;

-- Create sessions table for JWT token management
CREATE TABLE app_private.sessions (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES public."User"(id) ON DELETE CASCADE,
    created_at timestamptz NOT NULL DEFAULT now(),
    last_seen timestamptz NOT NULL DEFAULT now(),
    token uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    expires_at timestamptz NOT NULL DEFAULT (now() + interval '1 day'),
    ip_address inet,
    user_agent text,
    revoked_at timestamptz,
    metadata jsonb DEFAULT '{}'
);

-- Create user roles for role-based access control
CREATE TABLE app_private.user_roles (
    id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES public."User"(id) ON DELETE CASCADE,
    role app_role DEFAULT 'app_user',
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, role)
);

-- Create role enum type
DO $$ BEGIN
    CREATE TYPE app_role as enum('app_user', 'app_admin');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Create JWT user function to be used by PostGraphile
CREATE OR REPLACE FUNCTION app_public.current_user_id() RETURNS uuid AS $$
DECLARE
    v_user_id uuid;
BEGIN
    -- Extract from JWT claim 'sub' (subject)
    v_user_id := current_setting('jwt.claims.sub', true)::uuid;
    IF v_user_id IS NULL THEN
        -- For backwards compatibility in development
        IF current_setting('jwt.claims.user_id', true) IS NOT NULL THEN
            RETURN current_setting('jwt.claims.user_id', true)::uuid;
        END IF;
        -- Fallback for testing
        IF current_setting('app.current_user_id', true) IS NOT NULL THEN
            RETURN current_setting('app.current_user_id', true)::uuid;
        END IF;
        -- Return NULL for unauthenticated or throw error
        RETURN NULL;
    END IF;
    RETURN v_user_id;
END
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

-- Create user authentication function
CREATE OR REPLACE FUNCTION app_private.authenticate(
    email text,
    password text DEFAULT NULL
) RETURNS app_public.jwt_token AS $$
DECLARE
    v_user public."User";
    v_session app_private.sessions;
    v_token text;
BEGIN
    -- Look up the user
    SELECT * INTO v_user
    FROM public."User"
    WHERE email = authenticate.email
    AND deleted = false
    LIMIT 1;

    IF v_user IS NULL THEN
        RAISE EXCEPTION 'Invalid email or password';
    END IF;

    -- Create a new session
    INSERT INTO app_private.sessions (user_id, expires_at)
    VALUES (v_user.id, now() + interval '7 days')
    RETURNING * INTO v_session;

    -- Generate JWT token
    v_token := app_private.create_jwt_token(
        v_user.id,
        v_user.email,
        ARRAY['app_user']::app_role[]
    );

    -- Return structured JWT token
    RETURN (v_token, v_user.id, v_user.email)::app_public.jwt_token;
END
$$ LANGUAGE plpgsql STRICT SECURITY DEFINER;

-- JWT token type
CREATE TYPE app_public.jwt_token AS (
    token text,
    user_id uuid,
    email text
);

-- JWT creation function
CREATE OR REPLACE FUNCTION app_private.create_jwt_token(
    user_uuid uuid,
    user_email text,
    roles app_role[] DEFAULT ARRAY['app_user']::app_role[]
) RETURNS text AS $$
DECLARE
    v_secret text;
    v_payload jsonb;
    v_token text;
BEGIN
    -- Get JWT secret from environment
    v_secret := current_setting('jwt.secret', true);
    IF v_secret IS NULL THEN
        -- Fallback secret for development
        v_secret := 'atom_secret_key_dev_only_change_in_production';
    END IF;

    -- Build payload
    v_payload := jsonb_build_object(
        'sub', user_uuid,           -- Subject (user ID)
        'email', user_email,        -- User email
        'roles', roles,            -- User roles
        'iat', extract(epoch from now()),  -- Issued at
        'exp', extract(epoch from now()) + 60*60*24*7  -- 7 days expiry
    );

    -- Generate token (simplified for PostGraphile integration)
    -- PostGraphile JWT plugin will handle actual signing
    RETURN encode(convert_to(v_payload::text, 'utf8'), 'base64');
END
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

-- Enable Row Level Security on sessions
ALTER TABLE app_private.sessions ENABLE ROW LEVEL SECURITY;

-- Create policy: users can only see their own sessions
CREATE POLICY session_owner_policy ON app_private.sessions
    FOR ALL
    USING (user_id = app_public.current_user_id());

-- Create user registration function
CREATE OR REPLACE FUNCTION app_public.register_user(
    email text,
    name text,
    user_metadata jsonb DEFAULT '{}'::jsonb
) RETURNS public."User" AS $$
DECLARE
    v_user public."User";
BEGIN
    -- Check if email already exists
    IF EXISTS (SELECT 1 FROM public."User" WHERE email = register_user.email) THEN
        RAISE EXCEPTION 'Email already exists';
    END IF;

    -- Create new user
    INSERT INTO public."User" (email, name, createdDate, updatedAt)
    VALUES (register_user.email, register_user.name, now(), now())
    RETURNING * INTO v_user;

    -- Assign default role
    INSERT INTO app_private.user_roles (user_id, role)
    VALUES (v_user.id, 'app_user');

    RETURN v_user;
END
$$ LANGUAGE plpgsql STRICT SECURITY DEFINER;

-- Create role checking function
CREATE OR REPLACE FUNCTION app_public.current_user_roles() RETURNS app_role[] AS $$
BEGIN
    RETURN ARRAY(
        SELECT role
        FROM app_private.user_roles
        WHERE user_id = app_public.current_user_id()
    );
END
$$ LANGUAGE plpgsql STABLE SECURITY DEFINER;

-- Create role-based policies
CREATE POLICY user_data_policy ON public."User"
    FOR ALL
    USING (
        id = app_public.current_user_id()
        OR 'app_admin' = ANY(app_public.current_user_roles())
    );

-- Ensure User table has proper indexes
CREATE INDEX IF NOT EXISTS user_email_idx ON public."User"(email);
CREATE INDEX IF NOT EXISTS user_created_date_idx ON public."User"(createdDate);

-- Create index for session lookups
CREATE INDEX IF NOT EXISTS session_user_id_idx ON app_private.sessions(user_id);
CREATE INDEX IF NOT EXISTS session_token_idx ON app_private.sessions(token);
CREATE INDEX IF NOT EXISTS session_expires_at_idx ON app_private.sessions(expires_at);

-- Create custom table expression for user auth info
CREATE OR REPLACE VIEW app_public.current_user_with_auth AS
SELECT
    u.id,
    u.email,
    u.name,
    u.createdDate,
    u.updatedAt,
    app_public.current_user_roles() as roles,
    (SELECT COUNT(*) FROM app_private.sessions WHERE user_id = u.id AND revoked_at IS NULL) as active_sessions,
    (SELECT token FROM app_private.sessions WHERE user_id = u.id AND expires_at > now() ORDER BY created_at DESC LIMIT 1) as current_token
FROM public."User" u
WHERE id = app_public.current_user_id();

-- Grant appropriate permissions
GRANT ALL ON public."User" TO postgraphile;
GRANT SELECT ON app_public.current_user_with_auth TO postgraphile;
GRANT SELECT ON app_public.current_user_id() TO postgraphile;
GRANT SELECT ON app_public.current_user_roles() TO postgraphile;
GRANT EXECUTE ON FUNCTION app_public.register_user(text, text, jsonb) TO postgraphile;
GRANT EXECUTE ON FUNCTION app_private.authenticate(text, text) TO postgraphile;

-- Update existing tables to use authenticated user
ALTER TABLE public."User"
ADD COLUMN IF NOT EXISTS password_hash text,
ADD COLUMN IF NOT EXISTS email_verified boolean DEFAULT false,
ADD COLUMN IF NOT EXISTS auth_metadata jsonb DEFAULT '{}'::jsonb;

-- Migrate existing user data to use current_user_id context
UPDATE public."User"
SET email_verified = true, auth_metadata = '{"migrated_from_env": true}'::jsonb
WHERE id IN (SELECT id FROM public."User" WHERE email IS NOT NULL);

-- Ensure all auth tables have proper connection
-- This sets up PostGraphile integration for JWT with existing user system
