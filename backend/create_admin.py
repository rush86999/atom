import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.auth import get_password_hash
from core.database import Base
from core.models import User, UserStatus

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./atom.db") # Default to sqlite if not set
if "postgres" in DATABASE_URL:
    # Ensure correct driver
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

email = "admin@example.com"
password = "securePass123"

with SessionLocal() as db:
    # Check if user exists
    user = db.query(User).filter(User.email == email).first()

    if user:
        print(f"User {email} exists. resetting password...")
        user.password_hash = get_password_hash(password)
        user.status = UserStatus.ACTIVE
        db.commit()
        print(f"User {email} password reset to '{password}'")
    else:
        print(f"User {email} not found. Creating...")
        new_user = User(
            email=email,
            password_hash=get_password_hash(password),
            first_name="Admin",
            last_name="User",
            status=UserStatus.ACTIVE
        )
        db.add(new_user)
        db.commit()
        print(f"User {email} created with password '{password}'")
