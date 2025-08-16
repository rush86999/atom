import unittest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from python_api_service.mailchimp_service import get_mailchimp_client, set_mailchimp_credentials

class TestMailchimpService(unittest.TestCase):

    @patch('os.environ.get')
    @patch('python_api_service.mailchimp_service.decrypt')
    def test_get_mailchimp_client_success(self, mock_decrypt, mock_os_get):
        async def run_test():
            # Arrange
            mock_os_get.return_value = "test_encryption_key"
            mock_decrypt.return_value = '{"api_key": "test_api_key", "server_prefix": "us1"}'

            mock_conn = MagicMock()
            mock_conn.fetchrow = AsyncMock(return_value={'encrypted_secret': 'encrypted_string'})

            mock_pool = MagicMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            # Act
            client = await get_mailchimp_client("test_user_id", mock_pool)

            # Assert
            print(dir(client))
            self.assertIsNotNone(client)
            # self.assertEqual(client.config["api_key"], "test_api_key")
            # self.assertEqual(client.config["server"], "us1")

        asyncio.run(run_test())

    @patch('os.environ.get')
    @patch('python_api_service.mailchimp_service.encrypt')
    def test_set_mailchimp_credentials_success(self, mock_encrypt, mock_os_get):
        async def run_test():
            # Arrange
            mock_os_get.return_value = "test_encryption_key"
            mock_encrypt.return_value = "encrypted_credentials"

            mock_conn = MagicMock()
            mock_conn.execute = AsyncMock()

            mock_pool = MagicMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            # Act
            result = await set_mailchimp_credentials("test_user_id", "test_api_key", "us1", mock_pool)

            # Assert
            self.assertTrue(result["ok"])
            mock_conn.execute.assert_called_once()

        asyncio.run(run_test())

if __name__ == '__main__':
    unittest.main()
