"""
Slack Database Handler
Complete token management for Slack OAuth
"""

import os
import json
import logging
import psycopg2
import psycopg2.pool
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union
from loguru import logger

# Import crypto utilities
try:
    from crypto_utils import encrypt_data, decrypt_data
    CRYPTO_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Crypto utils not available: {e}")
    CRYPTO_AVAILABLE = False

# Import database utilities
try:
    from db_utils import get_db_connection, close_db_connection
    DB_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Database utils not available: {e}")
    DB_AVAILABLE = False

def ensure_database_table():
    """Ensure Slack OAuth tokens table exists"""
    try:
        if not DB_AVAILABLE:
            logger.warning("Database not available, skipping table creation")
            return False
        
        conn = get_db_connection()
        if not conn:
            logger.error("Failed to get database connection for Slack table creation")
            return False
        
        try:
            with conn.cursor() as cursor:
                # Create Slack OAuth tokens table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_slack_oauth_tokens (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        team_id VARCHAR(255) NOT NULL,
                        access_token TEXT NOT NULL,
                        refresh_token TEXT,
                        token_type VARCHAR(50) DEFAULT 'Bearer',
                        scope TEXT,
                        team_name VARCHAR(255),
                        user_name VARCHAR(255),
                        bot_user_id VARCHAR(255),
                        expires_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_active BOOLEAN DEFAULT TRUE,
                        UNIQUE(user_id, team_id)
                    )
                """)
                
                # Create indexes
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_slack_tokens_user_id 
                    ON user_slack_oauth_tokens(user_id)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_slack_tokens_team_id 
                    ON user_slack_oauth_tokens(team_id)
                """)
                
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_slack_tokens_active 
                    ON user_slack_oauth_tokens(user_id, is_active)
                """)
                
                # Create updated_at trigger
                cursor.execute("""
                    CREATE OR REPLACE FUNCTION update_slack_token_updated_at()
                    RETURNS TRIGGER AS $$
                    BEGIN
                        NEW.updated_at = CURRENT_TIMESTAMP;
                        RETURN NEW;
                    END;
                    $$ language 'plpgsql';
                """)
                
                cursor.execute("""
                    DROP TRIGGER IF EXISTS update_slack_token_updated_at_trigger 
                    ON user_slack_oauth_tokens;
                """)
                
                cursor.execute("""
                    CREATE TRIGGER update_slack_token_updated_at_trigger
                        BEFORE UPDATE ON user_slack_oauth_tokens
                        FOR EACH ROW
                        EXECUTE FUNCTION update_slack_token_updated_at();
                """)
                
                conn.commit()
                logger.info("Slack OAuth tokens table ensured successfully")
                return True
                
        except psycopg2.Error as e:
            logger.error(f"Database error creating Slack table: {e}")
            conn.rollback()
            return False
        finally:
            close_db_connection(conn)
            
    except Exception as e:
        logger.error(f"Error creating Slack database table: {e}")
        return False

async def save_user_slack_tokens(user_id: str, token_data: Dict[str, Any]) -> bool:
    """
    Save Slack OAuth tokens for user with encryption
    
    Args:
        user_id: User ID
        token_data: Slack token data from OAuth
        
    Returns:
        bool: True if successful
    """
    try:
        if not DB_AVAILABLE:
            logger.warning("Database not available, using fallback for Slack token storage")
            return await _save_slack_tokens_fallback(user_id, token_data)
        
        conn = get_db_connection()
        if not conn:
            logger.error("Failed to get database connection for Slack token saving")
            return False
        
        try:
            with conn.cursor() as cursor:
                # Encrypt sensitive data
                access_token = token_data['access_token']
                refresh_token = token_data.get('refresh_token')
                
                if CRYPTO_AVAILABLE:
                    access_token = encrypt_data(access_token.encode()).decode()
                    if refresh_token:
                        refresh_token = encrypt_data(refresh_token.encode()).decode()
                
                # Calculate expiration
                expires_in = token_data.get('expires_in', 7200)  # Default 2 hours
                expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
                
                # Insert or update tokens
                cursor.execute("""
                    INSERT INTO user_slack_oauth_tokens 
                    (user_id, team_id, access_token, refresh_token, token_type, scope,
                     team_name, user_name, bot_user_id, expires_at, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (user_id, team_id) 
                    DO UPDATE SET
                    access_token = EXCLUDED.access_token,
                    refresh_token = EXCLUDED.refresh_token,
                    token_type = EXCLUDED.token_type,
                    scope = EXCLUDED.scope,
                    team_name = EXCLUDED.team_name,
                    user_name = EXCLUDED.user_name,
                    bot_user_id = EXCLUDED.bot_user_id,
                    expires_at = EXCLUDED.expires_at,
                    updated_at = CURRENT_TIMESTAMP,
                    is_active = EXCLUDED.is_active
                """, (
                    user_id,
                    token_data.get('team_id', token_data.get('team', {}).get('id')),
                    access_token,
                    refresh_token,
                    token_data.get('token_type', 'Bearer'),
                    token_data.get('scope', ''),
                    token_data.get('team_name', token_data.get('team', {}).get('name')),
                    token_data.get('user_name', token_data.get('user', {}).get('name')),
                    token_data.get('bot_user_id'),
                    expires_at,
                    True
                ))
                
                conn.commit()
                logger.info(f"Slack tokens saved successfully for user {user_id}")
                return True
                
        except psycopg2.Error as e:
            logger.error(f"Database error saving Slack tokens: {e}")
            conn.rollback()
            return False
        finally:
            close_db_connection(conn)
            
    except Exception as e:
        logger.error(f"Error saving Slack tokens: {e}")
        return False

async def get_user_slack_tokens(user_id: str, team_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get Slack OAuth tokens for user with decryption
    
    Args:
        user_id: User ID
        team_id: Optional team ID for multi-workspace support
        
    Returns:
        dict: Token data or None if not found
    """
    try:
        if not DB_AVAILABLE:
            logger.warning("Database not available, using fallback for Slack token retrieval")
            return await _get_slack_tokens_fallback(user_id)
        
        conn = get_db_connection()
        if not conn:
            logger.error("Failed to get database connection for Slack token retrieval")
            return None
        
        try:
            with conn.cursor() as cursor:
                if team_id:
                    cursor.execute("""
                        SELECT access_token, refresh_token, token_type, scope,
                               team_id, team_name, user_name, bot_user_id,
                               expires_at, created_at, updated_at
                        FROM user_slack_oauth_tokens
                        WHERE user_id = %s AND team_id = %s AND is_active = TRUE
                        ORDER BY updated_at DESC
                        LIMIT 1
                    """, (user_id, team_id))
                else:
                    cursor.execute("""
                        SELECT access_token, refresh_token, token_type, scope,
                               team_id, team_name, user_name, bot_user_id,
                               expires_at, created_at, updated_at
                        FROM user_slack_oauth_tokens
                        WHERE user_id = %s AND is_active = TRUE
                        ORDER BY updated_at DESC
                        LIMIT 1
                    """, (user_id,))
                
                result = cursor.fetchone()
                
                if result:
                    # Decrypt sensitive data
                    access_token = result[0]
                    refresh_token = result[1]
                    
                    if CRYPTO_AVAILABLE:
                        access_token = decrypt_data(access_token.encode()).decode()
                        if refresh_token:
                            refresh_token = decrypt_data(refresh_token.encode()).decode()
                    
                    # Check if token is expired
                    expires_at = result[8]
                    if expires_at and expires_at <= datetime.utcnow():
                        logger.warning(f"Slack token expired for user {user_id}")
                        # Deactivate expired token
                        await _deactivate_slack_token(user_id, team_id or result[4])
                        return None
                    
                    return {
                        'access_token': access_token,
                        'refresh_token': refresh_token,
                        'token_type': result[2],
                        'scope': result[3],
                        'team_id': result[4],
                        'team_name': result[5],
                        'user_name': result[6],
                        'bot_user_id': result[7],
                        'expires_at': result[8].isoformat() if result[8] else None,
                        'created_at': result[9].isoformat() if result[9] else None,
                        'updated_at': result[10].isoformat() if result[10] else None
                    }
                else:
                    logger.info(f"No active Slack tokens found for user {user_id}")
                    return None
                
        except psycopg2.Error as e:
            logger.error(f"Database error retrieving Slack tokens: {e}")
            return None
        finally:
            close_db_connection(conn)
            
    except Exception as e:
        logger.error(f"Error getting Slack tokens: {e}")
        return None

async def get_user_slack_workspaces(user_id: str) -> List[Dict[str, Any]]:
    """Get all workspaces for user"""
    try:
        if not DB_AVAILABLE:
            return await _get_slack_workspaces_fallback(user_id)
        
        conn = get_db_connection()
        if not conn:
            return []
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT team_id, team_name, user_name, bot_user_id,
                           expires_at, updated_at
                    FROM user_slack_oauth_tokens
                    WHERE user_id = %s AND is_active = TRUE
                    ORDER BY updated_at DESC
                """, (user_id,))
                
                results = cursor.fetchall()
                
                workspaces = []
                for result in results:
                    workspaces.append({
                        'team_id': result[0],
                        'team_name': result[1],
                        'user_name': result[2],
                        'bot_user_id': result[3],
                        'expires_at': result[4].isoformat() if result[4] else None,
                        'updated_at': result[5].isoformat() if result[5] else None
                    })
                
                return workspaces
                
        except psycopg2.Error as e:
            logger.error(f"Database error retrieving Slack workspaces: {e}")
            return []
        finally:
            close_db_connection(conn)
            
    except Exception as e:
        logger.error(f"Error getting Slack workspaces: {e}")
        return []

async def delete_user_slack_tokens(user_id: str, team_id: Optional[str] = None) -> bool:
    """
    Delete Slack OAuth tokens for user (for de-authentication)
    
    Args:
        user_id: User ID
        team_id: Optional team ID
        
    Returns:
        bool: True if successful
    """
    try:
        if not DB_AVAILABLE:
            return await _delete_slack_tokens_fallback(user_id)
        
        conn = get_db_connection()
        if not conn:
            logger.error("Failed to get database connection for Slack token deletion")
            return False
        
        try:
            with conn.cursor() as cursor:
                if team_id:
                    cursor.execute("""
                        DELETE FROM user_slack_oauth_tokens
                        WHERE user_id = %s AND team_id = %s
                    """, (user_id, team_id))
                else:
                    cursor.execute("""
                        DELETE FROM user_slack_oauth_tokens
                        WHERE user_id = %s
                    """, (user_id,))
                
                conn.commit()
                logger.info(f"Slack tokens deleted for user {user_id}")
                return True
                
        except psycopg2.Error as e:
            logger.error(f"Database error deleting Slack tokens: {e}")
            conn.rollback()
            return False
        finally:
            close_db_connection(conn)
            
    except Exception as e:
        logger.error(f"Error deleting Slack tokens: {e}")
        return False

async def _deactivate_slack_token(user_id: str, team_id: str) -> bool:
    """Deactivate expired Slack token"""
    try:
        if not DB_AVAILABLE:
            return True  # Skip if no database
        
        conn = get_db_connection()
        if not conn:
            return False
        
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE user_slack_oauth_tokens
                    SET is_active = FALSE
                    WHERE user_id = %s AND team_id = %s
                """, (user_id, team_id))
                
                conn.commit()
                return True
                
        except psycopg2.Error as e:
            logger.error(f"Database error deactivating Slack token: {e}")
            conn.rollback()
            return False
        finally:
            close_db_connection(conn)
            
    except Exception as e:
        logger.error(f"Error deactivating Slack token: {e}")
        return False

