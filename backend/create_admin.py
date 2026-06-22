"""
One-off script to create/reset the admin user.

SECURITY: Password is sourced from ADMIN_PASSWORD env var. If unset,
a random password is generated and printed to stdout (matches the
behavior of core/admin_bootstrap.py used at app startup).

Usage:
    ADMIN_PASSWORD=... python create_admin.py
"""
import os
import secrets
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.auth import get_password_hash
from core.database import Base
from core.models import User, UserStatus

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./atom.db")  # Default to sqlite if not set
if "postgres" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

email = "admin@example.com"
# SECURITY: never hardcode — pull from env or generate a random password
password = os.getenv("ADMIN_PASSWORD") or secrets.token_urlsafe(16)

with SessionLocal() as db:
    user = db.query(User).filter(User.email == email).first()

    if user:
        print(f"User {email} exists. resetting password...")
        user.password_hash = get_password_hash(password)
        user.status = UserStatus.ACTIVE
        db.commit()
        print(f"User {email} password reset.")
        if not os.getenv("ADMIN_PASSWORD"):
            print(f"Generated password: {password}")
            print("Set ADMIN_PASSWORD env var to pin it across runs.")
    else:
        print(f"User {email} not found. Creating...")
        new_user = User(
            email=email,
            hashed_password=get_password_hash(password),
            first_name="Admin",
            last_name="User",
            status=UserStatus.ACTIVE
        )
        db.add(new_user)
        db.commit()
        print(f"User {email} created.")
        if not os.getenv("ADMIN_PASSWORD"):
            print(f"Generated password: {password}")
            print("Set ADMIN_PASSWORD env var to pin it across runs.")
