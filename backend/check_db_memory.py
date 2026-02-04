
import logging
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.models import Base, User, UserStatus

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_memory_db():
    print("Testing In-Memory DB (sqlite:///:memory:)")
    engine = create_engine("sqlite:///:memory:", echo=True)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Create Tables
        print("Creating tables...")
        Base.metadata.create_all(engine)
        
        # Insert User
        print("Inserting user...")
        new_user = User(
            email="test@example.com",
            first_name="Test",
            last_name="User",
            status=UserStatus.ACTIVE
        )
        session.add(new_user)
        session.commit()
        
        # Query User
        print("Querying user...")
        user = session.query(User).filter(User.email == "test@example.com").first()
        if user:
            print(f"SUCCESS: User found: {user.email}, ID: {user.id}")
            with open("db_success.txt", "w") as f:
                f.write(f"SUCCESS: User found: {user.email}, ID: {user.id}")
        else:
            print("FAILURE: User NOT found")
            
    except Exception as e:
        print("CRITICAL ERROR:")
        with open("db_error.log", "w") as f:
            import traceback
            traceback.print_exc(file=f)
        import traceback
        traceback.print_exc()
    finally:
        session.close()

if __name__ == "__main__":
    test_memory_db()
