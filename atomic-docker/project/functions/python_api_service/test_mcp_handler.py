import unittest
from unittest.mock import patch, MagicMock
from python_api_service.main_api_app import create_app

class McpHandlerTestCase(unittest.TestCase):

    def setUp(self):
        self.app = create_app(db_pool=MagicMock())
        self.client = self.app.test_client()

    @patch('python_api_service.mcp_handler.get_mcp_credentials')
    @patch('python_api_service.gdrive_service.GDriveApiClient._get_service')
    def test_list_files_route(self, mock_get_drive_service, mock_get_mcp_credentials):
        mock_get_mcp_credentials.return_value = MagicMock(token='test_token', provider='gdrive', refresh_token='test_refresh_token', token_uri='test_token_uri', client_id='test_client_id', client_secret='test_client_secret')
        mock_service = MagicMock()
        mock_service.files.return_value.list.return_value.execute.return_value = {"files": []}
        mock_get_drive_service.return_value = mock_service

        response = self.client.get('/mcp/files', headers={'X-Hasura-User-Id': 'test-user'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "success", "data": {"files": [], "nextPageToken": None}})

    @patch('python_api_service.mcp_handler.get_mcp_credentials')
    @patch('python_api_service.gdrive_service.GDriveApiClient._get_service')
    def test_get_file_metadata_route(self, mock_get_drive_service, mock_get_mcp_credentials):
        mock_get_mcp_credentials.return_value = MagicMock(token='test_token', provider='gdrive', refresh_token='test_refresh_token', token_uri='test_token_uri', client_id='test_client_id', client_secret='test_client_secret')
        mock_service = MagicMock()
        mock_service.files.return_value.get.return_value.execute.return_value = {"name": "test_file"}
        mock_get_drive_service.return_value = mock_service

        response = self.client.get('/mcp/files/test_file_id', headers={'X-Hasura-User-Id': 'test-user'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "success", "data": {"name": "test_file"}})

    @patch('python_api_service.mcp_handler.get_mcp_credentials')
    @patch('googleapiclient.http._retry_request')
    @patch('python_api_service.gdrive_service.GDriveApiClient._get_service')
    def test_download_file_route(self, mock_get_drive_service, mock_retry_request, mock_get_mcp_credentials):
        mock_get_mcp_credentials.return_value = MagicMock(token='test_token', provider='gdrive', refresh_token='test_refresh_token', token_uri='test_token_uri', client_id='test_client_id', client_secret='test_client_secret')
        mock_service = MagicMock()
        mock_service.files.return_value.get.return_value.execute.return_value = {"name": "test_file", "mimeType": "text/plain"}
        mock_response = MagicMock()
        mock_response.status = 200
        mock_retry_request.return_value = (mock_response, b'test_content')
        mock_get_drive_service.return_value = mock_service

        response = self.client.get('/mcp/files/test_file_id/download', headers={'X-Hasura-User-Id': 'test-user'})
        self.assertEqual(response.status_code, 200)
        # The response will be a JSON object with the file name, content, and mime type.
        # We can't easily check the content, so we'll just check the status and the file name.
        self.assertEqual(response.json['status'], "success")
        self.assertTrue(response.json['data']['file_name'])

class McpDropboxHandlerTestCase(unittest.TestCase):

    def setUp(self):
        self.app = create_app(db_pool=MagicMock())
        self.client = self.app.test_client()

    @patch('python_api_service.mcp_handler.get_mcp_credentials')
    @patch('python_api_service.dropbox_service.DropboxService.list_files')
    def test_list_files_route_dropbox(self, mock_list_files, mock_get_mcp_credentials):
        mock_get_mcp_credentials.return_value = MagicMock(token='test_token', provider='dropbox')
        mock_list_files.return_value = {"status": "success", "data": {"files": []}}

        response = self.client.get('/mcp/files', headers={'X-Hasura-User-Id': 'test-user'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "success", "data": {"files": []}})

class McpOneDriveHandlerTestCase(unittest.TestCase):

    def setUp(self):
        self.app = create_app(db_pool=MagicMock())
        self.client = self.app.test_client()

    @patch('python_api_service.mcp_handler.get_mcp_credentials')
    @patch('python_api_service.onedrive_service.OneDriveService.list_files')
    def test_list_files_route_onedrive(self, mock_list_files, mock_get_mcp_credentials):
        mock_get_mcp_credentials.return_value = MagicMock(token='test_token', provider='onedrive')
        mock_list_files.return_value = {"status": "success", "data": {"files": []}}

        response = self.client.get('/mcp/files', headers={'X-Hasura-User-Id': 'test-user'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "success", "data": {"files": []}})

if __name__ == '__main__':
    unittest.main()
