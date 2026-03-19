# SQLAlchemy 2.0 text() Wrapper Fix Guide

## Issue Summary

SQLAlchemy 2.0+ requires explicit `text()` wrapper for raw SQL strings passed to `execute()`. This affects test files that use raw SQL to create tables or insert data.

## Error Message

```
sqlalchemy.exc.ArgumentError: Textual SQL expression should be explicitly declared as text()
```

## Files Affected

Based on scan, only **1 file** requires manual fixes:
- `tests/api/test_admin_routes.py` (28 `db.execute()` calls)

Other files either:
- Don't use `db.execute()` with raw SQL
- Already have `text()` wrapper

## Manual Fix Steps

### Step 1: Add text to imports

**Line 19:**
```python
# BEFORE
from sqlalchemy import create_engine

# AFTER
from sqlalchemy import create_engine, text
```

### Step 2: Wrap execute calls with text()

**For simple calls (no parameters):**

```python
# BEFORE
db.execute("""
    CREATE TABLE users (
        id VARCHAR PRIMARY KEY
    )
""")

# AFTER
db.execute(text("""
    CREATE TABLE users (
        id VARCHAR PRIMARY KEY
    )
"""))
```

**For parameterized calls:**

```python
# BEFORE
db.execute("""
    INSERT INTO users (id, name) VALUES (:id, :name)
""", {"id": 1, "name": "test"})

# AFTER
db.execute(text("""
    INSERT INTO users (id, name) VALUES (:id, :name)
"""), {"id": 1, "name": "test"})
```

**Key Difference:**
- Simple calls: Add extra `)` after `"""` → `"""))`
- Parameterized calls: Keep `"""),` and add extra `)` after params → `"""), {...}))`

### Specific Lines to Fix in test_admin_routes.py

**Simple calls (add extra )) after """):**
- Lines 62-71: Users table CREATE
- Lines 74-91: WebSocket state table CREATE
- Lines 94-104: Skill ratings table CREATE
- Lines 107-118: Failed rating uploads table CREATE
- Lines 121-126: Skills table CREATE
- Lines 129-134: Tenants table CREATE
- Lines 137-153: Conflict log table CREATE
- Lines 156-168: Skill cache table CREATE
- Line 272-276: WebSocket INSERT (simple)
- Line 306-310: WebSocket UPDATE (simple)
- Line 342-346: WebSocket disable (simple)
- Line 536-539: WebSocket enable (simple)
- Line 594-591: Rating sync INSERT (simple)

**Parameterized calls (keep """), and add )) after params}):**
- Lines 253-257: WebSocket INSERT with `:now` parameter
- Line 382-384: Skill ratings INSERT with loop params
- Line 424-425: Skill ratings INSERT with f-string params
- Line 503-504: Failed uploads INSERT with loop params
- Line 543-544: Conflict log INSERT with dict params
- Line 574-575: Skill cache INSERT with loop params
- Line 598-599: Skill cache UPDATE with loop params
- Line 639-640: Skill cache INSERT with dict params

## Automated Fix Script

Due to the complexity of distinguishing simple vs parameterized calls, manual fixing is recommended. However, the `fix_execute.py` script provides a starting point:

```bash
python3 fix_execute.py tests/api/test_admin_routes.py
```

**Note:** Script handles simple calls correctly but may need manual adjustment for parameterized calls.

## Verification

After fixing, verify syntax:

```bash
python3 -c "import ast; ast.parse(open('tests/api/test_admin_routes.py').read()); print('Syntax OK')"
```

Then run tests:

```bash
python3 -m pytest tests/api/test_admin_routes.py -v
```

## Expected Impact

- **Tests fixed:** 28 test setup statements
- **Estimated pass rate improvement:** 5-10%
- **Time required:** ~15 minutes manual fix

## Alternative Approach

If manual fixing is too time-consuming, consider:
1. Disabling affected tests temporarily
2. Using SQLAlchemy's `session.execute()` with `text()` instead of raw `db.execute()`
3. Migrating to Alembic migrations for test schema setup

## Status

- [x] Issue identified
- [x] Fix guide created
- [ ] Manual fixes applied
- [ ] Tests verified

---

**Created:** 2026-03-16
**Phase:** 197-quality-first-push-80
**Plan:** 197-01
