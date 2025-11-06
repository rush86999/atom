"""
Trello OAuth Database Handler
Secure token storage and management for Trello integration
"""

import os
import asyncpg
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

async def init_trello_oauth_table(db_pool):
    """Initialize Trello OAuth tokens table"""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS oauth_trello_tokens (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    access_token TEXT NOT NULL,
                    token_secret TEXT NOT NULL,
                    token_type VARCHAR(50) DEFAULT 'Bearer',
                    scope TEXT,
                    expires_at TIMESTAMP WITH TIME ZONE,
                    member_id TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id)
                )
            """)
            
            # Create indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_oauth_trello_user_id 
                ON oauth_trello_tokens(user_id)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_oauth_trello_member_id 
                ON oauth_trello_tokens(member_id)
            """)
            
            logger.info("Trello OAuth tokens table initialized successfully")
            
    except Exception as e:
        logger.error(f"Failed to initialize Trello OAuth tokens table: {e}")
        raise

async def save_trello_tokens(
    db_pool,
    user_id: str,
    access_token: str,
    token_secret: str,
    token_type: str = 'Bearer',
    scope: str = None,
    expires_at: datetime = None,
    member_id: str = None
) -> Dict[str, Any]:
    """Save or update Trello OAuth tokens"""
    try:
        async with db_pool.acquire() as conn:
            # Check if user already has tokens
            existing = await conn.fetchrow(
                "SELECT id FROM oauth_trello_tokens WHERE user_id = $1",
                user_id
            )
            
            if existing:
                # Update existing tokens
                await conn.execute("""
                    UPDATE oauth_trello_tokens 
                    SET access_token = $2, 
                        token_secret = $3,
                        token_type = $4,
                        scope = $5,
                        expires_at = $6,
                        member_id = $7,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $1
                """, user_id, access_token, token_secret, token_type, scope, 
                    expires_at, member_id)
                
                logger.info(f"Updated Trello OAuth tokens for user {user_id}")
            else:
                # Insert new tokens
                await conn.execute("""
                    INSERT INTO oauth_trello_tokens 
                    (user_id, access_token, token_secret, token_type, scope, 
                     expires_at, member_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, user_id, access_token, token_secret, token_type, scope,
                    expires_at, member_id)
                
                logger.info(f"Stored new Trello OAuth tokens for user {user_id}")
            
            return {
                'success': True,
                'user_id': user_id,
                'message': 'Trello OAuth tokens stored successfully'
            }
            
    except Exception as e:
        logger.error(f"Failed to store Trello OAuth tokens for user {user_id}: {e}")
        return {
            'success': False,
            'error': str(e),
            'user_id': user_id
        }

async def get_trello_tokens(db_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Get Trello OAuth tokens for a user"""
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT access_token, token_secret, token_type, scope, 
                       expires_at, member_id, created_at, updated_at
                FROM oauth_trello_tokens 
                WHERE user_id = $1
            """, user_id)
            
            if row:
                tokens = {
                    'access_token': row['access_token'],
                    'token_secret': row['token_secret'],
                    'token_type': row['token_type'],
                    'scope': row['scope'],
                    'expires_at': row['expires_at'],
                    'member_id': row['member_id'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                }
                
                # Check if token is expired
                if row['expires_at']:
                    is_expired = datetime.now(timezone.utc) >= row['expires_at']
                    tokens['expired'] = is_expired
                else:
                    tokens['expired'] = False
                
                logger.debug(f"Retrieved Trello OAuth tokens for user {user_id}")
                return tokens
            else:
                logger.info(f"No Trello OAuth tokens found for user {user_id}")
                return None
                
    except Exception as e:
        logger.error(f"Failed to get Trello OAuth tokens for user {user_id}: {e}")
        return None

async def update_trello_tokens(
    db_pool,
    user_id: str,
    access_token: str = None,
    token_secret: str = None,
    expires_at: datetime = None,
    member_id: str = None,
    scope: str = None
) -> Dict[str, Any]:
    """Update specific Trello OAuth token fields"""
    try:
        async with db_pool.acquire() as conn:
            # Build dynamic update query
            updates = []
            params = [1, user_id]  # Start with index 1 for user_id param
            param_index = 3
            
            if access_token is not None:
                updates.append(f"access_token = ${param_index}")
                params.append(access_token)
                param_index += 1
            
            if token_secret is not None:
                updates.append(f"token_secret = ${param_index}")
                params.append(token_secret)
                param_index += 1
            
            if expires_at is not None:
                updates.append(f"expires_at = ${param_index}")
                params.append(expires_at)
                param_index += 1
            
            if member_id is not None:
                updates.append(f"member_id = ${param_index}")
                params.append(member_id)
                param_index += 1
            
            if scope is not None:
                updates.append(f"scope = ${param_index}")
                params.append(scope)
                param_index += 1
            
            updates.append("updated_at = CURRENT_TIMESTAMP")
            
            if updates:
                query = f"""
                    UPDATE oauth_trello_tokens 
                    SET {', '.join(updates)}
                    WHERE user_id = ${param_index}
                """
                params.append(user_id)
                
                result = await conn.execute(query, *params)
                
                logger.info(f"Updated Trello OAuth tokens for user {user_id}")
                return {
                    'success': True,
                    'user_id': user_id,
                    'message': 'Trello OAuth tokens updated successfully'
                }
            else:
                return {
                    'success': False,
                    'error': 'No fields to update',
                    'user_id': user_id
                }
                
    except Exception as e:
        logger.error(f"Failed to update Trello OAuth tokens for user {user_id}: {e}")
        return {
            'success': False,
            'error': str(e),
            'user_id': user_id
        }

async def delete_trello_tokens(db_pool, user_id: str) -> Dict[str, Any]:
    """Delete Trello OAuth tokens for a user"""
    try:
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM oauth_trello_tokens WHERE user_id = $1",
                user_id
            )
            
            logger.info(f"Deleted Trello OAuth tokens for user {user_id}")
            return {
                'success': True,
                'user_id': user_id,
                'message': 'Trello OAuth tokens deleted successfully'
            }
            
    except Exception as e:
        logger.error(f"Failed to delete Trello OAuth tokens for user {user_id}: {e}")
        return {
            'success': False,
            'error': str(e),
            'user_id': user_id
        }

async def refresh_trello_tokens_if_needed(db_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Check and refresh Trello tokens if they're expired"""
    try:
        tokens = await get_trello_tokens(db_pool, user_id)
        
        if not tokens:
            logger.warning(f"No Trello tokens found for user {user_id}")
            return None
        
        # Check if token needs refresh
        needs_refresh = tokens.get('expired', False)
        
        if not needs_refresh:
            # Token is still valid
            return tokens
        
        # Note: Trello tokens don't have refresh tokens
        # User needs to re-authenticate
        logger.error(f"Trello token expired for user {user_id} - re-authentication required")
        return None
            
    except Exception as e:
        logger.error(f"Error refreshing Trello tokens for user {user_id}: {e}")
        return None

async def get_all_trello_users(db_pool) -> list:
    """Get all users with Trello OAuth tokens"""
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT user_id, member_id, created_at, updated_at, expires_at
                FROM oauth_trello_tokens
                ORDER BY updated_at DESC
            """)
            
            users = []
            for row in rows:
                users.append({
                    'user_id': row['user_id'],
                    'member_id': row['member_id'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at'],
                    'expires_at': row['expires_at']
                })
            
            logger.debug(f"Retrieved {len(users)} users with Trello OAuth tokens")
            return users
            
    except Exception as e:
        logger.error(f"Failed to get Trello users: {e}")
        return []

async def cleanup_expired_trello_tokens(db_pool) -> Dict[str, Any]:
    """Clean up expired Trello tokens (older than 30 days)"""
    try:
        async with db_pool.acquire() as conn:
            # Delete tokens expired for more than 30 days
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
            
            result = await conn.execute("""
                DELETE FROM oauth_trello_tokens 
                WHERE expires_at IS NOT NULL 
                AND expires_at < $1
            """, cutoff_date)
            
            logger.info(f"Cleaned up expired Trello OAuth tokens older than {cutoff_date}")
            return {
                'success': True,
                'message': 'Expired Trello tokens cleanup completed',
                'cutoff_date': cutoff_date.isoformat()
            }
            
    except Exception as e:
        logger.error(f"Failed to cleanup expired Trello tokens: {e}")
        return {
            'success': False,
            'error': str(e)
        }

# Convenience function aliases
async def save_user_trello_tokens(db_pool, user_id: str, **kwargs) -> Dict[str, Any]:
    """Alias for save_trello_tokens with user_id parameter"""
    return await save_trello_tokens(db_pool, user_id, **kwargs)

async def get_user_trello_tokens(db_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Alias for get_trello_tokens"""
    return await get_trello_tokens(db_pool, user_id)

async def delete_user_trello_tokens(db_pool, user_id: str) -> Dict[str, Any]:
    """Alias for delete_trello_tokens"""
    return await delete_trello_tokens(db_pool, user_id)

# Legacy function aliases for compatibility
async def save_tokens(db_pool, user_id: str, encrypted_access_token: bytes, encrypted_refresh_token: bytes, expires_at: datetime, scope: str):
    """Legacy function for compatibility"""
    # Decode tokens (assuming they were encrypted)
    import base64
    try:
        access_token = base64.b64decode(encrypted_access_token).decode()
        refresh_token = base64.b64decode(encrypted_refresh_token).decode()
    except:
        access_token = encrypted_access_token.decode() if isinstance(encrypted_access_token, bytes) else encrypted_access_token
        refresh_token = encrypted_refresh_token.decode() if isinstance(encrypted_refresh_token, bytes) else encrypted_refresh_token
    
    return await save_trello_tokens(db_pool, user_id, access_token, refresh_token, 'Bearer', scope, expires_at)

async def get_tokens(db_pool, user_id: str):
    """Legacy function for compatibility"""
    tokens = await get_trello_tokens(db_pool, user_id)
    if tokens:
        # Return in legacy format
        return (
            tokens['access_token'].encode(),
            tokens['token_secret'].encode(),
            tokens['expires_at']
        )
    return None

async def delete_tokens(db_pool, user_id: str):
    """Legacy function for compatibility"""
    return await delete_trello_tokens(db_pool, user_id)