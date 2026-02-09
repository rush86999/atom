import sys
import os
import sqlite3
import logging
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from core.models import User, UserRole, UserStatus
from core.auth import get_password_hash

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Start by checking which one is actually used
DATABASE_URL = "sqlite:///dev.db"  # Use LOCAL dev.db relative to backend execution
DB_PATH = "dev.db"

def fix_parent_db():
    logger.info(f"Targeting Database: {os.path.abspath(DB_PATH)}")
    
    # 1. Fix Schema (Add Column)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("PRAGMA table_info(users)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "email_verified" not in columns:
            logger.info("Adding missing column 'email_verified'...")
            cursor.execute("ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 0")

        if "tenant_id" not in columns:
            logger.info("Adding missing column 'tenant_id'...")
            cursor.execute("ALTER TABLE users ADD COLUMN tenant_id VARCHAR")

        if "skills" not in columns:
            logger.info("Adding missing column 'skills'...")
            cursor.execute("ALTER TABLE users ADD COLUMN skills TEXT")
            
        if "onboarding_completed" not in columns:
            logger.info("Adding missing column 'onboarding_completed'...")
            cursor.execute("ALTER TABLE users ADD COLUMN onboarding_completed BOOLEAN DEFAULT 0")
            
        if "onboarding_step" not in columns:
            logger.info("Adding missing column 'onboarding_step'...")
            cursor.execute("ALTER TABLE users ADD COLUMN onboarding_step VARCHAR DEFAULT 'welcome'")

        if "capacity_hours" not in columns:
            logger.info("Adding missing column 'capacity_hours'...")
            cursor.execute("ALTER TABLE users ADD COLUMN capacity_hours FLOAT DEFAULT 40.0")

        if "hourly_cost_rate" not in columns:
             logger.info("Adding missing column 'hourly_cost_rate'...")
             cursor.execute("ALTER TABLE users ADD COLUMN hourly_cost_rate FLOAT DEFAULT 0.0")
             
        if "metadata_json" not in columns:
             logger.info("Adding missing column 'metadata_json'...")
             cursor.execute("ALTER TABLE users ADD COLUMN metadata_json JSON")

        if "preferences" not in columns:
             logger.info("Adding missing column 'preferences'...")
             cursor.execute("ALTER TABLE users ADD COLUMN preferences JSON")

        if "two_factor_enabled" not in columns:
             logger.info("Adding missing column 'two_factor_enabled'...")
             cursor.execute("ALTER TABLE users ADD COLUMN two_factor_enabled BOOLEAN DEFAULT 0")

        if "two_factor_secret" not in columns:
             logger.info("Adding missing column 'two_factor_secret'...")
             cursor.execute("ALTER TABLE users ADD COLUMN two_factor_secret VARCHAR")

        if "two_factor_backup_codes" not in columns:
             logger.info("Adding missing column 'two_factor_backup_codes'...")
             cursor.execute("ALTER TABLE users ADD COLUMN two_factor_backup_codes JSON")
             
        conn.commit()
        logger.info("✓ Schema sync completed.")
    except Exception as e:
        logger.error(f"Schema Error: {e}")
    finally:
        conn.close()

    # 2. Update Admin User
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    
    try:
        email = "admin@example.com"
        password = "securePass123"
        hashed_password = get_password_hash(password)
        
        user = db.query(User).filter(User.email == email).first()
        
        if user:
            logger.info(f"Updating existing user: {email}")
            user.password_hash = hashed_password
            user.email_verified = True
            user.status = UserStatus.ACTIVE
            if user.role not in [UserRole.SUPER_ADMIN, UserRole.WORKSPACE_ADMIN]:
                user.role = UserRole.WORKSPACE_ADMIN
            
            db.commit()
            logger.info(f"✓ User {email} updated (password reset & verified)")
        else:
            logger.info(f"Creating new admin user: {email}")
            new_user = User(
                email=email,
                password_hash=hashed_password,
                first_name="Admin",
                last_name="User",
                role=UserRole.WORKSPACE_ADMIN,
                status=UserStatus.ACTIVE,
                workspace_id="default",
                email_verified=True
            )
            db.add(new_user)
            db.commit()
            logger.info(f"✓ Created user {email}")
            
    except Exception as e:
        logger.error(f"User Update Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    # Add parent path for imports if needed
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    fix_parent_db()
