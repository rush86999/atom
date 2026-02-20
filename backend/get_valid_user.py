
import sqlite3
import os

DB_PATH = r"c:\Users\Mannan Bajaj\atom\backend\data\atom.db"

def get_users():
    print(f"Checking DB at: {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("❌ DB file does not exist!")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if users table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
        if not cursor.fetchone():
             print("❌ Table 'users' does not exist!")
             conn.close()
             return

        cursor.execute("SELECT id, email FROM users LIMIT 5")
        users = cursor.fetchall()
        
        if not users:
            print("❌ No users found in database!")
        else:
            print("✅ Found users:")
            for user in users:
                print(f"ID: {user[0]}, Email: {user[1]}")
        
        conn.close()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    get_users()
