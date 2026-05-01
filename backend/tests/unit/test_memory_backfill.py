"""
Memory Backfill System Tests
TDD Pattern: Red-Green-Refactor

Tests verify:
1. Pipeline 1: Entity type backfill with temporary storage and promotion
2. Pipeline 2: Entity node backfill with semantic data and batch migration
3. TTL-based cleanup for unpromised data
4. Redis-based background processing (non-blocking)
5. Batch processing for memory management

Coverage: MemoryBackfillService, TemporaryEntityStorage, BackfillJobQueue
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
import asyncio
import json

from core.database import SessionLocal, Base
from core.models import EntityTypeDefinition, GraphNode, Tenant, Workspace
from core.memory_backfill_service import MemoryBackfillService
from core.temporary_entity_storage import TemporaryEntityType, TemporaryEntityNode
from core.backfill_job_queue import BackfillJobQueue, get_backfill_job_queue, BackfillJobType, BackfillJobStatus


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def db():
    """Create test database session."""
    from core.database import engine
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def sample_tenant(db):
    """Create sample tenant for testing."""
    tenant = Tenant(
        id="test-tenant-123",
        name="Test Tenant",
        subdomain="test-tenant",
        plan_type="free"
    )
    db.add(tenant)
    db.commit()
    return tenant


@pytest.fixture
def sample_workspace(db, sample_tenant):
    """Create sample workspace for testing."""
    workspace = Workspace(
        id="test-workspace-456",
        tenant_id=sample_tenant.id,
        name="Test Workspace"
    )
    db.add(workspace)
    db.commit()
    return workspace


@pytest.fixture
def backfill_service(db):
    """Create memory backfill service for testing."""
    return MemoryBackfillService(db=db)


@pytest.fixture
def job_queue():
    """Create backfill job queue for testing."""
    return get_backfill_job_queue()


@pytest.fixture
def sample_entity_type_schema():
    """Sample entity type JSON schema."""
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Invoice",
        "type": "object",
        "properties": {
            "invoice_number": {
                "type": "string",
                "description": "Unique invoice identifier"
            },
            "amount": {
                "type": "number",
                "minimum": 0,
                "description": "Invoice amount in USD"
            },
            "vendor": {
                "type": "string",
                "description": "Vendor name"
            },
            "status": {
                "type": "string",
                "enum": ["pending", "paid", "overdue"],
                "description": "Payment status"
            }
        },
        "required": ["invoice_number", "amount", "vendor"]
    }


@pytest.fixture
def sample_entity_nodes():
    """Sample entity node data for backfill."""
    return [
        {
            "name": "INV-001",
            "type": "invoice",
            "properties": {
                "invoice_number": "INV-001",
                "amount": 1500.00,
                "vendor": "Acme Corp",
                "status": "paid"
            },
            "description": "Office supplies invoice"
        },
        {
            "name": "INV-002",
            "type": "invoice",
            "properties": {
                "invoice_number": "INV-002",
                "amount": 3200.50,
                "vendor": "Global Supplies Inc",
                "status": "pending"
            },
            "description": "Equipment purchase"
        },
        {
            "name": "INV-003",
            "type": "invoice",
            "properties": {
                "invoice_number": "INV-003",
                "amount": 890.00,
                "vendor": "Tech Solutions LLC",
                "status": "overdue"
            },
            "description": "Software license renewal"
        }
    ]


# ============================================================================
# Test Suite 1: Pipeline 1 - Entity Type Backfill
# ============================================================================

class TestEntityTypeBackfillPipeline:
    """
    TDD Test Suite: Entity type backfill with temporary storage and promotion.

    Red: Write failing tests first
    Green: Implement entity type backfill logic
    Refactor: Improve performance and error handling
    """

    def test_store_entity_type_in_temporary_storage(self, backfill_service, sample_tenant, sample_entity_type_schema):
        """
        RED: Store entity type schema in temporary storage before promotion.

        Test Requirements:
        - Entity type stored with draft status
        - No active EntityTypeDefinition created yet
        - Metadata includes source, ingestion_timestamp, ttl
        - Schema validated before storage
        """
        # Store entity type in temporary storage
        temp_entity_type = backfill_service.store_temporary_entity_type(
            tenant_id=sample_tenant.id,
            slug="invoice",
            display_name="Invoice",
            description="Customer invoice entity",
            json_schema=sample_entity_type_schema,
            source="memory_ingestion",
            ttl_hours=48
        )

        # Verify temporary storage
        assert temp_entity_type is not None, "Should create temporary entity type"
        assert temp_entity_type.slug == "invoice"
        assert temp_entity_type.status == "draft"
        assert temp_entity_type.tenant_id == sample_tenant.id
        assert temp_entity_type.source == "memory_ingestion"
        assert temp_entity_type.expires_at is not None, "Should have TTL expiration"
        assert temp_entity_type.json_schema == sample_entity_type_schema

        # Verify NOT in active entity types
        active_type = backfill_service.db.query(EntityTypeDefinition).filter(
            EntityTypeDefinition.tenant_id == sample_tenant.id,
            EntityTypeDefinition.slug == "invoice"
        ).first()
        assert active_type is None, "Should NOT create active EntityTypeDefinition yet"

    def test_promote_entity_type_to_active(self, backfill_service, sample_tenant, sample_entity_type_schema):
        """
        RED: Promote temporary entity type to active EntityTypeDefinition.

        Test Requirements:
        - Creates EntityTypeDefinition in active table
        - Validates schema before promotion
        - Sets is_active=True
        - Removes or marks temporary record as promoted
        """
        # First store in temporary
        temp_type = backfill_service.store_temporary_entity_type(
            tenant_id=sample_tenant.id,
            slug="invoice",
            display_name="Invoice",
            description="Customer invoice entity",
            json_schema=sample_entity_type_schema,
            source="memory_ingestion",
            ttl_hours=48
        )

        # Promote to active
        active_type = backfill_service.promote_entity_type(
            temporary_type_id=temp_type.id,
            tenant_id=sample_tenant.id
        )

        # Verify active entity type created
        assert active_type is not None, "Should create active EntityTypeDefinition"
        assert active_type.slug == "invoice"
        assert active_type.display_name == "Invoice"
        assert active_type.is_active is True
        assert active_type.json_schema == sample_entity_type_schema

        # Verify temporary record marked as promoted
        backfill_service.db.refresh(temp_type)
        assert temp_type.status == "promoted", "Temporary record should be marked as promoted"

    def test_reject_entity_type_cleanup(self, backfill_service, sample_tenant, sample_entity_type_schema):
        """
        RED: Rejected entity types should be cleaned up.

        Test Requirements:
        - Rejected types marked for deletion
        - Background job cleans up after set time
        - No active EntityTypeDefinition created
        """
        # Store in temporary
        temp_type = backfill_service.store_temporary_entity_type(
            tenant_id=sample_tenant.id,
            slug="invoice",
            display_name="Invoice",
            description="Customer invoice entity",
            json_schema=sample_entity_type_schema,
            source="memory_ingestion",
            ttl_hours=48
        )

        # Reject the entity type
        backfill_service.reject_entity_type(
            temporary_type_id=temp_type.id,
            tenant_id=sample_tenant.id,
            reason="Duplicate of existing type"
        )

        # Verify marked for deletion
        backfill_service.db.refresh(temp_type)
        assert temp_type.status == "rejected"
        # Convert expires_at to UTC for comparison
        expires_at_utc = temp_type.expires_at.replace(tzinfo=timezone.utc) if temp_type.expires_at.tzinfo is None else temp_type.expires_at
        assert expires_at_utc <= datetime.now(timezone.utc) + timedelta(hours=1), "Should expire soon"

    def test_batch_store_entity_types(self, backfill_service, sample_tenant):
        """
        RED: Batch store multiple entity types efficiently.

        Test Requirements:
        - Store multiple entity types in single transaction
        - Batch size limited for memory management
        - All types stored with proper validation
        - Returns summary of successful/failed
        """
        schemas = {
            "invoice": {
                "title": "Invoice",
                "type": "object",
                "properties": {"amount": {"type": "number"}}
            },
            "vendor": {
                "title": "Vendor",
                "type": "object",
                "properties": {"name": {"type": "string"}}
            },
            "purchase_order": {
                "title": "Purchase Order",
                "type": "object",
                "properties": {"po_number": {"type": "string"}}
            }
        }

        # Batch store
        result = backfill_service.batch_store_temporary_entity_types(
            tenant_id=sample_tenant.id,
            entity_types=schemas,
            source="memory_ingestion",
            batch_size=2
        )

        # Verify batch results
        assert result["total"] == 3
        assert result["successful"] == 3
        assert result["failed"] == 0
        assert len(result["temporary_ids"]) == 3


# ============================================================================
# Test Suite 2: Pipeline 2 - Entity Node Backfill
# ============================================================================

class TestEntityNodeBackfillPipeline:
    """
    TDD Test Suite: Entity node backfill with semantic data and batch migration.

    Red: Write failing tests first
    Green: Implement entity node backfill logic
    Refactor: Optimize batch processing and memory usage
    """

    def test_store_entity_nodes_in_temporary_storage(self, backfill_service, sample_tenant, sample_workspace, sample_entity_nodes):
        """
        RED: Store entity nodes in temporary storage before type promotion.

        Test Requirements:
        - Nodes stored with reference to temporary entity type
        - Semantic data preserved in properties
        - Batch insertion for efficiency
        - No GraphNodes created yet
        """
        # First create temporary entity type
        temp_type = backfill_service.store_temporary_entity_type(
            tenant_id=sample_tenant.id,
            slug="invoice",
            display_name="Invoice",
            description="Customer invoice",
            json_schema={"type": "object"},
            source="memory_ingestion"
        )

        # Store entity nodes
        temp_nodes = backfill_service.store_temporary_entity_nodes(
            tenant_id=sample_tenant.id,
            workspace_id=sample_workspace.id,
            entity_type_slug="invoice",
            nodes=sample_entity_nodes,
            batch_size=2
        )

        # Verify temporary storage
        assert len(temp_nodes) == 3, "Should store all 3 nodes"
        assert all(node.type == "invoice" for node in temp_nodes)
        assert all(node.status == "pending" for node in temp_nodes)

        # Verify NOT in active GraphNodes
        active_nodes = backfill_service.db.query(GraphNode).filter(
            GraphNode.workspace_id == sample_workspace.id,
            GraphNode.type == "invoice"
        ).all()
        assert len(active_nodes) == 0, "Should NOT create GraphNodes yet"

    def test_migrate_nodes_after_type_promotion(self, backfill_service, sample_tenant, sample_workspace, sample_entity_type_schema, sample_entity_nodes):
        """
        RED: Migrate temporary nodes to GraphNodes after entity type promotion.

        Test Requirements:
        - Batch migration triggered by type promotion
        - All temporary nodes for type migrated to GraphNodes
        - Properties and semantic data preserved
        - Temporary nodes marked as migrated
        """
        # Store temporary entity type
        temp_type = backfill_service.store_temporary_entity_type(
            tenant_id=sample_tenant.id,
            slug="invoice",
            display_name="Invoice",
            description="Customer invoice",
            json_schema=sample_entity_type_schema,
            source="memory_ingestion"
        )

        # Store temporary nodes
        temp_nodes = backfill_service.store_temporary_entity_nodes(
            tenant_id=sample_tenant.id,
            workspace_id=sample_workspace.id,
            entity_type_slug="invoice",
            nodes=sample_entity_nodes
        )

        # Promote entity type (should trigger node migration)
        active_type = backfill_service.promote_entity_type(
            temporary_type_id=temp_type.id,
            tenant_id=sample_tenant.id,
            migrate_nodes=True
        )

        # Verify GraphNodes created
        graph_nodes = backfill_service.db.query(GraphNode).filter(
            GraphNode.workspace_id == sample_workspace.id,
            GraphNode.type == "invoice"
        ).all()
        assert len(graph_nodes) == 3, "Should migrate all 3 nodes to GraphNodes"

        # Verify data preserved
        node_names = {node.name for node in graph_nodes}
        assert node_names == {"INV-001", "INV-002", "INV-003"}

        # Verify temporary nodes marked as migrated
        for temp_node in temp_nodes:
            backfill_service.db.refresh(temp_node)
            assert temp_node.status == "migrated"

    def test_batch_migrate_large_datasets(self, backfill_service, sample_tenant, sample_workspace):
        """
        RED: Batch migrate large node datasets without memory issues.

        Test Requirements:
        - Process nodes in batches (e.g., 1000 at a time)
        - Non-blocking processing with Redis queue
        - Memory usage controlled
        - Progress tracking for monitoring
        """
        # Create 5000 sample nodes
        large_dataset = [
            {
                "name": f"INV-{i:05d}",
                "type": "invoice",
                "properties": {"invoice_number": f"INV-{i:05d}", "amount": i * 100.0}
            }
            for i in range(1, 5001)
        ]

        # Store temporary entity type
        temp_type = backfill_service.store_temporary_entity_type(
            tenant_id=sample_tenant.id,
            slug="invoice",
            display_name="Invoice",
            json_schema={"type": "object"},
            source="memory_ingestion"
        )

        # Store all nodes in temporary storage
        temp_nodes = backfill_service.store_temporary_entity_nodes(
            tenant_id=sample_tenant.id,
            workspace_id=sample_workspace.id,
            entity_type_slug="invoice",
            nodes=large_dataset,
            batch_size=1000
        )

        assert len(temp_nodes) == 5000, "Should store all 5000 nodes"

        # Migrate in batches
        migration_result = backfill_service.batch_migrate_nodes(
            tenant_id=sample_tenant.id,
            workspace_id=sample_workspace.id,
            entity_type_slug="invoice",
            batch_size=1000
        )

        # Verify batch migration
        assert migration_result["total_nodes"] == 5000
        assert migration_result["migrated"] == 5000
        assert migration_result["batches_processed"] == 5
        assert migration_result["failed"] == 0


# ============================================================================
# Test Suite 3: TTL and Cleanup
# ============================================================================

class TestTTLCleanup:
    """
    TDD Test Suite: TTL-based cleanup for unpromoted data.

    Red: Write failing tests first
    Green: Implement TTL cleanup logic
    Refactor: Optimize cleanup performance
    """

    def test_expired_temporary_entity_types_cleanup(self, backfill_service, sample_tenant, sample_entity_type_schema):
        """
        RED: Expired temporary entity types are automatically cleaned up.

        Test Requirements:
        - Types past TTL marked for deletion
        - Background job runs cleanup periodically
        - No EntityTypeDefinition created for expired types
        """
        # Store entity type with short TTL
        temp_type = backfill_service.store_temporary_entity_type(
            tenant_id=sample_tenant.id,
            slug="invoice",
            display_name="Invoice",
            json_schema=sample_entity_type_schema,
            source="memory_ingestion",
            ttl_hours=1
        )

        # Manually expire the type
        temp_type.expires_at = datetime.now() - timedelta(hours=1)
        backfill_service.db.commit()

        # Run cleanup
        cleaned = backfill_service.cleanup_expired_temporary_data()

        assert cleaned["entity_types_removed"] >= 1
        assert temp_type.id in cleaned["removed_type_ids"]

    def test_expired_temporary_nodes_cleanup(self, backfill_service, sample_tenant, sample_workspace, sample_entity_nodes):
        """
        RED: Expired temporary nodes are cleaned up.

        Test Requirements:
        - Nodes past TTL removed from temporary storage
        - No GraphNodes created
        - Cleanup runs in batches to manage memory
        """
        # Store temporary type and nodes with short TTL
        temp_type = backfill_service.store_temporary_entity_type(
            tenant_id=sample_tenant.id,
            slug="invoice",
            display_name="Invoice",
            json_schema={"type": "object"},
            source="memory_ingestion",
            ttl_hours=1
        )

        temp_nodes = backfill_service.store_temporary_entity_nodes(
            tenant_id=sample_tenant.id,
            workspace_id=sample_workspace.id,
            entity_type_slug="invoice",
            nodes=sample_entity_nodes
        )

        # Manually expire
        temp_type.expires_at = datetime.now() - timedelta(hours=1)
        backfill_service.db.commit()

        # Run cleanup
        cleaned = backfill_service.cleanup_expired_temporary_data()

        assert cleaned["nodes_removed"] >= 3

    @pytest.mark.asyncio
    async def test_ttl_cleanup_runs_periodically(self, job_queue, backfill_service, sample_tenant):
        """
        RED: TTL cleanup runs automatically via Redis job scheduler.

        Test Requirements:
        - Cleanup job scheduled in Redis
        - Runs every hour (configurable)
        - Non-blocking execution
        - Logs cleanup results
        """
        # Schedule cleanup job
        job_id = await job_queue.schedule_ttl_cleanup(
            tenant_id=sample_tenant.id,
            interval_hours=1
        )

        assert job_id is not None, "Should schedule cleanup job"

        # Verify job queued
        job = await job_queue.get_job_status(job_id)
        assert job["status"] == "queued"
        assert job["job_type"] == "ttl_cleanup"


# ============================================================================
# Test Suite 4: Background Processing with Redis
# ============================================================================

class TestBackgroundProcessing:
    """
    TDD Test Suite: Redis-based background processing for non-blocking operations.

    Red: Write failing tests first
    Green: Implement Redis job queue
    Refactor: Optimize queue performance and reliability
    """

    @pytest.mark.asyncio
    async def test_schedule_entity_type_backfill_job(self, job_queue, sample_tenant, sample_entity_type_schema):
        """
        RED: Schedule entity type backfill as background job.

        Test Requirements:
        - Job queued in Redis
        - Non-blocking return
        - Job includes tenant_id, schema, metadata
        - Job status trackable
        """
        job_id = await job_queue.schedule_entity_type_backfill(
            tenant_id=sample_tenant.id,
            slug="invoice",
            display_name="Invoice",
            json_schema=sample_entity_type_schema,
            source="memory_ingestion"
        )

        assert job_id is not None, "Should schedule job and return ID"

        # Verify job status
        status = await job_queue.get_job_status(job_id)
        assert status["job_type"] == "entity_type_backfill"
        assert status["tenant_id"] == sample_tenant.id
        assert status["status"] in ["queued", "processing"]

    @pytest.mark.asyncio
    async def test_schedule_node_migration_job(self, job_queue, sample_tenant, sample_workspace):
        """
        RED: Schedule node migration as background job.

        Test Requirements:
        - Migration job queued after type promotion
        - Batch size configured in job
        - Progress tracking enabled
        - Non-blocking execution
        """
        job_id = await job_queue.schedule_node_migration(
            tenant_id=sample_tenant.id,
            workspace_id=sample_workspace.id,
            entity_type_slug="invoice",
            batch_size=1000
        )

        assert job_id is not None

        # Verify job details
        status = await job_queue.get_job_status(job_id)
        assert status["job_type"] == "node_migration"
        assert status["batch_size"] == 1000

    @pytest.mark.asyncio
    async def test_concurrent_job_processing(self, job_queue, sample_tenant):
        """
        RED: Multiple jobs process concurrently without blocking.

        Test Requirements:
        - Multiple jobs queued simultaneously
        - Worker pool processes jobs in parallel
        - No blocking between jobs
        - Resource limits enforced
        """
        # Schedule multiple jobs
        job_ids = []
        for i in range(5):
            job_id = await job_queue.schedule_entity_type_backfill(
                tenant_id=sample_tenant.id,
                slug=f"entity_type_{i}",
                display_name=f"Entity Type {i}",
                json_schema={"type": "object"},
                source="batch_import"
            )
            job_ids.append(job_id)

        # Verify all jobs queued
        for job_id in job_ids:
            status = await job_queue.get_job_status(job_id)
            assert status["status"] in ["queued", "processing"]

    @pytest.mark.asyncio
    async def test_job_failure_retry_logic(self, job_queue, sample_tenant):
        """
        RED: Failed jobs retry with exponential backoff.

        Test Requirements:
        - Failed jobs marked for retry
        - Exponential backoff: 1min, 5min, 15min, 1hr
        - Max retry limit enforced
        - Failed jobs moved to dead letter queue after max retries
        """
        # Schedule a job that will fail
        job_id = await job_queue.schedule_entity_type_backfill(
            tenant_id=sample_tenant.id,
            slug="invalid_type",
            display_name="Invalid Type",
            json_schema={"invalid": "schema"},  # Invalid schema
            source="test"
        )

        # Simulate job failure and retry
        await job_queue.process_job_with_retry(job_id)

        status = await job_queue.get_job_status(job_id)
        assert status["retry_count"] >= 1
        assert status["status"] in ["retrying", "failed", "dead_letter"]


# ============================================================================
# Test Suite 5: Batch Processing and Memory Management
# ============================================================================

class TestBatchProcessing:
    """
    TDD Test Suite: Batch processing for memory-efficient operations.

    Red: Write failing tests first
    Green: Implement batch processing logic
    Refactor: Optimize batch sizes and throughput
    """

    def test_adaptive_batch_sizing(self, backfill_service, sample_tenant, sample_workspace):
        """
        RED: Batch sizes adapt based on available memory.

        Test Requirements:
        - Monitor memory usage during processing
        - Reduce batch size if memory high
        - Increase batch size if memory low
        - Minimum/maximum batch size limits
        """
        # Test adaptive sizing
        batch_size = backfill_service.calculate_adaptive_batch_size(
            available_memory_mb=512,
            target_memory_usage_percent=70
        )

        assert 100 <= batch_size <= 5000, "Batch size should be within limits"

    def test_streaming_node_insertion(self, backfill_service, sample_tenant, sample_workspace):
        """
        RED: Stream node insertion to avoid loading all data into memory.

        Test Requirements:
        - Use server-side cursor for streaming
        - Process one batch at a time
        - Memory usage constant regardless of dataset size
        - Progress callbacks for monitoring
        """
        # Create large dataset
        large_dataset = [
            {
                "name": f"NODE-{i:06d}",
                "type": "test_entity",
                "properties": {"index": i}
            }
            for i in range(10000)
        ]

        # Store with streaming
        progress_updates = []
        def progress_callback(update):
            progress_updates.append(update)

        result = backfill_service.streaming_store_temporary_nodes(
            tenant_id=sample_tenant.id,
            workspace_id=sample_workspace.id,
            entity_type_slug="test_entity",
            nodes=large_dataset,
            batch_size=500,
            progress_callback=progress_callback
        )

        assert result["total_stored"] == 10000
        assert len(progress_updates) == 20  # 10000 / 500
        assert all(update["batch_size"] <= 500 for update in progress_updates)

    def test_memory_efficient_validation(self, backfill_service, sample_tenant):
        """
        RED: Validate schemas in batches without loading all into memory.

        Test Requirements:
        - Validate one schema at a time
        - Release memory after each validation
        - Collect validation errors efficiently
        - Continue processing after validation errors
        """
        # Create multiple schemas (some invalid)
        schemas = {
            "valid_type": {"title": "Valid", "type": "object"},
            "invalid_type": {"title": "Invalid", "type": "invalid_enum"},
            "another_valid": {"title": "Another Valid", "type": "object"},
            "another_invalid": {"title": "Another Invalid", "type": "bad_type"}
        }

        # Batch validate
        validation_result = backfill_service.batch_validate_schemas(
            tenant_id=sample_tenant.id,
            schemas=schemas,
            batch_size=2
        )

        assert validation_result["valid"] == 2
        assert validation_result["invalid"] == 2
        assert len(validation_result["errors"]) == 2


# ============================================================================
# Test Suite 6: Integration Tests
# ============================================================================

class TestMemoryBackfillIntegration:
    """
    TDD Test Suite: End-to-end integration tests for memory backfill system.

    Red: Write failing tests first
    Green: Implement full integration
    Refactor: Optimize end-to-end performance
    """

    @pytest.mark.asyncio
    async def test_full_backfill_workflow(self, backfill_service, job_queue, sample_tenant, sample_workspace, sample_entity_type_schema, sample_entity_nodes):
        """
        RED: Complete backfill workflow from ingestion to promotion to migration.

        Test Requirements:
        - Pipeline 1: Entity type stored temporarily
        - Pipeline 2: Entity nodes stored temporarily
        - User promotes entity type
        - Nodes automatically migrated to GraphNodes
        - Temporary data cleaned up
        """
        # Pipeline 1: Store entity type
        temp_type = backfill_service.store_temporary_entity_type(
            tenant_id=sample_tenant.id,
            slug="invoice",
            display_name="Invoice",
            json_schema=sample_entity_type_schema,
            source="memory_ingestion"
        )

        # Pipeline 2: Store entity nodes
        temp_nodes = backfill_service.store_temporary_entity_nodes(
            tenant_id=sample_tenant.id,
            workspace_id=sample_workspace.id,
            entity_type_slug="invoice",
            nodes=sample_entity_nodes
        )

        # User promotes entity type
        active_type = backfill_service.promote_entity_type(
            temporary_type_id=temp_type.id,
            tenant_id=sample_tenant.id,
            migrate_nodes=True
        )

        # Verify complete workflow
        assert active_type.is_active is True

        graph_nodes = backfill_service.db.query(GraphNode).filter(
            GraphNode.type == "invoice"
        ).all()
        assert len(graph_nodes) == 3

    @pytest.mark.asyncio
    async def test_rejection_workflow_cleanup(self, backfill_service, sample_tenant, sample_workspace, sample_entity_nodes):
        """
        RED: Rejected entity types cleanup associated nodes.

        Test Requirements:
        - Rejected type expires quickly
        - Associated nodes marked for cleanup
        - Background job removes all rejected data
        - No active data created
        """
        # Store entity type and nodes
        temp_type = backfill_service.store_temporary_entity_type(
            tenant_id=sample_tenant.id,
            slug="invoice",
            display_name="Invoice",
            json_schema={"type": "object"},
            source="memory_ingestion"
        )

        temp_nodes = backfill_service.store_temporary_entity_nodes(
            tenant_id=sample_tenant.id,
            workspace_id=sample_workspace.id,
            entity_type_slug="invoice",
            nodes=sample_entity_nodes
        )

        # Reject entity type
        backfill_service.reject_entity_type(
            temporary_type_id=temp_type.id,
            tenant_id=sample_tenant.id,
            reason="Not needed"
        )

        # Verify cleanup scheduled
        backfill_service.db.refresh(temp_type)
        assert temp_type.status == "rejected"
        # Convert expires_at to UTC for comparison
        expires_at_utc = temp_type.expires_at.replace(tzinfo=timezone.utc) if temp_type.expires_at.tzinfo is None else temp_type.expires_at
        assert expires_at_utc <= datetime.now(timezone.utc) + timedelta(hours=1)


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
