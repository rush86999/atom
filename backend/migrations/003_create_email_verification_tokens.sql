-- Email Verification Tokens Table
-- Stores tokens for email verification after user registration

CREATE TABLE IF NOT EXISTS email_verification_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for faster lookups
CREATE INDEX IF NOT EXISTS idx_email_verification_token ON email_verification_tokens(token);
CREATE INDEX IF NOT EXISTS idx_email_verification_user_expires ON email_verification_tokens(user_id, expires_at);

-- Clean up expired tokens (optional, can be run as a cron job)
-- DELETE FROM email_verification_tokens WHERE expires_at < NOW();
