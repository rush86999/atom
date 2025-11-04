#!/usr/bin/env python3
"""
Quick Setup Script for Real Authentication System

This script sets up the real authentication system with SQLite database
and initializes demo users for immediate testing.
"""

import os
import sys
import sqlite3
import bcrypt
import uuid
from pathlib import Path

# Configuration
SQLITE_DB_PATH = "/tmp/atom_auth.db"
DEMO_USERS = [
    {
        "id": "11111111-1111-1111-1111-111111111111",
        "email": "demo@atom.com",
        "password": "demo123",
        "name": "Demo User",
    },
    {
        "id": "22222222-2222-2222-2222-222222222222",
        "email": "noreply@atom.com",
        "password": "admin123",
        "name": "Admin User",
    },
]


def setup_database():
    """Setup SQLite database with required tables"""
    print("🔧 Setting up authentication database...")

    # Ensure directory exists
    Path(SQLITE_DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(SQLITE_DB_PATH)
    cursor = conn.cursor()

    # Create users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            deleted BOOLEAN DEFAULT FALSE
        )
    """)

    # Create user_credentials table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_credentials (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            email TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            deleted BOOLEAN DEFAULT FALSE,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    # Create indexes
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_credentials_user_id ON user_credentials(user_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_credentials_email ON user_credentials(email)"
    )

    print("✅ Database tables created successfully")
    return conn, cursor


def create_demo_users(conn, cursor):
    """Create demo users with hashed passwords"""
    print("👤 Creating demo users...")

    for user in DEMO_USERS:
        # Check if user already exists
        cursor.execute("SELECT id FROM users WHERE email = ?", (user["email"],))
        existing_user = cursor.fetchone()

        if existing_user:
            print(f"⚠️  User {user['email']} already exists, skipping...")
            continue

        # Hash password
        salt = bcrypt.gensalt()
        hashed_password = bcrypt.hashpw(user["password"].encode("utf-8"), salt)

        # Insert user
        cursor.execute(
            "INSERT INTO users (id, email, name) VALUES (?, ?, ?)",
            (user["id"], user["email"], user["name"]),
        )

        # Insert credentials
        cursor.execute(
            "INSERT INTO user_credentials (id, user_id, email, password_hash) VALUES (?, ?, ?, ?)",
            (
                str(uuid.uuid4()),
                user["id"],
                user["email"],
                hashed_password.decode("utf-8"),
            ),
        )

        print(f"✅ Created user: {user['email']}")

    conn.commit()


def test_authentication(cursor):
    """Test authentication with demo users"""
    print("\n🔐 Testing authentication...")

    for user in DEMO_USERS:
        cursor.execute(
            "SELECT uc.password_hash FROM user_credentials uc WHERE uc.email = ?",
            (user["email"],),
        )
        result = cursor.fetchone()

        if result:
            stored_hash = result[0]
            is_valid = bcrypt.checkpw(
                user["password"].encode("utf-8"), stored_hash.encode("utf-8")
            )
            status = "✅ VALID" if is_valid else "❌ INVALID"
            print(f"{status} {user['email']}: {user['password']}")
        else:
            print(f"❌ User {user['email']} not found")


def create_environment_file():
    """Create environment file for configuration"""
    env_content = """# Authentication Configuration
SQLITE_DB_PATH=/tmp/atom_auth.db
JWT_SECRET=your-jwt-secret-key-change-in-production-2024
NEXTAUTH_SECRET=your-nextauth-secret-key-change-in-production-2024
NEXTAUTH_URL=http://localhost:3000

# Backend API Configuration
API_BASE_URL=http://localhost:5058

# Demo Users (for reference)
DEMO_USER_EMAIL=demo@atom.com
DEMO_USER_PASSWORD=demo123
ADMIN_USER_EMAIL=noreply@atom.com
ADMIN_USER_PASSWORD=admin123
"""

    env_path = Path(".env.auth")
    env_path.write_text(env_content)
    print(f"✅ Environment file created: {env_path}")


def main():
    """Main setup function"""
    print("🚀 ATOM Real Authentication Setup")
    print("=" * 50)

    try:
        # Setup database
        conn, cursor = setup_database()

        # Create demo users
        create_demo_users(conn, cursor)

        # Test authentication
        test_authentication(cursor)

        # Create environment file
        create_environment_file()

        print("\n🎉 Setup completed successfully!")
        print("\n📋 Next Steps:")
        print("1. Restart the backend: python start_minimal_api.py")
        print(
            '2. Test login: curl -X POST http://localhost:5058/api/auth/login -H \'Content-Type: application/json\' -d \'{"email":"demo@atom.com","password":"demo123"}\''
        )
        print("3. Access the frontend: http://localhost:3000/auth/signin")
        print("\n🔑 Demo Credentials:")
        print("   Email: demo@atom.com / Password: demo123")
        print("   Email: noreply@atom.com / Password: admin123")

        conn.close()

    except Exception as e:
        print(f"❌ Setup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
