import sqlite3
import os

db_paths = [
    "backend/database.db",
    "backend/dev.db",
    "data/atom.db",
    "backend/data/atom.db"
]

for path in db_paths:
    if os.path.exists(path):
        print(f"\n--- Checking DB: {path} ---")
        try:
            conn = sqlite3.connect(path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            print(f"Tables: {[t[0] for t in tables]}")
            conn.close()
        except Exception as e:
            print(f"Error reading {path}: {e}")
    else:
        print(f"Path does not exist: {path}")
