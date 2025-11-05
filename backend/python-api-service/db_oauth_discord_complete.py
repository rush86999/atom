"""
Discord OAuth Database Operations
Complete database implementation for Discord token and user data storage
"""

import os
import logging
import json
import asyncio
import psycopg2
import psycopg2.pool
import psycopg2.extras
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List

# Import encryption utilities
try:
    from atom_encryption import encrypt_data, decrypt_data
    ENCRYPTION_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Encryption not available: {e}")
    ENCRYPTION_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)

# Database configuration
DB_URL = os.getenv('DATABASE_URL')
POSTGRES_DB = os.getenv('POSTGRES_DB')
POSTGRES_USER = os.getenv('POSTGRES_USER')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
POSTGRES_HOST = os.getenv('POSTGRES_HOST')
POSTGRES_PORT = os.getenv('POSTGRES_PORT')

class MockDiscordDB:
    """Mock Discord database for testing"""
    
    def __init__(self):
        self.users = {}
        self.tokens = {}
        self.guilds = {}
        self.channels = {}
        self.webhooks = {}
    
    async def save_user(self, user_data: Dict[str, Any]) -> bool:
        """Save user data"""
        try:
            user_id = user_data.get('id')
            if not user_id:
                return False
            
            self.users[user_id] = {
                **user_data,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            return True
        except Exception as e:
            logger.error(f"Mock DB save user error: {e}")
            return False
    
    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user data"""
        try:
            return self.users.get(user_id)
        except Exception as e:
            logger.error(f"Mock DB get user error: {e}")
            return None
    
    async def save_tokens(self, user_id: str, tokens: Dict[str, Any]) -> bool:
        """Save user tokens"""
        try:
            if ENCRYPTION_AVAILABLE:
                access_token = encrypt_data(tokens['access_token'], os.getenv('ATOM_OAUTH_ENCRYPTION_KEY'))
                refresh_token = encrypt_data(tokens['refresh_token'], os.getenv('ATOM_OAUTH_ENCRYPTION_KEY'))
            else:
                access_token = tokens['access_token']
                refresh_token = tokens['refresh_token']
            
            self.tokens[user_id] = {
                'user_id': user_id,
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_type': tokens.get('token_type', 'Bearer'),
                'scope': tokens.get('scope', ''),
                'expires_at': tokens.get('expires_at'),
                'refresh_token_expires_at': tokens.get('refresh_token_expires_at'),
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            return True
        except Exception as e:
            logger.error(f"Mock DB save tokens error: {e}")
            return False
    
    async def get_tokens(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user tokens"""
        try:
            token_data = self.tokens.get(user_id)
            if not token_data:
                return None
            
            # Decrypt tokens
            if ENCRYPTION_AVAILABLE:
                access_token = decrypt_data(token_data['access_token'], os.getenv('ATOM_OAUTH_ENCRYPTION_KEY'))
                refresh_token = decrypt_data(token_data['refresh_token'], os.getenv('ATOM_OAUTH_ENCRYPTION_KEY'))
            else:
                access_token = token_data['access_token']
                refresh_token = token_data['refresh_token']
            
            return {
                'user_id': user_id,
                'access_token': access_token,
                'refresh_token': refresh_token,
                'token_type': token_data.get('token_type', 'Bearer'),
                'scope': token_data.get('scope', ''),
                'expires_at': token_data.get('expires_at'),
                'refresh_token_expires_at': token_data.get('refresh_token_expires_at'),
                'created_at': token_data.get('created_at'),
                'updated_at': token_data.get('updated_at')
            }
        except Exception as e:
            logger.error(f"Mock DB get tokens error: {e}")
            return None
    
    async def delete_tokens(self, user_id: str) -> bool:
        """Delete user tokens"""
        try:
            if user_id in self.tokens:
                del self.tokens[user_id]
            return True
        except Exception as e:
            logger.error(f"Mock DB delete tokens error: {e}")
            return False
    
    async def save_guild_data(self, user_id: str, guild_data: Dict[str, Any]) -> bool:
        """Save guild data"""
        try:
            guild_id = guild_data.get('id')
            if not guild_id:
                return False
            
            self.guilds[f"{user_id}:{guild_id}"] = {
                **guild_data,
                'user_id': user_id,
                'saved_at': datetime.utcnow().isoformat()
            }
            return True
        except Exception as e:
            logger.error(f"Mock DB save guild error: {e}")
            return False
    
    async def get_user_guilds(self, user_id: str) -> List[Dict[str, Any]]:
        """Get user guilds"""
        try:
            user_guilds = []
            for key, guild_data in self.guilds.items():
                if key.startswith(f"{user_id}:"):
                    user_guilds.append(guild_data)
            return user_guilds
        except Exception as e:
            logger.error(f"Mock DB get user guilds error: {e}")
            return []
    
    async def save_webhook(self, webhook_data: Dict[str, Any]) -> bool:
        """Save webhook data"""
        try:
            webhook_id = webhook_data.get('id') or f"webhook_{len(self.webhooks)}"
            self.webhooks[webhook_id] = {
                **webhook_data,
                'id': webhook_id,
                'created_at': datetime.utcnow().isoformat()
            }
            return True
        except Exception as e:
            logger.error(f"Mock DB save webhook error: {e}")
            return False
    
    async def get_webhook(self, webhook_id: str) -> Optional[Dict[str, Any]]:
        """Get webhook data"""
        try:
            return self.webhooks.get(webhook_id)
        except Exception as e:
            logger.error(f"Mock DB get webhook error: {e}")
            return None

class PostgresDiscordDB:
    """PostgreSQL Discord database implementation"""
    
    def __init__(self):
        self.connection_pool = None
        self._init_connection_pool()
    
    def _init_connection_pool(self):
        """Initialize PostgreSQL connection pool"""
        try:
            # Try environment variables first
            if DB_URL:
                self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                    1, 20, DB_URL,
                    cursor_factory=psycopg2.extras.RealDictCursor
                )
            elif all([POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST]):
                self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                    1, 20,
                    database=POSTGRES_DB,
                    user=POSTGRES_USER,
                    password=POSTGRES_PASSWORD,
                    host=POSTGRES_HOST,
                    port=POSTGRES_PORT or 5432,
                    cursor_factory=psycopg2.extras.RealDictCursor
                )
            
            if self.connection_pool:
                self._create_tables()
                
        except Exception as e:
            logger.warning(f"PostgreSQL connection failed: {e}")
            self.connection_pool = None
    
    def _create_tables(self):
        """Create Discord database tables"""
        try:
            with self.connection_pool.getconn() as conn:
                with conn.cursor() as cur:
                    # Discord users table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS discord_users (
                            user_id VARCHAR(50) PRIMARY KEY,
                            username VARCHAR(100),
                            discriminator VARCHAR(10),
                            global_name VARCHAR(100),
                            display_name VARCHAR(100),
                            avatar_hash VARCHAR(100),
                            bot BOOLEAN DEFAULT FALSE,
                            verified BOOLEAN DEFAULT FALSE,
                            email VARCHAR(255),
                            locale VARCHAR(10),
                            premium_type INTEGER DEFAULT 0,
                            flags INTEGER DEFAULT 0,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                        );
                    """)
                    
                    # Discord tokens table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS discord_tokens (
                            user_id VARCHAR(50) PRIMARY KEY,
                            access_token TEXT NOT NULL,
                            refresh_token TEXT,
                            token_type VARCHAR(20) DEFAULT 'Bearer',
                            scope TEXT,
                            expires_at TIMESTAMP WITH TIME ZONE,
                            refresh_token_expires_at TIMESTAMP WITH TIME ZONE,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES discord_users (user_id) ON DELETE CASCADE
                        );
                    """)
                    
                    # Discord guilds table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS discord_guilds (
                            id VARCHAR(50) PRIMARY KEY,
                            user_id VARCHAR(50) NOT NULL,
                            guild_id VARCHAR(50) NOT NULL,
                            name VARCHAR(200) NOT NULL,
                            icon_hash VARCHAR(100),
                            banner_hash VARCHAR(100),
                            owner_id VARCHAR(50),
                            permissions VARCHAR(50),
                            member_count INTEGER,
                            description TEXT,
                            features TEXT[],
                            premium_tier INTEGER DEFAULT 0,
                            joined_at TIMESTAMP WITH TIME ZONE,
                            saved_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES discord_users (user_id) ON DELETE CASCADE
                        );
                    """)
                    
                    # Discord channels table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS discord_channels (
                            id VARCHAR(50) PRIMARY KEY,
                            user_id VARCHAR(50) NOT NULL,
                            channel_id VARCHAR(50) NOT NULL,
                            guild_id VARCHAR(50) NOT NULL,
                            name VARCHAR(200) NOT NULL,
                            type INTEGER NOT NULL,
                            topic TEXT,
                            position INTEGER DEFAULT 0,
                            nsfw BOOLEAN DEFAULT FALSE,
                            rate_limit_per_user INTEGER DEFAULT 0,
                            message_count INTEGER DEFAULT 0,
                            member_count INTEGER DEFAULT 0,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES discord_users (user_id) ON DELETE CASCADE
                        );
                    """)
                    
                    # Discord webhooks table
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS discord_webhooks (
                            id VARCHAR(50) PRIMARY KEY,
                            user_id VARCHAR(50) NOT NULL,
                            webhook_type VARCHAR(50) NOT NULL,
                            channel_id VARCHAR(50),
                            guild_id VARCHAR(50),
                            webhook_url TEXT NOT NULL,
                            secret VARCHAR(255),
                            events TEXT[],
                            active BOOLEAN DEFAULT TRUE,
                            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (user_id) REFERENCES discord_users (user_id) ON DELETE CASCADE
                        );
                    """)
                    
                conn.commit()
                
        except Exception as e:
            logger.error(f"Error creating Discord tables: {e}")
    
    async def save_user(self, user_data: Dict[str, Any]) -> bool:
        """Save or update user data"""
        try:
            with self.connection_pool.getconn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO discord_users 
                        (user_id, username, discriminator, global_name, display_name, 
                         avatar_hash, bot, verified, email, locale, premium_type, flags)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (user_id) 
                        DO UPDATE SET
                            username = EXCLUDED.username,
                            discriminator = EXCLUDED.discriminator,
                            global_name = EXCLUDED.global_name,
                            display_name = EXCLUDED.display_name,
                            avatar_hash = EXCLUDED.avatar_hash,
                            bot = EXCLUDED.bot,
                            verified = EXCLUDED.verified,
                            email = EXCLUDED.email,
                            locale = EXCLUDED.locale,
                            premium_type = EXCLUDED.premium_type,
                            flags = EXCLUDED.flags,
                            updated_at = CURRENT_TIMESTAMP
                    """, (
                        user_data.get('id'),
                        user_data.get('username'),
                        user_data.get('discriminator'),
                        user_data.get('global_name'),
                        user_data.get('display_name'),
                        user_data.get('avatar_hash'),
                        user_data.get('bot', False),
                        user_data.get('verified', False),
                        user_data.get('email'),
                        user_data.get('locale'),
                        user_data.get('premium_type', 0),
                        user_data.get('flags', 0)
                    ))
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"PostgreSQL save Discord user error: {e}")
            return False
    
    async def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user data"""
        try:
            with self.connection_pool.getconn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM discord_users WHERE user_id = %s
                    """, (user_id,))
                    
                    result = cur.fetchone()
                    return dict(result) if result else None
                    
        except Exception as e:
            logger.error(f"PostgreSQL get Discord user error: {e}")
            return None
    
    async def save_tokens(self, user_id: str, tokens: Dict[str, Any]) -> bool:
        """Save or update user tokens"""
        try:
            # Encrypt tokens if encryption available
            if ENCRYPTION_AVAILABLE:
                access_token = encrypt_data(tokens['access_token'], os.getenv('ATOM_OAUTH_ENCRYPTION_KEY'))
                refresh_token = encrypt_data(tokens['refresh_token'], os.getenv('ATOM_OAUTH_ENCRYPTION_KEY'))
            else:
                access_token = tokens['access_token']
                refresh_token = tokens['refresh_token']
            
            with self.connection_pool.getconn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO discord_tokens 
                        (user_id, access_token, refresh_token, token_type, scope, 
                         expires_at, refresh_token_expires_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (user_id) 
                        DO UPDATE SET
                            access_token = EXCLUDED.access_token,
                            refresh_token = EXCLUDED.refresh_token,
                            token_type = EXCLUDED.token_type,
                            scope = EXCLUDED.scope,
                            expires_at = EXCLUDED.expires_at,
                            refresh_token_expires_at = EXCLUDED.refresh_token_expires_at,
                            updated_at = CURRENT_TIMESTAMP
                    """, (
                        user_id,
                        access_token,
                        refresh_token,
                        tokens.get('token_type', 'Bearer'),
                        tokens.get('scope', ''),
                        tokens.get('expires_at'),
                        tokens.get('refresh_token_expires_at')
                    ))
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"PostgreSQL save Discord tokens error: {e}")
            return False
    
    async def get_tokens(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user tokens"""
        try:
            with self.connection_pool.getconn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM discord_tokens WHERE user_id = %s
                    """, (user_id,))
                    
                    result = cur.fetchone()
                    if not result:
                        return None
                    
                    result = dict(result)
                    
                    # Decrypt tokens
                    if ENCRYPTION_AVAILABLE:
                        access_token = decrypt_data(result['access_token'], os.getenv('ATOM_OAUTH_ENCRYPTION_KEY'))
                        refresh_token = decrypt_data(result['refresh_token'], os.getenv('ATOM_OAUTH_ENCRYPTION_KEY'))
                    else:
                        access_token = result['access_token']
                        refresh_token = result['refresh_token']
                    
                    return {
                        'user_id': result['user_id'],
                        'access_token': access_token,
                        'refresh_token': refresh_token,
                        'token_type': result['token_type'],
                        'scope': result['scope'],
                        'expires_at': result['expires_at'],
                        'refresh_token_expires_at': result['refresh_token_expires_at'],
                        'created_at': result['created_at'],
                        'updated_at': result['updated_at']
                    }
                    
        except Exception as e:
            logger.error(f"PostgreSQL get Discord tokens error: {e}")
            return None
    
    async def delete_tokens(self, user_id: str) -> bool:
        """Delete user tokens"""
        try:
            with self.connection_pool.getconn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        DELETE FROM discord_tokens WHERE user_id = %s
                    """, (user_id,))
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"PostgreSQL delete Discord tokens error: {e}")
            return False
    
    async def save_guild_data(self, user_id: str, guild_data: Dict[str, Any]) -> bool:
        """Save guild data"""
        try:
            with self.connection_pool.getconn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO discord_guilds 
                        (id, user_id, guild_id, name, icon_hash, banner_hash, owner_id,
                         permissions, member_count, description, features, premium_tier, joined_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) 
                        DO UPDATE SET
                            name = EXCLUDED.name,
                            icon_hash = EXCLUDED.icon_hash,
                            banner_hash = EXCLUDED.banner_hash,
                            permissions = EXCLUDED.permissions,
                            member_count = EXCLUDED.member_count,
                            description = EXCLUDED.description,
                            features = EXCLUDED.features,
                            premium_tier = EXCLUDED.premium_tier,
                            saved_at = CURRENT_TIMESTAMP
                    """, (
                        f"{user_id}:{guild_data.get('id')}",
                        user_id,
                        guild_data.get('id'),
                        guild_data.get('name'),
                        guild_data.get('icon_hash'),
                        guild_data.get('banner_hash'),
                        guild_data.get('owner_id'),
                        guild_data.get('permissions'),
                        guild_data.get('member_count'),
                        guild_data.get('description'),
                        guild_data.get('features', []),
                        guild_data.get('premium_tier', 0),
                        guild_data.get('joined_at')
                    ))
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"PostgreSQL save Discord guild error: {e}")
            return False
    
    async def get_user_guilds(self, user_id: str) -> List[Dict[str, Any]]:
        """Get user guilds"""
        try:
            with self.connection_pool.getconn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM discord_guilds WHERE user_id = %s ORDER BY saved_at DESC
                    """, (user_id,))
                    
                    results = cur.fetchall()
                    return [dict(result) for result in results]
                    
        except Exception as e:
            logger.error(f"PostgreSQL get user Discord guilds error: {e}")
            return []
    
    async def save_webhook(self, webhook_data: Dict[str, Any]) -> bool:
        """Save webhook data"""
        try:
            with self.connection_pool.getconn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO discord_webhooks 
                        (id, user_id, webhook_type, channel_id, guild_id, webhook_url,
                         secret, events, active)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id) 
                        DO UPDATE SET
                            webhook_type = EXCLUDED.webhook_type,
                            channel_id = EXCLUDED.channel_id,
                            guild_id = EXCLUDED.guild_id,
                            webhook_url = EXCLUDED.webhook_url,
                            secret = EXCLUDED.secret,
                            events = EXCLUDED.events,
                            active = EXCLUDED.active
                    """, (
                        webhook_data.get('id'),
                        webhook_data.get('user_id'),
                        webhook_data.get('webhook_type'),
                        webhook_data.get('channel_id'),
                        webhook_data.get('guild_id'),
                        webhook_data.get('webhook_url'),
                        webhook_data.get('secret'),
                        webhook_data.get('events', []),
                        webhook_data.get('active', True)
                    ))
                conn.commit()
                return True
                
        except Exception as e:
            logger.error(f"PostgreSQL save Discord webhook error: {e}")
            return False
    
    async def get_webhook(self, webhook_id: str) -> Optional[Dict[str, Any]]:
        """Get webhook data"""
        try:
            with self.connection_pool.getconn() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT * FROM discord_webhooks WHERE id = %s
                    """, (webhook_id,))
                    
                    result = cur.fetchone()
                    return dict(result) if result else None
                    
        except Exception as e:
            logger.error(f"PostgreSQL get Discord webhook error: {e}")
            return None

