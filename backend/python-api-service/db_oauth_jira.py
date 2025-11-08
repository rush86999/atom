"""
Jira OAuth Database Handler
Secure token storage and management for Jira integration
"""

import os
import asyncpg
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

async def init_jira_oauth_table(db_pool):
    """Initialize Jira OAuth tokens table"""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS oauth_jira_tokens (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT,
                    token_type VARCHAR(50) DEFAULT 'Bearer',
                    scope TEXT,
                    expires_at TIMESTAMP WITH TIME ZONE,
                    cloud_id TEXT,
                    resources TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id)
                )
            """)
            
            # Create indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_oauth_jira_user_id 
                ON oauth_jira_tokens(user_id)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_oauth_jira_cloud_id 
                ON oauth_jira_tokens(cloud_id)
            """)
            
            logger.info("Jira OAuth tokens table initialized successfully")
            
    except Exception as e:
        logger.error(f"Failed to initialize Jira OAuth tokens table: {e}")
        raise

async def save_jira_tokens(
    db_pool,
    user_id: str,
    access_token: str,
    refresh_token: str = None,
    token_type: str = 'Bearer',
    scope: str = None,
    expires_at: datetime = None,
    cloud_id: str = None,
    resources: str = None
) -> Dict[str, Any]:
    """Save or update Jira OAuth tokens"""
    try:
        async with db_pool.acquire() as conn:
            # Check if user already has tokens
            existing = await conn.fetchrow(
                "SELECT id FROM oauth_jira_tokens WHERE user_id = $1",
                user_id
            )
            
            if existing:
                # Update existing tokens
                await conn.execute("""
                    UPDATE oauth_jira_tokens 
                    SET access_token = $2, 
                        refresh_token = COALESCE($3, refresh_token),
                        token_type = $4,
                        scope = $5,
                        expires_at = $6,
                        cloud_id = $7,
                        resources = $8,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $1
                """, user_id, access_token, refresh_token, token_type, scope, 
                    expires_at, cloud_id, resources)
                
                logger.info(f"Updated Jira OAuth tokens for user {user_id}")
            else:
                # Insert new tokens
                await conn.execute("""
                    INSERT INTO oauth_jira_tokens 
                    (user_id, access_token, refresh_token, token_type, scope, 
                     expires_at, cloud_id, resources)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """, user_id, access_token, refresh_token, token_type, scope,
                    expires_at, cloud_id, resources)
                
                logger.info(f"Stored new Jira OAuth tokens for user {user_id}")
            
            return {
                'success': True,
                'user_id': user_id,
                'message': 'Jira OAuth tokens stored successfully'
            }
            
    except Exception as e:
        logger.error(f"Failed to store Jira OAuth tokens for user {user_id}: {e}")
        return {
            'success': False,
            'error': str(e),
            'user_id': user_id
        }

async def get_jira_tokens(db_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Get Jira OAuth tokens for a user"""
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT access_token, refresh_token, token_type, scope, 
                       expires_at, cloud_id, resources, 
                       created_at, updated_at
                FROM oauth_jira_tokens 
                WHERE user_id = $1
            """, user_id)
            
            if row:
                tokens = {
                    'access_token': row['access_token'],
                    'refresh_token': row['refresh_token'],
                    'token_type': row['token_type'],
                    'scope': row['scope'],
                    'expires_at': row['expires_at'],
                    'cloud_id': row['cloud_id'],
                    'resources': row['resources'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                }
                
                # Check if token is expired
                if row['expires_at']:
                    is_expired = datetime.now(timezone.utc) >= row['expires_at']
                    tokens['expired'] = is_expired
                else:
                    tokens['expired'] = False
                
                logger.debug(f"Retrieved Jira OAuth tokens for user {user_id}")
                return tokens
            else:
                logger.info(f"No Jira OAuth tokens found for user {user_id}")
                return None
                
    except Exception as e:
        logger.error(f"Failed to get Jira OAuth tokens for user {user_id}: {e}")
        return None

async def update_jira_tokens(
    db_pool,
    user_id: str,
    access_token: str = None,
    refresh_token: str = None,
    expires_at: datetime = None,
    cloud_id: str = None,
    resources: str = None
) -> Dict[str, Any]:
    """Update specific Jira OAuth token fields"""
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
            
            if cloud_id is not None:
                updates.append(f"cloud_id = ${param_index}")
                params.append(cloud_id)
                param_index += 1
            
            if resources is not None:
                updates.append(f"resources = ${param_index}")
                params.append(resources)
                param_index += 1
            
            updates.append("updated_at = CURRENT_TIMESTAMP")
            
            if updates:
                query = f"""
                    UPDATE oauth_jira_tokens 
                    SET {', '.join(updates)}
                    WHERE user_id = ${param_index}
                """
                params.append(user_id)
                
                result = await conn.execute(query, *params)
                
                logger.info(f"Updated Jira OAuth tokens for user {user_id}")
                return {
                    'success': True,
                    'user_id': user_id,
                    'message': 'Jira OAuth tokens updated successfully'
                }
            else:
                return {
                    'success': False,
                    'error': 'No fields to update',
                    'user_id': user_id
                }
                
    except Exception as e:
        logger.error(f"Failed to update Jira OAuth tokens for user {user_id}: {e}")
        return {
            'success': False,
            'error': str(e),
            'user_id': user_id
        }

async def delete_jira_tokens(db_pool, user_id: str) -> Dict[str, Any]:
    """Delete Jira OAuth tokens for a user"""
    try:
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM oauth_jira_tokens WHERE user_id = $1",
                user_id
            )
            
            logger.info(f"Deleted Jira OAuth tokens for user {user_id}")
            return {
                'success': True,
                'user_id': user_id,
                'message': 'Jira OAuth tokens deleted successfully'
            }
            
    except Exception as e:
        logger.error(f"Failed to delete Jira OAuth tokens for user {user_id}: {e}")
        return {
            'success': False,
            'error': str(e),
            'user_id': user_id
        }

