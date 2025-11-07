"""
ATOM HubSpot Database Handler
Database operations for HubSpot OAuth tokens and user data
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
class HubSpotOAuthToken:
    """HubSpot OAuth token data model"""
    user_id: str
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_in: int = 3600
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    hub_id: Optional[str] = None
    hub_domain: Optional[str] = None
    app_id: Optional[str] = None
    scopes: Optional[List[str]] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
        if self.scopes is None:
            self.scopes = []

@dataclass
class HubSpotUserData:
    """HubSpot user/account data model"""
    user_id: str
    hub_id: str
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    portal_id: Optional[str] = None
    account_type: Optional[str] = None
    time_zone: Optional[str] = None
    currency: Optional[str] = None
    super_admin: Optional[bool] = None
    is_super_admin: Optional[bool] = None
    is_primary_user: Optional[bool] = None
    role_id: Optional[int] = None
    role_name: Optional[str] = None
    user_teams: Optional[List[Dict[str, Any]]] = None
    permissions: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
        if self.user_teams is None:
            self.user_teams = []
        if self.permissions is None:
            self.permissions = {}
        if self.metadata is None:
            self.metadata = {}

@dataclass
class HubSpotPortalData:
    """HubSpot portal/company data model"""
    user_id: str
    portal_id: str
    company_name: Optional[str] = None
    domain: Optional[str] = None
    currency: Optional[str] = None
    time_zone: Optional[str] = None
    portal_type: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()

class HubSpotDBHandler:
    """Database handler for HubSpot integration"""
    
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
            logger.info("SQLite database initialized for HubSpot")
        except Exception as e:
            logger.error(f"Failed to initialize SQLite: {e}")
            raise
    
    def _create_sqlite_tables(self):
        """Create SQLite tables for HubSpot data"""
        cursor = self.sqlite_conn.cursor()
        
        # OAuth tokens table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hubspot_oauth_tokens (
                user_id TEXT PRIMARY KEY,
                access_token TEXT NOT NULL,
                refresh_token TEXT,
                token_type TEXT DEFAULT 'Bearer',
                expires_in INTEGER DEFAULT 3600,
                hub_id TEXT,
                hub_domain TEXT,
                app_id TEXT,
                scopes TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # User/account data table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hubspot_user_data (
                user_id TEXT PRIMARY KEY,
                hub_id TEXT NOT NULL,
                user_email TEXT,
                user_name TEXT,
                first_name TEXT,
                last_name TEXT,
                portal_id TEXT,
                account_type TEXT,
                time_zone TEXT,
                currency TEXT,
                super_admin INTEGER,
                is_super_admin INTEGER,
                is_primary_user INTEGER,
                role_id INTEGER,
                role_name TEXT,
                user_teams TEXT DEFAULT '[]',
                permissions TEXT DEFAULT '{}',
                metadata TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Portal/company data table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hubspot_portal_data (
                user_id TEXT PRIMARY KEY,
                portal_id TEXT NOT NULL,
                company_name TEXT,
                domain TEXT,
                currency TEXT,
                time_zone TEXT,
                portal_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.sqlite_conn.commit()
        logger.info("SQLite tables created for HubSpot")
    
    async def save_tokens(self, tokens: HubSpotOAuthToken) -> bool:
        """Save or update OAuth tokens"""
        try:
            if self.db_type == "sqlite":
                return self._save_tokens_sqlite(tokens)
            else:
                return await self._save_tokens_postgresql(tokens)
        except Exception as e:
            logger.error(f"Failed to save tokens: {e}")
            return False
    
    def _save_tokens_sqlite(self, tokens: HubSpotOAuthToken) -> bool:
        """Save tokens to SQLite"""
        try:
            cursor = self.sqlite_conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO hubspot_oauth_tokens 
                (user_id, access_token, refresh_token, token_type, expires_in, 
                 hub_id, hub_domain, app_id, scopes, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tokens.user_id,
                tokens.access_token,
                tokens.refresh_token,
                tokens.token_type,
                tokens.expires_in,
                tokens.hub_id,
                tokens.hub_domain,
                tokens.app_id,
                json.dumps(tokens.scopes) if tokens.scopes else "[]",
                tokens.updated_at if tokens.updated_at else datetime.utcnow()
            ))
            
            self.sqlite_conn.commit()
            logger.info(f"Tokens saved for user {tokens.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save tokens to SQLite: {e}")
            return False
    
    async def _save_tokens_postgresql(self, tokens: HubSpotOAuthToken) -> bool:
        """Save tokens to PostgreSQL"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO hubspot_oauth_tokens 
                    (user_id, access_token, refresh_token, token_type, expires_in, 
                     hub_id, hub_domain, app_id, scopes, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (user_id) 
                    DO UPDATE SET 
                        access_token = $2,
                        refresh_token = $3,
                        token_type = $4,
                        expires_in = $5,
                        hub_id = $6,
                        hub_domain = $7,
                        app_id = $8,
                        scopes = $9,
                        updated_at = $10
                """, (
                    tokens.user_id,
                    tokens.access_token,
                    tokens.refresh_token,
                    tokens.token_type,
                    tokens.expires_in,
                    tokens.hub_id,
                    tokens.hub_domain,
                    tokens.app_id,
                    tokens.scopes,
                    datetime.utcnow()
                ))
                
                logger.info(f"Tokens saved for user {tokens.user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to save tokens to PostgreSQL: {e}")
            return False
    
    async def get_tokens(self, user_id: str) -> Optional[HubSpotOAuthToken]:
        """Get OAuth tokens for user"""
        try:
            if self.db_type == "sqlite":
                return self._get_tokens_sqlite(user_id)
            else:
                return await self._get_tokens_postgresql(user_id)
        except Exception as e:
            logger.error(f"Failed to get tokens: {e}")
            return None
    
    def _get_tokens_sqlite(self, user_id: str) -> Optional[HubSpotOAuthToken]:
        """Get tokens from SQLite"""
        try:
            cursor = self.sqlite_conn.cursor()
            cursor.execute("""
                SELECT * FROM hubspot_oauth_tokens 
                WHERE user_id = ?
            """, (user_id,))
            
            row = cursor.fetchone()
            if row:
                return HubSpotOAuthToken(
                    user_id=row['user_id'],
                    access_token=row['access_token'],
                    refresh_token=row['refresh_token'],
                    token_type=row['token_type'],
                    expires_in=row['expires_in'],
                    created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                    updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
                    hub_id=row['hub_id'],
                    hub_domain=row['hub_domain'],
                    app_id=row['app_id'],
                    scopes=json.loads(row['scopes']) if row['scopes'] else []
                )
            return None
            
        except Exception as e:
            logger.error(f"Failed to get tokens from SQLite: {e}")
            return None
    
    async def _get_tokens_postgresql(self, user_id: str) -> Optional[HubSpotOAuthToken]:
        """Get tokens from PostgreSQL"""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT * FROM hubspot_oauth_tokens 
                    WHERE user_id = $1
                """, user_id)
                
                if row:
                    return HubSpotOAuthToken(
                        user_id=row['user_id'],
                        access_token=row['access_token'],
                        refresh_token=row['refresh_token'],
                        token_type=row['token_type'],
                        expires_in=row['expires_in'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at'],
                        hub_id=row['hub_id'],
                        hub_domain=row['hub_domain'],
                        app_id=row['app_id'],
                        scopes=row['scopes']
                    )
                return None
                
        except Exception as e:
            logger.error(f"Failed to get tokens from PostgreSQL: {e}")
            return None
    
    async def save_user_data(self, user_data: HubSpotUserData) -> bool:
        """Save or update user data"""
        try:
            if self.db_type == "sqlite":
                return self._save_user_data_sqlite(user_data)
            else:
                return await self._save_user_data_postgresql(user_data)
        except Exception as e:
            logger.error(f"Failed to save user data: {e}")
            return False
    
    def _save_user_data_sqlite(self, user_data: HubSpotUserData) -> bool:
        """Save user data to SQLite"""
        try:
            cursor = self.sqlite_conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO hubspot_user_data 
                (user_id, hub_id, user_email, user_name, first_name, last_name, 
                 portal_id, account_type, time_zone, currency, super_admin, 
                 is_super_admin, is_primary_user, role_id, role_name, user_teams, 
                 permissions, metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_data.user_id,
                user_data.hub_id,
                user_data.user_email,
                user_data.user_name,
                user_data.first_name,
                user_data.last_name,
                user_data.portal_id,
                user_data.account_type,
                user_data.time_zone,
                user_data.currency,
                user_data.super_admin,
                user_data.is_super_admin,
                user_data.is_primary_user,
                user_data.role_id,
                user_data.role_name,
                json.dumps(user_data.user_teams) if user_data.user_teams else "[]",
                json.dumps(user_data.permissions) if user_data.permissions else "{}",
                json.dumps(user_data.metadata) if user_data.metadata else "{}",
                user_data.updated_at if user_data.updated_at else datetime.utcnow()
            ))
            
            self.sqlite_conn.commit()
            logger.info(f"User data saved for {user_data.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save user data to SQLite: {e}")
            return False
    
    async def _save_user_data_postgresql(self, user_data: HubSpotUserData) -> bool:
        """Save user data to PostgreSQL"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO hubspot_user_data 
                    (user_id, hub_id, user_email, user_name, first_name, last_name, 
                     portal_id, account_type, time_zone, currency, super_admin, 
                     is_super_admin, is_primary_user, role_id, role_name, user_teams, 
                     permissions, metadata, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)
                    ON CONFLICT (user_id) 
                    DO UPDATE SET 
                        hub_id = $2,
                        user_email = $3,
                        user_name = $4,
                        first_name = $5,
                        last_name = $6,
                        portal_id = $7,
                        account_type = $8,
                        time_zone = $9,
                        currency = $10,
                        super_admin = $11,
                        is_super_admin = $12,
                        is_primary_user = $13,
                        role_id = $14,
                        role_name = $15,
                        user_teams = $16,
                        permissions = $17,
                        metadata = $18,
                        updated_at = $19
                """, (
                    user_data.user_id,
                    user_data.hub_id,
                    user_data.user_email,
                    user_data.user_name,
                    user_data.first_name,
                    user_data.last_name,
                    user_data.portal_id,
                    user_data.account_type,
                    user_data.time_zone,
                    user_data.currency,
                    user_data.super_admin,
                    user_data.is_super_admin,
                    user_data.is_primary_user,
                    user_data.role_id,
                    user_data.role_name,
                    user_data.user_teams,
                    user_data.permissions,
                    user_data.metadata,
                    datetime.utcnow()
                ))
                
                logger.info(f"User data saved for {user_data.user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to save user data to PostgreSQL: {e}")
            return False
    
    async def get_user_data(self, user_id: str) -> Optional[HubSpotUserData]:
        """Get user data for user"""
        try:
            if self.db_type == "sqlite":
                return self._get_user_data_sqlite(user_id)
            else:
                return await self._get_user_data_postgresql(user_id)
        except Exception as e:
            logger.error(f"Failed to get user data: {e}")
            return None
    
    def _get_user_data_sqlite(self, user_id: str) -> Optional[HubSpotUserData]:
        """Get user data from SQLite"""
        try:
            cursor = self.sqlite_conn.cursor()
            cursor.execute("""
                SELECT * FROM hubspot_user_data 
                WHERE user_id = ?
            """, (user_id,))
            
            row = cursor.fetchone()
            if row:
                return HubSpotUserData(
                    user_id=row['user_id'],
                    hub_id=row['hub_id'],
                    user_email=row['user_email'],
                    user_name=row['user_name'],
                    first_name=row['first_name'],
                    last_name=row['last_name'],
                    portal_id=row['portal_id'],
                    account_type=row['account_type'],
                    time_zone=row['time_zone'],
                    currency=row['currency'],
                    super_admin=bool(row['super_admin']) if row['super_admin'] is not None else None,
                    is_super_admin=bool(row['is_super_admin']) if row['is_super_admin'] is not None else None,
                    is_primary_user=bool(row['is_primary_user']) if row['is_primary_user'] is not None else None,
                    role_id=row['role_id'],
                    role_name=row['role_name'],
                    user_teams=json.loads(row['user_teams']) if row['user_teams'] else [],
                    permissions=json.loads(row['permissions']) if row['permissions'] else {},
                    metadata=json.loads(row['metadata']) if row['metadata'] else {},
                    created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                    updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
                )
            return None
            
        except Exception as e:
            logger.error(f"Failed to get user data from SQLite: {e}")
            return None
    
    async def _get_user_data_postgresql(self, user_id: str) -> Optional[HubSpotUserData]:
        """Get user data from PostgreSQL"""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT * FROM hubspot_user_data 
                    WHERE user_id = $1
                """, user_id)
                
                if row:
                    return HubSpotUserData(
                        user_id=row['user_id'],
                        hub_id=row['hub_id'],
                        user_email=row['user_email'],
                        user_name=row['user_name'],
                        first_name=row['first_name'],
                        last_name=row['last_name'],
                        portal_id=row['portal_id'],
                        account_type=row['account_type'],
                        time_zone=row['time_zone'],
                        currency=row['currency'],
                        super_admin=row['super_admin'],
                        is_super_admin=row['is_super_admin'],
                        is_primary_user=row['is_primary_user'],
                        role_id=row['role_id'],
                        role_name=row['role_name'],
                        user_teams=row['user_teams'],
                        permissions=row['permissions'],
                        metadata=row['metadata'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    )
                return None
                
        except Exception as e:
            logger.error(f"Failed to get user data from PostgreSQL: {e}")
            return None
    
    async def save_portal_data(self, portal_data: HubSpotPortalData) -> bool:
        """Save or update portal data"""
        try:
            if self.db_type == "sqlite":
                return self._save_portal_data_sqlite(portal_data)
            else:
                return await self._save_portal_data_postgresql(portal_data)
        except Exception as e:
            logger.error(f"Failed to save portal data: {e}")
            return False
    
    def _save_portal_data_sqlite(self, portal_data: HubSpotPortalData) -> bool:
        """Save portal data to SQLite"""
        try:
            cursor = self.sqlite_conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO hubspot_portal_data 
                (user_id, portal_id, company_name, domain, currency, 
                 time_zone, portal_type, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                portal_data.user_id,
                portal_data.portal_id,
                portal_data.company_name,
                portal_data.domain,
                portal_data.currency,
                portal_data.time_zone,
                portal_data.portal_type,
                portal_data.updated_at if portal_data.updated_at else datetime.utcnow()
            ))
            
            self.sqlite_conn.commit()
            logger.info(f"Portal data saved for {portal_data.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save portal data to SQLite: {e}")
            return False
    
    async def _save_portal_data_postgresql(self, portal_data: HubSpotPortalData) -> bool:
        """Save portal data to PostgreSQL"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO hubspot_portal_data 
                    (user_id, portal_id, company_name, domain, currency, 
                     time_zone, portal_type, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (user_id) 
                    DO UPDATE SET 
                        portal_id = $2,
                        company_name = $3,
                        domain = $4,
                        currency = $5,
                        time_zone = $6,
                        portal_type = $7,
                        updated_at = $8
                """, (
                    portal_data.user_id,
                    portal_data.portal_id,
                    portal_data.company_name,
                    portal_data.domain,
                    portal_data.currency,
                    portal_data.time_zone,
                    portal_data.portal_type,
                    datetime.utcnow()
                ))
                
                logger.info(f"Portal data saved for {portal_data.user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to save portal data to PostgreSQL: {e}")
            return False
    
    async def get_portal_data(self, user_id: str) -> Optional[HubSpotPortalData]:
        """Get portal data for user"""
        try:
            if self.db_type == "sqlite":
                return self._get_portal_data_sqlite(user_id)
            else:
                return await self._get_portal_data_postgresql(user_id)
        except Exception as e:
            logger.error(f"Failed to get portal data: {e}")
            return None
    
    def _get_portal_data_sqlite(self, user_id: str) -> Optional[HubSpotPortalData]:
        """Get portal data from SQLite"""
        try:
            cursor = self.sqlite_conn.cursor()
            cursor.execute("""
                SELECT * FROM hubspot_portal_data 
                WHERE user_id = ?
            """, (user_id,))
            
            row = cursor.fetchone()
            if row:
                return HubSpotPortalData(
                    user_id=row['user_id'],
                    portal_id=row['portal_id'],
                    company_name=row['company_name'],
                    domain=row['domain'],
                    currency=row['currency'],
                    time_zone=row['time_zone'],
                    portal_type=row['portal_type'],
                    created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                    updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
                )
            return None
            
        except Exception as e:
            logger.error(f"Failed to get portal data from SQLite: {e}")
            return None
    
    async def _get_portal_data_postgresql(self, user_id: str) -> Optional[HubSpotPortalData]:
        """Get portal data from PostgreSQL"""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT * FROM hubspot_portal_data 
                    WHERE user_id = $1
                """, user_id)
                
                if row:
                    return HubSpotPortalData(
                        user_id=row['user_id'],
                        portal_id=row['portal_id'],
                        company_name=row['company_name'],
                        domain=row['domain'],
                        currency=row['currency'],
                        time_zone=row['time_zone'],
                        portal_type=row['portal_type'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    )
                return None
                
        except Exception as e:
            logger.error(f"Failed to get portal data from PostgreSQL: {e}")
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
                DELETE FROM hubspot_oauth_tokens 
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
                    DELETE FROM hubspot_oauth_tokens 
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
        """List all users with HubSpot integration"""
        try:
            if self.db_type == "sqlite":
                cursor = self.sqlite_conn.cursor()
                cursor.execute("SELECT DISTINCT user_id FROM hubspot_oauth_tokens")
                rows = cursor.fetchall()
                return [row[0] for row in rows]
            else:
                async with self.db_pool.acquire() as conn:
                    rows = await conn.fetch("SELECT DISTINCT user_id FROM hubspot_oauth_tokens")
                    return [row['user_id'] for row in rows]
        except Exception as e:
            logger.error(f"Failed to list users: {e}")
            return []

# Database factory
def create_hubspot_db_handler(db_pool=None, db_type="postgresql") -> HubSpotDBHandler:
    """Factory function to create HubSpot database handler"""
    return HubSpotDBHandler(db_pool, db_type)