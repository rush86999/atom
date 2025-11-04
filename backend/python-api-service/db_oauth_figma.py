"""
Figma OAuth Token Database Operations
Secure storage for Figma OAuth tokens in PostgreSQL
"""

import logging
from datetime import datetime, timezone
import base64

logger = logging.getLogger(__name__)

async def save_tokens(db_conn_pool, user_id: str, access_token: str, refresh_token: str, expires_at: datetime, scope: str, user_info: dict = None):
    """Save Figma OAuth tokens"""
    sql = """
        INSERT INTO user_figma_oauth_tokens 
        (user_id, access_token, refresh_token, expires_at, scope, user_info, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE SET
            access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            expires_at = EXCLUDED.expires_at,
            scope = EXCLUDED.scope,
            user_info = EXCLUDED.user_info,
            updated_at = EXCLUDED.updated_at
    """
    
    conn = await db_conn_pool.acquire()
    try:
        now = datetime.now(timezone.utc)
        
        await conn.execute(
            sql,
            (
                user_id,
                access_token,
                refresh_token,
                expires_at,
                scope,
                user_info,
                now,
                now
            )
        )
        
        await conn.commit()
        logger.info(f"Successfully saved Figma tokens for user {user_id}")
        
    except Exception as e:
        await conn.rollback()
        logger.error(f"Error saving Figma tokens for user {user_id}: {e}")
        raise
    finally:
        await db_conn_pool.release(conn)

async def get_tokens(db_conn_pool, user_id: str):
    """Get Figma OAuth tokens for user"""
    sql = """
        SELECT access_token, refresh_token, expires_at, scope, user_info, updated_at
        FROM user_figma_oauth_tokens
        WHERE user_id = %s
    """
    
    conn = await db_conn_pool.acquire()
    try:
        result = await conn.execute(sql, (user_id,))
        row = await result.fetchone()
        
        if not row:
            logger.warning(f"No Figma tokens found for user {user_id}")
            return None
        
        tokens = {
            'access_token': row['access_token'],
            'refresh_token': row['refresh_token'],
            'expires_at': row['expires_at'],
            'scope': row['scope'],
            'user_info': row['user_info'],
            'updated_at': row['updated_at']
        }
        
        # Check if tokens are expired
        if datetime.now(timezone.utc) >= tokens['expires_at']:
            logger.warning(f"Figma tokens for user {user_id} are expired")
            return None
        
        logger.info(f"Successfully retrieved Figma tokens for user {user_id}")
        return tokens
        
    except Exception as e:
        logger.error(f"Error retrieving Figma tokens for user {user_id}: {e}")
        raise
    finally:
        await db_conn_pool.release(conn)

async def delete_tokens(db_conn_pool, user_id: str):
    """Delete Figma OAuth tokens for user"""
    sql = "DELETE FROM user_figma_oauth_tokens WHERE user_id = %s"
    
    conn = await db_conn_pool.acquire()
    try:
        await conn.execute(sql, (user_id,))
        await conn.commit()
        logger.info(f"Successfully deleted Figma tokens for user {user_id}")
        
    except Exception as e:
        await conn.rollback()
        logger.error(f"Error deleting Figma tokens for user {user_id}: {e}")
        raise
    finally:
        await db_conn_pool.release(conn)

async def get_user_figma_files(db_conn_pool, user_id: str, file_ids: list = None):
    """Get Figma files for user from database"""
    if not file_ids:
        return []
    
    # Create placeholders for IN clause
    placeholders = ','.join(['%s'] * len(file_ids))
    sql = f"""
        SELECT file_id, name, key, last_modified, thumbnail_url, created_at
        FROM user_figma_files
        WHERE user_id = %s AND file_id IN ({placeholders})
        ORDER BY last_modified DESC
    """
    
    conn = await db_conn_pool.acquire()
    try:
        result = await conn.execute(sql, [user_id] + file_ids)
        rows = await result.fetchall()
        
        files = []
        for row in rows:
            files.append({
                'file_id': row['file_id'],
                'name': row['name'],
                'key': row['key'],
                'last_modified': row['last_modified'],
                'thumbnail_url': row['thumbnail_url'],
                'created_at': row['created_at']
            })
        
        logger.info(f"Successfully retrieved {len(files)} Figma files for user {user_id}")
        return files
        
    except Exception as e:
        logger.error(f"Error retrieving Figma files for user {user_id}: {e}")
        raise
    finally:
        await db_conn_pool.release(conn)

