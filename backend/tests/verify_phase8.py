
import unittest
import asyncio
from unittest.mock import MagicMock, patch
import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.business_health_service import BusinessHealthService

class TestBusinessHealth(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.service = BusinessHealthService(self.mock_db)

    def test_get_health_metrics(self):
        print("\n🧪 Testing Health Metrics Aggregation...")
        metrics = self.service.get_health_metrics("ws_test")
        
        self.assertIn("cash_runway", metrics)
        self.assertEqual(metrics["cash_runway"]["value"], "4.2 months")
        self.assertEqual(metrics["lead_velocity"]["status"], "healthy")
        print(f"Health Metrics: {metrics}")
        print("✅ Health Metrics Verified")

    @patch("core.business_health_service.ai_enhanced_service")
    def test_get_daily_priorities(self, mock_ai):
        print("\n🧪 Testing Daily Priorities...")
        # Mock DB returns
        self.mock_db.query.return_value.filter.return_value.limit.return_value.all.return_value = []
        
        # Async run
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(self.service.get_daily_priorities("ws_test"))
        loop.close()
        
        self.assertIn("priorities", result)
        self.assertIn("owner_advice", result)
        
        # Check if default priorities are present (Strategy, etc.)
        titles = [p["title"] for p in result["priorities"]]
        print(f"Generated Priorities: {titles}")
        self.assertTrue(any("Scale Check" in t for t in titles))
        print("✅ Priorities Verified")

if __name__ == "__main__":
    unittest.main()
