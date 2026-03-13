# Phase 182: Core Services Coverage (Package Governance) - RESEARCH

**Phase Goal**: Achieve 75%+ line coverage on Python package governance system services.

**Date**: March 13, 2026
**Context**: Continuation of Phase 181 (World Model Coverage) - applying established test patterns to package governance services.

---

## 1. System Architecture Overview

### 1.1 Package Governance Service (`package_governance_service.py`)

**Purpose**: Maturity-based access control for Python and npm packages.

**Key Components**:

1. **Cache Integration**:
   - Uses `GovernanceCache` for <1ms permission checks
   - Cache key format: `"pkg:{package_type}:{package_name}:{version}"`
   - Cache value: `{"allowed": bool, "maturity_required": str, "reason": str}`

2. **Maturity-Based Access Control**:
   - `STUDENT` agents: Blocked from ALL packages (non-negotiable)
   - `INTERN` agents: Require explicit approval per version
   - `SUPERVISED` agents: Allowed if `min_maturity <= SUPERVISED`
   - `AUTONOMOUS` agents: Allowed if `min_maturity <= AUTONOMOUS`
   - Banned packages: Blocked for ALL agents

3. **Package Lifecycle**:
   - `request_package_approval()`: Create/update with status='pending'
   - `approve_package()`: Set status='active', invalidate cache
   - `ban_package()`: Set status='banned', store ban_reason
   - `list_packages()`: Filter by status/package_type

4. **Maturity Comparison**:
   - `MATURITY_ORDER`: student=0, intern=1, supervised=2, autonomous=3
   - `_maturity_cmp()`: Compare two maturity levels

**Current Coverage**: 70 tests (464 lines), high coverage already achieved
- `test_package_governance.py`: 70 tests passing
- STUDENT blocking, INTERN approval, maturity gating, banned packages
- Cache behavior, package lifecycle, edge cases

---

### 1.2 Package Dependency Scanner (`package_dependency_scanner.py`)

**Purpose**: Vulnerability scanning for Python packages using pip-audit and Safety.

**Key Components**:

1. **Vulnerability Scanning**:
   - `scan_packages()`: Main entry point
   - `_run_pip_audit()`: PyPA-maintained vulnerability scanner
   - `_run_safety_check()`: Commercial vulnerability database (optional API key)

2. **Dependency Analysis**:
   - `_build_dependency_tree()`: Uses pipdeptree to get full dependency tree
   - `_check_version_conflicts()`: Detects duplicate package versions

3. **Error Handling**:
   - Timeout handling for subprocess calls (120s for pip-audit/Safety, 30s for pipdeptree)
   - JSON parse error handling
   - Graceful degradation (returns empty vulnerabilities on failure)

**Current Coverage**: 367 lines
- `test_package_dependency_scanner.py`: Comprehensive mocking of subprocess calls
- pip-audit integration tests (safe/vulnerable packages)
- Safety integration tests (with/without API key)
- Dependency tree building, version conflicts
- Error handling (timeout, parse errors, exceptions)

---

### 1.3 Package Installer (`package_installer.py`)

**Purpose**: Docker-based Python package installation for skill isolation.

**Key Components**:

1. **Image Building**:
   - `install_packages()`: Main workflow (scan → build → return image_tag)
   - `_build_skill_image()`: Creates Dockerfile with venv + packages
   - Image tag format: `"atom-skill:{skill_id}-v1"` (slashes replaced with dashes)

2. **Execution**:
   - `execute_with_packages()`: Run code using custom Docker image
   - Uses `HazardSandbox.execute_python()` with custom image parameter

3. **Image Management**:
   - `cleanup_skill_image()`: Remove Docker image
   - `get_skill_images()`: List all atom-skill images

4. **Security Constraints**:
   - Pre-installation vulnerability scanning
   - Read-only root filesystem
   - Non-root user execution
   - Resource limits (timeout, memory, CPU)

**Current Coverage**: 491 lines
- `test_package_installer.py`: 49 tests with extensive Docker mocking
- Mock docker.errors exceptions (ImageNotFound, APIError, DockerException)
- Image building, execution, cleanup, listing
- Error handling, build log capture, image tag formatting

