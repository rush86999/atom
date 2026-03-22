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

### Test File Naming Convention

**Critical Rule:** Test filenames must be unique across the entire test suite, regardless of directory.

Python's import system is basename-based, not path-based. Files with identical basenames in different directories cause collection errors.

**Naming Patterns:**
- Primary service tests: `test_<service>_coverage.py` (e.g., `test_agent_governance_service_coverage.py`)
- Module-specific tests: `test_<service>_<module>.py` (e.g., `test_agent_graduation_service_memory.py`)
- Extended coverage: `test_<service>_coverage_extend.py` (e.g., `test_cognitive_tier_system_coverage_extend.py`)

**Examples:**
```
tests/core/agents/test_agent_graduation_service_coverage.py      # Primary coverage
tests/core/memory/test_agent_graduation_service_memory.py         # Memory module tests
tests/core/episodes/test_episode_retrieval_service_coverage.py    # Primary coverage
tests/core/memory/test_episode_retrieval_memory.py                # Memory module tests
tests/core/llm/test_cognitive_tier_system_coverage.py            # Primary coverage
tests/core/llm/test_cognitive_tier_system_coverage_extend.py      # Extended coverage
```

**Anti-Patterns to Avoid:**
- DO NOT use same basename in different directories: `tests/core/agents/test_foo.py` and `tests/core/memory/test_foo.py`
- DO NOT rely on directory structure for uniqueness (Python ignores directories in module resolution)
- DO NOT ignore collection errors (they mask missing tests and inflate coverage gaps)

**Verifying Uniqueness:**
```bash
# Check for duplicate test basenames
find tests/ -name "test_*.py" -type f | xargs -n1 basename | sort | uniq -d
# Expected: No output (no duplicates)
```

**Collection Error Detection:**
```bash
# Check for collection errors before committing
pytest --collect-only -q 2>&1 | grep -c "ERROR collecting"
# Expected: 0
```

### Security Testing Patterns

Security tests validate defense-in-depth protections against real-world attacks. Use these patterns when testing sandbox execution, package installation, or external code execution.

#### Container Escape Tests

Validate Docker isolation prevents breakout attempts:

```python
class TestContainerEscape:
    """Container escape attack prevention tests."""

    @patch('core.skill_sandbox.docker.from_env')
    def test_privileged_mode_disabled(self, mock_docker, mock_docker_client):
        """
        Verify containers NEVER run with --privileged flag.

        Privileged mode disables all security mechanisms and allows
        full host access (CVE-2019-5736, CVE-2025-9074).

        Security: CRITICAL
        """
        mock_docker.return_value = mock_docker_client

        sandbox = HazardSandbox()
        sandbox.execute_python(code="print('test')", inputs={})

        # Verify privileged=False (or not set, default is False)
        call_kwargs = mock_docker_client.containers.run.call_args[1]
        assert call_kwargs.get('privileged', False) == False, \
            "Container must NOT run in privileged mode"

    @patch('core.skill_sandbox.docker.from_env')
    def test_docker_socket_not_mounted(self, mock_docker, mock_docker_client):
        """
        Verify Docker socket is NEVER mounted in containers.

        Mounting /var/run/docker.sock enables container escape
        and full host control (Docker-out-of-Docker attack).

        Security: CRITICAL
        """
        mock_docker.return_value = mock_docker_client

        sandbox = HazardSandbox()
        sandbox.execute_python(code="print('test')", inputs={})

        call_kwargs = mock_docker_client.containers.run.call_args[1]
        volumes = call_kwargs.get('volumes', {})

        assert '/var/run/docker.sock' not in str(volumes), \
            "Docker socket must NOT be mounted (enables container escape)"
```

#### Resource Exhaustion Tests

Validate resource limits prevent DoS attacks:

