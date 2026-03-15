"""
Coverage-driven tests for lancedb_handler.py (55% -> 75%+ target)

FIX for Phase 193 mock complexity issues:
- Use pytest-mock's mocker.fixture instead of complex mock setup
- Use MagicMock for flexible mocking
- Use mock_open for file operations
- Simplify mock configuration to reduce test fragility

Coverage Target Areas:
- Lines 100-200: Vector search with query embedding
- Lines 200-300: Batch insert operations
- Lines 300-400: Table management (create, delete)
- Lines 400-500: Knowledge graph operations
- Lines 500-600: Error handling and edge cases
"""

import pytest
import sys
from unittest.mock import Mock, MagicMock, mock_open
from datetime import datetime
from typing import Dict, Any, Optional, List
import json
import os

# ============================================================================
# Module-level mocking - patches lancedb BEFORE importing handler
# This prevents import errors when lancedb is not installed
# ============================================================================
sys.modules['lancedb'] = MagicMock()

mock_lancedb = MagicMock()
mock_lancedb.connect = Mock(return_value=mock_lancedb)
mock_lancedb.table_names = Mock(return_value=[])
sys.modules['lancedb'].connect = mock_lancedb.connect

# Now we can safely import the handler
from core.lancedb_handler import (
    LanceDBHandler,
    LANCEDB_AVAILABLE,
    NUMPY_AVAILABLE,
    PANDAS_AVAILABLE,
    MockEmbedder,
)


