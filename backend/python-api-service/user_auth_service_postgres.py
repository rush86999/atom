"""
User Authentication Service for ATOM Platform - PostgreSQL Version

This service provides user authentication and management functionality
using PostgreSQL as the primary database with SQLite as fallback.
"""

import os
import logging
import uuid
import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
import sqlite3

# Import PostgreSQL database utilities
try:
    from db_utils import get_db_cursor, execute_query, execute_insert, execute_update

    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    logging.warning(
        "PostgreSQL database utilities not available, falling back to SQLite"
    )

logger = logging.getLogger(__name__)

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "your-jwt-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# SQLite Database Configuration (Fallback)
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "/tmp/atom_auth.db")


class UserAuthServicePostgres:
    """
    Service for user authentication and management using PostgreSQL
    """

    @staticmethod
    def init_database():
        """Initialize database tables if they don't exist"""
        if POSTGRES_AVAILABLE:
            return UserAuthServicePostgres._init_postgres_tables()
        else:
            return UserAuthServicePostgres._init_sqlite_tables()

    @staticmethod
    def _init_postgres_tables():
        """Initialize PostgreSQL tables"""
        try:
            # Check if tables exist and create them if needed
            with get_db_cursor() as cursor:
                # Check if User_Credentials table exists
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

                    # Create User table if it doesn't exist
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS public."User" (
                            id UUID PRIMARY KEY,
                            email TEXT,
                            name TEXT,
                            "createdDate" TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
                            deleted BOOLEAN DEFAULT FALSE NOT NULL,
                            "updatedAt" TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                        );
                    """)

                    # Create User_Credentials table
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS public."User_Credentials" (
                            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                            "userId" UUID NOT NULL REFERENCES public."User"(id) ON DELETE CASCADE,
                            email TEXT NOT NULL,
                            password_hash TEXT NOT NULL,
                            "createdAt" TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
                            "updatedAt" TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
                            deleted BOOLEAN DEFAULT FALSE NOT NULL
                        );
                    """)

                    # Create indexes
                    cursor.execute("""
                        CREATE INDEX IF NOT EXISTS idx_user_credentials_user_id
                        ON public."User_Credentials"("userId");
                    """)
                    cursor.execute("""
                        CREATE INDEX IF NOT EXISTS idx_user_credentials_email
                        ON public."User_Credentials"(email);
                    """)
                    cursor.execute("""
                        CREATE UNIQUE INDEX IF NOT EXISTS idx_user_credentials_user_email_unique
                        ON public."User_Credentials"("userId", email) WHERE deleted = false;
                    """)

                    logger.info("PostgreSQL authentication tables created successfully")
                else:
                    logger.info("PostgreSQL authentication tables already exist")

            return True
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL tables: {e}")
            return False

    @staticmethod
    def _init_sqlite_tables():
        """Initialize SQLite tables (fallback)"""
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

            conn.commit()
            conn.close()

            logger.info("SQLite authentication tables initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize SQLite tables: {e}")
            return False

    @classmethod
    async def create_user(
        cls, email: str, password: str, name: str = None
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Create a new user account using PostgreSQL"""

        # Validate input
        if not email or not password:
            return False, "Email and password are required", None

        if len(password) < 6:
            return False, "Password must be at least 6 characters", None

        try:
            # Initialize database if needed
            cls.init_database()

            if POSTGRES_AVAILABLE:
                return await cls._create_user_postgres(email, password, name)
            else:
                return await cls._create_user_sqlite(email, password, name)

        except Exception as e:
            logger.error(f"User creation error: {str(e)}")
            return False, f"Failed to create user: {str(e)}", None

    @classmethod
    async def _create_user_postgres(
        cls, email: str, password: str, name: str = None
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Create user in PostgreSQL"""
        try:
            # Check if user already exists
            existing_user = await cls._get_user_by_email_postgres(email)
            if existing_user:
                return False, "User with this email already exists", None

            # Hash password
            password_hash = cls._hash_password(password)
            user_id = str(uuid.uuid4())

            with get_db_cursor() as cursor:
                # Create user record
                cursor.execute(
                    """
                    INSERT INTO public."User" (id, email, name, "createdDate", "updatedAt")
                    VALUES (%s, %s, %s, NOW(), NOW())
                    ON CONFLICT (id) DO NOTHING
                """,
                    (user_id, email, name),
                )

                # Create credentials record
                cursor.execute(
                    """
                    INSERT INTO public."User_Credentials"
                    ("userId", email, password_hash, "createdAt", "updatedAt")
                    VALUES (%s, %s, %s, NOW(), NOW())
                """,
                    (user_id, email, password_hash),
                )

            logger.info(f"Successfully created user in PostgreSQL: {email}")

            user_info = {
                "id": user_id,
                "email": email,
                "name": name or email.split("@")[0],
            }

            return True, None, user_info

        except Exception as e:
            logger.error(f"PostgreSQL user creation error: {str(e)}")
            return False, f"Database error: {str(e)}", None

    @classmethod
    async def _create_user_sqlite(
        cls, email: str, password: str, name: str = None
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Create user in SQLite (fallback)"""
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

            logger.info(f"Successfully created user in SQLite: {email}")

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
    async def authenticate_user(
        cls, email: str, password: str
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Authenticate a user with email and password"""

        if not email or not password:
            return False, "Email and password are required", None

        try:
            # Initialize database if needed
            cls.init_database()

            if POSTGRES_AVAILABLE:
                return await cls._authenticate_user_postgres(email, password)
            else:
                return await cls._authenticate_user_sqlite(email, password)

        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return False, "Authentication service unavailable", None

    @classmethod
    async def _authenticate_user_postgres(
        cls, email: str, password: str
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Authenticate user against PostgreSQL"""
        try:
            # Get user credentials
            with get_db_cursor() as cursor:
                cursor.execute(
                    """
                    SELECT uc."userId", uc.password_hash, u.email, u.name
                    FROM public."User_Credentials" uc
                    JOIN public."User" u ON uc."userId" = u.id
                    WHERE uc.email = %s AND uc.deleted = FALSE AND u.deleted = FALSE
                """,
                    (email,),
                )

                result = cursor.fetchone()

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
            logger.error(f"PostgreSQL authentication error: {str(e)}")
            return False, "Authentication failed", None

    @classmethod
    async def _authenticate_user_sqlite(
        cls, email: str, password: str
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Authenticate user against SQLite (fallback)"""
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

    @classmethod
    async def _get_user_by_email_postgres(cls, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email from PostgreSQL"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, email, name, "createdDate", "updatedAt"
                    FROM public."User"
                    WHERE email = %s AND deleted = FALSE
                """,
                    (email,),
                )

                result = cursor.fetchone()

            if result:
                return {
                    "id": result[0],
                    "email": result[1],
                    "name": result[2],
                    "created_date": result[3],
                    "updated_at": result[4],
                }
            return None
        except Exception as e:
            logger.error(f"Error getting user by email from PostgreSQL: {e}")
            return None

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
    async def get_user_profile(
        cls, user_id: str
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Get user profile information"""
        try:
            if POSTGRES_AVAILABLE:
                return await cls._get_user_profile_postgres(user_id)
            else:
                return await cls._get_user_profile_sqlite(user_id)
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return False, "Failed to get user profile", None

    @classmethod
    async def _get_user_profile_postgres(
        cls, user_id: str
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Get user profile from PostgreSQL"""
        try:
            with get_db_cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id, email, name, "createdDate", "updatedAt"
                    FROM public."User"
                    WHERE id = %s AND deleted = FALSE
                """,
                    (user_id,),
                )

                result = cursor.fetchone()

            if result:
                profile = {
                    "id": result[0],
                    "email": result[1],
                    "name": result[2],
                    "created_date": result[3].isoformat() if result[3] else None,
                    "updated_at": result[4].isoformat() if result[4] else None,
                }
                return True, None, profile
            else:
                return False, "User not found", None
        except Exception as e:
            logger.error(f"Error getting user profile from PostgreSQL: {e}")
            return False, "Database error", None

    @classmethod
    async def _get_user_profile_sqlite(
        cls, user_id: str
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Get user profile from SQLite (fallback)"""
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
            "service": "user_auth_service_postgres",
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "database": {
                "postgresql": "available" if POSTGRES_AVAILABLE else "unavailable",
                "sqlite": "available",
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
