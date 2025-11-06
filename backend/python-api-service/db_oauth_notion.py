"""
Notion OAuth Database Handler
Secure token storage and management for Notion integration
"""

import os
import asyncpg
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

async def init_notion_oauth_table(db_pool):
    """Initialize Notion OAuth tokens table"""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS oauth_notion_tokens (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    access_token TEXT NOT NULL,
                    workspace_id VARCHAR(255),
                    workspace_name VARCHAR(255),
                    workspace_icon TEXT,
                    bot_id VARCHAR(255),
                    owner_data JSONB,
                    duplicated_template_id VARCHAR(255),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id)
                )
            """)
            
            # Create indexes
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_oauth_notion_user_id 
                ON oauth_notion_tokens(user_id)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_oauth_notion_workspace_id 
                ON oauth_notion_tokens(workspace_id)
            """)
            
            logger.info("Notion OAuth tokens table initialized successfully")
            
    except Exception as e:
        logger.error(f"Failed to initialize Notion OAuth tokens table: {e}")
        raise

async def save_notion_tokens(
    db_pool,
    user_id: str,
    access_token: str,
    workspace_id: str = None,
    workspace_name: str = None,
    workspace_icon: str = None,
    bot_id: str = None,
    owner_data: Dict[str, Any] = None,
    duplicated_template_id: str = None
) -> Dict[str, Any]:
    """Save or update Notion OAuth tokens"""
    try:
        async with db_pool.acquire() as conn:
            # Check if user already has tokens
            existing = await conn.fetchrow(
                "SELECT id FROM oauth_notion_tokens WHERE user_id = $1",
                user_id
            )
            
            if existing:
                # Update existing tokens
                await conn.execute("""
                    UPDATE oauth_notion_tokens 
                    SET access_token = $2, 
                        workspace_id = $3,
                        workspace_name = $4,
                        workspace_icon = $5,
                        bot_id = $6,
                        owner_data = $7,
                        duplicated_template_id = $8,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = $1
                """, user_id, access_token, workspace_id, workspace_name, 
                    workspace_icon, bot_id, owner_data, duplicated_template_id)
                
                logger.info(f"Updated Notion OAuth tokens for user {user_id}")
            else:
                # Insert new tokens
                await conn.execute("""
                    INSERT INTO oauth_notion_tokens 
                    (user_id, access_token, workspace_id, workspace_name, 
                     workspace_icon, bot_id, owner_data, duplicated_template_id)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """, user_id, access_token, workspace_id, workspace_name,
                    workspace_icon, bot_id, owner_data, duplicated_template_id)
                
                logger.info(f"Stored new Notion OAuth tokens for user {user_id}")
            
            return {
                'success': True,
                'user_id': user_id,
                'message': 'Notion OAuth tokens stored successfully'
            }
            
    except Exception as e:
        logger.error(f"Failed to store Notion OAuth tokens for user {user_id}: {e}")
        return {
            'success': False,
            'error': str(e),
            'user_id': user_id
        }

