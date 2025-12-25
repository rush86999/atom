
import unittest
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.database import Base
from core.user_preference_service import UserPreference, UserPreferenceService

class TestUserPreferences(unittest.TestCase):
    def setUp(self):
        # Create in-memory DB
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.service = UserPreferenceService(self.db)

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(self.engine)

    def test_workspace_isolation(self):
        print("\n🧪 Testing User Preference Isolation...")
        user_id = "user_123"
        
        # 1. Set theme in WS1
        self.service.set_preference(user_id, "ws_1", "theme", "dark")
        
        # 2. Set theme in WS2
        self.service.set_preference(user_id, "ws_2", "theme", "light")
        
        # 3. Verify WS1
        val_ws1 = self.service.get_preference(user_id, "ws_1", "theme")
        print(f"WS1 Theme: {val_ws1}")
        self.assertEqual(val_ws1, "dark")
        
        # 4. Verify WS2
        val_ws2 = self.service.get_preference(user_id, "ws_2", "theme")
        print(f"WS2 Theme: {val_ws2}")
        self.assertEqual(val_ws2, "light")
        
        # 5. Verify default fallback
        val_ws3 = self.service.get_preference(user_id, "ws_3", "theme", default="system")
        print(f"WS3 Theme (Default): {val_ws3}")
        self.assertEqual(val_ws3, "system")
        
        print("✅ User Preferences Verified")

    def test_json_storage(self):
        print("\n🧪 Testing complex JSON storage...")
        user_id = "user_123"
        data = {"notifications": True, "frequency": "daily"}
        
        self.service.set_preference(user_id, "ws_1", "config", data)
        retrieved = self.service.get_preference(user_id, "ws_1", "config")
        
        print(f"Retrieved JSON: {retrieved}")
        self.assertEqual(retrieved["frequency"], "daily")
        self.assertTrue(retrieved["notifications"])
        print("✅ JSON Storage Verified")

if __name__ == "__main__":
    unittest.main()