```python
class TestResourceExhaustion:
    """Resource limit enforcement tests."""

    @patch('core.skill_sandbox.docker.from_env')
    def test_memory_limit_enforced(self, mock_docker, mock_docker_client):
        """
        Verify memory limit is set to prevent exhaustion attacks.

        Security: HIGH - Memory exhaustion can DoS the host
        """
        mock_docker.return_value = mock_docker_client

        sandbox = HazardSandbox()
        sandbox.execute_python(
            code="print('test')",
            inputs={},
            memory_limit="256m"
        )

        # Verify mem_limit is set
        call_kwargs = mock_docker_client.containers.run.call_args[1]
        assert call_kwargs.get('mem_limit') == "256m", \
            "Memory limit must be enforced to prevent exhaustion attacks"

    @patch('core.skill_sandbox.docker.from_env')
    def test_cpu_quota_enforced(self, mock_docker, mock_docker_client):
        """
        Verify CPU quota is set to prevent CPU exhaustion.

        Security: HIGH - CPU exhaustion can starve host processes
        """
        mock_docker.return_value = mock_docker_client

        sandbox = HazardSandbox()
        sandbox.execute_python(
            code="print('test')",
            inputs={},
            cpu_limit=0.5
        )

        # Verify cpu_quota is set (0.5 * 100000 = 50000)
        call_kwargs = mock_docker_client.containers.run.call_args[1]
        assert call_kwargs.get('cpu_quota') == 50000, \
            "CPU quota must be enforced (0.5 * 100000)"
```

#### Network Isolation Tests

Validate network isolation prevents data exfiltration:

```python
class TestNetworkIsolation:
    """Network isolation enforcement tests."""

    @patch('core.skill_sandbox.docker.from_env')
    def test_network_disabled(self, mock_docker, mock_docker_client):
        """
        Verify network is disabled to prevent data exfiltration.

        Security: CRITICAL - Network isolation prevents outbound attacks
        """
        mock_docker.return_value = mock_docker_client

        sandbox = HazardSandbox()
        sandbox.execute_python(code="print('test')", inputs={})

        # Verify network_disabled=True
        call_kwargs = mock_docker_client.containers.run.call_args[1]
        assert call_kwargs.get('network_disabled') is True, \
            "Network must be disabled to prevent data exfiltration"
```

#### Malicious Pattern Detection Tests

Validate static scanning detects malicious code patterns:

```python
class TestMaliciousPatternDetection:
    """Static scanning detects malicious patterns."""

    def test_subprocess_usage_detected(self, security_scanner):
        """
        Static scan detects subprocess usage.

        Security: HIGH - subprocess enables arbitrary command execution
        """
        malicious_code = """
import subprocess
user_input = 'rm -rf /'
subprocess.call(user_input, shell=True)
"""

        result = security_scanner.scan_skill(
            skill_name="malicious-subprocess",
            skill_content=malicious_code
        )

        assert result["safe"] == False, "Subprocess usage must be blocked"
        assert len(result["findings"]) > 0, "Security findings must be reported"
        assert any("subprocess" in f.lower() for f in result["findings"]), \
            "Finding must mention subprocess"

    def test_base64_obfuscation_detected(self, security_scanner):
        """
        Static scan detects base64 obfuscation.

        Security: HIGH - Base64 obfuscation hides malicious payloads
        """
        malicious_code = """
import base64
payload = 'c3VicHJvY2Vzcy5ydW4oWyJybSIsICJyZiIsICIvIl0p'
decoded = base64.b64decode(payload).decode()
exec(decoded)
"""

        result = security_scanner.scan_skill(
            skill_name="obfuscated-base64",
            skill_content=malicious_code
        )

        # Should detect base64.b64decode as suspicious
        assert result["safe"] == False or len(result["findings"]) > 0, \
            "Base64 obfuscation must be flagged"
```

#### Governance Blocking Tests

Validate maturity-based access controls:

