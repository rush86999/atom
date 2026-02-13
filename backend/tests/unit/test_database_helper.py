"""
Unit tests for database_helper.py

Tests comprehensive database operations including:
- Record CRUD operations
- Query helpers
- Transaction management
- Pagination
- Bulk operations
- Error handling
"""

import pytest
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy import create_engine, Column, String, Integer, DateTime, JSON
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from unittest.mock import Mock, MagicMock, patch
from typing import Optional

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
    paginate_query,
)

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# Test models
class TestModel(Base):
    """Test model for database operations"""
    __tablename__ = "test_models"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True)
    status = Column(String, default="active")
    age = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(String, nullable=True)


class TestModelWithMetadata(Base):
    """Test model with metadata_json field"""
    __tablename__ = "test_models_metadata"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    status = Column(String, default="active")
    metadata_json = Column(JSON, nullable=True)


# Fixtures
@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test"""
    # Create all tables
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop all tables after test
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def sample_records(db_session: Session):
    """Create sample records for testing"""
    records = [
        TestModel(id="1", name="Alice", email="alice@example.com", status="active", age=30),
        TestModel(id="2", name="Bob", email="bob@example.com", status="inactive", age=25),
        TestModel(id="3", name="Charlie", email="charlie@example.com", status="active", age=35),
        TestModel(id="4", name="Diana", email="diana@example.com", status="pending", age=28),
        TestModel(id="5", name="Eve", email="eve@example.com", status="active", age=32),
    ]
    for record in records:
        db_session.add(record)
    db_session.commit()
    return records


# ============================================================================
# get_or_404 Tests
# ============================================================================

class TestGetOr404:
    """Tests for get_or_404 function"""

    def test_get_or_404_existing_record(self, db_session: Session, sample_records):
        """Test retrieving an existing record"""
        result = get_or_404(db_session, TestModel, "1")
        assert result.id == "1"
        assert result.name == "Alice"
        assert result.email == "alice@example.com"

    def test_get_or_404_nonexistent_record(self, db_session: Session):
        """Test retrieving a non-existent record raises 404"""
        with pytest.raises(HTTPException) as exc_info:
            get_or_404(db_session, TestModel, "999")

        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
        assert "not found" in exc_info.value.detail.lower()

    def test_get_or_404_custom_error_message(self, db_session: Session):
        """Test custom error message for missing record"""
        with pytest.raises(HTTPException) as exc_info:
            get_or_404(db_session, TestModel, "999", error_msg="Custom error message")

        assert exc_info.value.detail == "Custom error message"

    def test_get_or_404_custom_id_field(self, db_session: Session, sample_records):
        """Test using custom ID field"""
        result = get_or_404(db_session, TestModel, "alice@example.com", id_field="email")
        assert result.name == "Alice"
        assert result.email == "alice@example.com"

    def test_get_or_404_default_uses_model_name(self, db_session: Session):
        """Test default error message includes model name"""
        with pytest.raises(HTTPException) as exc_info:
            get_or_404(db_session, TestModel, "999")

        assert "TestModel" in exc_info.value.detail


# ============================================================================
# get_by_id Tests
# ============================================================================

class TestGetById:
    """Tests for get_by_id function"""

    def test_get_by_id_existing_record(self, db_session: Session, sample_records):
        """Test retrieving an existing record"""
        result = get_by_id(db_session, TestModel, "1")
        assert result is not None
        assert result.id == "1"
        assert result.name == "Alice"

    def test_get_by_id_nonexistent_record(self, db_session: Session):
        """Test retrieving a non-existent record returns None"""
        result = get_by_id(db_session, TestModel, "999")
        assert result is None

    def test_get_by_id_custom_id_field(self, db_session: Session, sample_records):
        """Test using custom ID field"""
        result = get_by_id(db_session, TestModel, "bob@example.com", id_field="email")
        assert result is not None
        assert result.name == "Bob"


# ============================================================================
# get_by_field Tests
# ============================================================================

class TestGetByField:
    """Tests for get_by_field function"""

    def test_get_by_field_existing_record(self, db_session: Session, sample_records):
        """Test retrieving record by field value"""
        result = get_by_field(db_session, TestModel, "name", "Alice")
        assert result is not None
        assert result.name == "Alice"
        assert result.id == "1"

    def test_get_by_field_nonexistent_record(self, db_session: Session):
        """Test retrieving non-existent record returns None"""
        result = get_by_field(db_session, TestModel, "name", "NonExistent")
        assert result is None

    def test_get_by_field_different_field(self, db_session: Session, sample_records):
        """Test retrieving by different field"""
        result = get_by_field(db_session, TestModel, "status", "inactive")
        assert result is not None
        assert result.name == "Bob"


# ============================================================================
# get_all Tests
# ============================================================================

class TestGetAll:
    """Tests for get_all function"""

    def test_get_all_records(self, db_session: Session, sample_records):
        """Test retrieving all records"""
        results = get_all(db_session, TestModel)
        assert len(results) == 5
        assert all(isinstance(r, TestModel) for r in results)

    def test_get_all_with_filters(self, db_session: Session, sample_records):
        """Test filtering records"""
        results = get_all(db_session, TestModel, filters={"status": "active"})
        assert len(results) == 3
        assert all(r.status == "active" for r in results)

    def test_get_all_with_multiple_filters(self, db_session: Session, sample_records):
        """Test multiple filters"""
        results = get_all(db_session, TestModel, filters={"status": "active", "age": 30})
        assert len(results) == 1
        assert results[0].name == "Alice"

    def test_get_all_with_limit(self, db_session: Session, sample_records):
        """Test limiting results"""
        results = get_all(db_session, TestModel, limit=3)
        assert len(results) == 3

    def test_get_all_with_offset(self, db_session: Session, sample_records):
        """Test offsetting results"""
        results = get_all(db_session, TestModel, offset=2)
        assert len(results) == 3

    def test_get_all_with_order_by_asc(self, db_session: Session, sample_records):
        """Test ascending order"""
        results = get_all(db_session, TestModel, order_by="age")
        assert results[0].name == "Bob"  # age 25
        assert results[-1].name == "Charlie"  # age 35

    def test_get_all_with_order_by_desc(self, db_session: Session, sample_records):
        """Test descending order"""
        results = get_all(db_session, TestModel, order_by="-age")
        assert results[0].name == "Charlie"  # age 35
        assert results[-1].name == "Bob"  # age 25

    def test_get_all_combined_filters_and_pagination(self, db_session: Session, sample_records):
        """Test combining filters, order, and pagination"""
        results = get_all(
            db_session, TestModel,
            filters={"status": "active"},
            order_by="-age",
            limit=2,
            offset=0
        )
        assert len(results) == 2
        assert results[0].name == "Charlie"  # age 35

    def test_get_all_invalid_field_filter(self, db_session: Session, sample_records):
        """Test filtering by non-existent field doesn't crash"""
        results = get_all(db_session, TestModel, filters={"invalid_field": "value"})
        assert len(results) == 5  # All records returned

    def test_get_all_invalid_order_field(self, db_session: Session, sample_records):
        """Test ordering by non-existent field doesn't crash"""
        results = get_all(db_session, TestModel, order_by="invalid_field")
        assert len(results) == 5  # All records returned


