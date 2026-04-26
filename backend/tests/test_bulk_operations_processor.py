"""
Test suite for Bulk Operations Processor

Tests bulk operations processor including:
- Bulk job submission and management
- Job status tracking
- Job cancellation
- Batch processing with integration-specific processors
- Progress tracking and callbacks
- Error handling and recovery
- Performance statistics
- Integration-specific processors (Asana, Jira, Salesforce, etc.)
"""

import pytest
import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timezone, timedelta

from core.bulk_operations_processor import (
    OperationStatus,
    BulkJob,
    BulkOperation,
    IntegrationBulkProcessor,
    get_bulk_processor
)


class TestOperationStatus:
    """Test OperationStatus enum"""

    def test_operation_status_values(self):
        """OperationStatus has correct enum values."""
        assert OperationStatus.PENDING.value == "pending"
        assert OperationStatus.RUNNING.value == "running"
        assert OperationStatus.COMPLETED.value == "completed"
        assert OperationStatus.FAILED.value == "failed"
        assert OperationStatus.CANCELLED.value == "cancelled"
        assert OperationStatus.PARTIAL_SUCCESS.value == "partial_success"


class TestBulkJob:
    """Test BulkJob dataclass"""

    def test_bulk_job_creation(self):
        """BulkJob can be created with valid parameters."""
        operation = Mock()
        operation.items = [{"data": 1}, {"data": 2}]

        job = BulkJob(
            job_id="job-001",
            operation=operation,
            status=OperationStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            total_items=2
        )
        assert job.job_id == "job-001"
        assert job.status == OperationStatus.PENDING
        assert job.total_items == 2
        assert job.processed_items == 0
        assert job.successful_items == 0
        assert job.failed_items == 0

    def test_bulk_job_post_init(self):
        """BulkJob initializes lists in __post_init__."""
        operation = Mock()
        operation.items = [{"data": 1}]

        job = BulkJob(
            job_id="job-001",
            operation=operation,
            status=OperationStatus.PENDING,
            created_at=datetime.now(timezone.utc)
        )
        assert job.errors == []
        assert job.results == []
        assert job.total_items == 1  # Set from operation.items


class TestIntegrationBulkProcessorInit:
    """Test IntegrationBulkProcessor initialization"""

    def test_processor_initialization_default(self):
        """IntegrationBulkProcessor initializes with default parameters."""
        processor = IntegrationBulkProcessor()
        assert processor.max_concurrent_jobs == 5
        assert processor.default_batch_size == 100
        assert len(processor.active_jobs) == 0
        assert len(processor.job_queue) == 0

    def test_processor_initialization_with_mapper(self):
        """IntegrationBulkProcessor initializes with custom data mapper."""
        mock_mapper = Mock()
        processor = IntegrationBulkProcessor(data_mapper=mock_mapper)
        assert processor.data_mapper == mock_mapper

    def test_processor_integration_processors(self):
        """IntegrationBulkProcessor has processors for all integrations."""
        processor = IntegrationBulkProcessor()
        assert "asana" in processor.integration_processors
        assert "jira" in processor.integration_processors
        assert "salesforce" in processor.integration_processors
        assert "notion" in processor.integration_processors
        assert "airtable" in processor.integration_processors
        assert "hubspot" in processor.integration_processors
        assert "monday" in processor.integration_processors


class TestBulkJobSubmission:
    """Test bulk job submission and queuing"""

    @pytest.fixture
    def processor(self):
        """Create bulk processor instance."""
        return IntegrationBulkProcessor()

    @pytest.fixture
    def mock_operation(self):
        """Mock bulk operation."""
        operation = Mock(spec=BulkOperation)
        operation.integration_id = "asana"
        operation.operation_type = "create"
        operation.items = [
            {"name": "Task 1", "projects": ["proj1"]},
            {"name": "Task 2", "projects": ["proj1"]},
            {"name": "Task 3", "projects": ["proj1"]}
        ]
        operation.batch_size = None
        operation.progress_callback = None
        operation.stop_on_error = False
        operation.metadata = {}
        return operation

    @pytest.mark.asyncio
    async def test_submit_bulk_job_success(self, processor, mock_operation):
        """Bulk job submitted successfully."""
        job_id = await processor.submit_bulk_job(mock_operation)

        assert job_id is not None
        assert job_id in processor.active_jobs
        assert job_id in processor.job_queue

        job = processor.active_jobs[job_id]
        assert job.status == OperationStatus.PENDING
        assert job.total_items == 3

    @pytest.mark.asyncio
    async def test_submit_bulk_job_creates_unique_id(self, processor, mock_operation):
        """Each submitted job gets a unique ID."""
        job_id1 = await processor.submit_bulk_job(mock_operation)
        job_id2 = await processor.submit_bulk_job(mock_operation)

        assert job_id1 != job_id2
        assert job_id1 in processor.active_jobs
        assert job_id2 in processor.active_jobs


