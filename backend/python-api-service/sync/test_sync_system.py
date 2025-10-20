"""
Test file for LanceDB Sync System

This module provides comprehensive tests for the LanceDB sync system components.
"""

import os
import sys
import asyncio
import tempfile
import pytest
from unittest.mock import Mock, patch, AsyncMock
import json
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sync.incremental_sync_service import (
    IncrementalSyncService,
    SyncConfig,
    ChangeRecord,
)
from sync.source_change_detector import (
    SourceChangeDetector,
    SourceConfig,
    SourceChange,
    SourceType,
    ChangeType,
)
from sync.orchestration_service import OrchestrationService, OrchestrationConfig
from sync import LanceDBSyncConfig


class TestIncrementalSyncService:
    """Test IncrementalSyncService functionality"""

    @pytest.fixture
    def sync_config(self):
        """Create a test sync configuration"""
        return SyncConfig(
            local_db_path=":memory:",  # Use in-memory database for testing
            s3_bucket=None,  # Disable S3 for tests
            sync_interval=10,
            max_retries=2,
        )

    @pytest.fixture
    def sync_service(self, sync_config):
        """Create a test sync service instance"""
        with patch("sync.incremental_sync_service.lancedb"):
            with patch("sync.incremental_sync_service.boto3"):
                service = IncrementalSyncService(sync_config)
                # Mock the local database
                service.local_db = Mock()
                service.local_db.table_names.return_value = []
                service.local_db.open_table.return_value = Mock()
                return service

    @pytest.mark.asyncio
    async def test_process_document_incrementally_new(self, sync_service):
        """Test processing a new document"""
        # Mock document data
        document_data = {
            "doc_id": "test_doc_1",
            "doc_type": "pdf",
            "title": "Test Document",
            "metadata": {"author": "test"},
        }

        chunks_with_embeddings = [
            {
                "text_content": "Test content",
                "embedding": [0.1] * 1536,
                "metadata": {"chunk_index": 0},
            }
        ]

        # Mock existing document check to return None (new document)
        sync_service._get_existing_document = AsyncMock(return_value=None)
        sync_service._store_in_local_db = AsyncMock(return_value={"status": "success"})
        sync_service._sync_to_s3 = AsyncMock()

        result = await sync_service.process_document_incrementally(
            user_id="test_user",
            source_uri="file:///test.pdf",
            document_data=document_data,
            chunks_with_embeddings=chunks_with_embeddings,
        )

        assert result["status"] == "success"
        assert result["local_stored"] == True
        assert result["remote_sync_queued"] == True
        sync_service._store_in_local_db.assert_called_once()
        sync_service._sync_to_s3.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_document_incrementally_unchanged(self, sync_service):
        """Test processing an unchanged document"""
        document_data = {
            "doc_id": "test_doc_1",
            "doc_type": "pdf",
            "title": "Test Document",
        }

        chunks_with_embeddings = [
            {
                "text_content": "Test content",
                "embedding": [0.1] * 1536,
            }
        ]

        # Mock existing document with same checksum
        existing_doc = {
            "doc_id": "test_doc_1",
            "checksum": sync_service._generate_checksum(
                document_data, chunks_with_embeddings
            ),
        }
        sync_service._get_existing_document = AsyncMock(return_value=existing_doc)

        result = await sync_service.process_document_incrementally(
            user_id="test_user",
            source_uri="file:///test.pdf",
            document_data=document_data,
            chunks_with_embeddings=chunks_with_embeddings,
        )

        assert result["status"] == "skipped"
        assert "unchanged" in result["message"].lower()

    def test_generate_checksum(self, sync_service):
        """Test checksum generation for change detection"""
        test_data = {"key": "value", "number": 42}
        checksum1 = sync_service._generate_checksum(test_data)
        checksum2 = sync_service._generate_checksum(test_data)

        # Same data should produce same checksum
        assert checksum1 == checksum2

        # Different data should produce different checksum
        test_data2 = {"key": "different_value", "number": 42}
        checksum3 = sync_service._generate_checksum(test_data2)
        assert checksum1 != checksum3


class TestSourceChangeDetector:
    """Test SourceChangeDetector functionality"""

    @pytest.fixture
    def change_detector(self):
        """Create a test change detector"""
        with tempfile.TemporaryDirectory() as temp_dir:
            detector = SourceChangeDetector(state_dir=temp_dir)
            return detector

    def test_add_remove_source(self, change_detector):
        """Test adding and removing sources"""
        config = SourceConfig(
            source_type=SourceType.LOCAL_FILESYSTEM,
            source_id="test_source",
            config={"watch_paths": ["/test/path"]},
        )

        # Add source
        change_detector.add_source(config)
        assert "local_filesystem_test_source" in change_detector.sources

        # Remove source
        change_detector.remove_source(SourceType.LOCAL_FILESYSTEM, "test_source")
        assert "local_filesystem_test_source" not in change_detector.sources

    def test_add_change_handler(self, change_detector):
        """Test adding change handlers"""
        handler_called = False

        def test_handler(change):
            nonlocal handler_called
            handler_called = True

        change_detector.add_change_handler(test_handler)
        assert len(change_detector.change_handlers) == 1

        # Test handler is called
        test_change = SourceChange(
            source_type=SourceType.LOCAL_FILESYSTEM,
            source_id="test",
            item_id="test_item",
            item_path="/test/path",
            change_type=ChangeType.CREATED,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata={},
        )

        change_detector._handle_change(test_change)
        assert handler_called

    @pytest.mark.asyncio
    async def test_detect_local_filesystem_changes(self, change_detector):
        """Test local filesystem change detection"""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test file
            test_file = os.path.join(temp_dir, "test.txt")
            with open(test_file, "w") as f:
                f.write("Test content")

            config = SourceConfig(
                source_type=SourceType.LOCAL_FILESYSTEM,
                source_id="test",
                config={"watch_paths": [temp_dir], "file_patterns": ["*.txt"]},
            )

            changes = await change_detector._detect_local_filesystem_changes(config)

            # Should detect the created file
            assert len(changes) == 1
            change = changes[0]
            assert change.change_type == ChangeType.CREATED
            assert change.item_path == test_file


