# Code Quality Standards

**Version:** 1.0
**Last Updated:** 2026-02-16
**Applies to:** All Python code in the Atom backend

## Overview

This document defines the code quality standards for the Atom backend project. Following these standards ensures maintainable, reliable, and production-ready code.

## Type Hints

### Requirements

- **New code:** MUST have 100% type hint coverage on all function signatures
- **Existing code:** Incremental adoption - add type hints when modifying functions
- **Type checking:** Run MyPy locally before committing changes

### Type Hint Patterns

```python
# Function signatures MUST include parameter types and return types
def process_agent(agent_id: str, maturity_level: int) -> Dict[str, Any]:
    """Process an agent with given maturity level."""
    pass

# Use Optional for nullable types
def get_agent(agent_id: str) -> Optional[AgentRegistry]:
    """Get agent by ID, returns None if not found."""
    pass

# Use complex types for collections
def list_agents(category: Optional[str] = None) -> List[AgentRegistry]:
    """List agents by category."""
    pass

# Async functions must specify return types
async def execute_workflow(workflow_id: str) -> WorkflowExecution:
    """Execute a workflow asynchronously."""
    pass
```

### Import Required Types

```python
from typing import Any, Dict, List, Optional, Union, Callable, AsyncIterator
```

### MyPy Configuration

MyPy is configured in `backend/mypy.ini`:

- **Python version:** 3.11
- **Incremental adoption:** `disallow_untyped_defs = False`
- **Check untyped defs:** Enabled to gradually add type hints
- **Third-party libs:** Missing imports ignored

### Running MyPy

```bash
# Type check specific files
cd backend && mypy core/llm/byok_handler.py

# Type check entire core directory
cd backend && mypy core/ --config-file mypy.ini

# Type check with verbose output
cd backend && mypy core/ --show-error-codes --show-error-context
```

## Error Handling

### Principles

1. **Use specific exception types** - Never catch bare `Exception:` if you can be more specific
2. **Log with context** - Always include relevant context in error messages
3. **Preserve stack traces** - Use `raise ... from e` for exception chaining
4. **Never swallow exceptions silently** - Always log or handle appropriately

### Error Handling Patterns

```python
# Standardized error handling with context
try:
    agent = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
    if not agent:
        raise ValueError(f"Agent not found: {agent_id}")
except SQLAlchemyError as e:
    logger.error(f"Database error while fetching agent {agent_id}: {e}")
    raise

# Validation errors with descriptive messages
def validate_agent_maturity(agent: AgentRegistry, action: str) -> None:
    """Validate agent maturity for performing an action."""
    required_level = ACTION_COMPLEXITY.get(action, 2)
    if agent.confidence_score < required_level:
        raise ValueError(
            f"Agent {agent.name} (score: {agent.confidence_score}) "
            f"insufficient for {action} (required: {required_level})"
        )

# Exception chaining to preserve stack traces
try:
    result = await external_service_call()
except httpx.HTTPError as e:
    logger.error(f"External service error: {e}")
    raise ExternalServiceError(f"Failed to call external service: {e}") from e
```

### Exception Categories

- **Database errors:** `SQLAlchemyError`, `IntegrityError`
- **Validation errors:** `ValueError`, `ValidationError`
- **Not found errors:** Return `None` or raise specific exception
- **Permission errors:** Custom `PermissionDeniedException`
- **External service errors:** `ExternalServiceError`, `HTTPError`

## Logging

### Standards

- **Use structlog** for structured logging with context
- **Include relevant context** in all log messages
- **Use appropriate log levels:** DEBUG, INFO, WARNING, ERROR, CRITICAL

### Logging Patterns

```python
import structlog

logger = structlog.get_logger(__name__)

# Debug level for detailed troubleshooting
logger.debug(f"Cache HIT for governance check: {agent_id}:{action_type}")

# Info level for normal operations
logger.info(f"Registered new agent: {name}", agent_id=agent.id)

# Warning level for unexpected but recoverable issues
logger.warning(f"Failed to initialize {provider_id} client: {e}")

# Error level for failures
logger.error(f"LLM Generation failed: {e}", agent_id=agent_id)

# Critical level for system-wide failures
logger.critical(f"Database connection lost: {e}")
```

### Context Enrichment

```python
# Include relevant context in log messages
logger.info(
    "Agent maturity transition",
    agent_id=agent.id,
    agent_name=agent.name,
    previous_status=previous_status,
    new_status=agent.status,
    confidence_score=new_score
)
```

