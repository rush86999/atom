
import logging
import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine
import sqlalchemy
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

load_dotenv()
# CRITICAL: Production database configuration
logger = logging.getLogger(__name__)
logger.debug(f"Loading core.database module. ENV: MOCK={os.getenv('ATOM_MOCK_DATABASE')}")

def _clean_postgresql_url(url: str) -> str:
    """Strip ALL SSL and conflicting parameters from a PostgreSQL URL.
    Backported from SaaS to ensure compatibility with providers like Neon/Supabase
    that inject conflicting parameters into the connection string.
    """
    if not url or "postgresql" not in url or "?" not in url:
        return url
    try:
        from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
        parsed = urlparse(url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        
        # Comprehensive list of parameters to remove
        params_to_remove = [
            'sslmode', 'channel_binding', 'sslcert', 'sslkey', 'sslrootcert', 
            'ssl', 'sslrootcert', 'sslcompression', 'target_session_attrs'
        ]
        removed = [p for p in params_to_remove if p in params]
        
        for param in params_to_remove:
            params.pop(param, None)
            
        new_query = urlencode(params, doseq=True) if params else ''
        clean_url = urlunparse(parsed._replace(query=new_query))
        
        if removed:
            logger.debug(f"✓ Cleaned URL params: {removed}")
        return clean_url
    except Exception as e:
        logger.warning(f"Failed to clean URL: {e}")
        return url

# Anchor for relative SQLite paths — a .env URL like sqlite:///./data/atom.db
# is written relative to the backend/ directory (the documented launch dir),
# so resolve it against backend/ to make the database independent of the
# launch CWD (repo root vs backend/ previously meant two different databases).
_DATABASE_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _anchor_sqlite_url(url: str) -> str:
    """Resolve relative SQLite file paths against the backend/ directory.

    ``sqlite:///./data/atom.db`` is CWD-relative in SQLAlchemy: launching
    uvicorn from the repo root vs backend/ silently pointed at two different
    databases. Anchoring reproduces the backend/-launch location from any
    CWD. Absolute paths, ``:memory:`` and non-SQLite URLs pass through
    untouched.
    """
    if not url or not url.startswith("sqlite"):
        return url
    scheme, sep, rest = url.partition(":///")
    if not sep:
        return url
    path = rest
    query = ""
    if "?" in path:
        path, query = path.split("?", 1)
        query = "?" + query
    if not path or path.startswith(("/", ":")):
        return url
    anchored = os.path.normpath(os.path.join(_DATABASE_BACKEND_DIR, path))
    return f"{scheme}:///{anchored}{query}"


def _targets_live_dev_db(url: str) -> bool:
    """True when a SQLite URL resolves to a LIVE dev database file —
    ``backend/dev.db`` (this module's development fallback) or
    ``backend/data/atom.db`` (the application data store). The 2026-09-04
    incident wiped the latter from a stray test run."""
    if not url or not url.startswith("sqlite"):
        return False
    path = _anchor_sqlite_url(url).partition(":///")[2].split("?", 1)[0]
    dev_paths = (
        os.path.join(_DATABASE_BACKEND_DIR, "dev.db"),
        os.path.join(_DATABASE_BACKEND_DIR, "data", "atom.db"),
    )
    return os.path.normpath(path) in (os.path.normpath(p) for p in dev_paths)


def get_database_url():
    """Get database URL with production safety checks"""
    import sys

    env = os.getenv("ENVIRONMENT", "development")
    database_url = os.getenv("DATABASE_URL")

    # INCIDENT GUARD (2026-09-04): a pytest run without TESTING=1 pointed at
    # the live dev DB and wiped it. Whenever pytest is the importing process,
    # keep pytest OFF the live dev databases: unset DATABASE_URL or one that
    # resolves to backend/dev.db / backend/data/atom.db is forced onto the
    # isolated test database. An explicit NON-dev DATABASE_URL is honored —
    # the e2e journey (ci.yml) points pytest at /tmp/atom_e2e.db, the very
    # file the booted backend server uses; forcing the isolated DB here made
    # the journey fixtures write to a fresh table-less copy
    # ("no such table: users", CI 2026-09-05). TESTING=0 still opts a pytest
    # process back into whatever DATABASE_URL says, guard off.
    pytest_running = (
        os.getenv("PYTEST_CURRENT_TEST") is not None
        or os.getenv("PYTEST_VERSION") is not None
        or "pytest" in sys.modules
    )
    if pytest_running and os.getenv("TESTING") != "0":
        if database_url and not _targets_live_dev_db(database_url):
            database_url = _anchor_sqlite_url(_clean_postgresql_url(database_url))
            logger.warning(
                "🧪 pytest detected: honoring explicit non-dev test DB (%s)",
                database_url,
            )
            return database_url
        base_dir = _DATABASE_BACKEND_DIR
        db_path = os.path.join(base_dir, "test_integration.db")
        database_url = f"sqlite:///{db_path}"
        logger.warning("🧪 pytest detected: forcing isolated test DB (%s)", db_path)
        return database_url

    if os.getenv("TESTING") == "1":
        # Force SQLite for integration tests to prevent connection to production Postgres
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(base_dir, "test_integration.db")
        database_url = f"sqlite:///{db_path}"
        logger.info(f"🧪 TESTING mode enabled: Forcing SQLite ({db_path})")
        return database_url

    if not database_url:
        if env == "production":
            raise ValueError(
                "CRITICAL: DATABASE_URL environment variable is required in production! "
                "Cannot use default SQLite in production."
            )
        else:
            # Development fallback
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base_dir, "dev.db")
            database_url = f"sqlite:///{db_path}"
            logger.warning(f"⚠️  Using SQLite file database ({db_path})")
    
    # CI/Testing Override
    if os.getenv("ATOM_MOCK_DATABASE", "false").lower() == "true":
        database_url = "sqlite:///:memory:"
        logger.warning("🛡️  ATOM_MOCK_DATABASE enabled: Using in-memory SQLite")
        return database_url

    # Clean the URL before adding our own SSL parameters
    database_url = _clean_postgresql_url(database_url)

    # Anchor relative SQLite paths so the DB file is independent of the
    # launch CWD (repo root vs backend/ previously meant different databases).
    database_url = _anchor_sqlite_url(database_url)

    # Security: Ensure SSL for PostgreSQL in production
    if env == "production" and "postgresql" in database_url:
        if "sslmode=" not in database_url:
            database_url += "?sslmode=require"
            logger.info("🔒 Added SSL requirement for PostgreSQL connection")

    # Sync back to environment for consistency across processes
    os.environ["DATABASE_URL"] = database_url
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
        pool_size = None
        max_overflow = None
    else:
        # File-backed SQLite (dev/Personal Edition + e2e runs against the
        # live backend): the default QueuePool (size 5, overflow 10, 30s
        # timeout) exhausts under bursty sync-endpoint load (login audits,
        # canvas CRUD, notifications + layout integration polls on every
        # page load), wedging the whole backend mid-suite
        # ("QueuePool limit ... reached, connection timed out"). Use a
        # generous pool with a longer checkout timeout for dev SQLite.
        poolclass = "QueuePool"
        pool_size = 50
        max_overflow = 50
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

