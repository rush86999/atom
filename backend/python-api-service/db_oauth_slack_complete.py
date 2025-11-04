"""
Slack OAuth Database Operations
Handles storage and retrieval of Slack OAuth tokens and user data
"""

import os
import logging
import asyncio
import json
import base64
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
import asyncpg
import sqlite3
import aiosqlite

# Import encryption utilities
try:
    from atom_encryption import decrypt_data, encrypt_data
    ENCRYPTION_AVAILABLE = True
except ImportError:
    ENCRYPTION_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("atom_encryption not available, tokens will be stored in plaintext")

logger = logging.getLogger(__name__)

# Database configuration
DB_TYPE = os.getenv('ATOM_DB_TYPE', 'sqlite')
POSTGRES_URL = os.getenv('ATOM_POSTGRES_URL')
ATOM_OAUTH_ENCRYPTION_KEY = os.getenv('ATOM_OAUTH_ENCRYPTION_KEY')

# Slack OAuth configuration
SLACK_CLIENT_ID = os.getenv('SLACK_CLIENT_ID', 'mock_slack_client_id')
SLACK_CLIENT_SECRET = os.getenv('SLACK_CLIENT_SECRET', 'mock_slack_client_secret')
SLACK_REDIRECT_URI = os.getenv('SLACK_REDIRECT_URI', 'http://localhost:3000/integrations/slack/callback')
SLACK_SCOPE = os.getenv('SLACK_SCOPE', 'channels:read channels:write chat:write chat:write.public files:read files:write users:read team:read')

# Mock database fallback
MOCK_DB = {
    'slack_tokens': {},
    'slack_users': {},
    'slack_channels': {},
    'slack_messages': {},
    'slack_files': {},
    'slack_webhooks': {}
}

# Initialize SQLite database if needed
def init_sqlite_db():
    """Initialize SQLite database with Slack tables"""
    try:
        db_path = os.getenv('ATOM_SQLITE_PATH', 'data/atom_development.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Slack tokens table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS slack_oauth_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                access_token TEXT NOT NULL,
                token_type TEXT DEFAULT 'bot',
                scope TEXT,
                expires_at TIMESTAMP,
                refresh_token TEXT,
                team_id TEXT,
                team_name TEXT,
                bot_user_id TEXT,
                app_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id)
            )
        ''')
        
        # Slack users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS slack_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                slack_user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                email TEXT,
                real_name TEXT,
                display_name TEXT,
                image_24 TEXT,
                image_32 TEXT,
                image_48 TEXT,
                image_72 TEXT,
                image_192 TEXT,
                image_512 TEXT,
                title TEXT,
                team_id TEXT,
                is_bot BOOLEAN DEFAULT FALSE,
                is_admin BOOLEAN DEFAULT FALSE,
                is_owner BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id)
            )
        ''')
        
        # Slack channels cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS slack_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                name TEXT NOT NULL,
                is_channel BOOLEAN DEFAULT TRUE,
                is_group BOOLEAN DEFAULT FALSE,
                is_im BOOLEAN DEFAULT FALSE,
                is_mpim BOOLEAN DEFAULT FALSE,
                is_private BOOLEAN DEFAULT FALSE,
                is_archived BOOLEAN DEFAULT FALSE,
                is_general BOOLEAN DEFAULT FALSE,
                topic TEXT,
                purpose TEXT,
                num_members INTEGER DEFAULT 0,
                created_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, channel_id)
            )
        ''')
        
        # Slack messages cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS slack_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                user TEXT,
                text TEXT,
                thread_ts TEXT,
                timestamp TEXT NOT NULL,
                message_type TEXT DEFAULT 'message',
                subtype TEXT,
                reactions TEXT,
                attachments TEXT,
                files TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, message_id)
            )
        ''')
        
        # Slack files cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS slack_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                file_id TEXT NOT NULL,
                name TEXT NOT NULL,
                title TEXT,
                mimetype TEXT,
                filetype TEXT,
                size INTEGER DEFAULT 0,
                url_private TEXT,
                url_private_download TEXT,
                user TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, file_id)
            )
        ''')
        
        # Slack webhooks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS slack_webhooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                webhook_id TEXT NOT NULL,
                team_id TEXT,
                channel_id TEXT,
                configuration_url TEXT,
                url TEXT,
                name TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, webhook_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Slack SQLite database initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize Slack SQLite database: {e}")
        raise

# Initialize database
if DB_TYPE == 'sqlite':
    init_sqlite_db()

async def save_tokens(db_conn_pool, user_id: str, token_data: Dict[str, Any]) -> bool:
    """
    Save Slack OAuth tokens for user
    """
    try:
        if DB_TYPE == 'postgres' and db_conn_pool:
            return await _save_tokens_postgres(db_conn_pool, user_id, token_data)
        elif DB_TYPE == 'sqlite':
            return await _save_tokens_sqlite(user_id, token_data)
        else:
            # Mock fallback
            MOCK_DB['slack_tokens'][user_id] = {
                **token_data,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            return True
    except Exception as e:
        logger.error(f"Error saving Slack tokens for user {user_id}: {e}")
        return False

async def _save_tokens_postgres(db_conn_pool, user_id: str, token_data: Dict[str, Any]) -> bool:
    """Save tokens to PostgreSQL"""
    try:
        # Encrypt sensitive data
        access_token = token_data.get('access_token', '')
        refresh_token = token_data.get('refresh_token', '')
        
        if ENCRYPTION_AVAILABLE:
            access_token = encrypt_data(access_token, ATOM_OAUTH_ENCRYPTION_KEY)
            refresh_token = encrypt_data(refresh_token, ATOM_OAUTH_ENCRYPTION_KEY)
        
        async with db_conn_pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO slack_oauth_tokens 
                (user_id, access_token, token_type, scope, expires_at, refresh_token,
                 team_id, team_name, bot_user_id, app_id)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (user_id) 
                DO UPDATE SET 
                access_token = $2, token_type = $3, scope = $4, expires_at = $5, 
                refresh_token = $6, team_id = $7, team_name = $8, bot_user_id = $9,
                app_id = $10, updated_at = CURRENT_TIMESTAMP
            ''', (
                user_id,
                access_token,
                token_data.get('token_type', 'bot'),
                token_data.get('scope'),
                token_data.get('expires_at'),
                refresh_token,
                token_data.get('team_id'),
                token_data.get('team_name'),
                token_data.get('bot_user_id'),
                token_data.get('app_id')
            ))
        
        logger.info(f"Slack tokens saved for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving Slack tokens to PostgreSQL: {e}")
        return False

