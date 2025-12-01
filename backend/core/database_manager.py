"""
Database Manager

Handles SQLite database connections and operations using aiosqlite.
Provides async methods for executing queries and managing transactions.
"""

import os
import logging
import json
import aiosqlite
from typing import Optional, List, Dict, Any, Tuple
from core.config import get_config

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self):
        self.config = get_config()
        # Extract path from sqlite:///path/to/db
        db_url = self.config.database.url
        if db_url.startswith("sqlite:///"):
            self.db_path = db_url.replace("sqlite:///", "")
        else:
            self.db_path = "atom_data.db"
            
        self.connection: Optional[aiosqlite.Connection] = None
        
    async def initialize(self):
        """Initialize database connection and schema"""
        try:
            self.connection = await aiosqlite.connect(self.db_path)
            self.connection.row_factory = aiosqlite.Row
            logger.info(f"Connected to database: {self.db_path}")
            
            await self._create_tables()
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
    
    async def _create_tables(self):
        """Create necessary tables if they don't exist"""
        # Workflow Executions Table
        await self.execute("""
            CREATE TABLE IF NOT EXISTS workflow_executions (
                execution_id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                status TEXT NOT NULL,
                input_data TEXT,
                steps TEXT,
                outputs TEXT,
                context TEXT,
                created_at TEXT,
                updated_at TEXT,
                error TEXT
            )
        """)
        logger.info("Database tables initialized")

    async def close(self):
        """Close database connection"""
        if self.connection:
            await self.connection.close()
            self.connection = None
            logger.info("Database connection closed")
    
    async def execute(self, query: str, params: Tuple = ()) -> aiosqlite.Cursor:
        """Execute a query (INSERT, UPDATE, DELETE, CREATE)"""
        if not self.connection:
            await self.initialize()
            
        async with self.connection.execute(query, params) as cursor:
            await self.connection.commit()
            return cursor

    async def fetch_one(self, query: str, params: Tuple = ()) -> Optional[Dict[str, Any]]:
        """Fetch a single row"""
        if not self.connection:
            await self.initialize()
            
        async with self.connection.execute(query, params) as cursor:
            row = await cursor.fetchone()
            if row:
                return dict(row)
            return None

    async def fetch_all(self, query: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """Fetch all rows"""
        if not self.connection:
            await self.initialize()
            
        async with self.connection.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # User operations (placeholder implementations updated to use DB if needed later)
    async def create_user(self, email: str, name: Optional[str] = None):
        return {"id": "user_1", "email": email, "name": name}
    
    async def get_user_by_email(self, email: str):
        return {"id": "user_1", "email": email, "name": "Test User"}

# Global instance
db_manager = DatabaseManager()
