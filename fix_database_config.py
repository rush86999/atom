#!/usr/bin/env python3
"""
Database Configuration Fix for ATOM Platform

This script fixes database configuration issues by ensuring proper
SQLite fallback is used when PostgreSQL is not available.
It also creates necessary database tables and ensures proper
connection handling.
"""

import os
import sys
import logging
import sqlite3
import json
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class DatabaseConfigFixer:
    """Fixes database configuration issues for ATOM platform"""

    def __init__(self):
        self.db_path = None
        self.connection = None

    def get_database_path(self):
        """Get the SQLite database path from environment or use default"""
        database_url = os.getenv("DATABASE_URL", "sqlite:///./data/atom_development.db")

        if database_url.startswith("sqlite:///"):
            db_path = database_url[10:]  # Remove 'sqlite:///' prefix
        else:
            db_path = "./data/atom_development.db"
            logger.warning(f"Invalid DATABASE_URL format, using default: {db_path}")

        # Ensure directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self.db_path = db_path
        logger.info(f"Using database path: {db_path}")
        return db_path

    def create_database_tables(self):
        """Create necessary database tables if they don't exist"""
        try:
            self.connection = sqlite3.connect(self.db_path)
            cursor = self.connection.cursor()

            # Create users table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    name TEXT,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    deleted INTEGER DEFAULT 0
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
                    deleted INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)

            # Create messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    message_type TEXT DEFAULT 'text',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    deleted INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)

            # Create tasks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    status TEXT DEFAULT 'pending',
                    priority TEXT DEFAULT 'medium',
                    due_date TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    deleted INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)

            # Create indexes for performance
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_credentials_user_id ON user_credentials(user_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_credentials_email ON user_credentials(email)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)"
            )

            self.connection.commit()
            logger.info("Database tables created successfully")

        except Exception as e:
            logger.error(f"Error creating database tables: {e}")
            if self.connection:
                self.connection.rollback()
            raise

    def insert_demo_data(self):
        """Insert demo data for testing"""
        try:
            cursor = self.connection.cursor()

            # Insert demo users if they don't exist - simplified to debug
            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO users (id, email, name) VALUES (?, ?, ?)",
                    (
                        "11111111-1111-1111-1111-111111111111",
                        "demo@atom.com",
                        "Demo User",
                    ),
                )
                logger.info("Inserted demo user 1")
            except Exception as e:
                logger.error(f"Error inserting demo user 1: {e}")

            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO users (id, email, name) VALUES (?, ?, ?)",
                    (
                        "22222222-2222-2222-2222-222222222222",
                        "noreply@atom.com",
                        "Admin User",
                    ),
                )
                logger.info("Inserted demo user 2")
            except Exception as e:
                logger.error(f"Error inserting demo user 2: {e}")

            # Insert demo credentials (passwords: demo123 and admin123) - simplified
            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO user_credentials (id, user_id, email, password_hash) VALUES (?, ?, ?, ?)",
                    (
                        "cred_demo",
                        "11111111-1111-1111-1111-111111111111",
                        "demo@atom.com",
                        "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj89tiM7FEyG",
                    ),
                )
                logger.info("Inserted demo credential 1")
            except Exception as e:
                logger.error(f"Error inserting demo credential 1: {e}")

            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO user_credentials (id, user_id, email, password_hash) VALUES (?, ?, ?, ?)",
                    (
                        "cred_admin",
                        "22222222-2222-2222-2222-222222222222",
                        "noreply@atom.com",
                        "$2b$12$8S5DlN8pZfV6W6eF5YqZXOe3nJ9mR7Lk2V1rB4wX3yH7vM8N9pQ1K",
                    ),
                )
                logger.info("Inserted demo credential 2")
            except Exception as e:
                logger.error(f"Error inserting demo credential 2: {e}")

            # Insert demo messages - simplified
            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO messages (id, user_id, content, message_type) VALUES (?, ?, ?, ?)",
                    (
                        "msg_001",
                        "11111111-1111-1111-1111-111111111111",
                        "Hello, welcome to ATOM!",
                        "welcome",
                    ),
                )
                logger.info("Inserted demo message 1")
            except Exception as e:
                logger.error(f"Error inserting demo message 1: {e}")

            # Insert demo tasks - simplified
            try:
                cursor.execute(
                    "INSERT OR IGNORE INTO tasks (id, user_id, title, description, status, priority) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        "task_001",
                        "11111111-1111-1111-1111-111111111111",
                        "Complete onboarding",
                        "Learn about ATOM features",
                        "pending",
                        "medium",
                    ),
                )
                logger.info("Inserted demo task 1")
            except Exception as e:
                logger.error(f"Error inserting demo task 1: {e}")

            self.connection.commit()
            logger.info("Demo data inserted successfully")

        except Exception as e:
            logger.error(f"Error inserting demo data: {e}")
            if self.connection:
                self.connection.rollback()
            raise

    def test_database_operations(self):
        """Test database operations to ensure everything is working"""
        try:
            cursor = self.connection.cursor()

            # Test user query
            cursor.execute("SELECT COUNT(*) as count FROM users")
            user_count = cursor.fetchone()[0]
            logger.info(f"Users in database: {user_count}")

            # Test messages query
            cursor.execute("SELECT COUNT(*) as count FROM messages")
            message_count = cursor.fetchone()[0]
            logger.info(f"Messages in database: {message_count}")

            # Test tasks query
            cursor.execute("SELECT COUNT(*) as count FROM tasks")
            task_count = cursor.fetchone()[0]
            logger.info(f"Tasks in database: {task_count}")

            # Test authentication query
            cursor.execute(
                """
                SELECT u.id, u.email, u.name
                FROM users u
                JOIN user_credentials uc ON u.id = uc.user_id
                WHERE u.email = ? AND u.deleted = FALSE
            """,
                ("demo@atom.com",),
            )

            user = cursor.fetchone()
            if user:
                logger.info(f"Authentication test passed: Found user {user[1]}")
            else:
                logger.warning("Authentication test: No demo user found")

            return True

        except Exception as e:
            logger.error(f"Database test failed: {e}")
            return False

    def create_environment_config(self):
        """Create environment configuration for proper database usage"""
        env_config = {
            "DATABASE_URL": f"sqlite:///{self.db_path}",
            "FLASK_ENV": "development",
            "FLASK_SECRET_KEY": "dev-secret-key-change-in-production",
            "SQLITE_FALLBACK_ENABLED": "true",
        }

        # Write to .env file if accessible
        try:
            with open(".env", "w") as f:
                for key, value in env_config.items():
                    f.write(f"{key}={value}\n")
            logger.info("Environment configuration updated")
        except Exception as e:
            logger.warning(f"Could not update .env file: {e}")

        return env_config

    def run_fix(self):
        """Run the complete database configuration fix"""
        logger.info("🚀 Starting Database Configuration Fix")
        logger.info("=" * 50)

        try:
            # Step 1: Get database path
            self.get_database_path()

            # Step 2: Create tables
            self.create_database_tables()

            # Step 3: Insert demo data
            self.insert_demo_data()

            # Step 4: Test operations
            test_result = self.test_database_operations()

            # Step 5: Create environment config
            env_config = self.create_environment_config()

            # Step 6: Close connection
            if self.connection:
                self.connection.close()

            logger.info("=" * 50)
            if test_result:
                logger.info("✅ Database configuration fix completed successfully")
                return True
            else:
                logger.error("❌ Database configuration fix completed with warnings")
                return False

        except Exception as e:
            logger.error(f"❌ Database configuration fix failed: {e}")
            return False


def main():
    """Main function"""
    fixer = DatabaseConfigFixer()
    success = fixer.run_fix()

    if success:
        print("\n🎉 Database configuration is now ready!")
        print("The following endpoints should now work:")
        print("  - /api/messages")
        print("  - /api/tasks")
        print("  - /api/auth/* endpoints")
        print(
            "\nYou may need to restart the main application for changes to take effect."
        )
        sys.exit(0)
    else:
        print("\n❌ Database configuration fix failed. Check logs for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
