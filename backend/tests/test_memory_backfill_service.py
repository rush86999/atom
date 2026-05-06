"""
Comprehensive test suite for Memory Backfill Service

Tests episodic memory backfill logic, entity type storage, promotion,
node migration, batch processing, TTL cleanup, and memory management.
"""

import os
import sys
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

sys.path.append(os.getcwd())

from core.database import Base
from core.memory_backfill_service import MemoryBackfillService
from core.models import EntityTypeDefinition, GraphNode
from core.schema_validator import SchemaValidator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class TestMemoryBackfillService(unittest.TestCase):
    """Test suite for MemoryBackfillService"""

    def setUp(self):
        """Setup test database and service instance"""
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()

        # Mock schema validator
        self.mock_validator = Mock(spec=SchemaValidator)
        self.mock_validator.validate_schema.return_value = (True, "")

        self.service = MemoryBackfillService(
            db=self.db,
            schema_validator=self.mock_validator,
            job_queue=None
        )

    def tearDown(self):
        """Cleanup database session"""
        self.db.close()
        self.engine.dispose()

    # =========================================================================
    # Pipeline 1: Entity Type Backfill Tests
    # =========================================================================

    def test_store_temporary_entity_type_success(self):
        """Test successful storage of temporary entity type"""
        temp_type = self.service.store_temporary_entity_type(
            tenant_id="tenant-1",
            slug="invoice",
            display_name="Invoice",
            json_schema={"type": "object", "properties": {}},
            description="Business invoice entity",
            source="test_ingestion",
            ttl_hours=48,
            confidence_score=85
        )

        self.assertIsNotNone(temp_type.id)
        self.assertEqual(temp_type.tenant_id, "tenant-1")
        self.assertEqual(temp_type.slug, "invoice")
        self.assertEqual(temp_type.display_name, "Invoice")
        self.assertEqual(temp_type.description, "Business invoice entity")
        self.assertEqual(temp_type.source, "test_ingestion")
        self.assertEqual(temp_type.confidence_score, 85)
        self.assertIsNotNone(temp_type.expires_at)

    def test_store_temporary_entity_type_invalid_schema(self):
        """Test that invalid schema raises ValueError"""
        self.mock_validator.validate_schema.return_value = (False, "Invalid schema format")

        with self.assertRaises(ValueError) as context:
            self.service.store_temporary_entity_type(
                tenant_id="tenant-1",
                slug="invoice",
                display_name="Invoice",
                json_schema={"invalid": "schema"}
            )

        self.assertIn("Invalid JSON schema", str(context.exception))

    def test_store_temporary_entity_type_expiration_calculation(self):
        """Test that expiration time is calculated correctly"""
        temp_type = self.service.store_temporary_entity_type(
            tenant_id="tenant-1",
            slug="invoice",
            display_name="Invoice",
            json_schema={"type": "object"},
            ttl_hours=24
        )

        expected_expiry = datetime.utcnow() + timedelta(hours=24)
        time_diff = abs((temp_type.expires_at - expected_expiry).total_seconds())
        self.assertLess(time_diff, 5)  # Within 5 seconds

    def test_promote_entity_type_success(self):
        """Test successful promotion of temporary entity type"""
        # First store temporary type
        temp_type = self.service.store_temporary_entity_type(
            tenant_id="tenant-1",
            slug="customer",
            display_name="Customer",
            json_schema={"type": "object"}
        )

        # Promote to active
        active_type = self.service.promote_entity_type(
            temporary_type_id=temp_type.id,
            tenant_id="tenant-1",
            migrate_nodes=False
        )

        self.assertIsNotNone(active_type.id)
        self.assertEqual(active_type.slug, "customer")
        self.assertEqual(active_type.display_name, "Customer")
        self.assertTrue(active_type.is_active)
        self.assertEqual(active_type.version, 1)

    def test_promote_entity_type_not_found(self):
        """Test promotion fails when temporary type not found"""
        with self.assertRaises(ValueError) as context:
            self.service.promote_entity_type(
                temporary_type_id="nonexistent-id",
                tenant_id="tenant-1"
            )

        self.assertIn("not found", str(context.exception))

    def test_promote_entity_type_invalid_status(self):
        """Test promotion fails when status is not draft"""
        # Store temporary type
        temp_type = self.service.store_temporary_entity_type(
            tenant_id="tenant-1",
            slug="invoice",
            display_name="Invoice",
            json_schema={"type": "object"}
        )

        # Manually set status to promoted
        temp_type.status = "promoted"
        self.db.commit()

        # Try to promote again
        with self.assertRaises(ValueError) as context:
            self.service.promote_entity_type(
                temporary_type_id=temp_type.id,
                tenant_id="tenant-1"
            )

        self.assertIn("Cannot promote", str(context.exception))

    def test_promote_entity_type_duplicate_slug(self):
        """Test promotion fails when slug already exists"""
        # Create existing active type
        existing = EntityTypeDefinition(
            tenant_id="tenant-1",
            slug="customer",
            display_name="Customer",
            json_schema={"type": "object"},
            is_active=True,
            version=1
        )
        self.db.add(existing)
        self.db.commit()

        # Try to promote temporary type with same slug
        temp_type = self.service.store_temporary_entity_type(
            tenant_id="tenant-1",
            slug="customer",
            display_name="Customer",
            json_schema={"type": "object"}
        )

        with self.assertRaises(ValueError) as context:
            self.service.promote_entity_type(
                temporary_type_id=temp_type.id,
                tenant_id="tenant-1"
            )

        self.assertIn("already exists", str(context.exception))

    def test_reject_entity_type_success(self):
        """Test successful rejection of temporary entity type"""
        temp_type = self.service.store_temporary_entity_type(
            tenant_id="tenant-1",
            slug="rejected_type",
            display_name="Rejected Type",
            json_schema={"type": "object"}
        )

        self.service.reject_entity_type(
            temporary_type_id=temp_type.id,
            tenant_id="tenant-1",
            reason="Not needed",
            ttl_hours=1
        )

        # Refresh from database
        self.db.refresh(temp_type)
        self.assertEqual(temp_type.status, "rejected")

    def test_reject_entity_type_not_found(self):
        """Test rejection fails when type not found"""
        with self.assertRaises(ValueError) as context:
            self.service.reject_entity_type(
                temporary_type_id="nonexistent-id",
                tenant_id="tenant-1",
                reason="Test"
            )

        self.assertIn("not found", str(context.exception))

    # =========================================================================
    # Pipeline 2: Entity Node Backfill Tests
    # =========================================================================

    def test_store_temporary_entity_nodes_success(self):
        """Test successful storage of temporary entity nodes"""
        # First create temporary type
        temp_type = self.service.store_temporary_entity_type(
            tenant_id="tenant-1",
            slug="customer",
            display_name="Customer",
            json_schema={"type": "object"}
        )

        # Store nodes
        nodes = [
            {
                "name": "Customer A",
                "description": "First customer",
                "properties": {"email": "customer-a@example.com"}
            },
            {
                "name": "Customer B",
                "properties": {"email": "customer-b@example.com"}
            }
        ]

        created_nodes = self.service.store_temporary_entity_nodes(
            tenant_id="tenant-1",
            workspace_id="workspace-1",
            entity_type_slug="customer",
            nodes=nodes,
            batch_size=1000
        )

        self.assertEqual(len(created_nodes), 2)
        self.assertEqual(created_nodes[0].name, "Customer A")
        self.assertEqual(created_nodes[1].name, "Customer B")

    def test_store_temporary_entity_nodes_draft_type_not_found(self):
        """Test storage fails when draft type not found"""
        nodes = [{"name": "Test", "properties": {}}]

        with self.assertRaises(ValueError) as context:
            self.service.store_temporary_entity_nodes(
                tenant_id="tenant-1",
                workspace_id="workspace-1",
                entity_type_slug="nonexistent",
                nodes=nodes
            )

        self.assertIn("not found", str(context.exception))

    def test_batch_migrate_nodes_success(self):
        """Test successful batch migration of nodes"""
        # Create temporary type and nodes (would need proper setup)
        # This test requires full TemporaryEntityNode model setup
        # For now, test the method signature and return structure
        result = self.service.batch_migrate_nodes(
            tenant_id="tenant-1",
            workspace_id="workspace-1",
            entity_type_slug="customer",
            batch_size=1000
        )

        self.assertIsInstance(result, dict)
        self.assertIn("total_nodes", result)
        self.assertIn("migrated", result)
        self.assertIn("failed", result)
        self.assertIn("batches_processed", result)

    # =========================================================================
    # Batch Storage Tests
    # =========================================================================

    def test_batch_store_temporary_entity_types_success(self):
        """Test batch storage of multiple entity types"""
        entity_types = {
            "type1": {"title": "Type 1", "type": "object"},
            "type2": {"title": "Type 2", "type": "object"},
            "type3": {"title": "Type 3", "type": "object"}
        }

        result = self.service.batch_store_temporary_entity_types(
            tenant_id="tenant-1",
            entity_types=entity_types,
            source="batch_test",
            batch_size=2
        )

        self.assertEqual(result["total"], 3)
        self.assertEqual(result["successful"], 3)
        self.assertEqual(result["failed"], 0)
        self.assertEqual(len(result["temporary_ids"]), 3)

    def test_batch_store_temporary_entity_types_partial_failure(self):
        """Test batch storage with some failures"""
        entity_types = {
            "type1": {"title": "Type 1", "type": "object"},
            "type2": {"title": "Type 2", "type": "invalid"}  # Will fail validation
        }

        # Make validator fail for type2
        def validate_side_effect(schema):
            if schema.get("title") == "Type 2":
                return (False, "Invalid schema")
            return (True, "")

        self.mock_validator.validate_schema.side_effect = validate_side_effect

        result = self.service.batch_store_temporary_entity_types(
            tenant_id="tenant-1",
            entity_types=entity_types,
            source="batch_test"
        )

        self.assertEqual(result["total"], 2)
        self.assertEqual(result["successful"], 1)
        self.assertEqual(result["failed"], 1)

    # =========================================================================
    # TTL Cleanup Tests
    # =========================================================================

    def test_cleanup_expired_temporary_data(self):
        """Test cleanup of expired temporary data"""
        # Create expired temporary type
        temp_type = self.service.store_temporary_entity_type(
            tenant_id="tenant-1",
            slug="expired_type",
            display_name="Expired Type",
            json_schema={"type": "object"},
            ttl_hours=-1  # Already expired
        )

        # Manually set expires_at to past
        temp_type.expires_at = datetime.utcnow() - timedelta(hours=1)
        self.db.commit()

        # Run cleanup
        result = self.service.cleanup_expired_temporary_data()

        self.assertIsInstance(result, dict)
        self.assertIn("entity_types_removed", result)
        self.assertIn("nodes_removed", result)

    # =========================================================================
    # Memory Management Tests
    # =========================================================================

    def test_calculate_adaptive_batch_size_low_memory(self):
        """Test adaptive batch size for low memory"""
        batch_size = self.service.calculate_adaptive_batch_size(
            available_memory_mb=128,
            target_memory_usage_percent=70
        )

        self.assertEqual(batch_size, 100)  # Minimum for low memory

    def test_calculate_adaptive_batch_size_medium_memory(self):
        """Test adaptive batch size for medium memory"""
        batch_size = self.service.calculate_adaptive_batch_size(
            available_memory_mb=512,
            target_memory_usage_percent=70
        )

        # 512MB falls in range <1024, base_size=1000, adjusted by 70% = 700
        self.assertEqual(batch_size, 700)  # Adjusted size for 512MB

    def test_calculate_adaptive_batch_size_high_memory(self):
        """Test adaptive batch size for high memory"""
        batch_size = self.service.calculate_adaptive_batch_size(
            available_memory_mb=2048,
            target_memory_usage_percent=70
        )

        # 2048MB falls in range >=2048, base_size=5000, adjusted by 70% = 3500
        self.assertEqual(batch_size, 3500)  # Adjusted size for 2GB at 70%

    def test_calculate_adaptive_batch_size_very_high_memory(self):
        """Test adaptive batch size for very high memory"""
        batch_size = self.service.calculate_adaptive_batch_size(
            available_memory_mb=4096,
            target_memory_usage_percent=100
        )

        # 4096MB falls in range >=2048, base_size=5000, adjusted by 100% = 5000
        self.assertEqual(batch_size, 5000)  # Maximum cap

    def test_calculate_adaptive_batch_size_target_adjustment(self):
        """Test adaptive batch size with target percentage adjustment"""
        batch_size = self.service.calculate_adaptive_batch_size(
            available_memory_mb=1024,
            target_memory_usage_percent=50
        )

        # 1024MB falls in range <2048, base_size=2000, adjusted by 50% = 1000
        self.assertEqual(batch_size, 1000)

    def test_streaming_store_temporary_nodes_success(self):
        """Test streaming storage of temporary nodes"""
        # Create temporary type first
        temp_type = self.service.store_temporary_entity_type(
            tenant_id="tenant-1",
            slug="customer",
            display_name="Customer",
            json_schema={"type": "object"}
        )

        nodes = [
            {"name": f"Customer {i}", "properties": {"id": i}}
            for i in range(10)
        ]

        result = self.service.streaming_store_temporary_nodes(
            tenant_id="tenant-1",
            workspace_id="workspace-1",
            entity_type_slug="customer",
            nodes=nodes,
            batch_size=3
        )

        self.assertEqual(result["total_stored"], 10)
        self.assertEqual(result["batches_processed"], 4)  # ceil(10/3)

    def test_streaming_store_with_progress_callback(self):
        """Test streaming storage with progress callback"""
        # Create temporary type
        temp_type = self.service.store_temporary_entity_type(
            tenant_id="tenant-1",
            slug="customer",
            display_name="Customer",
            json_schema={"type": "object"}
        )

        nodes = [{"name": f"Customer {i}", "properties": {}} for i in range(5)]

        progress_updates = []

        def progress_callback(update):
            progress_updates.append(update)

        result = self.service.streaming_store_temporary_nodes(
            tenant_id="tenant-1",
            workspace_id="workspace-1",
            entity_type_slug="customer",
            nodes=nodes,
            batch_size=2,
            progress_callback=progress_callback
        )

        self.assertEqual(len(progress_updates), 3)  # 5 nodes / 2 batch size = 3 batches
        self.assertEqual(progress_updates[0]["batch"], 1)
        self.assertEqual(progress_updates[0]["batch_size"], 2)

    def test_batch_validate_schemas_all_valid(self):
        """Test batch validation of schemas with all valid"""
        schemas = {
            "schema1": {"type": "object"},
            "schema2": {"type": "object"},
            "schema3": {"type": "object"}
        }

        result = self.service.batch_validate_schemas(
            tenant_id="tenant-1",
            schemas=schemas,
            batch_size=2
        )

        self.assertEqual(result["valid"], 3)
        self.assertEqual(result["invalid"], 0)
        self.assertEqual(len(result["errors"]), 0)

    def test_batch_validate_schemas_mixed(self):
        """Test batch validation with mixed valid/invalid"""
        schemas = {
            "schema1": {"type": "object"},
            "schema2": {"invalid": "schema"},
            "schema3": {"type": "object"}
        }

        def validate_side_effect(schema):
            if "invalid" in schema:
                return (False, "Invalid schema")
            return (True, "")

        self.mock_validator.validate_schema.side_effect = validate_side_effect

        result = self.service.batch_validate_schemas(
            tenant_id="tenant-1",
            schemas=schemas
        )

        self.assertEqual(result["valid"], 2)
        self.assertEqual(result["invalid"], 1)
        self.assertEqual(len(result["errors"]), 1)


if __name__ == "__main__":
    unittest.main()
