import sys
import os
import sqlite3
from sqlalchemy import create_engine, text

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.database import DATABASE_URL

def fix_schema():
    print(f"Connecting to database: {DATABASE_URL}")
    
    # Handle SQLite specifically
    if DATABASE_URL.startswith("sqlite"):
        db_path = DATABASE_URL.replace("sqlite:///", "")
        
        # Check if file exists
        if not os.path.exists(db_path):
            print(f"Database file not found at {db_path}")
            return

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        try:
            # Check if column exists
            cursor.execute("PRAGMA table_info(users)")
            columns = [info[1] for info in cursor.fetchall()]
            
            if "email_verified" not in columns:
                print("Adding missing column 'email_verified'...")
                cursor.execute("ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 0")
                conn.commit()
                print("✓ Column added successfully.")
            else:
                print("Column 'email_verified' already exists.")
                
        except Exception as e:
            print(f"Error updating schema: {e}")
        finally:
            conn.close()
    else:
        print("Not using SQLite, manual migration might be needed for:", DATABASE_URL)

if __name__ == "__main__":
    fix_schema()
