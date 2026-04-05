# Database Model Best Practices Guide

**Created**: February 4, 2026
**Purpose**: Establish consistent patterns for database models in Atom

This guide documents the best practices for database model definitions based on the audit conducted in `docs/DATABASE_MODEL_AUDIT.md`.

---

## Field Type Standards

### 1. String Columns

**Always specify length** for String columns to ensure cross-database compatibility:

```python
# ✅ CORRECT - With length specification
id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
email = Column(String(255), nullable=False)
name = Column(String(255), nullable=False)
description = Column(String(500), nullable=True)
api_key = Column(String(128), unique=True, nullable=True)

# ❌ AVOID - Without length (causes issues with MySQL/PostgreSQL)
id = Column(String, primary_key=True)
email = Column(String)
name = Column(String)
```

**Length Guidelines**:
- `String(36)`: UUID fields (primary keys, foreign keys)
- `String(128)`: API keys, tokens, short identifiers
- `String(255)`: Names, emails, URLs, standard text fields
- `String(500)`: Longer text content (descriptions, messages)
- `Text`: Unbounded text content (long form text, HTML, JSON)

---

### 2. Boolean Fields

**Use Boolean type** for boolean flags:

```python
# ✅ CORRECT
is_active = Column(Boolean, default=False)
email_verified = Column(Boolean, default=False)
onboarding_completed = Column(Boolean, default=False)

# ❌ AVOID - Integer for boolean flags
is_active = Column(Integer, default=0)
enabled = Column(Integer, default=1)
```

---

### 3. DateTime Fields

**Always use `DateTime(timezone=True)`** for timestamps:

```python
# ✅ CORRECT
created_at = Column(DateTime(timezone=True), server_default=func.now())
updated_at = Column(DateTime(timezone=True), onupdate=func.now())
last_login = Column(DateTime(timezone=True), nullable=True)

# ❌ AVOID - DateTime without timezone
created_at = Column(DateTime, server_default=func.now())
```

---

### 4. JSON Data

**Use `JSON` type** for structured JSON data:

```python
# ✅ CORRECT - For JSON data
metadata = Column(JSON, default={})
preferences = Column(JSON, default={})
configuration = Column(JSON, nullable=True)
tags = Column(JSON, default=list)

# ❌ AVOID - Text for JSON data
metadata = Column(Text, nullable=True)  # No JSON validation
context = Column(Text)  # Manual parsing required
```

**When to use `Text`**:
- Long form text content (user comments, descriptions)
- HTML content
- Plain text that doesn't need JSON validation

---

### 5. Relationships

**Use `back_populates` instead of `backref`**:

```python
# ✅ CORRECT - Explicit and clear
class User(Base):
    sessions = relationship("UserSession", back_populates="user")
    audit_logs = relationship("AuditLog", back_populates="user")

class UserSession(Base):
    user = relationship("User", back_populates="sessions")

class AuditLog(Base):
    user = relationship("User", back_populates="audit_logs")

# ❌ AVOID - Implicit and deprecated
class User(Base):
    sessions = relationship("UserSession", backref="user")  # Implicit, harder to debug
```

**Benefits of `back_populates`**:
- Explicit relationships on both sides
- Easier to debug and understand
- Better IDE autocomplete support
- SQLAlchemy recommended pattern

---

## Model Definition Template

Use this template for new models:

```python
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base

class MyModel(Base):
    __tablename__ = "my_models"

    # Primary Key (always String(36) for UUID)
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Foreign Keys (String(36))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    workspace_id = Column(String(36), ForeignKey("workspaces.id"), nullable=True, index=True)

    # String Fields (with lengths)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    description = Column(String(500), nullable=True)
    status = Column(String(50), default="active")

    # Boolean Fields
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    # Integer Fields
    count = Column(Integer, default=0)
    priority = Column(Integer, default=0)

    # JSON Fields
    metadata = Column(JSON, default={})
    configuration = Column(JSON, nullable=True)

    # Text Fields (for long content)
    content = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # DateTime Fields (always with timezone)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_active_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships (using back_populates)
    user = relationship("User", back_populates="my_models")
    workspace = relationship("Workspace", back_populates="my_models")
```

---

## Migration Guidelines

### Adding New Fields

When adding new fields to existing models, follow these patterns:

1. **String fields**: Always specify length
2. **Boolean fields**: Use `Boolean` with `default=False`
3. **JSON fields**: Use `JSON` type with `default={}`
4. **DateTime**: Always use `DateTime(timezone=True)`

### Updating Existing Models

When updating existing models:

1. **Create a migration** using Alembic
2. **Use `alembic revision`** to create migration script
3. **Test migration** on development database first
4. **Backup production** before running migration

#### Example Migration Process:

```bash
# 1. Create migration
alembic revision -m "update_user_model_field_types"

# 2. Edit generated migration file to use ALTER COLUMN
# 3. Test migration
alembic upgrade head

# 4. Verify data integrity
python -c "from core.models import User; print(User.__table_args__)"

# 5. Commit if successful
git add alembic/versions/
git commit -m "feat: update user model field types"
```

---

## Common Patterns

### Pattern 1: UUID Primary Keys

```python
from uuid import uuid4

id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
```

### Pattern 2: Timestamp Fields

```python
created_at = Column(DateTime(timezone=True), server_default=func.now())
updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

### Pattern 3: Foreign Key Relationships

```python
# Parent model
class User(Base):
    id = Column(String(36), primary_key=True)
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")

# Child model
class UserSession(Base):
    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    user = relationship("User", back_populates="sessions")
```

### Pattern 4: JSON Metadata

```python
metadata = Column(JSON, default=dict)
settings = Column(JSON, default={})
tags = Column(JSON, default=list)
```

---

## Anti-Patterns to Avoid

### ❌ Don't Use String Without Length

```python
# BAD
name = Column(String)
description = Column(String)

# GOOD
name = Column(String(255))
description = Column(String(500))
```

### ❌ Don't Use backref

```python
# BAD
relationship("User", backref="sessions")

# GOOD
relationship("User", back_populates="sessions")
```

### ❌ Don't Use Text for JSON

```python
# BAD
metadata = Column(Text)  # No validation
config = Column(Text)  # Manual parsing needed

# GOOD
metadata = Column(JSON, default={})
config = Column(JSON, default={})
```

### ❌ Don't Use Integer for Booleans

```python
# BAD
is_active = Column(Integer, default=0)

# GOOD
is_active = Column(Boolean, default=False)
```

---

## Checklist for New Models

Before committing a new model, verify:

- [ ] All String columns have length specifications
- [ ] Boolean columns use `Boolean` type (not Integer)
- [ ] DateTime columns use `DateTime(timezone=True)`
- [ ] JSON data uses `JSON` type (not Text)
- [ ] Relationships use `back_populates` (not backref)
- [ ] Primary keys are `String(36)` for UUIDs
- [ ] Foreign keys have `index=True` for lookups
- [ ] Timestamp fields have appropriate defaults

---

## References

- Database Model Audit: `docs/DATABASE_MODEL_AUDIT.md`
- SQLAlchemy Documentation: https://docs.sqlalchemy.org/
- Alembic Documentation: https://alembic.sqlalchemy.org/

---

**Last Updated**: February 4, 2026
**Maintained By**: Development Team
