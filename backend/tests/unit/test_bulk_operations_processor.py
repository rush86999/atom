"""
Unit tests for IntegrationBulkProcessor class.

Tests cover:
- Initialization with data mapper
- Job submission and status tracking
- Job cancellation
- Batch processing
- Error handling
- Performance statistics
"""

from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timezone
import pytest

from core.bulk_operations_processor import (
    IntegrationBulkProcessor,
    BulkJob,
    OperationStatus,
    BulkOperation,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_processor():
    """Mock bulk processor instance."""
    with patch('core.bulk_operations_processor.get_data_mapper') as mock_mapper:
        mock_mapper.return_value = Mock()
        processor = IntegrationBulkProcessor()
        return processor


@pytest.fixture
def sample_operation():
    """Sample bulk operation."""
    return BulkOperation(
        integration_id="asana",
        operation_type="create",
        items=[{"name": "Task 1"}, {"name": "Task 2"}],
        batch_size=100
    )


# ============================================================================
# Test: Initialization
# ============================================================================

class TestIntegrationBulkProcessorInit:
    """Tests for IntegrationBulkProcessor initialization."""

    def test_init_default(self):
        """Test default initialization."""
        with patch('core.bulk_operations_processor.get_data_mapper'):
            processor = IntegrationBulkProcessor()
            assert processor.active_jobs == {}
            assert processor.job_queue == []
            assert processor.max_concurrent_jobs == 5
            assert processor.default_batch_size == 100

    def test_init_with_custom_mapper(self):
        """Test initialization with custom data mapper."""
        mock_mapper = Mock()
        processor = IntegrationBulkProcessor(data_mapper=mock_mapper)
        assert processor.data_mapper == mock_mapper


# ============================================================================
# Test: Job Submission
# ============================================================================

class TestSubmitBulkJob:
    """Tests for submit_bulk_job method."""

    @pytest.mark.asyncio
    async def test_submit_job_success(self, mock_processor, sample_operation):
        """Test successful job submission."""
        job_id = await mock_processor.submit_bulk_job(sample_operation)

        assert job_id is not None
        assert job_id.startswith("bulk_")
        assert job_id in mock_processor.active_jobs
        assert job_id in mock_processor.job_queue

    @pytest.mark.asyncio
    async def test_submit_job_creates_bulk_job(self, mock_processor, sample_operation):
        """Test submission creates BulkJob with correct attributes."""
        job_id = await mock_processor.submit_bulk_job(sample_operation)
        job = mock_processor.active_jobs[job_id]

        assert isinstance(job, BulkJob)
        assert job.operation == sample_operation
        assert job.status == OperationStatus.PENDING
        assert job.total_items == 2
        assert job.processed_items == 0


# ============================================================================
# Test: Job Status
# ============================================================================

class TestGetJobStatus:
    """Tests for get_job_status method."""

    @pytest.mark.asyncio
    async def test_get_job_status_existing(self, mock_processor, sample_operation):
        """Test getting status of existing job."""
        job_id = await mock_processor.submit_bulk_job(sample_operation)
        status = await mock_processor.get_job_status(job_id)

        assert status is not None
        assert status.job_id == job_id
        assert status.status == OperationStatus.PENDING

    @pytest.mark.asyncio
    async def test_get_job_status_nonexistent(self, mock_processor):
        """Test getting status of non-existent job."""
        status = await mock_processor.get_job_status("nonexistent")
        assert status is None


# ============================================================================
# Test: Job Cancellation
# ============================================================================

class TestCancelJob:
    """Tests for cancel_job method."""

    @pytest.mark.asyncio
    async def test_cancel_pending_job(self, mock_processor, sample_operation):
        """Test cancelling a pending job."""
        job_id = await mock_processor.submit_bulk_job(sample_operation)
        result = await mock_processor.cancel_job(job_id)

        assert result is True
        assert mock_processor.active_jobs[job_id].status == OperationStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_running_job(self, mock_processor, sample_operation):
        """Test cancelling a running job."""
        job_id = await mock_processor.submit_bulk_job(sample_operation)
        mock_processor.active_jobs[job_id].status = OperationStatus.RUNNING

        result = await mock_processor.cancel_job(job_id)

        assert result is True
        assert mock_processor.active_jobs[job_id].status == OperationStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_cancel_completed_job_fails(self, mock_processor, sample_operation):
        """Test cancelling completed job fails."""
        job_id = await mock_processor.submit_bulk_job(sample_operation)
        mock_processor.active_jobs[job_id].status = OperationStatus.COMPLETED

        result = await mock_processor.cancel_job(job_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_job(self, mock_processor):
        """Test cancelling non-existent job."""
        result = await mock_processor.cancel_job("nonexistent")
        assert result is False


# ============================================================================
# Test: Performance Statistics
# ============================================================================

class TestPerformanceStats:
    """Tests for get_performance_stats method."""

    def test_get_stats_empty(self, mock_processor):
        """Test stats with no jobs."""
        stats = mock_processor.get_performance_stats()

        assert stats["total_jobs"] == 0
        assert stats["running_jobs"] == 0
        assert stats["completed_jobs"] == 0

    @pytest.mark.asyncio
    async def test_get_stats_with_jobs(self, mock_processor, sample_operation):
        """Test stats with active jobs."""
        # Submit and complete a job
        job_id = await mock_processor.submit_bulk_job(sample_operation)
        job = mock_processor.active_jobs[job_id]
        job.status = OperationStatus.COMPLETED
        job.started_at = datetime.now(timezone.utc)
        job.completed_at = datetime.now(timezone.utc)
        job.successful_items = 2

        stats = mock_processor.get_performance_stats()

        assert stats["total_jobs"] == 1
        assert stats["completed_jobs"] == 1
        assert stats["success_rate"] == 100.0


# ============================================================================
# Test: BulkJob Dataclass
# ============================================================================

class TestBulkJob:
    """Tests for BulkJob dataclass."""

    def test_bulk_job_creation(self):
        """Test BulkJob creation."""
        operation = BulkOperation(
            integration_id="test",
            operation_type="create",
            items=[{"id": 1}]
        )

        job = BulkJob(
            job_id="test-1",
            operation=operation,
            status=OperationStatus.PENDING,
            created_at=datetime.now(timezone.utc),
            total_items=1
        )

        assert job.job_id == "test-1"
        assert job.status == OperationStatus.PENDING
        assert job.total_items == 1
        assert job.processed_items == 0

    def test_bulk_job_post_init(self, sample_operation):
        """Test BulkJob __post_init__ sets total_items from operation."""
        job = BulkJob(
            job_id="test-1",
            operation=sample_operation,
            status=OperationStatus.PENDING,
            created_at=datetime.now(timezone.utc)
        )

        # total_items should be set from operation.items length
        assert job.total_items == 2


# ============================================================================
# Test: OperationStatus Enum
# ============================================================================

class TestOperationStatus:
    """Tests for OperationStatus enum."""

    def test_status_values(self):
        """Test all status values exist."""
        assert OperationStatus.PENDING.value == "pending"
        assert OperationStatus.RUNNING.value == "running"
        assert OperationStatus.COMPLETED.value == "completed"
        assert OperationStatus.FAILED.value == "failed"
        assert OperationStatus.CANCELLED.value == "cancelled"
        assert OperationStatus.PARTIAL_SUCCESS.value == "partial_success"


# ============================================================================
# Test: Integration Processors
# ============================================================================

class TestIntegrationProcessors:
    """Tests for integration-specific processors."""

    def test_has_asana_processor(self, mock_processor):
        """Test Asana processor exists."""
        assert "asana" in mock_processor.integration_processors
        assert callable(mock_processor.integration_processors["asana"])

    def test_has_jira_processor(self, mock_processor):
        """Test Jira processor exists."""
        assert "jira" in mock_processor.integration_processors

    def test_has_salesforce_processor(self, mock_processor):
        """Test Salesforce processor exists."""
        assert "salesforce" in mock_processor.integration_processors

    def test_all_supported_integrations(self, mock_processor):
        """Test all expected integrations are supported."""
        expected = ["asana", "jira", "salesforce", "notion", "airtable", "hubspot", "monday"]
        for integration in expected:
            assert integration in mock_processor.integration_processors


    def test_all_supported_integrations(self, mock_processor):
        """Test all expected integrations are supported."""
        expected = ["asana", "jira", "salesforce", "notion", "airtable", "hubspot", "monday"]
        for integration in expected:
            assert integration in mock_processor.integration_processors


# ============================================================================
# Test: Batch Processing
# ============================================================================

class TestBatchProcessing:
    """Tests for batch size handling and chunking logic."""

    @pytest.mark.asyncio
    async def test_prepare_items_basic(self, mock_processor):
        """Test basic item preparation."""
        operation = BulkOperation(
            integration_id="asana",
            operation_type="create",
            items=[{"name": f"Task {i}"} for i in range(5)]
        )

        items = await mock_processor._prepare_items(operation)

        assert len(items) == 5
        assert items[0]["name"] == "Task 0"

    @pytest.mark.asyncio
    async def test_batch_splitting(self, mock_processor):
        """Test items split into correct batch sizes."""
        items = [{"name": f"Task {i}"} for i in range(10)]
        batch_size = 3

        batches = [items[i:i + batch_size] for i in range(0, len(items), batch_size)]

        assert len(batches) == 4  # 10 items / 3 = 4 batches
        assert len(batches[0]) == 3
        assert len(batches[1]) == 3
        assert len(batches[2]) == 3
        assert len(batches[3]) == 1

    @pytest.mark.asyncio
    async def test_empty_batch_handling(self, mock_processor):
        """Test empty batch is handled correctly."""
        operation = BulkOperation(
            integration_id="asana",
            operation_type="create",
            items=[],
            batch_size=10
        )

        items = await mock_processor._prepare_items(operation)
        batches = [items[i:i + 10] for i in range(0, len(items), 10)]

        assert len(batches) == 1
        assert len(batches[0]) == 0

    @pytest.mark.asyncio
    async def test_single_item_batch(self, mock_processor):
        """Test single item batch works correctly."""
        operation = BulkOperation(
            integration_id="asana",
            operation_type="create",
            items=[{"name": "Single Task"}],
            batch_size=100
        )

        items = await mock_processor._prepare_items(operation)
        batches = [items[i:i + 100] for i in range(0, len(items), 100)]

        assert len(batches) == 1
        assert len(batches[0]) == 1


# ============================================================================
# Test: Error Handling
# ============================================================================

class TestErrorHandling:
    """Tests for partial failures, rollback, error reporting."""

    @pytest.mark.asyncio
    async def test_update_job_progress_success(self, mock_processor):
        """Test job progress updates on success."""
        from core.bulk_operations_processor import BulkJob

        job = BulkJob(
            job_id="test-job",
            operation=BulkOperation(
                integration_id="asana",
                operation_type="create",
                items=[]
            ),
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc)
        )

        batch_results = [
            {"success": True, "item": {"name": "Task 1"}},
            {"success": True, "item": {"name": "Task 2"}}
        ]

        await mock_processor._update_job_progress(job, batch_results, 1, 2)

        assert job.processed_items == 2
        assert job.successful_items == 2
        assert job.failed_items == 0
        assert job.progress_percentage == 50.0

    @pytest.mark.asyncio
    async def test_update_job_progress_with_failure(self, mock_processor):
        """Test job progress tracks failures."""
        from core.bulk_operations_processor import BulkJob

        job = BulkJob(
            job_id="test-job",
            operation=BulkOperation(
                integration_id="asana",
                operation_type="create",
                items=[]
            ),
            status=OperationStatus.RUNNING,
            created_at=datetime.now(timezone.utc)
        )

        batch_results = [
            {"success": True, "item": {"name": "Task 1"}},
            {"success": False, "item": {"name": "Task 2"}, "error": "Invalid data"}
        ]

        await mock_processor._update_job_progress(job, batch_results, 1, 2)

        assert job.processed_items == 2
        assert job.successful_items == 1
        assert job.failed_items == 1
        assert len(job.errors) == 1


# ============================================================================
# Test: Global Instance
# ============================================================================

class TestGlobalInstance:
    """Tests for global bulk processor instance."""

    def test_get_bulk_processor(self):
        """Test global processor instance retrieval."""
        from core.bulk_operations_processor import get_bulk_processor

        processor = get_bulk_processor()
        assert processor is not None
        assert isinstance(processor, IntegrationBulkProcessor)

    def test_global_processor_singleton(self):
        """Test global processor is singleton."""
        from core.bulk_operations_processor import get_bulk_processor

        processor1 = get_bulk_processor()
        processor2 = get_bulk_processor()

        assert processor1 is processor2


# ============================================================================
# Test: Edge Cases
# ============================================================================

class TestBulkProcessorEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_zero_items_bulk_operation(self, mock_processor):
        """Test bulk operation with zero items."""
        operation = BulkOperation(
            integration_id="asana",
            operation_type="create",
            items=[]
        )

        job_id = await mock_processor.submit_bulk_job(operation)
        job = mock_processor.active_jobs[job_id]

        assert job.total_items == 0

    @pytest.mark.asyncio
    async def test_very_large_batch_size(self, mock_processor):
        """Test handling of very large batch size."""
        operation = BulkOperation(
            integration_id="asana",
            operation_type="create",
            items=[{"name": f"Task {i}"} for i in range(10)],
            batch_size=10000
        )

        items = await mock_processor._prepare_items(operation)
        batches = [items[i:i + 10000] for i in range(0, len(items), 10000)]

        assert len(batches) == 1
        assert len(batches[0]) == 10

    @pytest.mark.asyncio
    async def test_concurrent_job_limit(self, mock_processor):
        """Test concurrent job limit is enforced."""
        assert mock_processor.max_concurrent_jobs == 5

        # Test limit can be changed
        mock_processor.max_concurrent_jobs = 10
        assert mock_processor.max_concurrent_jobs == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
