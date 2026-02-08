# Code Quality Guide for Atom

**Last Updated**: February 4, 2026

This guide establishes code quality standards and provides tools to maintain them across the Atom codebase.

---

## Overview

Code quality is critical for:
- **Maintainability**: Easier to understand and modify
- **Reliability**: Fewer bugs and edge cases
- **Performance**: Optimized code execution
- **Collaboration**: Consistent style across team members

---

## Code Quality Tools

### Required Tools

Install these tools for local development:

```bash
# Linting and formatting
pip install flake8 black isort mypy

# Type stubs
pip install types-requests types-pyyaml

# Pre-commit hooks
pip install pre-commit
```

### Tool Configuration Files

- `.flake8` - Flake8 linting configuration
- `.isort.cfg` - Import sorting configuration (already exists)
- `pyproject.toml` - Black and mypy configuration

---

## Code Quality Standards

### 1. Code Style (PEP 8 + Black)

**Line Length**: Maximum 120 characters

```python
# Bad: Line too long
def some_very_long_function_name(parameter_one, parameter_two, parameter_three, parameter_four, parameter_five):
    pass

# Good: Break into multiple lines
def some_very_long_function_name(
    parameter_one,
    parameter_two,
    parameter_three,
    parameter_four,
    parameter_five
):
    pass
```

**Indentation**: 4 spaces (no tabs)

```python
# Good
if condition:
    do_something()
    if another_condition:
        do_another_thing()
```

**Blank Lines**: 2 blank lines between top-level definitions, 1 blank line between methods

```python
# Good
class MyClass:
    def method_one(self):
        pass

    def method_two(self):
        pass


def my_function():
    pass
```

**Imports**: Organized into 3 groups (standard library, third-party, local)

```python
# Good
import os
import sys
from typing import Dict, List

import fastapi
from sqlalchemy.orm import Session

from core.models import User
from core.database import get_db
```

### 2. Type Hints

All functions should have type hints for parameters and return values.

```python
# Bad
def process_user(user_id, data):
    # What types are these?
    return result

# Good
from typing import Dict, Any

def process_user(user_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Process user data"""
    return result
```

**Complex Type Hints**:

```python
from typing import List, Dict, Optional, Union, Callable, AsyncIterator

def complex_function(
    items: List[Dict[str, Any]],
    callback: Optional[Callable[[str], bool]] = None,
    max_attempts: int = 3
) -> AsyncIterator[str]:
    """Process items with optional callback"""
    pass
```

### 3. Docstrings

All public functions, classes, and methods should have docstrings.

**Google Style Docstrings** (Preferred):

```python
def create_user(
    email: str,
    name: str,
    role: str = "member"
) -> User:
    """Create a new user in the system.

    Args:
        email: User's email address (must be unique)
        name: User's display name
        role: User's role (member, admin, etc.)

    Returns:
        User: Created user object with ID assigned

    Raises:
        ValueError: If email already exists
        ValidationError: If email format is invalid

    Example:
        >>> user = create_user("test@example.com", "Test User")
        >>> print(user.id)
        'abc-123-def'
    """
    pass
```

**Class Docstrings**:

```python
class AgentGovernanceService:
    """Manages agent lifecycle, permissions, and maturity tracking.

    This service provides:
    - Agent registration and updates
    - Permission checking for agent operations
    - Maturity level tracking and promotion
    - Execution audit logging

    Attributes:
        cache: Governance cache for fast lookups
        db: Database session for persistence

    Example:
        >>> service = AgentGovernanceService()
        >>> allowed = await service.check_permission(agent_id, "browser_automation")
        >>> print(allowed)
        True
    """

    def __init__(self):
        """Initialize the governance service."""
        pass
```

### 4. Error Handling

**Specific Exceptions**:

```python
# Bad: Catching all exceptions
try:
    result = risky_operation()
except Exception:
    pass  # Silent failure!

# Good: Catch specific exceptions
try:
    result = risky_operation()
except ValueError as e:
    logger.error(f"Invalid value: {e}")
    raise
except ConnectionError as e:
    logger.warning(f"Connection failed, retrying: {e}")
    result = retry_operation()
```

**Custom Exceptions**:

```python
class AgentNotFoundError(Exception):
    """Raised when an agent is not found"""

    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        super().__init__(f"Agent {agent_id} not found")

# Usage
if not agent:
    raise AgentNotFoundError(agent_id)
```

**Error Messages**:

```python
# Bad
raise Exception("Error")

# Good
raise ValueError(
    f"Invalid maturity level '{level}'. "
    f"Must be one of: {', '.join(MaturityLevel.__members__.keys())}"
)
```

