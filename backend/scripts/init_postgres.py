import logging
import sys
import os

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from core.database import engine, Base
# Import all models to ensure they are registered with Base.metadata
import core.models
import accounting.models
# Add other model imports as needed

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    logger.info(f"Initializing database at {engine.url}")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ All tables created successfully.")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_db()
