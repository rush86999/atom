import unittest
from unittest.mock import patch, MagicMock
import json
from flask import Flask
import os # Added for sys.path manipulation, if needed, though test structure assumes correct PYTHONPATH

# To ensure python_api_service and its submodules like _utils can be found,
# we might need to adjust sys.path here, similar to how note_handler.py does it.
# This depends on where the tests are run from.
# For subtask robustness, we'll assume the provided import structure in the test
# will work if the test runner's environment is set up correctly.

# Attempt to import the blueprint.
try:
    # This assumes 'python_api_service' is on PYTHONPATH or tests are run from 'functions' directory
    from python_api_service.search_routes import search_routes_bp
    # Also attempt to import the modules that search_routes.py itself tries to import,
    # so we can patch them effectively if they were successfully imported by search_routes.py
    # If search_routes.py had to use its mocks, these patches might target those mocks if not careful,
    # but the goal is to patch what search_routes.py *uses*.
    from python_api_service._utils import lancedb_service # For patching lancedb_service.search_similar_notes
    from python_api_service import note_utils # For patching get_text_embedding_openai if it's from there
                                      # search_routes.py actually imports from global note_utils
                                      # So, the patch target for get_text_embedding_openai should be
                                      # where it's defined or imported in search_routes.py's scope.
                                      # The original code uses `from note_utils import get_text_embedding_openai`
                                      # which is ambiguous here. It should be relative to `FUNCTIONS_DIR`
                                      # or `python_api_service` package.
                                      # For the purpose of the test, the patch targets in test methods are key.
except ImportError as e_main:
    print(f"Warning: Initial import attempt for search_routes_bp or its dependencies failed: {e_main}. This might be due to PYTHONPATH issues.")
    # Fallback for local execution or specific structures if functions/ is the root for python_api_service
    FUNCTIONS_DIR_TEST = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if FUNCTIONS_DIR_TEST not in sys.path:
        sys.path.insert(0, FUNCTIONS_DIR_TEST)

    try:
        from python_api_service.search_routes import search_routes_bp
    except ImportError as e_fallback:
        print(f"Critical: Could not import search_routes_bp for testing even after path adjustment: {e_fallback}. Ensure PYTHONPATH is correct or that python_api_service is a package.")
        search_routes_bp = None


