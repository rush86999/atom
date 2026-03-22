import sqlite3
import os

db_path = "backend/data/atom.db" # The one with all the other tables

if os.path.exists(db_path):
    print(f"Adding employee_workspaces table to {db_path}...")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS employee_workspaces (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            agent_id TEXT,
            workspace_state JSON NOT NULL,
            deliverables JSON DEFAULT '[]',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)
        
        # Index for fast lookup
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_employee_workspaces_id ON employee_workspaces (id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_employee_workspaces_user_id ON employee_workspaces (user_id);")
        
        conn.commit()
        print("SUCCESS: Table created.")
        conn.close()
    except Exception as e:
        print(f"Error: {e}")
else:
    print(f"ERROR: DB not found at {db_path}")
