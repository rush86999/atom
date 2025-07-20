import unittest
from unittest.mock import MagicMock
import sys
import os

# Add the functions directory to the path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'project/functions')))

from competitor_analysis.main import app
from fastapi.testclient import TestClient
from competitor_analysis.dependencies import (
    get_scrape_website,
    get_get_twitter_data,
    get_get_news_data,
    get_get_financial_data,
    get_create_notion_page,
    get_store_data,
    get_generate_weekly_briefing,
)

class CompetitorAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_competitor_analysis(self):
        # Mock the dependencies
        mock_scrape_website = MagicMock(return_value={
            "blog_posts": [{"title": "Test Post", "link": "http://example.com/blog/test"}],
            "press_releases": [],
            "product_updates": [],
        })
        mock_get_twitter_data = MagicMock(return_value={"tweets": ["Test tweet"]})
        mock_get_news_data = MagicMock(return_value={
            "articles": [{"title": "Test Article", "url": "http://example.com/news/test"}]
        })
        mock_get_financial_data = MagicMock(return_value={
            "info": {
                "marketCap": 1000000,
                "enterpriseValue": 1000000,
                "trailingPE": 10,
                "forwardPE": 10,
                "pegRatio": 1,
            }
        })
        mock_create_notion_page = MagicMock()
        mock_store_data = MagicMock()

        app.dependency_overrides[get_scrape_website] = lambda: mock_scrape_website
        app.dependency_overrides[get_get_twitter_data] = lambda: mock_get_twitter_data
        app.dependency_overrides[get_get_news_data] = lambda: mock_get_news_data
        app.dependency_overrides[get_get_financial_data] = lambda: mock_get_financial_data
        app.dependency_overrides[get_create_notion_page] = lambda: mock_create_notion_page
        app.dependency_overrides[get_store_data] = lambda: mock_store_data

        response = self.client.post(
            "/competitor-analysis",
            params={
                "competitor_website": "http://example.com",
                "competitor_twitter_username": "testuser",
                "competitor_name": "TestCorp",
                "competitor_ticker": "TEST",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "success"})
        mock_store_data.assert_called_once()
        mock_create_notion_page.assert_called_once()

    def test_weekly_briefing(self):
        # Mock the dependencies
        mock_generate_weekly_briefing = MagicMock(return_value="Weekly briefing content")
        mock_create_notion_page = MagicMock()

        app.dependency_overrides[get_generate_weekly_briefing] = lambda: mock_generate_weekly_briefing
        app.dependency_overrides[get_create_notion_page] = lambda: mock_create_notion_page

        response = self.client.post("/weekly-briefing")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "success"})
        mock_create_notion_page.assert_called_once_with("Weekly Competitor Briefing", "Weekly briefing content")

if __name__ == "__main__":
    unittest.main()