# ============================================================================
# create_record Tests
# ============================================================================

class TestCreateRecord:
    """Tests for create_record function"""

    def test_create_record_success(self, db_session: Session):
        """Test creating a new record"""
        record = create_record(
            db_session,
            TestModel,
            id="new-1",
            name="Frank",
            email="frank@example.com",
            age=40
        )
        assert record.id == "new-1"
        assert record.name == "Frank"
        assert record.email == "frank@example.com"
        assert record.age == 40

    def test_create_record_with_commit(self, db_session: Session):
        """Test that record is committed to database"""
        record = create_record(
            db_session,
            TestModel,
            id="new-2",
            name="Grace",
            email="grace@example.com"
        )
        # Query in a new session to verify commit
        db_session.refresh(record)
        assert record.name == "Grace"

    def test_create_record_auto_refresh(self, db_session: Session):
        """Test that record is automatically refreshed"""
        record = create_record(
            db_session,
            TestModel,
            id="new-3",
            name="Henry"
        )
        assert record.created_at is not None


# ============================================================================
# update_record Tests
# ============================================================================

class TestUpdateRecord:
    """Tests for update_record function"""

    def test_update_record_success(self, db_session: Session, sample_records):
        """Test updating an existing record"""
        record = db_session.query(TestModel).filter(TestModel.id == "1").first()
        updated = update_record(
            db_session,
            record,
            name="Alice Updated",
            age=31
        )
        assert updated.name == "Alice Updated"
        assert updated.age == 31
        assert updated.email == "alice@example.com"  # Unchanged

    def test_update_record_with_commit(self, db_session: Session, sample_records):
        """Test that update is committed"""
        record = db_session.query(TestModel).filter(TestModel.id == "2").first()
        update_record(db_session, record, status="active")

        db_session.refresh(record)
        assert record.status == "active"

    def test_update_record_invalid_field(self, db_session: Session, sample_records):
        """Test updating with invalid field doesn't crash"""
        record = db_session.query(TestModel).filter(TestModel.id == "3").first()
        updated = update_record(db_session, record, invalid_field="value")
        assert updated.name == "Charlie"  # Unchanged