### 5. Logging

**Use Appropriate Log Levels**:

```python
import logging

logger = logging.getLogger(__name__)

# DEBUG: Detailed information for debugging
logger.debug(f"Variable x = {x}")

# INFO: General information about execution
logger.info(f"Processing workflow {workflow_id}")

# WARNING: Something unexpected but recoverable
logger.warning(f"Retry {attempt}/{max_retries} failed")

# ERROR: Error occurred but application continues
logger.error(f"Failed to connect to database: {e}")

# CRITICAL: Serious error, application may crash
logger.critical(f"Cannot start application: {e}")
```

**Structured Logging**:

```python
# Good: Structured logging with context
logger.info(
    "Agent execution completed",
    extra={
        "agent_id": agent_id,
        "execution_id": execution_id,
        "duration_ms": duration,
        "success": True
    }
)

# Good: Include relevant details in error
logger.error(
    f"Workflow execution failed: {error}",
    extra={
        "workflow_id": workflow_id,
        "step_id": step_id,
        "attempt": attempt,
        "error_type": type(error).__name__
    }
)
```

### 6. Async/Await Patterns

**Use async for I/O operations**:

```python
# Good: Async database operations
async def get_user(user_id: str) -> Optional[User]:
    async with get_async_db_session() as db:
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
```

**Avoid blocking in async functions**:

```python
# Bad: Blocking call in async function
async def process_data(data: str):
    time.sleep(1)  # Blocks event loop!
    return data.upper()

# Good: Async sleep
async def process_data(data: str):
    await asyncio.sleep(1)  # Non-blocking
    return data.upper()
```

### 7. Constants

**Use UPPER_CASE for constants**:

```python
# Constants at module level
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 30
CACHE_TTL_SECONDS = 3600

# Use in code
async def fetch_with_retry(url: str):
    for attempt in range(MAX_RETRIES):
        try:
            return await fetch(url, timeout=DEFAULT_TIMEOUT)
        except TimeoutError:
            if attempt >= MAX_RETRIES - 1:
                raise
```

**Configuration Enums**:

```python
from enum import Enum

class MaturityLevel(str, Enum):
    """Agent maturity levels"""
    STUDENT = "student"
    INTERN = "intern"
    SUPERVISED = "supervised"
    AUTONOMOUS = "autonomous"

# Usage
if agent.maturity < MaturityLevel.AUTONOMOUS:
    require_approval()
```

---

## Code Quality Automation

### Pre-commit Hooks

Install pre-commit hooks to automatically check code quality:

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run hooks manually
pre-commit run --all-files
```

**`.pre-commit-config.yaml`**:

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.12.0
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/pycqa/isort
    rev: 5.13.0
    hooks:
      - id: isort

  - repo: https://github.com/pycqa/flake8
    rev: 7.0.0
    hooks:
      - id: flake8

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies:
          - types-requests
          - types-pyyaml
```

### CI/CD Integration

**GitHub Actions Workflow** (`.github/workflows/code-quality.yml`):

```yaml
name: Code Quality

on: [push, pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install black isort flake8 mypy

      - name: Check code formatting (Black)
        run: black --check backend/

      - name: Check import sorting (isort)
        run: isort --check-only backend/

      - name: Lint with flake8
        run: flake8 backend/ --count --select=E9,F63,F7,F82 --show-source --statistics

      - name: Type check with mypy
        run: mypy backend/core/ --ignore-missing-imports
```

---

## Code Quality Checklist

### Before Committing Code

- [ ] Code formatted with Black
- [ ] Imports sorted with isort
- [ ] No flake8 errors
- [ ] Type hints added to all functions
- [ ] Docstrings added to public functions/classes
- [ ] Tests added for new functionality
- [ ] All tests passing
- [ ] No debug/TODO comments left in
- [ ] Logging added for important operations
- [ ] Error handling implemented

### Code Review Checklist

- [ ] Code follows style guide
- [ ] Sufficient error handling
- [ ] No security vulnerabilities
- [ ] Performance considerations addressed
- [ ] Tests cover edge cases
- [ ] Documentation updated
- [ ] No hardcoded credentials
- [ ] Database queries optimized
- [ ] No memory leaks
- [ ] Thread safety considered (if applicable)

---

## Common Code Quality Issues

### 1. Missing Type Hints

**Issue**: Functions without type hints

```python
# Bad
def calculate(data):
    return sum(data)

# Good
from typing import List

def calculate(data: List[float]) -> float:
    return sum(data)
```

