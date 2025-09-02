import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

async def save_tokens(db_conn_pool, user_id: str, encrypted_access_token: bytes, encrypted_refresh_token: bytes, expires_at: datetime, scope: str):
    sql = """
        INSERT INTO user_asana_oauth_tokens (user_id, encrypted_access_token, encrypted_refresh_token, expires_at, scope, created_at, updated_at)
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
    finally:
        db_conn_pool.putconn(conn)

async def get_tokens(db_conn_pool, user_id: str):
    sql = "SELECT encrypted_access_token, encrypted_refresh_token, expires_at FROM user_asana_oauth_tokens WHERE user_id = %s;"
    try:
        with db_conn_pool.getconn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (user_id,))
                return cur.fetchone()
    finally:
        db_conn_pool.putconn(conn)

async def delete_tokens(db_conn_pool, user_id: str):
    sql = "DELETE FROM user_asana_oauth_tokens WHERE user_id = %s;"
    try:
        with db_conn_pool.getconn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (user_id,))
            conn.commit()
    finally:
        db_conn_pool.putconn(conn)