# Add pool configuration (QueuePool is the SQLAlchemy default when these
# are set). SQLite file-backed (dev/e2e) uses a generous pool: see the
# sqlite branch above.
if pool_size:
    engine_kwargs.update({
        "pool_size": pool_size,
        "max_overflow": max_overflow,
        "pool_timeout": 60,
        "pool_recycle": 3600
    })

# BUG FIX: `poolclass` was computed above but never passed to create_engine,
# so in-memory SQLite (ATOM_MOCK_DATABASE=true) silently fell back to
# SingletonThreadPool — one private connection per thread. Each thread then
# saw its own EMPTY database (no tables), breaking any TestClient request
# (served on a portal thread) against data set up by test fixtures. Pass the
# StaticPool class when one was selected; the "QueuePool" values in the
# file-sqlite/postgres branches are names only and are left as-is (QueuePool
# is SQLAlchemy's default once pool_size is set).
if poolclass is not None and not isinstance(poolclass, str):
    engine_kwargs["poolclass"] = poolclass

engine = create_engine(DATABASE_URL, **engine_kwargs)

# SQLite durability/concurrency pragmas on EVERY connection (per-connection
# settings must be re-applied per checkout). Evidence (Sep 6, 2026): the
# ingestion re-walk wrote knowledge edges continuously while the DB sat in
# the default journal mode — every writer took an exclusive lock and EVERY
# reader endpoint blocked behind it ("app is just really slow in loading
# anything"; sampled the live process: the event-loop thread itself parked
# on a lock). WAL lets readers proceed while one writer works; NORMAL sync
# is the recommended pairing (durable across app crashes, only vulnerable
# to OS power loss); busy_timeout replaces spurious "database is locked".
if "sqlite" in DATABASE_URL and ":memory:" not in DATABASE_URL:
    from sqlalchemy import event as _sa_event

    @_sa_event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            # busy_timeout: connect_args may already request a longer grace
            # (timeout=20 → 20s). Never LOWER an existing setting.
            current_ms = cursor.execute("PRAGMA busy_timeout").fetchone()[0]
            if current_ms < 5000:
                cursor.execute("PRAGMA busy_timeout=5000")
        finally:
            cursor.close()

# Create session with production settings
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False  # Prevents detached instance errors
)

class Base(DeclarativeBase):
    """
    Base class for SQLAlchemy models.
    """
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
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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
    # NOTE: pool_* kwargs are QueuePool options and are REJECTED by NullPool,
    # which async SQLite (aiosqlite) uses by default. Applying them unconditionally
    # raises TypeError at import time — breaking alembic and any SQLite deploy.
    # Gate them on the Postgres dialect (asyncpg), where pooling is meaningful.
    _is_async_postgres = async_db_url.startswith(("postgresql+asyncpg://", "postgres+asyncpg://"))
    async_engine_kwargs = {
        "echo": os.getenv("SQL_ECHO", "false").lower() == "true",
    }
    if _is_async_postgres:
        async_engine_kwargs.update({
            "pool_pre_ping": True,
            "pool_recycle": 3600,
            "pool_timeout": 30,
        })

    # Add pool configuration for async engine (Postgres only)
    if _is_async_postgres and pool_size:
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
