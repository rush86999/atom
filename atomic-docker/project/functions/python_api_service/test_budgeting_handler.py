import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from flask import Flask
import json

from .budgeting_handler import budgeting_bp

class TestBudgetingRoutes(unittest.TestCase):

    def setUp(self):
        """Set up a Flask test app and client for each test."""
        self.app = Flask(__name__)
        self.app.register_blueprint(budgeting_bp)
        self.app.testing = True
        self.client = self.app.test_client()
        self.app.config['DB_CONNECTION_POOL'] = MagicMock()

    @patch('atomic-docker.project.functions.python_api_service.budgeting_handler.budgeting_service', new_callable=MagicMock)
    def test_create_budget_success(self, mock_budgeting_service):
        """Test the create budget endpoint for a successful case."""
        mock_budgeting_service.create_budget = AsyncMock(return_value={"id": 1, "name": "Groceries"})

        payload = {
            "user_id": "user-123",
            "name": "Groceries",
            "category": "Food",
            "amount": 500.00,
            "start_date": "2025-01-01"
        }
        response = self.client.post('/api/financial/budgets', json=payload)

        self.assertEqual(response.status_code, 201)
        response_data = response.get_json()
        self.assertTrue(response_data['ok'])
        mock_budgeting_service.create_budget.assert_called_once()

    @patch('atomic-docker.project.functions.python_api_service.budgeting_handler.budgeting_service', new_callable=MagicMock)
    def test_get_budget_summary_success(self, mock_budgeting_service):
        """Test the get budget summary endpoint for a successful case."""
        mock_summary = {"totalBudget": 1000, "totalSpent": 500, "categories": []}
        mock_budgeting_service.get_budget_summary = AsyncMock(return_value=mock_summary)

        response = self.client.get('/api/financial/budgets/summary?userId=user-123')

        self.assertEqual(response.status_code, 200)
        response_data = response.get_json()
        self.assertTrue(response_data['ok'])
        self.assertEqual(response_data['data'], mock_summary)
        mock_budgeting_service.get_budget_summary.assert_called_once_with(
            'user-123', self.app.config['DB_CONNECTION_POOL'], None, None
        )

    def test_get_budget_summary_missing_userid(self):
        """Test the get budget summary endpoint for a validation error."""
        response = self.client.get('/api/financial/budgets/summary') # Missing userId

        self.assertEqual(response.status_code, 400)
        response_data = response.get_json()
        self.assertFalse(response_data['ok'])
        self.assertEqual(response_data['error']['code'], 'VALIDATION_ERROR')
        self.assertIn('userId is required', response_data['error']['message'])

if __name__ == '__main__':
    unittest.main()
