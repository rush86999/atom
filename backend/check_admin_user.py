
import logging
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent directory to path to import core modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.database import DATABASE_URL
from core.models import User

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def debug_login():
    logger.info("Starting login debug...")
    logger.info(f"Database URL: {DATABASE_URL}")

    try:
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        with SessionLocal() as db:
            logger.info("✓ Database connection successful")

            # Check explicit admin user
            user = db.query(User).filter(User.email == "admin@example.com").first()
            if user:
                logger.info(f"✓ User 'admin@example.com' found. ID: {user.id}, Status: {user.status}")
                logger.info(f"  Password Hash start: {user.password_hash[:10] if user.password_hash else 'None'}...")
            else:
                logger.error("✗ User 'admin@example.com' NOT FOUND")

                # Check for any user
                logger.info("Listing first 5 users:")
                users = db.query(User).limit(5).all()
                if not users:
                    logger.warning("  No users found in database!")
                for u in users:
                    logger.info(f"  - {u.email} ({u.status})")

            # Check migration table if exists
            try:
                result = db.execute(text("SELECT * FROM alembic_version"))
                version = result.fetchone()
                logger.info(f"Alembic Version: {version}")
            except Exception:
                logger.info("Could not fetch alembic version (table might not exist)")

    except Exception as e:
        logger.error(f"✗ Database check failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_login()