async def get_notion_tokens(db_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Get Notion OAuth tokens for a user"""
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT access_token, workspace_id, workspace_name, workspace_icon, 
                       bot_id, owner_data, duplicated_template_id, 
                       created_at, updated_at
                FROM oauth_notion_tokens 
                WHERE user_id = $1
            """, user_id)
            
            if row:
                tokens = {
                    'access_token': row['access_token'],
                    'workspace_id': row['workspace_id'],
                    'workspace_name': row['workspace_name'],
                    'workspace_icon': row['workspace_icon'],
                    'bot_id': row['bot_id'],
                    'owner_data': row['owner_data'],
                    'duplicated_template_id': row['duplicated_template_id'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                }
                
                logger.debug(f"Retrieved Notion OAuth tokens for user {user_id}")
                return tokens
            else:
                logger.info(f"No Notion OAuth tokens found for user {user_id}")
                return None
                
    except Exception as e:
        logger.error(f"Failed to get Notion OAuth tokens for user {user_id}: {e}")
        return None

async def update_notion_tokens(
    db_pool,
    user_id: str,
    access_token: str = None,
    workspace_id: str = None,
    workspace_name: str = None
) -> Dict[str, Any]:
    """Update specific Notion OAuth token fields"""
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
            
            if workspace_id is not None:
                updates.append(f"workspace_id = ${param_index}")
                params.append(workspace_id)
                param_index += 1
            
            if workspace_name is not None:
                updates.append(f"workspace_name = ${param_index}")
                params.append(workspace_name)
                param_index += 1
            
            updates.append("updated_at = CURRENT_TIMESTAMP")
            
            if updates:
                query = f"""
                    UPDATE oauth_notion_tokens 
                    SET {', '.join(updates)}
                    WHERE user_id = ${param_index}
                """
                params.append(user_id)
                
                result = await conn.execute(query, *params)
                
                logger.info(f"Updated Notion OAuth tokens for user {user_id}")
                return {
                    'success': True,
                    'user_id': user_id,
                    'message': 'Notion OAuth tokens updated successfully'
                }
            else:
                return {
                    'success': False,
                    'error': 'No fields to update',
                    'user_id': user_id
                }
                
    except Exception as e:
        logger.error(f"Failed to update Notion OAuth tokens for user {user_id}: {e}")
        return {
            'success': False,
            'error': str(e),
            'user_id': user_id
        }

async def delete_notion_tokens(db_pool, user_id: str) -> Dict[str, Any]:
    """Delete Notion OAuth tokens for a user"""
    try:
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM oauth_notion_tokens WHERE user_id = $1",
                user_id
            )
            
            logger.info(f"Deleted Notion OAuth tokens for user {user_id}")
            return {
                'success': True,
                'user_id': user_id,
                'message': 'Notion OAuth tokens deleted successfully'
            }
            
    except Exception as e:
        logger.error(f"Failed to delete Notion OAuth tokens for user {user_id}: {e}")
        return {
            'success': False,
            'error': str(e),
            'user_id': user_id
        }

async def get_all_notion_users(db_pool) -> list:
    """Get all users with Notion OAuth tokens"""
    try:
        async with db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT user_id, workspace_id, workspace_name, workspace_icon, 
                       bot_id, created_at, updated_at
                FROM oauth_notion_tokens
                ORDER BY updated_at DESC
            """)
            
            users = []
            for row in rows:
                users.append({
                    'user_id': row['user_id'],
                    'workspace_id': row['workspace_id'],
                    'workspace_name': row['workspace_name'],
                    'workspace_icon': row['workspace_icon'],
                    'bot_id': row['bot_id'],
                    'created_at': row['created_at'],
                    'updated_at': row['updated_at']
                })
            
            logger.debug(f"Retrieved {len(users)} users with Notion OAuth tokens")
            return users
            
    except Exception as e:
        logger.error(f"Failed to get Notion users: {e}")
        return []

async def cleanup_expired_notion_tokens(db_pool) -> Dict[str, Any]:
    """Clean up old Notion tokens (older than 30 days without update)"""
    try:
        async with db_pool.acquire() as conn:
            # Delete tokens not updated for more than 30 days
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=30)
            
            result = await conn.execute("""
                DELETE FROM oauth_notion_tokens 
                WHERE updated_at < $1
            """, cutoff_date)
            
            logger.info(f"Cleaned up old Notion OAuth tokens older than {cutoff_date}")
            return {
                'success': True,
                'message': 'Old Notion tokens cleanup completed',
                'cutoff_date': cutoff_date.isoformat()
            }
            
    except Exception as e:
        logger.error(f"Failed to cleanup old Notion tokens: {e}")
        return {
            'success': False,
            'error': str(e)
        }

# Convenience function aliases
async def save_user_notion_tokens(db_pool, user_id: str, **kwargs) -> Dict[str, Any]:
    """Alias for save_notion_tokens with user_id parameter"""
    return await save_notion_tokens(db_pool, user_id, **kwargs)

async def get_user_notion_tokens(db_pool, user_id: str) -> Optional[Dict[str, Any]]:
    """Alias for get_notion_tokens"""
    return await get_notion_tokens(db_pool, user_id)

async def delete_user_notion_tokens(db_pool, user_id: str) -> Dict[str, Any]:
    """Alias for delete_notion_tokens"""
    return await delete_notion_tokens(db_pool, user_id)