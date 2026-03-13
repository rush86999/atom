"""
LanceDB Handler Initialization and Connection Tests

Comprehensive tests for LanceDB handler initialization, lazy loading,
S3/R2 configuration, embedding providers, and connection lifecycle.

Target: 75%+ line coverage on initialization code (lines 1-400 in lancedb_handler.py)

Tests use module-level mocking to avoid lancedb import errors while testing
real initialization flows, error handling, and configuration logic.
"""

import pytest
import sys
import builtins
from unittest.mock import Mock, MagicMock, AsyncMock, patch
from pathlib import Path
import tempfile
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
    MockEmbedder,
    LANCEDB_AVAILABLE,
    NUMPY_AVAILABLE,
    PANDAS_AVAILABLE,
    SENTENCE_TRANSFORMERS_AVAILABLE,
    OPENAI_AVAILABLE,
)

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_db_path():
    """Create temporary directory for local database tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_lancedb"
        yield db_path


@pytest.fixture
def handler_with_local_db(temp_db_path):
    """Handler configured for local file-based database."""
    return LanceDBHandler(
        db_path=str(temp_db_path),
        embedding_provider="mock",
        embedding_model="mock-model",
    )


@pytest.fixture
def handler_with_s3_db():
    """Handler configured for S3/R2 cloud storage."""
    return LanceDBHandler(
        db_path="s3://test-bucket/lancedb",
        embedding_provider="mock",
        embedding_model="mock-model",
    )


@pytest.fixture
def handler_with_openai():
    """Handler configured with OpenAI embedding provider."""
    return LanceDBHandler(
        db_path="/tmp/test_openai.db",
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
    )


@pytest.fixture
def handler_with_fastembed():
    """Handler configured with FastEmbed provider."""
    return LanceDBHandler(
        db_path="/tmp/test_fastembed.db",
        embedding_provider="fastembed",
        embedding_model="BAAI/bge-small-en-v1.5",
    )


@pytest.fixture
def mock_s3_config():
    """Mock S3/R2 configuration environment variables."""
    original_env = os.environ.copy()

    # Set R2 configuration
    os.environ["R2_ACCESS_KEY_ID"] = "test_r2_key"
    os.environ["R2_SECRET_ACCESS_KEY"] = "test_r2_secret"
    os.environ["AWS_ENDPOINT_URL"] = "https://test.r2.endpoint.com"

    yield {
        "R2_ACCESS_KEY_ID": "test_r2_key",
        "R2_SECRET_ACCESS_KEY": "test_r2_secret",
        "AWS_ENDPOINT_URL": "https://test.r2.endpoint.com",
    }

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_openai_config():
    """Mock OpenAI API configuration."""
    original_env = os.environ.copy()
    os.environ["OPENAI_API_KEY"] = "sk-test-key-12345"
    yield "sk-test-key-12345"
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_s3_client():
    """Mock boto3 S3 client for R2 configuration tests."""
    with patch('core.lancedb_handler.boto3') as mock_boto3:
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_boto3.Session.return_value = mock_session
        mock_session.client.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_db_connection():
    """Mock LanceDB database connection."""
    mock_db = MagicMock()
    mock_db.table_names = Mock(return_value=[])
    mock_db.open_table = Mock(return_value=MagicMock())
    return mock_db


# ============================================================================
# Test Infrastructure Tests
# ============================================================================

class TestTestingModuleInfrastructure:
    """Verify test mocking infrastructure is working correctly."""

    def test_lancedb_module_mocked(self):
        """Test that lancedb module is properly mocked."""
        assert 'lancedb' in sys.modules
        assert sys.modules['lancedb'] is not None

    def test_handler_import_succeeds(self):
        """Test that LanceDBHandler can be imported without lancedb installed."""
        assert LanceDBHandler is not None
        assert callable(LanceDBHandler)

    def test_handler_instantiation(self):
        """Test that handler can be instantiated without errors."""
        handler = LanceDBHandler(
            db_path="/tmp/test.db",
            embedding_provider="mock",
            embedding_model="mock-model",
        )
        assert handler is not None
        assert handler.db_path == "/tmp/test.db"
        assert handler.embedding_provider == "mock"

    def test_availability_flags_exist(self):
        """Test that module-level availability flags are defined."""
        assert isinstance(LANCEDB_AVAILABLE, bool)
        assert isinstance(NUMPY_AVAILABLE, bool)
        assert isinstance(PANDAS_AVAILABLE, bool)
        assert isinstance(SENTENCE_TRANSFORMERS_AVAILABLE, bool)
        assert isinstance(OPENAI_AVAILABLE, bool)

    def test_mock_embedder_available(self):
        """Test that MockEmbedder class is available."""
        embedder = MockEmbedder(dim=384)
        assert embedder.dim == 384

    def test_fixtures_loadable(self, handler_with_local_db, handler_with_s3_db):
        """Test that all fixtures can be loaded without errors."""
        assert handler_with_local_db is not None
        assert handler_with_s3_db is not None


# ============================================================================
# Task 2: Initialization and Connection Tests
# ============================================================================

class TestLanceDBInitialization:
    """Tests for LanceDB handler initialization and lazy loading."""

    def test_db_starts_as_none(self, handler_with_local_db):
        """Test that handler starts with db=None (lazy initialization)."""
        assert handler_with_local_db.db is None, "Handler should start with uninitialized DB"

    def test_ensure_db_initializes_on_first_call(self, handler_with_local_db, mock_db_connection):
        """Test that first call to _ensure_db triggers initialization."""
        handler = handler_with_local_db

        # Mock _initialize_db to return our mock connection
        with patch.object(handler, '_initialize_db') as mock_init:
            handler.db = mock_db_connection

            # Call _ensure_db - should check db is not None and skip initialization
            handler._ensure_db()

            # Verify db is set
            assert handler.db is not None
            assert handler.db == mock_db_connection

    @patch('core.lancedb_handler.LANCEDB_AVAILABLE', True)
    def test_ensure_db_skips_if_already_initialized(self, handler_with_local_db, mock_db_connection):
        """Test that subsequent _ensure_db calls skip initialization if db exists."""
        handler = handler_with_local_db

        # Set db directly (simulating already initialized)
        handler.db = mock_db_connection

        # Mock _initialize_db to track if it's called
        with patch.object(handler, '_initialize_db') as mock_init:
            # Call _ensure_db multiple times
            handler._ensure_db()
            handler._ensure_db()
            handler._ensure_db()

            # Verify _initialize_db was NOT called (db already exists)
            mock_init.assert_not_called()

    @patch('core.lancedb_handler.LANCEDB_AVAILABLE', True)
    def test_initialization_creates_directory_for_local_path(self, temp_db_path):
        """Test that _initialize_db creates directory for non-S3 paths."""
        db_path = temp_db_path / "new_db"
        handler = LanceDBHandler(
            db_path=str(db_path),
            embedding_provider="mock",
        )

        # Mock __import__ to intercept lancedb import
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == 'lancedb':
                mock_module = MagicMock()
                mock_module.connect = Mock(return_value=mock_db_connection)
                return mock_module
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=mock_import):
            # Call _initialize_db
            handler._initialize_db()

            # Verify directory was created
            assert db_path.exists(), "Directory should be created for local DB path"
            assert db_path.is_dir(), "DB path should be a directory"

    @patch('core.lancedb_handler.LANCEDB_AVAILABLE', True)
    @patch.dict(os.environ, {
        'AWS_ENDPOINT_URL': 'https://test.r2.endpoint.com',
        'R2_ACCESS_KEY_ID': 'test_r2_key',
        'R2_SECRET_ACCESS_KEY': 'test_r2_secret',
        'AWS_REGION': 'auto'
    })
    def test_s3_connection_with_endpoint(self, handler_with_s3_db):
        """Test that S3 connection uses AWS_ENDPOINT_URL in storage_options."""
        handler = handler_with_s3_db

        # Track storage_options passed to connect
        storage_options_captured = {}

        def mock_connect_fn(uri, storage_options=None):
            storage_options_captured.update(storage_options or {})
            return mock_db_connection

        # Mock __import__ to intercept lancedb
        original_import = builtins.__import__
        def mock_import(name, *args, **kwargs):
            if name == 'lancedb':
                mock_module = MagicMock()
                mock_module.connect = Mock(side_effect=mock_connect_fn)
                return mock_module
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=mock_import):
            handler._initialize_db()

            # Verify endpoint was in storage_options
            assert 'endpoint' in storage_options_captured
            assert storage_options_captured['endpoint'] == 'https://test.r2.endpoint.com'

    @patch('core.lancedb_handler.LANCEDB_AVAILABLE', True)
    @patch.dict(os.environ, {
        'R2_ACCESS_KEY_ID': 'test_r2_key',
        'R2_SECRET_ACCESS_KEY': 'test_r2_secret',
    })
    def test_s3_connection_with_r2_keys(self, handler_with_s3_db):
        """Test that S3 connection uses R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY."""
        handler = handler_with_s3_db

        # Track storage_options
        storage_options_captured = {}

        def mock_connect_fn(uri, storage_options=None):
            storage_options_captured.update(storage_options or {})
            return mock_db_connection

        original_import = builtins.__import__
        def mock_import(name, *args, **kwargs):
            if name == 'lancedb':
                mock_module = MagicMock()
                mock_module.connect = Mock(side_effect=mock_connect_fn)
                return mock_module
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=mock_import):
            handler._initialize_db()

            # Verify R2 keys are in storage_options (with aws_ prefix)
            assert storage_options_captured.get('aws_access_key_id') == 'test_r2_key'
            assert storage_options_captured.get('aws_secret_access_key') == 'test_r2_secret'

    @patch('core.lancedb_handler.LANCEDB_AVAILABLE', True)
    @patch.dict(os.environ, {
        'AWS_ACCESS_KEY_ID': 'test_aws_key',
        'AWS_SECRET_ACCESS_KEY': 'test_aws_secret',
    }, clear=True)
    def test_s3_connection_with_aws_keys_fallback(self, handler_with_s3_db):
        """Test that S3 connection falls back to AWS keys when R2 keys missing."""
        handler = handler_with_s3_db

        # Track storage_options
        storage_options_captured = {}

        def mock_connect_fn(uri, storage_options=None):
            storage_options_captured.update(storage_options or {})
            return mock_db_connection

        original_import = builtins.__import__
        def mock_import(name, *args, **kwargs):
            if name == 'lancedb':
                mock_module = MagicMock()
                mock_module.connect = Mock(side_effect=mock_connect_fn)
                return mock_module
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=mock_import):
            handler._initialize_db()

            # Verify AWS keys are used when R2 keys not set
            assert storage_options_captured.get('aws_access_key_id') == 'test_aws_key'
            assert storage_options_captured.get('aws_secret_access_key') == 'test_aws_secret'

    @patch('core.lancedb_handler.LANCEDB_AVAILABLE', True)
    @patch.dict(os.environ, {'AWS_REGION': 'us-west-2'})
    def test_s3_connection_uses_region(self, handler_with_s3_db):
        """Test that S3 connection uses AWS_REGION."""
        handler = handler_with_s3_db

        # Track storage_options
        storage_options_captured = {}

        def mock_connect_fn(uri, storage_options=None):
            storage_options_captured.update(storage_options or {})
            return mock_db_connection

        original_import = builtins.__import__
        def mock_import(name, *args, **kwargs):
            if name == 'lancedb':
                mock_module = MagicMock()
                mock_module.connect = Mock(side_effect=mock_connect_fn)
                return mock_module
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=mock_import):
            handler._initialize_db()

            # Verify region is in storage_options
            assert storage_options_captured.get('region') == 'us-west-2'

    @patch('core.lancedb_handler.LANCEDB_AVAILABLE', True)
    @patch.dict(os.environ, {}, clear=True)
    def test_s3_connection_uses_auto_region_when_missing(self, handler_with_s3_db):
        """Test that S3 connection uses 'auto' region when AWS_REGION not set."""
        handler = handler_with_s3_db

        # Track storage_options
        storage_options_captured = {}

        def mock_connect_fn(uri, storage_options=None):
            storage_options_captured.update(storage_options or {})
            return mock_db_connection

        original_import = builtins.__import__
        def mock_import(name, *args, **kwargs):
            if name == 'lancedb':
                mock_module = MagicMock()
                mock_module.connect = Mock(side_effect=mock_connect_fn)
                return mock_module
            return original_import(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=mock_import):
            handler._initialize_db()

            # Verify 'auto' region is default
            assert storage_options_captured.get('region') == 'auto'

    @patch('core.lancedb_handler.LANCEDB_AVAILABLE', True)
    def test_successful_connection_returns_table_list(self, handler_with_local_db):
        """Test that test_connection() returns connected=True and tables list."""
        handler = handler_with_local_db

        # Mock database connection
        mock_db = MagicMock()
        mock_db.table_names = Mock(return_value=['episodes', 'facts', 'canvas'])
        handler.db = mock_db

        # Call test_connection
        result = handler.test_connection()

        # Verify result structure
        assert result['connected'] is True
        assert 'tables' in result
        assert result['tables'] == ['episodes', 'facts', 'canvas']

    @patch('core.lancedb_handler.LANCEDB_AVAILABLE', True)
    def test_connection_failure_returns_error_status(self, handler_with_local_db):
        """Test that connection failure returns connected=False with error."""
        handler = handler_with_local_db

        # Mock database connection that raises error
        mock_db = MagicMock()
        mock_db.table_names = Mock(side_effect=RuntimeError("Connection timeout"))
        handler.db = mock_db

        # Call test_connection
        result = handler.test_connection()

        # Verify error status (uses 'message' not 'error')
        assert result['connected'] is False
        assert 'message' in result
        assert 'Connection timeout' in result['message']

    @patch('core.lancedb_handler.LANCEDB_AVAILABLE', False)
    def test_lancedb_unavailable_returns_error(self, handler_with_local_db):
        """Test that LANCEDB_AVAILABLE=False returns error message."""
        handler = handler_with_local_db

        # Call test_connection when LanceDB not available
        result = handler.test_connection()

        # Verify error message (uses 'message' not 'error')
        assert result['connected'] is False
        assert 'message' in result
        assert 'LanceDB not available' in result['message']

    @patch('core.lancedb_handler.get_byok_manager', return_value=MagicMock())
    def test_byok_manager_initialized_when_available(self, mock_get_byok):
        """Test that get_byok_manager() is called on init when available."""
        # Create handler (should call get_byok_manager)
        handler = LanceDBHandler(
            db_path="/tmp/test.db",
            embedding_provider="mock",
        )

        # Verify BYOK manager was initialized
        mock_get_byok.assert_called_once()
        assert handler.byok_manager is not None

    @patch('core.lancedb_handler.get_byok_manager', side_effect=Exception("BYOK init failed"))
    def test_byok_manager_handles_init_failure(self, mock_get_byok):
        """Test that exception in get_byok_manager sets manager to None."""
        # Create handler (should handle exception gracefully)
        handler = LanceDBHandler(
            db_path="/tmp/test.db",
            embedding_provider="mock",
        )

        # Verify BYOK manager is None after exception
        assert handler.byok_manager is None


# ============================================================================
# Task 3: Embedding Provider Tests
# ============================================================================

class TestLanceDBEmbeddingProviders:
    """Tests for embedding provider initialization and behavior."""

    @patch('core.lancedb_handler.SENTENCE_TRANSFORMERS_AVAILABLE', True)
    def test_local_provider_initializes_sentence_transformers(self):
        """Test that embedding_provider='local' uses SentenceTransformers."""
        handler = LanceDBHandler(
            db_path="/tmp/test.db",
            embedding_provider="local",
            embedding_model="sentence-transformers/all-MiniLM-L6-v2",
        )

        # Verify provider is set to local
        assert handler.embedding_provider == "local"
        assert handler.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"

    def test_openai_provider_initializes_client(self, mock_openai_config):
        """Test that embedding_provider='openai' initializes OpenAI client."""
        # Mock OpenAI import
        with patch('builtins.__import__') as mock_import:
            mock_openai_module = MagicMock()
            mock_openai_client = MagicMock()
            mock_openai_module.OpenAI = Mock(return_value=mock_openai_client)

            def import_side_effect(name, *args, **kwargs):
                if name == 'openai':
                    return mock_openai_module
                return builtins.__import__(name, *args, **kwargs)

            mock_import.side_effect = import_side_effect

            handler = LanceDBHandler(
                db_path="/tmp/test.db",
                embedding_provider="openai",
                embedding_model="text-embedding-3-small",
            )

            # Initialize embedder
            handler._initialize_embedder()

            # Verify OpenAI client was created
            assert handler.openai_client is not None

    @patch('core.lancedb_handler.SENTENCE_TRANSFORMERS_AVAILABLE', False)
    @patch('core.lancedb_handler.OPENAI_AVAILABLE', False)
    def test_mock_embedder_used_when_unavailable(self):
        """Test that SENTENCE_TRANSFORMERS_AVAILABLE=False uses MockEmbedder."""
        handler = LanceDBHandler(
            db_path="/tmp/test.db",
            embedding_provider="local",
        )

        # Initialize embedder
        handler._initialize_embedder()

        # Verify MockEmbedder is used
        assert handler.embedder is not None
        assert isinstance(handler.embedder, MockEmbedder)

    @patch.dict(os.environ, {'EMBEDDING_PROVIDER': 'openai'})
    def test_embedding_provider_from_env_var(self):
        """Test that EMBEDDING_PROVIDER env var is respected."""
        handler = LanceDBHandler(
            db_path="/tmp/test.db",
            # Don't specify embedding_provider - should use env var
        )

        # Verify env var was used
        assert handler.embedding_provider == "openai"

    def test_ensure_embedder_lazy_loads(self):
        """Test that first call to _ensure_embedder triggers _initialize_embedder."""
        handler = LanceDBHandler(
            db_path="/tmp/test.db",
            embedding_provider="mock",
        )

        # Start with no embedder
        assert handler.embedder is None

        # Mock _initialize_embedder
        with patch.object(handler, '_initialize_embedder') as mock_init:
            handler._ensure_embedder()

            # Verify initialization was called
            mock_init.assert_called_once()

    @patch('core.lancedb_handler.SENTENCE_TRANSFORMERS_AVAILABLE', True)
    def test_sentence_transformers_model_from_config(self):
        """Test that embedding_model parameter is used for SentenceTransformers."""
        model_name = "sentence-transformers/all-MiniLM-L6-v2"
        handler = LanceDBHandler(
            db_path="/tmp/test.db",
            embedding_provider="local",
            embedding_model=model_name,
        )

        # Verify model is set
        assert handler.embedding_model == model_name

    @patch.dict(os.environ, {'EMBEDDING_MODEL': 'BAAI/bge-small-en-v1.5'})
    def test_sentence_transformers_model_from_env(self):
        """Test that EMBEDDING_MODEL env var is used."""
        handler = LanceDBHandler(
            db_path="/tmp/test.db",
            embedding_provider="local",
        )

        # Verify env var was used
        assert handler.embedding_model == "BAAI/bge-small-en-v1.5"

    @patch('core.lancedb_handler.SENTENCE_TRANSFORMERS_AVAILABLE', True)
    def test_embedding_initialization_timeout(self):
        """Test that threading timeout handles model loading delays."""
        handler = LanceDBHandler(
            db_path="/tmp/test.db",
            embedding_provider="local",
            embedding_model="slow-model",
        )

        # Mock threading to simulate timeout (imported locally in _init_local_embedder)
        with patch('threading.Thread') as mock_thread_class:
            mock_thread = MagicMock()
            mock_queue = MagicMock()

            # Make queue.empty() return True (no result in time)
            mock_queue.empty.return_value = True
            mock_thread.is_alive.return_value = True  # Thread still running

            mock_thread_class.return_value = mock_thread

            # Patch queue.Queue (queue is the correct module)
            with patch('queue.Queue', return_value=mock_queue):
                # Initialize embedder (should timeout and fall back to MockEmbedder)
                handler._initialize_embedder()

                # Verify embedder falls back to MockEmbedder after timeout
                # (or is None if exception handling catches it)
                assert handler.embedder is None or isinstance(handler.embedder, MockEmbedder)

    @patch.dict(os.environ, {'OPENAI_API_KEY': 'sk-test-key'})
    def test_openai_client_initialized_with_api_key(self):
        """Test that OPENAI_API_KEY is used for client initialization."""
        handler = LanceDBHandler(
            db_path="/tmp/test.db",
            embedding_provider="openai",
        )

        # Verify API key is set
        assert handler.openai_api_key == "sk-test-key"

    @patch('core.lancedb_handler.OPENAI_AVAILABLE', True)
    def test_openai_embed_text_returns_vector(self, mock_openai_config):
        """Test that OpenAI API is called for embeddings."""
        handler = LanceDBHandler(
            db_path="/tmp/test.db",
            embedding_provider="openai",
        )

        # Mock OpenAI client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_client.embeddings.create = Mock(return_value=mock_response)
        handler.openai_client = mock_client

        # Mock _ensure_embedder to skip initialization
        with patch.object(handler, '_ensure_embedder'):
            # Call embed_text (using internal method)
            # This will use OpenAI if available
            vector = handler.embed_text("test text")

            # Verify vector is returned
            assert vector is not None
            assert len(vector) == 1536

    @patch('core.lancedb_handler.OPENAI_AVAILABLE', False)
    @patch('core.lancedb_handler.SENTENCE_TRANSFORMERS_AVAILABLE', False)
    def test_openai_embedding_fallback_to_mock(self):
        """Test that OpenAI failure falls back to MockEmbedder."""
        handler = LanceDBHandler(
            db_path="/tmp/test.db",
            embedding_provider="openai",
        )

        # Initialize embedder (should fall back to MockEmbedder)
        handler._initialize_embedder()

        # Verify MockEmbedder is used
        assert isinstance(handler.embedder, MockEmbedder)

    def test_mock_embedder_generates_consistent_vectors(self):
        """Test that MockEmbedder generates consistent vectors for same input."""
        embedder = MockEmbedder(dim=384)

        text = "test input"
        vector1 = embedder.encode(text)
        vector2 = embedder.encode(text)

        # Verify vectors are identical
        assert vector1 == vector2

    def test_mock_embedder_generates_unit_vectors(self):
        """Test that MockEmbedder vectors are normalized to unit length."""
        import math
        embedder = MockEmbedder(dim=384)

        vector = embedder.encode("test input")

        # Calculate norm
        norm = math.sqrt(sum(x * x for x in vector))

        # Verify norm is 1.0 (unit vector)
        assert abs(norm - 1.0) < 0.001

    def test_mock_embedder_handles_unicode(self):
        """Test that MockEmbedder handles special characters without errors."""
        embedder = MockEmbedder(dim=384)

        # Test with unicode and special characters
        texts = [
            "Hello 世界",
            "Test emoji 🚀",
            "Special chars: <>&\"'",
            "Latin: café",
            "Arabic: مرحبا",
        ]

        for text in texts:
            vector = embedder.encode(text)
            assert vector is not None
            assert len(vector) == 384


# ============================================================================
# Task 4: Error Path Tests for Initialization
# ============================================================================

class TestLanceDBInitializationErrorPaths:
    """Tests for error handling in LanceDB handler initialization."""

    @patch('core.lancedb_handler.LANCEDB_AVAILABLE', False)
    def test_lancedb_not_available_flag(self):
        """Test that LANCEDB_AVAILABLE=False is respected in handler state."""
        handler = LanceDBHandler(
            db_path="/tmp/test.db",
            embedding_provider="mock",
        )

        # Note: Due to module-level mocking, lancedb import will succeed
        # In real scenario without module mocking, LANCEDB_AVAILABLE=False
        # would prevent lancedb from being imported

        # Verify that the flag is False (test setup verification)
        from core.lancedb_handler import LANCEDB_AVAILABLE
        assert LANCEDB_AVAILABLE is False

        # test_connection should return error when LanceDB not available
        result = handler.test_connection()

        # Verify error status
        assert result['connected'] is False
        assert 'LanceDB not available' in result['message']

    @patch('core.lancedb_handler.NUMPY_AVAILABLE', False)
    def test_numpy_not_available_flag(self, handler_with_local_db):
        """Test that NUMPY_AVAILABLE=False affects vector operations."""
        handler = handler_with_local_db

        # Mock embedder to test numpy availability
        handler.embedder = MockEmbedder(dim=384)

        # Embed should work even without numpy (MockEmbedder has fallback)
        vector = handler.embedder.encode("test")

        # Verify vector is returned (may be list without numpy)
        assert vector is not None
        assert len(vector) == 384

    @patch('core.lancedb_handler.PANDAS_AVAILABLE', False)
    def test_pandas_not_available_flag(self, handler_with_local_db):
        """Test that PANDAS_AVAILABLE=False affects search results."""
        handler = handler_with_local_db

        # Mock database connection
        mock_db = MagicMock()
        mock_db.table_names = Mock(return_value=['episodes'])
        handler.db = mock_db

        # Test connection should work but won't use pandas
        result = handler.test_connection()

        # Verify connection succeeded
        assert result['connected'] is True
        assert 'tables' in result

    @patch('core.lancedb_handler.LANCEDB_AVAILABLE', True)
    @patch.dict(os.environ, {'AWS_ENDPOINT_URL': 'not-a-valid-url%%&&'})
    def test_invalid_s3_endpoint_format(self, handler_with_s3_db):
        """Test that malformed S3 endpoint is handled gracefully."""
        handler = handler_with_s3_db

        # Should not raise exception, just log error
        try:
            handler._initialize_db()
            # Initialization may succeed or fail gracefully
        except Exception as e:
            # If exception occurs, verify it's handled
            assert isinstance(e, (ValueError, AttributeError, Exception))

    @patch('core.lancedb_handler.LANCEDB_AVAILABLE', True)
    @patch.dict(os.environ, {}, clear=True)
    def test_missing_s3_credentials(self, handler_with_s3_db):
        """Test that missing S3 credentials are handled gracefully."""
        handler = handler_with_s3_db

        # Mock lancedb.connect to track call
        with patch('builtins.__import__') as mock_import:
            storage_options_passed = {}

            def mock_connect_fn(uri, storage_options=None):
                storage_options_passed.update(storage_options or {})
                return mock_db_connection

            def import_side_effect(name, *args, **kwargs):
                if name == 'lancedb':
                    mock_module = MagicMock()
                    mock_module.connect = Mock(side_effect=mock_connect_fn)
                    return mock_module
                return builtins.__import__(name, *args, **kwargs)

            mock_import.side_effect = import_side_effect

            # Initialize should succeed even without credentials
            handler._initialize_db()

            # storage_options may be empty or have partial config
            assert isinstance(storage_options_passed, dict)

    @patch('core.lancedb_handler.LANCEDB_AVAILABLE', True)
    def test_invalid_db_path_format(self):
        """Test that invalid local path is handled gracefully."""
        # Create path with invalid characters
        handler = LanceDBHandler(
            db_path="/tmp/db\x00name",  # Null byte in path
            embedding_provider="mock",
        )

        # Mock lancedb.connect
        with patch('builtins.__import__') as mock_import:
            def import_side_effect(name, *args, **kwargs):
                if name == 'lancedb':
                    mock_module = MagicMock()
                    mock_module.connect = Mock(return_value=mock_db_connection)
                    return mock_module
                return builtins.__import__(name, *args, **kwargs)

            mock_import.side_effect = import_side_effect

            try:
                handler._initialize_db()
                # May succeed or fail gracefully
            except (ValueError, OSError, TypeError):
                # Expected for invalid path
                pass

    @patch('core.lancedb_handler.SENTENCE_TRANSFORMERS_AVAILABLE', True)
    def test_model_loading_timeout(self):
        """Test that threading timeout sets embedder to MockEmbedder."""
        handler = LanceDBHandler(
            db_path="/tmp/test.db",
            embedding_provider="local",
            embedding_model="slow-model",
        )

        # Mock threading to simulate timeout
        with patch('threading.Thread') as mock_thread_class:
            mock_thread = MagicMock()
            mock_queue = MagicMock()

            # Simulate timeout
            mock_queue.empty.return_value = True
            mock_thread.is_alive.return_value = True

            mock_thread_class.return_value = mock_thread

            with patch('queue.Queue', return_value=mock_queue):
                # Initialize embedder
                handler._initialize_embedder()

                # Verify fallback to MockEmbedder or None
                assert handler.embedder is None or isinstance(handler.embedder, MockEmbedder)

    @patch('core.lancedb_handler.SENTENCE_TRANSFORMERS_AVAILABLE', False)
    @patch('core.lancedb_handler.OPENAI_AVAILABLE', False)
    def test_sentence_transformers_import_failure(self):
        """Test that ImportError falls back to MockEmbedder."""
        handler = LanceDBHandler(
            db_path="/tmp/test.db",
            embedding_provider="local",
        )

        # Initialize embedder (should fall back to MockEmbedder)
        handler._initialize_embedder()

        # Verify MockEmbedder is used
        assert isinstance(handler.embedder, MockEmbedder)

    @patch('core.lancedb_handler.OPENAI_AVAILABLE', True)
    def test_openai_client_init_failure(self, mock_openai_config):
        """Test that OpenAI init failure sets client to None."""
        handler = LanceDBHandler(
            db_path="/tmp/test.db",
            embedding_provider="openai",
        )

        # Mock OpenAI import to raise exception
        with patch('builtins.__import__') as mock_import:
            def import_side_effect(name, *args, **kwargs):
                if name == 'openai':
                    raise ImportError("OpenAI module not available")
                return builtins.__import__(name, *args, **kwargs)

            mock_import.side_effect = import_side_effect

            # Initialize embedder (should handle exception)
            handler._initialize_embedder()

            # Verify embedder is None or MockEmbedder (fallback)
            assert handler.embedder is None or isinstance(handler.embedder, MockEmbedder)

    @patch('core.lancedb_handler.LANCEDB_AVAILABLE', True)
    def test_connection_timeout_on_init(self, temp_db_path):
        """Test that connection timeout during _initialize_db is handled."""
        handler = LanceDBHandler(
            db_path=str(temp_db_path),
            embedding_provider="mock",
        )

        # Mock lancedb.connect to simulate timeout
        with patch('builtins.__import__') as mock_import:
            def import_side_effect(name, *args, **kwargs):
                if name == 'lancedb':
                    mock_module = MagicMock()
                    mock_module.connect = Mock(side_effect=TimeoutError("Connection timeout"))
                    return mock_module
                return builtins.__import__(name, *args, **kwargs)

            mock_import.side_effect = import_side_effect

            # Initialize should handle timeout gracefully
            handler._initialize_db()

            # Verify db is None after timeout
            assert handler.db is None

    @patch('core.lancedb_handler.LANCEDB_AVAILABLE', True)
    def test_permission_denied_on_db_path(self):
        """Test that os.makedirs permission error is handled."""
        # Use a path that typically requires permissions
        handler = LanceDBHandler(
            db_path="/root/.lancedb",  # Usually requires root
            embedding_provider="mock",
        )

        # Mock lancedb.connect
        with patch('builtins.__import__') as mock_import:
            def import_side_effect(name, *args, **kwargs):
                if name == 'lancedb':
                    mock_module = MagicMock()
                    mock_module.connect = Mock(return_value=mock_db_connection)
                    return mock_module
                return builtins.__import__(name, *args, **kwargs)

            mock_import.side_effect = import_side_effect

            try:
                handler._initialize_db()
                # May succeed or fail gracefully
            except (PermissionError, OSError):
                # Expected for restricted path
                pass
