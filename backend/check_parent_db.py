import sys
import os
from sqlalchemy import create_engine, inspect

# Point to parent directory DB
DATABASE_URL = "sqlite:///../dev.db"

def check_parent_columns():
    print(f"Inspecting database: {DATABASE_URL}")
    try:
        engine = create_engine(DATABASE_URL)
        inspector = inspect(engine)
        
        if not inspector.has_table("users"):
            print("❌ Table 'users' does not exist in parent DB!")
            return

        columns = [c['name'] for c in inspector.get_columns("users")]
        print(f"Columns in 'users': {columns}")
        
        if "email_verified" in columns:
            print("✅ 'email_verified' exists in parent DB.")
        else:
            print("❌ 'email_verified' MISSING in parent DB.")
            
    except Exception as e:
        print(f"Error checking parent DB: {e}")

if __name__ == "__main__":
    check_parent_columns()
