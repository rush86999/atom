
import logging
import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

load_dotenv()

# CRITICAL: Production database configuration
logger = logging.getLogger(__name__)
logger.debug(f"Loading core.database module. ENV: MOCK={os.getenv('ATOM_MOCK_DATABASE')}")

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
    """
    Dependency injection pattern for API routes.

    Usage in FastAPI endpoints:
        @app.get("/users/{user_id}")
        def get_user(user_id: str, db: Session = Depends(get_db)):
            user = db.query(User).filter(User.id == user_id).first()
            return user

    This is the RECOMMENDED pattern for API routes.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# Database Session Management Patterns
# ============================================================================

def get_db_session():
    """
    Context manager pattern for service layer functions.

    This is the RECOMMENDED pattern for service layer code, background tasks,
    and any non-API-route code that needs database access.

    Usage:
        from core.database import get_db_session

        with get_db_session() as db:
            user = db.query(User).first()
            user.name = "Updated"
            db.commit()
        # Session automatically closed after context

    Benefits:
    - Automatic cleanup with context manager
    - Clear scope for database operations
    - Prevents connection leaks
    - Thread-safe

    Preferred over manual `with SessionLocal() as db:` pattern.
    """
    from contextlib import contextmanager

    @contextmanager
    def _session_context():
        db = SessionLocal()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    return _session_context()


# Legacy alias for backwards compatibility
# Use get_db_session() in new code
def get_db_context():
    """
    DEPRECATED: Use get_db_session() instead.

    This is an alias for backwards compatibility with existing code.
    """
    return get_db_session()


# ============================================================================
# Session Management Guidelines
# ============================================================================

"""
STANDARD DATABASE SESSION PATTERNS

This codebase supports three database session management patterns:

1. CONTEXT MANAGER PATTERN (RECOMMENDED for Service Layer)
   --------------------------------------------------------
   Use for: Service layer functions, background tasks, scripts

   from core.database import get_db_session

   with get_db_session() as db:
       user = db.query(User).first()
       # ... perform operations ...
       db.commit()  # Optional - auto-commits on success
   # Session automatically closed

   Benefits:
   - Automatic cleanup
   - Clear scope
   - Prevents connection leaks
   - Auto-commit on success, auto-rollback on exception

2. DEPENDENCY INJECTION PATTERN (RECOMMENDED for API Routes)
   ---------------------------------------------------------
   Use for: FastAPI endpoint functions

   from core.database import get_db
   from fastapi import Depends

   @app.get("/users/{user_id}")
   def get_user(user_id: str, db: Session = Depends(get_db)):
       return db.query(User).filter(User.id == user_id).first()

   Benefits:
   - FastAPI standard pattern
   - Automatic lifecycle management
   - Testable with dependency override
   - Type-safe

