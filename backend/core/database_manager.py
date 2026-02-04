"""
Database Manager

⚠️ DEPRECATED - Retained for Async Operations Only

This module is kept ONLY for async database operations needed by chat_process_manager.py.
For all NEW code, use core.database with get_db() (dependency injection) or get_db_session() (context manager).

Why This File Still Exists:
    - chat_process_manager.py requires async database operations (execute, fetch_one, fetch_all)
    - core.database currently provides only synchronous SQLAlchemy sessions
    - TODO: Migrate chat_process_manager.py to async SQLAlchemy or add async support to core.database

Migration Status:
    - Phase 4 (Cleanup): Cannot remove until chat_process_manager.py is migrated
    - All other code has been migrated to core.database patterns
    - See: docs/DATABASE_SESSION_GUIDE.md for proper database patterns

For Production Code:
    - API Routes: Use `db: Session = Depends(get_db)`
    - Services: Use `with get_db_session() as db:`
    - Tests: Use `SessionLocal()` directly is acceptable
"""

import json
import logging
import os
import warnings
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.sql import text

from core.config import get_config
from core.database import Base
from core.models import AuditLog, User, UserSession, WorkflowExecution

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.config = get_config()
        self.db_url = self.config.database.url
        # Convert sync SQLAlchemy URL to async URL for aiosqlite
        if self.db_url.startswith("sqlite:///"):
            # Replace sqlite:/// with sqlite+aiosqlite:/// for async support
            self.async_db_url = self.db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
        elif self.db_url.startswith("postgresql://"):
            # For PostgreSQL, use asyncpg
            self.async_db_url = self.db_url.replace("postgresql://", "postgresql+asyncpg://")
        else:
            # Default to sqlite+aiosqlite
            self.async_db_url = "sqlite+aiosqlite:///atom_data.db"

        self.engine = None
        self.async_session_maker = None
        self._initialized = False

    async def initialize(self):
        """Initialize database connection and schema"""
        if self._initialized:
            return

        try:
            self.engine = create_async_engine(
                self.async_db_url,
                echo=False,
                future=True
            )
            self.async_session_maker = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )

            # Create tables that don't exist (only for development)
            # In production, use Alembic migrations
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            logger.info(f"Connected to database: {self.db_url}")
            self._initialized = True

        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise

    async def _get_session(self) -> AsyncSession:
        """Get async session"""
        if not self._initialized:
            await self.initialize()
        return self.async_session_maker()

    async def close(self):
        """Close database connection"""
        if self.engine:
            await self.engine.dispose()
            self.engine = None
            self.async_session_maker = None
            self._initialized = False
            logger.info("Database connection closed")

    async def execute(self, query: str, params: Tuple = ()) -> None:
        """Execute a raw SQL query (INSERT, UPDATE, DELETE, CREATE)"""
        async with await self._get_session() as session:
            try:
                # Convert params to dict for SQLAlchemy if needed
                # SQLAlchemy expects named parameters for some dialects
                # For simplicity, we'll use text() with positional parameters
                stmt = text(query)
                result = await session.execute(stmt, params)
                await session.commit()
                return result
            except Exception as e:
                await session.rollback()
                logger.error(f"Query execution failed: {e}, query: {query}, params: {params}")
                raise

    async def fetch_one(self, query: str, params: Tuple = ()) -> Optional[Dict[str, Any]]:
        """Fetch a single row using raw SQL"""
        async with await self._get_session() as session:
            try:
                stmt = text(query)
                result = await session.execute(stmt, params)
                row = result.fetchone()
                if row:
                    # Convert row to dict
                    return dict(row._mapping)
                return None
            except Exception as e:
                logger.error(f"Fetch one failed: {e}, query: {query}, params: {params}")
                raise

    async def fetch_all(self, query: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """Fetch all rows using raw SQL"""
        async with await self._get_session() as session:
            try:
                stmt = text(query)
                result = await session.execute(stmt, params)
                rows = result.fetchall()
                return [dict(row._mapping) for row in rows]
            except Exception as e:
                logger.error(f"Fetch all failed: {e}, query: {query}, params: {params}")
                raise

    # User operations - now using SQLAlchemy models
    async def create_user(self, email: str, name: Optional[str] = None) -> Dict[str, Any]:
        """Create a new user (real implementation)"""
        async with await self._get_session() as session:
            try:
                # Check if user already exists
                existing = await session.execute(
                    text("SELECT * FROM users WHERE email = :email"),
                    {"email": email}
                )
                if existing.fetchone():
                    raise ValueError(f"User with email {email} already exists")

                # Create new user
                user = User(
                    email=email,
                    first_name=name,
                    status="active",
                    role="member"
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)

                return {
                    "id": user.id,
                    "email": user.email,
                    "name": name,
                    "first_name": user.first_name,
                    "last_name": user.last_name
                }
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to create user: {e}")
                raise

    async def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email (real implementation)"""
        async with await self._get_session() as session:
            try:
                result = await session.execute(
                    text("SELECT * FROM users WHERE email = :email"),
                    {"email": email}
                )
                row = result.fetchone()
                if row:
                    user_dict = dict(row._mapping)
                    return {
                        "id": user_dict["id"],
                        "email": user_dict["email"],
                        "name": f"{user_dict.get('first_name', '')} {user_dict.get('last_name', '')}".strip(),
                        "first_name": user_dict.get("first_name"),
                        "last_name": user_dict.get("last_name"),
                        "role": user_dict.get("role"),
                        "status": user_dict.get("status")
                    }
                return None
            except Exception as e:
                logger.error(f"Failed to get user by email: {e}")
                raise

    # Additional helper methods for SQLAlchemy ORM operations
    async def create_workflow_execution(self, **kwargs) -> WorkflowExecution:
        """Create a workflow execution using ORM"""
        async with await self._get_session() as session:
            try:
                execution = WorkflowExecution(**kwargs)
                session.add(execution)
                await session.commit()
                await session.refresh(execution)
                return execution
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to create workflow execution: {e}")
                raise

    async def get_workflow_execution(self, execution_id: str) -> Optional[WorkflowExecution]:
        """Get workflow execution by ID using ORM"""
        async with await self._get_session() as session:
            try:
                result = await session.execute(
                    text("SELECT * FROM workflow_executions WHERE execution_id = :execution_id"),
                    {"execution_id": execution_id}
                )
                row = result.fetchone()
                if row:
                    # Convert to WorkflowExecution object
                    data = dict(row._mapping)
                    return WorkflowExecution(**data)
                return None
            except Exception as e:
                logger.error(f"Failed to get workflow execution: {e}")
                raise

# Global instance
db_manager = DatabaseManager()


# ============================================================================
# Synchronous Database Session Manager
# ============================================================================

from contextlib import contextmanager
from sqlalchemy.orm import Session as SyncSession
from core.database import SessionLocal


@contextmanager
def get_db_session(
    commit: bool = False,
    close: bool = True,
    rollback_on_error: bool = True
):
    """
    ⚠️ DEPRECATED: Use core.database.get_db_session() instead.

    This function is deprecated and will be removed in a future version.
    Please migrate to core.database.get_db_session() which provides the
    same functionality with better integration.

    Migration:
        OLD: from core.database_manager import get_db_session
        NEW: from core.database import get_db_session

    The new function has the same signature and behavior.

    ---

    Unified database session manager with auto-commit/rollback.

    Provides a context manager for database sessions that automatically:
    - Commits if `commit=True` and no exceptions occur
    - Rolls back if `rollback_on_error=True` and an exception occurs
    - Closes the session if `close=True`

    Args:
        commit: Whether to automatically commit on success (default: False)
        close: Whether to automatically close the session (default: True)
        rollback_on_error: Whether to rollback on error (default: True)

    Example:
        # Read-only (no commit)
        with get_db_session() as db:
            user = db.query(User).filter(User.id == user_id).first()
            print(user.name)

        # Auto-commit
        with get_db_session(commit=True) as db:
            user = User(name="John", email="john@example.com")
            db.add(user)
            # Automatically committed on exit

        # Manual transaction control
        with get_db_session(commit=False, close=False) as db:
            user = db.query(User).first()
            user.name = "Updated"
            db.commit()
        # Session still open for further operations

    Feature Flags:
        None - this is a core utility function
    """
    # Emit deprecation warning
    warnings.warn(
        "database_manager.get_db_session() is deprecated. "
        "Use core.database.get_db_session() instead. "
        "This function will be removed in version 2.0.",
        DeprecationWarning,
        stacklevel=2
    )

    db = SessionLocal()
    try:
        yield db
        if commit:
            db.commit()
    except Exception as e:
        if rollback_on_error:
            db.rollback()
        raise
    finally:
        if close:
            db.close()


def get_db_session_for_request():
    """
    ⚠️ DEPRECATED: Use core.database.get_db() instead.

    This function is deprecated and will be removed in a future version.
    Please migrate to core.database.get_db() for FastAPI dependencies.

    Migration:
        OLD: from core.database_manager import get_db_session_for_request
        NEW: from core.database import get_db

    ---

    Get database session for FastAPI request dependency.

    This is a generator function that can be used with FastAPI's Depends:

    Example:
        @router.get("/users/{user_id}")
        async def get_user(user_id: str, db: Session = Depends(get_db_session_for_request)):
            user = db.query(User).filter(User.id == user_id).first()
            return user

    Note: This function does NOT auto-commit or auto-close.
    FastAPI handles the lifecycle of the session.
    """
    # Emit deprecation warning
    warnings.warn(
        "database_manager.get_db_session_for_request() is deprecated. "
        "Use core.database.get_db() instead for FastAPI dependencies. "
        "This function will be removed in version 2.0.",
        DeprecationWarning,
        stacklevel=2
    )

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# Database Session Health Monitoring
# ============================================================================

import time
from collections import deque
from typing import Deque


class SessionHealthMonitor:
    """
    Monitor database session health and performance.

    Tracks:
    - Session creation time
    - Query execution time
    - Session lifetime
    - Error rates
    """

    def __init__(self, max_samples: int = 1000):
        self.max_samples = max_samples
        self.creation_times: Deque[float] = deque(maxlen=max_samples)
        self.query_times: Deque[float] = deque(maxlen=max_samples)
        self.error_count: int = 0
        self.total_sessions: int = 0

    def record_session_creation(self, duration: float):
        """Record time taken to create a session"""
        self.creation_times.append(duration)
        self.total_sessions += 1

    def record_query(self, duration: float):
        """Record time taken to execute a query"""
        self.query_times.append(duration)

    def record_error(self):
        """Record a database error"""
        self.error_count += 1

    def get_stats(self) -> Dict[str, Any]:
        """Get health statistics"""
        return {
            "total_sessions": self.total_sessions,
            "error_count": self.error_count,
            "error_rate": self.error_count / max(self.total_sessions, 1),
            "avg_creation_time": sum(self.creation_times) / max(len(self.creation_times), 1),
            "avg_query_time": sum(self.query_times) / max(len(self.query_times), 1),
            "p95_creation_time": self._percentile(self.creation_times, 95),
            "p99_creation_time": self._percentile(self.creation_times, 99),
        }

    def _percentile(self, data: Deque[float], p: int) -> float:
        """Calculate percentile of data"""
        if not data:
            return 0.0
        sorted_data = sorted(data)
        index = int(len(sorted_data) * p / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]


# Global health monitor instance
session_health_monitor = SessionHealthMonitor()


@contextmanager
def get_monitored_db_session(commit: bool = False, close: bool = True):
    """
    ⚠️ DEPRECATED: Health monitoring is now integrated into core.database.

    This function is deprecated. Use core.database.get_db_session() for
    standard operations. Health monitoring is available through the
    ErrorHandlingMiddleware in production.

    ---

    Get database session with health monitoring.

    Tracks session creation time and error rates for observability.

    Example:
        with get_monitored_db_session(commit=True) as db:
            user = User(name="John")
            db.add(user)
            # Session creation time and errors are automatically tracked
    """
    # Emit deprecation warning
    warnings.warn(
        "database_manager.get_monitored_db_session() is deprecated. "
        "Use core.database.get_db_session() instead. "
        "Health monitoring is now handled by ErrorHandlingMiddleware. "
        "This function will be removed in version 2.0.",
        DeprecationWarning,
        stacklevel=2
    )

    start_time = time.time()

    try:
        with get_db_session(commit=commit, close=close) as db:
            creation_time = time.time() - start_time
            session_health_monitor.record_session_creation(creation_time)
            yield db

    except Exception as e:
        session_health_monitor.record_error()
        raise
