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
