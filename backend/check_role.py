import sys
import os
import sqlite3

# Verify local dev.db
DB_PATH = "dev.db"

def check_role():
    print(f"Checking {os.path.abspath(DB_PATH)}...")
    if not os.path.exists(DB_PATH):
        print("❌ DB not found!")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT email, role, email_verified, tenant_id FROM users WHERE email='admin@example.com'")
        row = cursor.fetchone()
        if row:
            print(f"User: {row[0]}")
            print(f"Role: '{row[1]}' (Type: {type(row[1])})")
            print(f"Verified: {row[2]}")
            print(f"Tenant: {row[3]}")
        else:
            print("❌ Admin user not found.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_role()
