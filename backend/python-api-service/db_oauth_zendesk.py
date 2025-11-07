"""
ATOM Zendesk Database Handler
Database operations for Zendesk OAuth tokens and user data
Following ATOM database patterns and security practices
"""

import os
import json
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import asyncpg
import sqlite3
from loguru import logger

@dataclass
class ZendeskOAuthToken:
    """Zendesk OAuth token data model"""
    user_id: str
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_in: int = 3600
    scope: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()

@dataclass
class ZendeskUserData:
    """Zendesk user data model"""
    user_id: str
    zendesk_user_id: Optional[int] = None
    email: Optional[str] = None
    name: Optional[str] = None
    role: Optional[str] = None
    phone: Optional[str] = None
    organization_id: Optional[int] = None
    photo_url: Optional[str] = None
    time_zone: Optional[str] = None
    subdomain: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}

class ZendeskDBHandler:
    """Database handler for Zendesk integration"""
    
    def __init__(self, db_pool=None, db_type="postgresql"):
        self.db_pool = db_pool
        self.db_type = db_type
        self._init_db()
    
    def _init_db(self):
        """Initialize database connection"""
        if self.db_type == "sqlite":
            self._init_sqlite()
        else:
            # PostgreSQL is handled via connection pool
            pass
    
    def _init_sqlite(self):
        """Initialize SQLite database and create tables"""
        try:
            db_path = os.getenv("SQLITE_DB_PATH", "atom.db")
            self.sqlite_conn = sqlite3.connect(db_path, check_same_thread=False)
            self.sqlite_conn.row_factory = sqlite3.Row
            self._create_sqlite_tables()
            logger.info("SQLite database initialized for Zendesk")
        except Exception as e:
            logger.error(f"Failed to initialize SQLite: {e}")
            raise
    
    def _create_sqlite_tables(self):
        """Create SQLite tables for Zendesk data"""
        cursor = self.sqlite_conn.cursor()
        
        # OAuth tokens table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS zendesk_oauth_tokens (
                user_id TEXT PRIMARY KEY,
                access_token TEXT NOT NULL,
                refresh_token TEXT,
                token_type TEXT DEFAULT 'Bearer',
                expires_in INTEGER DEFAULT 3600,
                scope TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # User data table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS zendesk_user_data (
                user_id TEXT PRIMARY KEY,
                zendesk_user_id INTEGER,
                email TEXT,
                name TEXT,
                role TEXT,
                phone TEXT,
                organization_id INTEGER,
                photo_url TEXT,
                time_zone TEXT,
                subdomain TEXT,
                metadata TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.sqlite_conn.commit()
        logger.info("SQLite tables created for Zendesk")
    
    async def save_tokens(self, tokens: ZendeskOAuthToken) -> bool:
        """Save or update OAuth tokens"""
        try:
            if self.db_type == "sqlite":
                return self._save_tokens_sqlite(tokens)
            else:
                return await self._save_tokens_postgresql(tokens)
        except Exception as e:
            logger.error(f"Failed to save tokens: {e}")
            return False
    
    def _save_tokens_sqlite(self, tokens: ZendeskOAuthToken) -> bool:
        """Save tokens to SQLite"""
        try:
            cursor = self.sqlite_conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO zendesk_oauth_tokens 
                (user_id, access_token, refresh_token, token_type, expires_in, scope, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                tokens.user_id,
                tokens.access_token,
                tokens.refresh_token,
                tokens.token_type,
                tokens.expires_in,
                tokens.scope,
                tokens.updated_at if tokens.updated_at else datetime.utcnow()
            ))
            
            self.sqlite_conn.commit()
            logger.info(f"Tokens saved for user {tokens.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save tokens to SQLite: {e}")
            return False
    
    async def _save_tokens_postgresql(self, tokens: ZendeskOAuthToken) -> bool:
        """Save tokens to PostgreSQL"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO zendesk_oauth_tokens 
                    (user_id, access_token, refresh_token, token_type, expires_in, scope, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (user_id) 
                    DO UPDATE SET 
                        access_token = $2,
                        refresh_token = $3,
                        token_type = $4,
                        expires_in = $5,
                        scope = $6,
                        updated_at = $7
                """, (
                    tokens.user_id,
                    tokens.access_token,
                    tokens.refresh_token,
                    tokens.token_type,
                    tokens.expires_in,
                    tokens.scope,
                    datetime.utcnow()
                ))
                
                logger.info(f"Tokens saved for user {tokens.user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to save tokens to PostgreSQL: {e}")
            return False
    
    async def get_tokens(self, user_id: str) -> Optional[ZendeskOAuthToken]:
        """Get OAuth tokens for user"""
        try:
            if self.db_type == "sqlite":
                return self._get_tokens_sqlite(user_id)
            else:
                return await self._get_tokens_postgresql(user_id)
        except Exception as e:
            logger.error(f"Failed to get tokens: {e}")
            return None
    
    def _get_tokens_sqlite(self, user_id: str) -> Optional[ZendeskOAuthToken]:
        """Get tokens from SQLite"""
        try:
            cursor = self.sqlite_conn.cursor()
            cursor.execute("""
                SELECT * FROM zendesk_oauth_tokens 
                WHERE user_id = ?
            """, (user_id,))
            
            row = cursor.fetchone()
            if row:
                return ZendeskOAuthToken(
                    user_id=row['user_id'],
                    access_token=row['access_token'],
                    refresh_token=row['refresh_token'],
                    token_type=row['token_type'],
                    expires_in=row['expires_in'],
                    scope=row['scope'],
                    created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                    updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
                )
            return None
            
        except Exception as e:
            logger.error(f"Failed to get tokens from SQLite: {e}")
            return None
    
    async def _get_tokens_postgresql(self, user_id: str) -> Optional[ZendeskOAuthToken]:
        """Get tokens from PostgreSQL"""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT * FROM zendesk_oauth_tokens 
                    WHERE user_id = $1
                """, user_id)
                
                if row:
                    return ZendeskOAuthToken(
                        user_id=row['user_id'],
                        access_token=row['access_token'],
                        refresh_token=row['refresh_token'],
                        token_type=row['token_type'],
                        expires_in=row['expires_in'],
                        scope=row['scope'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    )
                return None
                
        except Exception as e:
            logger.error(f"Failed to get tokens from PostgreSQL: {e}")
            return None
    
    async def save_user_data(self, user_data: ZendeskUserData) -> bool:
        """Save or update user data"""
        try:
            if self.db_type == "sqlite":
                return self._save_user_data_sqlite(user_data)
            else:
                return await self._save_user_data_postgresql(user_data)
        except Exception as e:
            logger.error(f"Failed to save user data: {e}")
            return False
    
    def _save_user_data_sqlite(self, user_data: ZendeskUserData) -> bool:
        """Save user data to SQLite"""
        try:
            cursor = self.sqlite_conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO zendesk_user_data 
                (user_id, zendesk_user_id, email, name, role, phone, organization_id, 
                 photo_url, time_zone, subdomain, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_data.user_id,
                user_data.zendesk_user_id,
                user_data.email,
                user_data.name,
                user_data.role,
                user_data.phone,
                user_data.organization_id,
                user_data.photo_url,
                user_data.time_zone,
                user_data.subdomain,
                json.dumps(user_data.metadata),
                datetime.utcnow()
            ))
            
            self.sqlite_conn.commit()
            logger.info(f"User data saved for {user_data.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save user data to SQLite: {e}")
            return False
    
    async def _save_user_data_postgresql(self, user_data: ZendeskUserData) -> bool:
        """Save user data to PostgreSQL"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO zendesk_user_data 
                    (user_id, zendesk_user_id, email, name, role, phone, organization_id, 
                     photo_url, time_zone, subdomain, metadata, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    ON CONFLICT (user_id) 
                    DO UPDATE SET 
                        zendesk_user_id = $2,
                        email = $3,
                        name = $4,
                        role = $5,
                        phone = $6,
                        organization_id = $7,
                        photo_url = $8,
                        time_zone = $9,
                        subdomain = $10,
                        metadata = $11,
                        updated_at = $12
                """, (
                    user_data.user_id,
                    user_data.zendesk_user_id,
                    user_data.email,
                    user_data.name,
                    user_data.role,
                    user_data.phone,
                    user_data.organization_id,
                    user_data.photo_url,
                    user_data.time_zone,
                    user_data.subdomain,
                    json.dumps(user_data.metadata),
                    datetime.utcnow()
                ))
                
                logger.info(f"User data saved for {user_data.user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to save user data to PostgreSQL: {e}")
            return False
    
    async def get_user_data(self, user_id: str) -> Optional[ZendeskUserData]:
        """Get user data for user"""
        try:
            if self.db_type == "sqlite":
                return self._get_user_data_sqlite(user_id)
            else:
                return await self._get_user_data_postgresql(user_id)
        except Exception as e:
            logger.error(f"Failed to get user data: {e}")
            return None
    
    def _get_user_data_sqlite(self, user_id: str) -> Optional[ZendeskUserData]:
        """Get user data from SQLite"""
        try:
            cursor = self.sqlite_conn.cursor()
            cursor.execute("""
                SELECT * FROM zendesk_user_data 
                WHERE user_id = ?
            """, (user_id,))
            
            row = cursor.fetchone()
            if row:
                return ZendeskUserData(
                    user_id=row['user_id'],
                    zendesk_user_id=row['zendesk_user_id'],
                    email=row['email'],
                    name=row['name'],
                    role=row['role'],
                    phone=row['phone'],
                    organization_id=row['organization_id'],
                    photo_url=row['photo_url'],
                    time_zone=row['time_zone'],
                    subdomain=row['subdomain'],
                    metadata=json.loads(row['metadata']) if row['metadata'] else {},
                    created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                    updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
                )
            return None
            
        except Exception as e:
            logger.error(f"Failed to get user data from SQLite: {e}")
            return None
    
    async def _get_user_data_postgresql(self, user_id: str) -> Optional[ZendeskUserData]:
        """Get user data from PostgreSQL"""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT * FROM zendesk_user_data 
                    WHERE user_id = $1
                """, user_id)
                
                if row:
                    return ZendeskUserData(
                        user_id=row['user_id'],
                        zendesk_user_id=row['zendesk_user_id'],
                        email=row['email'],
                        name=row['name'],
                        role=row['role'],
                        phone=row['phone'],
                        organization_id=row['organization_id'],
                        photo_url=row['photo_url'],
                        time_zone=row['time_zone'],
                        subdomain=row['subdomain'],
                        metadata=json.loads(row['metadata']) if row['metadata'] else {},
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    )
                return None
                
        except Exception as e:
            logger.error(f"Failed to get user data from PostgreSQL: {e}")
            return None
    
    async def delete_tokens(self, user_id: str) -> bool:
        """Delete OAuth tokens for user"""
        try:
            if self.db_type == "sqlite":
                return self._delete_tokens_sqlite(user_id)
            else:
                return await self._delete_tokens_postgresql(user_id)
        except Exception as e:
            logger.error(f"Failed to delete tokens: {e}")
            return False
    
    def _delete_tokens_sqlite(self, user_id: str) -> bool:
        """Delete tokens from SQLite"""
        try:
            cursor = self.sqlite_conn.cursor()
            cursor.execute("""
                DELETE FROM zendesk_oauth_tokens 
                WHERE user_id = ?
            """, (user_id,))
            
            self.sqlite_conn.commit()
            logger.info(f"Tokens deleted for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete tokens from SQLite: {e}")
            return False
    
    async def _delete_tokens_postgresql(self, user_id: str) -> bool:
        """Delete tokens from PostgreSQL"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    DELETE FROM zendesk_oauth_tokens 
                    WHERE user_id = $1
                """, user_id)
                
                logger.info(f"Tokens deleted for user {user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete tokens from PostgreSQL: {e}")
            return False
    
    async def is_token_expired(self, user_id: str) -> bool:
        """Check if token is expired"""
        tokens = await self.get_tokens(user_id)
        if not tokens:
            return True
        
        if tokens.updated_at:
            expiry_time = tokens.updated_at + timedelta(seconds=tokens.expires_in)
            return datetime.utcnow() > expiry_time
        
        return True
    
    async def list_all_users(self) -> List[str]:
        """List all users with Zendesk integration"""
        try:
            if self.db_type == "sqlite":
                cursor = self.sqlite_conn.cursor()
                cursor.execute("SELECT DISTINCT user_id FROM zendesk_oauth_tokens")
                rows = cursor.fetchall()
                return [row[0] for row in rows]
            else:
                async with self.db_pool.acquire() as conn:
                    rows = await conn.fetch("SELECT DISTINCT user_id FROM zendesk_oauth_tokens")
                    return [row['user_id'] for row in rows]
        except Exception as e:
            logger.error(f"Failed to list users: {e}")
            return []

# Database factory
def create_zendesk_db_handler(db_pool=None, db_type="postgresql") -> ZendeskDBHandler:
    """Factory function to create Zendesk database handler"""
    return ZendeskDBHandler(db_pool, db_type)