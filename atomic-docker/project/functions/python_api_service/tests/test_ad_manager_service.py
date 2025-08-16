import unittest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from python_api_service.ad_manager_service import create_google_ads_campaign

class TestAdManagerService(unittest.TestCase):

    @patch('python_api_service.ad_manager_service.google_ads_service.get_google_ads_client')
    @patch('python_api_service.ad_manager_service.google_ads_service.create_campaign')
    def test_create_google_ads_campaign_success(self, mock_create_campaign, mock_get_google_ads_client):
        async def run_test():
            # Arrange
            mock_get_google_ads_client.return_value = MagicMock()
            mock_create_campaign.return_value = {"campaign_id": "12345"}

            mock_pool = MagicMock()

            # Act
            result = await create_google_ads_campaign("test_user_id", "test_customer_id", {}, mock_pool)

            # Assert
            self.assertEqual(result, {"campaign_id": "12345"})
            mock_get_google_ads_client.assert_called_once_with("test_user_id", mock_pool)
            mock_create_campaign.assert_called_once()

        asyncio.run(run_test())

if __name__ == '__main__':
    unittest.main()