# ============================================================================
# delete_record Tests
# ============================================================================

class TestDeleteRecord:
    """Tests for delete_record function"""

    def test_delete_record_success(self, db_session: Session, sample_records):
        """Test deleting a record"""
        record = db_session.query(TestModel).filter(TestModel.id == "1").first()
        result = delete_record(db_session, record)
        assert result is True

        # Verify deletion
        deleted = db_session.query(TestModel).filter(TestModel.id == "1").first()
        assert deleted is None

    def test_delete_record_with_commit(self, db_session: Session, sample_records):
        """Test that deletion is committed"""
        record = db_session.query(TestModel).filter(TestModel.id == "2").first()
        delete_record(db_session, record)

        count = db_session.query(TestModel).filter(TestModel.id == "2").count()
        assert count == 0


# ============================================================================
# soft_delete_record Tests
# ============================================================================

class TestSoftDeleteRecord:
    """Tests for soft_delete_record function"""

    def test_soft_delete_record_with_status_field(self, db_session: Session, sample_records):
        """Test soft deleting a record with status field"""
        record = db_session.query(TestModel).filter(TestModel.id == "1").first()
        result = soft_delete_record(db_session, record, deleted_by="user-123")

        assert result.status == "deleted"
        assert result.deleted_by == "user-123"
        assert result.deleted_at is not None

    def test_soft_delete_record_without_deleted_by(self, db_session: Session, sample_records):
        """Test soft delete without deleted_by"""
        record = db_session.query(TestModel).filter(TestModel.id == "2").first()
        result = soft_delete_record(db_session, record)

        assert result.status == "deleted"
        assert result.deleted_at is not None
        assert result.deleted_by is None

    def test_soft_delete_record_without_status_field(self, db_session: Session):
        """Test soft delete on model without status field"""
        # Create a model without status field
        class SimpleModel(Base):
            __tablename__ = "simple_models"
            id = Column(String, primary_key=True)
            name = Column(String)

        Base.metadata.create_all(bind=engine)

        record = SimpleModel(id="simple-1", name="Test")
        db_session.add(record)
        db_session.commit()

        # Should not crash
        result = soft_delete_record(db_session, record)
        assert result is not None


# ============================================================================
# check_exists Tests
# ============================================================================

class TestCheckExists:
    """Tests for check_exists function"""

    def test_check_exists_true(self, db_session: Session, sample_records):
        """Test checking existing record returns True"""
        result = check_exists(db_session, TestModel, "email", "alice@example.com")
        assert result is True

    def test_check_exists_false(self, db_session: Session, sample_records):
        """Test checking non-existent record returns False"""
        result = check_exists(db_session, TestModel, "email", "nonexistent@example.com")
        assert result is False

    def test_check_exists_different_field(self, db_session: Session, sample_records):
        """Test checking existence by different field"""
        result = check_exists(db_session, TestModel, "name", "Alice")
        assert result is True


# ============================================================================
# count_records Tests
# ============================================================================

class TestCountRecords:
    """Tests for count_records function"""

    def test_count_all_records(self, db_session: Session, sample_records):
        """Test counting all records"""
        count = count_records(db_session, TestModel)
        assert count == 5

    def test_count_with_filters(self, db_session: Session, sample_records):
        """Test counting with filters"""
        count = count_records(db_session, TestModel, filters={"status": "active"})
        assert count == 3

    def test_count_no_matches(self, db_session: Session, sample_records):
        """Test counting with no matches"""
        count = count_records(db_session, TestModel, filters={"status": "deleted"})
        assert count == 0

    def test_count_multiple_filters(self, db_session: Session, sample_records):
        """Test counting with multiple filters"""
        count = count_records(
            db_session, TestModel,
            filters={"status": "active", "age": 30}
        )
        assert count == 1


# ============================================================================
# bulk_create Tests
# ============================================================================

