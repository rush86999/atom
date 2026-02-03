
import os
import sys
from sqlalchemy import text

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from core.database import engine


def migrate():
    print("Migrating User model for Onboarding...")
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN onboarding_completed BOOLEAN DEFAULT FALSE"))
            print("Added onboarding_completed column.")
        except Exception as e:
            print(f"Skipping onboarding_completed: {e}")
            
        try:
            conn.execute(text("ALTER TABLE users ADD COLUMN onboarding_step VARCHAR DEFAULT 'welcome'"))
            print("Added onboarding_step column.")
        except Exception as e:
            print(f"Skipping onboarding_step: {e}")
            
        conn.commit()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