# Initialize database based on availability
def init_discord_db() -> MockDiscordDB or PostgresDiscordDB:
    """Initialize Discord database based on availability"""
    
    # Try PostgreSQL first
    try:
        postgres_db = PostgresDiscordDB()
        if postgres_db.connection_pool:
            logger.info("Discord PostgreSQL database initialized")
            return postgres_db
    except Exception as e:
        logger.warning(f"PostgreSQL Discord DB not available: {e}")
    
    # Fall back to mock database
    logger.info("Discord Mock database initialized")
    return MockDiscordDB()

# Initialize database instance
discord_db = init_discord_db()

# Database operation functions
async def save_discord_user(conn, user_data: Dict[str, Any]) -> bool:
    """Save Discord user data"""
    return await discord_db.save_user(user_data)

async def get_discord_user(conn, user_id: str) -> Optional[Dict[str, Any]]:
    """Get Discord user data"""
    return await discord_db.get_user(user_id)

async def save_discord_tokens(conn, user_id: str, tokens: Dict[str, Any]) -> bool:
    """Save Discord tokens"""
    return await discord_db.save_tokens(user_id, tokens)

async def get_discord_tokens(conn, user_id: str) -> Optional[Dict[str, Any]]:
    """Get Discord tokens"""
    return await discord_db.get_tokens(user_id)

