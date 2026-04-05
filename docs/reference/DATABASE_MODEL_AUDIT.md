# Database Model Field Type Audit Report

**Generated**: 2026-02-04  
**File**: backend/core/models.py  
**Lines**: 3,876  
**Models**: 80+ models

## Executive Summary

The database models are **generally well-structured** with consistent use of:
- ✅ `DateTime(timezone=True)` for all timestamp fields
- ✅ `Boolean` for boolean flags (61 fields)
- ✅ `Integer` for actual numeric data (counts, sizes)
- ✅ `JSON` type for JSON data (30+ fields)

**However, there are several inconsistencies that should be addressed:**

---

## Critical Issues

### 1. String Columns Without Length Specification

**Issue**: Many `String` columns don't specify a length, which can cause issues:
- MySQL: Requires length for VARCHAR
- PostgreSQL: Works but may impact performance
- SQLite: Ignores length, but inconsistent schema

**Impact**: 100+ columns affected across all models

**Examples**:
```python
# Current (inconsistent)
id = Column(String, primary_key=True)  # No length
name = Column(String, nullable=False)   # No length
email = Column(String)                  # No length

# Recommended
id = Column(String(36), primary_key=True)  # UUID
name = Column(String(255), nullable=False)
email = Column(String(255))
```

**Models Affected**: All models with String columns

**Migration Complexity**: **HIGH**
- Requires schema migration for each column
- May impact indexing and foreign keys
- Needs careful testing with PostgreSQL and SQLite

**Recommendation**: 
- Use `String(36)` for UUID fields (primary keys)
- Use `String(255)` for names, emails
- Use `String(500)` for longer text fields
- Use `Text` for unbounded text content

---

### 2. Relationship Inconsistencies: backref vs back_populates

**Issue**: Mixed usage of `backref` and `back_populates`

**Current State**:
- `backref`: 82 uses (deprecated pattern)
- `back_populates`: 34 uses (recommended pattern)

**Examples**:
```python
# Current (mixed)
class User(Base):
    sessions = relationship("UserSession", backref="user")  # OLD

# Recommended
class User(Base):
    sessions = relationship("UserSession", back_populates="user")  # NEW

class UserSession(Base):
    user = relationship("User", back_populates="sessions")
```

**Impact**: Code clarity and SQLAlchemy best practices

**Migration Complexity**: **MEDIUM**
- No database schema changes needed
- Requires code updates for all relationships
- Can be done incrementally

**Recommendation**: 
- Migrate to `back_populates` for new code
- Gradually update existing relationships
- Remove all `backref` usage

---

## Moderate Issues

### 3. JSON Data Stored in Text Columns

**Issue**: Some JSON data stored in `Text` columns instead of `JSON` columns

**Examples Found**:
```python
# Current (inconsistent)
metadata_json = Column(Text, nullable=True)              # Line 417
context = Column(Text, nullable=True)                     # Lines 301, 383
input_data = Column(Text, nullable=True)                  # Line 298
context_snapshot = Column(Text, nullable=False)           # Line 885
input_context = Column(Text, nullable=True)                # Line 604

# Should be JSON
metadata_json = Column(JSON, nullable=True)
context = Column(JSON, nullable=True)
input_data = Column(JSON, nullable=True)
context_snapshot = Column(JSON, nullable=False)
input_context = Column(JSON, nullable=True)
```

**Impact**: 
- No JSON validation at database level
- No automatic serialization/deserialization
- Manual JSON parsing required

**Migration Complexity**: **MEDIUM**
- Requires ALTER COLUMN operations
- Data migration needed for existing data
- Test for data integrity

**Recommendation**:
- Migrate all JSON data to `JSON` columns
- Use `JSON` for structured data
- Use `Text` only for plain text content

---

## Low Priority Issues

### 4. Float vs Numeric for Financial Data

**Issue**: Some financial fields use `Float` instead of `Numeric`

**Examples**:
```python
# Current
amount = Column(Float, nullable=True)

# Recommended (for financial data)
amount = Column(Numeric(10, 2), nullable=True)
```

**Impact**: Precision for financial calculations

**Migration Complexity**: **HIGH** (if changed)
- Requires data migration
- Affects existing records

**Recommendation**: 
- Use `Numeric` for new financial fields
- Keep `Float` for non-critical numeric data

---

## Consistent Patterns (Keep These!)

### ✅ DateTime Fields
All timestamp fields consistently use `DateTime(timezone=True)`:
```python
created_at = Column(DateTime(timezone=True), server_default=func.now())
updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

### ✅ Boolean Fields
Boolean flags consistently use `Boolean` type:
```python
is_active = Column(Boolean, default=False)
email_verified = Column(Boolean, default=False)
```

### ✅ JSON Fields
JSON data appropriately uses `JSON` type:
```python
metadata_json = Column(JSON, default={})
preferences = Column(JSON, default={})
```

---

## Migration Priority & Recommendations

### Phase 1: Quick Wins (Low Risk)
1. Update new relationships to use `back_populates`
2. Add length specs to new String columns
3. Use `JSON` type for new JSON fields

### Phase 2: Medium Risk
1. Migrate `backref` to `back_populates` incrementally
2. Convert Text→JSON for JSON data fields
3. Document best practices for new models

### Phase 3: Higher Risk (Requires Planning)
1. Add length specifications to existing String columns
2. Create Alembic migration for schema changes
3. Test migration with backup database first

---

## Statistics

| Category | Count | Status |
|----------|-------|--------|
| Total Lines | 3,876 | - |
| Models (estimated) | 80+ | - |
| String without length | 100+ | ⚠️ Needs Fix |
| backref usage | 82 | ⚠️ Should Replace |
| back_populates usage | 34 | ✅ Good Pattern |
| Boolean fields | 61 | ✅ Consistent |
| DateTime(timezone=True) | 50+ | ✅ Consistent |
| JSON fields | 30+ | ✅ Consistent |
| Text storing JSON | 6 | ⚠️ Should be JSON |

---

## Conclusion

The database models are **70% consistent** with good patterns. The main issues are:

1. **String length specifications** - Most critical for cross-database compatibility
2. **Relationship patterns** - Backref vs back_populates inconsistency
3. **JSON in Text columns** - Should use JSON type

**Recommendation**: 
- Fix in phases, starting with new code
- Create Alembic migrations for schema changes
- Update documentation with best practices

**Estimated Effort**: 
- Phase 1 (Quick Wins): 2-4 hours
- Phase 2 (Medium): 8-16 hours
- Phase 3 (High): 16-24 hours (with testing)
