
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main_api_app import app
from core.database import Base, get_db

class TestPreferenceAPI(unittest.TestCase):
    def setUp(self):
        # Setup in-memory DB for testing
        SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
        self.engine = create_engine(
            SQLALCHEMY_DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        
        def override_get_db():
            try:
                db = self.TestingSessionLocal()
                yield db
            finally:
                db.close()
                
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        Base.metadata.drop_all(bind=self.engine)

    def test_preferences_lifecycle(self):
        user_id = "test_user_1"
        workspace_id = "ws_1"
        
        # 1. Get initial preferences (should be empty object)
        response = self.client.get(f"/api/preferences?user_id={user_id}&workspace_id={workspace_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {})
        
        # 2. Set a preference (Theme)
        payload_theme = {
            "user_id": user_id,
            "workspace_id": workspace_id,
            "key": "theme",
            "value": "dark"
        }
        response = self.client.post("/api/preferences", json=payload_theme)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        
        # 3. Set another preference (Notifications)
        payload_notif = {
            "user_id": user_id,
            "workspace_id": workspace_id,
            "key": "notifications_enabled",
            "value": False
        }
        self.client.post("/api/preferences", json=payload_notif)
        
        # 4. Verify persistence via get_all
        response = self.client.get(f"/api/preferences?user_id={user_id}&workspace_id={workspace_id}")
        data = response.json()
        self.assertEqual(data["theme"], "dark")
        self.assertEqual(data["notifications_enabled"], False)
        
        # 5. Verify individual get
        response = self.client.get(f"/api/preferences/theme?user_id={user_id}&workspace_id={workspace_id}")
        self.assertEqual(response.json()["value"], "dark")
        
        # 6. Update preference
        payload_theme_update = {
            "user_id": user_id,
            "workspace_id": workspace_id,
            "key": "theme",
            "value": "light"
        }
        self.client.post("/api/preferences", json=payload_theme_update)
        
        response = self.client.get(f"/api/preferences?user_id={user_id}&workspace_id={workspace_id}")
        self.assertEqual(response.json()["theme"], "light")

if __name__ == "__main__":
    unittest.main()
