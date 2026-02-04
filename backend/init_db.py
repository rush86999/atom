
import logging
import os
import sys

# Add parent directory to path to import core modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.database import Base, engine
from core.models import User, UserStatus

# Import other models if needed to ensure they are registered with Base
# from core.workflow_models import ... 

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    logger.info("Creating database tables...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✓ Tables created successfully.")
    except Exception as e:
        logger.error(f"✗ Failed to create tables: {e}")
        raise e

if __name__ == "__main__":
    init_db()
