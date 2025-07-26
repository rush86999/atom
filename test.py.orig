import unittest
from unittest.mock import patch, MagicMock
import requests
from bs4 import BeautifulSoup
import sys
import os

# Add the atomic-docker directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from atomic-docker.project.functions.atom-agent import research_agent

class TestSearch(unittest.TestCase):

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

if __name__ == '__main__':
    unittest.main()
