import sqlite3

def get_db_connection():
    """
    Returns a connection to the database.
    """
    conn = sqlite3.connect("project_health.db")
    conn.row_factory = sqlite3.Row
    return conn

def create_table():
    """
    Creates the configurations table if it doesn't exist.
    """
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS configurations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trello_board_id TEXT NOT NULL,
            git_repo_path TEXT NOT NULL,
            slack_channel_id TEXT NOT NULL,
            google_calendar_id TEXT NOT NULL,
            project_manager_email TEXT NOT NULL
        )
    """)
    conn.close()

create_table()