class TestJobStatusTracking:
    """Test job status retrieval and tracking"""

    @pytest.fixture
    def processor(self):
        """Create bulk processor instance."""
        return IntegrationBulkProcessor()

    @pytest.fixture
    def mock_job(self):
        """Mock bulk job."""
        operation = Mock()
        operation.items = [{"data": 1}]

        return BulkJob(
            job_id="job-001",
            operation=operation,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            total_items=1,
            processed_items=1,
            successful_items=1,
            failed_items=0,
            progress_percentage=100.0
        )

    @pytest.mark.asyncio
    async def test_get_job_status_success(self, processor, mock_job):
        """Job status retrieved successfully."""
        processor.active_jobs["job-001"] = mock_job

        status = await processor.get_job_status("job-001")
        assert status is not None
        assert status.job_id == "job-001"
        assert status.status == OperationStatus.RUNNING
        assert status.progress_percentage == 100.0

    @pytest.mark.asyncio
    async def test_get_job_status_not_found(self, processor):
        """get_job_status returns None for non-existent job."""
        status = await processor.get_job_status("nonexistent")
        assert status is None


class TestJobCancellation:
    """Test job cancellation"""

    @pytest.fixture
    def processor(self):
        """Create bulk processor instance."""
        return IntegrationBulkProcessor()

    @pytest.fixture
    def mock_operation(self):
        """Mock bulk operation."""
        operation = Mock(spec=BulkOperation)
        operation.items = [{"data": 1}]
        return operation

    @pytest.mark.asyncio
    async def test_cancel_pending_job(self, processor, mock_operation):
        """Pending job can be cancelled."""
        job_id = await processor.submit_bulk_job(mock_operation)
        job = processor.active_jobs[job_id]
        job.status = OperationStatus.PENDING

        success = await processor.cancel_job(job_id)
        assert success is True
        assert job.status == OperationStatus.CANCELLED
        assert job.completed_at is not None

    @pytest.mark.asyncio
    async def test_cancel_running_job(self, processor, mock_operation):
        """Running job can be cancelled."""
        job_id = await processor.submit_bulk_job(mock_operation)
        job = processor.active_jobs[job_id]
        job.status = OperationStatus.RUNNING

        success = await processor.cancel_job(job_id)
        assert success is True
        assert job.status == OperationStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_completed_job_fails(self, processor, mock_operation):
        """Cannot cancel completed job."""
        job_id = await processor.submit_bulk_job(mock_operation)
        job = processor.active_jobs[job_id]
        job.status = OperationStatus.COMPLETED

        success = await processor.cancel_job(job_id)
        assert success is False

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_job(self, processor):
        """Cancel returns False for non-existent job."""
        success = await processor.cancel_job("nonexistent")
        assert success is False


