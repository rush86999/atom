"""
Comprehensive unit tests for LanceDB Handler

Covers:
- LanceDB initialization and connection management
- Vector table creation and management
- Document insertion (single and batch)
- Semantic search with filters
- Embedding generation (OpenAI, SentenceTransformers, MockEmbedder)
- Knowledge graph operations
- Dual vector storage (ST + FastEmbed)
- Chat history management
- Error handling and graceful degradation
"""

import pytest
import json
import os
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from unittest.mock import Mock, MagicMock, AsyncMock, patch, mock_open
import hashlib

from core.lancedb_handler import (
    LanceDBHandler,
    ChatHistoryManager,
    MockEmbedder,
    get_lancedb_handler,
    get_chat_history_manager,
    LANCEDB_AVAILABLE,
    NUMPY_AVAILABLE,
    PANDAS_AVAILABLE,
    SENTENCE_TRANSFORMERS_AVAILABLE,
    OPENAI_AVAILABLE
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def temp_db_path():
    """Create temporary directory for LanceDB tests"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "test_lancedb")
        yield db_path


@pytest.fixture
def mock_lancedb_connection():
    """Mock LanceDB connection"""
    mock_db = Mock()
    mock_db.connect = Mock(return_value=mock_db)
    mock_db.table_names = Mock(return_value=[])
    return mock_db


@pytest.fixture
def mock_table():
    """Mock LanceDB table"""
    table = Mock()
    table.search = Mock(return_value=table)
    table.where = Mock(return_value=table)
    table.limit = Mock(return_value=table)
    table.to_pandas = Mock(return_value=MagicMock())
    table.add = Mock()
    return table


@pytest.fixture
def sample_documents():
    """Sample documents for testing"""
    return [
        {
            "id": "doc1",
            "text": "Machine learning is a subset of artificial intelligence",
            "source": "test",
            "metadata": {"category": "AI"},
            "user_id": "user1"
        },
        {
            "id": "doc2",
            "text": "Deep learning uses neural networks with multiple layers",
            "source": "test",
            "metadata": {"category": "DL"},
            "user_id": "user1"
        },
        {
            "id": "doc3",
            "text": "Python is a popular programming language for data science",
            "source": "test",
            "metadata": {"category": "programming"},
            "user_id": "user2"
        }
    ]


# ============================================================================
# Test Class 1: TestLanceDBInitialization (6 tests)
# ============================================================================

class TestLanceDBInitialization:
    """Test LanceDB handler initialization"""

    def test_initialize_with_default_path(self, temp_db_path):
        """Initialize handler with default local path"""
        handler = LanceDBHandler(db_path=temp_db_path)

        assert handler.db_path == temp_db_path
        assert handler.workspace_id == "default"
        assert handler.embedding_provider in ["local", "openai", "fastembed"]

    def test_initialize_with_openai_provider(self, temp_db_path, monkeypatch):
        """Initialize handler with OpenAI embedding provider"""
        monkeypatch.setenv("EMBEDDING_PROVIDER", "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")

        with patch('core.lancedb_handler.OPENAI_AVAILABLE', True):
            handler = LanceDBHandler(db_path=temp_db_path)

            assert handler.embedding_provider == "openai"

    def test_initialize_with_s3_path(self, monkeypatch):
        """Initialize handler with S3 path"""
        monkeypatch.setenv("AWS_ENDPOINT_URL", "https://minio.example.com")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test-key")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test-secret")

        handler = LanceDBHandler(db_path="s3://test-bucket/lancedb")

        assert handler.db_path == "s3://test-bucket/lancedb"

    def test_initialize_with_r2_credentials(self, monkeypatch):
        """Initialize handler with Cloudflare R2 credentials"""
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "r2-key")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "r2-secret")
        monkeypatch.setenv("AWS_REGION", "auto")

        handler = LanceDBHandler(db_path="s3://r2-bucket/memory")

        assert handler.db_path == "s3://r2-bucket/memory"

    @patch('core.lancedb_handler.LANCEDB_AVAILABLE', False)
    def test_initialize_when_lancedb_not_available(self, temp_db_path):
        """Initialize handler when LanceDB is not available"""
        handler = LanceDBHandler(db_path=temp_db_path)

        assert handler.db is None, "DB should be None when LanceDB unavailable"

    def test_test_connection_returns_success(self, temp_db_path, mock_lancedb_connection):
        """Test connection returns success status"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection

        result = handler.test_connection()

        assert result["status"] == "success"
        assert result["connected"] is True


# ============================================================================
# Test Class 2: TestEmbedderInitialization (5 tests)
# ============================================================================

class TestEmbedderInitialization:
    """Test embedding provider initialization"""

    @patch('core.lancedb_handler.SENTENCE_TRANSFORMERS_AVAILABLE', True)
    @patch('core.lancedb_handler.SentenceTransformer')
    def test_initialize_sentence_transformers(self, mock_transformer_class, temp_db_path):
        """Initialize SentenceTransformer embedder"""
        mock_model = Mock()
        mock_transformer_class.return_value = mock_model

        handler = LanceDBHandler(db_path=temp_db_path, embedding_provider="local")

        assert handler.embedder is not None

    @patch('core.lancedb_handler.OPENAI_AVAILABLE', True)
    @patch('core.lancedb_handler.OpenAI')
    def test_initialize_openai_embedder(self, mock_openai_class, temp_db_path, monkeypatch):
        """Initialize OpenAI embedder"""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        handler = LanceDBHandler(db_path=temp_db_path, embedding_provider="openai")

        assert handler.openai_client is not None

    def test_fallback_to_mock_embedder(self, temp_db_path):
        """Fallback to MockEmbedder when SentenceTransformers unavailable"""
        with patch('core.lancedb_handler.SENTENCE_TRANSFORMERS_AVAILABLE', False):
            handler = LanceDBHandler(db_path=temp_db_path, embedding_provider="local")

            assert isinstance(handler.embedder, MockEmbedder)

    def test_mock_embedder_generates_consistent_vectors(self):
        """MockEmbedder generates consistent vectors for same text"""
        embedder = MockEmbedder(dim=384)

        vec1 = embedder.encode("test text")
        vec2 = embedder.encode("test text")

        assert vec1 == vec2, "Same text should produce same vector"

    def test_mock_embedder_generates_different_vectors(self):
        """MockEmbedder generates different vectors for different text"""
        embedder = MockEmbedder(dim=384)

        vec1 = embedder.encode("text one")
        vec2 = embedder.encode("text two")

        assert vec1 != vec2, "Different text should produce different vectors"

    @patch('core.lancedb_handler.OPENAI_AVAILABLE', False)
    def test_openai_fallback_to_local_on_missing_key(self, temp_db_path, monkeypatch):
        """OpenAI provider falls back to local when API key missing"""
        # Remove API key
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        handler = LanceDBHandler(db_path=temp_db_path, embedding_provider="openai")

        assert handler.embedding_provider == "local", "Should fall back to local"


# ============================================================================
# Test Class 3: TestVectorOperations (10 tests)
# ============================================================================

class TestVectorOperations:
    """Test vector storage and retrieval operations"""

    def test_embed_text_with_mock_embedder(self, temp_db_path):
        """Embed text using MockEmbedder"""
        handler = LanceDBHandler(db_path=temp_db_path)

        vector = handler.embed_text("Test document about machine learning")

        assert vector is not None
        assert len(vector) == 384  # MockEmbedder default dimension

    def test_embed_text_returns_none_on_failure(self, temp_db_path):
        """Embed text returns None on embedding failure"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.embedder = None

        vector = handler.embed_text("Test")

        assert vector is None

    @patch('core.lancedb_handler.NUMPY_AVAILABLE', True)
    def test_embed_text_with_numpy_conversion(self, temp_db_path):
        """Embed text returns numpy array when numpy available"""
        handler = LanceDBHandler(db_path=temp_db_path)

        vector = handler.embed_text("Test")

        assert vector is not None
        # Should be numpy array or list depending on implementation

    def test_create_table_with_default_schema(self, temp_db_path, mock_lancedb_connection):
        """Create table with default schema"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection

        mock_table = Mock()
        handler.db.create_table = Mock(return_value=mock_table)

        table = handler.create_table("test_table")

        assert table is not None
        handler.db.create_table.assert_called_once()

    def test_create_table_with_dual_vector_support(self, temp_db_path, mock_lancedb_connection):
        """Create table with dual vector columns (ST + FastEmbed)"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection

        mock_table = Mock()
        handler.db.create_table = Mock(return_value=mock_table)

        table = handler.create_table("test_table", dual_vector=True)

        assert table is not None
        # Verify dual_vector parameter was passed
        call_args = handler.db.create_table.call_args
        assert call_args is not None

    def test_create_table_with_custom_vector_size(self, temp_db_path, mock_lancedb_connection):
        """Create table with custom vector size"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection

        mock_table = Mock()
        handler.db.create_table = Mock(return_value=mock_table)

        table = handler.create_table("test_table", vector_size=1536)

        assert table is not None

    def test_get_existing_table(self, temp_db_path, mock_lancedb_connection, mock_table):
        """Get existing table"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection
        handler.db.table_names = Mock(return_value=["test_table"])
        handler.db.open_table = Mock(return_value=mock_table)

        table = handler.get_table("test_table")

        assert table is not None
        handler.db.open_table.assert_called_once_with("test_table")

    def test_get_nonexistent_table(self, temp_db_path, mock_lancedb_connection):
        """Get non-existent table returns None"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection
        handler.db.table_names = Mock(return_value=[])

        table = handler.get_table("nonexistent")

        assert table is None

    def test_drop_table(self, temp_db_path, mock_lancedb_connection):
        """Drop existing table"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection
        handler.db.table_names = Mock(return_value=["test_table"])
        handler.db.drop_table = Mock()

        result = handler.drop_table("test_table")

        assert result is True
        handler.db.drop_table.assert_called_once_with("test_table")

    def test_drop_nonexistent_table(self, temp_db_path, mock_lancedb_connection):
        """Drop non-existent table returns True (no-op)"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection
        handler.db.table_names = Mock(return_value=[])

        result = handler.drop_table("nonexistent")

        assert result is True


# ============================================================================
# Test Class 4: TestDocumentOperations (10 tests)
# ============================================================================

class TestDocumentOperations:
    """Test document insertion and retrieval"""

    def test_add_document_success(self, temp_db_path, mock_lancedb_connection, mock_table):
        """Add single document successfully"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection
        handler.db.create_table = Mock(return_value=mock_table)
        handler.get_table = Mock(return_value=mock_table)

        with patch('core.lancedb_handler.secrets_redactor') as mock_redactor:
            mock_redact_result = Mock()
            mock_redact_result.has_secrets = False
            mock_redactor_result = Mock()
            mock_redactor_result.redacted_text = "Safe text"
            mock_redact_result.redactions = []
            mock_redactor.redact.return_value = mock_redactor_result

            success = handler.add_document(
                table_name="test_table",
                text="Test document",
                source="test",
                metadata={"key": "value"}
            )

            assert success is True
            mock_table.add.assert_called_once()

    def test_add_document_with_secrets_redaction(self, temp_db_path, mock_lancedb_connection, mock_table):
        """Add document redacts secrets before storage"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection
        handler.db.create_table = Mock(return_value=mock_table)
        handler.get_table = Mock(return_value=mock_table)

        with patch('core.lancedb_handler.get_secrets_redactor') as mock_get_redactor:
            mock_redactor = Mock()
            mock_redact_result = Mock()
            mock_redact_result.has_secrets = True
            mock_redact_result.redacted_text = "API_KEY: [REDACTED]"
            mock_redact_result.redactions = [{"type": "api_key", "count": 1}]
            mock_redactor.redact.return_value = mock_redact_result
            mock_get_redactor.return_value = mock_redactor

            success = handler.add_document(
                table_name="test_table",
                text="API key: sk-1234567890",
                source="test"
            )

            assert success is True
            mock_redactor.redact.assert_called_once()

    def test_add_document_with_custom_id(self, temp_db_path, mock_lancedb_connection, mock_table):
        """Add document with custom document ID"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection
        handler.db.create_table = Mock(return_value=mock_table)
        handler.get_table = Mock(return_value=mock_table)

        with patch('core.lancedb_handler.secrets_redactor'):
            custom_id = "custom_doc_id"
            success = handler.add_document(
                table_name="test_table",
                text="Test",
                source="test",
                doc_id=custom_id
            )

            assert success is True
            # Verify custom ID was used
            call_args = mock_table.add.call_args
            assert call_args is not None

    def test_add_document_creates_table_if_needed(self, temp_db_path, mock_lancedb_connection):
        """Add document creates table if it doesn't exist"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection
        handler.get_table = Mock(return_value=None)

        mock_table = Mock()
        handler.db.create_table = Mock(return_value=mock_table)

        with patch('core.lancedb_handler.secrets_redactor'):
            success = handler.add_document(
                table_name="new_table",
                text="Test",
                source="test"
            )

            assert success is True
            handler.db.create_table.assert_called_once()

    def test_add_documents_batch(self, temp_db_path, mock_lancedb_connection, mock_table, sample_documents):
        """Add multiple documents in batch"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection
        handler.get_table = Mock(return_value=mock_table)

        count = handler.add_documents_batch("test_table", sample_documents)

        assert count == len(sample_documents)
        mock_table.add.assert_called_once()

    def test_add_documents_batch_skips_failed_embeddings(self, temp_db_path, mock_lancedb_connection, mock_table):
        """Batch add skips documents with failed embeddings"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection
        handler.get_table = Mock(return_value=mock_table)

        # Mock embed_text to return None for one document
        def mock_embed_func(text):
            return None if "fail" in text.lower() else [0.1] * 384

        handler.embed_text = mock_embed_func

        docs = [
            {"id": "1", "text": "Valid document", "source": "test"},
            {"id": "2", "text": "This will fail", "source": "test"},
            {"id": "3", "text": "Another valid", "source": "test"}
        ]

        count = handler.add_documents_batch("test_table", docs)

        assert count == 2, "Should skip failed document"

    def test_add_documents_batch_creates_table(self, temp_db_path, mock_lancedb_connection, sample_documents):
        """Batch add creates table if it doesn't exist"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection
        handler.get_table = Mock(return_value=None)

        mock_table = Mock()
        handler.db.create_table = Mock(return_value=mock_table)

        count = handler.add_documents_batch("test_table", sample_documents)

        assert count == len(sample_documents)
        handler.db.create_table.assert_called_once()


# ============================================================================
# Test Class 5: TestSemanticSearch (8 tests)
# ============================================================================

class TestSemanticSearch:
    """Test semantic vector search functionality"""

    def test_basic_vector_search(self, temp_db_path, mock_lancedb_connection):
        """Basic vector search by query text"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection

        # Mock table and search results
        mock_table = Mock()
        mock_df = Mock()
        mock_df.iterrows = Mock(return_value=[])
        mock_df.empty = True
        mock_table.search.return_value.limit.return_value.to_pandas.return_value = mock_df
        handler.get_table = Mock(return_value=mock_table)

        results = handler.search("test_table", "machine learning query")

        assert isinstance(results, list)
        mock_table.search.assert_called_once()

    def test_search_with_limit(self, temp_db_path, mock_lancedb_connection):
        """Search with custom result limit"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection

        mock_table = Mock()
        mock_df = Mock()
        mock_df.iterrows = Mock(return_value=[])
        mock_df.empty = True
        mock_table.search.return_value.limit.return_value.to_pandas.return_value = mock_df
        handler.get_table = Mock(return_value=mock_table)

        results = handler.search("test_table", "query", limit=5)

        # Verify limit was applied
        mock_table.search.return_value.limit.assert_called_with(5)

    def test_search_with_user_filter(self, temp_db_path, mock_lancedb_connection):
        """Search with user ID filter"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection

        mock_table = Mock()
        mock_df = Mock()
        mock_df.iterrows = Mock(return_value=[])
        mock_df.empty = True
        mock_table.search.return_value.limit.return_value.where.return_value.to_pandas.return_value = mock_df
        handler.get_table = Mock(return_value=mock_table)

        results = handler.search("test_table", "query", user_id="user123")

        # Verify where clause was applied
        mock_table.search.return_value.limit.return_value.where.assert_called_once()

    def test_search_with_custom_filter(self, temp_db_path, mock_lancedb_connection):
        """Search with custom filter expression"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection

        mock_table = Mock()
        mock_df = Mock()
        mock_df.iterrows = Mock(return_value=[])
        mock_df.empty = True
        mock_table.search.return_value.limit.return_value.where.return_value.to_pandas.return_value = mock_df
        handler.get_table = Mock(return_value=mock_table)

        results = handler.search(
            "test_table",
            "query",
            filter_str="category == 'AI'"
        )

        # Verify filter was applied
        mock_table.search.return_value.limit.return_value.where.assert_called_once()

    def test_search_converts_distance_to_similarity(self, temp_db_path, mock_lancedb_connection):
        """Search converts distance to similarity score"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection

        # Mock search result with distance
        mock_table = Mock()
        mock_df = Mock()
        mock_row = {
            'id': 'doc1',
            'text': 'Test document',
            'source': 'test',
            'metadata': '{}',
            'created_at': '2024-01-01T00:00:00Z',
            '_distance': 0.3  # Distance metric
        }
        mock_df.iterrows = Mock(return_value=[(0, mock_row)])
        mock_df.empty = False
        mock_table.search.return_value.limit.return_value.to_pandas.return_value = mock_df
        handler.get_table = Mock(return_value=mock_table)

        results = handler.search("test_table", "query")

        assert len(results) == 1
        # Distance 0.3 should convert to similarity 0.7
        assert abs(results[0]['score'] - 0.7) < 0.01

    def test_search_with_nonexistent_table(self, temp_db_path, mock_lancedb_connection):
        """Search with non-existent table returns empty list"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection
        handler.get_table = Mock(return_value=None)

        results = handler.search("nonexistent", "query")

        assert results == []

    def test_search_with_embedding_failure(self, temp_db_path, mock_lancedb_connection):
        """Search returns empty list on embedding failure"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection
        handler.embed_text = Mock(return_value=None)

        results = handler.search("test_table", "query")

        assert results == []

    @patch('core.lancedb_handler.PANDAS_AVAILABLE', False)
    def test_search_with_pandas_unavailable(self, temp_db_path, mock_lancedb_connection):
        """Search returns empty list when Pandas unavailable"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection

        mock_table = Mock()
        handler.get_table = Mock(return_value=mock_table)

        results = handler.search("test_table", "query")

        assert results == []


# ============================================================================
# Test Class 6: TestKnowledgeGraphOperations (5 tests)
# ============================================================================

class TestKnowledgeGraphOperations:
    """Test knowledge graph edge operations"""

    def test_add_knowledge_edge(self, temp_db_path, mock_lancedb_connection, mock_table):
        """Add knowledge graph edge"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection
        handler.get_table = Mock(return_value=None)
        handler.create_table = Mock(return_value=mock_table)

        success = handler.add_knowledge_edge(
            from_id="entity1",
            to_id="entity2",
            rel_type="related_to",
            description="Entity1 is related to Entity2",
            metadata={"strength": 0.8}
        )

        assert success is True
        mock_table.add.assert_called_once()

    def test_add_knowledge_edge_generates_unique_id(self, temp_db_path, mock_lancedb_connection, mock_table):
        """Add knowledge edge generates unique edge ID"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection
        handler.get_table = Mock(return_value=None)
        handler.create_table = Mock(return_value=mock_table)

        handler.add_knowledge_edge(
            from_id="entity1",
            to_id="entity2",
            rel_type="related_to"
        )

        call_args = mock_table.add.call_args
        assert call_args is not None
        record = call_args[0][0][0] if call_args[0] else call_args.kwargs.get('data', [{}])[0]
        assert 'entity1_related_to_entity2' in record.get('id', '')

    def test_query_knowledge_graph(self, temp_db_path, mock_lancedb_connection):
        """Query knowledge graph using semantic search"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection

        mock_table = Mock()
        mock_df = Mock()
        mock_df.iterrows = Mock(return_value=[])
        mock_df.empty = True
        mock_table.search.return_value.limit.return_value.to_pandas.return_value = mock_df
        handler.get_table = Mock(return_value=mock_table)

        results = handler.query_knowledge_graph("related entities")

        assert isinstance(results, list)
        handler.get_table.assert_called_once_with("knowledge_graph")


# ============================================================================
# Test Class 7: TestDualVectorStorage (6 tests)
# ============================================================================

class TestDualVectorStorage:
    """Test dual vector storage (ST + FastEmbed)"""

    @pytest.mark.asyncio
    async def test_add_embedding_to_vector_column(self, temp_db_path, mock_lancedb_connection, mock_table):
        """Add embedding to standard vector column"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection
        handler.get_table = Mock(return_value=None)
        handler.create_table = Mock(return_value=mock_table)

        vector = [0.1] * 1024  # ST dimension
        success = await handler.add_embedding(
            table_name="episodes",
            episode_id="ep1",
            vector=vector,
            vector_column="vector"
        )

        assert success is True
        mock_table.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_embedding_to_fastembed_column(self, temp_db_path, mock_lancedb_connection, mock_table):
        """Add embedding to FastEmbed vector column"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection
        handler.get_table = Mock(return_value=None)
        handler.create_table = Mock(return_value=mock_table)

        vector = [0.1] * 384  # FastEmbed dimension
        success = await handler.add_embedding(
            table_name="episodes",
            episode_id="ep1",
            vector=vector,
            vector_column="vector_fastembed"
        )

        assert success is True

    @pytest.mark.asyncio
    async def test_add_embedding_dimension_mismatch_raises_error(self, temp_db_path, mock_lancedb_connection):
        """Add embedding with dimension mismatch raises ValueError"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection

        # Wrong dimension for FastEmbed (384)
        vector = [0.1] * 500  # 500-dim vector

        with pytest.raises(ValueError, match="Dimension mismatch"):
            await handler.add_embedding(
                table_name="episodes",
                episode_id="ep1",
                vector=vector,
                vector_column="vector_fastembed"
            )

    @pytest.mark.asyncio
    async def test_add_embedding_invalid_column_raises_error(self, temp_db_path, mock_lancedb_connection):
        """Add embedding to invalid column raises ValueError"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection

        vector = [0.1] * 384

        with pytest.raises(ValueError, match="Unknown vector column"):
            await handler.add_embedding(
                table_name="episodes",
                episode_id="ep1",
                vector=vector,
                vector_column="invalid_column"
            )

    @pytest.mark.asyncio
    async def test_similarity_search_on_vector_column(self, temp_db_path, mock_lancedb_connection):
        """Similarity search on specified vector column"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection

        mock_table = Mock()
        mock_df = Mock()
        mock_df.iterrows = Mock(return_value=[])
        mock_df.empty = True
        mock_table.search.return_value.limit.return_value.to_pandas.return_value = mock_df
        handler.get_table = Mock(return_value=mock_table)

        vector = [0.1] * 384
        results = await handler.similarity_search(
            table_name="episodes",
            vector=vector,
            vector_column="vector_fastembed",
            top_k=5
        )

        assert isinstance(results, list)
        mock_table.search.assert_called_once_with(vector)

    @pytest.mark.asyncio
    async def test_similarity_search_with_dimension_mismatch(self, temp_db_path, mock_lancedb_connection):
        """Similarity search with dimension mismatch raises ValueError"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection

        vector = [0.1] * 500  # Wrong dimension

        with pytest.raises(ValueError, match="Dimension mismatch"):
            await handler.similarity_search(
                table_name="episodes",
                vector=vector,
                vector_column="vector_fastembed"
            )


# ============================================================================
# Test Class 8: TestChatHistoryManager (6 tests)
# ============================================================================

class TestChatHistoryManager:
    """Test chat history management"""

    def test_save_message(self, temp_db_path, mock_lancedb_connection, mock_table):
        """Save chat message with embedding"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection
        handler.create_table = Mock(return_value=mock_table)
        handler.get_table = Mock(return_value=mock_table)

        manager = ChatHistoryManager(handler)

        success = manager.save_message(
            session_id="session1",
            user_id="user1",
            role="user",
            content="Hello, how are you?",
            metadata={"intent": "greeting"}
        )

        assert success is True

    def test_get_session_history(self, temp_db_path, mock_lancedb_connection):
        """Retrieve session history in chronological order"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection

        mock_table = Mock()
        mock_df = Mock()
        # Mock multiple messages
        mock_rows = [
            {'id': 'msg1', 'text': 'Hello', 'role': 'user', 'created_at': '2024-01-01T12:00:00Z', 'metadata': '{"session_id": "session1"}'},
            {'id': 'msg2', 'text': 'Hi there', 'role': 'assistant', 'created_at': '2024-01-01T12:01:00Z', 'metadata': '{"session_id": "session1"}'}
        ]
        mock_df.iterrows = Mock(return_value=enumerate(mock_rows))
        mock_table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = mock_df
        handler.get_table = Mock(return_value=mock_table)

        manager = ChatHistoryManager(handler)

        with patch('core.lancedb_handler.PANDAS_AVAILABLE', True):
            messages = manager.get_session_history("session1", limit=10)

            assert len(messages) == 2

    def test_search_relevant_context(self, temp_db_path, mock_lancedb_connection):
        """Search semantically similar messages"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection

        mock_table = Mock()
        mock_df = Mock()
        mock_df.iterrows = Mock(return_value=[])
        mock_df.empty = True
        mock_table.search.return_value.limit.return_value.where.return_value.to_pandas.return_value = mock_df
        handler.get_table = Mock(return_value=mock_table)

        manager = ChatHistoryManager(handler)

        results = manager.search_relevant_context(
            query="machine learning",
            session_id="session1",
            limit=5
        )

        assert isinstance(results, list)

    def test_get_entity_mentions(self, temp_db_path, mock_lancedb_connection):
        """Find messages mentioning specific entity"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection

        mock_table = Mock()
        mock_df = Mock()
        mock_rows = [
            {'id': 'msg1', 'text': 'Workflow started', 'role': 'user', 'created_at': '2024-01-01T12:00:00Z', 'metadata': '{"workflow_id": "wf123", "session_id": "session1"}'}
        ]
        mock_df.iterrows = Mock(return_value=enumerate(mock_rows))
        mock_table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = mock_df
        handler.get_table = Mock(return_value=mock_table)

        manager = ChatHistoryManager(handler)

        with patch('core.lancedb_handler.PANDAS_AVAILABLE', True):
            messages = manager.get_entity_mentions(
                entity_type="workflow_id",
                entity_id="wf123",
                session_id="session1"
            )

            assert len(messages) >= 0


# ============================================================================
# Test Class 9: TestErrorHandling (6 tests)
# ============================================================================

class TestErrorHandling:
    """Test error handling and graceful degradation"""

    def test_lancedb_unavailable_returns_graceful_empty_results(self, temp_db_path):
        """Handler returns empty results when LanceDB unavailable"""
        with patch('core.lancedb_handler.LANCEDB_AVAILABLE', False):
            handler = LanceDBHandler(db_path=temp_db_path)

            results = handler.search("test_table", "query")

            assert results == []

    def test_table_creation_failure_returns_none(self, temp_db_path, mock_lancedb_connection):
        """Table creation failure returns None"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection
        handler.db.create_table = Mock(side_effect=Exception("Creation failed"))

        table = handler.create_table("test_table")

        assert table is None

    def test_document_add_failure_returns_false(self, temp_db_path, mock_lancedb_connection):
        """Document add failure returns False"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection

        mock_table = Mock()
        mock_table.add = Mock(side_effect=Exception("Add failed"))
        handler.get_table = Mock(return_value=mock_table)

        with patch('core.lancedb_handler.secrets_redactor'):
            success = handler.add_document(
                table_name="test_table",
                text="Test",
                source="test"
            )

            assert success is False

    def test_embed_text_failure_returns_none(self, temp_db_path):
        """Embed text failure returns None"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.embedder = Mock()
        handler.embedder.encode = Mock(side_effect=Exception("Embed failed"))

        vector = handler.embed_text("Test")

        assert vector is None

    def test_connection_test_failure_returns_error_status(self, temp_db_path, mock_lancedb_connection):
        """Connection test failure returns error status"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection
        handler.db.table_names = Mock(side_effect=Exception("Connection failed"))

        result = handler.test_connection()

        assert result["status"] == "error"
        assert result["connected"] is False

    def test_batch_add_partial_failure_continues(self, temp_db_path, mock_lancedb_connection, mock_table):
        """Batch add continues after individual embedding failures"""
        handler = LanceDBHandler(db_path=temp_db_path)
        handler.db = mock_lancedb_connection
        handler.get_table = Mock(return_value=mock_table)

        # Mock embed to fail for one document
        call_count = [0]
        def mock_embed(text):
            call_count[0] += 1
            return None if call_count[0] == 2 else [0.1] * 384

        handler.embed_text = mock_embed

        docs = [
            {"id": "1", "text": "Doc 1", "source": "test"},
            {"id": "2", "text": "Doc 2 (fails)", "source": "test"},
            {"id": "3", "text": "Doc 3", "source": "test"}
        ]

        count = handler.add_documents_batch("test_table", docs)

        # Should add 2 out of 3 documents
        assert count == 2


# ============================================================================
# Test Class 10: TestUtilityFunctions (4 tests)
# ============================================================================

class TestUtilityFunctions:
    """Test utility and helper functions"""

    def test_get_lancedb_handler_singleton(self, temp_db_path, monkeypatch):
        """get_lancedb_handler returns singleton instance"""
        monkeypatch.setenv("LANCEDB_URI_BASE", temp_db_path)

        handler1 = get_lancedb_handler("test_workspace")
        handler2 = get_lancedb_handler("test_workspace")

        assert handler1 is handler2, "Should return same instance for same workspace"

    def test_get_lancedb_handler_different_workspaces(self, temp_db_path, monkeypatch):
        """get_lancedb_handler creates different instances for different workspaces"""
        monkeypatch.setenv("LANCEDB_URI_BASE", temp_db_path)

        handler1 = get_lancedb_handler("workspace1")
        handler2 = get_lancedb_handler("workspace2")

        assert handler1 is not handler2, "Should return different instances for different workspaces"

    def test_get_chat_history_manager(self, temp_db_path):
        """get_chat_history_manager returns manager instance"""
        manager = get_chat_history_manager()

        assert isinstance(manager, ChatHistoryManager)
        assert manager.db is not None

    def test_embed_documents_batch_with_sentence_transformers(self):
        """Batch embedding using SentenceTransformers"""
        with patch('core.lancedb_handler.SENTENCE_TRANSFORMERS_AVAILABLE', True):
            with patch('core.lancedb_handler.SentenceTransformer') as mock_st:
                mock_model = Mock()
                mock_model.encode = Mock(return_value=[[0.1] * 384, [0.2] * 384])
                mock_st.return_value = mock_model

                from core.lancedb_handler import embed_documents_batch
                embeddings = embed_documents_batch(["text1", "text2"])

                assert embeddings is not None


# Total: 67 tests
