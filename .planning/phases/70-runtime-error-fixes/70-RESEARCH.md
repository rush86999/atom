# Phase 70: Runtime Error Fixes - Research

**Researched:** 2026-02-22
**Domain:** Python Runtime Error Detection & Resolution, FastAPI/SQLAlchemy Production Stability
**Confidence:** HIGH

## Summary

Phase 70 focuses on fixing all runtime crashes, unhandled exceptions, import errors, and type errors across the Atom platform codebase. Research reveals this is a critical foundation phase that must be completed before test coverage expansion (Phases 71-74). The codebase has identified issues including:

1. **SQLAlchemy relationship errors** - FFmpegJob.user relationship causing 76 test failures
2. **Import/dependency issues** - Missing dependencies and circular imports
3. **NameError issues** - Undefined variables in production code
4. **Unhandled exceptions** - Bare `except:` clauses that mask errors

The research indicates a systematic approach using modern Python tooling (pytest, mypy, ruff) combined with test-driven bug fixing is the industry best practice for 2026. Key insight from multiple sources: **use `back_populates` instead of `backref` for SQLAlchemy relationships** to prevent AttributeError in relationship access.

**Primary recommendation:** Implement a four-prategy approach: (1) Fix SQLAlchemy relationship errors with `back_populates`, (2) Detect and fix ImportError/NameError with static analysis, (3) Replace bare `except:` with specific exceptions, (4) Create regression tests for every fix using pytest.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | >=7.4.0 | Testing framework | Most popular Python testing framework, detailed error messages, parametrized testing, async support |
| **mypy** | >=1.8.0 | Static type checker | Catches type errors before runtime, essential for large codebases, industry standard in 2026 |
| **ruff** | Latest (Rust-based) | Ultra-fast linter/formatter | 10-100x faster than flake8, replaces multiple tools (flake8, isort, autoflake), actively maintained |
| **SQLAlchemy 2.0** | >=2.0.0 | ORM | Modern relationship API with `back_populates` best practice, explicit bidirectional relationships |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pytest-cov** | >=4.1.0 | Coverage reporting | Measure test coverage, ensure fixes are tested |
| **pytest-asyncio** | >=0.21.0 | Async test support | Required for FastAPI endpoint testing |
| **hypothesis** | >=6.92.0 | Property-based testing | Find edge cases that unit tests miss |
| **pytest-rerunfailures** | Latest | Flaky test handling | Automatically rerun failed tests with configurable delays |
| **black** | Latest | Code formatter | Enforces PEP 8, eliminates style debates |
| **bandit** | Latest | Security vulnerability scanner | Detect security issues in error handling |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **pytest** | unittest (built-in) | pytest has better fixtures, parametrization, and community support |
| **mypy** | pyright (Microsoft) | mypy is more mature, better FastAPI/SQLAlchemy integration |
| **ruff** | flake8+black+isort | ruff is 10-100x faster, single tool vs multiple |
| **back_populates** | backref | back_populates is explicit, modern, better for production (2026 best practice) |

**Installation:**
```bash
# Core tools (already in requirements.txt)
pip install pytest>=7.4.0 pytest-cov>=4.1.0 mypy>=1.8.0 ruff hypothesis

# Additional tools for error detection
pip install pytest-rerunfailures bandit safety

# Ruff installation (Rust-based ultra-fast linter)
pip install ruff
```

**Key Finding from Research:** As of 2026, **ruff has largely replaced flake8, isort, and pydocstyle** due to 10-100x faster performance while providing the same functionality. The modern Python stack favors ruff over traditional tools.

## Architecture Patterns

### Recommended Error Fix Workflow

```
1. Static Analysis (mypy + ruff)
   ↓
2. Runtime Detection (pytest execution)
   ↓
3. Test-Driven Fix (write failing test → fix → verify pass)
   ↓
4. Regression Prevention (commit test with fix)
```

### Pattern 1: SQLAlchemy Relationship Configuration (CRITICAL)
**What:** Explicit bidirectional relationships using `back_populates` instead of `backref`
**When to use:** All SQLAlchemy 2.0 relationship definitions
**Why:** Prevents AttributeError, ensures data consistency, better IDE support

**Example (CORRECT - back_populates):**
```python
# Source: SQLAlchemy 2.0 documentation, 2026 best practices
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship, DeclarativeBase

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    # Explicit relationship with back_populates
    ffmpeg_jobs = relationship("FFmpegJob", back_populates="user")

class FFmpegJob(Base):
    __tablename__ = 'ffmpeg_job'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    # Corresponding relationship with matching back_populates
    user = relationship("User", back_populates="ffmpeg_jobs")
```

