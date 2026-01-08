
import unittest
import asyncio
import os
import sys
from unittest.mock import MagicMock, patch, AsyncMock

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from operations.automations.competitive_intel import CompetitiveIntelWorkflow
from operations.automations.inventory_reconcile import InventoryReconciliationWorkflow
from finance.automations.payroll_guardian import PayrollReconciliationWorkflow

class TestPhase24SpecializedAgents(unittest.TestCase):
    
    @patch('core.lancedb_handler.get_lancedb_handler')
    def test_competitive_intel(self, mock_get_handler):
        print("\n🧪 Testing Competitive Intel Workflow...")
        
        # Setup Mock DB
        mock_handler = MagicMock()
        mock_get_handler.return_value = mock_handler
        
        agent = CompetitiveIntelWorkflow()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        competitors = ["competitor-a", "competitor-b"]
        result = loop.run_until_complete(
            agent.track_competitor_pricing(competitors, "widget-x")
        )
        loop.close()
        
        self.assertEqual(result["status"], "success")
        self.assertIn("competitor-a", result["competitor_data"])
        
        # Verify saved to BI
        mock_handler.add_document.assert_called_once()
        print("✅ Competitive Intel scraped and saved to BI.")

    @patch('core.lancedb_handler.get_lancedb_handler')
    def test_inventory_reconciliation(self, mock_get_handler):
        print("\n🧪 Testing Inventory Reconciliation...")
        
        # Setup Mock DB
        mock_handler = MagicMock()
        mock_get_handler.return_value = mock_handler
        
        agent = InventoryReconciliationWorkflow()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # SKU-999 is set to have variance in our mock
        skus = ["SKU-123", "SKU-999"]
        result = loop.run_until_complete(
            agent.reconcile_inventory(skus)
        )
        loop.close()
        
        self.assertTrue(result["has_variance"])
        self.assertEqual(len(result["discrepancies"]), 1)
        self.assertEqual(result["discrepancies"][0]["sku"], "SKU-999")
        
        # Verify saved to BI
        mock_handler.add_document.assert_called_once()
        print("✅ Inventory variance detected and saved to BI.")

    @patch('core.lancedb_handler.get_lancedb_handler')
    def test_payroll_reconciliation(self, mock_get_handler):
        print("\n🧪 Testing Payroll reconciliation...")
        
        # Setup Mock DB
        mock_handler = MagicMock()
        mock_get_handler.return_value = mock_handler
        
        agent = PayrollReconciliationWorkflow()
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Match Case
        result_match = loop.run_until_complete(agent.reconcile_payroll("2023-12"))
        self.assertTrue(result_match["match"])
        
        # Variance Case
        result_variance = loop.run_until_complete(agent.reconcile_payroll("2023-11"))
        self.assertFalse(result_variance["match"])
        
        # Verify saved to BI (Should be called twice)
        self.assertEqual(mock_handler.add_document.call_count, 2)
        print("✅ Payroll variances detected and saved to BI.")

if __name__ == "__main__":
    unittest.main()
