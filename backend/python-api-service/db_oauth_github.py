import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


async def save_tokens(
    db_conn_pool,
    user_id: str,
    encrypted_access_token: bytes,
    encrypted_refresh_token: bytes,
    expires_at: datetime,
    scope: str,
):
    """
    Save GitHub OAuth tokens for a user.

    Args:
        db_conn_pool: Database connection pool
        user_id: User identifier
        encrypted_access_token: Encrypted access token
        encrypted_refresh_token: Encrypted refresh token (GitHub doesn't use these, but kept for consistency)
        expires_at: Token expiration time
        scope: OAuth scope
    """
    sql = """
        INSERT INTO user_github_oauth_tokens (user_id, encrypted_access_token, encrypted_refresh_token, expires_at, scope, created_at, updated_at)
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
    except Exception as e:
        logger.error(f"Error saving GitHub OAuth tokens for user {user_id}: {e}")
        raise
    finally:
        db_conn_pool.putconn(conn)


async def get_tokens(db_conn_pool, user_id: str):
    """
    Get GitHub OAuth tokens for a user.

    Args:
        db_conn_pool: Database connection pool
        user_id: User identifier

    Returns:
        Tuple of (encrypted_access_token, encrypted_refresh_token, expires_at) or None if not found
    """
    sql = "SELECT encrypted_access_token, encrypted_refresh_token, expires_at FROM user_github_oauth_tokens WHERE user_id = %s;"
    try:
        with db_conn_pool.getconn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (user_id,))
                return cur.fetchone()
    except Exception as e:
        logger.error(f"Error getting GitHub OAuth tokens for user {user_id}: {e}")
        return None
    finally:
        db_conn_pool.putconn(conn)


async def delete_tokens(db_conn_pool, user_id: str):
    """
    Delete GitHub OAuth tokens for a user.

    Args:
        db_conn_pool: Database connection pool
        user_id: User identifier
    """
    sql = "DELETE FROM user_github_oauth_tokens WHERE user_id = %s;"
    try:
        with db_conn_pool.getconn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (user_id,))
            conn.commit()
    except Exception as e:
        logger.error(f"Error deleting GitHub OAuth tokens for user {user_id}: {e}")
        raise
    finally:
        db_conn_pool.putconn(conn)


async def token_exists(db_conn_pool, user_id: str) -> bool:
    """
    Check if GitHub OAuth tokens exist for a user.

    Args:
        db_conn_pool: Database connection pool
        user_id: User identifier

    Returns:
        True if tokens exist, False otherwise
    """
    sql = "SELECT 1 FROM user_github_oauth_tokens WHERE user_id = %s;"
    try:
        with db_conn_pool.getconn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (user_id,))
                return cur.fetchone() is not None
    except Exception as e:
        logger.error(f"Error checking GitHub OAuth tokens for user {user_id}: {e}")
        return False
    finally:
        db_conn_pool.putconn(conn)


async def get_token_expiry(db_conn_pool, user_id: str):
    """
    Get the expiration time of GitHub OAuth tokens for a user.

    Args:
        db_conn_pool: Database connection pool
        user_id: User identifier

    Returns:
        Expiration datetime or None if not found
    """
    sql = "SELECT expires_at FROM user_github_oauth_tokens WHERE user_id = %s;"
    try:
        with db_conn_pool.getconn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (user_id,))
                result = cur.fetchone()
                return result[0] if result else None
    except Exception as e:
        logger.error(f"Error getting GitHub token expiry for user {user_id}: {e}")
        return None
    finally:
        db_conn_pool.putconn(conn)