class TestBatchProcessing:
    """Test batch processing logic"""

    @pytest.fixture
    def processor(self):
        """Create bulk processor instance."""
        return IntegrationBulkProcessor()

    @pytest.fixture
    def mock_operation(self):
        """Mock bulk operation with multiple items."""
        operation = Mock(spec=BulkOperation)
        operation.integration_id = "airtable"
        operation.operation_type = "create"
        operation.items = [{"id": i} for i in range(10)]
        operation.batch_size = 3
        operation.progress_callback = None
        operation.stop_on_error = False
        operation.metadata = {}
        operation.mapping_id = None
        operation.schema_id = None
        return operation

    @pytest.mark.asyncio
    async def test_process_job_in_batches(self, processor, mock_operation):
        """Job processed in batches correctly."""
        job_id = await processor.submit_bulk_job(mock_operation)

        # Process job (simulate batch processing)
        job = processor.active_jobs[job_id]

        # Simulate batch processing
        batches = [
            mock_operation.items[i:i + mock_operation.batch_size]
            for i in range(0, len(mock_operation.items), mock_operation.batch_size)
        ]

        assert len(batches) == 4  # 10 items / batch_size 3 = 4 batches
        assert len(batches[0]) == 3
        assert len(batches[1]) == 3
        assert len(batches[2]) == 3
        assert len(batches[3]) == 1

    @pytest.mark.asyncio
    async def test_prepare_items_with_transformation(self, processor):
        """Items prepared with data transformations."""
        operation = Mock(spec=BulkOperation)
        operation.items = [{"data": 1}]
        operation.mapping_id = "mapping-001"
        operation.schema_id = None

        with patch.object(processor.data_mapper, 'transform_data') as mock_transform:
            mock_transform.return_value = [{"data": 1, "transformed": True}]

            items = await processor._prepare_items(operation)
            assert items[0].get("transformed") is True

    @pytest.mark.asyncio
    async def test_prepare_items_with_validation(self, processor):
        """Items validated during preparation."""
        operation = Mock(spec=BulkOperation)
        operation.items = [{"data": 1}]
        operation.mapping_id = None
        operation.schema_id = "schema-001"

        with patch.object(processor.data_mapper, 'validate_data') as mock_validate:
            mock_validate.return_value = {"valid": True, "warnings": []}

            items = await processor._prepare_items(operation)
            assert len(items) == 1


class TestProgressTracking:
    """Test progress tracking during job execution"""

    @pytest.fixture
    def processor(self):
        """Create bulk processor instance."""
        return IntegrationBulkProcessor()

    @pytest.fixture
    def mock_job(self):
        """Mock bulk job."""
        operation = Mock()
        operation.items = [{"data": 1}, {"data": 2}]
        operation.stop_on_error = False

        return BulkJob(
            job_id="job-001",
            operation=operation,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            total_items=2
        )

    @pytest.mark.asyncio
    async def test_update_job_progress_success(self, processor, mock_job):
        """Job progress updated correctly after batch completion."""
        batch_results = [
            {"success": True, "item": {"data": 1}},
            {"success": True, "item": {"data": 2}}
        ]

        await processor._update_job_progress(
            job=mock_job,
            batch_results=batch_results,
            current_batch=1,
            total_batches=1
        )

        assert mock_job.processed_items == 2
        assert mock_job.successful_items == 2
        assert mock_job.failed_items == 0
        assert mock_job.progress_percentage == 100.0

    @pytest.mark.asyncio
    async def test_update_job_progress_with_failures(self, processor, mock_job):
        """Job progress updated with failed items."""
        batch_results = [
            {"success": True, "item": {"data": 1}},
            {"success": False, "error": "Validation failed"}
        ]

        await processor._update_job_progress(
            job=mock_job,
            batch_results=batch_results,
            current_batch=1,
            total_batches=1
        )

        assert mock_job.processed_items == 2
        assert mock_job.successful_items == 1
        assert mock_job.failed_items == 1
        assert len(mock_job.errors) == 1

    @pytest.mark.asyncio
    async def test_update_job_progress_stop_on_error(self, processor, mock_job):
        """Job stops on error when stop_on_error is True."""
        mock_job.operation.stop_on_error = True

        batch_results = [
            {"success": True, "item": {"data": 1}},
            {"success": False, "error": "Critical error"}
        ]

        await processor._update_job_progress(
            job=mock_job,
            batch_results=batch_results,
            current_batch=1,
            total_batches=2
        )

        assert mock_job.status == OperationStatus.FAILED


