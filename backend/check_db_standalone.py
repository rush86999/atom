
import sys
import os
import logging
# numpy mock removed for testing


from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from core.models import User
DATABASE_URL = "sqlite:///./atom_v2.db"
# from core.database import DATABASE_URL, Base

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_db():
    print(f"Testing DB URL: {DATABASE_URL}")
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        print("Querying user...")
        user = session.query(User).filter(User.email == "admin@example.com").first()
        if user:
            print(f"User found: {user.email}, ID: {user.id}")
        else:
            print("User NOT found")
    except Exception as e:
        print("Error querying DB:")
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    test_db()