async def _save_tokens_sqlite(user_id: str, token_data: Dict[str, Any]) -> bool:
    """Save tokens to SQLite"""
    try:
        # Encrypt sensitive data
        access_token = token_data.get('access_token', '')
        refresh_token = token_data.get('refresh_token', '')
        
        if ENCRYPTION_AVAILABLE:
            access_token = encrypt_data(access_token, ATOM_OAUTH_ENCRYPTION_KEY)
            refresh_token = encrypt_data(refresh_token, ATOM_OAUTH_ENCRYPTION_KEY)
        
        db_path = os.getenv('ATOM_SQLITE_PATH', 'data/atom_development.db')
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute('''
                INSERT OR REPLACE INTO slack_oauth_tokens 
                (user_id, access_token, token_type, scope, expires_at, refresh_token,
                 team_id, team_name, bot_user_id, app_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                access_token,
                token_data.get('token_type', 'bot'),
                token_data.get('scope'),
                token_data.get('expires_at'),
                refresh_token,
                token_data.get('team_id'),
                token_data.get('team_name'),
                token_data.get('bot_user_id'),
                token_data.get('app_id')
            ))
            await conn.commit()
        
        logger.info(f"Slack tokens saved for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving Slack tokens to SQLite: {e}")
        return False

async def get_tokens(db_conn_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get Slack OAuth tokens for user
    """
    try:
        if DB_TYPE == 'postgres' and db_conn_pool:
            return await _get_tokens_postgres(db_conn_pool, user_id)
        elif DB_TYPE == 'sqlite':
            return await _get_tokens_sqlite(user_id)
        else:
            # Mock fallback
            return MOCK_DB['slack_tokens'].get(user_id)
    except Exception as e:
        logger.error(f"Error getting Slack tokens for user {user_id}: {e}")
        return None

async def _get_tokens_postgres(db_conn_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Get tokens from PostgreSQL"""
    try:
        async with db_conn_pool.acquire() as conn:
            row = await conn.fetchrow('''
                SELECT access_token, token_type, scope, expires_at, refresh_token,
                       team_id, team_name, bot_user_id, app_id,
                       created_at, updated_at
                FROM slack_oauth_tokens 
                WHERE user_id = $1
            ''', user_id)
            
            if not row:
                return None
            
            # Decrypt sensitive data
            access_token = row['access_token']
            refresh_token = row['refresh_token']
            
            if ENCRYPTION_AVAILABLE:
                access_token = decrypt_data(access_token, ATOM_OAUTH_ENCRYPTION_KEY)
                refresh_token = decrypt_data(refresh_token, ATOM_OAUTH_ENCRYPTION_KEY)
            
            return {
                'access_token': access_token,
                'token_type': row['token_type'],
                'scope': row['scope'],
                'expires_at': row['expires_at'],
                'refresh_token': refresh_token,
                'team_id': row['team_id'],
                'team_name': row['team_name'],
                'bot_user_id': row['bot_user_id'],
                'app_id': row['app_id'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }
        
    except Exception as e:
        logger.error(f"Error getting Slack tokens from PostgreSQL: {e}")
        return None

async def _get_tokens_sqlite(user_id: str) -> Optional[Dict[str, Any]]:
    """Get tokens from SQLite"""
    try:
        db_path = os.getenv('ATOM_SQLITE_PATH', 'data/atom_development.db')
        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute('''
                SELECT access_token, token_type, scope, expires_at, refresh_token,
                       team_id, team_name, bot_user_id, app_id,
                       created_at, updated_at
                FROM slack_oauth_tokens 
                WHERE user_id = ?
            ''', (user_id,))
            row = await cursor.fetchone()
            
            if not row:
                return None
            
            # Decrypt sensitive data
            access_token = row['access_token']
            refresh_token = row['refresh_token']
            
            if ENCRYPTION_AVAILABLE:
                access_token = decrypt_data(access_token, ATOM_OAUTH_ENCRYPTION_KEY)
                refresh_token = decrypt_data(refresh_token, ATOM_OAUTH_ENCRYPTION_KEY)
            
            return {
                'access_token': access_token,
                'token_type': row['token_type'],
                'scope': row['scope'],
                'expires_at': row['expires_at'],
                'refresh_token': refresh_token,
                'team_id': row['team_id'],
                'team_name': row['team_name'],
                'bot_user_id': row['bot_user_id'],
                'app_id': row['app_id'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }
        
    except Exception as e:
        logger.error(f"Error getting Slack tokens from SQLite: {e}")
        return None

async def delete_tokens(db_conn_pool, user_id: str) -> bool:
    """
    Delete Slack OAuth tokens for user
    """
    try:
        if DB_TYPE == 'postgres' and db_conn_pool:
            async with db_conn_pool.acquire() as conn:
                result = await conn.execute(
                    'DELETE FROM slack_oauth_tokens WHERE user_id = $1',
                    user_id
                )
                return result != 'DELETE 0'
        
        elif DB_TYPE == 'sqlite':
            db_path = os.getenv('ATOM_SQLITE_PATH', 'data/atom_development.db')
            async with aiosqlite.connect(db_path) as conn:
                await conn.execute(
                    'DELETE FROM slack_oauth_tokens WHERE user_id = ?',
                    (user_id,)
                )
                await conn.commit()
                return True
        
        else:
            # Mock fallback
            if user_id in MOCK_DB['slack_tokens']:
                del MOCK_DB['slack_tokens'][user_id]
                return True
            return False
        
    except Exception as e:
        logger.error(f"Error deleting Slack tokens for user {user_id}: {e}")
        return False

async def save_user_slack_tokens(db_conn_pool, user_id: str, token_data: Dict[str, Any]) -> bool:
    """
    Save Slack tokens and user data (combined operation)
    """
    try:
        # Save tokens
        tokens_saved = await save_tokens(db_conn_pool, user_id, token_data)
        
        # Extract and save user info if available
        if 'user_info' in token_data:
            user_info = token_data['user_info']
            user_saved = await save_slack_user(db_conn_pool, user_id, user_info)
        else:
            user_saved = True
        
        return tokens_saved and user_saved
        
    except Exception as e:
        logger.error(f"Error saving Slack user tokens for user {user_id}: {e}")
        return False

async def get_user_slack_tokens(db_conn_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get Slack tokens with user info
    """
    try:
        # Get tokens
        tokens = await get_tokens(db_conn_pool, user_id)
        if not tokens:
            return None
        
        # Get user info
        user_info = await get_slack_user(db_conn_pool, user_id)
        
        return {
            **tokens,
            'user_info': user_info
        }
        
    except Exception as e:
        logger.error(f"Error getting user Slack tokens for user {user_id}: {e}")
        return None

async def delete_user_slack_tokens(db_conn_pool, user_id: str) -> bool:
    """
    Delete Slack tokens and user data (combined operation)
    """
    try:
        # Delete tokens
        tokens_deleted = await delete_tokens(db_conn_pool, user_id)
        
        # Delete user info
        user_deleted = await delete_slack_user(db_conn_pool, user_id)
        
        return tokens_deleted or user_deleted
        
    except Exception as e:
        logger.error(f"Error deleting user Slack tokens for user {user_id}: {e}")
        return False

# Slack user data operations
async def save_slack_user(db_conn_pool, user_id: str, user_info: Dict[str, Any]) -> bool:
    """Save Slack user information"""
    try:
        if DB_TYPE == 'postgres' and db_conn_pool:
            return await _save_slack_user_postgres(db_conn_pool, user_id, user_info)
        elif DB_TYPE == 'sqlite':
            return await _save_slack_user_sqlite(user_id, user_info)
        else:
            # Mock fallback
            MOCK_DB['slack_users'][user_id] = {
                **user_info,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            return True
    except Exception as e:
        logger.error(f"Error saving Slack user info for user {user_id}: {e}")
        return False

async def _save_slack_user_postgres(db_conn_pool, user_id: str, user_info: Dict[str, Any]) -> bool:
    """Save Slack user info to PostgreSQL"""
    try:
        async with db_conn_pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO slack_users 
                (user_id, slack_user_id, name, email, real_name, display_name,
                 image_24, image_32, image_48, image_72, image_192, image_512,
                 title, team_id, is_bot, is_admin, is_owner)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                        $13, $14, $15, $16, $17, $18)
                ON CONFLICT (user_id) 
                DO UPDATE SET 
                slack_user_id = $2, name = $3, email = $4, real_name = $5,
                display_name = $6, image_24 = $7, image_32 = $8, image_48 = $9,
                image_72 = $10, image_192 = $11, image_512 = $12, title = $13,
                team_id = $14, is_bot = $15, is_admin = $16, is_owner = $17,
                updated_at = CURRENT_TIMESTAMP
            ''', (
                user_id,
                user_info.get('id'),
                user_info.get('name'),
                user_info.get('email'),
                user_info.get('real_name'),
                user_info.get('display_name'),
                user_info.get('image_24'),
                user_info.get('image_32'),
                user_info.get('image_48'),
                user_info.get('image_72'),
                user_info.get('image_192'),
                user_info.get('image_512'),
                user_info.get('title'),
                user_info.get('team', {}).get('id'),
                user_info.get('is_bot', False),
                user_info.get('is_admin', False),
                user_info.get('is_owner', False)
            ))
        
        logger.info(f"Slack user info saved for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving Slack user info to PostgreSQL: {e}")
        return False

