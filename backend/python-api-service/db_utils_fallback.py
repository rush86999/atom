"""
SQLite Fallback Database Utility

This module provides a fallback SQLite implementation when PostgreSQL is not available.
It mimics the interface of db_utils.py but uses SQLite instead of PostgreSQL.
"""

import os
import logging
import sqlite3
import json
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
from datetime import datetime

logger = logging.getLogger(__name__)

# Global SQLite connection
_sqlite_conn = None

def init_sqlite_db():
    """Initialize SQLite database connection"""
    global _sqlite_conn

    try:
        # Get database URL from environment, fallback to SQLite
        database_url = os.getenv('DATABASE_URL', 'sqlite:///tmp/atom_dev.db')

        # Extract SQLite path from URL
        if database_url.startswith('sqlite:///'):
            db_path = database_url[10:]  # Remove 'sqlite:///' prefix
        else:
            db_path = '/tmp/atom_dev.db'
            logger.warning(f"Invalid DATABASE_URL for SQLite: {database_url}. Using default: {db_path}")

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        _sqlite_conn = sqlite3.connect(db_path, check_same_thread=False)
        _sqlite_conn.row_factory = sqlite3.Row  # Enable dict-like access

        logger.info(f"SQLite database initialized at: {db_path}")
        return _sqlite_conn

    except Exception as e:
        logger.error(f"Failed to initialize SQLite database: {e}")
        return None

def get_db_connection():
    """Get SQLite database connection"""
    global _sqlite_conn
    if _sqlite_conn is None:
        _sqlite_conn = init_sqlite_db()
    return _sqlite_conn

@contextmanager
def get_db_cursor():
    """Context manager for database cursors"""
    conn = get_db_connection()
    if not conn:
        raise ConnectionError("SQLite database connection not available")

    cursor = None
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database transaction error: {e}")
        raise
    finally:
        if cursor:
            cursor.close()

async def execute_query(query: str, params: Optional[tuple] = None) -> List[Dict]:
    """Execute a query and return results as dictionaries"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(query, params or ())
            results = cursor.fetchall()
            return [dict(row) for row in results] if results else []
    except Exception as e:
        logger.error(f"Query execution error: {e}")
        raise

async def execute_insert(query: str, params: Optional[tuple] = None) -> Optional[int]:
    """Execute an INSERT query and return the inserted ID"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(query, params or ())
            if "RETURNING id" in query.upper():
                result = cursor.fetchone()
                return result[0] if result else None
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Insert execution error: {e}")
        raise

async def execute_update(query: str, params: Optional[tuple] = None) -> int:
    """Execute an UPDATE query and return number of affected rows"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(query, params or ())
            return cursor.rowcount
    except Exception as e:
        logger.error(f"Update execution error: {e}")
        raise

async def get_user_tokens(user_id: str, service_name: str) -> Optional[Dict[str, Any]]:
    """Get OAuth tokens for a user and service"""
    query = """
        SELECT access_token, refresh_token, expires_at, scope, created_at, updated_at
        FROM user_oauth_tokens
        WHERE user_id = ? AND service_name = ? AND deleted = 0
        ORDER BY created_at DESC
        LIMIT 1
    """

    try:
        results = await execute_query(query, (user_id, service_name))
        return results[0] if results else None
    except Exception as e:
        logger.error(f"Error getting tokens for user {user_id}, service {service_name}: {e}")
        return None

async def save_user_tokens(
    user_id: str,
    service_name: str,
    access_token: str,
    refresh_token: Optional[str] = None,
    expires_at: Optional[int] = None,
    scope: Optional[str] = None
) -> bool:
    """Save OAuth tokens for a user and service"""
    query = """
        INSERT INTO user_oauth_tokens
        (user_id, service_name, access_token, refresh_token, expires_at, scope)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id, service_name)
        DO UPDATE SET
            access_token = excluded.access_token,
            refresh_token = excluded.refresh_token,
            expires_at = excluded.expires_at,
            scope = excluded.scope,
            updated_at = CURRENT_TIMESTAMP
    """

    try:
        await execute_insert(query, (user_id, service_name, access_token, refresh_token, expires_at, scope))
        logger.info(f"Successfully saved tokens for user {user_id}, service {service_name}")
        return True
    except Exception as e:
        logger.error(f"Error saving tokens for user {user_id}, service {service_name}: {e}")
        return False

def create_tables_if_not_exist():
    """Create necessary tables if they don't exist"""
    conn = get_db_connection()
    if not conn:
        return False

    try:
        with conn:
            # User OAuth tokens table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_oauth_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    service_name TEXT NOT NULL,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT,
                    expires_at INTEGER,
                    scope TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    deleted BOOLEAN DEFAULT 0,
                    UNIQUE(user_id, service_name)
                )
            """)

            # Tasks table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    due_date TIMESTAMP,
                    priority TEXT DEFAULT 'medium',
                    status TEXT DEFAULT 'todo',
                    project TEXT,
                    tags TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    deleted BOOLEAN DEFAULT 0
                )
            """)

            logger.info("SQLite tables created successfully")
            return True

    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        return False

def close_db_connection():
    """Close the SQLite database connection"""
    global _sqlite_conn
    if _sqlite_conn:
        _sqlite_conn.close()
        logger.info("SQLite database connection closed")
        _sqlite_conn = None

# Initialize database and create tables when module is imported
init_sqlite_db()
create_tables_if_not_exist()