---

### 1.4 Package Routes (`api/package_routes.py`)

**Purpose**: REST API for package governance and management.

**Key Components**:

1. **Governance Endpoints** (Plan 01):
   - `GET /check`: Check package permission for agent
   - `POST /request`: Request package approval
   - `POST /approve`: Approve package (admin)
   - `POST /ban`: Ban package version (admin)
   - `GET /`: List all packages
   - `GET /stats`: Get cache statistics

2. **Package Management Endpoints** (Plan 04):
   - `POST /install`: Install packages for skill
   - `POST /execute`: Execute skill with packages
   - `DELETE /{skill_id}`: Cleanup skill image
   - `GET /{skill_id}/status`: Get skill image status
   - `GET /audit`: List package operations

3. **npm Endpoints** (Plan 04):
   - `POST /npm/install`: Install npm packages
   - `POST /npm/execute`: Execute Node.js skill
   - `DELETE /npm/{skill_id}`: Cleanup npm image
   - `GET /npm/{skill_id}/status`: Get npm image status
   - `GET /npm`: List npm packages

**Current Coverage**: 1227 lines
- `test_package_api_integration.py`: 11 endpoint tests with FastAPI TestClient
- Install endpoint (permission checks, vulnerabilities, invalid requirements)
- Execute endpoint (success, missing image)
- Cleanup endpoint (idempotent)
- Status endpoint (image exists, not found)
- Audit endpoint (list operations)
- Router registration tests

---

## 2. Current Test Coverage Analysis

### 2.1 Existing Test Files

| Test File | Lines | Tests | Coverage Focus |
|-----------|-------|-------|----------------|
| `test_package_governance.py` | 464 | 70 | Permission checks, cache behavior, lifecycle |
| `test_package_dependency_scanner.py` | 367 | 36 | Vulnerability scanning, dependency trees |
| `test_package_installer.py` | 491 | 49 | Docker image building, execution, cleanup |
| `test_package_api_integration.py` | 495 | 11 | REST API endpoints |

**Total**: 1,817 lines of tests, 166 tests

### 2.2 Coverage Gaps Identified

**Priority 1 - Critical Paths**:
1. **npm package governance** (missing from `test_package_governance.py`):
   - No tests for `package_type="npm"` parameter
   - npm package permission checks not tested
   - npm package approval/banning not tested

2. **npm package routes** (partial coverage):
   - `test_npm_package_routes.py` exists but not analyzed
   - Need to verify npm endpoints are tested

3. **Edge cases in permission checks**:
   - Missing agent defaults to STUDENT (tested but may need expansion)
   - Case sensitivity in package names
   - Version specifier edge cases (">=", "==", "~=", None)

**Priority 2 - Integration Scenarios**:
1. **Cache invalidation edge cases**:
   - Multiple agents accessing same package
   - Cache stampede scenarios
   - TTL expiration behavior

2. **Vulnerability scanning edge cases**:
   - Empty requirements list (tested)
   - Malformed requirements strings
   - pip-audit/Safety CLI not installed

3. **Docker build edge cases**:
   - Disk space exhausted
   - Network timeout during pip install
   - Conflicting dependencies in requirements.txt

**Priority 3 - Error Paths**:
1. **Database errors**:
   - Connection failures during permission check
   - Transaction rollback on approval/ban failure

2. **Subprocess errors**:
   - pip-audit not found in PATH
   - pipdeptree timeout handling
   - Docker daemon not running

3. **API error responses**:
   - 500 errors from service layer
   - Malformed request payloads
   - Missing query parameters

---

## 3. Test Patterns Established (Phase 181)

### 3.1 Database Mocking Pattern

```python
@pytest.fixture
def db_session():
    """Create test database session."""
    from core.database import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Usage**: Tests use real database with test data, cleaned up in `finally` blocks.

### 3.2 Factory Pattern for Agents

```python
from tests.factories.agent_factory import (
    StudentAgentFactory,
    InternAgentFactory,
    SupervisedAgentFactory,
    AutonomousAgentFactory
)

