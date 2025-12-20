"""
Database Manager

Handles database connections and operations using SQLAlchemy async.
Provides async methods for executing queries and managing transactions.
Unified database layer using SQLAlchemy models.
"""

import os
import logging
import json
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.sql import text
from sqlalchemy import inspect
from core.config import get_config
from core.database import Base
from core.models import WorkflowExecution, AuditLog, UserSession, User

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