class TestSearchRoutes(unittest.TestCase):

    def setUp(self):
        if not search_routes_bp:
            self.skipTest("search_routes_bp could not be imported. Skipping tests for search_routes.")

        self.app = Flask(__name__)
        self.app.register_blueprint(search_routes_bp, url_prefix='/api')
        self.app.testing = True # Enable testing mode for better error handling
        self.client = self.app.test_client()

    # Patching os.environ.get as it's used in search_routes.py
    @patch('python_api_service.search_routes.os.environ.get')
    # Patching get_text_embedding_openai where it's imported and used in search_routes.py
    # search_routes.py has `from note_utils import get_text_embedding_openai` (potentially problematic if note_utils is not in path)
    # or its own mock. We assume it resolves to *something* that we can patch in its namespace.
    @patch('python_api_service.search_routes.get_text_embedding_openai')
    # Patching lancedb_service.search_similar_notes where it's imported and used in search_routes.py
    @patch('python_api_service.search_routes.lancedb_service.search_similar_notes')
    def test_semantic_search_meetings_success(self, mock_search_similar_notes, mock_get_embedding, mock_env_get):
        # Configure mocks
        mock_env_get.return_value = "dummy_lancedb_uri" # For LANCEDB_URI
        mock_get_embedding.return_value = {"status": "success", "data": [0.05] * 1536}
        mock_search_similar_notes.return_value = {
            "status": "success",
            "data": [
                {"id": "page1", "title": "Meeting A", "date": "2023-01-01T10:00:00Z", "score": 0.9, "user_id": "user1"}
            ]
        }

        payload = {"query": "test query", "user_id": "user1", "openai_api_key": "test_key"}
        response = self.client.post('/api/semantic_search_meetings', json=payload)

        self.assertEqual(response.status_code, 200, f"Response data: {response.data.decode()}")
        data = response.get_json()
        self.assertEqual(data["status"], "success")
        self.assertIsInstance(data["data"], list)
        self.assertEqual(len(data["data"]), 1)
        self.assertEqual(data["data"][0]["notion_page_id"], "page1")
        self.assertEqual(data["data"][0]["meeting_title"], "Meeting A")
        self.assertEqual(data["data"][0]["score"], 0.9)

        mock_get_embedding.assert_called_once_with(text_to_embed="test query", openai_api_key_param="test_key")
        mock_search_similar_notes.assert_called_once_with(
            db_path="dummy_lancedb_uri",
            query_vector=[0.05] * 1536,
            user_id="user1",
            table_name="meeting_transcripts",
            limit=5
        )

    @patch('python_api_service.search_routes.os.environ.get')
    def test_semantic_search_missing_query(self, mock_env_get):
        if not search_routes_bp: self.skipTest("Blueprint not loaded")
        mock_env_get.return_value = "dummy_lancedb_uri"
        payload = {"user_id": "user1"} # Missing 'query'
        response = self.client.post('/api/semantic_search_meetings', json=payload)
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertEqual(data["status"], "error")
        self.assertIn("Missing 'query'", data["message"])

    @patch('python_api_service.search_routes.os.environ.get')
    def test_semantic_search_lancedb_uri_not_configured(self, mock_env_get):
        if not search_routes_bp: self.skipTest("Blueprint not loaded")
        mock_env_get.return_value = None # Simulate LANCEDB_URI not set
        payload = {"query": "test query"}
        response = self.client.post('/api/semantic_search_meetings', json=payload)
        self.assertEqual(response.status_code, 500)
        data = response.get_json()
        self.assertEqual(data["status"], "error")
        self.assertIn("LANCEDB_URI missing", data["message"])

    @patch('python_api_service.search_routes.os.environ.get')
    @patch('python_api_service.search_routes.get_text_embedding_openai')
    def test_semantic_search_embedding_failure(self, mock_get_embedding, mock_env_get):
        if not search_routes_bp: self.skipTest("Blueprint not loaded")
        mock_env_get.return_value = "dummy_lancedb_uri"
        mock_get_embedding.return_value = {"status": "error", "message": "Embedding generation failed"}

        payload = {"query": "test query"}
        response = self.client.post('/api/semantic_search_meetings', json=payload)
        self.assertEqual(response.status_code, 500)
        data = response.get_json()
        self.assertEqual(data["status"], "error")
        self.assertIn("Failed to process query: Embedding generation failed", data["message"])

    @patch('python_api_service.search_routes.os.environ.get')
    @patch('python_api_service.search_routes.get_text_embedding_openai')
    @patch('python_api_service.search_routes.lancedb_service.search_similar_notes')
    def test_semantic_search_lancedb_failure(self, mock_search_similar_notes, mock_get_embedding, mock_env_get):
        if not search_routes_bp: self.skipTest("Blueprint not loaded")
        mock_env_get.return_value = "dummy_lancedb_uri"
        mock_get_embedding.return_value = {"status": "success", "data": [0.05] * 1536}
        mock_search_similar_notes.return_value = {"status": "error", "message": "LanceDB search failed"}

        payload = {"query": "test query"}
        response = self.client.post('/api/semantic_search_meetings', json=payload)
        self.assertEqual(response.status_code, 500)
        data = response.get_json()
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["message"], "LanceDB search failed")

if __name__ == '__main__':
    # This allows running the tests directly from this file,
    # but it's better to run them using a test runner like `python -m unittest discover`
    # or `pytest` from the root of the project or `functions` directory,
    # ensuring PYTHONPATH is set up correctly for imports.
    unittest.main()
