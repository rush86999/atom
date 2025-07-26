-- Comprehensive financial feature parity schema additions for maybe-finance integration

-- BUDGET MANAGEMENT
CREATE TABLE budgets (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(255) NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    period_type VARCHAR(50) NOT NULL DEFAULT 'monthly', -- monthly, weekly, yearly
    start_date DATE NOT NULL,
    end_date DATE,
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE budget_categories (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    color VARCHAR(7),
    parent_category_id INTEGER REFERENCES budget_categories(id),
    is_system_category BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE budget_transactions (
    id SERIAL PRIMARY KEY,
    budget_id INTEGER NOT NULL REFERENCES budgets(id),
    transaction_id INTEGER NOT NULL REFERENCES transactions(id),
    amount_fraction NUMERIC(5, 4), -- Fraction of transaction attributed to this budget
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- FINANCIAL GOALS
CREATE TABLE financial_goals (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    target_amount NUMERIC(15, 2) NOT NULL,
    current_amount NUMERIC(15, 2) DEFAULT 0,
    goal_type VARCHAR(50) NOT NULL, -- emergency_fund, retirement, savings, debt_payoff, investment, purchase
    target_date DATE,
    priority INTEGER DEFAULT 1,
    status VARCHAR(50) DEFAULT 'active', -- active, paused, completed, cancelled
    account_id INTEGER REFERENCES accounts(id), -- Link to specific account for goal tracking
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE goal_contributions (
    id SERIAL PRIMARY KEY,
    goal_id INTEGER NOT NULL REFERENCES financial_goals(id),
    amount NUMERIC(15, 2) NOT NULL,
    contribution_date DATE NOT NULL,
    source_account_id INTEGER REFERENCES accounts(id),
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- NET WORTH HISTORY
CREATE TABLE net_worth_snapshots (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    snapshot_date DATE NOT NULL,
    total_assets NUMERIC(15, 2) NOT NULL,
    total_liabilities NUMERIC(15, 2) NOT NULL,
    net_worth NUMERIC(15, 2) NOT NULL,
    accounts_snapshot JSONB, -- Stores snapshot of all accounts at this time
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (user_id, snapshot_date)
);

-- INVESTMENT PERFORMANCE ENHANCEMENT
CREATE TABLE securities (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    security_type VARCHAR(50), -- stock, bond, etf, mutual_fund, crypto
    exchange VARCHAR(50),
    sector VARCHAR(100),
    currency VARCHAR(3) DEFAULT 'USD',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE investment_prices (
    id SERIAL PRIMARY KEY,
    security_id INTEGER NOT NULL REFERENCES securities(id),
    price_date DATE NOT NULL,
    price NUMERIC(15, 4) NOT NULL,
    volume BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (security_id, price_date)
);

CREATE TABLE investment_transactions (
    id SERIAL PRIMARY KEY,
    investment_id INTEGER NOT NULL REFERENCES investments(id),
    transaction_type VARCHAR(50) NOT NULL, -- buy, sell, dividend, split, merger
    shares NUMERIC(15, 6),
    price NUMERIC(15, 4),
    amount NUMERIC(15, 2),
    transaction_date DATE NOT NULL,
    fees NUMERIC(15, 2) DEFAULT 0,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- TRANSACTION CATEGORIZATION & RULES
CREATE TABLE transaction_categories (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    category_name VARCHAR(255) NOT NULL,
    parent_category_id INTEGER REFERENCES transaction_categories(id),
    is_system_category BOOLEAN DEFAULT FALSE,
    rules JSONB, -- JSON rules for auto-categorization
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE transaction_rules (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    rule_name VARCHAR(255) NOT NULL,
    pattern TEXT NOT NULL,
    pattern_type VARCHAR(50) NOT NULL, -- regex, contains, exact
    action VARCHAR(50) NOT NULL, -- categorize, flag, assign
    target_value VARCHAR(255), -- category to assign, or other target
    is_active BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- RECURRING TRANSACTIONS & PREDICTIONS
CREATE TABLE recurring_transactions (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    category_id INTEGER REFERENCES transaction_categories(id),
    frequency VARCHAR(50) NOT NULL, -- monthly, weekly, biweekly, yearly
    next_due_date DATE NOT NULL,
    account_id INTEGER REFERENCES accounts(id),
    is_active BOOLEAN DEFAULT TRUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ACCOUNT PLAID MAPPING
CREATE TABLE plaid_account_mappings (
    id SERIAL PRIMARY KEY,
    plaid_account_id VARCHAR(255) NOT NULL UNIQUE,
    atom_account_id INTEGER NOT NULL REFERENCES accounts(id),
    access_token VARCHAR(255) NOT NULL,
    item_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ADD INDICES FOR PERFORMANCE
CREATE INDEX idx_budgets_user_id ON budgets(user_id);
CREATE INDEX idx_budgets_category ON budgets(category);
CREATE INDEX idx_financial_goals_user_id ON financial_goals(user_id);
CREATE INDEX idx_financial_goals_status ON financial_goals(status);
CREATE INDEX idx_net_worth_snapshots_user_date ON net_worth_snapshots(user_id, snapshot_date);
CREATE INDEX idx_investment_prices_security_date ON investment_prices(security_id, price_date);
CREATE INDEX idx_transactions_account_id_date ON transactions(account_id, date);
CREATE INDEX idx_transactions_category ON transactions(category);

-- ADD UPDATED_AT TRIGGERS
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_budgets_updated_at BEFORE UPDATE ON budgets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_financial_goals_updated_at BEFORE UPDATE ON financial_goals
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
