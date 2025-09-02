import logging
from typing import Optional, Dict, Any

# Use psycopg2 for PostgreSQL interaction. Assumes this is in the environment.
try:
    import psycopg2
    from psycopg2 import pool as psycopg2_pool
    from psycopg2 import errors as psycopg2_errors
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    psycopg2_pool = None # To satisfy type hints if library is missing

logger = logging.getLogger(__name__)

# --- Constants ---
TABLE_NAME = "user_dropbox_oauth_tokens"

# --- Database Operations ---

async def save_tokens(db_conn_pool: Optional[psycopg2_pool.AbstractConnectionPool], user_id: str, encrypted_access_token: bytes, encrypted_refresh_token: Optional[bytes], expires_at: Optional[Any], scope: Optional[str]):
    """Saves new Dropbox OAuth tokens for a user."""
    if not PSYCOPG2_AVAILABLE or not db_conn_pool:
        logger.error("Database connection pool or psycopg2 is not available.")
        raise ConnectionError("Database connection is not configured.")

    sql = f"""
        INSERT INTO {TABLE_NAME} (user_id, encrypted_access_token, encrypted_refresh_token, expires_at, scope)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE SET
            encrypted_access_token = EXCLUDED.encrypted_access_token,
            encrypted_refresh_token = EXCLUDED.encrypted_refresh_token,
            expires_at = EXCLUDED.expires_at,
            scope = EXCLUDED.scope,
            updated_at = NOW();
    """
    conn = None
    try:
        conn = db_conn_pool.getconn()
        with conn.cursor() as cur:
            cur.execute(sql, (user_id, encrypted_access_token, encrypted_refresh_token, expires_at, scope))
        conn.commit()
        logger.info(f"Successfully saved Dropbox tokens for user_id: {user_id}")
    except (Exception, psycopg2.DatabaseError) as e:
        logger.error(f"Error saving Dropbox tokens for user_id {user_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        # Re-raise a generic exception to be handled by the calling route
        raise Exception("Failed to save Dropbox tokens to the database.") from e
    finally:
        if conn:
            db_conn_pool.putconn(conn)


async def get_tokens(db_conn_pool: Optional[psycopg2_pool.AbstractConnectionPool], user_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a user's Dropbox OAuth tokens from the database."""
    if not PSYCOPG2_AVAILABLE or not db_conn_pool:
        logger.error("Database connection pool or psycopg2 is not available.")
        raise ConnectionError("Database connection is not configured.")

    sql = f"SELECT * FROM {TABLE_NAME} WHERE user_id = %s;"
    conn = None
    try:
        conn = db_conn_pool.getconn()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (user_id,))
            tokens = cur.fetchone()
        if tokens:
            logger.info(f"Successfully retrieved Dropbox tokens for user_id: {user_id}")
            return dict(tokens)
        else:
            logger.info(f"No Dropbox tokens found for user_id: {user_id}")
            return None
    except (Exception, psycopg2.DatabaseError) as e:
        logger.error(f"Error getting Dropbox tokens for user_id {user_id}: {e}", exc_info=True)
        raise Exception("Failed to retrieve Dropbox tokens from the database.") from e
    finally:
        if conn:
            db_conn_pool.putconn(conn)


async def update_tokens(db_conn_pool: Optional[psycopg2_pool.AbstractConnectionPool], user_id: str, encrypted_access_token: bytes, expires_at: Optional[Any]):
    """Updates an existing user's Dropbox access token and expiration."""
    if not PSYCOPG2_AVAILABLE or not db_conn_pool:
        logger.error("Database connection pool or psycopg2 is not available.")
        raise ConnectionError("Database connection is not configured.")

    sql = f"""
        UPDATE {TABLE_NAME}
        SET encrypted_access_token = %s, expires_at = %s, updated_at = NOW()
        WHERE user_id = %s;
    """
    conn = None
    try:
        conn = db_conn_pool.getconn()
        with conn.cursor() as cur:
            cur.execute(sql, (encrypted_access_token, expires_at, user_id))
        conn.commit()
        logger.info(f"Successfully updated Dropbox access token for user_id: {user_id}")
    except (Exception, psycopg2.DatabaseError) as e:
        logger.error(f"Error updating Dropbox access token for user_id {user_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        raise Exception("Failed to update Dropbox access token in the database.") from e
    finally:
        if conn:
            db_conn_pool.putconn(conn)


async def delete_tokens(db_conn_pool: Optional[psycopg2_pool.AbstractConnectionPool], user_id: str):
    """Deletes a user's Dropbox OAuth tokens from the database."""
    if not PSYCOPG2_AVAILABLE or not db_conn_pool:
        logger.error("Database connection pool or psycopg2 is not available.")
        raise ConnectionError("Database connection is not configured.")

    sql = f"DELETE FROM {TABLE_NAME} WHERE user_id = %s;"
    conn = None
    try:
        conn = db_conn_pool.getconn()
        with conn.cursor() as cur:
            cur.execute(sql, (user_id,))
        conn.commit()
        logger.info(f"Successfully deleted Dropbox tokens for user_id: {user_id}")
    except (Exception, psycopg2.DatabaseError) as e:
        logger.error(f"Error deleting Dropbox tokens for user_id {user_id}: {e}", exc_info=True)
        if conn:
            conn.rollback()
        raise Exception("Failed to delete Dropbox tokens from the database.") from e
    finally:
        if conn:
            db_conn_pool.putconn(conn)