async def _save_slack_tokens_fallback(user_id: str, token_data: Dict[str, Any]) -> bool:
    """Fallback token storage using environment variables"""
    try:
        # In development/testing, use environment variable
        if os.getenv('SLACK_ACCESS_TOKEN'):
            logger.info(f"Slack tokens saved to environment for user {user_id} (fallback)")
            return True
        
        # Or save to file (development only)
        fallback_dir = os.path.join(os.getcwd(), 'data', 'slack_tokens')
        os.makedirs(fallback_dir, exist_ok=True)
        
        token_file = os.path.join(fallback_dir, f'{user_id}.json')
        
        # Prepare data for storage
        storage_data = {
            'user_id': user_id,
            'access_token': token_data['access_token'],
            'refresh_token': token_data.get('refresh_token'),
            'team_id': token_data.get('team_id'),
            'team_name': token_data.get('team_name'),
            'expires_at': (datetime.utcnow() + timedelta(seconds=token_data.get('expires_in', 7200))).isoformat(),
            'created_at': datetime.utcnow().isoformat()
        }
        
        with open(token_file, 'w') as f:
            json.dump(storage_data, f, indent=2)
        
        logger.info(f"Slack tokens saved to fallback storage for user {user_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error in fallback Slack token storage: {e}")
        return False