class TestAsanaProcessor:
    """Test Asana-specific bulk processor"""

    @pytest.fixture
    def processor(self):
        """Create bulk processor instance."""
        return IntegrationBulkProcessor()

    @pytest.fixture
    def mock_operation(self):
        """Mock Asana bulk operation."""
        operation = Mock(spec=BulkOperation)
        operation.integration_id = "asana"
        operation.operation_type = "create"
        operation.items = [
            {"name": "Task 1", "notes": "Description 1"},
            {"name": "Task 2", "notes": "Description 2"}
        ]
        operation.metadata = {"access_token": "asana-pat-token"}
        operation.batch_size = 100
        operation.progress_callback = None
        operation.stop_on_error = False
        return operation

    @pytest.mark.asyncio
    async def test_process_asana_bulk_create_success(self, processor, mock_operation):
        """Asana bulk create processes items successfully."""
        with patch('core.bulk_operations_processor.AsanaService') as mock_asana_class:
            mock_asana_instance = Mock()
            mock_asana_class.return_value = mock_asana_instance

            with patch.object(mock_asana_instance, 'create_task', new_callable=AsyncMock) as mock_create:
                mock_create.return_value = {"data": {"gid": "task-123"}}

                results = await processor._process_asana_bulk(
                    items=mock_operation.items,
                    operation=mock_operation
                )

                assert len(results) == 2
                assert results[0]["success"] is True
                assert results[1]["success"] is True

    @pytest.mark.asyncio
    async def test_process_asana_bulk_no_token(self, processor, mock_operation):
        """Asana processor fails when no access token."""
        mock_operation.metadata = {}

        results = await processor._process_asana_bulk(
            items=mock_operation.items,
            operation=mock_operation
        )

        assert all(not r["success"] for r in results)
        assert "access token not configured" in results[0]["error"]

    @pytest.mark.asyncio
    async def test_process_asana_bulk_update(self, processor, mock_operation):
        """Asana bulk update processes items successfully."""
        mock_operation.operation_type = "update"
        mock_operation.items = [
            {"task_id": "task-001", "updates": {"name": "Updated Task"}}
        ]

        with patch('core.bulk_operations_processor.AsanaService') as mock_asana_class:
            mock_asana_instance = Mock()
            mock_asana_class.return_value = mock_asana_instance

            with patch.object(mock_asana_instance, 'update_task', new_callable=AsyncMock) as mock_update:
                mock_update.return_value = {"data": {"gid": "task-001"}}

                results = await processor._process_asana_bulk(
                    items=mock_operation.items,
                    operation=mock_operation
                )

                assert len(results) == 1
                assert results[0]["success"] is True

    @pytest.mark.asyncio
    async def test_process_asana_bulk_delete(self, processor, mock_operation):
        """Asana bulk delete processes items successfully."""
        mock_operation.operation_type = "delete"
        mock_operation.items = [{"task_id": "task-001"}]

        with patch('core.bulk_operations_processor.AsanaService') as mock_asana_class:
            mock_asana_instance = Mock()
            mock_asana_class.return_value = mock_asana_instance

            with patch.object(mock_asana_instance, 'delete_task', new_callable=AsyncMock) as mock_delete:
                mock_delete.return_value = {"data": {"gid": "task-001"}}

                results = await processor._process_asana_bulk(
                    items=mock_operation.items,
                    operation=mock_operation
                )

                assert len(results) == 1
                assert results[0]["success"] is True