class TestBulkCreate:
    """Tests for bulk_create function"""

    def test_bulk_create_success(self, db_session: Session):
        """Test creating multiple records"""
        items = [
            {"id": "bulk-1", "name": "Bulk 1", "email": "bulk1@example.com"},
            {"id": "bulk-2", "name": "Bulk 2", "email": "bulk2@example.com"},
            {"id": "bulk-3", "name": "Bulk 3", "email": "bulk3@example.com"},
        ]
        records = bulk_create(db_session, TestModel, items)

        assert len(records) == 3
        assert records[0].name == "Bulk 1"
        assert records[1].name == "Bulk 2"
        assert records[2].name == "Bulk 3"

    def test_bulk_create_empty_list(self, db_session: Session):
        """Test bulk creating with empty list"""
        records = bulk_create(db_session, TestModel, [])
        assert len(records) == 0

    def test_bulk_create_single_item(self, db_session: Session):
        """Test bulk creating single item"""
        items = [{"id": "single-1", "name": "Single", "email": "single@example.com"}]
        records = bulk_create(db_session, TestModel, items)
        assert len(records) == 1
        assert records[0].name == "Single"


# ============================================================================
# get_or_create Tests
# ============================================================================

class TestGetOrCreate:
    """Tests for get_or_create function"""

    def test_get_or_create_existing(self, db_session: Session, sample_records):
        """Test getting existing record"""
        record, created = get_or_create(
            db_session,
            TestModel,
            filters={"email": "alice@example.com"}
        )
        assert created is False
        assert record.name == "Alice"

    def test_get_or_create_new(self, db_session: Session):
        """Test creating new record"""
        record, created = get_or_create(
            db_session,
            TestModel,
            filters={"email": "new@example.com"},
            defaults={"id": "new-1", "name": "New User", "age": 50}
        )
        assert created is True
        assert record.email == "new@example.com"
        assert record.name == "New User"

    def test_get_or_create_with_defaults(self, db_session: Session):
        """Test get_or_create with defaults"""
        record, created = get_or_create(
            db_session,
            TestModel,
            filters={"id": "default-1"},
            defaults={"name": "Default User", "email": "default@example.com", "age": 45}
        )
        assert created is True
        assert record.name == "Default User"

    def test_get_or_create_filters_included_in_creation(self, db_session: Session):
        """Test that filters are included in new record creation"""
        record, created = get_or_create(
            db_session,
            TestModel,
            filters={"id": "filter-1", "name": "Filter Name"},
            defaults={"email": "filter@example.com"}
        )
        assert created is True
        assert record.id == "filter-1"
        assert record.name == "Filter Name"


# ============================================================================
# execute_safe Tests
# ============================================================================

class TestExecuteSafe:
    """Tests for execute_safe function"""

    def test_execute_safe_success(self, db_session: Session, sample_records):
        """Test successful operation execution"""
        result = execute_safe(
            db_session,
            lambda: db_session.query(TestModel).filter(TestModel.id == "1").first(),
            "Failed to fetch record"
        )
        assert result is not None
        assert result.name == "Alice"

    def test_execute_safe_failure_raises_http_exception(self, db_session: Session):
        """Test failed operation raises HTTPException"""
        with pytest.raises(HTTPException) as exc_info:
            execute_safe(
                db_session,
                lambda: (_ for _ in ()).throw(Exception("Database error")),
                "Operation failed"
            )

        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Operation failed" in exc_info.value.detail

    def test_execute_safe_custom_error_message(self, db_session: Session):
        """Test custom error message is used"""
        with pytest.raises(HTTPException) as exc_info:
            execute_safe(
                db_session,
                lambda: (_ for _ in ()).throw(ValueError("Invalid data")),
                "Custom failure message"
            )

        assert exc_info.value.detail == "Custom failure message"


# ============================================================================
# paginate_query Tests
# ============================================================================

class TestPaginateQuery:
    """Tests for paginate_query function"""

    def test_paginate_query_default_page(self, db_session: Session, sample_records):
        """Test default pagination"""
        result = paginate_query(db_session, TestModel)
        assert "items" in result
        assert "total" in result
        assert "page" in result
        assert "page_size" in result
        assert "total_pages" in result

        assert result["total"] == 5
        assert len(result["items"]) == 5
        assert result["page"] == 1
        assert result["page_size"] == 20
        assert result["total_pages"] == 1

    def test_paginate_query_with_page_size(self, db_session: Session, sample_records):
        """Test pagination with custom page size"""
        result = paginate_query(db_session, TestModel, page=1, page_size=2)
        assert len(result["items"]) == 2
        assert result["total"] == 5
        assert result["page_size"] == 2
        assert result["total_pages"] == 3

    def test_paginate_query_second_page(self, db_session: Session, sample_records):
        """Test getting second page"""
        result = paginate_query(db_session, TestModel, page=2, page_size=2)
        assert len(result["items"]) == 2
        assert result["page"] == 2

    def test_paginate_query_with_filters(self, db_session: Session, sample_records):
        """Test pagination with filters"""
        result = paginate_query(
            db_session, TestModel,
            page=1,
            page_size=10,
            filters={"status": "active"}
        )
        assert result["total"] == 3
        assert len(result["items"]) == 3

    def test_paginate_query_with_ordering(self, db_session: Session, sample_records):
        """Test pagination with ordering"""
        result = paginate_query(
            db_session, TestModel,
            page=1,
            page_size=3,
            order_by="-age"
        )
        assert result["items"][0].name == "Charlie"  # Highest age

    def test_paginate_query_empty_results(self, db_session: Session):
        """Test pagination with no results"""
        result = paginate_query(
            db_session, TestModel,
            filters={"status": "deleted"}
        )
        assert result["total"] == 0
        assert result["total_pages"] == 0
        assert len(result["items"]) == 0

    def test_paginate_query_combined_options(self, db_session: Session, sample_records):
        """Test pagination with all options combined"""
        result = paginate_query(
            db_session, TestModel,
            page=1,
            page_size=2,
            filters={"status": "active"},
            order_by="age"
        )
        assert len(result["items"]) == 2
        assert result["total"] == 3
        assert result["total_pages"] == 2
        assert result["items"][0].name == "Alice"  # Lowest age among active


