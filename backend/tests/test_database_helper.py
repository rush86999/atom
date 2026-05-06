"""
Comprehensive test suite for Database Helper Module

Tests common database operations including CRUD helpers,
pagination, existence checks, batch operations, and error handling.
"""

import os
import sys
import unittest
from datetime import datetime
from unittest.mock import Mock

sys.path.append(os.getcwd())

from core.database import Base
from core.database_helper import (
    get_or_404,
    get_by_id,
    get_by_field,
    get_all,
    create_record,
    update_record,
    delete_record,
    soft_delete_record,
    check_exists,
    count_records,
    bulk_create,
    get_or_create,
    execute_safe,
    paginate_query
)
from core.models import Workspace, AgentRegistry
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class TestDatabaseHelper(unittest.TestCase):
    """Test suite for database helper functions"""

    def setUp(self):
        """Setup test database"""
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)
        self.db = self.SessionLocal()

    def tearDown(self):
        """Cleanup database session"""
        self.db.close()
        self.engine.dispose()

    # =========================================================================
    # Query Helper Tests
    # =========================================================================

    def test_get_or_404_success(self):
        """Test get_or_404 returns record when found"""
        workspace = Workspace(id="ws-1", name="Test Workspace")
        self.db.add(workspace)
        self.db.commit()

        result = get_or_404(self.db, Workspace, "ws-1")

        self.assertEqual(result.id, "ws-1")
        self.assertEqual(result.name, "Test Workspace")

    def test_get_or_404_not_found(self):
        """Test get_or_404 raises 404 when record not found"""
        with self.assertRaises(HTTPException) as context:
            get_or_404(self.db, Workspace, "nonexistent")

        self.assertEqual(context.exception.status_code, 404)
        self.assertIn("not found", context.exception.detail.lower())

    def test_get_or_404_custom_error_message(self):
        """Test get_or_404 with custom error message"""
        with self.assertRaises(HTTPException) as context:
            get_or_404(self.db, Workspace, "nonexistent", "Workspace not found")

        self.assertEqual(context.exception.detail, "Workspace not found")

    def test_get_or_404_custom_id_field(self):
        """Test get_or_404 with custom ID field"""
        workspace = Workspace(id="ws-1", name="custom-name")
        self.db.add(workspace)
        self.db.commit()

        result = get_or_404(self.db, Workspace, "custom-name", id_field="name")

        self.assertEqual(result.name, "custom-name")

    def test_get_by_id_found(self):
        """Test get_by_id returns record when found"""
        workspace = Workspace(id="ws-1", name="Test Workspace")
        self.db.add(workspace)
        self.db.commit()

        result = get_by_id(self.db, Workspace, "ws-1")

        self.assertIsNotNone(result)
        self.assertEqual(result.id, "ws-1")

    def test_get_by_id_not_found(self):
        """Test get_by_id returns None when not found"""
        result = get_by_id(self.db, Workspace, "nonexistent")

        self.assertIsNone(result)

    def test_get_by_field_success(self):
        """Test get_by_field with field lookup"""
        workspace = Workspace(id="ws-1", name="Unique Name")
        self.db.add(workspace)
        self.db.commit()

        result = get_by_field(self.db, Workspace, "name", "Unique Name")

        self.assertIsNotNone(result)
        self.assertEqual(result.name, "Unique Name")

    def test_get_by_field_not_found(self):
        """Test get_by_field returns None when not found"""
        result = get_by_field(self.db, Workspace, "name", "Nonexistent")

        self.assertIsNone(result)

    # =========================================================================
    # Query Multiple Records Tests
    # =========================================================================

    def test_get_all_no_filters(self):
        """Test get_all returns all records"""
        for i in range(3):
            workspace = Workspace(id=f"ws-{i}", name=f"Workspace {i}")
            self.db.add(workspace)
        self.db.commit()

        results = get_all(self.db, Workspace)

        self.assertEqual(len(results), 3)

    def test_get_all_with_filters(self):
        """Test get_all with field filters"""
        ws1 = Workspace(id="ws-1", name="Active Workspace")
        ws2 = Workspace(id="ws-2", name="Inactive Workspace")
        self.db.add_all([ws1, ws2])
        self.db.commit()

        results = get_all(self.db, Workspace, filters={"name": "Active Workspace"})

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Active Workspace")

    def test_get_all_with_limit(self):
        """Test get_all with limit"""
        for i in range(5):
            workspace = Workspace(id=f"ws-{i}", name=f"Workspace {i}")
            self.db.add(workspace)
        self.db.commit()

        results = get_all(self.db, Workspace, limit=3)

        self.assertEqual(len(results), 3)

    def test_get_all_with_offset(self):
        """Test get_all with offset"""
        for i in range(5):
            workspace = Workspace(id=f"ws-{i}", name=f"Workspace {i}")
            self.db.add(workspace)
        self.db.commit()

        results = get_all(self.db, Workspace, offset=2)

        self.assertEqual(len(results), 3)

    def test_get_all_with_order_by_asc(self):
        """Test get_all with ascending order"""
        for i in range(3):
            workspace = Workspace(id=f"ws-{i}", name=f"Workspace {i}")
            self.db.add(workspace)
        self.db.commit()

        results = get_all(self.db, Workspace, order_by="name")

        self.assertEqual(results[0].name, "Workspace 0")
        self.assertEqual(results[2].name, "Workspace 2")

    def test_get_all_with_order_by_desc(self):
        """Test get_all with descending order"""
        for i in range(3):
            workspace = Workspace(id=f"ws-{i}", name=f"Workspace {i}")
            self.db.add(workspace)
        self.db.commit()

        results = get_all(self.db, Workspace, order_by="-name")

        self.assertEqual(results[0].name, "Workspace 2")
        self.assertEqual(results[2].name, "Workspace 0")

    # =========================================================================
    # Create, Update, Delete Tests
    # =========================================================================

    def test_create_record_success(self):
        """Test create_record creates and returns new record"""
        workspace = create_record(
            self.db,
            Workspace,
            id="ws-1",
            name="New Workspace"
        )

        self.assertIsNotNone(workspace.id)
        self.assertEqual(workspace.name, "New Workspace")

        # Verify it's in database
        retrieved = self.db.query(Workspace).filter_by(id="ws-1").first()
        self.assertIsNotNone(retrieved)

    def test_update_record_success(self):
        """Test update_record updates fields"""
        workspace = Workspace(id="ws-1", name="Original Name")
        self.db.add(workspace)
        self.db.commit()

        updated = update_record(
            self.db,
            workspace,
            name="Updated Name"
        )

        self.assertEqual(updated.name, "Updated Name")

    def test_update_record_invalid_field(self):
        """Test update_record ignores invalid fields"""
        workspace = Workspace(id="ws-1", name="Original Name")
        self.db.add(workspace)
        self.db.commit()

        # Should not raise error, just ignore non-existent field
        updated = update_record(
            self.db,
            workspace,
            name="Updated Name",
            nonexistent_field="value"
        )

        self.assertEqual(updated.name, "Updated Name")
        self.assertFalse(hasattr(updated, "nonexistent_field"))

    def test_delete_record_success(self):
        """Test delete_record removes record"""
        workspace = Workspace(id="ws-1", name="To Delete")
        self.db.add(workspace)
        self.db.commit()

        result = delete_record(self.db, workspace)

        self.assertTrue(result)

        # Verify it's gone
        retrieved = self.db.query(Workspace).filter_by(id="ws-1").first()
        self.assertIsNone(retrieved)

    def test_soft_delete_record_with_status_field(self):
        """Test soft_delete_record sets status to deleted"""
        # Use AgentRegistry which has status field
        agent = AgentRegistry(
            id="agent-1",
            name="Test Agent",
            category="test",
            module_path="test",
            class_name="TestClass",
            status="active"
        )
        self.db.add(agent)
        self.db.commit()

        soft_delete_record(self.db, agent, deleted_by="user-1")

        self.assertEqual(agent.status, "deleted")
        # deleted_by and deleted_at may not exist on AgentRegistry
        # Just verify status was changed

    def test_soft_delete_record_without_status_field(self):
        """Test soft_delete_record with model without status field"""
        workspace = Workspace(id="ws-1", name="Test Workspace")
        self.db.add(workspace)
        self.db.commit()

        # Should not raise error even though Workspace has no status field
        soft_delete_record(self.db, workspace)

        # Workspace should still exist
        retrieved = self.db.query(Workspace).filter_by(id="ws-1").first()
        self.assertIsNotNone(retrieved)

    # =========================================================================
    # Existence and Count Tests
    # =========================================================================

    def test_check_exists_true(self):
        """Test check_exists returns True when record exists"""
        workspace = Workspace(id="ws-1", name="Test Workspace")
        self.db.add(workspace)
        self.db.commit()

        result = check_exists(self.db, Workspace, "id", "ws-1")

        self.assertTrue(result)

    def test_check_exists_false(self):
        """Test check_exists returns False when record doesn't exist"""
        result = check_exists(self.db, Workspace, "id", "nonexistent")

        self.assertFalse(result)

    def test_count_records_all(self):
        """Test count_records counts all records"""
        for i in range(5):
            workspace = Workspace(id=f"ws-{i}", name=f"Workspace {i}")
            self.db.add(workspace)
        self.db.commit()

        count = count_records(self.db, Workspace)

        self.assertEqual(count, 5)

    def test_count_records_with_filters(self):
        """Test count_records with filters"""
        ws1 = Workspace(id="ws-1", name="Active")
        ws2 = Workspace(id="ws-2", name="Active")
        ws3 = Workspace(id="ws-3", name="Inactive")
        self.db.add_all([ws1, ws2, ws3])
        self.db.commit()

        count = count_records(self.db, Workspace, filters={"name": "Active"})

        self.assertEqual(count, 2)

    # =========================================================================
    # Batch Operations Tests
    # =========================================================================

    def test_bulk_create_success(self):
        """Test bulk_create creates multiple records"""
        items = [
            {"id": "ws-1", "name": "Workspace 1"},
            {"id": "ws-2", "name": "Workspace 2"},
            {"id": "ws-3", "name": "Workspace 3"}
        ]

        records = bulk_create(self.db, Workspace, items)

        self.assertEqual(len(records), 3)
        self.assertEqual(records[0].name, "Workspace 1")
        self.assertEqual(records[1].name, "Workspace 2")
        self.assertEqual(records[2].name, "Workspace 3")

    def test_get_or_create_existing(self):
        """Test get_or_create returns existing record"""
        workspace = Workspace(id="ws-1", name="Test Workspace")
        self.db.add(workspace)
        self.db.commit()

        record, created = get_or_create(
            self.db,
            Workspace,
            filters={"id": "ws-1"},
            defaults={"name": "Default Name"}
        )

        self.assertFalse(created)
        self.assertEqual(record.name, "Test Workspace")

    def test_get_or_create_new(self):
        """Test get_or_create creates new record"""
        record, created = get_or_create(
            self.db,
            Workspace,
            filters={"id": "ws-1"},
            defaults={"name": "New Workspace"}
        )

        self.assertTrue(created)
        self.assertEqual(record.name, "New Workspace")
        self.assertEqual(record.id, "ws-1")

    # =========================================================================
    # Error Handling Tests
    # =========================================================================

    def test_execute_safe_success(self):
        """Test execute_safe executes operation successfully"""
        workspace = Workspace(id="ws-1", name="Test")
        self.db.add(workspace)
        self.db.commit()

        result = execute_safe(
            self.db,
            lambda: self.db.query(Workspace).filter_by(id="ws-1").first(),
            "Failed to fetch workspace"
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.id, "ws-1")

    def test_execute_safe_failure(self):
        """Test execute_safe raises HTTPException on failure"""
        with self.assertRaises(HTTPException) as context:
            execute_safe(
                self.db,
                lambda: (_ for _ in ()).throw(Exception("Database error")),
                "Operation failed"
            )

        self.assertEqual(context.exception.status_code, 500)
        self.assertIn("Operation failed", context.exception.detail)

    # =========================================================================
    # Pagination Tests
    # =========================================================================

    def test_paginate_query_first_page(self):
        """Test paginate_query returns first page"""
        for i in range(25):
            workspace = Workspace(id=f"ws-{i}", name=f"Workspace {i}")
            self.db.add(workspace)
        self.db.commit()

        result = paginate_query(
            self.db,
            Workspace,
            page=1,
            page_size=10
        )

        self.assertEqual(len(result["items"]), 10)
        self.assertEqual(result["total"], 25)
        self.assertEqual(result["page"], 1)
        self.assertEqual(result["page_size"], 10)
        self.assertEqual(result["total_pages"], 3)

    def test_paginate_query_last_page(self):
        """Test paginate_query returns last page with remaining items"""
        for i in range(25):
            workspace = Workspace(id=f"ws-{i}", name=f"Workspace {i}")
            self.db.add(workspace)
        self.db.commit()

        result = paginate_query(
            self.db,
            Workspace,
            page=3,
            page_size=10
        )

        self.assertEqual(len(result["items"]), 5)  # Remaining items
        self.assertEqual(result["total"], 25)
        self.assertEqual(result["page"], 3)
        self.assertEqual(result["total_pages"], 3)

    def test_paginate_query_with_filters(self):
        """Test paginate_query with filters"""
        for i in range(10):
            workspace = Workspace(
                id=f"ws-{i}",
                name=f"Workspace {i}" if i % 2 == 0 else "Other"
            )
            self.db.add(workspace)
        self.db.commit()

        result = paginate_query(
            self.db,
            Workspace,
            page=1,
            page_size=5,
            filters={"name": "Workspace 0"}
        )

        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["total"], 1)

    def test_paginate_query_with_ordering(self):
        """Test paginate_query with ordering"""
        for i in range(10):
            workspace = Workspace(id=f"ws-{i}", name=f"Workspace {i}")
            self.db.add(workspace)
        self.db.commit()

        result = paginate_query(
            self.db,
            Workspace,
            page=1,
            page_size=5,
            order_by="-name"
        )

        self.assertEqual(result["items"][0].name, "Workspace 9")
        self.assertEqual(result["items"][4].name, "Workspace 5")

    def test_paginate_query_empty_result(self):
        """Test paginate_query with no matching records"""
        result = paginate_query(
            self.db,
            Workspace,
            page=1,
            page_size=10
        )

        self.assertEqual(len(result["items"]), 0)
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["total_pages"], 0)


if __name__ == "__main__":
    unittest.main()