async def save_figma_file(db_conn_pool, user_id: str, file_data: dict):
    """Save Figma file metadata"""
    sql = """
        INSERT INTO user_figma_files 
        (user_id, file_id, name, key, last_modified, thumbnail_url, metadata, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, file_id) DO UPDATE SET
            name = EXCLUDED.name,
            key = EXCLUDED.key,
            last_modified = EXCLUDED.last_modified,
            thumbnail_url = EXCLUDED.thumbnail_url,
            metadata = EXCLUDED.metadata,
            updated_at = EXCLUDED.updated_at
    """
    
    conn = await db_conn_pool.acquire()
    try:
        now = datetime.now(timezone.utc)
        
        await conn.execute(
            sql,
            (
                user_id,
                file_data['file_id'],
                file_data['name'],
                file_data['key'],
                file_data.get('last_modified'),
                file_data.get('thumbnail_url'),
                file_data.get('metadata'),
                now,
                now
            )
        )
        
        await conn.commit()
        logger.debug(f"Successfully saved Figma file {file_data['name']} for user {user_id}")
        
    except Exception as e:
        await conn.rollback()
        logger.error(f"Error saving Figma file for user {user_id}: {e}")
        raise
    finally:
        await db_conn_pool.release(conn)

async def get_user_figma_components(db_conn_pool, user_id: str, component_keys: list = None):
    """Get Figma components for user from database"""
    if not component_keys:
        return []
    
    # Create placeholders for IN clause
    placeholders = ','.join(['%s'] * len(component_keys))
    sql = f"""
        SELECT component_key, name, file_key, node_id, component_type, thumbnail_url, created_at
        FROM user_figma_components
        WHERE user_id = %s AND component_key IN ({placeholders})
        ORDER BY created_at DESC
    """
    
    conn = await db_conn_pool.acquire()
    try:
        result = await conn.execute(sql, [user_id] + component_keys)
        rows = await result.fetchall()
        
        components = []
        for row in rows:
            components.append({
                'component_key': row['component_key'],
                'name': row['name'],
                'file_key': row['file_key'],
                'node_id': row['node_id'],
                'component_type': row['component_type'],
                'thumbnail_url': row['thumbnail_url'],
                'created_at': row['created_at']
            })
        
        logger.info(f"Successfully retrieved {len(components)} Figma components for user {user_id}")
        return components
        
    except Exception as e:
        logger.error(f"Error retrieving Figma components for user {user_id}: {e}")
        raise
    finally:
        await db_conn_pool.release(conn)

async def save_figma_component(db_conn_pool, user_id: str, component_data: dict):
    """Save Figma component metadata"""
    sql = """
        INSERT INTO user_figma_components 
        (user_id, component_key, name, file_key, node_id, component_type, thumbnail_url, metadata, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, component_key) DO UPDATE SET
            name = EXCLUDED.name,
            file_key = EXCLUDED.file_key,
            node_id = EXCLUDED.node_id,
            component_type = EXCLUDED.component_type,
            thumbnail_url = EXCLUDED.thumbnail_url,
            metadata = EXCLUDED.metadata,
            updated_at = EXCLUDED.updated_at
    """
    
    conn = await db_conn_pool.acquire()
    try:
        now = datetime.now(timezone.utc)
        
        await conn.execute(
            sql,
            (
                user_id,
                component_data['component_key'],
                component_data['name'],
                component_data['file_key'],
                component_data['node_id'],
                component_data['component_type'],
                component_data.get('thumbnail_url'),
                component_data.get('metadata'),
                now,
                now
            )
        )
        
        await conn.commit()
        logger.debug(f"Successfully saved Figma component {component_data['name']} for user {user_id}")
        
    except Exception as e:
        await conn.rollback()
        logger.error(f"Error saving Figma component for user {user_id}: {e}")
        raise
    finally:
        await db_conn_pool.release(conn)

async def get_figma_webhooks(db_conn_pool, user_id: str):
    """Get Figma webhooks for user"""
    sql = """
        SELECT webhook_id, file_id, endpoint_url, events, active, created_at
        FROM user_figma_webhooks
        WHERE user_id = %s
        ORDER BY created_at DESC
    """
    
    conn = await db_conn_pool.acquire()
    try:
        result = await conn.execute(sql, (user_id,))
        rows = await result.fetchall()
        
        webhooks = []
        for row in rows:
            webhooks.append({
                'webhook_id': row['webhook_id'],
                'file_id': row['file_id'],
                'endpoint_url': row['endpoint_url'],
                'events': row['events'],
                'active': row['active'],
                'created_at': row['created_at']
            })
        
        logger.info(f"Successfully retrieved {len(webhooks)} Figma webhooks for user {user_id}")
        return webhooks
        
    except Exception as e:
        logger.error(f"Error retrieving Figma webhooks for user {user_id}: {e}")
        raise
    finally:
        await db_conn_pool.release(conn)