3. MANUAL PATTERN (DEPRECATED - Avoid in new code)
   ------------------------------------------------
   OLD WAY (don't use):
       with get_db_session() as db:
       try:
           # operations
           db.commit()
       finally:
           db.close()

   NEW WAY (use context manager instead):
       with get_db_session() as db:
           # operations
           # auto-commit/rollback/close

MIGRATION GUIDE

If you see manual session management in code:
1. Replace `with get_db_session() as db:` with `with get_db_session() as db:`
2. Remove the `try/finally` block (context manager handles it)
3. Remove explicit `db.close()` calls
4. Optionally remove explicit `db.commit()` if at end of function

Example Migration:
    # OLD
    def process_data(data_id: str):
        with get_db_session() as db:
        try:
            data = db.query(Data).filter(Data.id == data_id).first()
            data.processed = True
            db.commit()
        finally:
            db.close()

    # NEW
    from core.database import get_db_session

    def process_data(data_id: str):
        with get_db_session() as db:
            data = db.query(Data).filter(Data.id == data_id).first()
            data.processed = True
            # Auto-commits on success

BEST PRACTICES

1. **API Routes**: Always use dependency injection (`Depends(get_db)`)
2. **Service Layer**: Always use context manager (`with get_db_session() as db:`)
3. **Testing**: Use dependency override or context manager
4. **Background Tasks**: Use context manager
5. **Scripts**: Use context manager

ANTI-PATTERNS TO AVOID

❌ Mixing patterns (e.g., manual + dependency injection)
❌ Forgetting to close sessions (use context manager)
❌ Long-running sessions (keep transactions short)
❌ Nested sessions (use one session per operation)
❌ Global session variables

PERFORMANCE NOTES

- PostgreSQL pool: 20 connections, 30 max overflow
- SQLite: Single connection with threading disabled
- Connection recycling: Every 3600 seconds (1 hour)
- Pool pre-ping: Enabled (verifies connections before use)

For high-throughput scenarios, consider:
- Using async sessions with SQLAlchemy async
- Connection pooling optimizations
- Read replicas for read-heavy workloads
"""


# ============================================================================
# Async Database Support (Experimental)
# ============================================================================

"""
ASYNC DATABASE SESSION PATTERN

For async/await code, use the async session factory:

    from core.database import get_async_db_session

    async with get_async_db_session() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        # Auto-commits on success, auto-rollback on exception

Benefits:
- Full async/await support
- Non-blocking database operations
- Better performance for I/O-bound workloads
- Compatible with async FastAPI endpoints
"""

try:
    from sqlalchemy.ext.asyncio import (
        AsyncSession,
        async_sessionmaker,
        create_async_engine
    )

    # Create async database URL
    # SQLite: sqlite:///./dev.db -> sqlite+aiosqlite:///./dev.db
    # PostgreSQL: postgresql://... -> postgresql+asyncpg://...
    async_db_url = DATABASE_URL

    if "sqlite:///" in async_db_url:
        async_db_url = async_db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    elif "postgresql://" in async_db_url:
        async_db_url = async_db_url.replace("postgresql://", "postgresql+asyncpg://")
    elif "postgres://" in async_db_url:
        async_db_url = async_db_url.replace("postgres://", "postgresql+asyncpg://")

    # Create async engine
    async_engine_kwargs = {
        "echo": os.getenv("SQL_ECHO", "false").lower() == "true",
    }

    # Add pool configuration for async engine
    if pool_size:
        async_engine_kwargs.update({
            "pool_size": pool_size,
            "max_overflow": max_overflow,
        })

    async_engine = create_async_engine(async_db_url, **async_engine_kwargs)

    # Create async session factory
    AsyncSessionLocal = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )

    ASYNC_DB_AVAILABLE = True
    logger.info("Async database support enabled")

except ImportError as e:
    ASYNC_DB_AVAILABLE = False
    logger.warning(f"Async database support unavailable: {e}")
    logger.warning("Install aiosqlite for SQLite async support: pip install aiosqlite")
    logger.warning("Install asyncpg for PostgreSQL async support: pip install asyncpg")

    async_engine = None
    AsyncSessionLocal = None


async def get_async_db():
    """
    Async dependency injection pattern for API routes.

    Usage in async FastAPI endpoints:
        @app.get("/users/{user_id}")
        async def get_user(user_id: str, db: AsyncSession = Depends(get_async_db)):
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            return user
    """
    if not ASYNC_DB_AVAILABLE:
        raise RuntimeError("Async database support not available. Install aiosqlite or asyncpg.")

    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def get_async_db_session():
    """
    Async context manager pattern for service layer.

    This is the RECOMMENDED pattern for async service layer code.

    Usage:
        from core.database import get_async_db_session
        from sqlalchemy import select

        async with get_async_db_session() as db:
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            user.name = "Updated"
            await db.commit()  # Optional - auto-commits on success
        # Session automatically closed after context

    Benefits:
    - Automatic cleanup with async context manager
    - Clear scope for database operations
    - Prevents connection leaks
    - Non-blocking database operations
    """
    if not ASYNC_DB_AVAILABLE:
        raise RuntimeError("Async database support not available. Install aiosqlite or asyncpg.")

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _async_session_context():
        async with AsyncSessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    return _async_session_context()
