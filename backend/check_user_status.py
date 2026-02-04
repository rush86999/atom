import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./atom.db")
if "postgres" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://")

try:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as connection:
        result = connection.execute(text("SELECT id, email, password_hash, status FROM users WHERE email = 'admin@example.com'"))
        user = result.fetchone()
        
        if user:
            print(f"✅ User found: {user.email}")
            print(f"   ID: {user.id}")
            print(f"   Status: {user.status}")
            print(f"   Hash start: {user.password_hash[:10]}...")
        else:
            print("❌ User 'admin@example.com' NOT FOUND")
            
except Exception as e:
    print(f"Error checking DB: {e}")