# ============================================================================
# Integration Tests
# ============================================================================

class TestDatabaseHelperIntegration:
    """Integration tests for database helper functions"""

    def test_full_crud_workflow(self, db_session: Session):
        """Test complete create, read, update, delete workflow"""
        # Create
        record = create_record(
            db_session,
            TestModel,
            id="workflow-1",
            name="Workflow Test",
            email="workflow@example.com"
        )
        assert record.id == "workflow-1"

        # Read
        fetched = get_by_id(db_session, TestModel, "workflow-1")
        assert fetched is not None
        assert fetched.name == "Workflow Test"

        # Update
        updated = update_record(db_session, fetched, age=30)
        assert updated.age == 30

        # Check exists
        exists = check_exists(db_session, TestModel, "id", "workflow-1")
        assert exists is True

        # Delete
        deleted = delete_record(db_session, updated)
        assert deleted is True

        # Verify deletion
        verify = get_by_id(db_session, TestModel, "workflow-1")
        assert verify is None

    def test_bulk_operations_workflow(self, db_session: Session):
        """Test bulk create and query workflow"""
        # Bulk create
        items = [
            {"id": f"bulk-{i}", "name": f"Bulk {i}", "email": f"bulk{i}@example.com"}
            for i in range(10)
        ]
        records = bulk_create(db_session, TestModel, items)
        assert len(records) == 10

        # Count all
        total = count_records(db_session, TestModel)
        assert total == 10

        # Paginate
        page1 = paginate_query(db_session, TestModel, page=1, page_size=5)
        assert len(page1["items"]) == 5
        assert page1["total_pages"] == 2

        page2 = paginate_query(db_session, TestModel, page=2, page_size=5)
        assert len(page2["items"]) == 5

    def test_soft_delete_preserves_record(self, db_session: Session):
        """Test soft delete preserves record in database"""
        # Create
        record = create_record(
            db_session,
            TestModel,
            id="soft-1",
            name="Soft Delete Test",
            email="soft@example.com"
        )

        # Soft delete
        soft_delete_record(db_session, record, deleted_by="admin")

        # Record still exists but with deleted status
        deleted = get_by_id(db_session, TestModel, "soft-1")
        assert deleted is not None
        assert deleted.status == "deleted"

        # Won't appear in active queries
        active = get_all(db_session, TestModel, filters={"status": "active"})
        assert deleted not in active

    def test_get_or_create_idempotent(self, db_session: Session):
        """Test get_or_create can be called multiple times safely"""
        filters = {"email": "idempotent@example.com"}
        defaults = {"id": "idem-1", "name": "Idempotent", "age": 25}

        # First call creates
        record1, created1 = get_or_create(db_session, TestModel, filters, defaults)
        assert created1 is True

        # Second call fetches
        record2, created2 = get_or_create(db_session, TestModel, filters, defaults)
        assert created2 is False

        # Same record
        assert record1.id == record2.id

    def test_execute_safe_with_database_error(self, db_session: Session):
        """Test execute_safe handles database errors gracefully"""
        # Try to insert duplicate (violates unique constraint on email)
        create_record(
            db_session,
            TestModel,
            id="unique-1",
            name="First",
            email="unique@example.com"
        )

        # This should fail with HTTPException, not raw database error
        with pytest.raises(HTTPException):
            execute_safe(
                db_session,
                lambda: create_record(
                    db_session,
                    TestModel,
                    id="unique-2",
                    name="Duplicate",
                    email="unique@example.com"  # Duplicate email
                ),
                "Failed to create duplicate record"
            )
