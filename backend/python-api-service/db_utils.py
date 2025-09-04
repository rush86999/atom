import os
import logging
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
import psycopg2
from psycopg2 import pool, sql, errors
from psycopg2.extras import RealDictCursor, DictCursor
import json

logger = logging.getLogger(__name__)

# Global connection pool
_db_pool = None

def init_db_pool():
    """Initialize the PostgreSQL connection pool"""
    global _db_pool

    try:
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            logger.error("DATABASE_URL environment variable is not set")
            return None

        logger.info("Initializing PostgreSQL connection pool...")

        _db_pool = pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=database_url
        )

        logger.info("PostgreSQL connection pool initialized successfully")
        return _db_pool

    except Exception as e:
        logger.error(f"Failed to initialize database connection pool: {e}")
        return None

def get_db_pool() -> Optional[pool.SimpleConnectionPool]:
    """Get the database connection pool"""
    global _db_pool
    if _db_pool is None:
        _db_pool = init_db_pool()
    return _db_pool

@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    db_pool = get_db_pool()
    if not db_pool:
        raise ConnectionError("Database connection pool not available")

    conn = None
    try:
        conn = db_pool.getconn()
        yield conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise
    finally:
        if conn:
            db_pool.putconn(conn)

@contextmanager
def get_db_cursor():
    """Context manager for database cursors"""
    with get_db_connection() as conn:
        cursor = conn.cursor(cursor_factory=DictCursor)
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database transaction error: {e}")
            raise
        finally:
            cursor.close()

async def execute_query(query: str, params: Optional[tuple] = None) -> List[Dict]:
    """Execute a query and return results as dictionaries"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(query, params)
            results = cursor.fetchall()
            return [dict(row) for row in results] if results else []
    except Exception as e:
        logger.error(f"Query execution error: {e}")
        raise

async def execute_insert(query: str, params: Optional[tuple] = None) -> Optional[int]:
    """Execute an INSERT query and return the inserted ID"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(query, params)
            if cursor.description and 'RETURNING id' in query.upper():
                result = cursor.fetchone()
                return result[0] if result else None
            return None
    except Exception as e:
        logger.error(f"Insert execution error: {e}")
        raise

async def execute_update(query: str, params: Optional[tuple] = None) -> int:
    """Execute an UPDATE query and return number of affected rows"""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.rowcount
    except Exception as e:
        logger.error(f"Update execution error: {e}")
        raise

async def get_user_tokens(user_id: str, service_name: str) -> Optional[Dict[str, Any]]:
    """Get OAuth tokens for a user and service"""
    query = """
        SELECT access_token, refresh_token, expires_at, scope, created_at, updated_at
        FROM user_oauth_tokens
        WHERE user_id = %s AND service_name = %s AND deleted = false
        ORDER BY created_at DESC
        LIMIT 1
    """

    try:
        results = await execute_query(query, (user_id, service_name))
        return results[0] if results else None
    except Exception as e:
        logger.error(f"Error getting tokens for user {user_id}, service {service_name}: {e}")
        return None

async def save_user_tokens(
    user_id: str,
    service_name: str,
    access_token: str,
    refresh_token: Optional[str] = None,
    expires_at: Optional[int] = None,
    scope: Optional[str] = None
) -> bool:
    """Save OAuth tokens for a user and service"""
    query = """
        INSERT INTO user_oauth_tokens
        (user_id, service_name, access_token, refresh_token, expires_at, scope)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, service_name)
        DO UPDATE SET
            access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            expires_at = EXCLUDED.expires_at,
            scope = EXCLUDED.scope,
            updated_at = CURRENT_TIMESTAMP
    """

    try:
        await execute_insert(query, (user_id, service_name, access_token, refresh_token, expires_at, scope))
        logger.info(f"Successfully saved tokens for user {user_id}, service {service_name}")
        return True
    except Exception as e:
        logger.error(f"Error saving tokens for user {user_id}, service {service_name}: {e}")
        return False

