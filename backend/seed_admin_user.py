"""
One-off admin user seeding script.

SECURITY: password is sourced from ADMIN_PASSWORD env var. If unset,
a random per-run password is generated and printed (matching the
behavior of core/admin_bootstrap.py used at app startup).

Usage:
    ADMIN_PASSWORD=... python seed_admin_user.py
"""
import logging
import os
import secrets
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

    # SECURITY: never hardcode the password — env var or random per run
    password = os.getenv("ADMIN_PASSWORD") or secrets.token_urlsafe(16)

    try:
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

        with SessionLocal() as db:
            user = db.query(User).filter(User.email == "admin@example.com").first()
            if user:
                logger.info("User 'admin@example.com' already exists; resetting password.")
                user.hashed_password = get_password_hash(password)
                user.status = UserStatus.ACTIVE
                db.commit()
                logger.info("Password updated.")
            else:
                logger.info("Creating 'admin@example.com'...")
                new_user = User(
                    email="admin@example.com",
                    hashed_password=get_password_hash(password),
                    first_name="Admin",
                    last_name="User",
                    status=UserStatus.ACTIVE,
                    role="admin",
                )
                db.add(new_user)
                db.commit()
                logger.info("User 'admin@example.com' created.")

            if not os.getenv("ADMIN_PASSWORD"):
                logger.warning("Generated admin password: %s", password)
                logger.warning("Set ADMIN_PASSWORD env var to pin it across runs.")

    except Exception as e:
        logger.error(f"Seed failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    seed_admin()