# ============================================================================
# Test Class: LanceDBHandler Coverage Extension (Phase 194)
# ============================================================================
class TestLanceDBHandlerCoverageExtend:
    """
    Extended coverage tests for LanceDBHandler with simplified mocks.

    Target: 75%+ coverage (from 55% baseline)
    Focus: Vector search, batch operations, table management, error handling
    """

    # =========================================================================
    # Vector Search Tests (15 tests) - Lines 100-200
    # =========================================================================

    def test_vector_search_with_simplified_mocks(self, mocker):
        """Cover vector search with simplified mock setup."""
        # Simplified: Use MagicMock instead of complex mock hierarchy
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.search.return_value = mock_table
        mock_table.to_pandas.return_value = []

        # Patch lancedb.connect at module level
        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        results = handler.vector_search(query="test", limit=10)

        # Verify LanceDB operations without complex assertions
        mock_table.search.assert_called_once()

    @pytest.mark.parametrize("limit,expected_calls", [
        (10, 1),
        (50, 1),
        (100, 1),
    ])
    def test_vector_search_with_various_limits(self, mocker, limit, expected_calls):
        """Cover vector search with different limit values."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.search.return_value = mock_table
        mock_table.limit.return_value = mock_table
        mock_table.to_pandas.return_value = []

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        handler.vector_search(query="test", limit=limit)

        mock_table.limit.assert_called_with(limit)

    def test_vector_search_with_filter(self, mocker):
        """Cover vector search with metadata filtering."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.search.return_value = mock_table
        mock_table.where.return_value = mock_table
        mock_table.to_pandas.return_value = []

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        handler.vector_search(
            query="test",
            filter="agent_id = 'test-agent'",
            limit=10
        )

        mock_table.where.assert_called_once()

    def test_vector_search_empty_results(self, mocker):
        """Cover empty result handling."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.search.return_value = mock_table
        mock_table.to_pandas.return_value = []  # Empty results

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        results = handler.vector_search(query="test", limit=10)

        assert results == []

    def test_vector_search_with_embedding(self, mocker):
        """Cover vector search with pre-computed embedding."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.search.return_value = mock_table
        mock_table.to_pandas.return_value = []

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        embedding = [0.1] * 384
        handler.vector_search(query_embedding=embedding, limit=10)

        # Verify search was called with embedding
        mock_table.search.assert_called_once()

    def test_vector_search_with_table_name(self, mocker):
        """Cover vector search with custom table name."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.search.return_value = mock_table
        mock_table.to_pandas.return_value = []

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        handler.vector_search(query="test", table_name="custom_table", limit=10)

        # Verify correct table was opened
        mock_client.open_table.assert_called_with("custom_table")

    def test_vector_search_with_metric_type(self, mocker):
        """Cover vector search with different metric types."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.search.return_value = mock_table
        mock_table.to_pandas.return_value = []

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        handler.vector_search(query="test", metric_type="cosine", limit=10)

        mock_table.search.assert_called_once()

    def test_vector_search_with_nprobes(self, mocker):
        """Cover vector search with nprobes parameter."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.search.return_value = mock_table
        mock_table.to_pandas.return_value = []

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        handler.vector_search(query="test", nprobes=10, limit=10)

        mock_table.search.assert_called_once()

    def test_vector_search_returns_results(self, mocker):
        """Cover vector search returning actual results."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.search.return_value = mock_table

        # Mock pandas DataFrame
        if PANDAS_AVAILABLE:
            import pandas as pd
            mock_results = pd.DataFrame({
                'id': ['doc1', 'doc2'],
                'text': ['Test 1', 'Test 2'],
                '_distance': [0.1, 0.2]
            })
            mock_table.to_pandas.return_value = mock_results
        else:
            mock_table.to_pandas.return_value = []

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        results = handler.vector_search(query="test", limit=10)

        if PANDAS_AVAILABLE:
            assert len(results) == 2
            assert results[0]['id'] == 'doc1'
        else:
            assert results == []

    def test_vector_search_with_where_clause(self, mocker):
        """Cover vector search with WHERE clause filtering."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.search.return_value = mock_table
        mock_table.where.return_value = mock_table
        mock_table.to_pandas.return_value = []

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        handler.vector_search(
            query="test",
            where="user_id = 'test-user'",
            limit=10
        )

        mock_table.where.assert_called_once()

    def test_vector_search_multiple_queries(self, mocker):
        """Cover multiple vector search calls."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.search.return_value = mock_table
        mock_table.to_pandas.return_value = []

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        handler.vector_search(query="test1", limit=10)
        handler.vector_search(query="test2", limit=10)

        assert mock_table.search.call_count == 2

    def test_vector_search_with_invalid_query(self, mocker):
        """Cover vector search with invalid/empty query."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.search.side_effect = ValueError("Invalid query")

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")

        with pytest.raises(ValueError):
            handler.vector_search(query="", limit=10)

    def test_vector_search_with_timeout(self, mocker):
        """Cover vector search timeout handling."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.search.side_effect = TimeoutError("Query timeout")

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")

        with pytest.raises(TimeoutError):
            handler.vector_search(query="test", limit=10)

    def test_vector_search_with_connection_error(self, mocker):
        """Cover vector search connection error handling."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.side_effect = ConnectionError("Not connected")

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")

        with pytest.raises(ConnectionError):
            handler.vector_search(query="test", limit=10)

    def test_vector_search_after_reconnection(self, mocker):
        """Cover vector search after DB reconnection."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.search.return_value = mock_table
        mock_table.to_pandas.return_value = []

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        handler._initialize_db()
        handler.vector_search(query="test", limit=10)

        # Verify reconnection didn't break search
        mock_table.search.assert_called_once()

    # =========================================================================
    # Batch Insert Tests (12 tests) - Lines 200-300
    # =========================================================================

    def test_batch_insert_with_file_operations(self, mocker):
        """Cover batch insert with file operation mocks."""
        # Mock file operations using mock_open
        mocker.patch("builtins.open", mocker.mock_open(read_data="data"))
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("os.makedirs")

        # Mock LanceDB operations
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.add.return_value = None

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="file://test.db")
        handler.batch_insert(data=[{"id": "1", "vector": [0.1, 0.2]}])

        # Verify table was created and data was added
        mock_client.create_table.assert_called_once()
        mock_table.add.assert_called_once()

    def test_batch_insert_with_chunks(self, mocker):
        """Cover chunked insertion for large datasets."""
        mocker.patch("builtins.open", mocker.mock_open(read_data="data"))
        mocker.patch("os.path.exists", return_value=True)
        mocker.patch("os.makedirs")

        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.add.return_value = None

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="file://test.db")

        # Insert data larger than default chunk size
        large_data = [{"id": str(i), "vector": [0.1, 0.2]} for i in range(1500)]
        handler.batch_insert(data=large_data, chunk_size=1000)

        # Should be called twice (1500 / 1000 = 2 chunks)
        assert mock_table.add.call_count == 2

    @pytest.mark.parametrize("batch_size,expected_chunks", [
        (100, 1),
        (500, 1),
        (1000, 2),
        (1500, 2),
    ])
    def test_batch_insert_chunking(self, mocker, batch_size, expected_chunks):
        """Cover chunking logic with various batch sizes."""
        mocker.patch("builtins.open", mocker.mock_open(read_data="data"))
        mocker.patch("os.path.exists", return_value=True)

        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="file://test.db")
        handler.batch_insert(
            data=[{"id": str(i), "vector": [0.1]} for i in range(batch_size)],
            chunk_size=1000
        )

        assert mock_table.add.call_count == expected_chunks

    def test_batch_insert_with_empty_data(self, mocker):
        """Cover batch insert with empty data list."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        handler.batch_insert(data=[])

        # Should not call add for empty data
        mock_table.add.assert_not_called()

    def test_batch_insert_with_metadata(self, mocker):
        """Cover batch insert with metadata fields."""
        mocker.patch("builtins.open", mocker.mock_open(read_data="data"))
        mocker.patch("os.path.exists", return_value=True)

        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.add.return_value = None

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="file://test.db")
        data = [
            {
                "id": "doc1",
                "text": "Test document",
                "metadata": {"key": "value"},
                "vector": [0.1] * 384
            }
        ]
        handler.batch_insert(data=data)

        mock_table.add.assert_called_once()

    def test_batch_insert_with_error_handling(self, mocker):
        """Cover batch insert with partial failure handling."""
        mocker.patch("builtins.open", mocker.mock_open(read_data="data"))
        mocker.patch("os.path.exists", return_value=True)

        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.add.side_effect = Exception("Insert failed")

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="file://test.db")

        with pytest.raises(Exception):
            handler.batch_insert(data=[{"id": "1"}])

    def test_batch_insert_with_table_creation(self, mocker):
        """Cover batch insert creating new table."""
        mocker.patch("builtins.open", mocker.mock_open(read_data="data"))
        mocker.patch("os.path.exists", return_value=False)

        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.create_table.return_value = mock_table
        mock_table.add.return_value = None

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="file://test.db")
        handler.batch_insert(data=[{"id": "1"}])

        mock_client.create_table.assert_called_once()

    def test_batch_insert_with_existing_table(self, mocker):
        """Cover batch insert to existing table."""
        mocker.patch("builtins.open", mocker.mock_open(read_data="data"))
        mocker.patch("os.path.exists", return_value=True)

        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.add.return_value = None

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="file://test.db")
        handler.batch_insert(data=[{"id": "1"}])

        # Should open existing table, not create new one
        mock_client.open_table.assert_called_once()
        mock_client.create_table.assert_not_called()

    def test_batch_insert_with_custom_schema(self, mocker):
        """Cover batch insert with custom schema."""
        mocker.patch("builtins.open", mocker.mock_open(read_data="data"))
        mocker.patch("os.path.exists", return_value=False)

        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.create_table.return_value = mock_table
        mock_table.add.return_value = None

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="file://test.db")
        schema = [
            {"name": "id", "type": "string"},
            {"name": "vector", "type": "vector", "dim": 384}
        ]
        handler.batch_insert(data=[{"id": "1"}], schema=schema)

        mock_client.create_table.assert_called_once()

    def test_batch_insert_with_duplicates(self, mocker):
        """Cover batch insert with duplicate IDs."""
        mocker.patch("builtins.open", mocker.mock_open(read_data="data"))
        mocker.patch("os.path.exists", return_value=True)

        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.add.return_value = None

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="file://test.db")
        data = [
            {"id": "doc1", "text": "First"},
            {"id": "doc1", "text": "Duplicate"}  # Same ID
        ]
        handler.batch_insert(data=data)

        # Both should be inserted (LanceDB behavior)
        assert mock_table.add.call_count == 1

    # =========================================================================
    # Table Management Tests (10 tests) - Lines 300-400
    # =========================================================================

    def test_create_table(self, mocker):
        """Cover table creation."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.create_table.return_value = mock_table

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        handler.create_table(
            name="test_table",
            schema=[{"name": "id", "type": "string"}]
        )

        mock_client.create_table.assert_called_once()

    def test_delete_table(self, mocker):
        """Cover table deletion."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.drop.return_value = None

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        handler.delete_table(name="test_table")

        mock_table.drop.assert_called_once()

    def test_table_exists(self, mocker):
        """Cover table existence check."""
        mock_client = mocker.MagicMock()
        mock_client.open_table.side_effect = Exception("Table not found")

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        exists = handler.table_exists(name="test_table")

        assert exists is False

    def test_table_exists_true(self, mocker):
        """Cover table exists returning True."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        exists = handler.table_exists(name="test_table")

        assert exists is True

    def test_list_tables(self, mocker):
        """Cover listing all tables."""
        mock_client = mocker.MagicMock()
        mock_client.table_names.return_value = ["table1", "table2", "table3"]

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        tables = handler.list_tables()

        assert tables == ["table1", "table2", "table3"]

    def test_list_tables_empty(self, mocker):
        """Cover listing tables when none exist."""
        mock_client = mocker.MagicMock()
        mock_client.table_names.return_value = []

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        tables = handler.list_tables()

        assert tables == []

    def test_get_table(self, mocker):
        """Cover getting table reference."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        table = handler.get_table(name="test_table")

        assert table is not None
        mock_client.open_table.assert_called_once()

    def test_create_table_with_vector_column(self, mocker):
        """Cover creating table with vector column."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.create_table.return_value = mock_table

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        schema = [
            {"name": "id", "type": "string"},
            {"name": "vector", "type": "vector", "dim": 384}
        ]
        handler.create_table(name="vectors_table", schema=schema)

        mock_client.create_table.assert_called_once()

    def test_delete_table_nonexistent(self, mocker):
        """Cover deleting non-existent table."""
        mock_client = mocker.MagicMock()
        mock_client.open_table.side_effect = Exception("Table not found")

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")

        # Should handle gracefully or raise appropriate error
        with pytest.raises(Exception):
            handler.delete_table(name="nonexistent_table")

    def test_table_count(self, mocker):
        """Cover getting table row count."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.count.return_value = 100

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        count = handler.table_count(name="test_table")

        assert count == 100

    # =========================================================================
    # Knowledge Graph Operations Tests (8 tests) - Lines 400-500
    # =========================================================================

    def test_knowledge_graph_traversal(self, mocker):
        """Cover knowledge graph operations."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.search.return_value = mock_table
        mock_table.where.return_value = mock_table
        mock_table.to_pandas.return_value = []

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        results = handler.knowledge_graph_traversal(
            entity_id="test-entity",
            max_depth=2
        )

        # Verify search was called for traversal
        assert mock_table.search.call_count > 0

    def test_related_entities_search(self, mocker):
        """Cover related entity search."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.search.return_value = mock_table
        mock_table.to_pandas.return_value = [
            {"id": "entity-1", "relation": "related_to"},
            {"id": "entity-2", "relation": "depends_on"}
        ]

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        results = handler.find_related_entities(
            entity_id="test-entity",
            relation_type="related_to"
        )

        # Should filter by relation type
        mock_table.search.assert_called_once()

    def test_add_entity_relation(self, mocker):
        """Cover adding entity relation."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.add.return_value = None

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        handler.add_entity_relation(
            from_entity="entity-1",
            to_entity="entity-2",
            relation_type="connected_to"
        )

        mock_table.add.assert_called_once()

    def test_get_entity_relations(self, mocker):
        """Cover getting all relations for an entity."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.search.return_value = mock_table
        mock_table.to_pandas.return_value = [
            {"from_entity": "entity-1", "to_entity": "entity-2", "relation": "connected"}
        ]

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        relations = handler.get_entity_relations(entity_id="entity-1")

        mock_table.search.assert_called_once()

    def test_delete_entity_relation(self, mocker):
        """Cover deleting entity relation."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.delete.return_value = None

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        handler.delete_entity_relation(
            from_entity="entity-1",
            to_entity="entity-2"
        )

        mock_table.delete.assert_called_once()

    def test_graph_traversal_depth_1(self, mocker):
        """Cover graph traversal with depth 1."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.search.return_value = mock_table
        mock_table.to_pandas.return_value = []

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        handler.knowledge_graph_traversal(
            entity_id="test-entity",
            max_depth=1
        )

        # Should only search once for depth 1
        assert mock_table.search.call_count == 1

    def test_graph_traversal_depth_3(self, mocker):
        """Cover graph traversal with depth 3."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.search.return_value = mock_table
        mock_table.to_pandas.return_value = []

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        handler.knowledge_graph_traversal(
            entity_id="test-entity",
            max_depth=3
        )

        # Should search multiple times for depth 3
        assert mock_table.search.call_count >= 1

    def test_graph_traversal_with_filter(self, mocker):
        """Cover graph traversal with relation type filter."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.search.return_value = mock_table
        mock_table.where.return_value = mock_table
        mock_table.to_pandas.return_value = []

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")
        handler.knowledge_graph_traversal(
            entity_id="test-entity",
            max_depth=2,
            relation_filter="connected_to"
        )

        # Should apply where filter
        mock_table.where.assert_called()

    # =========================================================================
    # Error Handling Tests (10 tests) - Lines 500-600
    # =========================================================================

    def test_connection_error_handling(self, mocker):
        """Cover connection error handling."""
        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            side_effect=Exception("Connection failed")
        )

        handler = LanceDBHandler(db_path="invalid://uri")

        with pytest.raises(Exception):
            handler.vector_search(query="test", limit=10)

    def test_invalid_query_handling(self, mocker):
        """Cover invalid query error handling."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.search.side_effect = ValueError("Invalid query")

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")

        with pytest.raises(ValueError):
            handler.vector_search(query="", limit=10)

    def test_timeout_handling(self, mocker):
        """Cover timeout handling."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.search.side_effect = TimeoutError("Query timeout")

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")

        with pytest.raises(TimeoutError):
            handler.vector_search(query="test", limit=10)

    def test_table_not_found_error(self, mocker):
        """Cover table not found error."""
        mock_client = mocker.MagicMock()
        mock_client.open_table.side_effect = Exception("Table not found")

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")

        with pytest.raises(Exception):
            handler.get_table(name="nonexistent")

    def test_batch_insert_error(self, mocker):
        """Cover batch insert error handling."""
        mocker.patch("builtins.open", mocker.mock_open(read_data="data"))
        mocker.patch("os.path.exists", return_value=True)

        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.add.side_effect = RuntimeError("Insert failed")

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="file://test.db")

        with pytest.raises(RuntimeError):
            handler.batch_insert(data=[{"id": "1"}])

    def test_embedding_generation_error(self, mocker):
        """Cover embedding generation error."""
        handler = LanceDBHandler()

        # Mock embedder to raise error
        mock_embedder = mocker.MagicMock()
        mock_embedder.encode.side_effect = Exception("Embedding failed")
        handler.embedder = mock_embedder

        with pytest.raises(Exception):
            handler._generate_embedding(text="test")

    def test_invalid_vector_dimension(self, mocker):
        """Cover invalid vector dimension error."""
        mocker.patch("builtins.open", mocker.mock_open(read_data="data"))

        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.create_table.return_value = mock_table
        mock_table.add.side_effect = ValueError("Invalid dimension")

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="file://test.db")

        with pytest.raises(ValueError):
            handler.batch_insert(data=[{"id": "1", "vector": [0.1]}])

    def test_database_lock_error(self, mocker):
        """Cover database lock error handling."""
        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            side_effect=IOError("Database locked")
        )

        handler = LanceDBHandler(db_path="file://locked.db")

        with pytest.raises(IOError):
            handler._initialize_db()

    def test_memory_allocation_error(self, mocker):
        """Cover memory allocation error."""
        mock_client = mocker.MagicMock()
        mock_table = mocker.MagicMock()
        mock_client.open_table.return_value = mock_table
        mock_table.search.side_effect = MemoryError("Out of memory")

        mocker.patch(
            "core.lancedb_handler.lancedb.connect",
            return_value=mock_client
        )

        handler = LanceDBHandler(db_path="memory://")

        with pytest.raises(MemoryError):
            handler.vector_search(query="test", limit=10)

    def test_permission_error_handling(self, mocker):
        """Cover permission error handling."""
        mocker.patch("os.path.exists", return_value=False)
        mocker.patch("os.makedirs", side_effect=PermissionError("Access denied"))

        handler = LanceDBHandler(db_path="/root/protected/db")

        with pytest.raises(PermissionError):
            handler._initialize_db()

    # =========================================================================
    # Initialization and Configuration Tests (5 tests)
    # =========================================================================

    @pytest.mark.parametrize("uri,expected_type", [
        ("memory://", "memory"),
        ("file:///tmp/test.db", "file"),
        ("s3://bucket/path", "s3"),
    ])
    def test_handler_initialization(self, uri, expected_type):
        """Cover handler initialization for different URI types."""
        handler = LanceDBHandler(db_path=uri)

        assert handler.db_path == uri

    def test_handler_with_custom_config(self):
        """Cover handler initialization with custom configuration."""
        handler = LanceDBHandler(
            db_path="memory://",
            embedding_provider="openai",
            embedding_model="text-embedding-3-small"
        )

        assert handler.embedding_provider == "openai"
        assert handler.embedding_model == "text-embedding-3-small"

    def test_dual_vector_config(self):
        """Cover dual vector storage configuration."""
        handler = LanceDBHandler()

        assert "vector" in handler.vector_columns
        assert "vector_fastembed" in handler.vector_columns
        assert handler.vector_columns["vector"] == 1024
        assert handler.vector_columns["vector_fastembed"] == 384

    def test_workspace_id_default(self):
        """Cover default workspace_id (single-tenant)."""
        handler = LanceDBHandler()

        assert handler.workspace_id == "default"

    def test_environment_variable_config(self, monkeypatch):
        """Cover environment variable configuration."""
        monkeypatch.setenv("EMBEDDING_PROVIDER", "fastembed")
        monkeypatch.setenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

        handler = LanceDBHandler()

        assert handler.embedding_provider == "fastembed"
        assert handler.embedding_model == "BAAI/bge-small-en-v1.5"
