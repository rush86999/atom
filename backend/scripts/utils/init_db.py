import os
import sys
from sqlalchemy import create_engine

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

# Import model modules to ensure all models are registered with Base.metadata
# Using module imports instead of wildcard to avoid NameError issues
from accounting import models as accounting_models
from ecommerce import models as ecommerce_models
from marketing import models as marketing_models
from saas import models as saas_models
from sales import models as sales_models
from service_delivery import models as service_delivery_models
from core import database
from core import models as core_models

# Use Base from core.models for consistency
Base = core_models.Base


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
