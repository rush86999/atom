import sys
import os
import logging
from sqlalchemy.orm import Session

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.database import SessionLocal, engine
from core.models import User, UserRole, UserStatus
from core.auth import get_password_hash

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def ensure_admin():
    db = SessionLocal()
    try:
        email = "admin@example.com"
        password = "securePass123"
        hashed_password = get_password_hash(password)
        
        user = db.query(User).filter(User.email == email).first()
        
        if user:
            logger.info(f"Updating existing user: {email}")
            user.password_hash = hashed_password
            user.status = UserStatus.ACTIVE
            # Ensure admin role if not already
            if user.role not in [UserRole.SUPER_ADMIN, UserRole.WORKSPACE_ADMIN]:
                user.role = UserRole.WORKSPACE_ADMIN
            
            db.commit()
            logger.info(f"✓ Password updated for {email}")
        else:
            logger.info(f"Creating new admin user: {email}")
            new_user = User(
                email=email,
                password_hash=hashed_password,
                first_name="Admin",
                last_name="User",
                role=UserRole.WORKSPACE_ADMIN,
                status=UserStatus.ACTIVE,
                workspace_id="default"
            )
            db.add(new_user)
            db.commit()
            logger.info(f"✓ Created user {email}")
            
    except Exception as e:
        logger.error(f"Error ensuring admin user: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    ensure_admin()
