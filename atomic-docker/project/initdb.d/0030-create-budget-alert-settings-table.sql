CREATE TABLE budget_alert_settings (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    threshold INTEGER NOT NULL DEFAULT 90,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TRIGGER update_budget_alert_settings_updated_at BEFORE UPDATE ON budget_alert_settings
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
