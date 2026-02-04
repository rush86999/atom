
import asyncio
import http.server
import logging
import os
import socketserver
import sys
import threading
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

# Add backend to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from browser_engine.agent import BrowserAgent

# We don't import lancedb_handler anymore as we mock it

PORT = 8092
MOCK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mock_operations")

logging.basicConfig(level=logging.INFO)

class MockServerHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=MOCK_DIR, **kwargs)
    def log_message(self, format, *args):
        pass

def start_server():
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), MockServerHandler) as httpd:
        httpd.serve_forever()

class TestPhase22Context(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        print(f"Starting mock server on port {PORT} serving {MOCK_DIR}...")
        cls.server_thread = threading.Thread(target=start_server, daemon=True)
        cls.server_thread.start()
        time.sleep(1)
        cls.base_url = f"http://localhost:{PORT}"

    @patch('core.lancedb_handler.get_lancedb_handler')
    @patch('browser_engine.agent.BrowserManager')
    def test_context_injection(self, MockBrowserManager, MockGetHandler):
        print("\n🧪 Testing Context Injection (Memory -> Agent)...")
        
        # Setup Browser Mocks
        mock_instance = MockBrowserManager.get_instance.return_value
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_context.new_page.return_value = mock_page
        mock_instance.new_context = AsyncMock(return_value=mock_context)
        
        # Setup LanceDB Mocks
        mock_handler = MagicMock()
        MockGetHandler.return_value = mock_handler
        
        # Return mock credential on search
        mock_handler.search.return_value = [
            {"text": "The Salesforce Username is admin@atom.ai and the password is super_secret."}
        ]
        
        agent = BrowserAgent(headless=True)
        goal = "Login to Salesforce using saved credentials"
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            agent.execute_task(f"{self.base_url}/context_test_login.html", goal)
        )
        loop.close()
        
        self.assertEqual(result["status"], "success")
        
        # Verify username was filled with "admin@atom.ai"
        mock_page.fill.assert_any_call("#username", "admin@atom.ai")
        print("✅ Agent retrieved 'admin@atom.ai' from mocked memory and filled form.")

    @patch('core.lancedb_handler.get_lancedb_handler')
    @patch('browser_engine.agent.BrowserManager')
    def test_safety_guardrails(self, MockBrowserManager, MockGetHandler):
        print("\n🧪 Testing Safety Guardrails...")
        
        # Setup Browser Mocks
        mock_instance = MockBrowserManager.get_instance.return_value
        mock_page = AsyncMock()
        mock_context = AsyncMock()
        mock_context.new_page.return_value = mock_page
        mock_instance.new_context = AsyncMock(return_value=mock_context)
        
        # Setup LanceDB Mocks
        mock_handler = MagicMock()
        MockGetHandler.return_value = mock_handler
        mock_handler.search.return_value = [] # No context needed
        
        agent = BrowserAgent(headless=True)
        goal = "Pay Tax immediately"
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        result = loop.run_until_complete(
            agent.execute_task(f"{self.base_url}/context_test_login.html", goal, safe_mode=True)
        )
        loop.close()
        
        self.assertEqual(result["status"], "blocked")
        self.assertIn("Security Guardrail Triggered", result.get("error", ""))
        print("✅ High-risk action blocked successfully.")

if __name__ == "__main__":
    unittest.main()
