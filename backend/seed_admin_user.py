
import logging
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add parent directory to path to import core modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.auth import get_password_hash
from core.database import DATABASE_URL
from core.models import User, UserStatus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def seed_admin():
    logger.info("Starting admin seed...")
    logger.info(f"Database URL: {DATABASE_URL}")

    try:
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        with SessionLocal() as db:
            # Check if user exists
            user = db.query(User).filter(User.email == "admin@example.com").first()
            if user:
                logger.info("✓ User 'admin@example.com' already exists.")
                # Optional: Reset password if needed? The user said "securePass123"
                # Let's update it just in case
                user.password_hash = get_password_hash("securePass123")
                user.status = UserStatus.ACTIVE
                db.commit()
                logger.info("✓ Password updated to 'securePass123' and status set to ACTIVE")
            else:
                logger.info("Creating 'admin@example.com'...")
                new_user = User(
                    email="admin@example.com",
                    password_hash=get_password_hash("securePass123"),
                    first_name="Admin",
                    last_name="User",
                    status=UserStatus.ACTIVE,
                    role="admin"
                )
                db.add(new_user)
                db.commit()
                logger.info("✓ User 'admin@example.com' created successfully with password 'securePass123'")

    except Exception as e:
        logger.error(f"✗ Seed failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    seed_admin()
