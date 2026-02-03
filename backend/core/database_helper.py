"""
Database Helper Module

Provides common database operations to reduce code duplication across
the Atom platform. This module standardizes database queries, error handling,
and common patterns.

Usage:
    from core.database_helper import get_or_404, get_by_id, create_with_audit

    # Get entity or raise 404
    agent = get_or_404(db, AgentRegistry, agent_id, "Agent not found")

    # Get by ID (returns None if not found)
    user = get_by_id(db, User, user_id)

    # Create with automatic tracking
    agent = create_with_audit(db, AgentRegistry, name="My Agent", created_by=user_id)
"""

import logging
from typing import Type, TypeVar, Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from fastapi import HTTPException, status

from core.database import Base

logger = logging.getLogger(__name__)

# Generic type for SQLAlchemy models
ModelType = TypeVar("ModelType", bound=Base)


def get_or_404(
    db: Session,
    model: Type[ModelType],
    id: str,
    error_msg: Optional[str] = None,
    id_field: str = "id"
) -> ModelType:
    """
    Get a database record by ID or raise 404 HTTPException.

    This is the most common database operation pattern, used 20+ times
    across the codebase. This helper standardizes the implementation.

    Args:
        db: Database session
        model: SQLAlchemy model class
        id: ID value to search for
        error_msg: Custom error message (default: "{ModelName} not found")
        id_field: Field name to search (default: "id")

    Returns:
        The model instance

    Raises:
        HTTPException: 404 if record not found

    Example:
        agent = get_or_404(db, AgentRegistry, agent_id)
        user = get_or_404(db, User, user_id, "User not found", id_field="id")
    """
    result = db.query(model).filter(getattr(model, id_field) == id).first()

    if not result:
        model_name = model.__name__
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error_msg or f"{model_name} not found"
        )

    return result


def get_by_id(
    db: Session,
    model: Type[ModelType],
    id: str,
    id_field: str = "id"
) -> Optional[ModelType]:
    """
    Get a database record by ID, returning None if not found.

    Unlike get_or_404, this doesn't raise an exception for missing records.

    Args:
        db: Database session
        model: SQLAlchemy model class
        id: ID value to search for
        id_field: Field name to search (default: "id")

    Returns:
        The model instance or None

    Example:
        user = get_by_id(db, User, user_id)
        if user:
            # Process user
    """
    return db.query(model).filter(getattr(model, id_field) == id).first()


def get_by_field(
    db: Session,
    model: Type[ModelType],
    field_name: str,
    value: Any
) -> Optional[ModelType]:
    """
    Get a database record by a specific field value.

    Args:
        db: Database session
        model: SQLAlchemy model class
        field_name: Field name to search
        value: Value to match

    Returns:
        The model instance or None

    Example:
        user = get_by_field(db, User, "email", "user@example.com")
        workspace = get_by_field(db, Workspace, "name", "My Workspace")
    """
    return db.query(model).filter(getattr(model, field_name) == value).first()


def get_all(
    db: Session,
    model: Type[ModelType],
    filters: Optional[Dict[str, Any]] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    order_by: Optional[str] = None
) -> List[ModelType]:
    """
    Get multiple records with optional filtering and pagination.

    Args:
        db: Database session
        model: SQLAlchemy model class
        filters: Dict of field_name=value filters
        limit: Maximum number of records to return
        offset: Number of records to skip
        order_by: Field name to order by (prefix with "-" for desc)

    Returns:
        List of model instances

    Example:
        # Get all active agents
        agents = get_all(db, AgentRegistry, filters={"status": "active"})

        # Get recent executions with pagination
        executions = get_all(
            db,
            AgentExecution,
            filters={"agent_id": agent_id},
            order_by="-created_at",
            limit=10
        )
    """
    query = db.query(model)

    # Apply filters
    if filters:
        for field_name, value in filters.items():
            if hasattr(model, field_name):
                query = query.filter(getattr(model, field_name) == value)

    # Apply ordering
    if order_by:
        if order_by.startswith("-"):
            # Descending order
            field_name = order_by[1:]
            if hasattr(model, field_name):
                query = query.order_by(getattr(model, field_name).desc())
        else:
            # Ascending order
            if hasattr(model, order_by):
                query = query.order_by(getattr(model, order_by).asc())

    # Apply pagination
    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)

    return query.all()


def create_record(
    db: Session,
    model: Type[ModelType],
    **kwargs
) -> ModelType:
    """
    Create a new database record with automatic commit.

    Args:
        db: Database session
        model: SQLAlchemy model class
        **kwargs: Field values for the new record

    Returns:
        Created model instance

    Example:
        agent = create_record(
            db,
            AgentRegistry,
            name="My Agent",
            maturity_level="INTERN",
            created_by="user-123"
        )
    """
    record = model(**kwargs)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def update_record(
    db: Session,
    record: ModelType,
    **kwargs
) -> ModelType:
    """
    Update a database record with automatic commit.

    Args:
        db: Database session
        record: Model instance to update
        **kwargs: Field values to update

    Returns:
        Updated model instance

    Example:
        agent = get_or_404(db, AgentRegistry, agent_id)
        update_record(
            db,
            agent,
            maturity_level="SUPERVISED",
            confidence_score=0.85
        )
    """
    for field_name, value in kwargs.items():
        if hasattr(record, field_name):
            setattr(record, field_name, value)

    db.commit()
    db.refresh(record)
    return record