@pytest.fixture
def autonomous_agent(db_session: Session):
    agent = AutonomousAgentFactory(_session=db_session)
    db_session.commit()
    return agent
```

**Usage**: Factory pattern creates agents with proper maturity levels.

### 3.3 Subprocess Mocking Pattern

```python
@patch('subprocess.run')
def test_vulnerable_package(self, mock_run, scanner):
    vuln_json = json.dumps([{
        "name": "requests",
        "versions": ["2.20.0"],
        "id": "CVE-2018-18074",
        "description": "DoS vulnerability",
        "fix_versions": ["2.20.1"]
    }])
    mock_run.return_value = MagicMock(
        returncode=1,
        stdout=vuln_json,
        stderr=""
    )
```

**Usage**: Mock subprocess calls for external tools (pip-audit, Safety, pipdeptree).

### 3.4 Docker Mocking Pattern

```python
# Mock docker module BEFORE imports
sys.modules['docker'] = MagicMock()
sys.modules['docker'].errors = docker_errors_mock

@pytest.fixture
def installer(mock_docker_client):
    with patch('core.package_installer.docker.from_env', return_value=mock_docker_client):
        with patch('core.package_installer.HazardSandbox'):
            yield PackageInstaller()
```

**Usage**: Mock Docker client and exceptions to avoid real Docker calls.

### 3.5 FastAPI TestClient Pattern

```python
from fastapi.testclient import TestClient
from main import app

@pytest.fixture
def client():
    return TestClient(app)

def test_install_endpoint(self, client, db_session):
    response = client.post("/api/packages/install", json={...})
    assert response.status_code == 200
```

**Usage**: Use TestClient for REST API endpoint testing.

---

## 4. Security Integration Points

### 4.1 Vulnerability Scanning Tools

**pip-audit** (PyPA-maintained):
- CLI command: `pip-audit --format json --requirement requirements.txt`
- Output: JSON array of vulnerabilities
- Fields: `id`, `name`, `versions`, `description`, `fix_versions`
- Return code: 0 (safe), 1 (vulnerabilities found)

**Safety** (Commercial database):
- CLI command: `safety check --file requirements.txt --json --continue-on-errors`
- Optional: `--api-key <key>` for commercial database
- Output: JSON array of vulnerabilities
- Fields: `id`, `package_name`, `vulnerability_id`, `affected_versions`, `advisory`

### 4.2 Security Test Patterns

**Test vulnerability detection**:
```python
def test_scanner_detects_vulnerabilities(self, scanner):
    vuln_json = json.dumps([{
        "id": "CVE-2021-1234",
        "name": "vulnerable-pkg",
        "versions": ["1.0.0"],
        "description": "RCE vulnerability",
        "fix_versions": ["1.0.1"]
    }])
    # Mock subprocess to return vulnerability data
    result = scanner.scan_packages(["vulnerable-pkg==1.0.0"])
    assert result["safe"] == False
    assert len(result["vulnerabilities"]) == 1
```

**Test build failure on vulnerabilities**:
```python
def test_install_fails_on_vulnerabilities(self, installer):
    installer.scanner.scan_packages.return_value = {
        "safe": False,
        "vulnerabilities": [{"cve_id": "CVE-2021-1234"}]
    }
    result = installer.install_packages(skill_id="test", requirements=[...])
    assert result["success"] == False
    assert "Vulnerabilities detected" in result["error"]
