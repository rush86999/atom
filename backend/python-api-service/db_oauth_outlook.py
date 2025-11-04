"""
Database handler for Outlook OAuth tokens
Follows GitLab pattern for consistency
"""

import os
import asyncpg
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

async def init_outlook_oauth_table(db_pool):
    """Initialize the Outlook OAuth tokens table if it doesn't exist"""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS oauth_outlook_tokens (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT,
                    token_type VARCHAR(50) DEFAULT 'Bearer',
                    scope TEXT,
                    expires_at TIMESTAMP WITH TIME ZONE,
                    tenant_id VARCHAR(255),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id)
                )
            """)
            
            # Create index for better performance
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_oauth_outlook_user_id 
                ON oauth_outlook_tokens(user_id)
            """)
            
            logger.info("Outlook OAuth tokens table initialized successfully")
            
    except Exception as e:
        logger.error(f"Failed to initialize Outlook OAuth tokens table: {e}")
        raise

async def store_outlook_tokens(
    db_pool, 
    user_id: str, 
    access_token: str, 
    refresh_token: str = None,
    expires_at: datetime = None,
    scope: str = None,
    tenant_id: str = None
) -> Dict[str, Any]:
    """Store or update Outlook OAuth tokens"""
    try:
        async with db_pool.acquire() as conn:
            # Check if user already has tokens
            existing = await conn.fetchrow(
                "SELECT id FROM oauth_outlook_tokens WHERE user_id = $1",
                user_id
            )
            
            if existing:
                # Update existing tokens
                await conn.execute("""
                    UPDATE oauth_outlook_tokens 
                    SET access_token = $2, 
                        refresh_token = COALESCE($3, refresh_token),
                        scope = $4,
                        expires_at = $5,
                        tenant_id = $6,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $1
                """, user_id, access_token, refresh_token, scope, expires_at, tenant_id)
                
                logger.info(f"Updated Outlook OAuth tokens for user {user_id}")
            else:
                # Insert new tokens
                await conn.execute("""
                    INSERT INTO oauth_outlook_tokens 
                    (user_id, access_token, refresh_token, scope, expires_at, tenant_id)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, user_id, access_token, refresh_token, scope, expires_at, tenant_id)
                
                logger.info(f"Stored new Outlook OAuth tokens for user {user_id}")
            
            return {
                'success': True,
                'user_id': user_id,
                'message': 'Outlook OAuth tokens stored successfully'
            }
            
    except Exception as e:
        logger.error(f"Failed to store Outlook OAuth tokens for user {user_id}: {e}")
        return {
            'success': False,
            'error': str(e),
            'user_id': user_id
        }

async def get_outlook_tokens(db_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Get Outlook OAuth tokens for a user"""
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT access_token, refresh_token, token_type, scope, 
                       expires_at, tenant_id, created_at, updated_at
                FROM oauth_outlook_tokens 
                WHERE user_id = $1
            """, user_id)
            
            if row:
                tokens = {
                    'access_token': row['access_token'],
                    'refresh_token': row['refresh_token'],
                    'token_type': row['token_type'],
                    'scope': row['scope'],
                    'expires_at': row['expires_at'],
                    'tenant_id': row['tenant_id'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                }
                
                # Check if token is expired
                if row['expires_at']:
                    is_expired = datetime.now(timezone.utc) >= row['expires_at']
                    tokens['expired'] = is_expired
                else:
                    tokens['expired'] = False
                
                logger.debug(f"Retrieved Outlook OAuth tokens for user {user_id}")
                return tokens
            else:
                logger.info(f"No Outlook OAuth tokens found for user {user_id}")
                return None
                
    except Exception as e:
        logger.error(f"Failed to get Outlook OAuth tokens for user {user_id}: {e}")
        return None

async def update_outlook_tokens(
    db_pool, 
    user_id: str, 
    access_token: str = None,
    refresh_token: str = None,
    expires_at: datetime = None
) -> Dict[str, Any]:
    """Update specific Outlook OAuth token fields"""
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
            
            if refresh_token is not None:
                updates.append(f"refresh_token = ${param_index}")
                params.append(refresh_token)
                param_index += 1
            
            if expires_at is not None:
                updates.append(f"expires_at = ${param_index}")
                params.append(expires_at)
                param_index += 1
            
            updates.append("updated_at = CURRENT_TIMESTAMP")
            
            if updates:
                query = f"""
                    UPDATE oauth_outlook_tokens 
                    SET {', '.join(updates)}
                    WHERE user_id = ${param_index}
                """
                params.append(user_id)
                
                result = await conn.execute(query, *params)
                
                logger.info(f"Updated Outlook OAuth tokens for user {user_id}")
                return {
                    'success': True,
                    'user_id': user_id,
                    'message': 'Outlook OAuth tokens updated successfully'
                }
            else:
                return {
                    'success': False,
                    'error': 'No fields to update',
                    'user_id': user_id
                }
                
    except Exception as e:
        logger.error(f"Failed to update Outlook OAuth tokens for user {user_id}: {e}")
        return {
            'success': False,
            'error': str(e),
            'user_id': user_id
        }

async def delete_outlook_tokens(db_pool, user_id: str) -> Dict[str, Any]:
    """Delete Outlook OAuth tokens for a user"""
    try:
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM oauth_outlook_tokens WHERE user_id = $1",
                user_id
            )
            
            logger.info(f"Deleted Outlook OAuth tokens for user {user_id}")
            return {
                'success': True,
                'user_id': user_id,
                'message': 'Outlook OAuth tokens deleted successfully'
            }
            
    except Exception as e:
        logger.error(f"Failed to delete Outlook OAuth tokens for user {user_id}: {e}")
        return {
            'success': False,
            'error': str(e),
            'user_id': user_id
        }

async def refresh_outlook_tokens_if_needed(db_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Check and refresh Outlook tokens if they're expired"""
    try:
        tokens = await get_outlook_tokens(db_pool, user_id)
        
        if not tokens:
            logger.warning(f"No Outlook tokens found for user {user_id}")
            return None
        
        # Check if token needs refresh
        needs_refresh = tokens.get('expired', False)
        
        if not needs_refresh:
            # Token is still valid
            return tokens
        
        # Token needs refresh
        if not tokens.get('refresh_token'):
            logger.error(f"No refresh token available for Outlook user {user_id}")
            return None
        
        # Refresh token using OAuth handler
        from auth_handler_outlook_new import outlook_oauth_handler
        
        # Refresh token
        refresh_result = outlook_oauth_handler.refresh_token(tokens['refresh_token'])
        
        if refresh_result.get('success'):
            new_access_token = refresh_result.get('access_token')
            new_refresh_token = refresh_result.get('refresh_token', tokens['refresh_token'])
            expires_in = refresh_result.get('expires_in', 3600)
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            
            # Update tokens in database
            await update_outlook_tokens(
                db_pool, user_id, new_access_token, new_refresh_token, expires_at
            )
            
            # Return refreshed tokens
            refreshed_tokens = tokens.copy()
            refreshed_tokens['access_token'] = new_access_token
            refreshed_tokens['refresh_token'] = new_refresh_token
            refreshed_tokens['expires_at'] = expires_at
            refreshed_tokens['expired'] = False
            
            logger.info(f"Successfully refreshed Outlook tokens for user {user_id}")
            return refreshed_tokens
        else:
            logger.error(f"Failed to refresh Outlook tokens for user {user_id}: {refresh_result.get('error')}")
            return None
            
    except Exception as e:
        logger.error(f"Error refreshing Outlook tokens for user {user_id}: {e}")
        return None

async def get_all_outlook_users(db_pool) -> list:
    """Get all users with Outlook OAuth tokens"""
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT user_id, tenant_id, created_at, updated_at, expires_at
                FROM oauth_outlook_tokens
                ORDER BY updated_at DESC
            """)
            
            users = []
            for row in rows:
                users.append({
                    'user_id': row['user_id'],
                    'tenant_id': row['tenant_id'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at'],
                    'expires_at': row['expires_at']
                })
            
            logger.debug(f"Retrieved {len(users)} users with Outlook OAuth tokens")
            return users
            
    except Exception as e:
        logger.error(f"Failed to get Outlook users: {e}")
        return []

async def cleanup_expired_outlook_tokens(db_pool) -> Dict[str, Any]:
    """Clean up expired Outlook tokens (older than 30 days)"""
    try:
        async with db_pool.acquire() as conn:
            # Delete tokens expired for more than 30 days
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
            
            result = await conn.execute("""
                DELETE FROM oauth_outlook_tokens 
                WHERE expires_at IS NOT NULL 
                AND expires_at < $1
            """, cutoff_date)
            
            logger.info(f"Cleaned up expired Outlook OAuth tokens older than {cutoff_date}")
            return {
                'success': True,
                'message': 'Expired Outlook tokens cleanup completed',
                'cutoff_date': cutoff_date.isoformat()
            }
            
    except Exception as e:
        logger.error(f"Failed to cleanup expired Outlook tokens: {e}")
        return {
            'success': False,
            'error': str(e)
        }