import logging
import os
from typing import Optional, Dict, Any
from datetime import datetime, timezone, timedelta # Added timedelta for placeholder

# Import psycopg2 and its error types and pool
try:
    import psycopg2
    from psycopg2 import pool as psycopg2_pool
    from psycopg2 import errors as psycopg2_errors
    from psycopg2.extras import RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    # Define dummy error and pool for type hinting if psycopg2 is not available
    class psycopg2_errors: # type: ignore
        class Error(Exception): pass
    class psycopg2_pool: # type: ignore
        class AbstractConnectionPool: pass


logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

TABLE_NAME = "user_gdrive_oauth_tokens"

# --- Concrete DB Operation Examples (using psycopg2-like syntax for PostgreSQL) ---

def save_or_update_gdrive_tokens(
    db_conn_pool: Optional[psycopg2_pool.AbstractConnectionPool],
    user_id: str,
    gdrive_user_email: str,
    encrypted_access_token: str,
    encrypted_refresh_token: Optional[str],
    expiry_timestamp_ms: int,
    scopes: Optional[str]
) -> bool:
    """
    Saves or updates Google Drive OAuth tokens for a user in the database using UPSERT.
    Uses psycopg2 for PostgreSQL.
    Assumes db_conn_pool is a psycopg2 connection pool.
    """
    sql = f"""
    INSERT INTO {TABLE_NAME}
      (user_id, gdrive_user_email, access_token_encrypted, refresh_token_encrypted,
       expiry_timestamp_ms, scopes_granted, created_at, last_updated_at)
    VALUES
      (%(user_id)s, %(gdrive_user_email)s, %(access_token_encrypted)s, %(refresh_token_encrypted)s,
       %(expiry_timestamp_ms)s, %(scopes_granted)s, NOW() AT TIME ZONE 'UTC', NOW() AT TIME ZONE 'UTC')
    ON CONFLICT (user_id) DO UPDATE SET
      gdrive_user_email = EXCLUDED.gdrive_user_email,
      access_token_encrypted = EXCLUDED.access_token_encrypted,
      refresh_token_encrypted = COALESCE(EXCLUDED.refresh_token_encrypted, {TABLE_NAME}.refresh_token_encrypted),
      expiry_timestamp_ms = EXCLUDED.expiry_timestamp_ms,
      scopes_granted = EXCLUDED.scopes_granted,
      last_updated_at = NOW() AT TIME ZONE 'UTC';
    """
    params = {
        "user_id": user_id, "gdrive_user_email": gdrive_user_email,
        "access_token_encrypted": encrypted_access_token,
        "refresh_token_encrypted": encrypted_refresh_token,
        "expiry_timestamp_ms": expiry_timestamp_ms, "scopes_granted": scopes
    }

    logger.info(f"DB: Attempting to save/update GDrive tokens for user_id: {user_id}")
    conn = None
    try:
        if not PSYCOPG2_AVAILABLE:
            logger.error("DB: psycopg2 not available. Cannot execute save_or_update_gdrive_tokens.")
            return False
        if db_conn_pool is None:
            logger.error("DB: Connection pool is None. Cannot execute save_or_update_gdrive_tokens.")
            # In a real scenario, this might raise an error or be handled by application setup.
            # For now, returning False to indicate failure to proceed.
            return False

        conn = db_conn_pool.getconn()
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()
        logger.info(f"DB: Successfully executed save/update for GDrive tokens for user_id: {user_id}")
        return True
    except psycopg2_errors.Error as e:
        logger.error(f"DB: psycopg2 error during save/update GDrive tokens for user_id {user_id}: {e}", exc_info=True)
        if conn: conn.rollback()
        return False
    except Exception as e:
        logger.error(f"DB: Unexpected error during save/update GDrive tokens for user_id {user_id}: {e}", exc_info=True)
        if conn: conn.rollback()
        return False
    finally:
        if conn and db_conn_pool: db_conn_pool.putconn(conn)

