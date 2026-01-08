import sys
import os
import unittest
import threading
import time
import asyncio
from pathlib import Path

# Add project root
sys.path.append(os.getcwd())

from finance.automations.legacy_portals import BankPortalWorkflow
from tests.mock_bank.server import run_server

# Configure logging
import logging
logging.basicConfig(level=logging.INFO)

class TestPhase19Browser(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        # Start Mock Server in background thread
        cls.server_thread = threading.Thread(target=run_server, daemon=True)
        cls.server_thread.start()
        time.sleep(2) # Wait for server startup

    async def test_bank_portal_download(self):
        print("\n--- Phase 19: Browser Agent Verification ---")
        
        workflow = BankPortalWorkflow(headless=True)
        creds = {"username": "admin", "password": "1234"}
        # Localhost URL for mock server
        url = "http://127.0.0.1:8083/login.html"
        
        result = await workflow.download_monthly_statement(url, creds)
        
        self.assertEqual(result["status"], "success")
        self.assertTrue(os.path.exists("downloaded_statement.pdf"))
        print(f"✅ Download Verification Successful: {result['file']}")
        
        # Cleanup
        if os.path.exists("downloaded_statement.pdf"):
            os.remove("downloaded_statement.pdf")

if __name__ == "__main__":
    unittest.main()
