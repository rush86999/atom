CREATE TABLE referrals (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    referral_code VARCHAR(255) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