def get_gdrive_oauth_details(
    db_conn_pool: Optional[psycopg2_pool.AbstractConnectionPool],
    user_id: str
) -> Optional[Dict[str, Any]]:
    """
    Retrieves stored GDrive OAuth details for a user.
    Returns a dict with all fields from the table or None if not found/error.
    Uses psycopg2.
    """
    sql = f"""
    SELECT user_id, gdrive_user_email, access_token_encrypted, refresh_token_encrypted,
           expiry_timestamp_ms, scopes_granted,
           created_at AT TIME ZONE 'UTC' AS created_at,
           last_updated_at AT TIME ZONE 'UTC' AS last_updated_at
    FROM {TABLE_NAME} WHERE user_id = %(user_id)s;
    """
    # Note: Aliased created_at_utc to created_at and last_updated_at_utc to last_updated_at
    # to match common key naming conventions for RealDictCursor.
    params = {"user_id": user_id}

    logger.info(f"DB: Retrieving GDrive OAuth details for user_id: {user_id}")
    conn = None
    try:
        if not PSYCOPG2_AVAILABLE:
            logger.error("DB: psycopg2 not available. Cannot execute get_gdrive_oauth_details.")
            # Fallback to placeholder if psycopg2 isn't available but code needs to run conceptually
            if user_id.startswith("user_with_token_") or user_id.startswith("user_with_expired_token_"):
                is_expired = user_id.startswith("user_with_expired_token_")
                now_dt = datetime.now(timezone.utc)
                expiry_dt = now_dt - timedelta(hours=1) if is_expired else now_dt + timedelta(hours=1)
                return {
                    "user_id": user_id, "gdrive_user_email": f"{user_id.split('_')[-1]}@example.com",
                    "access_token_encrypted": f"encrypted_{'expired_' if is_expired else ''}access_for_{user_id}",
                    "refresh_token_encrypted": f"encrypted_refresh_for_{user_id}",
                    "expiry_timestamp_ms": int(expiry_dt.timestamp() * 1000),
                    "scopes_granted": "['https://www.googleapis.com/auth/drive.readonly', 'https://www.googleapis.com/auth/userinfo.email']",
                    "created_at": now_dt.isoformat(), "last_updated_at": now_dt.isoformat()
                }
            return None
        if db_conn_pool is None:
            logger.error("DB: Connection pool is None. Cannot execute get_gdrive_oauth_details.")
            return None

        conn = db_conn_pool.getconn()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            record = cur.fetchone() # RealDictCursor returns a dict-like object or None
            if record:
                # Convert datetime objects to ISO strings
                if isinstance(record.get('created_at'), datetime):
                    record['created_at'] = record['created_at'].isoformat()
                if isinstance(record.get('last_updated_at'), datetime):
                    record['last_updated_at'] = record['last_updated_at'].isoformat()
                logger.info(f"DB: Found GDrive OAuth details for user_id: {user_id}")
                return dict(record) # Ensure it's a standard dict
            else:
                logger.info(f"DB: No GDrive OAuth details found for user_id: {user_id}")
                return None
    except psycopg2_errors.Error as e:
        logger.error(f"DB: psycopg2 error retrieving GDrive OAuth details for user_id {user_id}: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"DB: Unexpected error retrieving GDrive OAuth details for user_id {user_id}: {e}", exc_info=True)
        return None
    finally:
        if conn and db_conn_pool: db_conn_pool.putconn(conn)


def update_gdrive_access_token(
    db_conn_pool: Optional[psycopg2_pool.AbstractConnectionPool],
    user_id: str,
    new_encrypted_access_token: str,
    new_expiry_timestamp_ms: int
) -> bool:
    """
    Updates only the access token and its expiry for a user after a refresh.
    Uses psycopg2.
    """
    sql = f"""
    UPDATE {TABLE_NAME} SET
      access_token_encrypted = %(access_token_encrypted)s,
      expiry_timestamp_ms = %(expiry_timestamp_ms)s,
      last_updated_at = NOW() AT TIME ZONE 'UTC'
    WHERE user_id = %(user_id)s;
    """
    params = {
        "user_id": user_id,
        "access_token_encrypted": new_encrypted_access_token,
        "expiry_timestamp_ms": new_expiry_timestamp_ms
    }

    logger.info(f"DB: Updating GDrive access token for user_id: {user_id}")
    conn = None
    try:
        if not PSYCOPG2_AVAILABLE:
            logger.error("DB: psycopg2 not available. Cannot execute update_gdrive_access_token.")
            return False
        if db_conn_pool is None:
            logger.error("DB: Connection pool is None. Cannot execute update_gdrive_access_token.")
            return False

        conn = db_conn_pool.getconn()
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            if cur.rowcount > 0:
                logger.info(f"DB: Successfully updated GDrive access token for user_id: {user_id}")
                return True
            else:
                logger.warn(f"DB: No record found for user_id {user_id} during access token update. Token not updated.")
                return False
    except psycopg2_errors.Error as e:
        logger.error(f"DB: psycopg2 error updating GDrive access token for user_id {user_id}: {e}", exc_info=True)
        if conn: conn.rollback()
        return False
    except Exception as e:
        logger.error(f"DB: Unexpected error updating GDrive access token for user_id {user_id}: {e}", exc_info=True)
        if conn: conn.rollback()
        return False
    finally:
        if conn and db_conn_pool: db_conn_pool.putconn(conn)

def delete_gdrive_tokens(db_conn_pool: Optional[psycopg2_pool.AbstractConnectionPool], user_id: str) -> bool:
    """
    Deletes GDrive OAuth tokens for a user. Uses psycopg2.
    """
    sql = f"DELETE FROM {TABLE_NAME} WHERE user_id = %(user_id)s;"
    params = {"user_id": user_id}

    logger.info(f"DB: Deleting GDrive tokens for user_id: {user_id}")
    conn = None
    try:
        if not PSYCOPG2_AVAILABLE:
            logger.error("DB: psycopg2 not available. Cannot execute delete_gdrive_tokens.")
            return False
        if db_conn_pool is None:
            logger.error("DB: Connection pool is None. Cannot execute delete_gdrive_tokens.")
            return False

        conn = db_conn_pool.getconn()
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            logger.info(f"DB: Successfully deleted GDrive tokens for user_id: {user_id} (deleted {cur.rowcount} rows).")
            return True
    except psycopg2_errors.Error as e:
        logger.error(f"DB: psycopg2 error deleting GDrive tokens for user_id {user_id}: {e}", exc_info=True)
        if conn: conn.rollback()
        return False
    except Exception as e:
        logger.error(f"DB: Unexpected error deleting GDrive tokens for user_id {user_id}: {e}", exc_info=True)
        if conn: conn.rollback()
        return False
    finally:
        if conn and db_conn_pool: db_conn_pool.putconn(conn)

```
