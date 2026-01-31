
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.pool import StaticPool
import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

# CRITICAL: Production database configuration
logger = logging.getLogger(__name__)
print(f"DEBUG: Loading core.database module. ENV: MOCK={os.getenv('ATOM_MOCK_DATABASE')}", file=sys.stderr)

def get_database_url():
    """Get database URL with production safety checks"""
    env = os.getenv("ENVIRONMENT", "development")
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        if env == "production":
            raise ValueError(
                "CRITICAL: DATABASE_URL environment variable is required in production! "
                "Cannot use default SQLite in production."
            )
        else:
            # Development fallback: Use FILE-BASED SQLite to prevent threading/import issues
            database_url = "sqlite:///./dev.db"
            logger.warning(
                "⚠️ WARNING: Using SQLite file database (dev.db). "
                "Set DATABASE_URL for production deployment."
            )
    
    # CI/Testing Override: Force in-memory SQLite if requested
    # This prevents blocking connection attempts during import checks
    if os.getenv("ATOM_MOCK_DATABASE", "false").lower() == "true":
        database_url = "sqlite:///:memory:"
        logger.warning("🛡️ ATOM_MOCK_DATABASE enabled: Using in-memory SQLite for CI/Testing")
        return database_url

    # Security: Ensure SSL for PostgreSQL in production
    if env == "production" and "postgresql" in database_url:
        if "sslmode=" not in database_url:
            database_url += "?sslmode=require"
            logger.info("🔒 Added SSL requirement for PostgreSQL connection")

    return database_url

DATABASE_URL = get_database_url()

# Production-ready connection configuration
if "sqlite" in DATABASE_URL:
    # SQLite configuration (development only)
    connect_args = {
        "check_same_thread": False,
        "timeout": 20  # Prevent database locking
    }
    if ":memory:" in DATABASE_URL:
        poolclass = StaticPool
    else:
        poolclass = None
    pool_size = None
    max_overflow = None
elif "postgresql" in DATABASE_URL:
    # PostgreSQL configuration
    env = os.getenv("ENVIRONMENT", "development")
    if env == "production":
        connect_args = {
            "sslmode": "require",
            "sslcert": os.getenv("DB_SSL_CERT"),
            "sslkey": os.getenv("DB_SSL_KEY"),
            "sslrootcert": os.getenv("DB_SSL_ROOT_CERT")
        }
    else:
        # Local development usually doesn't need SSL
        connect_args = {
            "sslmode": os.getenv("DB_SSL_MODE", "prefer")
        }
    
    # Remove None values
    connect_args = {k: v for k, v in connect_args.items() if v is not None}
    poolclass = "QueuePool"
    pool_size = 20
    max_overflow = 30
else:
    # Default configuration for other databases
    connect_args = {}
    poolclass = None
    pool_size = None
    max_overflow = None

# Create engine with production settings
engine_kwargs = {
    "connect_args": connect_args,
    "pool_pre_ping": True,  # Verify connection before usage
    "pool_recycle": 3600,  # Recycle connections every hour
    "echo": os.getenv("SQL_ECHO", "false").lower() == "true"
}

# Add pool configuration for PostgreSQL
if pool_size:
    engine_kwargs.update({
        "pool_size": pool_size,
        "max_overflow": max_overflow,
        "pool_timeout": 30,
        "pool_recycle": 3600
    })

engine = create_engine(DATABASE_URL, **engine_kwargs)

# Create session with production settings
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False  # Prevents detached instance errors
)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
