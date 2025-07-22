import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import os

# Adjust sys.path to allow importing from _utils
import sys
FUNCTIONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if FUNCTIONS_DIR not in sys.path:
    sys.path.insert(0, FUNCTIONS_DIR)

# Import the function to be tested
from _utils.lancedb_service import search_meeting_transcripts

class TestSearchMeetingTranscripts(unittest.TestCase):

    def setUp(self):
        """Set up mock objects for LanceDB connection and table."""
        self.lancedb_patcher = patch('_utils.lancedb_service.lancedb')
        self.mock_lancedb = self.lancedb_patcher.start()
        self.addCleanup(self.lancedb_patcher.stop)
        self.mock_db = MagicMock()
        self.mock_table = MagicMock()
        self.mock_lancedb.connect.return_value = self.mock_db
        self.mock_db.open_table.return_value = self.mock_table

        # Mock for the search query chain
        self.mock_search_builder = MagicMock()
        self.mock_table.search.return_value = self.mock_search_builder
        self.mock_search_builder.limit.return_value = self.mock_search_builder
        self.mock_search_builder.where.return_value = self.mock_search_builder
        self.mock_search_builder.select.return_value = self.mock_search_builder

    def test_search_success_with_results(self):
        """Test a successful search that returns formatted results."""
        mock_results = [
            {
                'notion_page_id': 'page1',
                'notion_page_title': 'Meeting A',
                'notion_page_url': 'http://notion.so/page1',
                'text_chunk': 'This is the first chunk of text.',
                '_distance': 0.1,
                'last_edited_at_notion': datetime(2023, 1, 1, 10, 0, 0, tzinfo=timezone.utc),
                'user_id': 'user1'
            },
            {
                'notion_page_id': 'page2',
                'notion_page_title': 'Meeting B',
                'notion_page_url': 'http://notion.so/page2',
                'text_chunk': 'This is the second chunk of text which is very long and will certainly be truncated to make sure that the preview functionality is working as expected and does not overflow the user interface with an excessive amount of text that nobody wants to read.',
                '_distance': 0.2,
                'last_edited_at_notion': 1672653600000000000, # Nanosecond timestamp
                'user_id': 'user1'
            }
        ]
        self.mock_search_builder.to_list.return_value = mock_results

        result = search_meeting_transcripts(
            db_path="dummy_path",
            query_vector=[0.1]*10,
            user_id="user1",
            table_name="transcripts"
        )

        self.assertEqual(result['status'], 'success')
        self.assertEqual(len(result['data']), 2)

        # Verify first result
        self.assertEqual(result['data'][0]['notion_page_id'], 'page1')
        self.assertEqual(result['data'][0]['score'], 0.1)
        self.assertEqual(result['data'][0]['last_edited_at_notion'], '2023-01-01T10:00:00+00:00')
        self.assertEqual(result['data'][0]['text_chunk_preview'], 'This is the first chunk of text.')

        # Verify second result (truncation and timestamp conversion)
        self.assertEqual(result['data'][1]['notion_page_id'], 'page2')
        self.assertTrue(result['data'][1]['text_chunk_preview'].endswith('...'))
        self.assertEqual(len(result['data'][1]['text_chunk_preview']), 250)
        self.assertEqual(result['data'][1]['last_edited_at_notion'], '2023-01-02T10:00:00+00:00')

        # Verify LanceDB calls
        self.mock_lancedb.connect.assert_called_once_with("dummy_path")
        self.mock_db.open_table.assert_called_once_with("transcripts")
        self.mock_table.search.assert_called_once()
        self.mock_search_builder.limit.assert_called_once_with(5) # Default limit
        self.mock_search_builder.where.assert_called_once_with("user_id = 'user1'")
        self.mock_search_builder.select.assert_called_once()

    def test_search_table_not_found(self):
        """Test that search handles a non-existent table gracefully."""
        self.mock_db.open_table.side_effect = FileNotFoundError("Table not found")

        result = search_meeting_transcripts("p", [0.1], "u1", "t1")

        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['data'], [])
        self.assertIn("Table 't1' not found", result['message'])

    def test_search_no_results(self):
        """Test a successful search that returns no results."""
        self.mock_search_builder.to_list.return_value = []

        result = search_meeting_transcripts("p", [0.1], "u1", "t1")

        self.assertEqual(result['status'], 'success')
        self.assertEqual(len(result['data']), 0)

    def test_validation_errors(self):
        """Test that the function returns validation errors for missing parameters."""
        test_cases = [
            {"db_path": "", "query_vector": [0.1], "user_id": "u1", "table_name": "t1", "code": "LANCEDB_CONFIG_ERROR"},
            {"db_path": "p", "query_vector": [], "user_id": "u1", "table_name": "t1", "code": "VALIDATION_ERROR"},
            {"db_path": "p", "query_vector": [0.1], "user_id": "", "table_name": "t1", "code": "VALIDATION_ERROR_USERID"},
            {"db_path": "p", "query_vector": [0.1], "user_id": "u1", "table_name": "", "code": "LANCEDB_CONFIG_ERROR_TABLE"},
        ]

        for case in test_cases:
            with self.subTest(msg=f"Testing missing {case['code']}"):
                result = search_meeting_transcripts(**{k: v for k, v in case.items() if k != 'code'})
                self.assertEqual(result['status'], 'error')
                self.assertEqual(result['code'], case['code'])

    def test_lancedb_general_exception(self):
        """Test handling of a generic exception during search."""
        self.mock_table.search.side_effect = Exception("A wild error appeared")

        result = search_meeting_transcripts("p", [0.1], "u1", "t1")

        self.assertEqual(result['status'], 'error')
        self.assertEqual(result['code'], 'LANCEDB_SEARCH_ERROR')
        self.assertIn("LanceDB search operation failed", result['message'])

if __name__ == '__main__':
    unittest.main()