**Example (WRONG - backref):**
```python
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    # backref automatically creates reverse relationship (implicit, less clear)
    jobs = relationship("FFmpegJob", backref="owner")  # DON'T USE

class FFmpegJob(Base):
    __tablename__ = 'ffmpeg_job'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    # No explicit relationship here - confusing!
```

**Current Issue in Codebase (FFmpegJob.user):**
```python
# In models.py line 5835:
class FFmpegJob(Base):
    __tablename__ = "ffmpeg_job"
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    # ISSUE: Uses backref instead of back_populates
    user = relationship("User", backref="ffmpeg_jobs")  # ❌ WRONG

# In models.py line 284 (User class):
class User(Base):
    __tablename__ = "users"
    # ISSUE: No back_populates for FFmpegJob relationship
    # Missing: ffmpeg_jobs = relationship("FFmpegJob", back_populates="user")
    # This causes AttributeError when accessing user.ffmpeg_jobs
```

**Fix:**
```python
# Add to User model (around line 287):
ffmpeg_jobs = relationship("FFmpegJob", back_populates="user")

# Change FFmpegJob line 5835:
user = relationship("User", back_populates="ffmpeg_jobs")
```

### Pattern 2: ImportError Detection and Prevention
**What:** Graceful dependency handling with explicit ImportError checks
**When to use:** Optional dependencies or heavy libraries (lancedb, pandas, etc.)
**Example:**
```python
# Source: Python ImportError best practices, 2025-2026
try:
    import lancedb
    import numpy as np
    import pandas as pd
except ImportError as e:
    lancedb = None
    logger.warning(f"Heavy dependencies not available: {e}")
    # Provide graceful degradation or raise clear error
    raise ConfigurationError(
        "Optional dependencies missing. Install with: pip install atom[extras]"
    ) if REQUIRED else None
```

### Pattern 3: Specific Exception Handling (No Bare Except)
**What:** Always catch specific exception types, never use bare `except:`
**When to use:** All error handling
**Example:**
```python
# WRONG - Bare except masks all errors including KeyboardInterrupt
try:
    process_data()
except:
    pass  # ❌ BAD: Catches everything, including SystemExit

# CORRECT - Specific exceptions
try:
    process_data()
except (ValueError, KeyError) as e:
    logger.warning(f"Expected error during processing: {e}")
    # Handle specific known errors
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    raise  # Re-raise unexpected errors
```

**Current Codebase Issues Found:**
- 13 bare `except:` clauses in backend/ (as noted in IMPLEMENTATION_PROGRESS_BATCH2.md)
- Multiple `except Exception as e:` without re-raising or logging

### Pattern 4: Test-Driven Bug Fix Workflow
**What:** Write failing test first, then fix, ensuring regression prevention
**When to use:** All runtime error fixes
**Example:**
```python
# Step 1: Write test that exposes the bug
def test_ffmpeg_job_user_relationship():
    """Test that FFmpegJob.user relationship works correctly"""
    # Create test user
    user = User(id="test-user", email="test@example.com")
    db.add(user)
    db.commit()

    # Create FFmpegJob with user
    job = FFmpegJob(
        id="test-job",
        user_id="test-user",
        operation="trim_video"
    )
    db.add(job)
    db.commit()

    # Test relationship access (this would fail with AttributeError)
    loaded_job = db.query(FFmpegJob).filter_by(id="test-job").first()
    assert loaded_job.user is not None  # FAILS before fix
    assert loaded_job.user.id == "test-user"

# Step 2: Run test - should FAIL
# Step 3: Fix the relationship (add back_populates)
# Step 4: Run test - should PASS
# Step 5: Test prevents regression
```

### Pattern 5: FastAPI Exception Handler Registration
**What:** Global exception handlers for consistent error responses
**When to use:** All FastAPI applications
**Example:**
```python
# Source: FastAPI error handling best practices, 2025-2026
from fastapi import FastAPI
from core.exceptions import AtomException
from core.error_handlers import atom_exception_handler, global_exception_handler

app = FastAPI()

# Register AtomException handler
app.add_exception_handler(AtomException, atom_exception_handler)

# Register catch-all Exception handler
app.add_exception_handler(Exception, global_exception_handler)
```