```

---

## 5. Performance Considerations

### 5.1 Cache Performance

**Target**: <1ms cached lookups (GovernanceCache integration)

**Current implementation**:
- Uses `GovernanceCache` with LRU eviction
- Cache key: `"pkg:{package_type}:{package_name}:{version}"`
- Cache invalidation: `cache.clear()` on approval/ban

**Test requirements**:
- Verify cache hit rate > 90%
- Measure cache lookup latency (<1ms P99)
- Test cache invalidation propagation

### 5.2 Docker Build Performance

**Target**: <5min image build time

**Current implementation**:
- Base image: `python:3.11-slim` (minimal)
- Virtual environment: `/opt/atom_skill_env`
- Layer caching: Docker uses layer cache for unchanged requirements

**Test requirements**:
- Mock Docker build to avoid slow tests
- Test build log capture and reporting
- Verify image tag format and reusability

### 5.3 Vulnerability Scan Performance

**Target**: <30s for typical dependency tree

**Current implementation**:
- pip-audit timeout: 120s
- pipdeptree timeout: 30s
- Safety timeout: 120s
- Parallel scanning: pip-audit and Safety run sequentially

**Test requirements**:
- Test timeout handling
- Verify graceful degradation on timeout
- Mock slow subprocess calls

---

## 6. Recommended Test Coverage Strategy

### 6.1 Phase 182 Plan Breakdown

**Plan 01: Package Governance Service Coverage** (Target: 85%)
- npm package permission checks (`package_type="npm"`)
- Cache invalidation edge cases
- Case sensitivity in package names
- Version specifier edge cases (">=", "~=", None)
- Missing agent defaults to STUDENT
- Database error handling

**Plan 02: Dependency Scanner Coverage** (Target: 85%)
- Malformed requirements strings
- CLI tools not installed (pip-audit, pipdeptree, Safety)
- Subprocess timeout edge cases
- Empty JSON output from scanners
- Transitive dependency conflicts
- Large dependency trees (performance test)

**Plan 03: Package Installer Coverage** (Target: 85%)
- Docker daemon not running
- Disk space exhausted
- Network timeout during pip install
- Conflicting dependencies in requirements.txt
- Build log streaming and capture
- Image reuse across multiple install calls
- Resource limit enforcement

**Plan 04: API Routes Coverage** (Target: 80%)
- npm governance endpoints (approve, ban, check, list)
- npm installation/execution endpoints
- Malformed request payloads
- Missing query parameters
- 500 error propagation from services
- Audit trail filtering edge cases
- Pagination for package list (if implemented)

### 6.2 Test File Organization

**New Test Files**:
1. `tests/test_package_governance_npm.py`: npm-specific governance tests
2. `tests/test_package_scanner_edge_cases.py`: Scanner edge cases
3. `tests/test_package_installer_edge_cases.py`: Installer edge cases
4. `tests/test_package_routes_npm.py`: npm API endpoint tests

**Updated Test Files**:
1. `tests/test_package_governance.py`: Add npm permission tests
2. `tests/test_package_dependency_scanner.py`: Add edge case tests
3. `tests/test_package_installer.py`: Add Docker edge case tests
4. `tests/test_package_api_integration.py`: Add npm endpoint tests

### 6.3 Coverage Targets

| Module | Current | Target | Gap |
|--------|---------|--------|-----|
| `package_governance_service.py` (418 lines) | ~90% | 95% | +5% |
| `package_dependency_scanner.py` (307 lines) | ~80% | 85% | +5% |
| `package_installer.py` (366 lines) | ~85% | 90% | +5% |
| `api/package_routes.py` (1,227 lines) | ~40% | 75% | +35% |

**Overall Target**: 75%+ coverage across all package governance modules.

---

## 7. Dependencies and Integration Points

### 7.1 Database Models

**PackageRegistry** (`core/models.py`):
```python
class PackageRegistry(Base):
    id = Column(String, primary_key=True)  # "numpy:1.21.0"
    name = Column(String, nullable=False, index=True)
    version = Column(String, nullable=False, index=True)
    package_type = Column(String, default="python")  # "python" or "npm"
    min_maturity = Column(String, default="INTERN")
    status = Column(String, default="untrusted")  # untrusted, active, banned, pending
    ban_reason = Column(Text, nullable=True)
    approved_by = Column(String, ForeignKey("users.id"))
    approved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