async def delete_discord_tokens(conn, user_id: str) -> bool:
    """Delete Discord tokens"""
    return await discord_db.delete_tokens(user_id)

async def save_user_discord_guilds(conn, user_id: str, guilds: List[Dict[str, Any]]) -> bool:
    """Save user Discord guilds"""
    try:
        for guild in guilds:
            await discord_db.save_guild_data(user_id, guild)
        return True
    except Exception as e:
        logger.error(f"Save Discord guilds error: {e}")
        return False

async def get_user_discord_guilds(conn, user_id: str) -> List[Dict[str, Any]]:
    """Get user Discord guilds"""
    return await discord_db.get_user_guilds(user_id)

async def save_discord_webhook(conn, webhook_data: Dict[str, Any]) -> bool:
    """Save Discord webhook"""
    return await discord_db.save_webhook(webhook_data)

async def get_discord_webhook(conn, webhook_id: str) -> Optional[Dict[str, Any]]:
    """Get Discord webhook"""
    return await discord_db.get_webhook(webhook_id)

async def is_discord_token_valid(conn, user_id: str) -> bool:
    """Check if Discord token is valid"""
    tokens = await get_discord_tokens(conn, user_id)
    if not tokens:
        return False
    
    # Check if token is expired
    expires_at = tokens.get('expires_at')
    if expires_at:
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        
        # Add 5 minute buffer
        if expires_at < datetime.utcnow() - timedelta(minutes=5):
            return False
    
    return True

async def refresh_discord_token_if_needed(conn, user_id: str, refresh_func) -> Optional[Dict[str, Any]]:
    """Refresh Discord token if needed"""
    tokens = await get_discord_tokens(conn, user_id)
    if not tokens:
        return None
    
    # Check if token needs refresh
    expires_at = tokens.get('expires_at')
    if expires_at:
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        
        # Refresh if expires within 30 minutes
        if expires_at < datetime.utcnow() + timedelta(minutes=30):
            refresh_token = tokens.get('refresh_token')
            if refresh_token:
                try:
                    new_tokens = await refresh_func(refresh_token)
                    if new_tokens and new_tokens.get('access_token'):
                        await save_discord_tokens(conn, user_id, new_tokens)
                        return new_tokens
                except Exception as e:
                    logger.error(f"Discord token refresh error: {e}")
    
    return tokens

# Export functions
__all__ = [
    'discord_db',
    'save_discord_user',
    'get_discord_user',
    'save_discord_tokens',
    'get_discord_tokens',
    'delete_discord_tokens',
    'save_user_discord_guilds',
    'get_user_discord_guilds',
    'save_discord_webhook',
    'get_discord_webhook',
    'is_discord_token_valid',
    'refresh_discord_token_if_needed'
]