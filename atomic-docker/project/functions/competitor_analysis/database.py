import sqlite3

def get_db_connection():
    """
    Returns a connection to the database.
    """
    conn = sqlite3.connect("competitor_analysis.db")
    conn.row_factory = sqlite3.Row
    return conn

def create_table():
    """
    Creates the competitors table if it doesn't exist.
    """
    conn = get_db_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS competitors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            website TEXT NOT NULL,
            twitter_username TEXT,
            ticker TEXT
        )
    """)
    conn.close()

create_table()
