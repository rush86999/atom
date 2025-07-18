import unittest
from unittest.mock import patch, MagicMock
from python_api_service.main_api_app import create_app

class McpHandlerTestCase(unittest.TestCase):

    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    @patch('python_api_service.mcp_handler.get_mcp_credentials')
    @patch('python_api_service.mcp_service.list_mcp_files')
    def test_list_files_route(self, mock_list_mcp_files, mock_get_mcp_credentials):
        mock_get_mcp_credentials.return_value = MagicMock(token='test_token')
        mock_list_mcp_files.return_value = {"status": "success", "data": {"files": []}}

        response = self.client.get('/mcp/files', headers={'X-Hasura-User-Id': 'test-user'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "success", "data": {"files": []}})

    @patch('python_api_service.mcp_handler.get_mcp_credentials')
    @patch('python_api_service.mcp_service.get_mcp_file_metadata')
    def test_get_file_metadata_route(self, mock_get_mcp_file_metadata, mock_get_mcp_credentials):
        mock_get_mcp_credentials.return_value = MagicMock(token='test_token')
        mock_get_mcp_file_metadata.return_value = {"status": "success", "data": {"name": "test_file"}}

        response = self.client.get('/mcp/files/test_file_id', headers={'X-Hasura-User-Id': 'test-user'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "success", "data": {"name": "test_file"}})

    @patch('python_api_service.mcp_handler.get_mcp_credentials')
    @patch('python_api_service.mcp_service.download_mcp_file')
    def test_download_file_route(self, mock_download_mcp_file, mock_get_mcp_credentials):
        mock_get_mcp_credentials.return_value = MagicMock(token='test_token')
        mock_download_mcp_file.return_value = {"status": "success", "data": {"file_name": "test_file"}}

        response = self.client.get('/mcp/files/test_file_id/download', headers={'X-Hasura-User-Id': 'test-user'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "success", "data": {"file_name": "test_file"}})

if __name__ == '__main__':
    unittest.main()
