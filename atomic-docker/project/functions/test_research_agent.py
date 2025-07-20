import unittest
from unittest.mock import patch, MagicMock
import requests
from bs4 import BeautifulSoup
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

import research_agent
from hybrid_search_service import UnifiedSearchResultItem
import asyncio

class TestResearchAgent(unittest.TestCase):

    @patch('requests.get')
    def test_python_search_web_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = """
        <div id="links" class="results">
            <div class="result">
                <a class="result__a" href="http://example.com/1">Test Title 1</a>
                <a class="result__snippet" href="http://example.com/1">Test snippet 1</a>
            </div>
            <div class="result">
                <a class="result__a" href="http://example.com/2">Test Title 2</a>
                <a class="result__snippet" href="http://example.com/2">Test snippet 2</a>
            </div>
        </div>
        """
        mock_get.return_value = mock_response

        results = research_agent.python_search_web("test query")
        self.assertEqual(results["status"], "success")
        self.assertEqual(len(results["data"]), 2)
        self.assertEqual(results["data"][0]["title"], "Test Title 1")
        self.assertEqual(results["data"][0]["link"], "http://example.com/1")
        self.assertEqual(results["data"][0]["snippet"], "Test snippet 1")
        mock_get.assert_called_once_with("https://html.duckduckgo.com/html/?q=test query", headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"})

    @patch('requests.get')
    def test_python_search_web_http_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.HTTPError("API Error")
        results = research_agent.python_search_web("test query")
        self.assertEqual(results["status"], "error")
        self.assertEqual(results["code"], "NETWORK_ERROR")

    @patch('requests.get')
    def test_python_search_web_connection_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection Error")
        results = research_agent.python_search_web("test query")
        self.assertEqual(results["status"], "error")
        self.assertEqual(results["code"], "NETWORK_ERROR")

    @patch('requests.get')
    def test_python_search_web_unexpected_format(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html><body><p>Unexpected format</p></body></html>"
        mock_get.return_value = mock_response
        results = research_agent.python_search_web("test query")
        self.assertEqual(results["status"], "success")
        self.assertEqual(len(results["data"]), 0)

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    @patch('multi_agent_research_service.search_meeting_archives', new_callable=unittest.mock.AsyncMock)
    def test_search_past_research_success(self, mock_search_meeting_archives):
        async def run_test():
            mock_search_meeting_archives.return_value = [{"title": "Test Title", "snippet": "Test Snippet"}]

            results = await research_agent.search_past_research("test query", "user1")

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]['title'], "Test Title")
            mock_search_meeting_archives.assert_called_once()

        self.loop.run_until_complete(run_test())

    @patch('multi_agent_research_service.search_meeting_archives', new_callable=unittest.mock.AsyncMock)
    def test_search_past_research_exception(self, mock_search_meeting_archives):
        async def run_test():
            mock_search_meeting_archives.side_effect = Exception("Search failed")

            results = await research_agent.search_past_research("test query", "user1")
            self.assertEqual(len(results), 0)
            mock_search_meeting_archives.assert_called_once()

        self.loop.run_until_complete(run_test())


if __name__ == '__main__':
    unittest.main()