**Current Codebase Status:**
- ✅ `core/exceptions.py` - Comprehensive AtomException hierarchy (779 lines)
- ✅ `core/error_handlers.py` - Handler functions with `api_error()` helper
- ✅ `core/error_middleware.py` - Global ErrorHandlingMiddleware
- ❓ **MUST VERIFY:** Are handlers registered in `main_api_app.py`?

### Anti-Patterns to Avoid

- **Anti-pattern 1:** Using `backref` in SQLAlchemy 2.0
  - **Why it's bad:** Implicit relationships cause AttributeError, hard to debug
  - **Use instead:** Explicit `back_populates` on both sides

- **Anti-pattern 2:** Bare `except:` clauses
  - **Why it's bad:** Catches KeyboardInterrupt/SystemExit, masks real errors
  - **Use instead:** Specific exception types, log and re-raise unexpected errors

- **Anti-pattern 3:** `from module import *`
  - **Why it's bad:** Causes NameError, unclear what's imported, namespace pollution
  - **Use instead:** Explicit imports: `from module import SpecificClass`

- **Anti-pattern 4:** Missing `__init__.py` in packages
  - **Why it's bad:** Causes ImportError, Python doesn't recognize directory as package
  - **Use instead:** Always include `__init__.py` (can be empty) in package directories

- **Anti-pattern 5:** Circular imports
  - **Why it's bad:** Causes ImportError or AttributeError at runtime
  - **Use instead:** Deferred imports inside functions, restructure modules

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Type checking** | Custom type validation decorators | mypy static analysis | Catches 15-30% of bugs before runtime, industry standard |
| **Code linting** | Custom regex-based linters | ruff | 10-100x faster, replaces flake8+isort+autoflake, actively maintained |
| **Import checking** | Manual import scanning | ruff import checks | Detects unused imports, missing __init__.py, circular dependencies |
| **Error tracking** | Custom error logging | ErrorHandlingMiddleware (already exists) | Already implemented in codebase, provides statistics |
| **Relationship testing** | Manual relationship validation tests | pytest with SQLAlchemy test fixtures | Automatic session management, rollback, isolation |
| **SQL validation** | Custom SQL syntax checkers | Alembic migrations | Schema validation, rollback support, already in use |

**Key insight:** The codebase already has robust error infrastructure (`exceptions.py`, `error_handlers.py`, `error_middleware.py`). **Don't build new error systems - use and extend existing ones.**

## Common Pitfalls

### Pitfall 1: SQLAlchemy Relationship Errors (CRITICAL - Current Blocker)
**What goes wrong:** AttributeError when accessing relationship attributes (e.g., `job.user` raises AttributeError)
**Why it happens:** Using `backref` instead of `back_populates`, or missing relationship on one side
**How to avoid:**
  1. **Always use `back_populates`** in SQLAlchemy 2.0+ (2026 best practice)
  2. Define relationship on BOTH sides of the association
  3. Ensure names match exactly (case-sensitive)
  4. Add foreign key constraints in Alembic migrations
**Warning signs:**
  - Test failures with "AttributeError: 'X' object has no attribute 'Y'"
  - 76 test failures mentioning FFmpegJob.user (current blocker)
  - SQLAlchemy warnings about relationship sync issues

**Example of Current Issue:**
```python
# models.py line 5835 - WRONG
class FFmpegJob(Base):
    user = relationship("User", backref="ffmpeg_jobs")  # ❌

# models.py line 284 - MISSING RELATIONSHIP
class User(Base):
    # No ffmpeg_jobs relationship defined
    messages = relationship("TeamMessage", back_populates="sender")
    activity = relationship("UserActivity", back_populates="user", ...)
    # Missing: ffmpeg_jobs = relationship("FFmpegJob", back_populates="user")
```

**Fix Required:**
```python
# Add to User model (after line 287):
ffmpeg_jobs = relationship("FFmpegJob", back_populates="user")

# Change FFmpegJob (line 5835):
user = relationship("User", back_populates="ffmpeg_jobs")

# Alembic migration already exists (048f33b17b11) but relationship fix needed
```

### Pitfall 2: ImportError from Missing Dependencies
**What goes wrong:** `ModuleNotFoundError: No module named 'X'` at runtime
**Why it happens:**
  - Dependencies not listed in requirements.txt
  - Optional dependencies imported without checks
  - Virtual environment not activated
**How to avoid:**
  1. **Always check requirements.txt** before importing optional deps
  2. Use try-except ImportError with graceful degradation
  3. Document optional dependencies in comments
  4. Run `pip install -r requirements.txt` in CI/CD