def delete_record(
    db: Session,
    record: ModelType
) -> bool:
    """
    Delete a database record with automatic commit.

    Args:
        db: Database session
        record: Model instance to delete

    Returns:
        True if deleted successfully

    Example:
        agent = get_or_404(db, AgentRegistry, agent_id)
        delete_record(db, agent)
    """
    db.delete(record)
    db.commit()
    return True


def soft_delete_record(
    db: Session,
    record: ModelType,
    deleted_by: Optional[str] = None
) -> ModelType:
    """
    Soft delete a record by setting status to "deleted" (if supported).

    This is preferred over hard deletion for audit purposes.

    Args:
        db: Database session
        record: Model instance to soft delete
        deleted_by: User ID who performed the deletion

    Returns:
        Updated model instance

    Example:
        agent = get_or_404(db, AgentRegistry, agent_id)
        soft_delete_record(db, agent, deleted_by=user_id)
    """
    if hasattr(record, "status"):
        record.status = "deleted"

    if hasattr(record, "deleted_by") and deleted_by:
        record.deleted_by = deleted_by

    if hasattr(record, "deleted_at"):
        from datetime import datetime
        record.deleted_at = datetime.now()

    db.commit()
    db.refresh(record)
    return record


def check_exists(
    db: Session,
    model: Type[ModelType],
    field_name: str,
    value: Any
) -> bool:
    """
    Check if a record exists with the given field value.

    More efficient than get_by_field when you only need to know existence.

    Args:
        db: Database session
        model: SQLAlchemy model class
        field_name: Field name to check
        value: Value to match

    Returns:
        True if record exists, False otherwise

    Example:
        if check_exists(db, User, "email", "user@example.com"):
            raise HTTPException(400, "Email already exists")
    """
    return db.query(model).filter(getattr(model, field_name) == value).first() is not None


def count_records(
    db: Session,
    model: Type[ModelType],
    filters: Optional[Dict[str, Any]] = None
) -> int:
    """
    Count records matching the given filters.

    Args:
        db: Database session
        model: SQLAlchemy model class
        filters: Dict of field_name=value filters

    Returns:
        Count of matching records

    Example:
        active_agents = count_records(db, AgentRegistry, {"status": "active"})
        total_executions = count_records(db, AgentExecution)
    """
    query = db.query(model)

    if filters:
        for field_name, value in filters.items():
            if hasattr(model, field_name):
                query = query.filter(getattr(model, field_name) == value)

    return query.count()


def bulk_create(
    db: Session,
    model: Type[ModelType],
    items: List[Dict[str, Any]]
) -> List[ModelType]:
    """
    Create multiple records in a single transaction.

    Args:
        db: Database session
        model: SQLAlchemy model class
        items: List of dicts with field values

    Returns:
        List of created model instances

    Example:
        agents = bulk_create(
            db,
            AgentRegistry,
            [
                {"name": "Agent 1", "maturity_level": "INTERN"},
                {"name": "Agent 2", "maturity_level": "STUDENT"}
            ]
        )
    """
    records = [model(**item) for item in items]
    db.add_all(records)
    db.commit()

    for record in records:
        db.refresh(record)

    return records


def get_or_create(
    db: Session,
    model: Type[ModelType],
    filters: Dict[str, Any],
    defaults: Optional[Dict[str, Any]] = None
) -> tuple[ModelType, bool]:
    """
    Get a record matching filters, or create it if it doesn't exist.

    Args:
        db: Database session
        model: SQLAlchemy model class
        filters: Fields to match for existing record
        defaults: Default values for new record (if created)

    Returns:
        Tuple of (record, created) where created is True if new record was created

    Example:
        workspace, created = get_or_create(
            db,
            Workspace,
            filters={"name": "Default Workspace"},
            defaults={"status": "active"}
        )

        if created:
            logger.info(f"Created new workspace: {workspace.id}")
    """
    record = db.query(model).filter_by(**filters).first()

    if record:
        return record, False

    # Create new record
    create_params = {**filters, **(defaults or {})}
    record = model(**create_params)
    db.add(record)
    db.commit()
    db.refresh(record)

    return record, True


def execute_safe(
    db: Session,
    operation: callable,
    error_message: str = "Database operation failed"
) -> Any:
    """
    Execute a database operation with standardized error handling.

    Args:
        db: Database session
        operation: Callable that performs the database operation
        error_message: Custom error message for exceptions

    Returns:
        Result of the operation

    Raises:
        HTTPException: 500 if operation fails

    Example:
        result = execute_safe(
            db,
            lambda: db.query(AgentRegistry).filter(...).all(),
            "Failed to fetch agents"
        )
    """
    try:
        return operation()
    except Exception as e:
        logger.error(f"{error_message}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_message
        )


def paginate_query(
    db: Session,
    model: Type[ModelType],
    page: int = 1,
    page_size: int = 20,
    filters: Optional[Dict[str, Any]] = None,
    order_by: Optional[str] = None
) -> Dict[str, Any]:
    """
    Paginated query with metadata.

    Args:
        db: Database session
        model: SQLAlchemy model class
        page: Page number (1-indexed)
        page_size: Number of items per page
        filters: Optional field filters
        order_by: Optional field ordering

    Returns:
        Dict with items, total, page, page_size, total_pages

    Example:
        result = paginate_query(
            db,
            AgentExecution,
            page=1,
            page_size=10,
            filters={"agent_id": agent_id},
            order_by="-created_at"
        )

        items = result["items"]
        total_pages = result["total_pages"]
    """
    # Get total count
    total = count_records(db, model, filters)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    # Get paginated items
    offset = (page - 1) * page_size
    items = get_all(
        db,
        model,
        filters=filters,
        limit=page_size,
        offset=offset,
        order_by=order_by
    )

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages
    }