### 2. Overly Complex Functions

**Issue**: Functions doing too much

```python
# Bad: 200+ line function
def process_workflow(workflow_id: str):
    # 200 lines of logic
    pass

# Good: Break into smaller functions
def process_workflow(workflow_id: str):
    workflow = load_workflow(workflow_id)
    validate_workflow(workflow)
    execute_workflow(workflow)
    save_results(workflow)
```

### 3. Magic Numbers

**Issue**: Unexplained numeric values

```python
# Bad
if value > 0.7:
    promote_agent()

# Good
CONFIDENCE_THRESHOLD = 0.7

if value > CONFIDENCE_THRESHOLD:
    promote_agent()
```

### 4. Deep Nesting

**Issue**: Code nested too deep

```python
# Bad
if condition1:
    if condition2:
        if condition3:
            do_something()

# Good: Early returns
if not condition1:
    return
if not condition2:
    return
if condition3:
    do_something()
```

### 5. Large Classes

**Issue**: Classes with too many responsibilities

```python
# Bad: 3000+ line class
class AdvancedWorkflowOrchestrator:
    # 50+ methods
    pass

# Good: Split into multiple classes
class WorkflowOrchestrator:
    """Main orchestration logic"""
    pass

class WorkflowExecutor:
    """Execute workflow steps"""
    pass

class WorkflowValidator:
    """Validate workflow definitions"""
    pass
```

---

## Performance Considerations

### Database Queries

```python
# Bad: N+1 query problem
async def get_users_with_sessions():
    users = await db.execute(select(User))
    for user in users:
        sessions = await db.execute(  # N+1 problem!
            select(UserSession).where(UserSession.user_id == user.id)
        )

# Good: Eager loading
from sqlalchemy.orm import selectinload

async def get_users_with_sessions():
    result = await db.execute(
        select(User)
        .options(selectinload(User.sessions))
    )
    return result.scalars().all()
```

### Caching

```python
# Good: Cache expensive operations
from functools import lru_cache

@lru_cache(maxsize=128)
def get_governance_config(agent_id: str) -> Dict[str, Any]:
    """Get governance configuration (cached)"""
    # Expensive operation
    return load_config(agent_id)
```

---

## Security Best Practices

### 1. Input Validation

```python
# Good: Validate input
from pydantic import BaseModel, validator

class CreateUserRequest(BaseModel):
    email: str
    name: str

    @validator('email')
    def validate_email(cls, v):
        if '@' not in v:
            raise ValueError('Invalid email format')
        return v
```

### 2. SQL Injection Prevention

```python
# Bad: String concatenation
query = f"SELECT * FROM users WHERE email = '{email}'"

# Good: Parameterized queries
query = select(User).where(User.email == email)
```

### 3. Secret Management

```python
# Bad: Hardcoded secrets
API_KEY = "sk-1234567890"

# Good: Environment variables
from core.config import get_config
config = get_config()
api_key = config.api_key
```

---

## Testing Best Practices

### Test Coverage

```python
# Good: Comprehensive test cases
def test_agent_governance():
    # Test happy path
    assert check_permission(agent_id, "read") is True

    # Test denied permission
    assert check_permission(agent_id, "delete") is False

    # Test edge cases
    with pytest.raises(AgentNotFoundError):
        check_permission("invalid_id", "read")
```

### Test Organization

```python
# Good: Organized test class
class TestAgentGovernance:
    def test_check_permission_allowed(self):
        pass

    def test_check_permission_denied(self):
        pass

    def test_check_permission_invalid_agent(self):
        pass
```

---

## Code Quality Metrics

Track these metrics to measure code quality:

| Metric | Target | Tool |
|--------|--------|------|
| Test Coverage | >80% | pytest-cov |
| Cyclomatic Complexity | <15 | flake8 |
| Code Duplication | <5% | pylint |
| Type Hint Coverage | >90% | mypy |
| Documentation Coverage | >70% | interrogate |

---

## Resources

- **PEP 8**: https://peps.python.org/pep-0008/
- **PEP 257** (Docstrings): https://peps.python.org/pep-0257/
- **Type Hints**: https://docs.python.org/3/library/typing.html
- **Google Python Style Guide**: https://google.github.io/styleguide/pyguide.html

---

## Summary

Following this code quality guide ensures:
- ✅ Consistent code style across the codebase
- ✅ Fewer bugs through type hints and linting
- ✅ Better documentation through docstrings
- ✅ Easier onboarding for new developers
- ✅ More maintainable codebase

---

*Last updated: February 4, 2026*
