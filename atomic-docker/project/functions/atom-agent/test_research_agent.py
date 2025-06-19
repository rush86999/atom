import unittest
from unittest.mock import patch, MagicMock
import json
import requests

# Assuming research_agent.py is in the same directory or PYTHONPATH is set up correctly
from . import research_agent

class TestResearchAgent(unittest.TestCase):

    @patch('requests.get')
    def test_python_search_web_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_items = [{
            "title": "Test Title 1", "link": "http://example.com/1", "snippet": "Test snippet 1"
        }, {
            "title": "Test Title 2", "link": "http://example.com/2", "snippet": "Test snippet 2"
        }]
        mock_response.json.return_value = {"items": mock_items}
        mock_get.return_value = mock_response

        results = research_agent.python_search_web("test query", "fake_api_key")
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["title"], "Test Title 1")
        mock_get.assert_called_once_with("https://api.exampleSearchEngine.com/search", params={"q": "test query", "key": "fake_api_key"})

    @patch('requests.get')
    def test_python_search_web_api_http_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.HTTPError("API Error")
        results = research_agent.python_search_web("test query", "fake_api_key")
        self.assertEqual(results, [])

    @patch('requests.get')
    def test_python_search_web_api_connection_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection Error")
        results = research_agent.python_search_web("test query", "fake_api_key")
        self.assertEqual(results, [])

    @patch('requests.get')
    def test_python_search_web_json_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("JSON Error", "doc", 0)
        mock_get.return_value = mock_response
        results = research_agent.python_search_web("test query", "fake_api_key")
        self.assertEqual(results, [])

    @patch('requests.get')
    def test_python_search_web_unexpected_format(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"unexpected_key": []} # Missing 'items'
        mock_get.return_value = mock_response
        results = research_agent.python_search_web("test query", "fake_api_key")
        self.assertEqual(results, [])

if __name__ == '__main__':
    unittest.main()