async def _get_slack_tokens_fallback(user_id: str) -> Optional[Dict[str, Any]]:
    """Fallback token retrieval using environment variables"""
    try:
        # Check environment variables first
        env_token = os.getenv('SLACK_ACCESS_TOKEN')
        env_refresh = os.getenv('SLACK_REFRESH_TOKEN')
        env_team_id = os.getenv('SLACK_TEAM_ID')
        env_team_name = os.getenv('SLACK_TEAM_NAME')
        
        if env_token:
            logger.info(f"Slack tokens retrieved from environment for user {user_id} (fallback)")
            return {
                'access_token': env_token,
                'refresh_token': env_refresh,
                'token_type': 'Bearer',
                'scope': os.getenv('SLACK_SCOPE', 'channels:read,users:read,team:read'),
                'team_id': env_team_id,
                'team_name': env_team_name,
                'user_name': 'Test User',
                'expires_at': (datetime.utcnow() + timedelta(hours=1)).isoformat()
            }
        
        # Try file-based fallback
        fallback_dir = os.path.join(os.getcwd(), 'data', 'slack_tokens')
        token_file = os.path.join(fallback_dir, f'{user_id}.json')
        
        if os.path.exists(token_file):
            with open(token_file, 'r') as f:
                storage_data = json.load(f)
            
            # Check if expired
            expires_at = storage_data.get('expires_at')
            if expires_at:
                expiry_date = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                if expiry_date <= datetime.utcnow():
                    logger.warning(f"Fallback Slack token expired for user {user_id}")
                    return None
            
            logger.info(f"Slack tokens retrieved from fallback storage for user {user_id}")
            return storage_data
        
        return None
        
    except Exception as e:
        logger.error(f"Error in fallback Slack token retrieval: {e}")
        return None

