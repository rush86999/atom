
import logging
import sys
import os

# Ensure backend directory is in python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Force usage of the correct DB file (atom.db) as used by the running server
os.environ["DATABASE_URL"] = "sqlite:///c:/Users/Mannan Bajaj/atom/backend/data/atom.db"

from core.database import engine, SessionLocal, Base
from core.models import User
from core.auth import get_password_hash
import uuid

# Import all models to ensure they are registered with Base
import core.models_registration 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    logger.info("creating all tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("tables created.")

    db = SessionLocal()
    try:
        # Check if admin exists
        admin_email = "admin@example.com"
        existing_user = db.query(User).filter(User.email == admin_email).first()
        
        if not existing_user:
            logger.info("Creating default admin user...")
            admin_user = User(
                id=str(uuid.uuid4()),
                email=admin_email,
                password_hash=get_password_hash("admin123"),
                is_active=True,
                role="admin",
                first_name="Admin",
                last_name="User"
            )
            db.add(admin_user)
            db.commit()
            logger.info(f"Admin user created with ID: {admin_user.id}")
            print(f"ADMIN_ID={admin_user.id}")
        else:
            logger.info(f"Admin user already exists with ID: {existing_user.id}")
            print(f"ADMIN_ID={existing_user.id}")

    except Exception as e:
        logger.error(f"Error initializing DB: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
