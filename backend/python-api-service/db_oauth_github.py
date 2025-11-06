"""
GitHub OAuth Database Handler
Secure token storage and management for GitHub integration
"""

import os
import asyncpg
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

async def init_github_oauth_table(db_pool):
    """Initialize GitHub OAuth tokens table"""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS oauth_github_tokens (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    access_token TEXT NOT NULL,
                    token_type VARCHAR(50) DEFAULT 'Bearer',
                    scope TEXT,
                    expires_at TIMESTAMP WITH TIME ZONE,
                    refresh_token TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id)
                )
            """)
            
            # Create indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_oauth_github_user_id 
                ON oauth_github_tokens(user_id)
            """)
            
            logger.info("GitHub OAuth tokens table initialized successfully")
            
    except Exception as e:
        logger.error(f"Failed to initialize GitHub OAuth tokens table: {e}")
        raise

async def save_github_tokens(
    db_pool,
    user_id: str,
    access_token: str,
    refresh_token: str = None,
    token_type: str = 'Bearer',
    scope: str = None,
    expires_at: datetime = None
) -> Dict[str, Any]:
    """Save or update GitHub OAuth tokens"""
    try:
        async with db_pool.acquire() as conn:
            # Check if user already has tokens
            existing = await conn.fetchrow(
                "SELECT id FROM oauth_github_tokens WHERE user_id = $1",
                user_id
            )
            
            if existing:
                # Update existing tokens
                await conn.execute("""
                    UPDATE oauth_github_tokens 
                    SET access_token = $2, 
                        refresh_token = COALESCE($3, refresh_token),
                        token_type = $4,
                        scope = $5,
                        expires_at = $6,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $1
                """, user_id, access_token, refresh_token, token_type, scope, 
                    expires_at)
                
                logger.info(f"Updated GitHub OAuth tokens for user {user_id}")
            else:
                # Insert new tokens
                await conn.execute("""
                    INSERT INTO oauth_github_tokens 
                    (user_id, access_token, refresh_token, token_type, scope, expires_at)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, user_id, access_token, refresh_token, token_type, scope,
                    expires_at)
                
                logger.info(f"Stored new GitHub OAuth tokens for user {user_id}")
            
            return {
                'success': True,
                'user_id': user_id,
                'message': 'GitHub OAuth tokens stored successfully'
            }
            
    except Exception as e:
        logger.error(f"Failed to store GitHub OAuth tokens for user {user_id}: {e}")
        return {
            'success': False,
            'error': str(e),
            'user_id': user_id
        }

async def get_github_tokens(db_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Get GitHub OAuth tokens for a user"""
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT access_token, refresh_token, token_type, scope, 
                       expires_at, created_at, updated_at
                FROM oauth_github_tokens 
                WHERE user_id = $1
            """, user_id)
            
            if row:
                tokens = {
                    'access_token': row['access_token'],
                    'refresh_token': row['refresh_token'],
                    'token_type': row['token_type'],
                    'scope': row['scope'],
                    'expires_at': row['expires_at'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                }
                
                # Check if token is expired
                if row['expires_at']:
                    is_expired = datetime.now(timezone.utc) >= row['expires_at']
                    tokens['expired'] = is_expired
                else:
                    tokens['expired'] = False
                
                logger.debug(f"Retrieved GitHub OAuth tokens for user {user_id}")
                return tokens
            else:
                logger.info(f"No GitHub OAuth tokens found for user {user_id}")
                return None
                
    except Exception as e:
        logger.error(f"Failed to get GitHub OAuth tokens for user {user_id}: {e}")
        return None

async def update_github_tokens(
    db_pool,
    user_id: str,
    access_token: str = None,
    refresh_token: str = None,
    expires_at: datetime = None,
    scope: str = None
) -> Dict[str, Any]:
    """Update specific GitHub OAuth token fields"""
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
            
            if scope is not None:
                updates.append(f"scope = ${param_index}")
                params.append(scope)
                param_index += 1
            
            updates.append("updated_at = CURRENT_TIMESTAMP")
            
            if updates:
                query = f"""
                    UPDATE oauth_github_tokens 
                    SET {', '.join(updates)}
                    WHERE user_id = ${param_index}
                """
                params.append(user_id)
                
                result = await conn.execute(query, *params)
                
                logger.info(f"Updated GitHub OAuth tokens for user {user_id}")
                return {
                    'success': True,
                    'user_id': user_id,
                    'message': 'GitHub OAuth tokens updated successfully'
                }
            else:
                return {
                    'success': False,
                    'error': 'No fields to update',
                    'user_id': user_id
                }
                
    except Exception as e:
        logger.error(f"Failed to update GitHub OAuth tokens for user {user_id}: {e}")
        return {
            'success': False,
            'error': str(e),
            'user_id': user_id
        }

async def delete_github_tokens(db_pool, user_id: str) -> Dict[str, Any]:
    """Delete GitHub OAuth tokens for a user"""
    try:
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM oauth_github_tokens WHERE user_id = $1",
                user_id
            )
            
            logger.info(f"Deleted GitHub OAuth tokens for user {user_id}")
            return {
                'success': True,
                'user_id': user_id,
                'message': 'GitHub OAuth tokens deleted successfully'
            }
            
    except Exception as e:
        logger.error(f"Failed to delete GitHub OAuth tokens for user {user_id}: {e}")
        return {
            'success': False,
            'error': str(e),
            'user_id': user_id
        }

async def refresh_github_tokens_if_needed(db_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Check and refresh GitHub tokens if they're expired"""
    try:
        tokens = await get_github_tokens(db_pool, user_id)
        
        if not tokens:
            logger.warning(f"No GitHub tokens found for user {user_id}")
            return None
        
        # Check if token needs refresh
        needs_refresh = tokens.get('expired', False)
        
        if not needs_refresh:
            # Token is still valid
            return tokens
        
        # Note: GitHub tokens don't have refresh tokens
        # User needs to re-authenticate
        logger.error(f"GitHub token expired for user {user_id} - re-authentication required")
        return None
            
    except Exception as e:
        logger.error(f"Error refreshing GitHub tokens for user {user_id}: {e}")
        return None

async def get_all_github_users(db_pool) -> list:
    """Get all users with GitHub OAuth tokens"""
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT user_id, created_at, updated_at, expires_at
                FROM oauth_github_tokens
                ORDER BY updated_at DESC
            """)
            
            users = []
            for row in rows:
                users.append({
                    'user_id': row['user_id'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at'],
                    'expires_at': row['expires_at']
                })
            
            logger.debug(f"Retrieved {len(users)} users with GitHub OAuth tokens")
            return users
            
    except Exception as e:
        logger.error(f"Failed to get GitHub users: {e}")
        return []

async def cleanup_expired_github_tokens(db_pool) -> Dict[str, Any]:
    """Clean up expired GitHub tokens (older than 30 days)"""
    try:
        async with db_pool.acquire() as conn:
            # Delete tokens expired for more than 30 days
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
            
            result = await conn.execute("""
                DELETE FROM oauth_github_tokens 
                WHERE expires_at IS NOT NULL 
                AND expires_at < $1
            """, cutoff_date)
            
            logger.info(f"Cleaned up expired GitHub OAuth tokens older than {cutoff_date}")
            return {
                'success': True,
                'message': 'Expired GitHub tokens cleanup completed',
                'cutoff_date': cutoff_date.isoformat()
            }
            
    except Exception as e:
        logger.error(f"Failed to cleanup expired GitHub tokens: {e}")
        return {
            'success': False,
            'error': str(e)
        }

# Convenience function aliases
async def save_user_github_tokens(db_pool, user_id: str, **kwargs) -> Dict[str, Any]:
    """Alias for save_github_tokens with user_id parameter"""
    return await save_github_tokens(db_pool, user_id, **kwargs)

async def get_user_github_tokens(db_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Alias for get_github_tokens"""
    return await get_github_tokens(db_pool, user_id)

async def delete_user_github_tokens(db_pool, user_id: str) -> Dict[str, Any]:
    """Alias for delete_github_tokens"""
    return await delete_github_tokens(db_pool, user_id)