async def _save_slack_user_sqlite(user_id: str, user_info: Dict[str, Any]) -> bool:
    """Save Slack user info to SQLite"""
    try:
        db_path = os.getenv('ATOM_SQLITE_PATH', 'data/atom_development.db')
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute('''
                INSERT OR REPLACE INTO slack_users 
                (user_id, slack_user_id, name, email, real_name, display_name,
                 image_24, image_32, image_48, image_72, image_192, image_512,
                 title, team_id, is_bot, is_admin, is_owner)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                user_info.get('id'),
                user_info.get('name'),
                user_info.get('email'),
                user_info.get('real_name'),
                user_info.get('display_name'),
                user_info.get('image_24'),
                user_info.get('image_32'),
                user_info.get('image_48'),
                user_info.get('image_72'),
                user_info.get('image_192'),
                user_info.get('image_512'),
                user_info.get('title'),
                user_info.get('team', {}).get('id'),
                user_info.get('is_bot', False),
                user_info.get('is_admin', False),
                user_info.get('is_owner', False)
            ))
            await conn.commit()
        
        logger.info(f"Slack user info saved for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving Slack user info to SQLite: {e}")
        return False

async def get_slack_user(db_conn_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Get Slack user information"""
    try:
        if DB_TYPE == 'postgres' and db_conn_pool:
            return await _get_slack_user_postgres(db_conn_pool, user_id)
        elif DB_TYPE == 'sqlite':
            return await _get_slack_user_sqlite(user_id)
        else:
            # Mock fallback
            return MOCK_DB['slack_users'].get(user_id)
    except Exception as e:
        logger.error(f"Error getting Slack user info for user {user_id}: {e}")
        return None

async def _get_slack_user_postgres(db_conn_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Get Slack user info from PostgreSQL"""
    try:
        async with db_conn_pool.acquire() as conn:
            row = await conn.fetchrow('''
                SELECT slack_user_id, name, email, real_name, display_name,
                       image_24, image_32, image_48, image_72, image_192, image_512,
                       title, team_id, is_bot, is_admin, is_owner,
                       created_at, updated_at
                FROM slack_users 
                WHERE user_id = $1
            ''', user_id)
            
            if not row:
                return None
            
            return {
                'id': row['slack_user_id'],
                'name': row['name'],
                'email': row['email'],
                'real_name': row['real_name'],
                'display_name': row['display_name'],
                'image_24': row['image_24'],
                'image_32': row['image_32'],
                'image_48': row['image_48'],
                'image_72': row['image_72'],
                'image_192': row['image_192'],
                'image_512': row['image_512'],
                'title': row['title'],
                'team_id': row['team_id'],
                'is_bot': row['is_bot'],
                'is_admin': row['is_admin'],
                'is_owner': row['is_owner'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }
        
    except Exception as e:
        logger.error(f"Error getting Slack user info from PostgreSQL: {e}")
        return None

async def _get_slack_user_sqlite(user_id: str) -> Optional[Dict[str, Any]]:
    """Get Slack user info from SQLite"""
    try:
        db_path = os.getenv('ATOM_SQLITE_PATH', 'data/atom_development.db')
        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute('''
                SELECT slack_user_id, name, email, real_name, display_name,
                       image_24, image_32, image_48, image_72, image_192, image_512,
                       title, team_id, is_bot, is_admin, is_owner,
                       created_at, updated_at
                FROM slack_users 
                WHERE user_id = ?
            ''', (user_id,))
            row = await cursor.fetchone()
            
            if not row:
                return None
            
            return {
                'id': row['slack_user_id'],
                'name': row['name'],
                'email': row['email'],
                'real_name': row['real_name'],
                'display_name': row['display_name'],
                'image_24': row['image_24'],
                'image_32': row['image_32'],
                'image_48': row['image_48'],
                'image_72': row['image_72'],
                'image_192': row['image_192'],
                'image_512': row['image_512'],
                'title': row['title'],
                'team_id': row['team_id'],
                'is_bot': row['is_bot'],
                'is_admin': row['is_admin'],
                'is_owner': row['is_owner'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }
        
    except Exception as e:
        logger.error(f"Error getting Slack user info from SQLite: {e}")
        return None

async def delete_slack_user(db_conn_pool, user_id: str) -> bool:
    """Delete Slack user information"""
    try:
        if DB_TYPE == 'postgres' and db_conn_pool:
            async with db_conn_pool.acquire() as conn:
                result = await conn.execute(
                    'DELETE FROM slack_users WHERE user_id = $1',
                    user_id
                )
                return result != 'DELETE 0'
        
        elif DB_TYPE == 'sqlite':
            db_path = os.getenv('ATOM_SQLITE_PATH', 'data/atom_development.db')
            async with aiosqlite.connect(db_path) as conn:
                await conn.execute(
                    'DELETE FROM slack_users WHERE user_id = ?',
                    (user_id,)
                )
                await conn.commit()
                return True
        
        else:
            # Mock fallback
            if user_id in MOCK_DB['slack_users']:
                del MOCK_DB['slack_users'][user_id]
                return True
            return False
        
    except Exception as e:
        logger.error(f"Error deleting Slack user info for user {user_id}: {e}")
        return False

# Helper functions for Slack-specific operations
async def refresh_slack_tokens(db_conn_pool, user_id: str, new_token_data: Dict[str, Any]) -> bool:
    """Refresh Slack tokens with new access token"""
    try:
        # Get existing tokens
        existing_tokens = await get_tokens(db_conn_pool, user_id)
        if not existing_tokens:
            return False
        
        # Update with new token data
        updated_token_data = {
            **existing_tokens,
            **new_token_data,
            'updated_at': datetime.utcnow().isoformat()
        }
        
        return await save_tokens(db_conn_pool, user_id, updated_token_data)
        
    except Exception as e:
        logger.error(f"Error refreshing Slack tokens for user {user_id}: {e}")
        return False

async def get_slack_user_channels(db_conn_pool, user_id: str) -> List[Dict[str, Any]]:
    """Get cached channels for Slack user"""
    try:
        if DB_TYPE == 'postgres' and db_conn_pool:
            async with db_conn_pool.acquire() as conn:
                rows = await conn.fetch('''
                    SELECT channel_id, name, is_channel, is_group, is_im, is_mpim,
                           is_private, is_archived, is_general, topic, purpose,
                           num_members, created_at, updated_at
                    FROM slack_channels 
                    WHERE user_id = $1
                    ORDER BY name
                ''', user_id)
                
                return [dict(row) for row in rows]
        
        elif DB_TYPE == 'sqlite':
            db_path = os.getenv('ATOM_SQLITE_PATH', 'data/atom_development.db')
            async with aiosqlite.connect(db_path) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute('''
                    SELECT channel_id, name, is_channel, is_group, is_im, is_mpim,
                           is_private, is_archived, is_general, topic, purpose,
                           num_members, created_at, updated_at
                    FROM slack_channels 
                    WHERE user_id = ?
                    ORDER BY name
                ''', (user_id,))
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        
        else:
            # Mock fallback
            return [channel for channel in MOCK_DB['slack_channels'].values() 
                   if channel.get('user_id') == user_id]
        
    except Exception as e:
        logger.error(f"Error getting cached Slack channels for user {user_id}: {e}")
        return []

async def save_slack_channels(db_conn_pool, user_id: str, channels: List[Dict[str, Any]]) -> bool:
    """Save Slack channels cache"""
    try:
        if not channels:
            return True
        
        if DB_TYPE == 'postgres' and db_conn_pool:
            async with db_conn_pool.acquire() as conn:
                for channel in channels:
                    await conn.execute('''
                        INSERT INTO slack_channels 
                        (user_id, channel_id, name, is_channel, is_group, is_im,
                         is_mpim, is_private, is_archived, is_general, topic,
                         purpose, num_members)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                        ON CONFLICT (user_id, channel_id) 
                        DO UPDATE SET 
                        name = $3, is_channel = $4, is_group = $5, is_im = $6,
                        is_mpim = $7, is_private = $8, is_archived = $9,
                        is_general = $10, topic = $11, purpose = $12,
                        num_members = $13, updated_at = CURRENT_TIMESTAMP
                    ''', (
                        user_id,
                        channel.get('id'),
                        channel.get('name'),
                        channel.get('is_channel', True),
                        channel.get('is_group', False),
                        channel.get('is_im', False),
                        channel.get('is_mpim', False),
                        channel.get('is_private', False),
                        channel.get('is_archived', False),
                        channel.get('is_general', False),
                        json.dumps(channel.get('topic', {})),
                        json.dumps(channel.get('purpose', {})),
                        channel.get('num_members', 0)
                    ))
        
        elif DB_TYPE == 'sqlite':
            db_path = os.getenv('ATOM_SQLITE_PATH', 'data/atom_development.db')
            async with aiosqlite.connect(db_path) as conn:
                for channel in channels:
                    await conn.execute('''
                        INSERT OR REPLACE INTO slack_channels 
                        (user_id, channel_id, name, is_channel, is_group, is_im,
                         is_mpim, is_private, is_archived, is_general, topic,
                         purpose, num_members)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        user_id,
                        channel.get('id'),
                        channel.get('name'),
                        channel.get('is_channel', True),
                        channel.get('is_group', False),
                        channel.get('is_im', False),
                        channel.get('is_mpim', False),
                        channel.get('is_private', False),
                        channel.get('is_archived', False),
                        channel.get('is_general', False),
                        json.dumps(channel.get('topic', {})),
                        json.dumps(channel.get('purpose', {})),
                        channel.get('num_members', 0)
                    ))
                await conn.commit()
        
        else:
            # Mock fallback
            for channel in channels:
                channel_key = f"{user_id}_{channel.get('id')}"
                MOCK_DB['slack_channels'][channel_key] = {
                    **channel,
                    'user_id': user_id,
                    'updated_at': datetime.utcnow().isoformat()
                }
        
        logger.info(f"Saved {len(channels)} Slack channels for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving Slack channels for user {user_id}: {e}")
        return False

# Utility functions
def is_token_expired(expires_at: str) -> bool:
    """Check if token is expired"""
    if not expires_at:
        return True
    
    try:
        expiry_time = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        current_time = datetime.now(timezone.utc)
        # Add 5 minute buffer
        return current_time >= expiry_time - timedelta(minutes=5)
    except Exception:
        return True

async def cleanup_expired_tokens(db_conn_pool) -> int:
    """Clean up expired tokens"""
    try:
        # Implementation depends on database type
        # This is a placeholder for cleanup logic
        logger.info("Cleaning up expired Slack tokens")
        return 0
    except Exception as e:
        logger.error(f"Error cleaning up expired Slack tokens: {e}")
        return 0