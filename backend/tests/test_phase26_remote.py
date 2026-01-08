import sys
import os
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio

sys.path.append(os.getcwd())

from browser_engine.driver import BrowserManager

class TestPhase26Remote(unittest.IsolatedAsyncioTestCase):
    
    async def test_remote_connection_logic(self):
        print("\n--- Phase 26: Remote Browser Connection Test ---")
        
        # Reset Singleton
        BrowserManager._instance = None
        
        # Mock Playwright
        mock_playwright = AsyncMock()
        mock_browser = AsyncMock()
        mock_playwright.chromium.connect_over_cdp.return_value = mock_browser
        
        # Patch async_playwright to return our mock
        with patch('browser_engine.driver.async_playwright', return_value=MagicMock(start=AsyncMock(return_value=mock_playwright))):
            
            # Patch Environment Variable
            with patch.dict(os.environ, {"BROWSER_WS_ENDPOINT": "ws://remote-browser:3000"}):
                
                # Initialize Manager
                manager = BrowserManager.get_instance()
                await manager.start()
                
                # Check if connect_over_cdp was called
                mock_playwright.chromium.connect_over_cdp.assert_called_with("ws://remote-browser:3000")
                print("✅ connect_over_cdp called with correct endpoint")
                
                # Check if launch was NOT called
                mock_playwright.chromium.launch.assert_not_called()
                print("✅ standard launch() was skipped")

        # Cleanup
        BrowserManager._instance = None

if __name__ == "__main__":
    unittest.main()