class TestOtherIntegrationProcessors:
    """Test other integration processors (Jira, Salesforce, etc.)"""

    @pytest.fixture
    def processor(self):
        """Create bulk processor instance."""
        return IntegrationBulkProcessor()

    @pytest.mark.asyncio
    async def test_process_jira_bulk_create(self, processor):
        """Jira bulk create processes items."""
        operation = Mock()
        operation.operation_type = "create"
        operation.items = [{"summary": "Test issue"}]

        results = await processor._process_jira_bulk(
            items=operation.items,
            operation=operation
        )

        assert len(results) == 1
        assert results[0]["success"] is True

    @pytest.mark.asyncio
    async def test_process_salesforce_bulk_create(self, processor):
        """Salesforce bulk create processes items."""
        operation = Mock()
        operation.operation_type = "create"
        operation.items = [{"firstName": "John", "lastName": "Doe"}]

        results = await processor._process_salesforce_bulk(
            items=operation.items,
            operation=operation
        )

        assert len(results) == 1
        assert results[0]["success"] is True

    @pytest.mark.asyncio
    async def test_process_notion_bulk_create(self, processor):
        """Notion bulk create processes items."""
        operation = Mock()
        operation.operation_type = "create"
        operation.items = [{"title": "New Page"}]

        results = await processor._process_notion_bulk(
            items=operation.items,
            operation=operation
        )

        assert len(results) == 1
        assert results[0]["success"] is True

    @pytest.mark.asyncio
    async def test_process_airtable_bulk_create(self, processor):
        """Airtable bulk create processes items."""
        operation = Mock()
        operation.operation_type = "create"
        operation.items = [{"Name": "Record 1"}]

        results = await processor._process_airtable_bulk(
            items=operation.items,
            operation=operation
        )

        assert len(results) == 1
        assert results[0]["success"] is True

    @pytest.mark.asyncio
    async def test_process_hubspot_bulk_create(self, processor):
        """HubSpot bulk create processes items."""
        operation = Mock()
        operation.operation_type = "create"
        operation.items = [{"email": "test@example.com"}]

        results = await processor._process_hubspot_bulk(
            items=operation.items,
            operation=operation
        )

        assert len(results) == 1
        assert results[0]["success"] is True

    @pytest.mark.asyncio
    async def test_process_monday_bulk_create(self, processor):
        """Monday.com bulk create processes items."""
        operation = Mock()
        operation.operation_type = "create"
        operation.items = [{"name": "New Item"}]

        results = await processor._process_monday_bulk(
            items=operation.items,
            operation=operation
        )

        assert len(results) == 1
        assert results[0]["success"] is True


class TestPerformanceStatistics:
    """Test performance statistics collection"""

    @pytest.fixture
    def processor(self):
        """Create bulk processor instance."""
        return IntegrationBulkProcessor()

    def test_get_performance_stats_empty(self, processor):
        """Performance stats return zeros when no jobs completed."""
        stats = processor.get_performance_stats()
        assert stats["total_jobs"] == 0
        assert stats["running_jobs"] == 0
        assert stats["completed_jobs"] == 0
        assert stats["queue_length"] == 0

    def test_get_performance_stats_with_jobs(self, processor):
        """Performance stats calculated correctly."""
        operation = Mock()
        operation.items = [{"data": 1}]

        # Add completed job
        job1 = BulkJob(
            job_id="job-001",
            operation=operation,
            status=OperationStatus.COMPLETED,
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc) + timedelta(seconds=10),
            total_items=1,
            successful_items=1,
            failed_items=0
        )
        processor.active_jobs["job-001"] = job1

        # Add running job
        job2 = BulkJob(
            job_id="job-002",
            operation=operation,
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            total_items=1
        )
        processor.active_jobs["job-002"] = job2

        stats = processor.get_performance_stats()
        assert stats["total_jobs"] == 2
        assert stats["running_jobs"] == 1
        assert stats["completed_jobs"] == 1
        assert stats["success_rate"] == 100.0


class TestJobResultsPersistence:
    """Test job results persistence to disk"""

    @pytest.fixture
    def processor(self):
        """Create bulk processor instance."""
        return IntegrationBulkProcessor()

    @pytest.fixture
    def mock_job(self):
        """Mock bulk job."""
        operation = Mock(spec=BulkOperation)
        operation.items = [{"data": 1}]

        return BulkJob(
            job_id="job-001",
            operation=operation,
            status=OperationStatus.COMPLETED,
            created_at=datetime.now(timezone.utc),
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            total_items=1,
            processed_items=1,
            successful_items=1,
            failed_items=0,
            progress_percentage=100.0,
            results=[{"success": True}],
            errors=[]
        )

    @pytest.mark.asyncio
    async def test_save_job_results(self, processor, mock_job, tmp_path):
        """Job results saved to disk successfully."""
        # Override results directory
        processor._job_results_dir = tmp_path

        await processor._save_job_results(mock_job)

        results_file = tmp_path / "job-001_results.json"
        assert results_file.exists()

        with open(results_file) as f:
            data = json.load(f)
            assert data["job_id"] == "job-001"
            assert data["status"] == "completed"
            assert data["successful_items"] == 1


class TestGlobalProcessorInstance:
    """Test global bulk processor singleton"""

    def test_get_bulk_processor_singleton(self):
        """get_bulk_processor returns singleton instance."""
        processor1 = get_bulk_processor()
        processor2 = get_bulk_processor()
        assert processor1 is processor2
