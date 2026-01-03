
import sqlite3
import os

db_path = "backend/atom_dev.db" 
if not os.path.exists(db_path):
    print("DB not found at backend/atom_dev.db, trying atom_dev.db")
    db_path = "atom_dev.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

def add_column_if_not_exists(table, col_name, col_type):
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
        print(f"Added {col_name}")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print(f"Column {col_name} already exists")
        else:
            print(f"Error adding {col_name}: {e}")

print(f"Migrating {db_path}...")
add_column_if_not_exists("users", "skills", "TEXT")
add_column_if_not_exists("users", "capacity_hours", "FLOAT DEFAULT 40.0")
add_column_if_not_exists("users", "hourly_cost_rate", "FLOAT DEFAULT 0.0")
add_column_if_not_exists("users", "metadata_json", "TEXT") # SQLite uses TEXT for JSON

conn.commit()
conn.close()
print("Migration done.")
