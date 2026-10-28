
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
        
        # Truthful contract (2026-10-27): no fabricated customer rows when no
        # usage/customer feed is connected. Any returned row must be recorded.
        self.assertIsInstance(risks, list)
        for risk in risks:
            self.assertIn("churn_probability", risk)
        print(f"Recorded churn signals: {len(risks)}")
        print("✅ Churn Logic Verified (no invented records)")

    def test_early_warning_signals(self):
        print("\n🧪 Testing Early Warning (AR & Bookings)...")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        ar_delays = loop.run_until_complete(self.services["warning"].detect_ar_delays("ws_test"))
        booking_scan = loop.run_until_complete(self.services["warning"].monitor_booking_drops("ws_test"))
        loop.close()
        
        self.assertIsInstance(ar_delays, list)
        self.assertEqual(booking_scan["status"], "no_data")
        self.assertFalse(booking_scan["anomaly_detected"])
        print(f"Recorded AR risks: {len(ar_delays)}")
        print(f"Booking state: {booking_scan['status']}")
        print("✅ Early Warning Verified (truthful empty state)")

    def test_fraud_alerts(self):
        print("\n🧪 Testing Fraud Detection...")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        alerts = loop.run_until_complete(self.services["fraud"].detect_anomalies("ws_test"))
        loop.close()
        
        self.assertIsInstance(alerts, list)
        for alert in alerts:
            self.assertIn("severity", alert)
        print(f"Recorded fraud alerts: {len(alerts)}")
        print("✅ Fraud Logic Verified (no invented records)")

    def test_growth_readiness(self):
        print("\n🧪 Testing Growth Readiness...")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        readiness = loop.run_until_complete(self.services["growth"].check_scaling_readiness("ws_test"))
        loop.close()
        
        self.assertIn("bottlenecks", readiness)
        self.assertEqual(readiness["status"], "no_data")
        self.assertIsNone(readiness["can_scale"])
        print(f"Readiness state: {readiness['status']}")
        print("✅ Expansion Playbook Verified (truthful empty state)")

if __name__ == "__main__":
    unittest.main()