class TestOrchestrationService:
    """Test OrchestrationService functionality"""

    @pytest.fixture
    def orchestration_config(self):
        """Create test orchestration configuration"""
        return OrchestrationConfig(
            local_db_path=":memory:",
            s3_bucket=None,
            enable_source_monitoring=False,  # Disable for simpler tests
        )

    @pytest.fixture
    def orchestration_service(self, orchestration_config):
        """Create test orchestration service"""
        with patch("sync.orchestration_service.IncrementalSyncService"):
            with patch("sync.orchestration_service.SourceChangeDetector"):
                service = OrchestrationService(orchestration_config)
                service.sync_service = Mock()
                service.change_detector = None  # Disabled in config
                return service

    @pytest.mark.asyncio
    async def test_start_stop_service(self, orchestration_service):
        """Test starting and stopping the service"""
        # Mock sync service methods
        orchestration_service.sync_service.get_sync_status = AsyncMock(
            return_value={
                "local_db_available": True,
                "s3_sync_available": False,
                "pending_syncs": 0,
                "failed_syncs": 0,
            }
        )

        await orchestration_service.start()
        assert orchestration_service.running == True

        await orchestration_service.stop()
        assert orchestration_service.running == False

    @pytest.mark.asyncio
    async def test_get_system_status(self, orchestration_service):
        """Test system status reporting"""
        orchestration_service.running = True

        # Mock sync service status
        orchestration_service.sync_service.get_sync_status = AsyncMock(
            return_value={
                "local_db_available": True,
                "s3_sync_available": False,
                "pending_syncs": 0,
                "failed_syncs": 0,
                "total_changes": 0,
            }
        )

        status = await orchestration_service.get_system_status()

        assert status["service_running"] == True
        assert "config" in status
        assert "sync_service" in status


class TestConfiguration:
    """Test configuration management"""

    def test_config_from_env(self):
        """Test configuration creation from environment variables"""
        with patch.dict(
            os.environ,
            {
                "LANCEDB_URI": "/test/path",
                "S3_BUCKET": "test-bucket",
                "SYNC_INTERVAL": "60",
            },
        ):
            config = LanceDBSyncConfig.from_env()

            assert config.local_db_path == "/test/path"
            assert config.s3_bucket == "test-bucket"
            assert config.sync_interval == 60

    def test_config_validation(self):
        """Test configuration validation"""
        # Valid configuration
        valid_config = LanceDBSyncConfig(
            local_db_path="/test/path",
            s3_bucket="valid-bucket",
            sync_interval=300,
        )
        assert valid_config.validate() == True

        # Invalid configuration
        invalid_config = LanceDBSyncConfig(
            local_db_path="",  # Empty path
            sync_interval=-1,  # Negative interval
        )
        assert invalid_config.validate() == False


@pytest.mark.asyncio
async def test_integration_workflow():
    """Test complete integration workflow"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test configuration
        config = LanceDBSyncConfig(
            local_db_path=os.path.join(temp_dir, "test_db"),
            s3_bucket=None,  # Disable S3 for test
            enable_source_monitoring=False,
        )

        # Mock components for integration test
        with patch("sync.incremental_sync_service.lancedb") as mock_lancedb:
            with patch("sync.incremental_sync_service.boto3"):
                # Create mock database
                mock_db = Mock()
                mock_lancedb.connect.return_value = mock_db
                mock_db.table_names.return_value = []
                mock_db.open_table.return_value = Mock()

                # Test document processing
                from sync.incremental_sync_service import IncrementalSyncService

                sync_service = IncrementalSyncService(config)

                # Mock the document processing
                sync_service._get_existing_document = AsyncMock(return_value=None)
                sync_service._store_in_local_db = AsyncMock(
                    return_value={"status": "success"}
                )

                document_data = {
                    "doc_id": "integration_test",
                    "doc_type": "test",
                    "title": "Integration Test",
                }

                chunks = [{"text_content": "Test", "embedding": [0.1] * 1536}]

                result = await sync_service.process_document_incrementally(
                    user_id="test_user",
                    source_uri="test://integration",
                    document_data=document_data,
                    chunks_with_embeddings=chunks,
                )

                assert result["status"] == "success"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
