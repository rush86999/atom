"""
Database utilities for Notion OAuth tokens

This module provides functions for storing and retrieving Notion OAuth tokens
in the database with proper encryption.
"""

import os
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

# Try to import database dependencies
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    import psycopg2.pool

    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    logging.warning("psycopg2 not available - database operations will be disabled")

# Import crypto utilities for token encryption
try:
    from crypto_utils import encrypt_data, decrypt_data

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logging.warning("crypto_utils not available - token encryption will be disabled")

logger = logging.getLogger(__name__)

# Table name for Notion OAuth tokens
TABLE_NAME = "user_notion_oauth_tokens"


def save_tokens(
    db_conn_pool: Optional[psycopg2.pool.AbstractConnectionPool],
    user_id: str,
    access_token: str,
    refresh_token: str,
    bot_id: str,
    workspace_name: Optional[str] = None,
    workspace_id: Optional[str] = None,
    workspace_icon: Optional[str] = None,
    owner_data: Optional[Dict[str, Any]] = None,
    duplicated_template_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Save Notion OAuth tokens for a user.

    Args:
        db_conn_pool: Database connection pool
        user_id: User identifier
        access_token: Notion access token
        refresh_token: Notion refresh token
        bot_id: Notion bot ID
        workspace_name: Workspace name
        workspace_id: Workspace ID
        workspace_icon: Workspace icon URL
        owner_data: Owner information
        duplicated_template_id: Duplicated template ID

    Returns:
        Dict with operation status
    """
    if not PSYCOPG2_AVAILABLE or not db_conn_pool:
        logger.error("Database connection pool or psycopg2 is not available.")
        return {
            "ok": False,
            "error": {
                "code": "DB_UNAVAILABLE",
                "message": "Database connection is not configured.",
            },
        }

    if not CRYPTO_AVAILABLE:
        logger.error("Crypto utilities not available - cannot encrypt tokens")
        return {
            "ok": False,
            "error": {
                "code": "CRYPTO_UNAVAILABLE",
                "message": "Token encryption is not available.",
            },
        }

    try:
        # Encrypt tokens for secure storage
        encrypted_access_token = encrypt_data(access_token)
        encrypted_refresh_token = encrypt_data(refresh_token)

        # Serialize owner data to JSON string
        owner_json = None
        if owner_data:
            import json

            owner_json = json.dumps(owner_data)

        # Current timestamp
        now = datetime.now()

        sql = f"""
            INSERT INTO {TABLE_NAME} (
                user_id, encrypted_access_token, encrypted_refresh_token,
                bot_id, workspace_name, workspace_id, workspace_icon,
                owner_data, duplicated_template_id, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                encrypted_access_token = EXCLUDED.encrypted_access_token,
                encrypted_refresh_token = EXCLUDED.encrypted_refresh_token,
                bot_id = EXCLUDED.bot_id,
                workspace_name = EXCLUDED.workspace_name,
                workspace_id = EXCLUDED.workspace_id,
                workspace_icon = EXCLUDED.workspace_icon,
                owner_data = EXCLUDED.owner_data,
                duplicated_template_id = EXCLUDED.duplicated_template_id,
                updated_at = %s;
        """

        conn = None
        try:
            conn = db_conn_pool.getconn()
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        user_id,
                        encrypted_access_token,
                        encrypted_refresh_token,
                        bot_id,
                        workspace_name,
                        workspace_id,
                        workspace_icon,
                        owner_json,
                        duplicated_template_id,
                        now,
                        now,
                        now,
                    ),
                )
            conn.commit()
            logger.info(f"Successfully saved Notion OAuth tokens for user {user_id}")
            return {"ok": True, "message": "Tokens saved successfully"}

        except Exception as db_error:
            logger.error(
                f"Database error saving Notion tokens for user {user_id}: {db_error}"
            )
            if conn:
                conn.rollback()
            return {
                "ok": False,
                "error": {
                    "code": "DB_ERROR",
                    "message": f"Database error: {str(db_error)}",
                },
            }
        finally:
            if conn:
                db_conn_pool.putconn(conn)

    except Exception as e:
        logger.error(f"Error saving Notion OAuth tokens for user {user_id}: {e}")
        return {
            "ok": False,
            "error": {
                "code": "SAVE_ERROR",
                "message": f"Failed to save tokens: {str(e)}",
            },
        }


def get_tokens(
    db_conn_pool: Optional[psycopg2.pool.AbstractConnectionPool], user_id: str
) -> Optional[Dict[str, Any]]:
    """
    Get Notion OAuth tokens for a user.

    Args:
        db_conn_pool: Database connection pool
        user_id: User identifier

    Returns:
        Dict with decrypted tokens and metadata, or None if not found
    """
    if not PSYCOPG2_AVAILABLE or not db_conn_pool:
        logger.error("Database connection pool or psycopg2 is not available.")
        return None

    if not CRYPTO_AVAILABLE:
        logger.error("Crypto utilities not available - cannot decrypt tokens")
        return None

    sql = f"""
        SELECT
            encrypted_access_token, encrypted_refresh_token,
            bot_id, workspace_name, workspace_id, workspace_icon,
            owner_data, duplicated_template_id, created_at, updated_at
        FROM {TABLE_NAME}
        WHERE user_id = %s;
    """

    conn = None
    try:
        conn = db_conn_pool.getconn()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (user_id,))
            result = cur.fetchone()

        if not result:
            logger.info(f"No Notion OAuth tokens found for user {user_id}")
            return None

        # Decrypt tokens
        try:
            access_token = decrypt_data(result["encrypted_access_token"])
            refresh_token = decrypt_data(result["encrypted_refresh_token"])
        except Exception as decrypt_error:
            logger.error(
                f"Failed to decrypt Notion tokens for user {user_id}: {decrypt_error}"
            )
            return None

        # Parse owner data from JSON
        owner_data = None
        if result["owner_data"]:
            try:
                import json

                owner_data = json.loads(result["owner_data"])
            except Exception as json_error:
                logger.warning(
                    f"Failed to parse owner data for user {user_id}: {json_error}"
                )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "bot_id": result["bot_id"],
            "workspace_name": result["workspace_name"],
            "workspace_id": result["workspace_id"],
            "workspace_icon": result["workspace_icon"],
            "owner": owner_data,
            "duplicated_template_id": result["duplicated_template_id"],
            "created_at": result["created_at"],
            "updated_at": result["updated_at"],
        }

    except Exception as e:
        logger.error(f"Error getting Notion OAuth tokens for user {user_id}: {e}")
        return None
    finally:
        if conn:
            db_conn_pool.putconn(conn)


def delete_tokens(
    db_conn_pool: Optional[psycopg2.pool.AbstractConnectionPool], user_id: str
) -> Dict[str, Any]:
    """
    Delete Notion OAuth tokens for a user.

    Args:
        db_conn_pool: Database connection pool
        user_id: User identifier

    Returns:
        Dict with operation status
    """
    if not PSYCOPG2_AVAILABLE or not db_conn_pool:
        logger.error("Database connection pool or psycopg2 is not available.")
        return {
            "ok": False,
            "error": {
                "code": "DB_UNAVAILABLE",
                "message": "Database connection is not configured.",
            },
        }

    sql = f"DELETE FROM {TABLE_NAME} WHERE user_id = %s;"

    conn = None
    try:
        conn = db_conn_pool.getconn()
        with conn.cursor() as cur:
            cur.execute(sql, (user_id,))
        conn.commit()
        logger.info(f"Successfully deleted Notion OAuth tokens for user {user_id}")
        return {"ok": True, "message": "Tokens deleted successfully"}

    except Exception as e:
        logger.error(f"Error deleting Notion OAuth tokens for user {user_id}: {e}")
        if conn:
            conn.rollback()
        return {
            "ok": False,
            "error": {
                "code": "DELETE_ERROR",
                "message": f"Failed to delete tokens: {str(e)}",
            },
        }
    finally:
        if conn:
            db_conn_pool.putconn(conn)


def update_tokens(
    db_conn_pool: Optional[psycopg2.pool.AbstractConnectionPool],
    user_id: str,
    access_token: str,
    refresh_token: str,
    bot_id: Optional[str] = None,
    workspace_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update Notion OAuth tokens for a user.

    Args:
        db_conn_pool: Database connection pool
        user_id: User identifier
        access_token: New access token
        refresh_token: New refresh token
        bot_id: Optional bot ID update
        workspace_name: Optional workspace name update

    Returns:
        Dict with operation status
    """
    if not PSYCOPG2_AVAILABLE or not db_conn_pool:
        logger.error("Database connection pool or psycopg2 is not available.")
        return {
            "ok": False,
            "error": {
                "code": "DB_UNAVAILABLE",
                "message": "Database connection is not configured.",
            },
        }

    if not CRYPTO_AVAILABLE:
        logger.error("Crypto utilities not available - cannot encrypt tokens")
        return {
            "ok": False,
            "error": {
                "code": "CRYPTO_UNAVAILABLE",
                "message": "Token encryption is not available.",
            },
        }

    try:
        # Encrypt tokens for secure storage
        encrypted_access_token = encrypt_data(access_token)
        encrypted_refresh_token = encrypt_data(refresh_token)

        # Current timestamp
        now = datetime.now()

        # Build dynamic update query
        update_fields = [
            "encrypted_access_token = %s",
            "encrypted_refresh_token = %s",
            "updated_at = %s",
        ]
        params = [encrypted_access_token, encrypted_refresh_token, now]

        if bot_id:
            update_fields.append("bot_id = %s")
            params.append(bot_id)

        if workspace_name:
            update_fields.append("workspace_name = %s")
            params.append(workspace_name)

        sql = f"""
            UPDATE {TABLE_NAME}
            SET {", ".join(update_fields)}
            WHERE user_id = %s;
        """
        params.append(user_id)

        conn = None
        try:
            conn = db_conn_pool.getconn()
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
            conn.commit()
            logger.info(f"Successfully updated Notion OAuth tokens for user {user_id}")
            return {"ok": True, "message": "Tokens updated successfully"}

        except Exception as db_error:
            logger.error(
                f"Database error updating Notion tokens for user {user_id}: {db_error}"
            )
            if conn:
                conn.rollback()
            return {
                "ok": False,
                "error": {
                    "code": "DB_ERROR",
                    "message": f"Database error: {str(db_error)}",
                },
            }
        finally:
            if conn:
                db_conn_pool.putconn(conn)

    except Exception as e:
        logger.error(f"Error updating Notion OAuth tokens for user {user_id}: {e}")
        return {
            "ok": False,
            "error": {
                "code": "UPDATE_ERROR",
                "message": f"Failed to update tokens: {str(e)}",
            },
        }


def get_user_workspaces(
    db_conn_pool: Optional[psycopg2.pool.AbstractConnectionPool],
) -> Dict[str, Any]:
    """
    Get all Notion workspaces connected by users.

    Args:
        db_conn_pool: Database connection pool

    Returns:
        Dict with workspaces data
    """
    if not PSYCOPG2_AVAILABLE or not db_conn_pool:
        logger.error("Database connection pool or psycopg2 is not available.")
        return {
            "ok": False,
            "error": {
                "code": "DB_UNAVAILABLE",
                "message": "Database connection is not configured.",
            },
        }

    sql = f"""
        SELECT
            user_id, bot_id, workspace_name, workspace_id, workspace_icon,
            created_at, updated_at
        FROM {TABLE_NAME}
        ORDER BY updated_at DESC;
    """

    conn = None
    try:
        conn = db_conn_pool.getconn()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql)
            results = cur.fetchall()

        workspaces = []
        for row in results:
            workspaces.append(
                {
                    "user_id": row["user_id"],
                    "bot_id": row["bot_id"],
                    "workspace_name": row["workspace_name"],
                    "workspace_id": row["workspace_id"],
                    "workspace_icon": row["workspace_icon"],
                    "connected_at": row["created_at"],
                    "last_updated": row["updated_at"],
                }
            )

        return {
            "ok": True,
            "data": {"workspaces": workspaces, "total_count": len(workspaces)},
        }

    except Exception as e:
        logger.error(f"Error getting Notion user workspaces: {e}")
        return {
            "ok": False,
            "error": {
                "code": "QUERY_ERROR",
                "message": f"Failed to get workspaces: {str(e)}",
            },
        }
    finally:
        if conn:
            db_conn_pool.putconn(conn)

async def get_user_notion_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """Get Notion tokens for a user from database"""
    try:
        # Try to use generic OAuth storage first
        try:
            from .db_oauth_gdrive import get_tokens
            from flask import current_app
            
            db_conn_pool = getattr(current_app, "db_pool", None) or current_app.config.get("DB_CONNECTION_POOL", None)
            if not db_conn_pool:
                logger.error("Notion: Database connection pool not available")
                return None
                
            tokens = await get_tokens(db_conn_pool, user_id, "notion")
            return tokens
            
        except ImportError:
            logger.warning("Notion: Using mock token storage (database not available)")
            # Mock implementation for testing
            return {
                'user_id': user_id,
                'access_token': 'mock_access_token',
                'bot_id': 'mock_bot_id',
                'workspace_name': 'Mock Workspace',
                'workspace_id': 'mock_workspace_id',
                'workspace_icon': None,
                'owner_data': None,
                'duplicated_template_id': None,
                'token_type': 'Bearer',
                'created_at': datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Notion: Error getting tokens for user {user_id}: {e}")
        return None

async def save_user_notion_tokens(user_id: str, token_data: Dict[str, Any]) -> Dict[str, Any]:
    """Save Notion tokens for a user to database"""
    try:
        # Try to use generic OAuth storage first
        try:
            from .db_oauth_gdrive import store_tokens
            from flask import current_app
            
            db_conn_pool = getattr(current_app, "db_pool", None) or current_app.config.get("DB_CONNECTION_POOL", None)
            if not db_conn_pool:
                logger.error("Notion: Database connection pool not available")
                return {"success": False, "error": "Database not available"}
            
            # Store tokens using generic OAuth storage
            await store_tokens(
                db_conn_pool=db_conn_pool,
                user_id=user_id,
                service_name="notion",
                access_token=token_data.get('access_token'),
                refresh_token=None,  # Notion doesn't use refresh tokens
                expires_at=None,  # Notion tokens don't expire in traditional way
                scope='notion'  # Fixed scope for Notion
            )
            
            logger.info(f"Notion: Tokens saved successfully for user {user_id}")
            return {"success": True, "message": "Tokens saved successfully"}
            
        except ImportError:
            logger.warning("Notion: Using mock token storage (database not available)")
            # Mock implementation for testing
            logger.info(f"Notion: Mock saving tokens for user {user_id}")
            return {"success": True, "message": "Tokens saved (mock)"}
            
    except Exception as e:
        logger.error(f"Notion: Error saving tokens for user {user_id}: {e}")
        return {"success": False, "error": str(e)}