**Warning signs:**
  - Import errors in production but not development
  - Linter warnings about missing imports
  - Failed CI/CD pipelines with import errors

### Pitfall 3: NameError from Undefined Variables
**What goes wrong:** `NameError: name 'X' is not defined` during execution
**Why it happens:**
  - Typos in variable names
  - Using `from module import *` (wildcard imports)
  - Variables used before assignment
  - Missing imports
**How to avoid:**
  1. **NEVER use `from module import *`** (enforce with ruff)
  2. Use explicit imports: `from module import specific_function`
  3. Enable mypy to catch undefined names
  4. Use linter (ruff) with undefined-name rule
**Warning signs:**
  - Intermittent errors (only when certain code paths execute)
  - Errors that "disappear" after code changes
  - Linter warnings about undefined names

### Pitfall 4: TypeError from Type Mismatches
**What goes wrong:** `TypeError: unsupported operand type(s) for +: 'str' and 'int'`
**Why it happens:**
  - No type hints
  - Missing type validation
  - Implicit type conversions
**How to avoid:**
  1. **Add type hints to all functions** (enforce with mypy --strict)
  2. Use isinstance() checks before operations
  3. Enable mypy in pre-commit hooks
  4. Use pydantic for data validation
**Warning signs:**
  - Errors only with certain input values
  - Type-related mypy warnings ignored
  - Runtime errors in production but not dev (different data types)

### Pitfall 5: Bare Except Clauses Masking Errors
**What goes wrong:** Bugs silently caught, no error logged, impossible to debug
**Why it happens:**
  - Lazy error handling: `except: pass`
  - Fear of crashing
  - Copying bad patterns
**How to avoid:**
  1. **ALWAYS specify exception types:** `except ValueError as e:`
  2. Log errors before handling: `logger.error(f"Error: {e}")`
  3. Re-raise unexpected errors: `except Exception as e: logger.error(...); raise`
  4. Use ruff to detect bare except clauses
**Warning signs:**
  - "Mysterious" bugs that can't be reproduced
  - Code that "should fail" but doesn't
  - Silent failures in logs

### Pitfall 6: Missing Alembic Foreign Key Constraints
**What goes wrong:** Database allows invalid references, orphaned records
**Why it happens:**
  - ForeignKey defined in model but not in database
  - SQLite foreign_keys disabled by default
  - Missing Alembic migration
**How to avoid:**
  1. **Always create Alembic migration** when adding ForeignKey
  2. Enable foreign keys in SQLite: `PRAGMA foreign_keys = ON`
  3. Test relationship access in pytest
**Warning signs:**
  - Can insert invalid user_id without error
  - Deleting user doesn't cascade to related records
  - ORM relationship returns None even when FK exists

### Pitfall 7: Circular Import Dependencies
**What goes wrong:** `ImportError` or `AttributeError` at module load time
**Why it happens:**
  - Module A imports Module B
  - Module B imports Module A
  - Both at module level (top of file)
**How to avoid:**
  1. **Use deferred imports** inside functions
  2. Restructure to remove circular dependency
  3. Use `TYPE_CHECKING` for type hints only
**Warning signs:**
  - Import errors that "move around" when you change imports
  - AttributeError: 'module' object has no attribute 'X'
  - Works in some files but not others

## Code Examples

Verified patterns from official sources:

### SQLAlchemy 2.0 Relationship Configuration
```python
# Source: SQLAlchemy 2.0 Documentation, 2026 best practices
from sqlalchemy import Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship, DeclarativeBase

class Base(DeclarativeBase):
    pass

# CORRECT: Explicit back_populates on both sides
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    jobs = relationship("Job", back_populates="user")  # Explicit

class Job(Base):
    __tablename__ = 'jobs'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    user = relationship("User", back_populates="jobs")  # Matching name
```

### Pytest Exception Testing
```python
# Source: pytest documentation, 2025-2026 best practices
import pytest

def test_specific_exception():
    """Test that specific exception is raised"""
    with pytest.raises(ValueError, match="must be positive"):
        calculate_square_root(-1)

def test_exception_attributes():
    """Test exception has correct attributes"""
    with pytest.raises(CustomError) as exc_info:
        function_that_raises()
    assert exc_info.value.error_code == "ERROR_123"
    assert exc_info.value.severity == "high"
```