async def get_decrypted_credential(user_id: str, service_name: str) -> Optional[str]:
    """Get decrypted credential for a user and service"""
    tokens = await get_user_tokens(user_id, service_name)
    return tokens.get('access_token') if tokens else None

async def create_plaid_item(user_id: str, access_token: str, item_id: str) -> bool:
    """Create a new Plaid item in database"""
    query = """
        INSERT INTO plaid_items (user_id, access_token, item_id, status)
        VALUES (%s, %s, %s, 'active')
        ON CONFLICT (user_id, item_id)
        DO UPDATE SET
            access_token = EXCLUDED.access_token,
            status = 'active',
            updated_at = CURRENT_TIMESTAMP
    """

    try:
        await execute_insert(query, (user_id, access_token, item_id))
        logger.info(f"Successfully created Plaid item for user {user_id}")
        return True
    except Exception as e:
        logger.error(f"Error creating Plaid item for user {user_id}: {e}")
        return False

async def get_plaid_access_token(user_id: str) -> Optional[str]:
    """Get Plaid access token for a user"""
    query = """
        SELECT access_token FROM plaid_items
        WHERE user_id = %s AND status = 'active'
        ORDER BY created_at DESC
        LIMIT 1
    """

    try:
        results = await execute_query(query, (user_id,))
        return results[0]['access_token'] if results else None
    except Exception as e:
        logger.error(f"Error getting Plaid access token for user {user_id}: {e}")
        return None

async def save_calendar_event(user_id: str, event_data: Dict[str, Any]) -> Optional[str]:
    """Save calendar event to database"""
    query = """
        INSERT INTO calendar_events
        (user_id, event_id, title, start_time, end_time, description, location,
         attendees, provider, provider_event_id, status, recurrence)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (user_id, event_id)
        DO UPDATE SET
            title = EXCLUDED.title,
            start_time = EXCLUDED.start_time,
            end_time = EXCLUDED.end_time,
            description = EXCLUDED.description,
            location = EXCLUDED.location,
            attendees = EXCLUDED.attendees,
            status = EXCLUDED.status,
            recurrence = EXCLUDED.recurrence,
            updated_at = CURRENT_TIMESTAMP
        RETURNING event_id
    """

    try:
        event_id = await execute_insert(query, (
            user_id,
            event_data.get('id'),
            event_data.get('title'),
            event_data.get('start'),
            event_data.get('end'),
            event_data.get('description'),
            event_data.get('location'),
            json.dumps(event_data.get('attendees', [])),
            event_data.get('provider'),
            event_data.get('provider_event_id'),
            event_data.get('status', 'confirmed'),
            json.dumps(event_data.get('recurrence', []))
        ))
        return event_id
    except Exception as e:
        logger.error(f"Error saving calendar event for user {user_id}: {e}")
        return None

async def get_user_calendar_events(user_id: str, start_date: str, end_date: str) -> List[Dict]:
    """Get calendar events for a user within date range"""
    query = """
        SELECT event_id, title, start_time, end_time, description, location,
               attendees, provider, provider_event_id, status, recurrence
        FROM calendar_events
        WHERE user_id = %s
          AND start_time >= %s
          AND end_time <= %s
          AND deleted = false
        ORDER BY start_time ASC
    """

    try:
        events = await execute_query(query, (user_id, start_date, end_date))
        for event in events:
            if event.get('attendees'):
                event['attendees'] = json.loads(event['attendees'])
            if event.get('recurrence'):
                event['recurrence'] = json.loads(event['recurrence'])
        return events
    except Exception as e:
        logger.error(f"Error getting calendar events for user {user_id}: {e}")
        return []

def close_db_pool():
    """Close the database connection pool"""
    global _db_pool
    if _db_pool:
        _db_pool.closeall()
        logger.info("Database connection pool closed")
        _db_pool = None

# Initialize pool when module is imported
init_db_pool()
