-- Create User Credentials Table Migration
-- This migration adds the User_Credentials table for storing user authentication credentials

CREATE TABLE IF NOT EXISTS public."User_Credentials" (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "userId" UUID NOT NULL REFERENCES public."User"(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    "createdAt" TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    "updatedAt" TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    deleted BOOLEAN DEFAULT FALSE NOT NULL
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_user_credentials_user_id ON public."User_Credentials"("userId");
CREATE INDEX IF NOT EXISTS idx_user_credentials_email ON public."User_Credentials"(email);
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_credentials_user_email_unique ON public."User_Credentials"("userId", email) WHERE deleted = false;

-- Add trigger for updatedAt
CREATE OR REPLACE FUNCTION update_user_credentials_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW."updatedAt" = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_user_credentials_updated_at
    BEFORE UPDATE ON public."User_Credentials"
    FOR EACH ROW
    EXECUTE FUNCTION update_user_credentials_updated_at();

-- Add comments
COMMENT ON TABLE public."User_Credentials" IS 'Stores user authentication credentials including password hashes';
COMMENT ON COLUMN public."User_Credentials".password_hash IS 'BCrypt hashed password';
COMMENT ON COLUMN public."User_Credentials".deleted IS 'Soft delete flag for user credentials';

-- Insert initial demo users (optional - for development)
-- Note: Passwords are hashed with bcrypt - demo123 and admin123
INSERT INTO public."User" (id, email, name, "createdDate", "updatedAt") VALUES
    ('11111111-1111-1111-1111-111111111111', 'demo@atom.com', 'Demo User', NOW(), NOW()),
    ('22222222-2222-2222-2222-222222222222', 'admin@atom.com', 'Admin User', NOW(), NOW())
ON CONFLICT (id) DO NOTHING;

INSERT INTO public."User_Credentials" ("userId", email, password_hash) VALUES
    ('11111111-1111-1111-1111-111111111111', 'demo@atom.com', '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj89tiM7FEyG'), -- demo123
    ('22222222-2222-2222-2222-222222222222', 'admin@atom.com', '$2b$12$8S5DlN8pZfV6W6eF5YqZXOe3nJ9mR7Lk2V1rB4wX3yH7vM8N9pQ1K') -- admin123
ON CONFLICT ("userId", email) DO NOTHING;
