
import http.server
import os
import socketserver
import sys
import threading
import time
import unittest

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from operations.automations.logistics_manager import LogisticsManagerWorkflow
from operations.automations.marketplace_admin import MarketplaceAdminWorkflow

PORT = 8089
MOCK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_operations")

class MockServerHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=MOCK_DIR, **kwargs)
    
    def log_message(self, format, *args):
        pass # Silence logs

def start_server():
    # Allow reuse address to prevent "Address already in use"
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), MockServerHandler) as httpd:
        httpd.serve_forever()

class TestPhase21Operations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print(f"Starting mock server on port {PORT} serving {MOCK_DIR}...")
        cls.server_thread = threading.Thread(target=start_server, daemon=True)
        cls.server_thread.start()
        time.sleep(1) # Wait for server to start
        cls.base_url = f"http://localhost:{PORT}"

    def test_marketplace_admin_update_listing(self):
        print("\n🧪 Testing Marketplace Admin (Seller Central)...")
        agent = MarketplaceAdminWorkflow(self.base_url)
        
        # Test 1: Update existing SKU
        result = agent.update_listing_price("SKU-123", "49.99")
        if not result["success"]:
            print(f"FAILED: {result.get('error')}")
            
        self.assertTrue(result["success"])
        self.assertIn("Found SKU SKU-123", str(result["action_log"]))
        print("✅ SKU-123 update verified (Agent found inputs correctly)")
        
        # Test 2: Missing SKU
        result = agent.update_listing_price("SKU-UNKNOWN", "10.00")
        self.assertFalse(result["success"])
        self.assertIn("not found", result["error"])
        print("✅ Missing SKU handled correctly")

    def test_logistics_manager_place_po(self):
        print("\n🧪 Testing Logistics Manager (Supplier Portal)...")
        agent = LogisticsManagerWorkflow(self.base_url)
        
        result = agent.place_purchase_order("SKU-555", 100)
        self.assertTrue(result["success"])
        self.assertEqual(result["po_details"]["sku"], "SKU-555")
        self.assertEqual(result["po_details"]["action"], "Clicked Submit Order")
        print("✅ PO placement verified (Agent filled form correctly)")

if __name__ == "__main__":
    unittest.main()
