"""
User Authentication Service for ATOM Platform

This service provides user authentication and management functionality
using SQLite as the primary database with PostgreSQL as a fallback option.
"""

import os
import logging
import uuid
import bcrypt
import jwt
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "your-jwt-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# Database Configuration
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "/tmp/atom_auth.db")
POSTGRES_ENABLED = os.getenv("POSTGRES_ENABLED", "false").lower() == "true"

# PostgreSQL imports (optional)
try:
    import psycopg2
    from psycopg2 import pool

    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    logger.warning("PostgreSQL libraries not available, using SQLite only")


class UserAuthService:
    """
    Service for user authentication and management
    """

    @staticmethod
    def init_database():
        """Initialize database tables"""
        try:
            # Always initialize SQLite first (primary)
            UserAuthService._init_sqlite_tables()

            # Initialize PostgreSQL if enabled and available
            if POSTGRES_ENABLED and POSTGRES_AVAILABLE:
                UserAuthService._init_postgres_tables()

            return True
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            return False

    @staticmethod
    def _init_sqlite_tables():
        """Initialize SQLite database with required tables"""
        try:
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

            # Insert demo users if they don't exist
            demo_users = [
                ("11111111-1111-1111-1111-111111111111", "demo@atom.com", "Demo User"),
                (
                    "22222222-2222-2222-2222-222222222222",
                    "noreply@atom.com",
                    "Admin User",
                ),
            ]

            for user_id, email, name in demo_users:
                cursor.execute(
                    "INSERT OR IGNORE INTO users (id, email, name) VALUES (?, ?, ?)",
                    (user_id, email, name),
                )

            # Insert demo credentials (passwords: demo123 and admin123)
            demo_credentials = [
                (
                    str(uuid.uuid4()),
                    "11111111-1111-1111-1111-111111111111",
                    "demo@atom.com",
                    "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj89tiM7FEyG",
                ),
                (
                    str(uuid.uuid4()),
                    "22222222-2222-2222-2222-222222222222",
                    "noreply@atom.com",
                    "$2b$12$8S5DlN8pZfV6W6eF5YqZXOe3nJ9mR7Lk2V1rB4wX3yH7vM8N9pQ1K",
                ),
            ]

            for cred_id, user_id, email, password_hash in demo_credentials:
                cursor.execute(
                    "INSERT OR IGNORE INTO user_credentials (id, user_id, email, password_hash) VALUES (?, ?, ?, ?)",
                    (cred_id, user_id, email, password_hash),
                )

            conn.commit()
            conn.close()

            logger.info("SQLite authentication tables initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize SQLite tables: {e}")
            return False

    @staticmethod
    def _init_postgres_tables():
        """Initialize PostgreSQL tables if enabled"""
        if not POSTGRES_ENABLED or not POSTGRES_AVAILABLE:
            return False

        try:
            database_url = os.getenv("DATABASE_URL")
            if not database_url:
                logger.warning(
                    "DATABASE_URL not set, skipping PostgreSQL initialization"
                )
                return False

            conn = psycopg2.connect(database_url)
            cursor = conn.cursor()

            # Check if tables exist
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'User_Credentials'
                );
            """)
            table_exists = cursor.fetchone()[0]

            if not table_exists:
                logger.info("Creating PostgreSQL authentication tables...")

                # Run the migration script
                migration_path = os.path.join(
                    os.path.dirname(__file__), "create_user_credentials_table.sql"
                )

                if os.path.exists(migration_path):
                    with open(migration_path, "r") as f:
                        migration_sql = f.read()
                    cursor.execute(migration_sql)
                    conn.commit()
                    logger.info("PostgreSQL authentication tables created successfully")
                else:
                    logger.warning("PostgreSQL migration script not found")
            else:
                logger.info("PostgreSQL authentication tables already exist")

            cursor.close()
            conn.close()
            return True

        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL tables: {e}")
            return False

    @classmethod
    def create_user(
        cls, email: str, password: str, name: str = None
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Create a new user account"""

        # Validate input
        if not email or not password:
            return False, "Email and password are required", None

        if len(password) < 6:
            return False, "Password must be at least 6 characters", None

        try:
            # Initialize database if needed
            cls.init_database()

            # Always use SQLite as primary
            return cls._create_user_sqlite(email, password, name)

        except Exception as e:
            logger.error(f"User creation error: {str(e)}")
            return False, f"Failed to create user: {str(e)}", None

    @classmethod
    def _create_user_sqlite(
        cls, email: str, password: str, name: str = None
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Create user in SQLite"""
        try:
            conn = sqlite3.connect(SQLITE_DB_PATH)
            cursor = conn.cursor()

            # Check if user already exists
            cursor.execute(
                "SELECT id FROM users WHERE email = ? AND deleted = FALSE", (email,)
            )
            if cursor.fetchone():
                conn.close()
                return False, "User with this email already exists", None

            # Hash password
            password_hash = cls._hash_password(password)
            user_id = str(uuid.uuid4())

            # Create user record
            cursor.execute(
                "INSERT INTO users (id, email, name) VALUES (?, ?, ?)",
                (user_id, email, name),
            )

            # Create credentials record
            cursor.execute(
                "INSERT INTO user_credentials (id, user_id, email, password_hash) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), user_id, email, password_hash),
            )

            conn.commit()
            conn.close()

            logger.info(f"Successfully created user: {email}")

            user_info = {
                "id": user_id,
                "email": email,
                "name": name or email.split("@")[0],
            }

            return True, None, user_info

        except Exception as e:
            logger.error(f"SQLite user creation error: {str(e)}")
            return False, f"Database error: {str(e)}", None

    @classmethod
    def authenticate_user(
        cls, email: str, password: str
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Authenticate a user with email and password"""

        if not email or not password:
            return False, "Email and password are required", None

        try:
            # Initialize database if needed
            cls.init_database()

            # Always use SQLite as primary
            return cls._authenticate_user_sqlite(email, password)

        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return False, "Authentication service unavailable", None

    @classmethod
    def _authenticate_user_sqlite(
        cls, email: str, password: str
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Authenticate user against SQLite"""
        try:
            conn = sqlite3.connect(SQLITE_DB_PATH)
            cursor = conn.cursor()

            # Get user credentials
            cursor.execute(
                """
                SELECT uc.user_id, uc.password_hash, u.email, u.name
                FROM user_credentials uc
                JOIN users u ON uc.user_id = u.id
                WHERE uc.email = ? AND uc.deleted = FALSE AND u.deleted = FALSE
            """,
                (email,),
            )

            result = cursor.fetchone()
            conn.close()

            if not result:
                return False, "Invalid email or password", None

            user_id, password_hash, user_email, user_name = result

            # Verify password
            if not cls._verify_password(password, password_hash):
                return False, "Invalid email or password", None

            # Generate JWT token
            token = cls._generate_jwt_token(user_id, user_email)

            user_info = {
                "id": user_id,
                "email": user_email,
                "name": user_name,
                "token": token,
            }

            logger.info(f"User authenticated successfully: {email}")
            return True, None, user_info

        except Exception as e:
            logger.error(f"SQLite authentication error: {str(e)}")
            return False, "Authentication failed", None

    @staticmethod
    def _hash_password(password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    @staticmethod
    def _verify_password(password: str, hashed_password: str) -> bool:
        """Verify password against bcrypt hash"""
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"), hashed_password.encode("utf-8")
            )
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False

    @staticmethod
    def _generate_jwt_token(user_id: str, email: str) -> str:
        """Generate JWT token for authenticated user"""
        payload = {
            "user_id": user_id,
            "email": email,
            "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS),
            "iat": datetime.utcnow(),
        }
        return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

    @staticmethod
    def verify_jwt_token(token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token and return payload if valid"""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            logger.error("JWT token expired")
            return None
        except jwt.InvalidTokenError:
            logger.error("Invalid JWT token")
            return None

    @classmethod
    def get_user_profile(
        cls, user_id: str
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Get user profile information"""
        try:
            return cls._get_user_profile_sqlite(user_id)
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return False, "Failed to get user profile", None

    @classmethod
    def _get_user_profile_sqlite(
        cls, user_id: str
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Get user profile from SQLite"""
        try:
            conn = sqlite3.connect(SQLITE_DB_PATH)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, email, name, created_date, updated_at
                FROM users
                WHERE id = ? AND deleted = FALSE
            """,
                (user_id,),
            )

            result = cursor.fetchone()
            conn.close()

            if result:
                profile = {
                    "id": result[0],
                    "email": result[1],
                    "name": result[2],
                    "created_date": result[3],
                    "updated_at": result[4],
                }
                return True, None, profile
            else:
                return False, "User not found", None
        except Exception as e:
            logger.error(f"Error getting user profile from SQLite: {e}")
            return False, "Database error", None

    @classmethod
    def health_check(cls) -> Dict[str, Any]:
        """Check service health"""
        health_status = {
            "service": "user_auth_service",
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "database": {
                "primary": "sqlite",
                "postgresql": "enabled" if POSTGRES_ENABLED else "disabled",
                "postgresql_available": POSTGRES_AVAILABLE,
            },
        }

        # Test database connectivity
        try:
            cls.init_database()
            health_status["database_initialized"] = True
        except Exception as e:
            health_status["database_initialized"] = False
            health_status["error"] = str(e)
            health_status["status"] = "unhealthy"

        return health_status
