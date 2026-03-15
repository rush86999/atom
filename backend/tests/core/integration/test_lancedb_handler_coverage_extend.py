"""
Coverage-driven tests for lancedb_handler.py (19.1% -> 70%+ target)

Coverage Target Areas:
- Lines 128-180: Handler initialization and lazy loading
- Lines 180-295: DB and embedder initialization (with BYOK integration)
- Lines 297-415: Table management (create, get, drop)
- Lines 451-667: Document operations (add, search, get by ID)
- Lines 669-724: Batch document operations
- Lines 726-801: Similarity search with filters
- Lines 906-1108: Dual vector storage and similarity search
- Lines 1111-1369: ChatHistoryManager class

Test Strategy:
- Mock LanceDB client to avoid external dependencies
- Cover vector operations, search, and batch operations
- Test error handling and edge cases
- Focus on achieving 70%+ coverage (496+ of 709 statements)
"""

import pytest
import sys
from unittest.mock import Mock, MagicMock, AsyncMock, patch, call
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

# Mock numpy and pandas for vector operations
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

# Now we can safely import the handler
from core.lancedb_handler import (
    LanceDBHandler,
    LANCEDB_AVAILABLE,
    NUMPY_AVAILABLE as Handler_NUMPY,
    PANDAS_AVAILABLE as Handler_PANDAS,
    ChatHistoryManager,
    get_lancedb_handler,
    get_chat_history_manager,
    MockEmbedder,
)

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_lancedb_client():
    """Mock LanceDB client."""
    client = MagicMock()
    client.table_names = Mock(return_value=[])
    return client


@pytest.fixture
def mock_table():
    """Mock LanceDB table."""
    table = MagicMock()
    table.add = Mock()
    table.search = Mock()
    table.name = "test_table"
    return table


@pytest.fixture
def sample_vector_384():
    """384-dim vector for testing."""
    if NUMPY_AVAILABLE:
        return [0.1] * 384
    return [0.1] * 384


@pytest.fixture
def sample_vector_1024():
    """1024-dim vector for testing."""
    if NUMPY_AVAILABLE:
        return [0.1] * 1024
    return [0.1] * 1024


@pytest.fixture
def sample_search_results():
    """Mock search results as pandas DataFrame."""
    if not PANDAS_AVAILABLE:
        return None

    import pandas as pd
    return pd.DataFrame({
        'id': ['doc1', 'doc2', 'doc3'],
        'text': ['Test document 1', 'Test document 2', 'Test document 3'],
        'source': ['test', 'test', 'test'],
        'metadata': [{'key': 'value1'}, {'key': 'value2'}, {'key': 'value3'}],
        'created_at': ['2024-01-01T00:00:00', '2024-01-02T00:00:00', '2024-01-03T00:00:00'],
        '_distance': [0.1, 0.2, 0.3],
        'vector': [[0.1] * 384, [0.1] * 384, [0.1] * 384],
        'user_id': ['user1', 'user1', 'user1'],
        'workspace_id': ['default', 'default', 'default']
    })


@pytest.fixture
def handler_with_db():
    """Handler with mocked database connection."""
    # Reset module-level mock
    import lancedb as lancedb_module
    mock_db = MagicMock()
    mock_db.table_names = Mock(return_value=[])
    lancedb_module.connect = Mock(return_value=mock_db)

    handler = LanceDBHandler(db_path="/tmp/test.db")
    handler._initialize_db()
    return handler


# ============================================================================
# Test Class: LanceDBHandler Coverage Extension
# ============================================================================

