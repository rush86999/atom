
import sqlite3
import os

DB_PATH = 'dev.db'

def fix_schema():
    if not os.path.exists(DB_PATH):
        print(f"Database {DB_PATH} not found!")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check existing columns
        cursor.execute("PRAGMA table_info(workspaces)")
        columns_info = cursor.fetchall()
        existing_columns = [col[1] for col in columns_info]
        
        print(f"Existing columns in 'workspaces': {existing_columns}")

        missing_cols = {
            'satellite_api_key': 'TEXT',
            'is_startup': 'BOOLEAN DEFAULT 0',
            'learning_phase_completed': 'BOOLEAN DEFAULT 0',
            'metadata_json': 'TEXT DEFAULT "{}"'
        }

        for col, col_type in missing_cols.items():
            if col not in existing_columns:
                print(f"Adding missing column '{col}'...")
                cursor.execute(f"ALTER TABLE workspaces ADD COLUMN {col} {col_type}")
                print(f"Column '{col}' added successfully.")
            else:
                print(f"Column '{col}' already exists.")

        conn.commit()

    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    fix_schema()
