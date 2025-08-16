import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from flask import Flask
import json

# Import the blueprint after mocking dependencies if necessary, but here it's simple
from .transaction_handler import transaction_bp

class TestTransactionRoutes(unittest.TestCase):

    def setUp(self):
        """Set up a Flask test app and client for each test."""
        self.app = Flask(__name__)
        self.app.register_blueprint(transaction_bp)
        self.app.testing = True
        self.client = self.app.test_client()
        # Mock the database connection pool that the handler expects
        self.app.config['DB_CONNECTION_POOL'] = MagicMock()

    @patch('atomic-docker.project.functions.python_api_service.transaction_handler.transaction_service', new_callable=MagicMock)
    def test_search_transactions_success(self, mock_transaction_service):
        """Test the transaction search endpoint for a successful case."""
        # Configure the mock service to return a specific value
        mock_search_result = [
            {"id": 1, "description": "Coffee", "amount": -5.50},
            {"id": 2, "description": "More Coffee", "amount": -6.00}
        ]
        # Since the service function is async, the mock needs to be an AsyncMock
        mock_transaction_service.search_transactions = AsyncMock(return_value=mock_search_result)

        payload = {
            "userId": "user-123",
            "query": "Coffee",
            "dateRange": {"start": "2025-01-01", "end": "2025-01-31"}
        }

        # Use the test client to make a request
        response = self.client.post('/api/transactions/search', json=payload)

        # Assertions
        self.assertEqual(response.status_code, 200)
        response_data = response.get_json()
        self.assertTrue(response_data['ok'])
        self.assertEqual(response_data['transactions'], mock_search_result)

        # Verify that the service function was called with the correct arguments
        mock_transaction_service.search_transactions.assert_called_once_with(
            user_id='user-123',
            db_conn_pool=self.app.config['DB_CONNECTION_POOL'],
            query='Coffee',
            category=None, # from payload.get('category')
            date_range={'start': '2025-01-01', 'end': '2025-01-31'},
            amount_range=None, # from payload.get('amountRange')
            limit=50 # default
        )

    def test_search_transactions_missing_userid(self):
        """Test the transaction search endpoint for a validation error (missing userId)."""
        payload = {"query": "Coffee"} # Missing userId
        response = self.client.post('/api/transactions/search', json=payload)

        self.assertEqual(response.status_code, 400)
        response_data = response.get_json()
        self.assertFalse(response_data['ok'])
        self.assertEqual(response_data['error']['code'], 'VALIDATION_ERROR')
        self.assertIn('userId is required', response_data['error']['message'])

if __name__ == '__main__':
    unittest.main()
