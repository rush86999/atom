
import sys
# SIMULATE MAIN_API_APP ENVIRONMENT
sys.modules["numpy"] = None
sys.modules["pandas"] = None

from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String)

def test_interaction():
    print("Testing SQLAlchemy with sys.modules['numpy'] = None")
    engine = create_engine('sqlite:///:memory:', echo=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        u = User(name="Test")
        session.add(u)
        session.commit()
        print("Querying...")
        res = session.query(User).first()
        print(f"Result: {res.name}")
        print("SUCCESS")
    except Exception as e:
        print("FAILURE")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_interaction()
