# Database Migration Guide: database_manager to SQLAlchemy ORM

**Last Updated**: February 4, 2026

This guide documents the migration from the deprecated `database_manager.py` to SQLAlchemy ORM patterns using `core.database`.

---

## Overview

The `database_manager.py` module has been **deprecated**. All code should use SQLAlchemy ORM patterns from `core.database` instead.

**Migration Status**:
- ✅ `execution_state_manager.py` - MIGRATED
- ✅ `enhanced_execution_state_manager.py` - MIGRATED
- ✅ `api_routes.py` - MIGRATED
- ⚠️ Some files in `integrations/` may still use `database_manager`

---

## Why This Migration?

### Issues with `database_manager.py`

1. **Deprecated Pattern**: Uses a singleton manager pattern that's less flexible
2. **Async Complexity**: Async session management is complex and error-prone
3. **Limited Features**: Doesn't leverage SQLAlchemy 2.0 features
4. **Maintenance Burden**: Duplicate functionality with `core.database`

### Benefits of `core.database`

1. **Standard SQLAlchemy**: Uses industry-standard SQLAlchemy patterns
2. **Flexible Sessions**: Support for both sync and async sessions
3. **Better Performance**: Connection pooling, optimized queries
4. **Type Safety**: Better IDE support with SQLAlchemy ORM models
5. **Easier Testing**: Simpler to mock and test

---

## Migration Patterns

### Pattern 1: Async Database Operations

**Before** (using `database_manager`):
```python
from core.database_manager import db_manager

async def create_workflow_execution(workflow_id: str, input_data: dict):
    execution = await db_manager.create_workflow_execution(
        workflow_id=workflow_id,
        input_data=input_data,
        status="pending"
    )
    return execution
```

**After** (using `core.database`):
```python
from core.database import get_async_db_session
from core.models import WorkflowExecution

async def create_workflow_execution(workflow_id: str, input_data: dict):
    async with get_async_db_session() as db:
        execution = WorkflowExecution(
            workflow_id=workflow_id,
            input_data=input_data,
            status="pending"
        )
        db.add(execution)
        await db.commit()
        await db.refresh(execution)
        return execution
```

---

### Pattern 2: Query Operations

**Before** (using `database_manager`):
```python
from core.database_manager import db_manager

async def get_workflow_execution(execution_id: str):
    execution = await db_manager.get_workflow_execution(execution_id)
    return execution
```

**After** (using `core.database`):
```python
from core.database import get_async_db_session
from core.models import WorkflowExecution
from sqlalchemy import select

async def get_workflow_execution(execution_id: str):
    async with get_async_db_session() as db:
        result = await db.execute(
            select(WorkflowExecution).where(
                WorkflowExecution.execution_id == execution_id
            )
        )
        execution = result.scalar_one_or_none()
        return execution
```

---

### Pattern 3: Update Operations

**Before** (using `database_manager`):
```python
from core.database_manager import db_manager

async def update_execution_status(execution_id: str, status: str):
    # Old pattern using raw SQL
    await db_manager.execute(
        "UPDATE workflow_executions SET status = ? WHERE execution_id = ?",
        (status, execution_id)
    )
```

**After** (using `core.database`):
```python
from core.database import get_async_db_session
from core.models import WorkflowExecution
from sqlalchemy import select, update

async def update_execution_status(execution_id: str, status: str):
    async with get_async_db_session() as db:
        # Method 1: Load, modify, commit
        result = await db.execute(
            select(WorkflowExecution).where(
                WorkflowExecution.execution_id == execution_id
            )
        )
        execution = result.scalar_one_or_none()

        if execution:
            execution.status = status
            await db.commit()

        # Method 2: Bulk update (more efficient)
        # await db.execute(
        #     update(WorkflowExecution)
        #     .where(WorkflowExecution.execution_id == execution_id)
        #     .values(status=status)
        # )
        # await db.commit()
```

---

### Pattern 4: Synchronous Operations (FastAPI Routes)

**Before** (using `database_manager`):
```python
from fastapi import Depends
from core.database_manager import get_db_session_for_request

@router.post("/users")
async def create_user(
    email: str,
    name: str,
    db: Session = Depends(get_db_session_for_request)
):
    new_user = await db_manager.create_user(email, name)
    return new_user
```

**After** (using `core.database`):
```python
from fastapi import Depends
from core.database import get_db
from core.models import User
from sqlalchemy.orm import Session

@router.post("/users")
async def create_user(
    email: str,
    name: str,
    db: Session = Depends(get_db)
):
    new_user = User(
        email=email,
        first_name=name,
        status="active",
        role="member"
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user
```