```

**Test fixtures**: Use `PackageRegistry` directly in tests for approval/ban workflows.

### 7.2 External Services

**Docker**:
- Library: `docker` (Python Docker SDK)
- Client: `docker.from_env()`
- Exceptions: `ImageNotFound`, `APIError`, `DockerException`
- Mock: Use `MagicMock()` for `docker.from_env()` and `docker.errors`

**Security Tools**:
- pip-audit: PyPI package, CLI tool
- Safety: PyPI package, CLI tool with optional API key
- pipdeptree: PyPI package, dependency tree visualization

### 7.3 Internal Services

**GovernanceCache** (`core/governance_cache.py`):
- LRU cache with TTL
- Thread-safe operations
- Statistics tracking (hits, misses, evictions)
- Methods: `get()`, `set()`, `clear()`, `get_stats()`

**HazardSandbox** (`core/skill_sandbox.py`):
- Python code execution in containers
- Resource limits (timeout, memory, CPU)
- Custom image support: `execute_python(code, inputs, image=tag)`

**AuditService** (`core/audit_service.py`):
- Package audit trail
- Method: `create_package_audit()`
- Tracks: permission checks, installations, executions

---

## 8. Potential Pitfalls and Mitigations

### 8.1 Subprocess Mocking Complexity

**Pitfall**: Subprocess calls are deeply nested in scanner methods.

**Mitigation**: Use `@patch('subprocess.run')` at test class level, configure `side_effect` for multiple calls.

**Example**:
```python
@patch('subprocess.run')
def test_multiple_subprocess_calls(self, mock_run, scanner):
    # First call: pip install, second: pipdeptree, third: pip-audit
    mock_run.side_effect = [
        MagicMock(returncode=0, stdout=""),  # pip install
        MagicMock(returncode=0, stdout="[]"),  # pipdeptree
        MagicMock(returncode=1, stdout=vuln_json)  # pip-audit
    ]
    result = scanner.scan_packages(["requests==2.20.0"])
```

### 8.2 Docker Module Import Issues

**Pitfall**: `docker` module must be mocked BEFORE importing `package_installer`.

**Mitigation**: Mock docker at module level in test file:

```python
import sys
from unittest.mock import MagicMock

# Create real exception classes
class DockerException(Exception): pass
class ImageNotFound(Exception): pass

# Mock docker.errors module
docker_errors_mock = MagicMock()
docker_errors_mock.ImageNotFound = ImageNotFound
docker_errors_mock.DockerException = DockerException

# Mock docker module
sys.modules['docker'] = MagicMock()
sys.modules['docker'].errors = docker_errors_mock
sys.modules['docker.errors'] = docker_errors_mock
```

### 8.3 Database Session Management

**Pitfall**: Tests may leave database records if cleanup fails.

**Mitigation**: Use `try/finally` blocks and explicit cleanup:

```python
@pytest.fixture
def test_package(db_session: Session):
    package = PackageRegistry(
        id="test-pkg:1.0.0",
        name="test-pkg",
        version="1.0.0",
        status="active"
    )
    db_session.add(package)
    db_session.commit()
    yield package
    # Cleanup
    db_session.delete(package)
    db_session.commit()
```

### 8.4 npm Package Testing

**Pitfall**: npm package governance uses same service but different `package_type`.

**Mitigation**: Add explicit tests for `package_type="npm"` parameter:

```python
def test_npm_package_permission_check(self, governance_service, npm_agent, db_session):
    result = governance_service.check_package_permission(
        agent_id=npm_agent.id,
        package_name="lodash",
        version="4.17.21",
        db=db_session,
        package_type="npm"  # Explicit npm type
    )
    assert result["allowed"] == False  # Not approved yet
```

---

## 9. Integration with CI/CD

### 9.1 Test Execution Strategy

**Unit Tests** (fast, <1s):
- Governance service tests (cache, maturity checks)
- Scanner tests (subprocess mocking)
- Installer tests (Docker mocking)

**Integration Tests** (medium, <10s):
- API endpoint tests (FastAPI TestClient)
- Database integration tests (real DB)
- Cache performance tests

**E2E Tests** (slow, <60s):
- Real Docker build tests (optional, can skip in CI)
- Real vulnerability scans (use safe packages only)

### 9.2 Coverage Reporting

**Generate coverage report**:
```bash
pytest tests/test_package_governance.py \
    tests/test_package_dependency_scanner.py \
    tests/test_package_installer.py \
    tests/test_package_api_integration.py \
    --cov=core/package_governance_service \
    --cov=core/package_dependency_scanner \
    --cov=core/package_installer \
    --cov=api/package_routes \
    --cov-report=term-missing \
    --cov-report=html \
    --cov-report=json
