
import sqlite3
import os

# Assuming default dev DB
db_path = "backend/atom_dev.db" 
if not os.path.exists(db_path):
    # Try alternate location if widely used
    db_path = "atom_dev.db"

print(f"Checking DB: {db_path}")

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(users)")
    columns = cursor.fetchall()
    print("Columns in 'users' table:")
    for col in columns:
        print(col)
    conn.close()
except Exception as e:
    print(f"Error: {e}")