## Documentation

### Docstring Standards

All functions MUST have Google-style docstrings with Args and Returns sections:

```python
def process_workflow(
    workflow_id: str,
    inputs: Dict[str, Any],
    timeout: int = 30
) -> Optional[WorkflowExecution]:
    """
    Process a workflow with given inputs.

    Args:
        workflow_id: Unique identifier for the workflow
        inputs: Dictionary of input parameters for the workflow
        timeout: Maximum execution time in seconds (default: 30)

    Returns:
        WorkflowExecution object if successful, None if failed

    Raises:
        ValueError: If workflow_id is invalid
        TimeoutError: If workflow execution exceeds timeout
    """
    pass
```

### Comment Standards

- **Comment WHY, not WHAT** - Code should be self-explanatory about what it does
- **Keep comments up to date** - Outdated comments are worse than no comments
- **Use docstrings for function/module documentation** - Use inline comments for complex logic

```python
# GOOD: Explains why we're doing this
# Use 0.5 only if confidence_score is None, not if it's 0.0
current = agent.confidence_score if agent.confidence_score is not None else 0.5

# BAD: Just repeats what the code says
# Set current to confidence_score
current = agent.confidence_score if agent.confidence_score is not None else 0.5
```

## Code Formatting

### Standards

- **Use Black** for code formatting (88 character line length)
- **Use Ruff** for fast linting
- **Format on save** - Configure your IDE to format code automatically

### Configuration

Black and Ruff configuration in `backend/pyproject.toml`:

```toml
[tool.black]
line-length = 88
target-version = ['py311']

[tool.ruff]
line-length = 88
select = ["E", "F", "I", "N", "W"]
```

### Running Formatters

```bash
# Format code with Black
cd backend && black .

# Check formatting without modifying
cd backend && black --check .

# Lint with Ruff
cd backend && ruff check .

# Auto-fix linting issues
cd backend && ruff check --fix .
```

## Testing Standards

### Principles

- **Use pytest** for all testing
- **Type-safe fixtures** - Add type hints to test fixtures
- **Arrange-Act-Assert** pattern for clear test structure
- **Test names should describe behavior** - `test_agent_promotion_when_confidence_exceeds_threshold`

### Test Patterns

```python
import pytest
from core.models import AgentRegistry
from core.agent_governance_service import AgentGovernanceService

def test_agent_promotion_when_confidence_exceeds_threshold(db_session: Session):
    """
    Test that agent is promoted to AUTONOMOUS when confidence exceeds 0.9.
    """
    # Arrange
    governance = AgentGovernanceService(db_session)
    agent = AgentRegistry(
        name="Test Agent",
        category="testing",
        confidence_score=0.95
    )
    db_session.add(agent)
    db_session.commit()

    # Act
    result = governance.enforce_action(agent.id, "delete")

    # Assert
    assert result["proceed"] is True
    assert result["status"] == "APPROVED"
```

### Test Coverage Goals

- **Critical paths:** 90%+ coverage (governance, LLM routing, workflows)
- **Business logic:** 80%+ coverage
- **Overall:** 70%+ coverage

## Code Review Checklist

Before submitting a PR, verify:

- [ ] All functions have type hints (parameters and return types)
- [ ] MyPy passes without critical errors
- [ ] Black formatting applied
- [ ] Ruff linting passes
- [ ] All functions have docstrings (Args/Returns)
- [ ] Error handling uses specific exception types
- [ ] No bare `except:` clauses
- [ ] Logging includes relevant context
- [ ] Tests added for new functionality
- [ ] Tests pass locally

## Continuous Integration

MyPy will be integrated into CI/CD pipeline:

```yaml
# Type check with mypy (commented out during incremental adoption)
# - name: Type check with mypy
#   run: mypy core/ --config-file backend/mypy.ini
```

**Note:** During incremental adoption, MyPy is run locally but not enforced in CI. Once type coverage reaches 80%, CI enforcement will be enabled.

## Resources

- [MyPy Documentation](https://mypy.readthedocs.io/)
- [Black Documentation](https://black.readthedocs.io/)
- [Ruff Documentation](https://docs.astral.sh/ruff/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [PEP 8 - Style Guide for Python Code](https://peps.python.org/pep-0008/)

## Compliance

All Atom backend developers MUST follow these standards. Code that does not meet these standards will not be merged to main.

**Questions?** Contact the platform team or open an issue in the repository.
