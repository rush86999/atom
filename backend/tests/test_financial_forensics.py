
import unittest
import asyncio
from unittest.mock import MagicMock
import sys
import os

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.financial_forensics import get_forensics_services

class TestFinancialForensics(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.services = get_forensics_services(self.mock_db)

    def test_vendor_drift_detection(self):
        print("\n🧪 Testing Vendor Drift Detection...")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        drifts = loop.run_until_complete(self.services["vendor"].detect_price_drift("ws_test"))
        loop.close()
        
        self.assertIsInstance(drifts, list)
        self.assertTrue(len(drifts) > 0)
        self.assertIn("drift_percent", drifts[0])
        print(f"Detected Drifts: {len(drifts)} items found.")
        print("✅ Vendor Drift Verified")

    def test_pricing_suggestions(self):
        print("\n🧪 Testing Pricing Advisor...")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        suggestions = loop.run_until_complete(self.services["pricing"].get_pricing_recommendations("ws_test"))
        loop.close()
        
        self.assertTrue(len(suggestions) > 0)
        self.assertIn("target_price", suggestions[0])
        print(f"Pricing Suggestions: {len(suggestions)} items found.")
        print("✅ Pricing Logic Verified")

    def test_zombie_subscriptions(self):
        print("\n🧪 Testing Zombie Subscription Detection...")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        zombies = loop.run_until_complete(self.services["waste"].find_zombie_subscriptions("ws_test"))
        loop.close()
        
        self.assertTrue(len(zombies) > 0)
        self.assertIn("waste_score", zombies[0])
        print(f"Zombie Subscriptions: {len(zombies)} items found.")
        print("✅ Subscription Waste Verified")

if __name__ == "__main__":
    unittest.main()
