
import asyncio
import os
import sys
import unittest
from unittest.mock import MagicMock

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.risk_prevention import get_risk_services


class TestRiskPrevention(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.services = get_risk_services(self.mock_db)

    def test_churn_prediction(self):
        print("\n🧪 Testing Churn Prediction...")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        risks = loop.run_until_complete(self.services["churn"].predict_churn_risk("ws_test"))
        loop.close()
        
        self.assertTrue(len(risks) > 0)
        self.assertIn("churn_probability", risks[0])
        print(f"High-Risk Customers: {len(risks)}")
        print("✅ Churn Logic Verified")

    def test_early_warning_signals(self):
        print("\n🧪 Testing Early Warning (AR & Bookings)...")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        ar_delays = loop.run_until_complete(self.services["warning"].detect_ar_delays("ws_test"))
        booking_scan = loop.run_until_complete(self.services["warning"].monitor_booking_drops("ws_test"))
        loop.close()
        
        self.assertTrue(len(ar_delays) > 0)
        self.assertEqual(booking_scan["status"], "warning")
        print(f"AR Risks: {len(ar_delays)}")
        print(f"Booking Anomaly: {booking_scan['anomaly_detected']}")
        print("✅ Early Warning Verified")

    def test_fraud_alerts(self):
        print("\n🧪 Testing Fraud Detection...")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        alerts = loop.run_until_complete(self.services["fraud"].detect_anomalies("ws_test"))
        loop.close()
        
        self.assertTrue(len(alerts) > 0)
        self.assertEqual(alerts[0]["severity"], "HIGH")
        print(f"Fraud Alerts: {len(alerts)}")
        print("✅ Fraud Logic Verified")

    def test_growth_readiness(self):
        print("\n🧪 Testing Growth Readiness...")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        readiness = loop.run_until_complete(self.services["growth"].check_scaling_readiness("ws_test"))
        loop.close()
        
        self.assertTrue(readiness["can_scale"])
        self.assertIn("bottlenecks", readiness)
        print(f"Readiness Score: {readiness['readiness_score']}")
        print("✅ Expansion Playbook Verified")

if __name__ == "__main__":
    unittest.main()
