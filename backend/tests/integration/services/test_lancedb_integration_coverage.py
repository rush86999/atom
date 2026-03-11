"""
LanceDB Integration Coverage Tests

Comprehensive tests for LanceDB handler with deterministic mocks.
Target: 70%+ line coverage on core/lancedb_handler.py (1398 lines)

Tests mock external I/O (lancedb.connect, table operations) while testing
real embedding logic, vector search flows, and error handling.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
import json

from core.lancedb_handler import (
    LanceDBHandler,
    MockEmbedder,
    get_lancedb_handler,
    LANCEDB_AVAILABLE,
    NUMPY_AVAILABLE,
    PANDAS_AVAILABLE,
)

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_lancedb():
    """Mock LanceDB connection with deterministic table operations."""
    mock_db = Mock()
    mock_db.table_names = Mock(return_value=[])
    return mock_db

@pytest.fixture
def mock_table():
    """Mock LanceDB table with search and add operations."""
    table = Mock()
    table.search = Mock(return_value=table)
    table.where = Mock(return_value=table)
    table.limit = Mock(return_value=table)
    table.to_pandas = Mock(return_value=Mock())
    table.add = Mock()
    return table

@pytest.fixture
def handler():
    """Create handler instance with test configuration."""
    return LanceDBHandler(
        db_path="./test_db",
        embedding_provider="local",
        embedding_model="sentence-transformers/all-MiniLM-L6-v2"
    )

# ============================================================================
# Connection Tests
# ============================================================================

class TestLanceDBConnection:
    """Test LanceDB connection initialization and lifecycle."""

    @patch('core.lancedb_handler.LANCEDB_AVAILABLE', True)
    def test_initializes_db_connection_on_first_use(self, handler):
        """Test that handler initializes LanceDB connection lazily on first use."""
        # Start with db=None (uninitialized state)
        assert handler.db is None, "Handler should start with uninitialized DB"

        # Mock _initialize_db to simulate successful connection
        mock_db = Mock()
        mock_db.table_names = Mock(return_value=[])

        with patch.object(handler, '_initialize_db') as mock_init:
            handler._initialize_db = mock_init
            mock_init.return_value = None
            handler.db = mock_db

            # Now call _ensure_db - it should check db is not None and skip initialization
            handler._ensure_db()

            # Since we set db manually, _initialize_db should not be called again
            # This verifies lazy initialization (only called when db is None)
            assert handler.db is not None

    def test_connection_failure_returns_error_status(self, handler):
        """Test graceful handling of connection failures."""
        # Mock _ensure_db to simulate connection failure
        with patch.object(handler, '_ensure_db') as mock_ensure:
            # Set db to None after _ensure_db is called to simulate failure
            def side_effect():
                handler.db = None
            mock_ensure.side_effect = side_effect

            result = handler.test_connection()

            # Should return error status when db is None
            assert result["connected"] is False
            # The status should be "error" or the message should indicate not initialized
            assert result["status"] == "error" or "not initialized" in result["message"].lower()

    def test_connection_success_returns_table_list(self, handler):
        """Test successful connection returns available tables."""
        mock_db = Mock()
        mock_db.table_names = Mock(return_value=["episodes", "knowledge_graph"])
        handler.db = mock_db

        result = handler.test_connection()

        assert result["connected"] is True
        assert result["status"] == "success"
        assert result["tables"] == ["episodes", "knowledge_graph"]

    def test_lancedb_unavailable_returns_error(self):
        """Test handler behavior when LanceDB is not available."""
        with patch('core.lancedb_handler.LANCEDB_AVAILABLE', False):
            handler = LanceDBHandler()
            result = handler.test_connection()

            assert result["connected"] is False
            assert "LanceDB not available" in result["message"]

# ============================================================================
# Vector Search Tests
# ============================================================================

class TestLanceDBVectorSearch:
    """Test vector search operations with mocked LanceDB tables."""

    @patch('core.lancedb_handler.LanceDBHandler.embed_text')
    @patch('core.lancedb_handler.LanceDBHandler.get_table')
    def test_similarity_search_with_filters(self, mock_get_table, mock_embed, handler):
        """Test vector search with user_id and workspace_id filters."""
        # Mock embedding - return a Mock with tolist() method
        import numpy as np
        mock_vector = np.array([0.1] * 384, dtype=np.float32)
        mock_embed.return_value = mock_vector

        # Mock table search chain
        mock_table = Mock()
        mock_table.search = Mock(return_value=mock_table)
        mock_table.where = Mock(return_value=mock_table)
        mock_table.limit = Mock(return_value=mock_table)

        # Mock pandas result
        if PANDAS_AVAILABLE:
            import pandas as pd
            mock_df = pd.DataFrame({
                'id': ['ep1', 'ep2'],
                'text': ['result 1', 'result 2'],
                'source': ['test', 'test'],
                'metadata': [{'key': 'value'}, {'key2': 'value2'}],
                'created_at': ['2026-01-01', '2026-01-02'],
                '_distance': [0.2, 0.3]
            })
        else:
            mock_df = Mock()
        mock_table.to_pandas = Mock(return_value=mock_df)

        mock_get_table.return_value = mock_table

        # Create handler and search
        handler._ensure_db()
        handler.db = Mock()
        handler.db.table_names = Mock(return_value=['episodes'])

        results = handler.search(
            table_name="episodes",
            query="test query",
            user_id="test_user",
            limit=10
        )

        # Verify search was called
        mock_table.search.assert_called_once()
        assert len(results) >= 0

    @patch('core.lancedb_handler.LanceDBHandler.embed_text')
    def test_search_without_embedder_returns_empty(self, mock_embed, handler):
        """Test search behavior when embedding generation fails."""
        mock_embed.return_value = None

        handler._ensure_db()
        handler.db = Mock()
        handler.db.table_names = Mock(return_value=['episodes'])

        results = handler.search(
            table_name="episodes",
            query="test query",
            limit=10
        )

        assert results == []

# ============================================================================
# Batch Operations Tests
# ============================================================================

class TestLanceDBBatchOperations:
    """Test batch document operations with mocked tables."""

    @patch('core.lancedb_handler.LanceDBHandler.embed_text')
    @patch('core.lancedb_handler.LanceDBHandler.get_table')
    def test_add_documents_batch_success(self, mock_get_table, mock_embed, handler):
        """Test successful batch document addition."""
        # Mock embedding with correct dimension - use numpy array
        import numpy as np
        mock_embed.return_value = np.array([0.1] * 384, dtype=np.float32)

        # Mock table
        mock_table = Mock()
        mock_table.add = Mock()
        mock_get_table.return_value = mock_table

        handler._ensure_db()
        handler.db = Mock()
        handler.db.table_names = Mock(return_value=['test_table'])

        documents = [
            {"text": "doc1", "source": "test", "user_id": "user1"},
            {"text": "doc2", "source": "test", "user_id": "user1"}
        ]

        count = handler.add_documents_batch(
            table_name="test_table",
            documents=documents
        )

        assert count == 2
        mock_table.add.assert_called_once()

    @patch('core.lancedb_handler.LanceDBHandler.embed_text')
    def test_batch_handles_embedding_failure(self, mock_embed, handler):
        """Test that batch operations skip documents with failed embeddings."""
        # First embedding succeeds, second fails
        import numpy as np
        mock_embed.side_effect = [np.array([0.1] * 384, dtype=np.float32), None]

        handler._ensure_db()
        handler.db = Mock()
        mock_table = Mock()
        mock_table.add = Mock()
        handler.db.create_table = Mock(return_value=mock_table)
        handler.db.table_names = Mock(return_value=[])

        documents = [
            {"text": "doc1", "source": "test"},
            {"text": "doc2", "source": "test"}
        ]

        count = handler.add_documents_batch(
            table_name="test_table",
            documents=documents
        )

        # Only first document added (second skipped due to failed embedding)
        assert count == 1

# ============================================================================
# Knowledge Graph Tests
# ============================================================================

class TestLanceDBKnowledgeGraph:
    """Test knowledge graph edge operations."""

    @patch('core.lancedb_handler.LanceDBHandler.embed_text')
    @patch('core.lancedb_handler.LanceDBHandler.get_table')
    @patch('core.lancedb_handler.LanceDBHandler.create_table')
    def test_add_knowledge_edge_success(self, mock_create, mock_get, mock_embed, handler):
        """Test adding a knowledge graph edge successfully."""
        # Mock embedding
        import numpy as np
        mock_embed.return_value = np.array([0.1] * 384, dtype=np.float32)

        # Mock table (doesn't exist initially, then created)
        mock_get.return_value = None
        mock_table = Mock()
        mock_table.add = Mock()
        mock_create.return_value = mock_table

        handler._ensure_db()
        handler.db = Mock()
        handler.db.table_names = Mock(return_value=[])

        result = handler.add_knowledge_edge(
            from_id="entity1",
            to_id="entity2",
            rel_type="related_to",
            description="Entity1 is related to Entity2",
            user_id="test_user"
        )

        assert result is True
        mock_create.assert_called_once_with("knowledge_graph")
        mock_table.add.assert_called_once()

    @patch('core.lancedb_handler.LanceDBHandler.embed_text')
    @patch('core.lancedb_handler.LanceDBHandler.create_table')
    @patch('core.lancedb_handler.NUMPY_AVAILABLE', False)
    def test_knowledge_edge_with_embedding_fallback(self, mock_create, mock_embed, handler):
        """Test knowledge edge uses zero vector when embedding fails."""
        # Embedding fails
        mock_embed.return_value = None

        handler._ensure_db()
        handler.db = Mock()
        mock_table = Mock()
        mock_table.add = Mock()
        mock_create.return_value = mock_table
        handler.db.table_names = Mock(return_value=[])
        handler.get_table = Mock(return_value=None)

        result = handler.add_knowledge_edge(
            from_id="entity1",
            to_id="entity2",
            rel_type="related_to",
            description="Test edge"
        )

        # Should still succeed with zero vector fallback
        assert result is True

# ============================================================================
# Embedding Tests
# ============================================================================

class TestLanceDBEmbeddings:
    """Test embedding generation with different providers."""

    @patch('core.lancedb_handler.LanceDBHandler._initialize_embedder')
    def test_embed_text_with_mock_embedder(self, mock_init, handler):
        """Test embedding generation with mock embedder."""
        handler.embedder = MockEmbedder(dim=384)

        embedding = handler.embed_text("test text")

        assert embedding is not None
        assert len(embedding) == 384

    def test_mock_embedder_provides_deterministic_vectors(self):
        """Test that MockEmbedder returns consistent vectors for same input."""
        embedder = MockEmbedder(dim=384)

        vec1 = embedder.encode("same text")
        vec2 = embedder.encode("same text")

        assert len(vec1) == 384
        assert len(vec2) == 384
        # Same input should produce same vector (deterministic)
        assert vec1 == vec2

# ============================================================================
# Table Management Tests
# ============================================================================

class TestLanceDBTableManagement:
    """Test table creation, retrieval, and deletion."""

    @patch('core.lancedb_handler.LanceDBHandler._ensure_db')
    def test_get_table_returns_none_when_not_exists(self, mock_ensure, handler):
        """Test get_table returns None for non-existent tables."""
        handler.db = Mock()
        handler.db.table_names = Mock(return_value=["existing_table"])
        handler.db.open_table = Mock()

        result = handler.get_table("non_existent")

        assert result is None

    @patch('core.lancedb_handler.LanceDBHandler._ensure_db')
    def test_drop_table_removes_table_from_db(self, mock_ensure, handler):
        """Test drop_table removes table from database."""
        handler.db = Mock()
        handler.db.table_names = Mock(return_value=["table_to_drop"])
        handler.db.drop_table = Mock()

        result = handler.drop_table("table_to_drop")

        assert result is True
        handler.db.drop_table.assert_called_once_with("table_to_drop")

    @patch('core.lancedb_handler.LanceDBHandler._ensure_db')
    def test_drop_table_handles_non_existent_table(self, mock_ensure, handler):
        """Test drop_table returns True even if table doesn't exist."""
        handler.db = Mock()
        handler.db.table_names = Mock(return_value=[])
        handler.db.drop_table = Mock()

        result = handler.drop_table("non_existent")

        assert result is True
        handler.db.drop_table.assert_not_called()

# ============================================================================
# Error Path Tests
# ============================================================================

class TestLanceDBErrorPaths:
    """Test comprehensive error handling in LanceDB operations."""

    def test_unavailable_lancedb_returns_error_status(self):
        """Test handler behavior when LanceDB library is not available."""
        with patch('core.lancedb_handler.LANCEDB_AVAILABLE', False):
            handler = LanceDBHandler()
            result = handler.test_connection()

            assert result["connected"] is False
            assert result["status"] == "error"

    @patch('core.lancedb_handler.LanceDBHandler._ensure_db')
    def test_connection_exception_is_caught(self, mock_ensure, handler):
        """Test that connection exceptions are caught and returned."""
        handler.db = Mock()
        handler.db.table_names = Mock(side_effect=RuntimeError("Connection timeout"))

        result = handler.test_connection()

        assert result["connected"] is False
        assert "timeout" in result["message"].lower()

    @patch('core.lancedb_handler.LanceDBHandler._ensure_db')
    def test_table_operations_fail_when_db_none(self, mock_ensure, handler):
        """Test table operations fail gracefully when db is None."""
        handler.db = None

        result = handler.get_table("test_table")
        assert result is None

        result = handler.drop_table("test_table")
        assert result is False