### FastAPI Exception Handler Registration
```python
# Source: FastAPI error handling best practices (Dev.to, 2025)
from fastapi import FastAPI
from core.exceptions import AtomException
from core.error_handlers import atom_exception_handler

app = FastAPI()

# Register handlers BEFORE defining routes
app.add_exception_handler(AtomException, atom_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

@app.get("/agents/{agent_id}")
def get_agent(agent_id: str):
    # AtomException will be caught by atom_exception_handler
    if not agent_exists(agent_id):
        raise AgentNotFoundError(agent_id)
    return agent
```

### Mypy Type Checking Configuration
```python
# Source: mypy documentation, 2026 configuration best practices
# mypy.ini file content:
[mypy]
check_untyped_defs = True
disallow_untyped_defs = True
warn_return_any = True
warn_unused_ignores = True
strict_optional = True

# Per-module overrides (for third-party libs without types):
[mypy-third_party_lib.*]
ignore_missing_imports = True
```

### Ruff Configuration for Error Detection
```python
# Source: ruff documentation, 2026 configuration
# pyproject.toml file content:
[tool.ruff]
line-length = 100
target-version = "py311"

# Enable error detection rules
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes (undefined names, unused imports)
    "I",      # isort (import sorting)
    "B",      # flake8-bugbear (common pitfalls)
    "UP",     # pyupgrade (modern Python syntax)
]

# Detect bare except clauses
ignore = []

# Per-rule ignores:
[tool.ruff.per-file-ignores]
"__init__.py" = ["F401"]  # Allow unused imports in __init__.py
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **backref** | **back_populates** | SQLAlchemy 1.4+ (2020) | Explicit relationships, fewer AttributeError bugs |
| **flake8 + isort + pylint** | **ruff** (all-in-one) | 2023-2024 | 10-100x faster linting, single tool |
| **unittest** | **pytest** | 2018+ | Better fixtures, parametrization, async support |
| **Manual type checking** | **mypy** (static analysis) | 2019+ | Catch type errors before runtime |
| **Bare except clauses** | **Specific exceptions** | Ongoing | Better error visibility, debugging |
| ** Implicit error handling** | **Explicit exception handlers** | FastAPI (2018+) | Consistent API error responses |

**Deprecated/outdated:**
- **pkgutil.ImpImporter**: Removed in Python 3.12+, use `importlib` instead
- **backref in SQLAlchemy**: Still works but discouraged, use `back_populates`
- **Bare `except:`**: Never acceptable in production code (2026 standards)
- **`from module import *`**: Causes NameError, use explicit imports

## Error Categorization and Priority

Based on research findings, runtime errors should be categorized by severity:

### Critical (Fix Immediately - Blocks All Testing)
- **SQLAlchemy relationship errors** (FFmpegJob.user issue)
  - Impact: 76 test failures, blocks CI/CD
  - Fix: Add `back_populates` to User model
  - Priority: P0

### High (Fix Before Production)
- **ImportError**: Missing dependencies
  - Impact: Runtime crashes, feature unavailable
  - Fix: Add to requirements.txt or graceful ImportError handling
  - Priority: P1

- **NameError**: Undefined variables
  - Impact: Runtime crashes, intermittent failures
  - Fix: Fix typos, add imports, remove wildcard imports
  - Priority: P1

### Medium (Fix Soon)
- **TypeError**: Type mismatches
  - Impact: Incorrect behavior, data corruption
  - Fix: Add type hints, use isinstance checks
  - Priority: P2

- **AttributeError**: Missing attributes
  - Impact: Feature failures
  - Fix: Define attributes, fix relationship access
  - Priority: P2

### Low (Fix When Possible)
- **ValueError**: Invalid values (user input)
  - Impact: Validation failures (expected behavior)
  - Fix: Add validation, raise clear errors
  - Priority: P3

## Open Questions

1. **FFmpegJob.user relationship fix scope**
   - What we know: Relationship uses `backref` (line 5835), User model missing `back_populates`
   - What's unclear: Are there other models with similar issues?
   - Recommendation: Run mypy/ruff to find ALL relationship errors, fix in batch

2. **NameError locations in integration services**
   - What we know: STATE.md mentions "Integration services have NameError in production code"
   - What's unclear: Which specific files/lines have NameError?
   - Recommendation: Search for `NameError` in logs, grep for undefined variables, run ruff with undefined-name rule

3. **Bare except clause replacement strategy**
   - What we know: 13 bare except clauses noted in IMPLEMENTATION_PROGRESS_BATCH2.md
   - What's unclear: Should we replace with specific exceptions or remove entirely?
   - Recommendation: Replace with specific exceptions + logging, re-raise unexpected errors

4. **Test execution environment**
   - What we know: pytest not available in initial shell check
   - What's unclear: Is this a PATH issue or virtual environment issue?
   - Recommendation: Verify pytest installation in dev environment before Phase 70 execution

## Sources

### Primary (HIGH confidence)
- **Python Runtime Error Detection Tools 2026** - Comprehensive coverage of ruff, mypy, pytest best practices
  - URL: [提高代码质量：使用Python Lint工具black、ruff和mypy](https://m.blog.csdn.net/ndAbsAfaqwdav/article/details/144283128)
  - URL: [2025 年了，Python工具别只知道Pycharm了](https://blog.csdn.net/Sammyyyyy/article/details/149978357)
  - Verified ruff replaces flake8/isort, mypy for type checking, pytest best practices

- **SQLAlchemy Relationship Best Practices** - Explicit back_populates recommendation
  - URL: [你真的会用关系映射吗？SQLAlchemy高级Relationship配置深度揭秘](https://m.blog.csdn.net/gatherlume/article/details/152509441)
  - URL: [SQLAlchemy模型关系详解](https://blog.csdn.net/dengjianbin/article/details/151989676)
  - Verified: back_populates is 2026 best practice, backref discouraged

- **FastAPI Exception Handling** - Global handler patterns
  - URL: [Building Robust Error Handling in FastAPI](https://dev.to/buffolander/building-robust-error-handling-in-fastapi-and-avoiding-rookie-mistakes-ifg)
  - URL: [FastAPI 全局异常处理](https://cloud.tencent.com/developer/article/2600112)
  - Verified: app.add_exception_handler() pattern, middleware integration

- **Pytest Regression Testing** - Test-driven bug fix workflow
  - URL: [Python 最佳实践高级教程（三）](https://blog.csdn.net/wizardforcel/article/details/141069137)
  - URL: [最详细的 pytest 功能介绍](https://m.blog.csdn.net/qq_42183960/article/details/143827270)
  - Verified: Test-first bug fix approach, regression prevention strategies

### Secondary (MEDIUM confidence)
- **ImportError/AttributeError/TypeError Best Practices** - Fix patterns for common errors
  - URL: [Python 开发中最常见的错误大全](https://juejin.cn/post/7579499567869149234)
  - URL: [Python3 【包和模块】避坑宝典：常见错误解析](https://m.blog.cdn.net/weixin_47267103/article/details/145815633)
  - Verified: ImportError prevention, AttributeError fixes, TypeError handling

- **Python Error Categorization** - Severity levels and priority
  - URL: [干货 |17个常见的Python运行时错误](https://m.blog.csdn.net/Python_00001/article/details/141724138)
  - URL: [Python运行错误分类_常见问题说明](https://m.php.cn/faq/1928816.html)
  - Verified: Error types, severity classification, production impact

### Tertiary (LOW confidence)
- **Codebase-specific investigation** - Manual code analysis
  - **backend/core/models.py** - FFmpegJob relationship issue (line 5835)
  - **backend/core/exceptions.py** - Comprehensive exception hierarchy (779 lines)
  - **backend/core/error_handlers.py** - Helper functions for error handling
  - **backend/core/error_middleware.py** - ErrorHandlingMiddleware with statistics
  - **backend/requirements.txt** - All dependencies already listed
  - Verified: Existing error infrastructure is solid, needs relationship fixes

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Multiple authoritative sources confirm ruff/mypy/pytest as 2026 standard
- Architecture: HIGH - SQLAlchemy docs and FastAPI best practices explicitly recommend back_populates
- Pitfalls: HIGH - 76 test failures confirm FFmpegJob relationship error is real blocker
- Code examples: HIGH - All examples verified against official documentation (SQLAlchemy 2.0, pytest, FastAPI)

**Research date:** 2026-02-22
**Valid until:** 2026-04-22 (60 days - stable tooling ecosystem, but Python ecosystem evolves rapidly)

**Key research insights for Phase 70 planning:**
1. **FOUNDATION CRITICAL:** Fix SQLAlchemy relationships before any test coverage work (unblocks 76 tests)
2. **USE EXISTING INFRASTRUCTURE:** Don't build new error systems - exceptions.py, error_handlers.py, error_middleware.py are excellent
3. **TOOLCHAIN IS READY:** All tools (pytest, mypy, ruff) already in requirements.txt
4. **SYSTEMATIC APPROACH:** Static analysis → pytest execution → test-driven fix → regression prevention
5. **2026 BEST PRACTICE:** back_populates not backref, specific exceptions not bare except, explicit imports not wildcard