---

### Pattern 5: Complex Queries with Joins

**Before** (using `database_manager`):
```python
from core.database_manager import db_manager

async def get_user_with_sessions(user_id: str):
    # Raw SQL query
    rows = await db_manager.fetch_all(
        """
        SELECT u.*, s.*
        FROM users u
        LEFT JOIN user_sessions s ON u.id = s.user_id
        WHERE u.id = ?
        """,
        (user_id,)
    )
    return rows
```

**After** (using `core.database`):
```python
from core.database import get_async_db_session
from core.models import User, UserSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

async def get_user_with_sessions(user_id: str):
    async with get_async_db_session() as db:
        # Method 1: Using selectinload (eager loading)
        result = await db.execute(
            select(User)
            .options(selectinload(User.sessions))
            .where(User.id == user_id)
        )
        user = result.scalar_one_or_none()
        return user

        # Method 2: Using join
        # result = await db.execute(
        #     select(User, UserSession)
        #     .join(UserSession, User.id == UserSession.user_id)
        #     .where(User.id == user_id)
        # )
        # rows = result.all()
        # return rows
```

---

## Available Session Patterns

### 1. Async Session (for async functions)

```python
from core.database import get_async_db_session

async def my_async_function():
    async with get_async_db_session() as db:
        # Perform async database operations
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        return user
```

### 2. Sync Session (for FastAPI routes)

```python
from core.database import get_db
from sqlalchemy.orm import Session

@router.get("/users/{user_id}")
async def get_user(user_id: str, db: Session = Depends(get_db)):
    # Use synchronous database operations
    user = db.query(User).filter(User.id == user_id).first()
    return user
```

### 3. Context Manager (for explicit control)

```python
from core.database import get_db_session

def my_function():
    with get_db_session(commit=True) as db:
        # Automatically commits on success
        user = User(email="test@example.com")
        db.add(user)
        # Commit happens automatically
```

---

## Common Migration Examples

### Example 1: Migrating execution_state_manager.py

**Before**:
```python
from core.database_manager import DatabaseManager

class ExecutionStateManager:
    def __init__(self):
        self.db = DatabaseManager()

    async def create_execution(self, workflow_id: str, input_data: dict):
        return await self.db.create_workflow_execution(
            workflow_id=workflow_id,
            input_data=input_data
        )
```

**After**:
```python
from core.database import get_async_db_session
from core.models import WorkflowExecution

class ExecutionStateManager:
    # No database manager needed

    async def create_execution(self, workflow_id: str, input_data: dict):
        async with get_async_db_session() as db:
            execution = WorkflowExecution(
                workflow_id=workflow_id,
                input_data=input_data,
                status="pending"
            )
            db.add(execution)
            await db.commit()
            await db.refresh(execution)
            return execution.execution_id
```

---

### Example 2: Migrating User Creation

**Before**:
```python
from core.database_manager import db_manager

async def create_user(email: str, name: str):
    user = await db_manager.create_user(email, name)
    return user
```

**After**:
```python
from core.database import get_async_db_session
from core.models import User

async def create_user(email: str, name: str):
    async with get_async_db_session() as db:
        # Check if user exists
        from sqlalchemy import select
        result = await db.execute(
            select(User).where(User.email == email)
        )
        existing = result.scalar_one_or_none()

        if existing:
            raise ValueError(f"User with email {email} already exists")

        # Create new user
        user = User(
            email=email,
            first_name=name,
            status="active",
            role="member"
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        return {
            "id": user.id,
            "email": user.email,
            "name": name,
            "first_name": user.first_name,
            "last_name": user.last_name
        }
```

---

## Database Connection and Session Management

### Connection Pooling

`core.database` automatically handles connection pooling:

```python
from sqlalchemy.ext.asyncio import create_async_engine

# Connection pool is automatically configured
engine = create_async_engine(
    DATABASE_URL,
    pool_size=5,          # Number of connections to maintain
    max_overflow=10,      # Additional connections under load
    pool_timeout=30,      # Seconds to wait for connection
    pool_recycle=3600     # Recycle connections after 1 hour
)
```

### Session Best Practices

1. **Use Context Managers**: Always use `with` or `async with`
2. **Explicit Commit**: Commit transactions explicitly or use `commit=True` parameter
3. **Handle Exceptions**: Use try-except blocks for error handling
4. **Close Sessions**: Let context managers handle closing

**Good Pattern**:
```python
async def good_pattern():
    async with get_async_db_session() as db:
        try:
            # Database operations
            await db.commit()
        except Exception as e:
            await db.rollback()
            raise
```

