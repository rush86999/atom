CREATE TABLE user_credentials (
    user_id TEXT NOT NULL,
    service_name TEXT NOT NULL,
    encrypted_secret TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (user_id, service_name)
);
