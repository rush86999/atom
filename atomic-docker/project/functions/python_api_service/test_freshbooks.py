import unittest
from unittest.mock import patch, MagicMock
from python_api_service.main_api_app import create_app

class FreshbooksHandlerTestCase(unittest.TestCase):

    def setUp(self):
        self.app = create_app(db_pool=MagicMock())
        self.client = self.app.test_client()

    @patch('python_api_service.freshbooks_service.get_freshbooks_invoices')
    def test_get_invoices(self, mock_get_invoices):
        mock_get_invoices.return_value = []
        response = self.client.get('/api/freshbooks/invoices?user_id=123&account_id=456')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {'ok': True, 'data': []})

if __name__ == '__main__':
    unittest.main()