**Bad Pattern**:
```python
async def bad_pattern():
    db = await get_async_db_session()  # Don't do this - no context manager
    # If an exception occurs, session won't be closed properly
```

---

## Testing Migrated Code

### Test Examples

```python
import pytest
from core.database import get_async_db_session
from core.models import User
from sqlalchemy import select

@pytest.mark.asyncio
async def test_create_user():
    """Test user creation with new pattern"""
    async with get_async_db_session() as db:
        # Create user
        user = User(
            email="test@example.com",
            first_name="Test",
            status="active"
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

        # Verify user was created
        result = await db.execute(
            select(User).where(User.email == "test@example.com")
        )
        found_user = result.scalar_one_or_none()

        assert found_user is not None
        assert found_user.email == "test@example.com"
```

### Running Tests

```bash
# Run all tests
pytest backend/tests/ -v

# Run migration-specific tests
pytest backend/tests/test_execution_state_manager.py -v

# Run with coverage
pytest backend/tests/ --cov=core.execution_state_manager --cov-report=html
```

---

## Verification Checklist

After migrating code from `database_manager` to `core.database`, verify:

- [ ] All imports of `database_manager` are removed
- [ ] Code uses `get_async_db_session()` for async operations
- [ ] Code uses `get_db` for FastAPI route dependencies
- [ ] All database operations use SQLAlchemy ORM models
- [ ] No raw SQL queries remain (unless necessary)
- [ ] Error handling is in place (try-except with rollback)
- [ ] Tests pass for migrated code
- [ ] Application starts without errors
- [ ] Database operations work correctly

---

## Performance Considerations

### Query Optimization

1. **Use select() for Queries**: More efficient than raw SQL
2. **Eager Loading**: Use `selectinload()` to avoid N+1 queries
3. **Indexing**: Ensure foreign keys and frequently queried columns are indexed
4. **Connection Pooling**: Already configured in `core.database`

**Example: Avoiding N+1 Queries**

```python
# Bad: N+1 query problem
async def bad_get_users_with_sessions():
    async with get_async_db_session() as db:
        result = await db.execute(select(User))
        users = result.scalars().all()

        # This will execute a query for EACH user
        for user in users:
            sessions = user.sessions  # N+1 problem!

# Good: Use eager loading
async def good_get_users_with_sessions():
    async with get_async_db_session() as db:
        result = await db.execute(
            select(User)
            .options(selectinload(User.sessions))  # Load sessions in one query
        )
        users = result.scalars().all()

        # No additional queries
        for user in users:
            sessions = user.sessions  # Already loaded
```

---

## Troubleshooting

### Common Issues

#### 1. "Object is not attached to this session"

**Problem**: Trying to use an object outside its session

**Solution**: Use `expunge` or reload objects in new session

```python
async with get_async_db_session() as db:
    user = db.query(User).first()
    db.expunge(user)  # Detach from session
# Now 'user' can be used outside the session
```

#### 2. "PendingRollbackError"

**Problem**: Session has pending rollback after error

**Solution**: Always use try-except and explicit rollback

```python
async with get_async_db_session() as db:
    try:
        # Database operations
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise
```

#### 3. Import Errors After Migration

**Problem**: Can't find `get_async_db_session` or models

**Solution**: Ensure correct imports

```python
# Correct imports
from core.database import get_async_db_session, get_db
from core.models import User, WorkflowExecution
from sqlalchemy import select, update
```

---

## Rollback Plan

If issues arise after migration:

1. **Revert Code Changes**: Use git to revert to previous commit
2. **Restore Database**: If schema was modified, restore from backup
3. **Check Application Logs**: Look for specific error messages
4. **Fix Issues Incrementally**: Migrate one module at a time

```bash
# Revert migration commit
git revert <commit-hash>

# Restore database (if needed)
sqlite3 atom_backup.db .dump | sqlite3 atom_dev.db
```

---

## Additional Resources

- **SQLAlchemy 2.0 Documentation**: https://docs.sqlalchemy.org/en/20/
- **Async SQLAlchemy**: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html
- **Database Best Practices**: See `docs/DATABASE_MODEL_BEST_PRACTICES.md`
- **Model Reference**: See `backend/core/models.py`

---

## Summary

| Topic | Status |
|-------|--------|
| Migration Guide | ✅ Complete |
| Async Patterns | ✅ Documented |
| Sync Patterns | ✅ Documented |
| Testing | ✅ Complete |
| Troubleshooting | ✅ Documented |

---

*For questions or issues, please refer to the main documentation or open an issue.*
