import unittest
import json
from unittest.mock import patch

# Attempt to import Flask and the blueprint. If Flask is not installed,
# this import will fail. We use a flag to skip the tests if it's unavailable.
try:
    from flask import Flask, jsonify  # type: ignore
    from search_routes import search_routes_bp  # type: ignore
    FLASK_AVAILABLE = True
except ImportError:
    # If Flask isn't installed, we can't run the tests, so we set a flag.
    # The test class will check this flag and skip all tests.
    FLASK_AVAILABLE = False
    search_routes_bp = None
    print("Flask library not found. Skipping search routes tests.")


@unittest.skipIf(not FLASK_AVAILABLE, "Flask library is not installed, skipping integration tests for search routes.")
class TestSearchRoutes(unittest.TestCase):
    """
    Test suite for the search_routes blueprint.
    These are integration tests that verify request handling, response formatting,
    and interaction with mocked backend services.
    """

    def setUp(self):
        """Set up the Flask test client and environment for each test."""
        self.app = Flask(__name__)
        self.app.register_blueprint(search_routes_bp, url_prefix='/api')
        self.app.testing = True
        self.client = self.app.test_client()

    @patch('python_api_service.search_routes.lancedb_service.search_meeting_transcripts')
    @patch('python_api_service.search_routes.get_text_embedding_openai')
    @patch('python_api_service.search_routes.os.environ.get')
    def test_semantic_search_meetings_success(self, mock_env_get, mock_get_embedding, mock_search_transcripts):
        """Test a successful semantic search for meeting transcripts."""
        # Arrange: Configure mocks to simulate a successful workflow.
        mock_env_get.return_value = "dummy_lancedb_uri"
        mock_get_embedding.return_value = {"status": "success", "data": [0.1] * 1536}
        mock_search_transcripts.return_value = {
            "status": "success",
            "data": [
                {"notion_page_id": "page123", "notion_page_title": "Project Alpha Meeting", "score": 0.95}
            ]
        }
        payload = {"query": "project alpha", "user_id": "user123", "openai_api_key": "sk-test"}

        # Act: Make the HTTP POST request to the endpoint.
        response = self.client.post('/api/semantic_search_meetings', json=payload)
        data = response.get_json()

        # Assert: Verify the HTTP response and data payload are correct.
        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["status"], "success")
        self.assertIsInstance(data["data"], list)
        self.assertEqual(len(data["data"]), 1)
        self.assertEqual(data["data"][0]["notion_page_id"], "page123")
        self.assertEqual(data["data"][0]["notion_page_title"], "Project Alpha Meeting")

        # Assert: Verify that the backend services were called with the correct parameters.
        mock_env_get.assert_called_with("LANCEDB_URI")
        mock_get_embedding.assert_called_once_with(text_to_embed="project alpha", openai_api_key_param="sk-test")
        mock_search_transcripts.assert_called_once_with(
            db_path="dummy_lancedb_uri",
            query_vector=[0.1] * 1536,
            user_id="user123",
            table_name="meeting_transcripts_embeddings",
            limit=5
        )

    def test_semantic_search_missing_parameters(self):
        """Test error handling for requests missing 'query' or 'user_id'."""
        # Test case for missing 'query'.
        response_no_query = self.client.post('/api/semantic_search_meetings', json={"user_id": "user123"})
        self.assertEqual(response_no_query.status_code, 400)
        self.assertIn("Missing 'query' in request body", response_no_query.get_json()["message"])

        # Test case for missing 'user_id'.
        response_no_user = self.client.post('/api/semantic_search_meetings', json={"query": "test query"})
        self.assertEqual(response_no_user.status_code, 400)
        self.assertIn("Missing 'user_id' in request body", response_no_user.get_json()["message"])

    @patch('python_api_service.search_routes.os.environ.get')
    def test_semantic_search_lancedb_uri_not_configured(self, mock_env_get):
        """Test the 500 error response when the LANCEDB_URI environment variable is not set."""
        # Arrange
        mock_env_get.return_value = None  # Simulate that the environment variable is not configured.
        payload = {"query": "test", "user_id": "user123"}

        # Act
        response = self.client.post('/api/semantic_search_meetings', json=payload)
        data = response.get_json()

        # Assert
        self.assertEqual(response.status_code, 500)
        self.assertEqual(data["status"], "error")
        self.assertIn("LANCEDB_URI missing from environment", data["message"])

    @patch('python_api_service.search_routes.get_text_embedding_openai')
    @patch('python_api_service.search_routes.os.environ.get')
    def test_semantic_search_embedding_failure(self, mock_env_get, mock_get_embedding):
        """Test the 500 error response when the embedding service returns an error."""
        # Arrange
        mock_env_get.return_value = "dummy_lancedb_uri"
        mock_get_embedding.return_value = {"status": "error", "message": "OpenAI API key invalid"}
        payload = {"query": "test", "user_id": "user123", "openai_api_key": "bad-key"}

        # Act
        response = self.client.post('/api/semantic_search_meetings', json=payload)
        data = response.get_json()

        # Assert
        self.assertEqual(response.status_code, 500)
        self.assertEqual(data["status"], "error")
        self.assertIn("Failed to process query", data["message"])
        self.assertIn("OpenAI API key invalid", data["message"]) # Check that the underlying error is propagated.

    @patch('python_api_service.search_routes.lancedb_service.search_meeting_transcripts')
    @patch('python_api_service.search_routes.get_text_embedding_openai')
    @patch('python_api_service.search_routes.os.environ.get')
    def test_semantic_search_lancedb_failure(self, mock_env_get, mock_get_embedding, mock_search_transcripts):
        """Test the 500 error response when the LanceDB search itself fails."""
        # Arrange
        mock_env_get.return_value = "dummy_lancedb_uri"
        mock_get_embedding.return_value = {"status": "success", "data": [0.1] * 1536}
        mock_search_transcripts.return_value = {"status": "error", "message": "Could not connect to DB"}
        payload = {"query": "test", "user_id": "user123"}

        # Act
        response = self.client.post('/api/semantic_search_meetings', json=payload)
        data = response.get_json()

        # Assert
        self.assertEqual(response.status_code, 500)
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["message"], "Could not connect to DB")


if __name__ == '__main__':
    unittest.main()
