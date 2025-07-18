import unittest
from unittest.mock import patch, MagicMock, ANY
import json
from flask import Flask
from datetime import datetime, timezone
import os # For sys.path manipulation if needed, though test assumes correct PYTHONPATH

from atomic-docker.project.functions.python_api_service.task_routes import task_bp

# This mock will be used by the class-level patch
mock_notion_client_instance = MagicMock()

def setUpModule():
    """Skips all tests in this module if task_bp could not be imported."""
    if task_bp is None:
        raise unittest.SkipTest("task_bp could not be imported from python_api_service.task_routes. Skipping all tests in test_task_routes.py")

# Patch NotionClient where it's imported in task_routes.py
@patch('python_api_service.task_routes.NotionClient', return_value=mock_notion_client_instance)
class TestTaskRoutes(unittest.TestCase):

    def setUp(self):
        """Set up a Flask test app and client for each test."""
        self.app = Flask(__name__)
        self.app.register_blueprint(task_bp, url_prefix='/api')
        self.app.testing = True
        self.client = self.app.test_client()

        # Reset mocks before each test to ensure test isolation
        mock_notion_client_instance.reset_mock()
        # Re-assign specific method mocks as they might be cleared by reset_mock() on the parent
        mock_notion_client_instance.pages.create = MagicMock(return_value={"id": "default_page_id", "url": "http://notion.so/default"})
        mock_notion_client_instance.databases.query = MagicMock(return_value={"results": []})
        mock_notion_client_instance.pages.update = MagicMock(return_value={"id": "default_updated_id"})


    @patch('python_api_service.task_routes.os.environ.get')
    def test_create_task_success(self, mock_env_get, MockNotionClientClass): # MockNotionClientClass is the class mock from @patch
        env_vars = {"ATOM_NOTION_API_TOKEN": "test_token"}
        # Configure os.environ.get mock for this test
        mock_env_get.side_effect = lambda k, d=None: env_vars.get(k, d)

        # Configure the specific method mock on the shared instance
        mock_notion_client_instance.pages.create.return_value = {"id": "page_123", "url": "http://notion.so/page_123"}

        payload = {
            "description": "My new task", "dueDate": "2024-12-20", "status": "To Do",
            "priority": "High", "listName": "Work", "notes": "Detailed notes here.",
            "notion_db_id": "test_db_id"
        }
        response = self.client.post('/api/create-notion-task', json=payload)

        self.assertEqual(response.status_code, 201, f"Response data: {response.data.decode()}")
        data = response.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["data"]["taskId"], "page_123")

        mock_notion_client_instance.pages.create.assert_called_once()
        args, kwargs = mock_notion_client_instance.pages.create.call_args
        self.assertEqual(kwargs['parent']['database_id'], "test_db_id")
        self.assertEqual(kwargs['properties']['Task Description']['title'][0]['text']['content'], "My new task")
        self.assertEqual(kwargs['properties']['Due Date']['date']['start'], "2024-12-20")
        self.assertEqual(kwargs['properties']['Status']['select']['name'], "To Do")
        self.assertEqual(kwargs['properties']['Priority']['select']['name'], "High")
        self.assertEqual(kwargs['properties']['List Name']['rich_text'][0]['text']['content'], "Work")
        self.assertEqual(len(kwargs['children']), 1) # Assuming notes create one block
        self.assertEqual(kwargs['children'][0]['paragraph']['rich_text'][0]['text']['content'], "Detailed notes here.")


    @patch('python_api_service.task_routes.os.environ.get')
    def test_create_task_missing_description(self, mock_env_get, MockNotionClientClass):
        env_vars = {"ATOM_NOTION_API_TOKEN": "test_token"}
        mock_env_get.side_effect = lambda k, d=None: env_vars.get(k, d)
        payload = {"dueDate": "2024-12-20", "notion_db_id": "test_db_id"} # Missing description
        response = self.client.post('/api/create-notion-task', json=payload)
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data["ok"])
        self.assertEqual(data["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("Task description is required", data["error"]["message"])

    @patch('python_api_service.task_routes.os.environ.get')
    def test_query_tasks_success(self, mock_env_get, MockNotionClientClass):
        env_vars = {"ATOM_NOTION_API_TOKEN": "test_token"}
        mock_env_get.side_effect = lambda k, d=None: env_vars.get(k, d)

        mock_notion_client_instance.databases.query.return_value = {
            "results": [{
                "id": "page_abc", "url": "http://notion.so/page_abc", "created_time": "2023-01-01T00:00:00Z",
                "properties": {
                    "Task Description": {"title": [{"type": "text", "plain_text": "Fetched Task 1"}]},
                    "Due Date": {"date": {"start": "2024-01-15"}},
                    "Status": {"select": {"name": "In Progress"}},
                    "Priority": {"select": {"name": "Medium"}},
                    "List Name": {"rich_text": [{"type": "text", "plain_text": "Project X"}]}
                }
            }]
        }
        payload = {"status": "In Progress", "notion_db_id": "test_db_id"}
        response = self.client.post('/api/query-notion-tasks', json=payload)
        self.assertEqual(response.status_code, 200, f"Response data: {response.data.decode()}")
        data = response.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(len(data["data"]), 1)
        self.assertEqual(data["data"][0]["description"], "Fetched Task 1")
        self.assertEqual(data["data"][0]["status"], "In Progress")

        mock_notion_client_instance.databases.query.assert_called_once()
        args, kwargs = mock_notion_client_instance.databases.query.call_args
        self.assertEqual(kwargs['database_id'], "test_db_id")
        # Check if the status filter is correctly applied within the 'and' or directly
        if 'and' in kwargs['filter']:
            self.assertTrue(any(
                f.get("property") == "Status" and f.get("select", {}).get("equals") == "In Progress"
                for f in kwargs['filter']['and']
            ))
        else: # Single filter
            self.assertEqual(kwargs['filter']['property'], "Status")
            self.assertEqual(kwargs['filter']['select']['equals'], "In Progress")


    @patch('python_api_service.task_routes.os.environ.get')
    @patch('python_api_service.task_routes._resolve_date_query') # Patch helper in its own module
    def test_query_tasks_with_date_query(self, mock_resolve_date, mock_env_get, MockNotionClientClass):
        env_vars = {"ATOM_NOTION_API_TOKEN": "test_token"}
        mock_env_get.side_effect = lambda k, d=None: env_vars.get(k, d)

        # _resolve_date_query returns ISO strings. Notion date filter takes YYYY-MM-DD for "equals".
        mock_resolve_date.return_value = ("2024-01-10T00:00:00+00:00", "2024-01-10T00:00:00+00:00")
        mock_notion_client_instance.databases.query.return_value = {"results": []} # No data needed, just checking filter

        payload = {"dateQuery": "today", "notion_db_id": "test_db_id"}
        response = self.client.post('/api/query-notion-tasks', json=payload)

        self.assertEqual(response.status_code, 200, f"Response data: {response.data.decode()}")
        mock_resolve_date.assert_called_once_with("today")

        args, kwargs = mock_notion_client_instance.databases.query.call_args
        expected_date_filter = {"property": "Due Date", "date": {"equals": "2024-01-10"}} # Check for YYYY-MM-DD

        if 'and' in kwargs['filter']:
             self.assertIn(expected_date_filter, kwargs['filter']['and'])
        else: # Single filter
            self.assertEqual(kwargs['filter'], expected_date_filter)


    @patch('python_api_service.task_routes.os.environ.get')
    def test_update_task_success(self, mock_env_get, MockNotionClientClass):
        env_vars = {"ATOM_NOTION_API_TOKEN": "test_token"}
        mock_env_get.side_effect = lambda k, d=None: env_vars.get(k, d)

        mock_notion_client_instance.pages.update.return_value = {"id": "task_xyz"} # Notion update returns the page object

        payload = {"taskId": "task_xyz", "status": "Done", "priority": "Low"}
        response = self.client.post('/api/update-notion-task', json=payload)

        self.assertEqual(response.status_code, 200, f"Response data: {response.data.decode()}")
        data = response.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["data"]["taskId"], "task_xyz")
        self.assertIn("status", data["data"]["updatedProperties"])
        self.assertIn("priority", data["data"]["updatedProperties"])

        mock_notion_client_instance.pages.update.assert_called_once()
        args, kwargs = mock_notion_client_instance.pages.update.call_args
        self.assertEqual(kwargs['page_id'], "task_xyz")
        self.assertEqual(kwargs['properties']['Status']['select']['name'], "Done")
        self.assertEqual(kwargs['properties']['Priority']['select']['name'], "Low")

    @patch('python_api_service.task_routes.os.environ.get')
    def test_update_task_missing_task_id(self, mock_env_get, MockNotionClientClass):
        env_vars = {"ATOM_NOTION_API_TOKEN": "test_token"}
        mock_env_get.side_effect = lambda k, d=None: env_vars.get(k, d)

        payload = {"status": "Done"} # Missing taskId
        response = self.client.post('/api/update-notion-task', json=payload)
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertFalse(data["ok"])
        self.assertEqual(data["error"]["code"], "VALIDATION_ERROR")
        self.assertIn("Task ID (taskId) is required", data["error"]["message"])

    @patch('python_api_service.task_routes.os.environ.get')
    def test_update_task_no_updatable_fields(self, mock_env_get, MockNotionClientClass):
        env_vars = {"ATOM_NOTION_API_TOKEN": "test_token"}
        mock_env_get.side_effect = lambda k, d=None: env_vars.get(k, d)

        payload = {"taskId": "task_xyz"} # No actual fields to update
        response = self.client.post('/api/update-notion-task', json=payload)

        self.assertEqual(response.status_code, 200, f"Response data: {response.data.decode()}")
        data = response.get_json()
        self.assertTrue(data["ok"])
        self.assertIn("No updateable fields provided", data["data"]["message"])
        mock_notion_client_instance.pages.update.assert_not_called()

if __name__ == '__main__':
    unittest.main()
