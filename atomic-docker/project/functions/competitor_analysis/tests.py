import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.append(os.path.dirname(os.path.realpath(__file__)))
from main import competitor_analysis, weekly_briefing
from dependencies import (
    get_scrape_website,
    get_get_twitter_data,
    get_get_news_data,
    get_get_financial_data,
    get_create_notion_page,
    get_store_data,
    get_generate_weekly_briefing,
)

class TestCompetitorAnalysis(unittest.TestCase):

    def test_competitor_analysis(self):
        with patch('main.get_scrape_website') as mock_get_scrape_website, \
             patch('main.get_get_twitter_data') as mock_get_get_twitter_data, \
             patch('main.get_get_news_data') as mock_get_get_news_data, \
             patch('main.get_get_financial_data') as mock_get_get_financial_data, \
             patch('main.get_create_notion_page') as mock_get_create_notion_page, \
             patch('main.get_store_data') as mock_get_store_data, \
             patch('main.generate_competitor_briefing') as mock_generate_competitor_briefing:

            mock_get_scrape_website.return_value.return_value = {"blog_posts": [], "press_releases": [], "product_updates": []}
            mock_get_get_twitter_data.return_value.return_value = {"tweets": []}
            mock_get_get_news_data.return_value.return_value = {"articles": []}
            mock_get_get_financial_data.return_value.return_value = {"info": {"marketCap": "N/A", "enterpriseValue": "N/A", "trailingPE": "N/A", "forwardPE": "N/A", "pegRatio": "N/A"}}
            mock_generate_competitor_briefing.return_value = "briefing"
            mock_create_notion_page = MagicMock()
            mock_get_create_notion_page.return_value = mock_create_notion_page

            response = competitor_analysis(
                competitor_website="http://example.com",
                competitor_twitter_username="example",
                competitor_name="Example",
                competitor_ticker="EXMPL",
                scrape_website=mock_get_scrape_website(),
                get_twitter_data=mock_get_get_twitter_data(),
                get_news_data=mock_get_get_news_data(),
                get_financial_data=mock_get_get_financial_data(),
                create_notion_page=mock_get_create_notion_page(),
                store_data=mock_get_store_data(),
            )

            self.assertEqual(response, {"status": "success"})
            mock_create_notion_page.assert_called_once_with("Competitor Briefing for Example", "briefing")

    @patch.dict(os.environ, {"NOTION_TOKEN": "test", "NOTION_DATABASE_ID": "test"})
    def test_weekly_briefing(self):
        with patch('main.get_generate_weekly_briefing') as mock_get_generate_weekly_briefing, \
             patch('main.get_create_notion_page') as mock_get_create_notion_page:

            mock_get_generate_weekly_briefing.return_value.return_value = "weekly briefing"
            mock_create_notion_page = MagicMock()
            mock_get_create_notion_page.return_value = mock_create_notion_page

            response = weekly_briefing(
                generate_weekly_briefing=get_generate_weekly_briefing(),
                create_notion_page=get_create_notion_page(),
            )

            self.assertEqual(response, {"status": "success"})
            mock_get_create_notion_page().assert_called_once_with("Weekly Competitor Briefing", "weekly briefing")

if __name__ == '__main__':
    unittest.main()
