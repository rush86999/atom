"""
ATOM QuickBooks Database Handler
Database operations for QuickBooks OAuth tokens and user data
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
class QuickBooksOAuthToken:
    """QuickBooks OAuth token data model"""
    user_id: str
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_in: int = 3600
    x_refresh_token_expires_in: int = 864000
    realm_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()

@dataclass
class QuickBooksUserData:
    """QuickBooks user/company data model"""
    user_id: str
    realm_id: str
    company_name: Optional[str] = None
    legal_name: Optional[str] = None
    company_type: Optional[str] = None
    domain: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[Dict[str, Any]] = None
    environment: str = "sandbox"
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
        if self.address is None:
            self.address = {}

class QuickBooksDBHandler:
    """Database handler for QuickBooks integration"""
    
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
            logger.info("SQLite database initialized for QuickBooks")
        except Exception as e:
            logger.error(f"Failed to initialize SQLite: {e}")
            raise
    
    def _create_sqlite_tables(self):
        """Create SQLite tables for QuickBooks data"""
        cursor = self.sqlite_conn.cursor()
        
        # OAuth tokens table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quickbooks_oauth_tokens (
                user_id TEXT PRIMARY KEY,
                access_token TEXT NOT NULL,
                refresh_token TEXT,
                token_type TEXT DEFAULT 'Bearer',
                expires_in INTEGER DEFAULT 3600,
                x_refresh_token_expires_in INTEGER DEFAULT 864000,
                realm_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # User/company data table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS quickbooks_user_data (
                user_id TEXT PRIMARY KEY,
                realm_id TEXT NOT NULL,
                company_name TEXT,
                legal_name TEXT,
                company_type TEXT,
                domain TEXT,
                email TEXT,
                phone TEXT,
                website TEXT,
                address_line1 TEXT,
                address_line2 TEXT,
                address_city TEXT,
                address_state TEXT,
                address_postal_code TEXT,
                address_country TEXT,
                environment TEXT DEFAULT 'sandbox',
                metadata TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        self.sqlite_conn.commit()
        logger.info("SQLite tables created for QuickBooks")
    
    async def save_tokens(self, tokens: QuickBooksOAuthToken) -> bool:
        """Save or update OAuth tokens"""
        try:
            if self.db_type == "sqlite":
                return self._save_tokens_sqlite(tokens)
            else:
                return await self._save_tokens_postgresql(tokens)
        except Exception as e:
            logger.error(f"Failed to save tokens: {e}")
            return False
    
    def _save_tokens_sqlite(self, tokens: QuickBooksOAuthToken) -> bool:
        """Save tokens to SQLite"""
        try:
            cursor = self.sqlite_conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO quickbooks_oauth_tokens 
                (user_id, access_token, refresh_token, token_type, expires_in, 
                 x_refresh_token_expires_in, realm_id, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tokens.user_id,
                tokens.access_token,
                tokens.refresh_token,
                tokens.token_type,
                tokens.expires_in,
                tokens.x_refresh_token_expires_in,
                tokens.realm_id,
                tokens.updated_at if tokens.updated_at else datetime.utcnow()
            ))
            
            self.sqlite_conn.commit()
            logger.info(f"Tokens saved for user {tokens.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save tokens to SQLite: {e}")
            return False
    
    async def _save_tokens_postgresql(self, tokens: QuickBooksOAuthToken) -> bool:
        """Save tokens to PostgreSQL"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO quickbooks_oauth_tokens 
                    (user_id, access_token, refresh_token, token_type, expires_in, 
                     x_refresh_token_expires_in, realm_id, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (user_id) 
                    DO UPDATE SET 
                        access_token = $2,
                        refresh_token = $3,
                        token_type = $4,
                        expires_in = $5,
                        x_refresh_token_expires_in = $6,
                        realm_id = $7,
                        updated_at = $8
                """, (
                    tokens.user_id,
                    tokens.access_token,
                    tokens.refresh_token,
                    tokens.token_type,
                    tokens.expires_in,
                    tokens.x_refresh_token_expires_in,
                    tokens.realm_id,
                    datetime.utcnow()
                ))
                
                logger.info(f"Tokens saved for user {tokens.user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to save tokens to PostgreSQL: {e}")
            return False
    
    async def get_tokens(self, user_id: str) -> Optional[QuickBooksOAuthToken]:
        """Get OAuth tokens for user"""
        try:
            if self.db_type == "sqlite":
                return self._get_tokens_sqlite(user_id)
            else:
                return await self._get_tokens_postgresql(user_id)
        except Exception as e:
            logger.error(f"Failed to get tokens: {e}")
            return None
    
    def _get_tokens_sqlite(self, user_id: str) -> Optional[QuickBooksOAuthToken]:
        """Get tokens from SQLite"""
        try:
            cursor = self.sqlite_conn.cursor()
            cursor.execute("""
                SELECT * FROM quickbooks_oauth_tokens 
                WHERE user_id = ?
            """, (user_id,))
            
            row = cursor.fetchone()
            if row:
                return QuickBooksOAuthToken(
                    user_id=row['user_id'],
                    access_token=row['access_token'],
                    refresh_token=row['refresh_token'],
                    token_type=row['token_type'],
                    expires_in=row['expires_in'],
                    x_refresh_token_expires_in=row['x_refresh_token_expires_in'],
                    realm_id=row['realm_id'],
                    created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                    updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
                )
            return None
            
        except Exception as e:
            logger.error(f"Failed to get tokens from SQLite: {e}")
            return None
    
    async def _get_tokens_postgresql(self, user_id: str) -> Optional[QuickBooksOAuthToken]:
        """Get tokens from PostgreSQL"""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT * FROM quickbooks_oauth_tokens 
                    WHERE user_id = $1
                """, user_id)
                
                if row:
                    return QuickBooksOAuthToken(
                        user_id=row['user_id'],
                        access_token=row['access_token'],
                        refresh_token=row['refresh_token'],
                        token_type=row['token_type'],
                        expires_in=row['expires_in'],
                        x_refresh_token_expires_in=row['x_refresh_token_expires_in'],
                        realm_id=row['realm_id'],
                        created_at=row['created_at'],
                        updated_at=row['updated_at']
                    )
                return None
                
        except Exception as e:
            logger.error(f"Failed to get tokens from PostgreSQL: {e}")
            return None
    
    async def save_user_data(self, user_data: QuickBooksUserData) -> bool:
        """Save or update user data"""
        try:
            if self.db_type == "sqlite":
                return self._save_user_data_sqlite(user_data)
            else:
                return await self._save_user_data_postgresql(user_data)
        except Exception as e:
            logger.error(f"Failed to save user data: {e}")
            return False
    
    def _save_user_data_sqlite(self, user_data: QuickBooksUserData) -> bool:
        """Save user data to SQLite"""
        try:
            cursor = self.sqlite_conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO quickbooks_user_data 
                (user_id, realm_id, company_name, legal_name, company_type, domain, 
                 email, phone, website, address_line1, address_line2, address_city, 
                 address_state, address_postal_code, address_country, environment, 
                 metadata, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_data.user_id,
                user_data.realm_id,
                user_data.company_name,
                user_data.legal_name,
                user_data.company_type,
                user_data.domain,
                user_data.email,
                user_data.phone,
                user_data.website,
                user_data.address.get('line1') if user_data.address else None,
                user_data.address.get('line2') if user_data.address else None,
                user_data.address.get('city') if user_data.address else None,
                user_data.address.get('state') if user_data.address else None,
                user_data.address.get('postal_code') if user_data.address else None,
                user_data.address.get('country') if user_data.address else None,
                user_data.environment,
                json.dumps(user_data.metadata),
                datetime.utcnow()
            ))
            
            self.sqlite_conn.commit()
            logger.info(f"User data saved for {user_data.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save user data to SQLite: {e}")
            return False
    
    async def _save_user_data_postgresql(self, user_data: QuickBooksUserData) -> bool:
        """Save user data to PostgreSQL"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO quickbooks_user_data 
                    (user_id, realm_id, company_name, legal_name, company_type, domain, 
                     email, phone, website, address_line1, address_line2, address_city, 
                     address_state, address_postal_code, address_country, environment, 
                     metadata, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
                    ON CONFLICT (user_id) 
                    DO UPDATE SET 
                        realm_id = $2,
                        company_name = $3,
                        legal_name = $4,
                        company_type = $5,
                        domain = $6,
                        email = $7,
                        phone = $8,
                        website = $9,
                        address_line1 = $10,
                        address_line2 = $11,
                        address_city = $12,
                        address_state = $13,
                        address_postal_code = $14,
                        address_country = $15,
                        environment = $16,
                        metadata = $17,
                        updated_at = $18
                """, (
                    user_data.user_id,
                    user_data.realm_id,
                    user_data.company_name,
                    user_data.legal_name,
                    user_data.company_type,
                    user_data.domain,
                    user_data.email,
                    user_data.phone,
                    user_data.website,
                    user_data.address.get('line1') if user_data.address else None,
                    user_data.address.get('line2') if user_data.address else None,
                    user_data.address.get('city') if user_data.address else None,
                    user_data.address.get('state') if user_data.address else None,
                    user_data.address.get('postal_code') if user_data.address else None,
                    user_data.address.get('country') if user_data.address else None,
                    user_data.environment,
                    json.dumps(user_data.metadata),
                    datetime.utcnow()
                ))
                
                logger.info(f"User data saved for {user_data.user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to save user data to PostgreSQL: {e}")
            return False
    
    async def get_user_data(self, user_id: str) -> Optional[QuickBooksUserData]:
        """Get user data for user"""
        try:
            if self.db_type == "sqlite":
                return self._get_user_data_sqlite(user_id)
            else:
                return await self._get_user_data_postgresql(user_id)
        except Exception as e:
            logger.error(f"Failed to get user data: {e}")
            return None
    
    def _get_user_data_sqlite(self, user_id: str) -> Optional[QuickBooksUserData]:
        """Get user data from SQLite"""
        try:
            cursor = self.sqlite_conn.cursor()
            cursor.execute("""
                SELECT * FROM quickbooks_user_data 
                WHERE user_id = ?
            """, (user_id,))
            
            row = cursor.fetchone()
            if row:
                address = {}
                if row['address_line1'] or row['address_city'] or row['address_state']:
                    address = {
                        'line1': row['address_line1'],
                        'line2': row['address_line2'],
                        'city': row['address_city'],
                        'state': row['address_state'],
                        'postal_code': row['address_postal_code'],
                        'country': row['address_country']
                    }
                
                return QuickBooksUserData(
                    user_id=row['user_id'],
                    realm_id=row['realm_id'],
                    company_name=row['company_name'],
                    legal_name=row['legal_name'],
                    company_type=row['company_type'],
                    domain=row['domain'],
                    email=row['email'],
                    phone=row['phone'],
                    website=row['website'],
                    address=address,
                    environment=row['environment'],
                    metadata=json.loads(row['metadata']) if row['metadata'] else {},
                    created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                    updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
                )
            return None
            
        except Exception as e:
            logger.error(f"Failed to get user data from SQLite: {e}")
            return None
    
    async def _get_user_data_postgresql(self, user_id: str) -> Optional[QuickBooksUserData]:
        """Get user data from PostgreSQL"""
        try:
            async with self.db_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT * FROM quickbooks_user_data 
                    WHERE user_id = $1
                """, user_id)
                
                if row:
                    address = {}
                    if row['address_line1'] or row['address_city'] or row['address_state']:
                        address = {
                            'line1': row['address_line1'],
                            'line2': row['address_line2'],
                            'city': row['address_city'],
                            'state': row['address_state'],
                            'postal_code': row['address_postal_code'],
                            'country': row['address_country']
                        }
                    
                    return QuickBooksUserData(
                        user_id=row['user_id'],
                        realm_id=row['realm_id'],
                        company_name=row['company_name'],
                        legal_name=row['legal_name'],
                        company_type=row['company_type'],
                        domain=row['domain'],
                        email=row['email'],
                        phone=row['phone'],
                        website=row['website'],
                        address=address,
                        environment=row['environment'],
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
                DELETE FROM quickbooks_oauth_tokens 
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
                    DELETE FROM quickbooks_oauth_tokens 
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
    
    async def is_refresh_token_expired(self, user_id: str) -> bool:
        """Check if refresh token is expired"""
        tokens = await self.get_tokens(user_id)
        if not tokens or not tokens.created_at:
            return True
        
        # Refresh tokens typically expire after 100 days
        expiry_time = tokens.created_at + timedelta(seconds=tokens.x_refresh_token_expires_in)
        return datetime.utcnow() > expiry_time
    
    async def list_all_users(self) -> List[str]:
        """List all users with QuickBooks integration"""
        try:
            if self.db_type == "sqlite":
                cursor = self.sqlite_conn.cursor()
                cursor.execute("SELECT DISTINCT user_id FROM quickbooks_oauth_tokens")
                rows = cursor.fetchall()
                return [row[0] for row in rows]
            else:
                async with self.db_pool.acquire() as conn:
                    rows = await conn.fetch("SELECT DISTINCT user_id FROM quickbooks_oauth_tokens")
                    return [row['user_id'] for row in rows]
        except Exception as e:
            logger.error(f"Failed to list users: {e}")
            return []

# Database factory
def create_quickbooks_db_handler(db_pool=None, db_type="postgresql") -> QuickBooksDBHandler:
    """Factory function to create QuickBooks database handler"""
    return QuickBooksDBHandler(db_pool, db_type)