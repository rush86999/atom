# Database Session Management Guide

**Last Updated**: February 4, 2026
**Status**: ✅ Standardized
**Related Files**: `core/database.py`, `core/database_manager.py` (deprecated)

---

## Overview

Atom uses SQLAlchemy for database operations with **two standardized patterns** for session management. This guide explains when and how to use each pattern.

---

## Quick Reference

| Use Case | Pattern | Import |
|----------|---------|--------|
| **API Routes** | Dependency Injection | `from core.database import get_db` |
| **Service Layer** | Context Manager | `from core.database import get_db_session` |
| **Background Tasks** | Context Manager | `from core.database import get_db_session` |
| **Scripts** | Context Manager | `from core.database import get_db_session` |
| **Tests** | Either | Both supported |

---

## Pattern 1: Dependency Injection (API Routes)

### When to Use
✅ **USE** for: FastAPI endpoint functions
❌ **DON'T USE** for: Service layer, background tasks, scripts

### How to Use

```python
from fastapi import Depends
from sqlalchemy.orm import Session
from core.database import get_db
from core.models import User

@router.get("/users/{user_id}")
async def get_user(user_id: str, db: Session = Depends(get_db)):
    """
    API route with database access.

    FastAPI automatically:
    - Creates session before request
    - Closes session after request
    - Handles errors
    """
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise router.not_found_error("User", user_id)

    return router.success_response(data=user)

@router.post("/users")
async def create_user(user_data: UserCreate, db: Session = Depends(get_db)):
    """
    Create user with automatic transaction management.
    """
    user = User(**user_data.dict())
    db.add(user)
    db.commit()  # Explicit commit
    db.refresh(user)

    return router.success_response(
        data=user,
        message="User created successfully",
        status_code=201
    )
```

### Benefits
- ✅ FastAPI standard pattern
- ✅ Automatic lifecycle management
- ✅ Testable with dependency override
- ✅ Type-safe with IDE support
- ✅ Request-scoped sessions

### Testing with Dependency Override

```python
from fastapi.testclient import TestClient
from core.database import get_db

def override_get_db():
    """Use test database instead of real database"""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

client = TestClient(app)
app.dependency_overrides[get_db] = override_get_db

def test_create_user():
    response = client.post("/users", json={"email": "test@example.com"})
    assert response.status_code == 200
```

---

## Pattern 2: Context Manager (Service Layer)

### When to Use
✅ **USE** for: Service layer functions, background tasks, scripts
❌ **DON'T USE** for: API routes (use dependency injection instead)

### How to Use

```python
from core.database import get_db_session
from core.models import User

class UserService:
    """Service layer for user operations"""

    def get_user(self, user_id: str) -> Optional[User]:
        """
        Read operation - no commit needed.
        Session auto-closes after context.
        """
        with get_db_session() as db:
            user = db.query(User).filter(User.id == user_id).first()
            return user
        # Session closed here

    def create_user(self, email: str, name: str) -> User:
        """
        Write operation - auto-commits on success.
        Auto-rollback on exception.
        """
        with get_db_session() as db:
            user = User(email=email, first_name=name)
            db.add(user)
            # Auto-commits when exiting context successfully
            return user
        # Session closed here

    def update_user(self, user_id: str, name: str) -> bool:
        """
        Update with explicit commit control.
        """
        with get_db_session() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return False

            user.first_name = name
            db.commit()  # Optional - explicit commit
            return True
```

### Benefits
- ✅ Automatic cleanup with context manager
- ✅ Clear scope for database operations
- ✅ Prevents connection leaks
- ✅ Auto-commit on success, auto-rollback on exception
- ✅ Thread-safe

### Background Task Example

```python
from core.database import get_db_session
import asyncio

async def process_user_data_async(user_id: str):
    """
    Background task with database access.
    Context manager ensures cleanup even if task fails.
    """
    with get_db_session() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"User {user_id} not found")
            return

        # Process data
        user.processed = True
        # Auto-commits on success
```

