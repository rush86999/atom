CREATE TABLE IF NOT EXISTS user_preferences (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id VARCHAR(255) NOT NULL,
    workspace_id VARCHAR(255) NOT NULL,
    key VARCHAR(255) NOT NULL,
    value TEXT, -- JSON value stringified or simple text
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, workspace_id, key)
);

CREATE INDEX IF NOT EXISTS idx_user_preferences_lookup ON user_preferences(user_id, workspace_id);
