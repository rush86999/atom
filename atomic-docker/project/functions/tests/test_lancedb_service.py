import unittest
from unittest.mock import patch, MagicMock, call
from datetime import datetime
import os # For patching os.environ if needed for db_path, and os.path/os.makedirs

# Assuming lancedb_service.py is in _utils relative to 'functions' directory
# and tests are in 'functions/tests'.
# Adjust sys.path to allow importing from _utils
import sys
FUNCTIONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
UTILS_DIR = os.path.join(FUNCTIONS_DIR, '_utils')
if FUNCTIONS_DIR not in sys.path:
    sys.path.insert(0, FUNCTIONS_DIR) # Make 'functions' package available
if UTILS_DIR not in sys.path:
    sys.path.insert(0, UTILS_DIR) # Make '_utils' available for direct import if needed

# Import functions and classes to be tested from lancedb_service
from _utils.lancedb_service import (
    create_meeting_transcripts_table_if_not_exists,
    add_transcript_embedding,
    search_similar_notes,
    MeetingTranscriptSchema, # For asserting schema in create_table
    NoteSearchResult # For type hinting and asserting search results
)

class TestLanceDBService(unittest.TestCase):

    def setUp(self):
        # This mock will be used for the lancedb.connect() call within the service functions
        self.mock_db_connection = MagicMock()
        self.mock_table = MagicMock()

        # Configure db.open_table to return the mock_table
        self.mock_db_connection.open_table.return_value = self.mock_table
        # Configure db.table_names()
        self.mock_db_connection.table_names.return_value = []
        # Configure db.create_table()
        self.mock_db_connection.create_table.return_value = self.mock_table

        # Configure table methods
        self.mock_table.add = MagicMock()
        self.mock_table.delete = MagicMock()

        # Setup chainable search methods
        mock_search_intermediate = MagicMock()
        self.mock_table.search.return_value = mock_search_intermediate
        mock_search_intermediate.limit.return_value = mock_search_intermediate
        mock_search_intermediate.where.return_value = mock_search_intermediate
        mock_search_intermediate.select.return_value = mock_search_intermediate
        mock_search_intermediate.to_list.return_value = [] # Default to empty results

        self.mock_table.count_rows.return_value = 0


    @patch('os.makedirs')
    @patch('os.path.exists')
    @patch('lancedb.connect') # Patch where lancedb.connect is looked up (module where it's called)
    def test_create_meeting_transcripts_table_if_not_exists_creates_when_not_present(
        self, mock_lancedb_connect, mock_os_path_exists, mock_os_makedirs
    ):
        mock_lancedb_connect.return_value = self.mock_db_connection
        mock_os_path_exists.return_value = False # Simulate directory does not exist for local DB
        self.mock_db_connection.table_names.return_value = [] # Table does not exist

        create_meeting_transcripts_table_if_not_exists("local/db/path", table_name="test_transcripts")

        mock_lancedb_connect.assert_called_once_with("local/db/path")
        mock_os_path_exists.assert_called_once() # Check if dir exists
        mock_os_makedirs.assert_called_once()    # Create dir
        self.mock_db_connection.table_names.assert_called_once()
        self.mock_db_connection.create_table.assert_called_once_with(
            "test_transcripts", schema=MeetingTranscriptSchema, mode="create"
        )

    @patch('os.path.exists') # Assuming local DB path, so os.path.exists might be checked
    @patch('lancedb.connect')
    def test_create_meeting_transcripts_table_if_not_exists_does_nothing_if_present(
        self, mock_lancedb_connect, mock_os_path_exists
    ):
        mock_lancedb_connect.return_value = self.mock_db_connection
        mock_os_path_exists.return_value = True # Directory exists
        self.mock_db_connection.table_names.return_value = ["test_transcripts"] # Table exists

        create_meeting_transcripts_table_if_not_exists("local/db/path", table_name="test_transcripts")

        mock_lancedb_connect.assert_called_once_with("local/db/path")
        self.mock_db_connection.table_names.assert_called_once()
        self.mock_db_connection.create_table.assert_not_called()

    @patch('lancedb.connect')
    def test_add_transcript_embedding_success(self, mock_lancedb_connect):
        mock_lancedb_connect.return_value = self.mock_db_connection

        test_date = datetime(2024, 1, 1, 12, 0, 0)
        result = add_transcript_embedding(
            db_path="dummy/path",
            notion_page_id="page123",
            meeting_title="Test Meeting",
            meeting_date=test_date,
            transcript_chunk="This is a test chunk.",
            vector_embedding=[0.1] * 1536,
            user_id="user1"
        )

        self.assertEqual(result["status"], "success")
        self.mock_table.add.assert_called_once()
        added_data = self.mock_table.add.call_args[0][0] # Get the first positional argument
        self.assertEqual(len(added_data), 1)
        self.assertEqual(added_data[0]["notion_page_id"], "page123")
        self.assertEqual(added_data[0]["meeting_title"], "Test Meeting")
        self.assertEqual(added_data[0]["meeting_date"], test_date)
        self.assertEqual(added_data[0]["transcript_chunk"], "This is a test chunk.")
        self.assertEqual(len(added_data[0]["vector"]), 1536)
        self.assertIsInstance(added_data[0]["created_at"], datetime)


    @patch('lancedb.connect')
    def test_add_transcript_embedding_table_not_found(self, mock_lancedb_connect):
        mock_lancedb_connect.return_value = self.mock_db_connection
        self.mock_db_connection.open_table.side_effect = FileNotFoundError("Table not found")

        result = add_transcript_embedding(
            db_path="dummy/path", notion_page_id="p1", meeting_title="t1",
            meeting_date=datetime.now(), transcript_chunk="c1", vector_embedding=[0.1]*1536
        )
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["code"], "LANCEDB_TABLE_NOT_FOUND")
        self.mock_table.add.assert_not_called()

    def test_add_transcript_embedding_missing_params(self):
        result = add_transcript_embedding(
            db_path="dummy/path", notion_page_id="", meeting_title="t1", # notion_page_id is empty
            meeting_date=datetime.now(), transcript_chunk="c1", vector_embedding=[0.1]*1536
        )
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["code"], "VALIDATION_ERROR")


    @patch('lancedb.connect')
    def test_search_similar_notes_for_meeting_transcripts(self, mock_lancedb_connect):
        mock_lancedb_connect.return_value = self.mock_db_connection

        mock_meeting_date = datetime(2023, 1, 1, 10, 0, 0)
        mock_lance_results = [
            {"notion_page_id": "page1", "meeting_title": "Sync Up", "meeting_date": mock_meeting_date, "_distance": 0.1, "user_id": "user1"},
            {"notion_page_id": "page2", "meeting_title": "Planning", "meeting_date": datetime(2023,1,2,14,0,0), "_distance": 0.2, "user_id": "user1"}
        ]
        # Configure the chained calls for search
        self.mock_table.search.return_value.limit.return_value.where.return_value.select.return_value.to_list.return_value = mock_lance_results

        result = search_similar_notes(
            db_path="dummy/path",
            query_vector=[0.1]*1536,
            user_id="user1",
            table_name="meeting_transcripts",
            limit=2
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["data"]), 2)

        # Check that select was called with correct fields for meeting_transcripts
        # The mock setup for chained calls needs to point to the final mock object that has .select
        final_select_mock = self.mock_table.search.return_value.limit.return_value.where.return_value.select
        final_select_mock.assert_called_once_with(
            ["user_id", "notion_page_id", "meeting_title", "meeting_date"]
        )

        # Check formatted data
        first_item = result["data"][0]
        self.assertEqual(first_item["id"], "page1")
        self.assertEqual(first_item["title"], "Sync Up")
        self.assertEqual(first_item["date"], mock_meeting_date.isoformat())
        self.assertEqual(first_item["score"], 0.1)
        self.assertEqual(first_item["user_id"], "user1")

    @patch('lancedb.connect')
    def test_search_similar_notes_for_notes_table(self, mock_lancedb_connect):
        mock_lancedb_connect.return_value = self.mock_db_connection

        mock_updated_date = datetime(2023, 5, 5, 10, 0, 0)
        mock_lance_results = [
            {"note_id": "noteA", "updated_at": mock_updated_date, "_distance": 0.3, "user_id": "user2"},
        ]
        self.mock_table.search.return_value.limit.return_value.where.return_value.select.return_value.to_list.return_value = mock_lance_results

        result = search_similar_notes(
            db_path="dummy/path",
            query_vector=[0.2]*1536,
            user_id="user2",
            table_name="notes", # Explicitly testing "notes" table
            limit=1
        )
        self.assertEqual(result["status"], "success")
        self.assertEqual(len(result["data"]), 1)

        final_select_mock = self.mock_table.search.return_value.limit.return_value.where.return_value.select
        final_select_mock.assert_called_once_with(
             ["user_id", "note_id", "updated_at"]
        )

        first_item = result["data"][0]
        self.assertEqual(first_item["id"], "noteA")
        self.assertIsNone(first_item["title"]) # No title for "notes" table
        self.assertEqual(first_item["date"], mock_updated_date.isoformat())
        self.assertEqual(first_item["score"], 0.3)

    @patch('lancedb.connect')
    def test_search_similar_notes_user_id_filter(self, mock_lancedb_connect):
        mock_lancedb_connect.return_value = self.mock_db_connection
        self.mock_table.search.return_value.limit.return_value.where.return_value.select.return_value.to_list.return_value = []

        search_similar_notes(
            db_path="dummy/path", query_vector=[0.1]*1536, user_id="userTest123", table_name="meeting_transcripts"
        )
        # Check if 'where' was called correctly
        self.mock_table.search.return_value.limit.return_value.where.assert_called_once_with("user_id = 'userTest123'")

        # Test without user_id (no .where call)
        self.mock_table.search.return_value.limit.return_value.where.reset_mock() # Reset for next assertion
        search_similar_notes(
            db_path="dummy/path", query_vector=[0.1]*1536, user_id=None, table_name="meeting_transcripts"
        )
        self.mock_table.search.return_value.limit.return_value.where.assert_not_called()


    @patch('lancedb.connect')
    def test_search_similar_notes_table_not_found(self, mock_lancedb_connect):
        mock_lancedb_connect.return_value = self.mock_db_connection
        self.mock_db_connection.open_table.side_effect = FileNotFoundError("Table gone")

        result = search_similar_notes(db_path="dummy/path", query_vector=[0.1]*1536)
        self.assertEqual(result["status"], "success") # Returns success with empty data as per current implementation
        self.assertEqual(result["data"], [])
        self.assertIn("Table 'notes' not found", result["message"])

if __name__ == '__main__':
    unittest.main()
