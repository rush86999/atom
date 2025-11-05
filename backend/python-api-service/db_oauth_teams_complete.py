"""
Microsoft Teams OAuth Database Operations
Handles storage and retrieval of Teams OAuth tokens and user data
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

# Teams OAuth configuration
TEAMS_CLIENT_ID = os.getenv('TEAMS_CLIENT_ID', 'mock_teams_client_id')
TEAMS_CLIENT_SECRET = os.getenv('TEAMS_CLIENT_SECRET', 'mock_teams_client_secret')
TEAMS_REDIRECT_URI = os.getenv('TEAMS_REDIRECT_URI', 'http://localhost:3000/integrations/teams/callback')
TEAMS_SCOPE = os.getenv('TEAMS_SCOPE', 'offline_access,Channel.ReadBasic.All,ChannelMessage.Send.All,Chat.ReadWrite,User.Read.All,Team.ReadBasic.All')

# Mock database fallback
MOCK_DB = {
    'teams_tokens': {},
    'teams_users': {},
    'teams_channels': {},
    'teams_messages': {},
    'teams_meetings': {},
    'teams_files': {},
    'teams_webhooks': {}
}

# Initialize SQLite database if needed
def init_sqlite_db():
    """Initialize SQLite database with Teams tables"""
    try:
        db_path = os.getenv('ATOM_SQLITE_PATH', 'data/atom_development.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Teams tokens table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teams_oauth_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                access_token TEXT NOT NULL,
                token_type TEXT DEFAULT 'Bearer',
                scope TEXT,
                refresh_token TEXT,
                expires_at TIMESTAMP,
                id_token TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id)
            )
        ''')
        
        # Teams users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teams_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                teams_user_id TEXT NOT NULL,
                display_name TEXT NOT NULL,
                mail TEXT,
                given_name TEXT,
                surname TEXT,
                job_title TEXT,
                office_location TEXT,
                business_phones TEXT,
                mobile_phone TEXT,
                photo_available BOOLEAN DEFAULT FALSE,
                user_principal_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id)
            )
        ''')
        
        # Teams channels cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teams_channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                display_name TEXT NOT NULL,
                description TEXT,
                email TEXT,
                web_url TEXT,
                membership_type TEXT,
                tenant_id TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, channel_id)
            )
        ''')
        
        # Teams messages cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teams_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                from_user TEXT,
                subject TEXT,
                body TEXT,
                summary TEXT,
                importance TEXT DEFAULT 'normal',
                locale TEXT DEFAULT 'en-us',
                created_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, message_id)
            )
        ''')
        
        # Teams meetings cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teams_meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                meeting_id TEXT NOT NULL,
                subject TEXT,
                body TEXT,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                location TEXT,
                attendees TEXT,
                importance TEXT DEFAULT 'normal',
                created_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, meeting_id)
            )
        ''')
        
        # Teams files cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teams_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                file_id TEXT NOT NULL,
                name TEXT NOT NULL,
                size INTEGER DEFAULT 0,
                mime_type TEXT,
                file_type TEXT,
                web_url TEXT,
                created_by TEXT,
                created_at TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, file_id)
            )
        ''')
        
        # Teams webhooks table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teams_webhooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                webhook_id TEXT NOT NULL,
                resource TEXT,
                expiration_date_time TIMESTAMP,
                client_state TEXT,
                app_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, webhook_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("Teams SQLite database initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize Teams SQLite database: {e}")
        raise

# Initialize database
if DB_TYPE == 'sqlite':
    init_sqlite_db()

async def save_tokens(db_conn_pool, user_id: str, token_data: Dict[str, Any]) -> bool:
    """
    Save Teams OAuth tokens for user
    """
    try:
        if DB_TYPE == 'postgres' and db_conn_pool:
            return await _save_tokens_postgres(db_conn_pool, user_id, token_data)
        elif DB_TYPE == 'sqlite':
            return await _save_tokens_sqlite(user_id, token_data)
        else:
            # Mock fallback
            MOCK_DB['teams_tokens'][user_id] = {
                **token_data,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            return True
    except Exception as e:
        logger.error(f"Error saving Teams tokens for user {user_id}: {e}")
        return False

async def _save_tokens_postgres(db_conn_pool, user_id: str, token_data: Dict[str, Any]) -> bool:
    """Save tokens to PostgreSQL"""
    try:
        # Encrypt sensitive data
        access_token = token_data.get('access_token', '')
        refresh_token = token_data.get('refresh_token', '')
        id_token = token_data.get('id_token', '')
        
        if ENCRYPTION_AVAILABLE:
            access_token = encrypt_data(access_token, ATOM_OAUTH_ENCRYPTION_KEY)
            refresh_token = encrypt_data(refresh_token, ATOM_OAUTH_ENCRYPTION_KEY)
            id_token = encrypt_data(id_token, ATOM_OAUTH_ENCRYPTION_KEY)
        
        async with db_conn_pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO teams_oauth_tokens 
                (user_id, access_token, token_type, scope, refresh_token,
                 expires_at, id_token)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (user_id) 
                DO UPDATE SET 
                access_token = $2, token_type = $3, scope = $4, refresh_token = $5,
                expires_at = $6, id_token = $7, updated_at = CURRENT_TIMESTAMP
            ''', (
                user_id,
                access_token,
                token_data.get('token_type', 'Bearer'),
                token_data.get('scope'),
                refresh_token,
                token_data.get('expires_at'),
                id_token
            ))
        
        logger.info(f"Teams tokens saved for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving Teams tokens to PostgreSQL: {e}")
        return False

async def _save_tokens_sqlite(user_id: str, token_data: Dict[str, Any]) -> bool:
    """Save tokens to SQLite"""
    try:
        # Encrypt sensitive data
        access_token = token_data.get('access_token', '')
        refresh_token = token_data.get('refresh_token', '')
        id_token = token_data.get('id_token', '')
        
        if ENCRYPTION_AVAILABLE:
            access_token = encrypt_data(access_token, ATOM_OAUTH_ENCRYPTION_KEY)
            refresh_token = encrypt_data(refresh_token, ATOM_OAUTH_ENCRYPTION_KEY)
            id_token = encrypt_data(id_token, ATOM_OAUTH_ENCRYPTION_KEY)
        
        db_path = os.getenv('ATOM_SQLITE_PATH', 'data/atom_development.db')
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute('''
                INSERT OR REPLACE INTO teams_oauth_tokens 
                (user_id, access_token, token_type, scope, refresh_token,
                 expires_at, id_token)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                access_token,
                token_data.get('token_type', 'Bearer'),
                token_data.get('scope'),
                refresh_token,
                token_data.get('expires_at'),
                id_token
            ))
            await conn.commit()
        
        logger.info(f"Teams tokens saved for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving Teams tokens to SQLite: {e}")
        return False

async def get_tokens(db_conn_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get Teams OAuth tokens for user
    """
    try:
        if DB_TYPE == 'postgres' and db_conn_pool:
            return await _get_tokens_postgres(db_conn_pool, user_id)
        elif DB_TYPE == 'sqlite':
            return await _get_tokens_sqlite(user_id)
        else:
            # Mock fallback
            return MOCK_DB['teams_tokens'].get(user_id)
    except Exception as e:
        logger.error(f"Error getting Teams tokens for user {user_id}: {e}")
        return None

