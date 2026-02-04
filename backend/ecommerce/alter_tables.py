from sqlalchemy import text

from core.database import engine


def alter_schema():
    with engine.connect() as conn:
        print("Altering ecommerce_customers...")
        conn.execute(text("ALTER TABLE ecommerce_customers ADD COLUMN IF NOT EXISTS risk_score FLOAT DEFAULT 0.0"))
        conn.execute(text("ALTER TABLE ecommerce_customers ADD COLUMN IF NOT EXISTS risk_level VARCHAR DEFAULT 'low'"))
        
        print("Altering ecommerce_orders...")
        conn.execute(text("ALTER TABLE ecommerce_orders ADD COLUMN IF NOT EXISTS subscription_id VARCHAR REFERENCES ecommerce_subscriptions(id)"))
        
        conn.commit()
        print("Schema altered successfully.")

if __name__ == "__main__":
    alter_schema()