### Script Example

```python
#!/usr/bin/env python3
"""Migration script example"""

from core.database import get_db_session
from core.models import User

def migrate_users():
    """Migrate user data"""
    migrated_count = 0

    with get_db_session() as db:
        users = db.query(User).filter(User.status == "legacy").all()

        for user in users:
            user.status = "active"
            user.version = 2
            migrated_count += 1

        # Auto-commits when all migrations succeed

    print(f"Migrated {migrated_count} users")

if __name__ == "__main__":
    migrate_users()
```

---

## Deprecated Patterns

### ❌ Deprecated: database_manager.py

The `core.database_manager` module is **deprecated**. Use `core.database` instead.

#### Migration Guide

**OLD (Deprecated)**:
```python
from core.database_manager import get_db_session

with get_db_session() as db:
    user = db.query(User).first()
```

**NEW (Recommended)**:
```python
from core.database import get_db_session

with get_db_session() as db:
    user = db.query(User).first()
```

**Deprecation Warnings**:
- `database_manager.get_db_session()` → Use `database.get_db_session()`
- `database_manager.get_db_session_for_request()` → Use `database.get_db()`
- `database_manager.get_monitored_db_session()` → Use `database.get_db_session()`

These functions will emit `DeprecationWarning` and will be removed in version 2.0.

---

## Anti-Patterns to Avoid

### ❌ Manual Session Creation

**BAD**:
```python
def process_user(user_id: str):
    db = SessionLocal()  # Manual creation
    try:
        user = db.query(User).first()
        user.name = "Updated"
        db.commit()
    finally:
        db.close()  # Manual cleanup
```

**GOOD**:
```python
def process_user(user_id: str):
    with get_db_session() as db:  # Context manager
        user = db.query(User).first()
        user.name = "Updated"
        # Auto-commit, auto-cleanup
```

### ❌ Global Sessions

**BAD**:
```python
# Module-level session (NEVER DO THIS)
db = SessionLocal()

def get_user(user_id: str):
    return db.query(User).filter(User.id == user_id).first()
```

**GOOD**:
```python
def get_user(user_id: str):
    with get_db_session() as db:  # New session per call
        return db.query(User).filter(User.id == user_id).first()
```

### ❌ Mixing Patterns

**BAD**:
```python
@router.get("/users/{user_id}")
async def get_user(user_id: str, db: Session = Depends(get_db)):
    # Then inside the route:
    with get_db_session() as db2:  # DON'T create second session!
        other = db2.query(Other).first()
```

**GOOD**:
```python
@router.get("/users/{user_id}")
async def get_user(user_id: str, db: Session = Depends(get_db)):
    # Use the injected session for all database operations
    other = db.query(Other).first()  # Same session
```

---

## Best Practices

### 1. Keep Transactions Short

```python
# GOOD: Short transaction
with get_db_session() as db:
    user = db.query(User).first()
    user.name = "Updated"

# BAD: Long transaction with external calls
with get_db_session() as db:
    user = db.query(User).first()
    result = external_api_call()  # Holds database lock!
    user.data = result
```

### 2. Handle Exceptions Appropriately

```python
# GOOD: Let context manager handle rollback
def update_user(user_id: str, data: dict):
    with get_db_session() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User {user_id} not found")
        user.update(data)
        # Auto-rollback on ValueError
```

### 3. Use Explicit Commits When Needed

```python
# GOOD: Multiple operations, one transaction
def transfer_data(from_id: str, to_id: str):
    with get_db_session() as db:
        from_user = db.query(User).filter(User.id == from_id).first()
        to_user = db.query(User).filter(User.id == to_id).first()

        from_user.data_count -= 1
        to_user.data_count += 1

        db.commit()  # Single commit for both updates
```

### 4. Lazy Load Relationships Carefully

