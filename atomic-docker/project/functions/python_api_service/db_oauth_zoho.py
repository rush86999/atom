import logging
from psycopg2 import sql

logger = logging.getLogger(__name__)

async def store_zoho_tokens(user_id, access_token, refresh_token, db_conn_pool):
    """
    Stores Zoho OAuth tokens in the database.
    """
    query = sql.SQL("""
        INSERT INTO user_credentials (user_id, service, access_token, refresh_token)
        VALUES (%s, 'zoho', %s, %s)
        ON CONFLICT (user_id, service) DO UPDATE
        SET access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token;
    """)
    async with db_conn_pool.getconn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, (user_id, access_token, refresh_token))
        db_conn_pool.putconn(conn)

async def get_zoho_tokens(user_id, db_conn_pool):
    """
    Retrieves Zoho OAuth tokens from the database.
    """
    query = sql.SQL("""
        SELECT access_token, refresh_token
        FROM user_credentials
        WHERE user_id = %s AND service = 'zoho';
    """)
    async with db_conn_pool.getconn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, (user_id,))
            result = await cur.fetchone()
        db_conn_pool.putconn(conn)
    return result if result else (None, None)
