import logging
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

async def get_user_jira_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """Get Jira tokens for a user from database"""
    try:
        # Try to import database functions from existing modules
        try:
            from .db_oauth_gdrive import get_tokens
            # Reuse the generic OAuth token storage
            from flask import current_app
            
            db_conn_pool = getattr(current_app, "db_pool", None) or current_app.config.get("DB_CONNECTION_POOL", None)
            if not db_conn_pool:
                logger.error("Jira: Database connection pool not available")
                return None
                
            tokens = await get_tokens(db_conn_pool, user_id, "jira")
            return tokens
            
        except ImportError:
            logger.warning("Jira: Using mock token storage (database not available)")
            # Mock implementation for testing
            return {
                'user_id': user_id,
                'access_token': 'mock_access_token',
                'refresh_token': 'mock_refresh_token',
                'expires_in': 3600,
                'scope': 'read:jira-work read:jira-user write:jira-work',
                'token_type': 'Bearer',
                'created_at': datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Jira: Error getting tokens for user {user_id}: {e}")
        return None

async def save_user_jira_tokens(user_id: str, token_data: Dict[str, Any]) -> Dict[str, Any]:
    """Save Jira tokens for a user to database"""
    try:
        # Try to import database functions from existing modules
        try:
            from .db_oauth_gdrive import store_tokens
            from flask import current_app
            
            db_conn_pool = getattr(current_app, "db_pool", None) or current_app.config.get("DB_CONNECTION_POOL", None)
            if not db_conn_pool:
                logger.error("Jira: Database connection pool not available")
                return {"success": False, "error": "Database not available"}
            
            # Calculate expires_at
            expires_in = token_data.get('expires_in', 3600)
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
            
            # Store tokens using generic OAuth storage
            await store_tokens(
                db_conn_pool=db_conn_pool,
                user_id=user_id,
                service_name="jira",
                access_token=token_data.get('access_token'),
                refresh_token=token_data.get('refresh_token'),
                expires_at=expires_at,
                scope=token_data.get('scope', '')
            )
            
            logger.info(f"Jira: Tokens saved successfully for user {user_id}")
            return {"success": True, "message": "Tokens saved successfully"}
            
        except ImportError:
            logger.warning("Jira: Using mock token storage (database not available)")
            # Mock implementation for testing
            logger.info(f"Jira: Mock saving tokens for user {user_id}")
            return {"success": True, "message": "Tokens saved (mock)"}
            
    except Exception as e:
        logger.error(f"Jira: Error saving tokens for user {user_id}: {e}")
        return {"success": False, "error": str(e)}

async def save_tokens(db_conn_pool, user_id: str, encrypted_access_token: bytes, encrypted_refresh_token: bytes, expires_at: datetime, scope: str):
    """
    Save Jira OAuth tokens for a user.

    Args:
        db_conn_pool: Database connection pool
        user_id: User identifier
        encrypted_access_token: Encrypted access token
        encrypted_refresh_token: Encrypted refresh token
        expires_at: Token expiration time
        scope: OAuth scope
    """
    sql = """
        INSERT INTO user_jira_oauth_tokens (user_id, encrypted_access_token, encrypted_refresh_token, expires_at, scope, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE SET
            encrypted_access_token = EXCLUDED.encrypted_access_token,
            encrypted_refresh_token = EXCLUDED.encrypted_refresh_token,
            expires_at = EXCLUDED.expires_at,
            scope = EXCLUDED.scope,
            updated_at = %s;
    """
    now = datetime.now(timezone.utc)
    try:
        with db_conn_pool.getconn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (user_id, encrypted_access_token, encrypted_refresh_token, expires_at, scope, now, now, now))
            conn.commit()
    except Exception as e:
        logger.error(f"Error saving Jira OAuth tokens for user {user_id}: {e}")
        raise
    finally:
        db_conn_pool.putconn(conn)

async def get_tokens(db_conn_pool, user_id: str):
    """
    Get Jira OAuth tokens for a user.

    Args:
        db_conn_pool: Database connection pool
        user_id: User identifier

    Returns:
        Tuple of (encrypted_access_token, encrypted_refresh_token, expires_at) or None if not found
    """
    sql = "SELECT encrypted_access_token, encrypted_refresh_token, expires_at FROM user_jira_oauth_tokens WHERE user_id = %s;"
    try:
        with db_conn_pool.getconn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (user_id,))
                return cur.fetchone()
    except Exception as e:
        logger.error(f"Error getting Jira OAuth tokens for user {user_id}: {e}")
        return None
    finally:
        db_conn_pool.putconn(conn)

async def delete_tokens(db_conn_pool, user_id: str):
    """
    Delete Jira OAuth tokens for a user.

    Args:
        db_conn_pool: Database connection pool
        user_id: User identifier
    """
    sql = "DELETE FROM user_jira_oauth_tokens WHERE user_id = %s;"
    try:
        with db_conn_pool.getconn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (user_id,))
            conn.commit()
    except Exception as e:
        logger.error(f"Error deleting Jira OAuth tokens for user {user_id}: {e}")
        raise
    finally:
        db_conn_pool.putconn(conn)

async def token_exists(db_conn_pool, user_id: str) -> bool:
    """
    Check if Jira OAuth tokens exist for a user.

    Args:
        db_conn_pool: Database connection pool
        user_id: User identifier

    Returns:
        True if tokens exist, False otherwise
    """
    sql = "SELECT 1 FROM user_jira_oauth_tokens WHERE user_id = %s;"
    try:
        with db_conn_pool.getconn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (user_id,))
                return cur.fetchone() is not None
    except Exception as e:
        logger.error(f"Error checking Jira OAuth tokens for user {user_id}: {e}")
        return False
    finally:
        db_conn_pool.putconn(conn)

async def get_token_expiry(db_conn_pool, user_id: str):
    """
    Get the expiration time of Jira OAuth tokens for a user.

    Args:
        db_conn_pool: Database connection pool
        user_id: User identifier

    Returns:
        Expiration datetime or None if not found
    """
    sql = "SELECT expires_at FROM user_jira_oauth_tokens WHERE user_id = %s;"
    try:
        with db_conn_pool.getconn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (user_id,))
                result = cur.fetchone()
                return result[0] if result else None
    except Exception as e:
        logger.error(f"Error getting Jira token expiry for user {user_id}: {e}")
        return None
    finally:
        db_conn_pool.putconn(conn)
