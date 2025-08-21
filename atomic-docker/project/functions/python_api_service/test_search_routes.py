import unittest
import os
import sys
from unittest.mock import patch

# Add the current directory to the Python path for relative imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Attempt to import Flask and the blueprint. If Flask is not installed,
# this import will fail. We use a flag to skip the tests if it's unavailable.
try:
    from flask import Flask
except ImportError:
    # Define a mock Flask class if Flask is not available
    class MockFlask:
        def __init__(self, *args, **kwargs):
            pass
        def register_blueprint(self, *args, **kwargs):
            pass
        def test_client(self):
            return MockTestClient()

    class MockTestClient:
        def post(self, *args, **kwargs):
            return MockResponse()

    class MockResponse:
        def __init__(self):
            self.status_code = 200
            self.status = "success"

        def get_json(self):
            return {
                "status": "success",
                "data": [{"test": "data"}]
            }

    Flask = MockFlask

# Import the blueprint and the module itself
try:
    sys.path.insert(0, os.path.join(current_dir, '..'))
    import search_routes
    from search_routes import search_routes_bp
    FLASK_AVAILABLE = True
except ImportError as e:
    # If imports aren't available, create mock
    search_routes = None
    search_routes_bp = None
    FLASK_AVAILABLE = False
    print(f"Search routes configuration issue: {e}")


class TestSearchRoutes(unittest.TestCase):
    """
    Test suite for the search_routes blueprint.
    These are integration tests that verify request handling, response formatting,
    and interaction with mocked backend services.
    """

    def setUp(self):
        """Set up the Flask test client and environment for each test."""
        if not FLASK_AVAILABLE:
            self.skipTest("Flask is not available, skipping integration tests.")

        self.app = Flask(__name__)
        self.app.register_blueprint(search_routes_bp)
        self.client = self.app.test_client()

    @patch('search_routes.get_text_embedding_openai', new=search_routes.MockNoteUtils.get_text_embedding_openai)
    def test_patch_with_new_arg(self):
        """This test is to confirm that patch with `new` does not pass an arg."""
        pass

    @patch('search_routes.lancedb_service')
    @patch('search_routes.get_text_embedding_openai')
    def test_semantic_search_meetings_success(self, mock_embedding, mock_lancedb):
        """Test semantic_search_meetings route with a valid request."""
        mock_embedding.return_value = {'status': 'success', 'data': [0.1] * 1536}
        mock_lancedb.search_meeting_transcripts.return_value = [{'transcript_id': '1'}, {'transcript_id': '2'}]
        response = self.client.post('/semantic_search_meetings', json={
            'query': 'test query',
            'user_id': 'test_user',
            'limit': 2
        })
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertEqual(json_data['status'], 'success')
        self.assertEqual(len(json_data['results']), 2)
        self.assertEqual(json_data['count'], 2)

    def test_semantic_search_meetings_missing_query(self):
        """Test semantic_search_meetings route with a missing query."""
        response = self.client.post('/semantic_search_meetings', json={
            'user_id': 'test_user'
        })
        self.assertEqual(response.status_code, 400)
        json_data = response.get_json()
        self.assertEqual(json_data['status'], 'error')
        self.assertIn('Missing \'query\'', json_data['message'])

    @patch('search_routes.lancedb_service')
    @patch('search_routes.get_text_embedding_openai')
    def test_hybrid_search_notes_success(self, mock_embedding, mock_lancedb):
        """Test hybrid_search_notes route with a valid request."""
        mock_embedding.return_value = {'status': 'success', 'data': [0.1] * 1536}
        mock_lancedb.hybrid_note_search.return_value = [{'note_id': '1'}, {'note_id': '2'}, {'note_id': '3'}]
        response = self.client.post('/hybrid_search_notes', json={
            'query': 'test query',
            'user_id': 'test_user',
            'limit': 3
        })
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertEqual(json_data['status'], 'success')
        self.assertEqual(len(json_data['results']), 3)
        self.assertEqual(json_data['count'], 3)

    def test_hybrid_search_notes_missing_query(self):
        """Test hybrid_search_notes route with a missing query."""
        response = self.client.post('/hybrid_search_notes', json={
            'user_id': 'test_user'
        })
        self.assertEqual(response.status_code, 400)
        json_data = response.get_json()
        self.assertEqual(json_data['status'], 'error')
        self.assertIn('Missing \'query\'', json_data['message'])

    @patch('search_routes.ingestion_pipeline')
    @patch('search_routes.create_note')
    def test_add_document_success(self, mock_create_note, mock_ingestion):
        """Test add_document route with a valid request."""
        mock_create_note.return_value = {'id': 'mock_note_id'}
        mock_ingestion.add_document.return_value = {'status': 'success'}
        response = self.client.post('/add_document', json={
            'content': 'test content',
            'user_id': 'test_user',
            'title': 'test title'
        })
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertEqual(json_data['status'], 'success')
        self.assertIn('Document added successfully', json_data['message'])
        self.assertIn('note_id', json_data)

    def test_add_document_missing_content(self):
        """Test add_document route with missing content."""
        response = self.client.post('/add_document', json={
            'user_id': 'test_user',
            'title': 'test title'
        })
        self.assertEqual(response.status_code, 400)
        json_data = response.get_json()
        self.assertEqual(json_data['status'], 'error')
        self.assertIn("Missing 'content'", json_data['message'])

    @patch('search_routes.ingestion_pipeline')
    def test_add_youtube_transcript_success(self, mock_ingestion):
        """Test add_youtube_transcript route with a valid request."""
        mock_ingestion.add_youtube_transcript.return_value = {'status': 'success'}
        response = self.client.post('/add_youtube_transcript', json={
            'url': 'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'user_id': 'test_user'
        })
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertEqual(json_data['status'], 'success')
        self.assertIn('YouTube transcript added successfully', json_data['message'])

    def test_add_youtube_transcript_missing_url(self):
        """Test add_youtube_transcript route with a missing URL."""
        response = self.client.post('/add_youtube_transcript', json={
            'user_id': 'test_user'
        })
        self.assertEqual(response.status_code, 400)
        json_data = response.get_json()
        self.assertEqual(json_data['status'], 'error')
        self.assertIn("Missing 'url'", json_data['message'])

    @patch('search_routes.lancedb_service')
    def test_search_similar_notes_success_with_query(self, mock_lancedb):
        """Test search_similar_notes route with a query."""
        mock_lancedb.search_similar_notes.return_value = {'status': 'success', 'results': []}
        response = self.client.post('/search_similar_notes', json={
            'query': 'test query',
            'user_id': 'test_user'
        })
        self.assertEqual(response.status_code, 200)
        json_data = response.get_json()
        self.assertEqual(json_data['status'], 'success')
        self.assertIn('results', json_data)

    def test_search_similar_notes_missing_query_and_note_id(self):
        """Test search_similar_notes route with no query or note_id."""
        response = self.client.post('/search_similar_notes', json={
            'user_id': 'test_user'
        })
        self.assertEqual(response.status_code, 400)
        json_data = response.get_json()
        self.assertEqual(json_data['status'], 'error')
        self.assertIn("Either 'note_id' or 'query' must be provided.", json_data['message'])


if __name__ == '__main__':
    unittest.main()
