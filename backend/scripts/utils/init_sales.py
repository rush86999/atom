import logging
import os
import sys
from sqlalchemy import text

# Add the current directory to sys.path
sys.path.append(os.getcwd())

import sales.models

from core.database import Base, engine
import core.models

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_sales_tables():
    logger.info("Initializing sales tables...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Sales tables created successfully.")
    except Exception as e:
        logger.error(f"❌ Failed to create sales tables: {e}")
        sys.exit(1)

if __name__ == "__main__":
    init_sales_tables()
