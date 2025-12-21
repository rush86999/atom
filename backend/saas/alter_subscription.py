from sqlalchemy import text
import sys
import os

# Add project root
sys.path.append(os.getcwd())

from core.database import engine

def alter_subscription():
    print("Altering ecommerce_subscriptions table...")
    with engine.connect() as conn:
        with conn.begin(): # Transaction
            try:
                # tier_id
                conn.execute(text("ALTER TABLE ecommerce_subscriptions ADD COLUMN tier_id VARCHAR"))
                print("✅ Added tier_id column.")
            except Exception as e:
                print(f"ℹ️ tier_id column might already exist or error: {e}")
            
            try:
                 # current_period_usage
                 conn.execute(text("ALTER TABLE ecommerce_subscriptions ADD COLUMN current_period_usage JSON"))
                 print("✅ Added current_period_usage column.")
            except Exception as e:
                print(f"ℹ️ current_period_usage column might already exist or error: {e}")

if __name__ == "__main__":
    alter_subscription()