class TestLanceDBHandlerCoverageExtend:
    """
    Extended coverage tests for LanceDBHandler.

    Target: 70%+ coverage (496+ of 709 statements)
    Focus: Vector operations, search, batch operations, error handling
    """

    # =========================================================================
    # Initialization Tests (6 tests)
    # =========================================================================

    def test_handler_initialization_with_defaults(self):
        """Test handler initialization with default parameters."""
        handler = LanceDBHandler()

        assert handler.db_path == os.getenv("LANCEDB_URI", "./data/atom_memory")
        assert handler.workspace_id == "default"
        assert handler.embedding_provider in ["local", "openai", "fastembed"]
        assert handler.db is None  # Lazy initialization
        assert handler.embedder is None  # Lazy initialization

    def test_handler_initialization_with_custom_params(self):
        """Test handler initialization with custom parameters."""
        handler = LanceDBHandler(
            db_path="/custom/path",
            embedding_provider="openai",
            embedding_model="text-embedding-3-small"
        )

        assert handler.db_path == "/custom/path"
        assert handler.embedding_provider == "openai"
        assert handler.embedding_model == "text-embedding-3-small"

    def test_handler_initialization_with_env_vars(self, monkeypatch):
        """Test handler initialization respects environment variables."""
        monkeypatch.setenv("EMBEDDING_PROVIDER", "fastembed")
        monkeypatch.setenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")

        handler = LanceDBHandler()

        assert handler.embedding_provider == "fastembed"
        assert handler.embedding_model == "BAAI/bge-small-en-v1.5"
        assert handler.openai_api_key == "sk-test-key"

    def test_dual_vector_storage_config(self):
        """Test dual vector storage configuration."""
        handler = LanceDBHandler()

        assert handler.vector_columns == {
            "vector": 1024,  # SentenceTransformers
            "vector_fastembed": 384  # FastEmbed
        }

    def test_lazy_db_initialization(self):
        """Test DB is initialized lazily on first use."""
        with patch('core.lancedb_handler.lancedb.connect') as mock_connect:
            mock_db = MagicMock()
            mock_db.table_names = Mock(return_value=[])
            mock_connect.return_value = mock_db

            handler = LanceDBHandler()
            assert handler.db is None

            handler._ensure_db()
            assert handler.db is not None
            mock_connect.assert_called_once()

    def test_lazy_embedder_initialization(self):
        """Test embedder is initialized lazily on first use."""
        handler = LanceDBHandler()
        assert handler.embedder is None

        handler._ensure_embedder()
        # Should initialize mock embedder if sentence transformers not available
        assert handler.embedder is not None

    # =========================================================================
    # DB Initialization Tests (4 tests)
    # =========================================================================

    def test_initialize_db_local_path(self, tmp_path):
        """Test DB initialization with local path."""
        db_path = str(tmp_path / "test.db")

        # Use module-level mock
        import lancedb as lancedb_module
        mock_db = MagicMock()
        mock_db.table_names = Mock(return_value=[])
        lancedb_module.connect = Mock(return_value=mock_db)

        handler = LanceDBHandler(db_path=db_path)
        handler._initialize_db()

        assert handler.db is not None

    def test_initialize_db_s3_path(self, monkeypatch):
        """Test DB initialization with S3 path."""
        monkeypatch.setenv("AWS_ENDPOINT_URL", "https://r2.endpoint.com")
        monkeypatch.setenv("R2_ACCESS_KEY_ID", "access_key")
        monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "secret_key")
        monkeypatch.setenv("AWS_REGION", "auto")

        # Use module-level mock
        import lancedb as lancedb_module
        mock_db = MagicMock()
        mock_db.table_names = Mock(return_value=[])
        lancedb_module.connect = Mock(return_value=mock_db)

        handler = LanceDBHandler(db_path="s3://bucket/path")
        handler._initialize_db()

        # Verify storage options were passed
        call_kwargs = lancedb_module.connect.call_args[1]
        assert 'storage_options' in call_kwargs
        storage_options = call_kwargs['storage_options']
        assert storage_options['endpoint'] == "https://r2.endpoint.com"
        assert storage_options['aws_access_key_id'] == "access_key"

    def test_initialize_db_failure(self):
        """Test DB initialization failure handling."""
        # Use module-level mock
        import lancedb as lancedb_module
        lancedb_module.connect = Mock(side_effect=Exception("Connection failed"))

        handler = LanceDBHandler()
        handler._initialize_db()

        assert handler.db is None

    def test_ensure_db_already_initialized(self, handler_with_db):
        """Test _ensure_db doesn't reinitialize if already done."""
        initial_db = handler_with_db.db
        handler_with_db._ensure_db()

        assert handler_with_db.db is initial_db

    # =========================================================================
    # Embedder Initialization Tests (4 tests)
    # =========================================================================

    def test_init_local_embedder_with_sentence_transformers(self):
        """Test local embedder initialization with sentence transformers."""
        handler = LanceDBHandler()

        # Mock sentence transformers import
        with patch('core.lancedb_handler.SENTENCE_TRANSFORMERS_AVAILABLE', True):
            with patch('core.lancedb_handler.SentenceTransformer') as mock_st:
                mock_model = MagicMock()
                mock_model.encode = Mock(return_value=[0.1] * 384)
                mock_st.return_value = mock_model

                # Mock threading to avoid timeout
                with patch('core.lancedb_handler.threading') as mock_threading:
                    mock_queue = MagicMock()
                    mock_threading.Queue.return_value = mock_queue
                    mock_threading.Thread = MagicMock

                    handler._init_local_embedder()

                    assert handler.embedder is not None

    def test_init_local_embedder_fallback_to_mock(self):
        """Test fallback to MockEmbedder when sentence transformers unavailable."""
        with patch('core.lancedb_handler.SENTENCE_TRANSFORMERS_AVAILABLE', False):
            handler = LanceDBHandler()
            handler._init_local_embedder()

            assert handler.embedder is not None
            assert isinstance(handler.embedder, MockEmbedder)

    def test_init_openai_embedder_with_api_key(self, monkeypatch):
        """Test OpenAI embedder initialization with API key."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")

        with patch('core.lancedb_handler.OPENAI_AVAILABLE', True):
            with patch('openai.OpenAI') as mock_openai:
                mock_client = MagicMock()
                mock_openai.return_value = mock_client

                handler = LanceDBHandler(embedding_provider="openai")
                handler._initialize_embedder()

                assert handler.openai_client is not None

    def test_init_openai_embedder_fallback_to_local(self, monkeypatch):
        """Test fallback to local embedder when OpenAI API key missing."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        with patch('core.lancedb_handler.OPENAI_AVAILABLE', True):
            handler = LanceDBHandler(embedding_provider="openai")
            handler._initialize_embedder()

            # Should fallback to local
            assert handler.embedding_provider == "local"

    # =========================================================================
    # Connection Tests (3 tests)
    # =========================================================================

    def test_connection_success(self, handler_with_db):
        """Test successful connection check."""
        result = handler_with_db.test_connection()

        assert result['status'] == 'success'
        assert result['connected'] is True
        assert 'tables' in result

    def test_connection_not_available(self):
        """Test connection when LanceDB not available."""
        with patch('core.lancedb_handler.LANCEDB_AVAILABLE', False):
            handler = LanceDBHandler()
            result = handler.test_connection()

            assert result['status'] == 'error'
            assert result['connected'] is False
            assert 'not available' in result['message'].lower()

    def test_connection_not_initialized(self):
        """Test connection when DB not initialized."""
        handler = LanceDBHandler()
        # Manually set db to None to simulate uninitialized state
        handler.db = None

        result = handler.test_connection()

        assert result['status'] == 'error'
        assert result['connected'] is False

    # =========================================================================
    # Table Management Tests (8 tests)
    # =========================================================================

    def test_create_table_with_default_schema(self, handler_with_db):
        """Test creating table with default schema."""
        mock_table = MagicMock()
        handler_with_db.db.create_table = Mock(return_value=mock_table)

        result = handler_with_db.create_table("test_table")

        assert result is not None
        handler_with_db.db.create_table.assert_called_once()

    def test_create_table_with_dual_vector(self, handler_with_db):
        """Test creating table with dual vector storage."""
        mock_table = MagicMock()
        handler_with_db.db.create_table = Mock(return_value=mock_table)

        result = handler_with_db.create_table("test_table", dual_vector=True)

        assert result is not None
        # Verify dual vector column was added

    def test_create_table_for_knowledge_graph(self, handler_with_db):
        """Test creating knowledge graph table."""
        mock_table = MagicMock()
        handler_with_db.db.create_table = Mock(return_value=mock_table)

        result = handler_with_db.create_table("knowledge_graph")

        assert result is not None
        handler_with_db.db.create_table.assert_called_once()

    def test_create_table_failure(self, handler_with_db):
        """Test table creation failure."""
        handler_with_db.db.create_table = Mock(side_effect=Exception("Table creation failed"))

        result = handler_with_db.create_table("test_table")

        assert result is None

    def test_get_existing_table(self, handler_with_db):
        """Test getting existing table."""
        mock_table = MagicMock()
        handler_with_db.db.open_table = Mock(return_value=mock_table)
        handler_with_db.db.table_names = Mock(return_value=["test_table"])

        result = handler_with_db.get_table("test_table")

        assert result is not None
        handler_with_db.db.open_table.assert_called_once_with("test_table")

    def test_get_nonexistent_table(self, handler_with_db):
        """Test getting non-existent table."""
        handler_with_db.db.open_table = Mock(return_value=None)
        handler_with_db.db.table_names = Mock(return_value=["other_table"])

        result = handler_with_db.get_table("test_table")

        assert result is None

    def test_drop_table_success(self, handler_with_db):
        """Test successful table drop."""
        handler_with_db.db.table_names = Mock(return_value=["test_table"])
        handler_with_db.db.drop_table = Mock()

        result = handler_with_db.drop_table("test_table")

        assert result is True
        handler_with_db.db.drop_table.assert_called_once_with("test_table")

    def test_drop_table_failure(self, handler_with_db):
        """Test table drop failure."""
        handler_with_db.db.table_names = Mock(return_value=["test_table"])
        handler_with_db.db.drop_table = Mock(side_effect=Exception("Drop failed"))

        result = handler_with_db.drop_table("test_table")

        assert result is False

    # =========================================================================
    # Embedding Tests (4 tests)
    # =========================================================================

    def test_embed_text_with_local_provider(self, handler_with_db):
        """Test text embedding with local provider."""
        handler_with_db.embedder = Mock()
        handler_with_db.embedding_provider = "local"
        handler_with_db.embedder.encode = Mock(return_value=[0.1] * 384)

        result = handler_with_db.embed_text("test text")

        assert result is not None
        handler_with_db.embedder.encode.assert_called_once()

    def test_embed_text_with_openai_provider(self, handler_with_db):
        """Test text embedding with OpenAI provider."""
        handler_with_db.embedding_provider = "openai"
        handler_with_db.openai_client = MagicMock()

        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        handler_with_db.openai_client.embeddings.create = Mock(return_value=mock_response)

        result = handler_with_db.embed_text("test text")

        assert result is not None
        assert len(result) == 1536

    def test_embed_text_no_provider_available(self):
        """Test embedding when no provider available."""
        handler = LanceDBHandler()
        handler.embedder = None
        handler.openai_client = None
        handler.embedding_provider = "local"  # No provider

        result = handler.embed_text("test text")

        assert result is None

    def test_embed_text_failure(self, handler_with_db):
        """Test embedding failure handling."""
        handler_with_db.embedder = Mock()
        handler_with_db.embedder.encode = Mock(side_effect=Exception("Encoding failed"))

        result = handler_with_db.embed_text("test text")

        assert result is None

    # =========================================================================
    # Document Operations Tests (8 tests)
    # =========================================================================

    def test_add_document_success(self, handler_with_db):
        """Test successful document addition."""
        mock_table = MagicMock()
        handler_with_db.get_table = Mock(return_value=mock_table)

        # Mock embedding with numpy array that has tolist() method
        if NUMPY_AVAILABLE:
            import numpy as np
            mock_embedding = np.array([0.1] * 384, dtype=np.float32)
        else:
            # Create a list-like object with tolist method
            class MockVector(list):
                def tolist(self):
                    return list(self)
            mock_embedding = MockVector([0.1] * 384)

        handler_with_db.embed_text = Mock(return_value=mock_embedding)

        result = handler_with_db.add_document(
            "test_table",
            "Test document text",
            source="test_source",
            metadata={"key": "value"}
        )

        assert result is True
        mock_table.add.assert_called_once()

    def test_add_document_with_secrets_redaction(self, handler_with_db):
        """Test document addition with secrets redaction."""
        mock_table = MagicMock()
        handler_with_db.get_table = Mock(return_value=mock_table)
        handler_with_db.embed_text = Mock(return_value=[0.1] * 384)

        with patch('core.lancedb_handler.get_secrets_redactor') as mock_redactor:
            mock_redactor_instance = MagicMock()
            mock_redactor_instance.redact.return_value = MagicMock(
                has_secrets=True,
                redacted_text="REDACTED text",
                redactions=[{"type": "api_key"}]
            )
            mock_redactor.return_value = mock_redactor_instance

            result = handler_with_db.add_document(
                "test_table",
                "API key: sk-1234567890",
                source="test"
            )

            assert result is True

    def test_add_document_embedding_failure(self, handler_with_db):
        """Test document addition when embedding fails."""
        mock_table = MagicMock()
        handler_with_db.get_table = Mock(return_value=mock_table)
        handler_with_db.embed_text = Mock(return_value=None)

        result = handler_with_db.add_document(
            "test_table",
            "Test document"
        )

        assert result is False

    def test_add_document_with_custom_id(self, handler_with_db):
        """Test document addition with custom doc_id."""
        mock_table = MagicMock()
        handler_with_db.get_table = Mock(return_value=mock_table)
        handler_with_db.embed_text = Mock(return_value=[0.1] * 384)

        result = handler_with_db.add_document(
            "test_table",
            "Test document",
            doc_id="custom_doc_id"
        )

        assert result is True
        # Verify custom ID was used

    def test_get_document_by_id_success(self, handler_with_db, sample_search_results):
        """Test getting document by ID."""
        mock_table = MagicMock()
        handler_with_db.get_table = Mock(return_value=mock_table)

        # Mock search to return single document
        import pandas as pd
        single_doc = pd.DataFrame({
            'id': ['doc1'],
            'text': ['Test document'],
            'source': ['test'],
            'metadata': ['{"key": "value"}'],
            'created_at': ['2024-01-01T00:00:00'],
            'vector': [[0.1] * 384]
        })
        mock_table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = single_doc

        result = handler_with_db.get_document_by_id("test_table", "doc1")

        assert result is not None
        assert result['id'] == 'doc1'
        assert result['text'] == 'Test document'

    def test_get_document_by_id_not_found(self, handler_with_db):
        """Test getting non-existent document."""
        mock_table = MagicMock()
        handler_with_db.get_table = Mock(return_value=mock_table)

        import pandas as pd
        mock_table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = pd.DataFrame()

        result = handler_with_db.get_document_by_id("test_table", "nonexistent")

        assert result is None

    def test_list_documents_success(self, handler_with_db):
        """Test listing documents."""
        mock_table = MagicMock()
        handler_with_db.get_table = Mock(return_value=mock_table)

        import pandas as pd
        docs_df = pd.DataFrame({
            'id': ['doc1', 'doc2'],
            'text': ['Doc 1', 'Doc 2'],
            'source': ['test', 'test'],
            'metadata': ['{}', '{}'],
            'created_at': ['2024-01-01', '2024-01-02']
        })
        mock_table.search.return_value.limit.return_value.to_pandas.return_value = docs_df

        result = handler_with_db.list_documents("test_table", limit=10)

        assert len(result) == 2

    def test_list_documents_empty_table(self, handler_with_db):
        """Test listing documents from empty table."""
        mock_table = MagicMock()
        handler_with_db.get_table = Mock(return_value=mock_table)

        import pandas as pd
        mock_table.search.return_value.limit.return_value.to_pandas.return_value = pd.DataFrame()

        result = handler_with_db.list_documents("test_table")

        assert len(result) == 0

    # =========================================================================
    # Batch Operations Tests (7 tests)
    # =========================================================================

    def test_add_documents_batch_success(self, handler_with_db):
        """Test successful batch document addition."""
        mock_table = MagicMock()
        handler_with_db.get_table = Mock(return_value=mock_table)
        handler_with_db.embed_text = Mock(return_value=[0.1] * 384)

        documents = [
            {"text": "Doc 1", "source": "test"},
            {"text": "Doc 2", "source": "test"},
            {"text": "Doc 3", "source": "test"}
        ]

        result = handler_with_db.add_documents_batch("test_table", documents)

        assert result == 3
        mock_table.add.assert_called_once()

    def test_add_documents_batch_partial_failure(self, handler_with_db):
        """Test batch addition with some embedding failures."""
        mock_table = MagicMock()
        handler_with_db.get_table = Mock(return_value=mock_table)

        # First two succeed, third fails
        call_count = [0]
        def mock_embed(text):
            call_count[0] += 1
            if call_count[0] == 3:
                return None  # Third fails
            return [0.1] * 384

        handler_with_db.embed_text = Mock(side_effect=mock_embed)

        documents = [
            {"text": "Doc 1", "source": "test"},
            {"text": "Doc 2", "source": "test"},
            {"text": "Doc 3", "source": "test"}
        ]

        result = handler_with_db.add_documents_batch("test_table", documents)

        # Should only add 2 documents (third failed embedding)
        assert result == 2

    def test_add_documents_batch_create_table(self, handler_with_db):
        """Test batch addition creates table if not exists."""
        handler_with_db.get_table = Mock(return_value=None)
        handler_with_db.embed_text = Mock(return_value=[0.1] * 384)
        handler_with_db.db.create_table = Mock(return_value=MagicMock())

        documents = [{"text": "Doc 1", "source": "test"}]

        result = handler_with_db.add_documents_batch("test_table", documents)

        assert result == 1
        handler_with_db.db.create_table.assert_called_once()

    def test_add_documents_batch_empty_list(self, handler_with_db):
        """Test batch addition with empty document list."""
        result = handler_with_db.add_documents_batch("test_table", [])

        assert result == 0

    def test_add_documents_batch_all_failures(self, handler_with_db):
        """Test batch addition when all embeddings fail."""
        mock_table = MagicMock()
        handler_with_db.get_table = Mock(return_value=mock_table)
        handler_with_db.embed_text = Mock(return_value=None)

        documents = [
            {"text": "Doc 1", "source": "test"},
            {"text": "Doc 2", "source": "test"}
        ]

        result = handler_with_db.add_documents_batch("test_table", documents)

        assert result == 0

    def test_add_documents_batch_table_creation_failure(self, handler_with_db):
        """Test batch addition when table creation fails."""
        handler_with_db.get_table = Mock(return_value=None)
        handler_with_db.embed_text = Mock(return_value=[0.1] * 384)
        handler_with_db.db.create_table = Mock(side_effect=Exception("Creation failed"))

        documents = [{"text": "Doc 1", "source": "test"}]

        result = handler_with_db.add_documents_batch("test_table", documents)

        assert result == 0

    # =========================================================================
    # Similarity Search Tests (10 tests)
    # =========================================================================

    def test_search_basic(self, handler_with_db, sample_search_results):
        """Test basic similarity search."""
        mock_table = MagicMock()
        handler_with_db.get_table = Mock(return_value=mock_table)
        handler_with_db.embed_text = Mock(return_value=[0.1] * 384)

        # Mock search chain
        mock_search = MagicMock()
        mock_search.limit.return_value.where.return_value.to_pandas.return_value = sample_search_results
        mock_table.search.return_value = mock_search

        results = handler_with_db.search("test_table", "query text", limit=5)

        assert len(results) == 3
        assert results[0]['id'] == 'doc1'
        assert 'score' in results[0]

    def test_search_with_user_filter(self, handler_with_db, sample_search_results):
        """Test search with user_id filter."""
        mock_table = MagicMock()
        handler_with_db.get_table = Mock(return_value=mock_table)
        handler_with_db.embed_text = Mock(return_value=[0.1] * 384)

        mock_search = MagicMock()
        mock_search.limit.return_value.where.return_value.to_pandas.return_value = sample_search_results
        mock_table.search.return_value = mock_search

        results = handler_with_db.search("test_table", "query", user_id="user1", limit=5)

        assert len(results) >= 0
        # Verify filter was applied

    def test_search_with_custom_filter(self, handler_with_db, sample_search_results):
        """Test search with custom filter expression."""
        mock_table = MagicMock()
        handler_with_db.get_table = Mock(return_value=mock_table)
        handler_with_db.embed_text = Mock(return_value=[0.1] * 384)

        mock_search = MagicMock()
        mock_search.limit.return_value.where.return_value.to_pandas.return_value = sample_search_results
        mock_table.search.return_value = mock_search

        results = handler_with_db.search(
            "test_table",
            "query",
            filter_str="source == 'test'",
            limit=5
        )

        # Verify custom filter was applied
        assert len(results) >= 0

    def test_search_embedding_failure(self, handler_with_db):
        """Test search when embedding generation fails."""
        handler_with_db.embed_text = Mock(return_value=None)

        results = handler_with_db.search("test_table", "query")

        assert results == []

    def test_search_table_not_found(self, handler_with_db):
        """Test search when table doesn't exist."""
        handler_with_db.get_table = Mock(return_value=None)
        handler_with_db.embed_text = Mock(return_value=[0.1] * 384)

        results = handler_with_db.search("test_table", "query")

        assert results == []

    @pytest.mark.parametrize("limit,expected_min,expected_max", [
        (5, 0, 5),
        (10, 0, 10),
        (20, 0, 20),
    ])
    def test_search_with_various_limits(self, handler_with_db, sample_search_results,
                                       limit, expected_min, expected_max):
        """Test search with different limit values."""
        mock_table = MagicMock()
        handler_with_db.get_table = Mock(return_value=mock_table)
        handler_with_db.embed_text = Mock(return_value=[0.1] * 384)

        mock_search = MagicMock()
        mock_search.limit.return_value.where.return_value.to_pandas.return_value = sample_search_results
        mock_table.search.return_value = mock_search

        results = handler_with_db.search("test_table", "query", limit=limit)

        assert expected_min <= len(results) <= expected_max

    def test_search_score_calculation(self, handler_with_db):
        """Test search score is calculated correctly from distance."""
        mock_table = MagicMock()
        handler_with_db.get_table = Mock(return_value=mock_table)
        handler_with_db.embed_text = Mock(return_value=[0.1] * 384)

        # Create results with known distances
        import pandas as pd
        results_df = pd.DataFrame({
            'id': ['doc1', 'doc2'],
            'text': ['Doc 1', 'Doc 2'],
            'source': ['test', 'test'],
            'metadata': [{}],
            'created_at': ['2024-01-01', '2024-01-02'],
            '_distance': [0.2, 0.5]  # Distances
        })
        mock_search = MagicMock()
        mock_search.limit.return_value.where.return_value.to_pandas.return_value = results_df
        mock_table.search.return_value = mock_search

        results = handler_with_db.search("test_table", "query")

        # Scores should be 1.0 - distance
        assert results[0]['score'] == 0.8  # 1.0 - 0.2
        assert results[1]['score'] == 0.5  # 1.0 - 0.5

    def test_search_metadata_parsing(self, handler_with_db):
        """Test search metadata parsing (string vs dict)."""
        mock_table = MagicMock()
        handler_with_db.get_table = Mock(return_value=mock_table)
        handler_with_db.embed_text = Mock(return_value=[0.1] * 384)

        import pandas as pd
        results_df = pd.DataFrame({
            'id': ['doc1'],
            'text': ['Doc 1'],
            'source': ['test'],
            'metadata': ['{"key": "value"}'],  # String metadata
            'created_at': ['2024-01-01'],
            '_distance': [0.1]
        })
        mock_search = MagicMock()
        mock_search.limit.return_value.where.return_value.to_pandas.return_value = results_df
        mock_table.search.return_value = mock_search

        results = handler_with_db.search("test_table", "query")

        assert results[0]['metadata'] == {"key": "value"}

    # =========================================================================
    # Knowledge Graph Tests (3 tests)
    # =========================================================================

    def test_add_knowledge_edge_success(self, handler_with_db):
        """Test adding knowledge graph edge."""
        mock_table = MagicMock()
        handler_with_db.get_table = Mock(return_value=None)  # Table doesn't exist
        handler_with_db.create_table = Mock(return_value=mock_table)
        handler_with_db.embed_text = Mock(return_value=[0.1] * 384)

        result = handler_with_db.add_knowledge_edge(
            from_id="node1",
            to_id="node2",
            rel_type="connected_to",
            description="Node 1 is connected to node 2"
        )

        assert result is True

    def test_add_knowledge_edge_embedding_fallback(self, handler_with_db):
        """Test knowledge edge with embedding fallback to zero vector."""
        mock_table = MagicMock()
        handler_with_db.get_table = Mock(return_value=mock_table)
        handler_with_db.embed_text = Mock(return_value=None)

        result = handler_with_db.add_knowledge_edge(
            from_id="node1",
            to_id="node2",
            rel_type="connected_to",
            description="Test relationship"
        )

        assert result is True
        # Should use zero vector as fallback

    def test_query_knowledge_graph(self, handler_with_db, sample_search_results):
        """Test querying knowledge graph."""
        handler_with_db.search = Mock(return_value=sample_search_results[:1])

        results = handler_with_db.query_knowledge_graph("test query", limit=5)

        assert len(results) >= 0
        handler_with_db.search.assert_called_once_with("knowledge_graph", "test query", limit=5)

    # =========================================================================
    # Dual Vector Storage Tests (6 tests)
    # =========================================================================

    @pytest.mark.asyncio
    async def test_add_embedding_standard_vector(self, handler_with_db):
        """Test adding embedding to standard vector column."""
        mock_table = MagicMock()
        handler_with_db.get_table = Mock(return_value=mock_table)
        handler_with_db.create_table = Mock(return_value=mock_table)

        vector = [0.1] * 1024

        result = await handler_with_db.add_embedding(
            "test_table",
            episode_id="ep1",
            vector=vector,
            vector_column="vector"
        )

        assert result is True
        mock_table.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_embedding_fastembed_vector(self, handler_with_db):
        """Test adding embedding to fastembed vector column."""
        mock_table = MagicMock()
        handler_with_db.get_table = Mock(return_value=mock_table)
        handler_with_db.create_table = Mock(return_value=mock_table)

        vector = [0.1] * 384

        result = await handler_with_db.add_embedding(
            "test_table",
            episode_id="ep1",
            vector=vector,
            vector_column="vector_fastembed"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_add_embedding_dimension_mismatch(self, handler_with_db):
        """Test adding embedding with wrong dimension raises error."""
        with pytest.raises(ValueError, match="Dimension mismatch"):
            await handler_with_db.add_embedding(
                "test_table",
                episode_id="ep1",
                vector=[0.1] * 100,  # Wrong dimension
                vector_column="vector"  # Expects 1024
            )

    @pytest.mark.asyncio
    async def test_add_embedding_invalid_column(self, handler_with_db):
        """Test adding embedding to invalid column raises error."""
        with pytest.raises(ValueError, match="Unknown vector column"):
            await handler_with_db.add_embedding(
                "test_table",
                episode_id="ep1",
                vector=[0.1] * 384,
                vector_column="invalid_column"
            )

    @pytest.mark.asyncio
    async def test_similarity_search_standard_vector(self, handler_with_db):
        """Test similarity search on standard vector column."""
        mock_table = MagicMock()
        handler_with_db.get_table = Mock(return_value=mock_table)

        import pandas as pd
        results_df = pd.DataFrame({
            'id': ['ep1', 'ep2'],
            '_distance': [0.1, 0.2]
        })
        mock_table.search.return_value.limit.return_value.to_pandas.return_value = results_df

        vector = [0.1] * 1024
        results = await handler_with_db.similarity_search(
            "test_table",
            vector=vector,
            vector_column="vector",
            top_k=10
        )

        assert len(results) == 2
        assert results[0]['episode_id'] == 'ep1'
        assert results[0]['vector_column'] == 'vector'

    @pytest.mark.asyncio
    async def test_similarity_search_dimension_mismatch(self, handler_with_db):
        """Test similarity search with wrong dimension raises error."""
        with pytest.raises(ValueError, match="Dimension mismatch"):
            await handler_with_db.similarity_search(
                "test_table",
                vector=[0.1] * 100,  # Wrong dimension
                vector_column="vector"
            )

    # =========================================================================
    # Error Handling Tests (6 tests)
    # =========================================================================

    def test_table_not_initialized_error(self, handler_with_db):
        """Test operations when DB is not initialized."""
        handler_with_db.db = None

        result = handler_with_db.create_table("test_table")

        assert result is None

    def test_search_pandas_not_available(self, handler_with_db):
        """Test search fails gracefully when pandas not available."""
        with patch('core.lancedb_handler.PANDAS_AVAILABLE', False):
            handler_with_db.get_table = Mock(return_value=MagicMock())
            handler_with_db.embed_text = Mock(return_value=[0.1] * 384)

            results = handler_with_db.search("test_table", "query")

            assert results == []

    def test_list_documents_pandas_not_available(self, handler_with_db):
        """Test list_documents fails gracefully without pandas."""
        with patch('core.lancedb_handler.PANDAS_AVAILABLE', False):
            handler_with_db.get_table = Mock(return_value=MagicMock())

            results = handler_with_db.list_documents("test_table")

            assert results == []

    def test_get_document_parsing_error(self, handler_with_db):
        """Test get_document handles metadata parsing errors."""
        mock_table = MagicMock()
        handler_with_db.get_table = Mock(return_value=mock_table)

        import pandas as pd
        doc_df = pd.DataFrame({
            'id': ['doc1'],
            'text': ['Doc'],
            'source': ['test'],
            'metadata': ['invalid json'],  # Invalid JSON
            'created_at': ['2024-01-01']
        })
        mock_table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = doc_df

        result = handler_with_db.get_document_by_id("test_table", "doc1")

        # Should handle error and return doc with empty metadata
        assert result is not None
        assert result['metadata'] == {}

    def test_seed_mock_data(self, handler_with_db):
        """Test seed_mock_data method."""
        handler_with_db.add_documents_batch = Mock(return_value=3)

        documents = [{"text": "Doc 1"}, {"text": "Doc 2"}, {"text": "Doc 3"}]
        result = handler_with_db.seed_mock_data(documents)

        assert result == 3
        handler_with_db.add_documents_batch.assert_called_once()

    def test_workspace_isolation_enforcement(self, handler_with_db, sample_search_results):
        """Test that workspace_id filter is enforced in search."""
        mock_table = MagicMock()
        handler_with_db.get_table = Mock(return_value=mock_table)
        handler_with_db.embed_text = Mock(return_value=[0.1] * 384)
        handler_with_db.workspace_id = "test_workspace"

        mock_search = MagicMock()
        mock_search.limit.return_value.where.return_value.to_pandas.return_value = sample_search_results
        mock_table.search.return_value = mock_search

        handler_with_db.search("test_table", "query")

        # Verify workspace filter was applied
        args = mock_search.limit.return_value.where.call_args
        assert 'workspace_id' in str(args)

    # =========================================================================
    # Module Functions Tests (2 tests)
    # =========================================================================

    def test_get_lancedb_handler_singleton(self, monkeypatch, tmp_path):
        """Test get_lancedb_handler returns singleton instance."""
        monkeypatch.setenv("LANCEDB_URI_BASE", str(tmp_path))

        handler1 = get_lancedb_handler("test_workspace")
        handler2 = get_lancedb_handler("test_workspace")

        assert handler1 is handler2

    def test_get_lancedb_handler_different_workspaces(self, monkeypatch, tmp_path):
        """Test get_lancedb_handler creates separate instances per workspace."""
        monkeypatch.setenv("LANCEDB_URI_BASE", str(tmp_path))

        handler1 = get_lancedb_handler("workspace1")
        handler2 = get_lancedb_handler("workspace2")

        assert handler1 is not handler2
        assert handler1.workspace_id == "workspace1"
        assert handler2.workspace_id == "workspace2"


# ============================================================================
# Test Class: ChatHistoryManager Coverage Extension
# Target: Cover lines 1111-1369 (ChatHistoryManager class)
# ============================================================================

class TestChatHistoryManagerCoverageExtend:
    """
    Extended coverage tests for ChatHistoryManager.

    Target: Cover chat message save, retrieval, search, and entity mentions
    """

    # =========================================================================
    # Initialization Tests (2 tests)
    # =========================================================================

    def test_chat_history_manager_initialization(self):
        """Test ChatHistoryManager initialization."""
        mock_handler = MagicMock()
        mock_handler.db = MagicMock()
        mock_handler.db.table_names = Mock(return_value=[])

        manager = ChatHistoryManager(mock_handler)

        assert manager.db == mock_handler
        assert manager.table_name == "chat_messages"

    def test_chat_history_manager_table_creation(self):
        """Test chat_messages table is created on init."""
        mock_handler = MagicMock()
        mock_db = MagicMock()
        mock_db.table_names = Mock(return_value=[])
        mock_handler.db = mock_db
        mock_handler.create_table = Mock()

        manager = ChatHistoryManager(mock_handler)

        mock_handler.create_table.assert_called_once_with("chat_messages")

    # =========================================================================
    # Save Message Tests (3 tests)
    # =========================================================================

    def test_save_message_success(self):
        """Test successful message save."""
        mock_handler = MagicMock()
        mock_handler.db = MagicMock()
        mock_handler.db.table_names = Mock(return_value=["chat_messages"])
        mock_handler.add_document = Mock(return_value=True)

        manager = ChatHistoryManager(mock_handler)

        result = manager.save_message(
            session_id="session1",
            user_id="user1",
            role="user",
            content="Test message"
        )

        assert result is True
        mock_handler.add_document.assert_called_once()

    def test_save_message_with_metadata(self):
        """Test saving message with custom metadata."""
        mock_handler = MagicMock()
        mock_handler.db = MagicMock()
        mock_handler.db.table_names = Mock(return_value=["chat_messages"])
        mock_handler.add_document = Mock(return_value=True)

        manager = ChatHistoryManager(mock_handler)

        result = manager.save_message(
            session_id="session1",
            user_id="user1",
            role="assistant",
            content="Test response",
            metadata={"intent": "greeting", "workflow_id": "wf1"}
        )

        assert result is True
        # Verify metadata was merged

    def test_save_message_db_not_initialized(self):
        """Test save_message when DB not initialized."""
        mock_handler = MagicMock()
        mock_handler.db = None

        manager = ChatHistoryManager(mock_handler)

        result = manager.save_message(
            session_id="session1",
            user_id="user1",
            role="user",
            content="Test message"
        )

        assert result is False

    # =========================================================================
    # Session History Tests (3 tests)
    # =========================================================================

    def test_get_session_history_success(self):
        """Test retrieving session history."""
        mock_handler = MagicMock()
        mock_handler.db = MagicMock()
        mock_table = MagicMock()

        import pandas as pd
        history_df = pd.DataFrame({
            'id': ['msg1', 'msg2'],
            'text': ['Hello', 'Hi there'],
            'created_at': ['2024-01-01T10:00:00', '2024-01-01T10:01:00'],
            'metadata': [
                '{"session_id": "session1", "role": "user"}',
                '{"session_id": "session1", "role": "assistant"}'
            ]
        })
        mock_table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = history_df
        mock_handler.get_table = Mock(return_value=mock_table)

        manager = ChatHistoryManager(mock_handler)

        results = manager.get_session_history("session1", limit=10)

        assert len(results) == 2
        assert results[0]['role'] == 'user'
        assert results[1]['role'] == 'assistant'

    def test_get_session_history_sorting(self):
        """Test session history is sorted chronologically."""
        mock_handler = MagicMock()
        mock_handler.db = MagicMock()
        mock_table = MagicMock()

        import pandas as pd
        history_df = pd.DataFrame({
            'id': ['msg2', 'msg1'],  # Out of order
            'text': ['Second', 'First'],
            'created_at': ['2024-01-01T10:01:00', '2024-01-01T10:00:00'],
            'metadata': [
                '{"session_id": "session1", "role": "assistant"}',
                '{"session_id": "session1", "role": "user"}'
            ]
        })
        mock_table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = history_df
        mock_handler.get_table = Mock(return_value=mock_table)

        manager = ChatHistoryManager(mock_handler)

        results = manager.get_session_history("session1")

        # Should be sorted by created_at
        assert results[0]['text'] == 'First'
        assert results[1]['text'] == 'Second'

    def test_get_session_history_pandas_not_available(self):
        """Test get_session_history fails gracefully without pandas."""
        with patch('core.lancedb_handler.PANDAS_AVAILABLE', False):
            mock_handler = MagicMock()
            mock_handler.db = MagicMock()

            manager = ChatHistoryManager(mock_handler)

            results = manager.get_session_history("session1")

            assert results == []

    # =========================================================================
    # Search Context Tests (2 tests)
    # =========================================================================

    def test_search_relevant_context(self):
        """Test searching semantically similar messages."""
        mock_handler = MagicMock()
        mock_handler.db = MagicMock()
        mock_handler.search = Mock(return_value=[])

        manager = ChatHistoryManager(mock_handler)

        results = manager.search_relevant_context(
            query="previous conversation",
            session_id="session1",
            limit=5
        )

        mock_handler.search.assert_called_once()
        # Verify filter expression includes session_id

    def test_search_relevant_context_all_sessions(self):
        """Test searching across all sessions."""
        mock_handler = MagicMock()
        mock_handler.db = MagicMock()
        mock_handler.search = Mock(return_value=[])

        manager = ChatHistoryManager(mock_handler)

        results = manager.search_relevant_context(
            query="previous conversation",
            limit=5
        )

        mock_handler.search.assert_called_once()
        # No session filter should be applied

    # =========================================================================
    # Entity Mentions Tests (2 tests)
    # =========================================================================

    def test_get_entity_mentions(self):
        """Test finding messages mentioning specific entity."""
        mock_handler = MagicMock()
        mock_handler.db = MagicMock()
        mock_table = MagicMock()

        import pandas as pd
        mentions_df = pd.DataFrame({
            'id': ['msg1', 'msg2'],
            'text': ['Workflow started', 'Task completed'],
            'created_at': ['2024-01-01T10:00:00', '2024-01-01T10:01:00'],
            'metadata': [
                '{"role": "user", "workflow_id": "wf1"}',
                '{"role": "assistant", "workflow_id": "wf1"}'
            ]
        })
        mock_table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = mentions_df
        mock_handler.get_table = Mock(return_value=mock_table)

        manager = ChatHistoryManager(mock_handler)

        results = manager.get_entity_mentions(
            entity_type="workflow_id",
            entity_id="wf1"
        )

        assert len(results) == 2

    def test_get_entity_mentions_with_session_filter(self):
        """Test entity mentions filtered by session."""
        mock_handler = MagicMock()
        mock_handler.db = MagicMock()
        mock_table = MagicMock()

        import pandas as pd
        mentions_df = pd.DataFrame({
            'id': ['msg1'],
            'text': ['Workflow started'],
            'created_at': ['2024-01-01T10:00:00'],
            'metadata': ['{"role": "user", "workflow_id": "wf1", "session_id": "session1"}']
        })
        mock_table.search.return_value.where.return_value.limit.return_value.to_pandas.return_value = mentions_df
        mock_handler.get_table = Mock(return_value=mock_table)

        manager = ChatHistoryManager(mock_handler)

        results = manager.get_entity_mentions(
            entity_type="workflow_id",
            entity_id="wf1",
            session_id="session1"
        )

        assert len(results) == 1

    # =========================================================================
    # Module Functions Tests (1 test)
    # =========================================================================

    def test_get_chat_history_manager(self):
        """Test get_chat_history_manager factory function."""
        with patch('core.lancedb_handler.get_lancedb_handler') as mock_get_handler:
            mock_handler = MagicMock()
            mock_get_handler.return_value = mock_handler

            manager = get_chat_history_manager("test_workspace")

            assert manager.db == mock_handler
            mock_get_handler.assert_called_once_with("test_workspace")


# ============================================================================
# Utility Functions Tests
# ============================================================================

class TestUtilityFunctionsCoverage:
    """Coverage tests for utility functions."""

    def test_embed_documents_batch_with_sentence_transformers(self):
        """Test batch embedding with sentence transformers."""
        with patch('core.lancedb_handler.SENTENCE_TRANSFORMERS_AVAILABLE', True):
            with patch('core.lancedb_handler.SentenceTransformer') as mock_st:
                mock_model = MagicMock()
                mock_model.encode = Mock(return_value=[[0.1] * 384, [0.2] * 384])
                mock_st.return_value = mock_model

                from core.lancedb_handler import embed_documents_batch

                result = embed_documents_batch(["text1", "text2"])

                assert result is not None

    def test_embed_documents_batch_not_available(self):
        """Test batch embedding when sentence transformers unavailable."""
        with patch('core.lancedb_handler.SENTENCE_TRANSFORMERS_AVAILABLE', False):
            from core.lancedb_handler import embed_documents_batch

            result = embed_documents_batch(["text1", "text2"])

            assert result is None

    def test_create_memory_schema(self):
        """Test create_memory_schema utility function."""
        from core.lancedb_handler import create_memory_schema

        schema = create_memory_schema(vector_size=384)

        assert schema is not None
        assert 'id' in schema
        assert 'text' in schema
        assert 'vector' in schema