async def save_figma_webhook(db_conn_pool, user_id: str, webhook_data: dict):
    """Save Figma webhook configuration"""
    sql = """
        INSERT INTO user_figma_webhooks 
        (user_id, webhook_id, file_id, endpoint_url, events, active, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, webhook_id) DO UPDATE SET
            endpoint_url = EXCLUDED.endpoint_url,
            events = EXCLUDED.events,
            active = EXCLUDED.active,
            updated_at = EXCLUDED.updated_at
    """
    
    conn = await db_conn_pool.acquire()
    try:
        now = datetime.now(timezone.utc)
        
        await conn.execute(
            sql,
            (
                user_id,
                webhook_data['webhook_id'],
                webhook_data['file_id'],
                webhook_data['endpoint_url'],
                webhook_data['events'],
                webhook_data['active'],
                now,
                now
            )
        )
        
        await conn.commit()
        logger.info(f"Successfully saved Figma webhook {webhook_data['webhook_id']} for user {user_id}")
        
    except Exception as e:
        await conn.rollback()
        logger.error(f"Error saving Figma webhook for user {user_id}: {e}")
        raise
    finally:
        await db_conn_pool.release(conn)

# Helper functions
async def get_all_users_with_figma_tokens(db_conn_pool):
    """Get all users with valid Figma tokens"""
    sql = """
        SELECT user_id, access_token, refresh_token, expires_at, scope, user_info, updated_at
        FROM user_figma_oauth_tokens
        WHERE expires_at > %s
        ORDER BY updated_at DESC
    """
    
    conn = await db_conn_pool.acquire()
    try:
        now = datetime.now(timezone.utc)
        result = await conn.execute(sql, (now,))
        rows = await result.fetchall()
        
        users = []
        for row in rows:
            users.append({
                'user_id': row['user_id'],
                'access_token': row['access_token'],
                'refresh_token': row['refresh_token'],
                'expires_at': row['expires_at'],
                'scope': row['scope'],
                'user_info': row['user_info'],
                'updated_at': row['updated_at']
            })
        
        logger.info(f"Successfully retrieved {len(users)} users with Figma tokens")
        return users
        
    except Exception as e:
        logger.error(f"Error retrieving users with Figma tokens: {e}")
        raise
    finally:
        await db_conn_pool.release(conn)

async def refresh_figma_tokens(db_conn_pool, user_id: str, new_access_token: str, new_refresh_token: str, expires_at: datetime, scope: str):
    """Refresh Figma OAuth tokens"""
    sql = """
        UPDATE user_figma_oauth_tokens
        SET access_token = %s, refresh_token = %s, expires_at = %s, scope = %s, updated_at = %s
        WHERE user_id = %s
    """
    
    conn = await db_conn_pool.acquire()
    try:
        now = datetime.now(timezone.utc)
        
        await conn.execute(
            sql,
            (new_access_token, new_refresh_token, expires_at, scope, now, user_id)
        )
        
        await conn.commit()
        logger.info(f"Successfully refreshed Figma tokens for user {user_id}")
        
    except Exception as e:
        await conn.rollback()
        logger.error(f"Error refreshing Figma tokens for user {user_id}: {e}")
        raise
    finally:
        await db_conn_pool.release(conn)

async def update_figma_user_info(db_conn_pool, user_id: str, user_info: dict):
    """Update Figma user information"""
    sql = """
        UPDATE user_figma_oauth_tokens
        SET user_info = %s, updated_at = %s
        WHERE user_id = %s
    """
    
    conn = await db_conn_pool.acquire()
    try:
        now = datetime.now(timezone.utc)
        
        await conn.execute(sql, (user_info, now, user_id))
        await conn.commit()
        logger.info(f"Successfully updated Figma user info for user {user_id}")
        
    except Exception as e:
        await conn.rollback()
        logger.error(f"Error updating Figma user info for user {user_id}: {e}")
        raise
    finally:
        await db_conn_pool.release(conn)