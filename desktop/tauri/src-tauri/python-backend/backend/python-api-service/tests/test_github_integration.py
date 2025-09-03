import unittest
from unittest.mock import patch, MagicMock
from ..main_api_app import create_app
from ..github_service import get_user_repositories, create_repository

class GithubIntegrationTestCase(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    @patch('requests.get')
    def test_get_user_repositories(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"name": "test-repo"}]
        mock_get.return_value = mock_response

        with patch('github_service.get_decrypted_credential') as mock_get_credential:
            mock_get_credential.return_value = "test-token"
            response = self.client.get('/github/repos', headers={'user-id': 'test-user'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json, [{"name": "test-repo"}])

    @patch('requests.post')
    def test_create_repository(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"name": "new-repo"}
        mock_post.return_value = mock_response

        with patch('github_service.get_decrypted_credential') as mock_get_credential:
            mock_get_credential.return_value = "test-token"
            response = self.client.post('/github/repos', json={"name": "new-repo"}, headers={'user-id': 'test-user'})
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json, {"name": "new-repo"})

if __name__ == '__main__':
    unittest.main()