```python
class TestGovernanceBlocking:
    """Maturity-based governance blocks unauthorized access."""

    def test_student_agent_blocked_from_python_packages(self, governance, db_session: Session):
        """
        STUDENT agents cannot use Python packages (non-negotiable).

        Security: CRITICAL - Educational restriction, cannot be bypassed
        """
        student_agent = StudentAgentFactory(_session=db_session)
        db_session.commit()

        result = governance.check_package_permission(
            agent_id=student_agent.id,
            package_name="numpy",
            version="1.21.0",
            db=db_session
        )

        assert result["allowed"] == False, \
            "STUDENT agents must be blocked from ALL Python packages"
        assert "STUDENT agents cannot" in result["reason"], \
            "Reason must mention STUDENT restriction"

    def test_banned_package_blocks_all_agents(self, governance, db_session: Session):
        """
        Banned packages block ALL agents regardless of maturity.

        Security: CRITICAL - Ban list overrides all other rules
        """
        # Ban package
        governance.ban_package(
            package_name="malicious-lib",
            version="1.0.0",
            reason="Security vulnerability: CVE-2025-99999",
            db=db_session
        )

        # Create AUTONOMOUS agent (highest maturity)
        autonomous_agent = AutonomousAgentFactory(_session=db_session)
        db_session.commit()

        result = governance.check_package_permission(
            agent_id=autonomous_agent.id,
            package_name="malicious-lib",
            version="1.0.0",
            db=db_session
        )

        assert result["allowed"] == False, \
            "Banned packages must block even AUTONOMOUS agents"
        assert "banned" in result["reason"].lower(), \
            "Reason must mention ban"
```

#### Security Testing Best Practices

1. **Mock external dependencies** - Use `@patch` decorators to mock Docker, subprocess calls
2. **Test malicious fixtures** - Create fixture files with attack samples for reproducible testing
3. **Defense-in-depth validation** - Test all security layers (static scan + sandbox + governance)
4. **Security level annotations** - Mark tests with security level (CRITICAL, HIGH, MEDIUM, LOW)
5. **Clear assertion messages** - Explain WHY the security constraint is critical (reference CVEs)
6. **Use malicious package fixtures** - Import from `tests.fixtures.malicious_packages` for attack samples

Reference: `backend/tests/test_package_security.py` for comprehensive examples.

### API Route Testing with BaseAPIRouter

Testing API routes that use BaseAPIRouter requires specific patterns for mock patching and error response assertions.

#### Mock Patching: Patch Where Imported

Always patch services at their import location in the route module, not at their definition location.

```python
# Route file imports:
# api/admin/business_facts_routes.py
from core.agent_world_model import WorldModelService

# Test file patches at import location:
with patch('api.admin.business_facts_routes.WorldModelService', return_value=mock_service):
    response = client.get("/api/admin/governance/facts/123")
```

**Why:** When the route module imports `WorldModelService` at module level, it creates a reference to the original class. Patching at the definition location (`core.agent_world_model.WorldModelService`) doesn't affect this already-imported reference. Patching at the import location intercepts the reference the route actually uses.

**Exception:** For services imported inside functions (not at module level), patch at the original location:

```python
# Route function with local import:
def upload_document(file: UploadFile):
    from core.storage import get_storage_service  # Local import
    storage = get_storage_service()

# Test patch location:
with patch('core.storage.get_storage_service', return_value=mock_storage):
    response = client.post("/upload", files={"file": test_file})
```

#### Error Response Assertions

BaseAPIRouter.error_response() returns structured errors. Access nested message field:

```python
# Success response (200 OK)
response = client.get("/api/admin/governance/facts/123")
assert response.status_code == 200
data = response.json()
assert data["success"] == True
assert data["data"]["fact"] == "Invoices over $500 require VP approval"

# Error response (404, 400, 500, etc.)
response = client.get("/api/admin/governance/facts/non-existent")
assert response.status_code == 404
detail = response.json()["detail"]
assert detail["success"] == False
assert detail["error"]["code"] == "NOT_FOUND"
assert "not found" in detail["error"]["message"].lower()  # String operations on message
```

**Error Response Structure:**
```json
{
  "success": false,
  "error": {
    "code": "NOT_FOUND",
    "message": "Business fact not found: fact-123",
    "timestamp": "2026-03-20T11:05:21.123456",
    "details": {}
  }
}
```

