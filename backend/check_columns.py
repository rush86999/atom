import sys
import os
from sqlalchemy import create_engine, inspect

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.database import DATABASE_URL, engine

def check_columns():
    print(f"Inspecting database: {DATABASE_URL}")
    inspector = inspect(engine)
    
    if not inspector.has_table("users"):
        print("❌ Table 'users' does not exist!")
        return

    columns = [c['name'] for c in inspector.get_columns("users")]
    print(f"Columns in 'users': {columns}")
    
    if "email_verified" in columns:
        print("✅ 'email_verified' exists.")
    else:
        print("❌ 'email_verified' MISSING.")

if __name__ == "__main__":
    check_columns()