async def refresh_jira_tokens_if_needed(db_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Check and refresh Jira tokens if they're expired"""
    try:
        tokens = await get_jira_tokens(db_pool, user_id)
        
        if not tokens:
            logger.warning(f"No Jira tokens found for user {user_id}")
            return None
        
        # Check if token needs refresh
        needs_refresh = tokens.get('expired', False)
        
        if not needs_refresh:
            # Token is still valid
            return tokens
        
        # Token needs refresh
        if not tokens.get('refresh_token'):
            logger.error(f"No refresh token available for Jira user {user_id}")
            return None
        
        # Refresh token using OAuth handler
        from auth_handler_jira import refresh_access_token
        
        # Refresh token
        refresh_result = await refresh_access_token(tokens['refresh_token'])
        
        if refresh_result.get('success'):
            new_access_token = refresh_result.get('access_token')
            new_refresh_token = refresh_result.get('refresh_token', tokens['refresh_token'])
            expires_in = refresh_result.get('expires_in', 3600)  # 1 hour default
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            
            # Update tokens in database
            await update_jira_tokens(
                db_pool, user_id, new_access_token, new_refresh_token, expires_at
            )
            
            # Return refreshed tokens
            refreshed_tokens = tokens.copy()
            refreshed_tokens['access_token'] = new_access_token
            refreshed_tokens['refresh_token'] = new_refresh_token
            refreshed_tokens['expires_at'] = expires_at
            refreshed_tokens['expired'] = False
            
            logger.info(f"Successfully refreshed Jira tokens for user {user_id}")
            return refreshed_tokens
        else:
            logger.error(f"Failed to refresh Jira tokens for user {user_id}: {refresh_result.get('error')}")
            return None
            
    except Exception as e:
        logger.error(f"Error refreshing Jira tokens for user {user_id}: {e}")
        return None

async def get_all_jira_users(db_pool) -> list:
    """Get all users with Jira OAuth tokens"""
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT user_id, cloud_id, created_at, updated_at, expires_at
                FROM oauth_jira_tokens
                ORDER BY updated_at DESC
            """)
            
            users = []
            for row in rows:
                users.append({
                    'user_id': row['user_id'],
                    'cloud_id': row['cloud_id'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at'],
                    'expires_at': row['expires_at']
                })
            
            logger.debug(f"Retrieved {len(users)} users with Jira OAuth tokens")
            return users
            
    except Exception as e:
        logger.error(f"Failed to get Jira users: {e}")
        return []

async def cleanup_expired_jira_tokens(db_pool) -> Dict[str, Any]:
    """Clean up expired Jira tokens (older than 30 days)"""
    try:
        async with db_pool.acquire() as conn:
            # Delete tokens expired for more than 30 days
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
            
            result = await conn.execute("""
                DELETE FROM oauth_jira_tokens 
                WHERE expires_at IS NOT NULL 
                AND expires_at < $1
            """, cutoff_date)
            
            logger.info(f"Cleaned up expired Jira OAuth tokens older than {cutoff_date}")
            return {
                'success': True,
                'message': 'Expired Jira tokens cleanup completed',
                'cutoff_date': cutoff_date.isoformat()
            }
            
    except Exception as e:
        logger.error(f"Failed to cleanup expired Jira tokens: {e}")
        return {
            'success': False,
            'error': str(e)
        }

# Convenience function aliases
async def save_user_jira_tokens(db_pool, user_id: str, **kwargs) -> Dict[str, Any]:
    """Alias for save_jira_tokens with user_id parameter"""
    return await save_jira_tokens(db_pool, user_id, **kwargs)

async def get_user_jira_tokens(db_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Alias for get_jira_tokens"""
    return await get_jira_tokens(db_pool, user_id)

async def delete_user_jira_tokens(db_pool, user_id: str) -> Dict[str, Any]:
    """Alias for delete_jira_tokens"""
    return await delete_jira_tokens(db_pool, user_id)

async def get_jira_user(db_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Get Jira user information including cloud_id"""
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT cloud_id, resources FROM oauth_jira_tokens WHERE user_id = $1",
                user_id
            )
            
            if row:
                return {
                    'cloud_id': row['cloud_id'],
                    'resources': row['resources']
                }
            return None
    except Exception as e:
        logger.error(f"Failed to get Jira user for {user_id}: {e}")
        return None