async def _get_tokens_postgres(db_conn_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Get tokens from PostgreSQL"""
    try:
        async with db_conn_pool.acquire() as conn:
            row = await conn.fetchrow('''
                SELECT access_token, token_type, scope, refresh_token,
                       expires_at, id_token, created_at, updated_at
                FROM teams_oauth_tokens 
                WHERE user_id = $1
            ''', user_id)
            
            if not row:
                return None
            
            # Decrypt sensitive data
            access_token = row['access_token']
            refresh_token = row['refresh_token']
            id_token = row['id_token']
            
            if ENCRYPTION_AVAILABLE:
                access_token = decrypt_data(access_token, ATOM_OAUTH_ENCRYPTION_KEY)
                refresh_token = decrypt_data(refresh_token, ATOM_OAUTH_ENCRYPTION_KEY)
                id_token = decrypt_data(id_token, ATOM_OAUTH_ENCRYPTION_KEY)
            
            return {
                'access_token': access_token,
                'token_type': row['token_type'],
                'scope': row['scope'],
                'refresh_token': refresh_token,
                'expires_at': row['expires_at'],
                'id_token': id_token,
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }
        
    except Exception as e:
        logger.error(f"Error getting Teams tokens from PostgreSQL: {e}")
        return None

async def _get_tokens_sqlite(user_id: str) -> Optional[Dict[str, Any]]:
    """Get tokens from SQLite"""
    try:
        db_path = os.getenv('ATOM_SQLITE_PATH', 'data/atom_development.db')
        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute('''
                SELECT access_token, token_type, scope, refresh_token,
                       expires_at, id_token, created_at, updated_at
                FROM teams_oauth_tokens 
                WHERE user_id = ?
            ''', (user_id,))
            row = await cursor.fetchone()
            
            if not row:
                return None
            
            # Decrypt sensitive data
            access_token = row['access_token']
            refresh_token = row['refresh_token']
            id_token = row['id_token']
            
            if ENCRYPTION_AVAILABLE:
                access_token = decrypt_data(access_token, ATOM_OAUTH_ENCRYPTION_KEY)
                refresh_token = decrypt_data(refresh_token, ATOM_OAUTH_ENCRYPTION_KEY)
                id_token = decrypt_data(id_token, ATOM_OAUTH_ENCRYPTION_KEY)
            
            return {
                'access_token': access_token,
                'token_type': row['token_type'],
                'scope': row['scope'],
                'refresh_token': refresh_token,
                'expires_at': row['expires_at'],
                'id_token': id_token,
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }
        
    except Exception as e:
        logger.error(f"Error getting Teams tokens from SQLite: {e}")
        return None

async def delete_tokens(db_conn_pool, user_id: str) -> bool:
    """
    Delete Teams OAuth tokens for user
    """
    try:
        if DB_TYPE == 'postgres' and db_conn_pool:
            async with db_conn_pool.acquire() as conn:
                result = await conn.execute(
                    'DELETE FROM teams_oauth_tokens WHERE user_id = $1',
                    user_id
                )
                return result != 'DELETE 0'
        
        elif DB_TYPE == 'sqlite':
            db_path = os.getenv('ATOM_SQLITE_PATH', 'data/atom_development.db')
            async with aiosqlite.connect(db_path) as conn:
                await conn.execute(
                    'DELETE FROM teams_oauth_tokens WHERE user_id = ?',
                    (user_id,)
                )
                await conn.commit()
                return True
        
        else:
            # Mock fallback
            if user_id in MOCK_DB['teams_tokens']:
                del MOCK_DB['teams_tokens'][user_id]
                return True
            return False
        
    except Exception as e:
        logger.error(f"Error deleting Teams tokens for user {user_id}: {e}")
        return False

async def save_user_teams_tokens(db_conn_pool, user_id: str, token_data: Dict[str, Any]) -> bool:
    """
    Save Teams tokens and user data (combined operation)
    """
    try:
        # Save tokens
        tokens_saved = await save_tokens(db_conn_pool, user_id, token_data)
        
        # Extract and save user info if available
        if 'user_info' in token_data:
            user_info = token_data['user_info']
            user_saved = await save_teams_user(db_conn_pool, user_id, user_info)
        else:
            user_saved = True
        
        return tokens_saved and user_saved
        
    except Exception as e:
        logger.error(f"Error saving Teams user tokens for user {user_id}: {e}")
        return False

async def get_user_teams_tokens(db_conn_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get Teams tokens with user info
    """
    try:
        # Get tokens
        tokens = await get_tokens(db_conn_pool, user_id)
        if not tokens:
            return None
        
        # Get user info
        user_info = await get_teams_user(db_conn_pool, user_id)
        
        return {
            **tokens,
            'user_info': user_info
        }
        
    except Exception as e:
        logger.error(f"Error getting user Teams tokens for user {user_id}: {e}")
        return None

async def delete_user_teams_tokens(db_conn_pool, user_id: str) -> bool:
    """
    Delete Teams tokens and user data (combined operation)
    """
    try:
        # Delete tokens
        tokens_deleted = await delete_tokens(db_conn_pool, user_id)
        
        # Delete user info
        user_deleted = await delete_teams_user(db_conn_pool, user_id)
        
        return tokens_deleted or user_deleted
        
    except Exception as e:
        logger.error(f"Error deleting user Teams tokens for user {user_id}: {e}")
        return False

# Teams user data operations
async def save_teams_user(db_conn_pool, user_id: str, user_info: Dict[str, Any]) -> bool:
    """Save Teams user information"""
    try:
        if DB_TYPE == 'postgres' and db_conn_pool:
            return await _save_teams_user_postgres(db_conn_pool, user_id, user_info)
        elif DB_TYPE == 'sqlite':
            return await _save_teams_user_sqlite(user_id, user_info)
        else:
            # Mock fallback
            MOCK_DB['teams_users'][user_id] = {
                **user_info,
                'created_at': datetime.utcnow().isoformat(),
                'updated_at': datetime.utcnow().isoformat()
            }
            return True
    except Exception as e:
        logger.error(f"Error saving Teams user info for user {user_id}: {e}")
        return False

async def _save_teams_user_postgres(db_conn_pool, user_id: str, user_info: Dict[str, Any]) -> bool:
    """Save Teams user info to PostgreSQL"""
    try:
        async with db_conn_pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO teams_users 
                (user_id, teams_user_id, display_name, mail, given_name,
                 surname, job_title, office_location, business_phones,
                 mobile_phone, photo_available, user_principal_name)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                ON CONFLICT (user_id) 
                DO UPDATE SET 
                teams_user_id = $2, display_name = $3, mail = $4, given_name = $5,
                surname = $6, job_title = $7, office_location = $8,
                business_phones = $9, mobile_phone = $10, photo_available = $11,
                user_principal_name = $12, updated_at = CURRENT_TIMESTAMP
            ''', (
                user_id,
                user_info.get('id'),
                user_info.get('displayName'),
                user_info.get('mail'),
                user_info.get('givenName'),
                user_info.get('surname'),
                user_info.get('jobTitle'),
                user_info.get('officeLocation'),
                json.dumps(user_info.get('businessPhones', [])),
                user_info.get('mobilePhone'),
                user_info.get('photo_available', False),
                user_info.get('userPrincipalName')
            ))
        
        logger.info(f"Teams user info saved for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving Teams user info to PostgreSQL: {e}")
        return False

async def _save_teams_user_sqlite(user_id: str, user_info: Dict[str, Any]) -> bool:
    """Save Teams user info to SQLite"""
    try:
        db_path = os.getenv('ATOM_SQLITE_PATH', 'data/atom_development.db')
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute('''
                INSERT OR REPLACE INTO teams_users 
                (user_id, teams_user_id, display_name, mail, given_name,
                 surname, job_title, office_location, business_phones,
                 mobile_phone, photo_available, user_principal_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                user_info.get('id'),
                user_info.get('displayName'),
                user_info.get('mail'),
                user_info.get('givenName'),
                user_info.get('surname'),
                user_info.get('jobTitle'),
                user_info.get('officeLocation'),
                json.dumps(user_info.get('businessPhones', [])),
                user_info.get('mobilePhone'),
                user_info.get('photo_available', False),
                user_info.get('userPrincipalName')
            ))
            await conn.commit()
        
        logger.info(f"Teams user info saved for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving Teams user info to SQLite: {e}")
        return False