**Common HTTP Status Codes:**
- `400` - VALIDATION_ERROR (invalid input from BaseAPIRouter.validation_error)
- `401` - UNAUTHORIZED (missing/invalid auth)
- `403` - FORBIDDEN (insufficient permissions)
- `404` - NOT_FOUND (resource not found from BaseAPIRouter.not_found_error)
- `500` - INTERNAL_ERROR (server error)

#### Service Mock Fixtures

Use AsyncMock for async services, configure returns in fixture:

```python
@pytest.fixture
def mock_world_model_service(sample_business_fact):
    """Mock WorldModelService with configured return values."""
    mock = AsyncMock()
    mock.get_fact_by_id.return_value = sample_business_fact
    mock.list_all_facts.return_value = [sample_business_fact]
    mock.create_fact.return_value = sample_business_fact
    return mock

def test_get_fact_success(authenticated_admin_client, mock_world_model_service):
    """Test getting a business fact by ID."""
    with patch('api.admin.business_facts_routes.WorldModelService',
               return_value=mock_world_model_service):

        response = authenticated_admin_client.get("/api/admin/governance/facts/fact-123")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
```

**AsyncMock vs MagicMock:**
- **AsyncMock:** For async service methods (most API services)
- **MagicMock:** For sync methods or non-service objects

#### Configure Mocks Inside Patch Context

When overriding fixture defaults, configure mocks **inside** the patch context manager:

```python
# Before (incorrect):
mock_extractor.extract_facts_from_document.return_value = result
with patch('api.admin.routes.get_policy_fact_extractor', return_value=mock_extractor):
    # Test - uses fixture default, not result

# After (correct):
with patch('api.admin.routes.get_policy_fact_extractor',
           return_value=mock_extractor) as patched_extractor:
    patched_extractor.extract_facts_from_document.return_value = result
    # Test - uses test-specific result
```

#### S3/R2 Storage Mocking

Mock storage services for citation verification:

```python
@pytest.fixture
def mock_storage_service():
    """Mock S3/R2 storage service."""
    mock = MagicMock()
    mock.upload_file.return_value = "s3://atom-business-facts/uploads/test.pdf"
    mock.check_exists.return_value = True
    mock.download_file.return_value = b"PDF content bytes"
    return mock
```

#### PDF Extraction Mocking

Mock PDF extraction services for document upload tests:

```python
@pytest.fixture
def mock_policy_extractor():
    """Mock policy fact extractor."""
    mock = AsyncMock()
    mock.extract_facts_from_document.return_value = {
        "facts": [
            {
                "fact": "Invoices over $500 require VP approval",
                "citations": ["s3://atom-business-facts/policies/ap-policy.pdf:page:5"],
                "reason": "Extracted from AP policy document",
                "confidence": 0.95
            }
        ],
        "metadata": {"source": "ap-policy.pdf", "page_count": 10}
    }
    return mock
```

#### Complete Example

```python
def test_upload_and_extract_success(authenticated_admin_client,
                                   mock_policy_extractor,
                                   mock_storage_service):
    """Test successful document upload and fact extraction."""
    test_file = io.BytesIO(b"%PDF-1.4 ... test PDF content ...")

    with patch('api.admin.business_facts_routes.get_policy_fact_extractor',
               return_value=mock_policy_extractor):
        with patch('core.storage.get_storage_service', return_value=mock_storage_service):
            response = authenticated_admin_client.post(
                "/api/admin/governance/facts/upload",
                files={"file": ("test.pdf", test_file, "application/pdf")}
            )

            assert response.status_code == 201
            data = response.json()
            assert len(data["data"]["facts"]) == 1
            assert "VP approval" in data["data"]["facts"][0]["fact"]
```

**Reference:** See `.planning/phases/216-fix-business-facts-test-failures/216-PATTERN-DOC.md` for complete patterns with before/after examples from Phase 216 fixes.

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
