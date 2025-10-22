import os
import logging
import psycopg2
from psycopg2 import sql
from typing import Optional

logger = logging.getLogger(__name__)


def get_database_connection():
    """Get a database connection using DATABASE_URL environment variable"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable is not set")
        return None

    try:
        # Check if it's a SQLite URL
        if database_url.startswith("sqlite:///"):
            # Use SQLite fallback - tables are created automatically
            from db_utils_fallback import (
                init_sqlite_db,
                create_tables_if_not_exist,
            )

            init_sqlite_db()
            create_tables_if_not_exist()
            logger.info("SQLite database initialized with tables")
            return True
        else:
            # Use PostgreSQL
            conn = psycopg2.connect(database_url)
            conn.autocommit = True
            return conn
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return None


def create_tables(conn) -> bool:
    """Create all required database tables"""
    try:
        # Handle both PostgreSQL and SQLite cursor creation
        if hasattr(conn, "cursor"):
            cursor = conn.cursor()
        else:
            # SQLite connection
            cursor = conn
            # Generic user OAuth tokens table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_oauth_tokens (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    service_name VARCHAR(100) NOT NULL,
                    access_token TEXT NOT NULL,
                    refresh_token TEXT,
                    expires_at BIGINT,
                    scope TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    deleted BOOLEAN DEFAULT FALSE,
                    UNIQUE(user_id, service_name)
                )
            """)
            logger.info("Created user_oauth_tokens table")

            # Service-specific OAuth tokens tables
            service_tables = [
                ("user_asana_oauth_tokens", "Asana"),
                ("user_box_oauth_tokens", "Box"),
                ("user_dropbox_oauth_tokens", "Dropbox"),
                ("user_gdrive_oauth_tokens", "Google Drive"),
                ("user_trello_oauth_tokens", "Trello"),
                ("user_zoho_oauth_tokens", "Zoho"),
                ("user_jira_oauth_tokens", "Jira"),
            ]

            for table_name, service_name in service_tables:
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL UNIQUE,
                        encrypted_access_token BYTEA NOT NULL,
                        encrypted_refresh_token BYTEA,
                        expires_at TIMESTAMP,
                        scope TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                logger.info(f"Created {table_name} table")

            # User preferences table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL UNIQUE,
                    automation_level VARCHAR(20) DEFAULT 'moderate',
                    communication_style VARCHAR(20) DEFAULT 'friendly',
                    preferred_services JSONB DEFAULT '["gmail", "google_calendar", "notion"]',
                    business_context JSONB DEFAULT '{"companySize": "solo", "technicalSkill": "intermediate", "goals": ["automation", "efficiency"]}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("Created user_preferences table")

            # Conversation history table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversation_history (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    session_id VARCHAR(255) NOT NULL,
                    role VARCHAR(20) NOT NULL,
                    content TEXT NOT NULL,
                    message_type VARCHAR(50) DEFAULT 'text',
                    metadata JSONB,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("Created conversation_history table")

            # Chat contexts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_contexts (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL UNIQUE,
                    session_id VARCHAR(255) NOT NULL,
                    active_workflows JSONB DEFAULT '[]',
                    context_data JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("Created chat_contexts table")

            # Tasks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    title VARCHAR(500) NOT NULL,
                    description TEXT,
                    due_date TIMESTAMP,
                    priority VARCHAR(20) DEFAULT 'medium',
                    status VARCHAR(20) DEFAULT 'todo',
                    project VARCHAR(255),
                    tags JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    deleted BOOLEAN DEFAULT FALSE
                )
            """)
            logger.info("Created tasks table")

            # Messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    platform VARCHAR(50) NOT NULL,
                    sender VARCHAR(255) NOT NULL,
                    subject VARCHAR(500),
                    preview TEXT,
                    timestamp TIMESTAMP NOT NULL,
                    unread BOOLEAN DEFAULT TRUE,
                    priority VARCHAR(20) DEFAULT 'normal',
                    thread_id VARCHAR(255),
                    conversation_id VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    deleted BOOLEAN DEFAULT FALSE
                )
            """)
            logger.info("Created messages table")

            # Calendar events table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS calendar_events (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    event_id VARCHAR(255) NOT NULL,
                    title VARCHAR(500) NOT NULL,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP NOT NULL,
                    description TEXT,
                    location VARCHAR(500),
                    attendees JSONB,
                    provider VARCHAR(50) NOT NULL,
                    provider_event_id VARCHAR(255),
                    status VARCHAR(20) DEFAULT 'confirmed',
                    recurrence JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    deleted BOOLEAN DEFAULT FALSE,
                    UNIQUE(user_id, event_id)
                )
            """)
            logger.info("Created calendar_events table")

            # Meeting transcriptions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS meeting_transcriptions (
                    id SERIAL PRIMARY KEY,
                    meeting_id VARCHAR(255) NOT NULL UNIQUE,
                    transcript TEXT NOT NULL,
                    summary TEXT,
                    action_items JSONB,
                    key_topics JSONB,
                    confidence FLOAT DEFAULT 0.0,
                    duration FLOAT DEFAULT 0.0,
                    model VARCHAR(100),
                    is_placeholder BOOLEAN DEFAULT FALSE,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logger.info("Created meeting_transcriptions table")

            # Plaid items table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS plaid_items (
                    id SERIAL PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    access_token TEXT NOT NULL,
                    item_id VARCHAR(255) NOT NULL,
                    status VARCHAR(20) DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(user_id, item_id)
                )
            """)
            logger.info("Created plaid_items table")

            # Create indexes for better performance
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_oauth_tokens_user_id ON user_oauth_tokens(user_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id ON user_preferences(user_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversation_history_user_id ON conversation_history(user_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversation_history_session_id ON conversation_history(session_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_conversation_history_timestamp ON conversation_history(timestamp)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_chat_contexts_user_id ON chat_contexts(user_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks(user_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_due_date ON tasks(due_date)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_messages_unread ON messages(unread)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_calendar_events_user_id ON calendar_events(user_id)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_calendar_events_start_time ON calendar_events(start_time)"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_plaid_items_user_id ON plaid_items(user_id)"
            )

            # Create indexes for service-specific OAuth tables
            service_tables = [
                "user_asana_oauth_tokens",
                "user_box_oauth_tokens",
                "user_dropbox_oauth_tokens",
                "user_gdrive_oauth_tokens",
                "user_trello_oauth_tokens",
                "user_zoho_oauth_tokens",
                "user_jira_oauth_tokens",
            ]

            for table_name in service_tables:
                cursor.execute(
                    f"CREATE INDEX IF NOT EXISTS idx_{table_name}_user_id ON {table_name}(user_id)"
                )

            logger.info("Created all indexes")

            return True

    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        return False


def check_tables_exist(conn) -> bool:
    """Check if all required tables exist"""
    try:
        # Handle both PostgreSQL and SQLite cursor creation
        if hasattr(conn, "cursor"):
            cursor = conn.cursor()
        else:
            # SQLite connection
            cursor = conn
            tables_to_check = [
                "user_oauth_tokens",
                "user_preferences",
                "conversation_history",
                "chat_contexts",
                "tasks",
                "messages",
                "calendar_events",
                "meeting_transcriptions",
                "plaid_items",
                "user_asana_oauth_tokens",
                "user_box_oauth_tokens",
                "user_dropbox_oauth_tokens",
                "user_gdrive_oauth_tokens",
                "user_trello_oauth_tokens",
                "user_zoho_oauth_tokens",
                "user_jira_oauth_tokens",
            ]

            for table in tables_to_check:
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = %s
                    )
                """,
                    (table,),
                )
                exists = cursor.fetchone()[0]
                if not exists:
                    logger.warning(f"Table {table} does not exist")
                    return False

            logger.info("All required tables exist")
            return True

    except Exception as e:
        logger.error(f"Error checking tables: {e}")
        return False


def initialize_database():
    """Initialize the database by creating all required tables"""
    logger.info("Starting database initialization...")

    conn = get_database_connection()
    if not conn:
        logger.error("Failed to get database connection")
        return False

    try:
        # For SQLite, tables are already created by create_tables_if_not_exist
        if isinstance(conn, bool) and conn:
            logger.info("SQLite database initialized successfully")
            return True

        # Check if tables already exist (PostgreSQL)
        if check_tables_exist(conn):
            logger.info("Database tables already exist, skipping creation")
            return True

        # Create tables (PostgreSQL)
        success = create_tables(conn)
        if success:
            logger.info("Database initialization completed successfully")
        else:
            logger.error("Database initialization failed")

        return success

    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        return False
    finally:
        if conn and hasattr(conn, "close") and not isinstance(conn, bool):
            conn.close()


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Initialize database
    success = initialize_database()
    exit(0 if success else 1)
