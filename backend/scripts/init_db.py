
import sys
import os
from sqlalchemy import create_engine

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from core.database import DATABASE_URL, Base
from core.models import User, Team, Workspace, TeamMessage, ChatProcess

def init_db():
    print(f"Initializing database at {DATABASE_URL}...")
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully!")

if __name__ == "__main__":
    init_db()