```python
# GOOD: Eager load to avoid N+1 queries
from sqlalchemy.orm import joinedload

with get_db_session() as db:
    users = db.query(User).options(
        joinedload(User.posts)
    ).all()

# BAD: N+1 query problem
with get_db_session() as db:
    users = db.query(User).all()
    for user in users:
        print(user.posts)  # New query per user!
```

---

## Performance Tips

### Connection Pooling

The database connection pool is configured in `core/database.py`:

```python
# PostgreSQL (production)
pool_size = 20
max_overflow = 30
# Total: 50 connections maximum

# SQLite (development)
# No pooling (file-based)
```

### Query Optimization

```python
# GOOD: Select only needed columns
with get_db_session() as db:
    users = db.query(User.id, User.email).all()

# GOOD: Use indexes
with get_db_session() as db:
    user = db.query(User).filter(User.email == email).first()
    # Ensure User.email has index

# GOOD: Batch operations
with get_db_session() as db:
    db.bulk_insert_mappings(User, user_data_list)
```

---

## Troubleshooting

### "Session is closed" Error

**Problem**: Trying to use a session after it's closed.

**Solution**: Ensure all database operations happen within the context or request scope.

```python
# BAD
def get_user_email(user_id: str):
    with get_db_session() as db:
        user = db.query(User).first()
    return user.email  # Error! Session closed

# GOOD
def get_user_email(user_id: str):
    with get_db_session() as db:
        user = db.query(User).first()
        return user.email  # OK: Still in context
```

### "Detached instance" Error

**Problem**: Accessing lazy-loaded relationships after session closes.

**Solution**: Use `expire_on_commit=False` (default in Atom) or eager load.

```python
# GOOD: Already configured in core/database.py
SessionLocal = sessionmaker(
    expire_on_commit=False  # Prevents detached instance errors
)
```

### Connection Pool Exhaustion

**Problem**: Too many connections, pool exhausted.

**Solution**:
1. Use context managers to ensure cleanup
2. Don't create long-running transactions
3. Increase pool size if needed (in database.py)

---

## Testing

### Unit Tests with Override

```python
import pytest
from fastapi.testclient import TestClient
from core.database import get_db

@pytest.fixture
def db_session():
    """Provide test database session"""
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.rollback()
        db.close()

def test_create_user(db_session):
    """Test user creation"""
    user = User(email="test@example.com")
    db_session.add(user)
    db_session.commit()

    assert user.id is not None
```

### Integration Tests

```python
def test_api_create_user():
    """Test API endpoint"""
    client = TestClient(app)
    response = client.post("/users", json={"email": "test@example.com"})
    assert response.status_code == 200
    assert response.json()["success"] is True
```

---

## Migration Checklist

If you're migrating from old patterns:

- [ ] Replace `from core.database_manager import get_db_session` with `from core.database import get_db_session`
- [ ] Replace `from core.database_manager import get_db_session_for_request` with `from core.database import get_db`
- [ ] Remove manual `db.close()` calls (context manager handles it)
- [ ] Remove `try/finally` blocks around sessions (context manager handles it)
- [ ] Test all database operations after migration
- [ ] Verify deprecation warnings are resolved

---

## Summary

| Pattern | Use For | Import | Auto-Cleanup | Auto-Commit |
|---------|---------|--------|--------------|-------------|
| **Dependency Injection** | API Routes | `from core.database import get_db` | ✅ | ❌ (Manual) |
| **Context Manager** | Services, Tasks, Scripts | `from core.database import get_db_session` | ✅ | ✅ |

**Key Rules**:
1. ✅ API Routes → Use `Depends(get_db)`
2. ✅ Service Layer → Use `with get_db_session() as db:`
3. ❌ Never use `SessionLocal()` directly
4. ❌ Never use `database_manager` (deprecated)

---

## Related Documentation

- **API Standards**: `docs/API_STANDARDS.md`
- **Governance Guide**: `docs/GOVERNANCE_GUIDE.md`
- **Database Models**: `core/models.py`

---

*Generated: February 4, 2026*
*Atom Database Layer Documentation*