async def get_teams_user(db_conn_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Get Teams user information"""
    try:
        if DB_TYPE == 'postgres' and db_conn_pool:
            return await _get_teams_user_postgres(db_conn_pool, user_id)
        elif DB_TYPE == 'sqlite':
            return await _get_teams_user_sqlite(user_id)
        else:
            # Mock fallback
            return MOCK_DB['teams_users'].get(user_id)
    except Exception as e:
        logger.error(f"Error getting Teams user info for user {user_id}: {e}")
        return None

async def _get_teams_user_postgres(db_conn_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Get Teams user info from PostgreSQL"""
    try:
        async with db_conn_pool.acquire() as conn:
            row = await conn.fetchrow('''
                SELECT teams_user_id, display_name, mail, given_name, surname,
                       job_title, office_location, business_phones, mobile_phone,
                       photo_available, user_principal_name, created_at, updated_at
                FROM teams_users 
                WHERE user_id = $1
            ''', user_id)
            
            if not row:
                return None
            
            return {
                'id': row['teams_user_id'],
                'displayName': row['display_name'],
                'mail': row['mail'],
                'givenName': row['given_name'],
                'surname': row['surname'],
                'jobTitle': row['job_title'],
                'officeLocation': row['office_location'],
                'businessPhones': json.loads(row['business_phones']) if row['business_phones'] else [],
                'mobilePhone': row['mobile_phone'],
                'photo_available': row['photo_available'],
                'userPrincipalName': row['user_principal_name'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }
        
    except Exception as e:
        logger.error(f"Error getting Teams user info from PostgreSQL: {e}")
        return None

async def _get_teams_user_sqlite(user_id: str) -> Optional[Dict[str, Any]]:
    """Get Teams user info from SQLite"""
    try:
        db_path = os.getenv('ATOM_SQLITE_PATH', 'data/atom_development.db')
        async with aiosqlite.connect(db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute('''
                SELECT teams_user_id, display_name, mail, given_name, surname,
                       job_title, office_location, business_phones, mobile_phone,
                       photo_available, user_principal_name, created_at, updated_at
                FROM teams_users 
                WHERE user_id = ?
            ''', (user_id,))
            row = await cursor.fetchone()
            
            if not row:
                return None
            
            return {
                'id': row['teams_user_id'],
                'displayName': row['display_name'],
                'mail': row['mail'],
                'givenName': row['given_name'],
                'surname': row['surname'],
                'jobTitle': row['job_title'],
                'officeLocation': row['office_location'],
                'businessPhones': json.loads(row['business_phones']) if row['business_phones'] else [],
                'mobilePhone': row['mobile_phone'],
                'photo_available': row['photo_available'],
                'userPrincipalName': row['user_principal_name'],
                'created_at': row['created_at'],
                'updated_at': row['updated_at']
            }
        
    except Exception as e:
        logger.error(f"Error getting Teams user info from SQLite: {e}")
        return None

async def delete_teams_user(db_conn_pool, user_id: str) -> bool:
    """Delete Teams user information"""
    try:
        if DB_TYPE == 'postgres' and db_conn_pool:
            async with db_conn_pool.acquire() as conn:
                result = await conn.execute(
                    'DELETE FROM teams_users WHERE user_id = $1',
                    user_id
                )
                return result != 'DELETE 0'
        
        elif DB_TYPE == 'sqlite':
            db_path = os.getenv('ATOM_SQLITE_PATH', 'data/atom_development.db')
            async with aiosqlite.connect(db_path) as conn:
                await conn.execute(
                    'DELETE FROM teams_users WHERE user_id = ?',
                    (user_id,)
                )
                await conn.commit()
                return True
        
        else:
            # Mock fallback
            if user_id in MOCK_DB['teams_users']:
                del MOCK_DB['teams_users'][user_id]
                return True
            return False
        
    except Exception as e:
        logger.error(f"Error deleting Teams user info for user {user_id}: {e}")
        return False

# Helper functions for Teams-specific operations
async def refresh_teams_tokens(db_conn_pool, user_id: str, new_token_data: Dict[str, Any]) -> bool:
    """Refresh Teams tokens with new access token"""
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
        logger.error(f"Error refreshing Teams tokens for user {user_id}: {e}")
        return False

async def get_teams_user_channels(db_conn_pool, user_id: str) -> List[Dict[str, Any]]:
    """Get cached channels for Teams user"""
    try:
        if DB_TYPE == 'postgres' and db_conn_pool:
            async with db_conn_pool.acquire() as conn:
                rows = await conn.fetch('''
                    SELECT channel_id, display_name, description, email, web_url,
                           membership_type, tenant_id, created_at, updated_at
                    FROM teams_channels 
                    WHERE user_id = $1
                    ORDER BY display_name
                ''', user_id)
                
                return [dict(row) for row in rows]
        
        elif DB_TYPE == 'sqlite':
            db_path = os.getenv('ATOM_SQLITE_PATH', 'data/atom_development.db')
            async with aiosqlite.connect(db_path) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await conn.execute('''
                    SELECT channel_id, display_name, description, email, web_url,
                           membership_type, tenant_id, created_at, updated_at
                    FROM teams_channels 
                    WHERE user_id = ?
                    ORDER BY display_name
                ''', (user_id,))
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        
        else:
            # Mock fallback
            return [channel for channel in MOCK_DB['teams_channels'].values() 
                   if channel.get('user_id') == user_id]
        
    except Exception as e:
        logger.error(f"Error getting cached Teams channels for user {user_id}: {e}")
        return []

async def save_teams_channels(db_conn_pool, user_id: str, channels: List[Dict[str, Any]]) -> bool:
    """Save Teams channels cache"""
    try:
        if not channels:
            return True
        
        if DB_TYPE == 'postgres' and db_conn_pool:
            async with db_conn_pool.acquire() as conn:
                for channel in channels:
                    await conn.execute('''
                        INSERT INTO teams_channels 
                        (user_id, channel_id, display_name, description, email,
                         web_url, membership_type, tenant_id)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (user_id, channel_id) 
                        DO UPDATE SET 
                        display_name = $3, description = $4, email = $5,
                        web_url = $6, membership_type = $7, tenant_id = $8,
                        updated_at = CURRENT_TIMESTAMP
                    ''', (
                        user_id,
                        channel.get('id'),
                        channel.get('displayName'),
                        channel.get('description'),
                        channel.get('email'),
                        channel.get('webUrl'),
                        channel.get('membershipType'),
                        channel.get('tenantId')
                    ))
        
        elif DB_TYPE == 'sqlite':
            db_path = os.getenv('ATOM_SQLITE_PATH', 'data/atom_development.db')
            async with aiosqlite.connect(db_path) as conn:
                for channel in channels:
                    await conn.execute('''
                        INSERT OR REPLACE INTO teams_channels 
                        (user_id, channel_id, display_name, description, email,
                         web_url, membership_type, tenant_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        user_id,
                        channel.get('id'),
                        channel.get('displayName'),
                        channel.get('description'),
                        channel.get('email'),
                        channel.get('webUrl'),
                        channel.get('membershipType'),
                        channel.get('tenantId')
                    ))
                await conn.commit()
        
        else:
            # Mock fallback
            for channel in channels:
                channel_key = f"{user_id}_{channel.get('id')}"
                MOCK_DB['teams_channels'][channel_key] = {
                    **channel,
                    'user_id': user_id,
                    'updated_at': datetime.utcnow().isoformat()
                }
        
        logger.info(f"Saved {len(channels)} Teams channels for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error saving Teams channels for user {user_id}: {e}")
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
        logger.info("Cleaning up expired Teams tokens")
        return 0
    except Exception as e:
        logger.error(f"Error cleaning up expired Teams tokens: {e}")
        return 0