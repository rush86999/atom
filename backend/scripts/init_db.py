import os
import sys
from sqlalchemy import create_engine

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from accounting.models import *
from ecommerce.models import *
from marketing.models import *
from saas.models import *
from sales.models import *
from service_delivery.models import *

from core.database import DATABASE_URL, Base

# Import all models to ensure they are registered with Base.metadata
from core.models import *


def init_db():
    # Use SQLite for easy local verification
    sqlite_url = "sqlite:///backend/atom_dev.db"
    print(f"Initializing database at {sqlite_url}...")
    engine = create_engine(sqlite_url)
    
    # Manually add missing columns if they don't exist
    from sqlalchemy import text
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE workspaces ADD COLUMN is_startup BOOLEAN DEFAULT 0"))
            conn.execute(text("ALTER TABLE workspaces ADD COLUMN learning_phase_completed BOOLEAN DEFAULT 0"))
            conn.commit()
        except Exception as e:
            print(f"Note: Could not add columns (they might already exist): {e}")

    Base.metadata.create_all(engine)
    print("✅ All tables created successfully.")

if __name__ == "__main__":
    init_db()