```

**Coverage thresholds**:
- Line coverage: 75% minimum
- Branch coverage: 70% minimum (if available)

### 9.3 CI Pipeline Integration

**GitHub Actions workflow**:
```yaml
name: Package Governance Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov
      - name: Run tests
        run: |
          pytest tests/test_package_*.py \
            --cov=core/package_governance_service \
            --cov=core/package_dependency_scanner \
            --cov=core/package_installer \
            --cov=api/package_routes \
            --cov-report=xml
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

---

## 10. Summary and Recommendations

### 10.1 Key Findings

1. **Strong Foundation**: Package governance system has comprehensive test coverage (1,817 lines, 166 tests).

2. **npm Gap**: npm package governance is implemented but not fully tested (missing `package_type="npm"` tests).

3. **API Routes Gap**: API routes have partial coverage (only 11 tests for 1,227 lines of code).

4. **Edge Cases**: Error paths and edge cases need expansion (timeout handling, CLI not installed, disk space).

5. **Test Patterns**: Phase 181 established solid patterns for mocking, database testing, and API testing.

### 10.2 Recommended Execution Order

**Wave 1: Core Service Edge Cases** (Priority 1)
1. npm package governance tests
2. Scanner edge cases (CLI not installed, malformed input)
3. Installer edge cases (Docker daemon, disk space)
4. Cache invalidation stress tests

**Wave 2: API Routes Coverage** (Priority 2)
1. npm governance endpoints (approve, ban, check, list)
2. npm installation/execution endpoints
3. Error response propagation (500 errors)
4. Audit trail filtering and pagination

**Wave 3: Integration Scenarios** (Priority 3)
1. End-to-end vulnerability scanning (real pip-audit on safe packages)
2. Cache performance benchmarks (verify <1ms P99)
3. Docker build performance (verify <5min build time)
4. Multi-agent cache stampede scenarios

### 10.3 Success Criteria

**Quantitative**:
- 75%+ line coverage across all package governance modules
- 95%+ coverage on `package_governance_service.py`
- 85%+ coverage on `package_dependency_scanner.py`
- 90%+ coverage on `package_installer.py`
- 75%+ coverage on `api/package_routes.py`

**Qualitative**:
- All npm package governance flows tested
- All error paths tested with appropriate mocks
- All API endpoints covered with success/failure cases
- Cache performance verified (<1ms P99)
- Security integration verified (pip-audit, Safety)

---

## 11. Open Questions

1. **npm Package Installer**: Is `NpmPackageInstaller` tested separately? Need to verify `test_npm_package_installer.py`.

2. **npm Script Analyzer**: Is `NpmScriptAnalyzer` tested? Need to check for npm script security tests.

3. **Audit Service**: Does `create_package_audit()` have its own tests? Need to verify audit trail coverage.

4. **Performance Tests**: Are there existing performance benchmarks for cache and Docker build times?

5. **E2E Tests**: Should we add real Docker build tests (slow but validates actual behavior)?

---

## 12. References

**Documentation**:
- `docs/PYTHON_PACKAGES.md`: Package governance system documentation
- `docs/PACKAGE_SECURITY.md`: Security scanning implementation
- `backend/tests/test_package_*.py`: Existing test files
- `.planning/phases/181-core-services-coverage-world-model/181-RESEARCH.md`: Phase 181 research

**Source Files**:
- `core/package_governance_service.py` (418 lines)
- `core/package_dependency_scanner.py` (307 lines)
- `core/package_installer.py` (366 lines)
- `api/package_routes.py` (1,227 lines)
- `core/models.py`: PackageRegistry model (lines 6909-6957)

**Test Files**:
- `tests/test_package_governance.py` (464 lines, 70 tests)
- `tests/test_package_dependency_scanner.py` (367 lines, 36 tests)
- `tests/test_package_installer.py` (491 lines, 49 tests)
- `tests/test_package_api_integration.py` (495 lines, 11 tests)
- `tests/test_npm_package_routes.py`: npm endpoint tests (TODO: analyze)

---

**Next Step**: Create 182-01-PLAN.md with detailed test implementation plans for Wave 1 (Core Service Edge Cases).
