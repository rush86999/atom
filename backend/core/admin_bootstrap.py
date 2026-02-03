import logging
from sqlalchemy.orm import Session

from core.auth import get_password_hash
from core.database import get_db_session
from core.models import User, UserStatus

logger = logging.getLogger("ATOM_BOOTSTRAP")

def ensure_admin_user():
    """
    Ensures the admin@example.com user exists with the correct password.
    This runs INSIDE the main application process to avoid DB locks.
    """
    with get_db_session() as db:
    try:
        email = "admin@example.com"
        password = "securePass123"
        
        user = db.query(User).filter(User.email == email).first()
        
        if user:
            logger.info(f"BOOTSTRAP: User {email} found. resetting password...")
            user.password_hash = get_password_hash(password)
            user.status = UserStatus.ACTIVE
            db.commit()
            logger.info(f"BOOTSTRAP: Password for {email} reset to '{password}'")
        else:
            logger.info(f"BOOTSTRAP: User {email} not found. Creating...")
            new_user = User(
                id="00000000-0000-0000-0000-000000000000", # Fixed ID for development stability
                email=email,
                password_hash=get_password_hash(password),
                first_name="Admin",
                last_name="User",
                status=UserStatus.ACTIVE
            )
            db.add(new_user)
            db.commit()
            logger.info(f"BOOTSTRAP: Created {email} with password '{password}'")
            
    except Exception as e:
        logger.error(f"BOOTSTRAP FAILED: {e}")
        db.rollback()
    finally:
        db.close()
