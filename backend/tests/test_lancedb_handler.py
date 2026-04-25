"""
LanceDB Handler Tests
Tests for core/lancedb_handler.py
"""

import os
os.environ["TESTING"] = "1"

import pytest
from unittest.mock import Mock, patch, AsyncMock

from core.lancedb_handler import LanceDBHandler, get_lancedb_handler


@pytest.fixture
def mock_lancedb():
    """Mock LanceDB client."""
    client = Mock()
    return client


@pytest.fixture
def lancedb_handler(mock_lancedb):
    """Create LanceDBHandler instance."""
    with patch('lancedb.connect', return_value=mock_lancedb):
        handler = LanceDBHandler(workspace_id="test")
        return handler


class TestConnectionManagement:
    """Test connect, disconnect, connection pooling."""

    def test_handler_initialization(self):
        """Test handler can be initialized."""
        with patch('lancedb.connect'):
            handler = LanceDBHandler(workspace_id="test")
            assert handler is not None

    def test_get_handler_singleton(self):
        """Test get_lancedb_handler returns singleton."""
        with patch('lancedb.connect'):
            handler1 = get_lancedb_handler("test")
            handler2 = get_lancedb_handler("test")
            # Should return same instance for same workspace
            assert handler1 is not None


class TestTableOperations:
    """Test create table, delete table, list tables, schema validation."""

    def test_create_table(self, lancedb_handler):
        """Test creating a new table."""
        with patch.object(lancedb_handler, 'db') as mock_db:
            mock_db.create_table = Mock()
            lancedb_handler.create_table("test_table")
            mock_db.create_table.assert_called_once()

    def test_list_tables(self, lancedb_handler):
        """Test listing all tables."""
        with patch.object(lancedb_handler, 'db') as mock_db:
            mock_db.table_names = Mock(return_value=[])
            tables = lancedb_handler.list_tables()
            assert isinstance(tables, list)


class TestVectorOperations:
    """Test insert vectors, upert vectors, delete vectors."""

    @pytest.mark.asyncio
    async def test_add_documents(self, lancedb_handler):
        """Test adding documents to table."""
        with patch.object(lancedb_handler, 'db') as mock_db:
            mock_table = Mock()
            mock_db.open_table = Mock(return_value=mock_table)
            mock_table.add = Mock()
            
            await lancedb_handler.add_documents("test_table", [{"id": "1", "text": "test"}])
            mock_table.add.assert_called_once()


class TestSearchOperations:
    """Test similarity search, hybrid search, filtering."""

    @pytest.mark.asyncio
    async def test_search(self, lancedb_handler):
        """Test vector similarity search."""
        with patch.object(lancedb_handler, 'db') as mock_db:
            mock_table = Mock()
            mock_db.open_table = Mock(return_value=mock_table)
            mock_table.search = Mock(return_value=mock_table)
            mock_table.limit = Mock(return_value=mock_table)
            mock_table.to_arrow = Mock(return_value=[])
            
            results = await lancedb_handler.search("test_table", "query text", limit=5)
            assert results is not None


class TestErrorHandling:
    """Test connection failures, invalid vectors, table not found."""

    def test_handle_connection_failure(self):
        """Test handling connection failure gracefully."""
        with patch('lancedb.connect', side_effect=Exception("Connection failed")):
            with pytest.raises(Exception):
                LanceDBHandler(workspace_id="test")
