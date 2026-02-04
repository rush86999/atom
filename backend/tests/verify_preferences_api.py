
import os
import sys
import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import Base, get_db
from core.user_preference_routes import router as pref_router

# Import model to register with Base
from core.user_preference_service import UserPreference

# Setup test app
app = FastAPI()
app.include_router(pref_router, prefix="/api")

from sqlalchemy.pool import StaticPool

# In-memory DB with StaticPool to share connection across threads/sessions
engine = create_engine(
    "sqlite:///:memory:", 
    connect_args={"check_same_thread": False}, 
    poolclass=StaticPool
)
SessionLocal = sessionmaker(bind=engine)

def override_get_db():
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)

class TestPreferencesAPI(unittest.TestCase):
    def setUp(self):
        # Create tables AFTER importing models
        Base.metadata.create_all(engine)
        print(f"DEBUG: Tables registered in Base: {list(Base.metadata.tables.keys())}")

    def tearDown(self):
        Base.metadata.drop_all(engine)

    def test_set_and_get_preference(self):
        print("\n🧪 Testing POST/GET Preferences API...")
        
        # 1. Set Preference
        payload = {
            "user_id": "api_user",
            "workspace_id": "ws_api",
            "key": "theme",
            "value": "dark"
        }
        res = client.post("/api/preferences", json=payload)
        if res.status_code != 200:
            print(f"Error Response: {res.text}")
        self.assertEqual(res.status_code, 200)
        print(f"Set Response: {res.json()}")
        
        # 2. Get Specific Preference
        res = client.get("/api/preferences/theme?user_id=api_user&workspace_id=ws_api")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        print(f"Get Response: {data}")
        self.assertEqual(data["value"], "dark")
        
        # 3. Get All Preferences
        res = client.get("/api/preferences?user_id=api_user&workspace_id=ws_api")
        self.assertEqual(res.status_code, 200)
        all_data = res.json()
        print(f"Get All Response: {all_data}")
        self.assertEqual(all_data["theme"], "dark")
        
        print("✅ API Verified")

if __name__ == "__main__":
    unittest.main()
