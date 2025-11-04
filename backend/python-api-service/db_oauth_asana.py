import logging
from datetime import datetime, timezone
import crypto_utils

logger = logging.getLogger(__name__)


async def store_tokens(
    db_conn_pool,
    user_id: str,
    service_name: str,
    access_token: str,
    refresh_token: str,
    expires_at: datetime,
    scope: str,
):
    """Store encrypted OAuth tokens in database"""
    # Encrypt tokens before storing
    encrypted_access_token = crypto_utils.encrypt_message(access_token)
    encrypted_refresh_token = (
        crypto_utils.encrypt_message(refresh_token) if refresh_token else None
    )

    sql = """
        INSERT INTO user_asana_oauth_tokens (user_id, access_token, refresh_token, expires_at, scope, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE SET
            access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            expires_at = EXCLUDED.expires_at,
            scope = EXCLUDED.scope,
            updated_at = %s;
    """
    now = datetime.now(timezone.utc)
    try:
        with db_conn_pool.getconn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    sql,
                    (
                        user_id,
                        encrypted_access_token,
                        encrypted_refresh_token,
                        expires_at,
                        scope,
                        now,
                        now,
                        now,
                    ),
                )
            conn.commit()
    finally:
        db_conn_pool.putconn(conn)


async def get_tokens(db_conn_pool, user_id: str, service_name: str):
    """Get encrypted OAuth tokens from database and decrypt them"""
    sql = "SELECT access_token, refresh_token, expires_at, scope FROM user_asana_oauth_tokens WHERE user_id = %s;"
    try:
        with db_conn_pool.getconn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (user_id,))
                result = cur.fetchone()
                if not result:
                    return None

                encrypted_access_token, encrypted_refresh_token, expires_at, scope = (
                    result
                )

                # Decrypt tokens
                access_token = crypto_utils.decrypt_message(encrypted_access_token)
                refresh_token = (
                    crypto_utils.decrypt_message(encrypted_refresh_token)
                    if encrypted_refresh_token
                    else None
                )

                return {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "expires_at": expires_at,
                    "scope": scope,
                }
    finally:
        db_conn_pool.putconn(conn)


async def update_tokens(
    db_conn_pool,
    user_id: str,
    service_name: str,
    access_token: str,
    expires_at: datetime,
):
    """Update access token and expiration"""
    encrypted_access_token = crypto_utils.encrypt_message(access_token)

    sql = """
        UPDATE user_asana_oauth_tokens
        SET access_token = %s, expires_at = %s, updated_at = %s
        WHERE user_id = %s;
    """
    now = datetime.now(timezone.utc)
    try:
        with db_conn_pool.getconn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (encrypted_access_token, expires_at, now, user_id))
            conn.commit()
    finally:
        db_conn_pool.putconn(conn)


async def delete_tokens(db_conn_pool, user_id: str, service_name: str):
    """Delete OAuth tokens from database"""
    sql = "DELETE FROM user_asana_oauth_tokens WHERE user_id = %s;"
    try:
        with db_conn_pool.getconn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (user_id,))
            conn.commit()
    finally:
        db_conn_pool.putconn(conn)