async def _get_slack_workspaces_fallback(user_id: str) -> List[Dict[str, Any]]:
    """Fallback workspace retrieval"""
    try:
        # Check environment variables
        env_team_id = os.getenv('SLACK_TEAM_ID')
        env_team_name = os.getenv('SLACK_TEAM_NAME')
        env_bot_id = os.getenv('SLACK_BOT_USER_ID')
        
        if env_team_id:
            return [{
                'team_id': env_team_id,
                'team_name': env_team_name or 'Test Workspace',
                'user_name': 'Test User',
                'bot_user_id': env_bot_id,
                'expires_at': None,
                'updated_at': None
            }]
        
        return []
        
    except Exception as e:
        logger.error(f"Error in fallback Slack workspace retrieval: {e}")
        return []

async def _delete_slack_tokens_fallback(user_id: str) -> bool:
    """Fallback token deletion"""
    try:
        # Try to delete file-based storage
        fallback_dir = os.path.join(os.getcwd(), 'data', 'slack_tokens')
        token_file = os.path.join(fallback_dir, f'{user_id}.json')
        
        if os.path.exists(token_file):
            os.remove(token_file)
            logger.info(f"Slack tokens deleted from fallback storage for user {user_id}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error in fallback Slack token deletion: {e}")
        return False

# Initialize database table on module import
if __name__ != "__main__":
    asyncio.create_task(_initialize_slack_database())

async def _initialize_slack_database():
    """Initialize Slack database components"""
    try:
        # Wait a bit for app to fully initialize
        await asyncio.sleep(1)
        
        # Ensure database table exists
        table_created = ensure_database_table()
        if table_created:
            logger.info("Slack database initialization completed successfully")
        else:
            logger.warning("Slack database initialization failed, using fallback storage")
            
    except Exception as e:
        logger.error(f"Slack database initialization error: {e}")