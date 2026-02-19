# Advanced Skill Execution

**Phase 60** introduces advanced skill execution features that build on Atom's Community Skills infrastructure (Phase 14), Python Package Support (Phase 35), and npm Package Support (Phase 36).

---

## Table of Contents

1. [Features Overview](#features-overview)
2. [Quick Start](#quick-start)
3. [Performance Targets](#performance-targets)
4. [Architecture](#architecture)
5. [Security Considerations](#security-considerations)
6. [API Reference](#api-reference)
7. [Troubleshooting](#troubleshooting)
8. [Related Documentation](#related-documentation)

---

## Features Overview

### 1. Skill Marketplace

The Skill Marketplace provides a centralized hub for discovering, rating, and installing community skills.

- **Discovery**: Search and browse skills by category, type, and popularity
- **Ratings**: Submit 1-5 star ratings with reviews
- **Installation**: One-click installation with automatic dependency management
- **API**: REST endpoints for marketplace operations
- **Local Storage**: PostgreSQL-based marketplace with Atom SaaS sync architecture (future)

**Status**: ✅ Implemented (Plan 60-01)

### 2. Dynamic Skill Loading

Load and reload skills at runtime without service restart.

- **Hot-Reload**: Skills update within 1 second of file changes
- **Module Cache**: Proper sys.modules management prevents stale code
- **File Monitoring**: Optional watchdog-based file watching
- **Performance**: Target < 1 second for skill loading

**How It Works**:
```python
import importlib.util
import sys

# Load skill dynamically
spec = importlib.util.spec_from_file_location("my_skill", "/path/to/skill.py")
module = importlib.util.module_from_spec(spec)
sys.modules["my_skill"] = module
spec.loader.exec_module(module)

# Hot-reload: Clear cache before reload
if "my_skill" in sys.modules:
    del sys.modules["my_skill"]
module = importlib.reload(module)
```

**Status**: ✅ Implemented (Plan 60-02)

### 3. Skill Composition

Chain multiple skills into complex workflows with DAG validation.

- **DAG Validation**: Automatic cycle detection using NetworkX
- **Data Passing**: Output from one skill becomes input to next
- **Rollback**: Failed workflows automatically roll back
- **Conditional Execution**: Skip steps based on conditions
- **Parallel Execution**: Independent steps execute concurrently

**Example Workflow**:
```python
from core.skill_composition_engine import SkillCompositionEngine, SkillStep

engine = SkillCompositionEngine(db)

steps = [
    SkillStep("fetch", "http_get", {"url": "api.example.com"}, []),
    SkillStep("process", "analyze", {"algorithm": "sentiment"}, ["fetch"]),
    SkillStep("save", "database_insert", {}, ["process"])
]

result = await engine.execute_workflow("my-workflow", steps, "my-agent")
```

**Status**: ✅ Implemented (Plan 60-03)

### 4. Auto-Installation

Automatic dependency resolution and installation.

- **Conflict Detection**: Version conflict detection before installation
- **Batch Installation**: Install multiple skills efficiently
- **Distributed Locking**: Prevent concurrent build conflicts
- **Rollback**: Cleanup on installation failure
- **Support**: Both Python (pip) and npm packages

**Status**: ✅ Implemented (Plan 60-04)

### 5. Supply Chain Security

Comprehensive protection against real-world supply chain attacks.

- **Typosquatting Detection**: Low download count warnings
- **Dependency Confusion**: Internal package protection
- **Postinstall Malware**: Script analysis blocks cryptojackers
- **Audit Trail**: All security decisions logged
- **E2E Testing**: 36 tests covering all major threat vectors

**Attack Coverage**:
- ✅ Container escape prevention (privileged mode, Docker socket, host mounts)
- ✅ Resource exhaustion protection (memory, CPU, timeout)
- ✅ Network isolation (no external access)
- ✅ Filesystem isolation (read-only, no host mounts)
- ✅ Malicious pattern detection (subprocess, eval, base64, pickle)
- ✅ Vulnerability scanning (pip-audit, npm audit)
- ✅ Typosquatting packages (reqeusts, numpyy, panads, exprss, lodas)
- ✅ Dependency confusion (internal-sounding package names)
- ✅ Postinstall malware (cryptojackers, Shai-Hulud, Sha1-Hulud)

**Status**: ✅ Implemented (Plan 60-06)

---

## Quick Start

### Browse the Marketplace

```bash
curl "http://localhost:8000/marketplace/skills?page=1&page_size=20"
```

**Response**:
```json
{
  "skills": [
    {
      "id": "abc-123",
      "skill_name": "CSV Data Processor",
      "skill_type": "python_code",
      "description": "Process CSV files with pandas",
      "category": "data",
      "status": "Active",
      "avg_rating": 4.5,
      "rating_count": 12
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20
}
```

### Install a Skill

```bash
curl -X POST "http://localhost:8000/marketplace/skills/{skill_id}/install" \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "my-agent", "auto_install_deps": true}'
```

### Create a Workflow

```python
from core.skill_composition_engine import SkillCompositionEngine, SkillStep

engine = SkillCompositionEngine(db)

steps = [
    SkillStep("fetch", "http_get", {"url": "api.example.com"}, []),
    SkillStep("process", "analyze", {"algorithm": "sentiment"}, ["fetch"]),
    SkillStep("save", "database_insert", {}, ["process"])
]

result = await engine.execute_workflow("my-workflow", steps, "my-agent")
```

### Hot-Reload a Skill

```python
from core.skill_dynamic_loader import get_global_loader

loader = get_global_loader()

# Load skill
module = loader.load_skill("my_skill", "/path/to/skill.py")

# After file modification, hot-reload
reloaded = loader.reload_skill("my_skill")
```

### Auto-Install Dependencies

```bash
# Python packages
curl -X POST "http://localhost:8000/auto-install/install" \
  -H "Content-Type: application/json" \
  -d '{
    "skill_id": "data-analysis",
    "packages": ["pandas==2.0.0", "numpy>=1.24.0"],
    "package_type": "python",
    "agent_id": "my-agent"
  }'

# npm packages
curl -X POST "http://localhost:8000/auto-install/install" \
  -H "Content-Type: application/json" \
  -d '{
    "skill_id": "web-scraper",
    "packages": ["lodash@4.17.21", "axios@^1.6.0"],
    "package_type": "npm",
    "agent_id": "my-agent"
  }'
```

---

## Performance Targets

| Operation | Target | Current | Notes |
|-----------|--------|---------|-------|
| **Package Installation** | < 5 seconds | ~3-5s | Small packages (requests, lodash) |
| **Skill Loading** | < 1 second | ~0.5-1s | Dynamic import from file |
| **Hot-Reload** | < 1 second | ~0.3-0.8s | File change to reload |
| **Marketplace Search** | < 100ms | ~20-50ms | With pagination |
| **Workflow Validation** | < 50ms | ~10-30ms | DAG validation |
| **Dependency Resolution** | < 500ms | ~100-300ms | Conflict detection |

**Benchmarking**:
```bash
# Run performance benchmarks
pytest backend/tests/test_performance_benchmarks.py --benchmark-only

# Check for regressions
pytest backend/tests/test_performance_benchmarks.py --benchmark-only --benchmark-json=benchmark.json
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Skill Marketplace                       │
│  (Discovery, Search, Ratings, Installation)                │
│  PostgreSQL-based with Atom SaaS sync architecture         │
└───────────────┬─────────────────────────────────────────────┘
                      │
    ┌───────────────▼─────────────────────────────────────────────┐
    │                 Dynamic Skill Loader                         │
    │  (importlib loading, hot-reload, module cache management)   │
    │  watchdog-based file monitoring for auto-reload             │
    └───────────────┬─────────────────────────────────────────────┘
                      │
    ┌───────────────▼─────────────────────────────────────────────┐
    │              Skill Composition Engine                        │
    │  (DAG validation, topological execution, rollback)          │
    │  NetworkX for cycle detection and ordering                  │
    └───────────────┬─────────────────────────────────────────────┘
                      │
    ┌───────────────▼─────────────────────────────────────────────┐
    │               Auto-Installer Service                        │
    │  (Dependency resolution, conflict detection, locking)       │
    │  Distributed locking to prevent build conflicts             │
    └───────────────┬─────────────────────────────────────────────┘
                      │
    ┌───────────────▼─────────────────────────────────────────────┐
    │        Package Installers (Python + npm)                     │
    │  (Docker images, vulnerability scanning, sandbox)           │
    │  Per-skill isolation with conflict detection                │
    └──────────────────────────────────────────────────────────────┘
```

**Component Details**:

1. **SkillMarketplaceService**: PostgreSQL-based marketplace with search, ratings, categories
2. **SkillDynamicLoader**: importlib-based loading with watchdog file monitoring
3. **SkillCompositionEngine**: DAG workflow executor with NetworkX validation
4. **AutoInstallerService**: Dependency resolution with conflict detection
5. **PackageInstaller** (Python): Docker images with pip-audit scanning
6. **NpmPackageInstaller** (npm): Docker images with npm audit and --ignore-scripts

---

## Security Considerations

### Supply Chain Protection

Atom implements comprehensive supply chain security across all package installation workflows:

#### 1. Governance Checks

All packages require maturity-based approval:

| Agent Level | Python Packages | npm Packages |
|-------------|----------------|--------------|
| **STUDENT** | ❌ Blocked | ❌ Blocked |
| **INTERN** | ⚠️ Approval Required | ⚠️ Approval Required |
| **SUPERVISED** | ✅ If approved | ✅ If approved |
| **AUTONOMOUS** | ✅ If approved | ✅ If approved |

**Banned packages block all agents regardless of maturity.**

#### 2. Vulnerability Scanning

- **Python**: pip-audit (PyPI/GitHub Security Advisories) + Safety DB (optional)
- **npm**: npm audit (known vulnerabilities) + Snyk (optional)

**Before Installation**:
```python
# Scan for vulnerabilities
result = scanner.scan_packages(["pandas==2.0.0", "numpy>=1.24.0"])

if result["vulnerabilities"]:
    logger.warning(f"Found {len(result['vulnerabilities'])} vulnerabilities")
    # Block installation or require approval
```

#### 3. Script Analysis

Postinstall scripts are analyzed for malicious patterns:

**Detection Categories**:
- Cryptojackers (crypto mining, high CPU usage)
- Data exfiltration (network requests to unknown hosts)
- Credential theft (accessing .env, ~/.aws/credentials)
- Persistence mechanisms (cron jobs, startup scripts)

**Malicious Patterns**:
```python
# Blocked patterns
- fetch, axios (network requests)
- child_process, exec (command execution)
- process.env, fs.readFile (credential access)
- Base64 obfuscation (payload hiding)
```

#### 4. Audit Logging

All security decisions are logged:

```python
# Security decision logged
{
  "timestamp": "2026-02-19T21:00:00Z",
  "agent_id": "my-agent",
  "skill_id": "data-analysis",
  "package": "pandas==2.0.0",
  "decision": "allowed",
  "reason": "Package approved for SUPERVISED+ agents",
  "scan_result": {"vulnerabilities": [], "malicious_patterns": []}
}
```

### Sandbox Isolation

All package execution occurs in isolated Docker containers:

**Python Packages**:
- Base image: `python:3.11-slim`
- User: Non-root (UID 1000)
- Network: Disabled
- Filesystem: Read-only (except /tmp)
- Virtual environment: `/opt/atom_skill_env`

**npm Packages**:
- Base image: `node:20-alpine`
- User: nodejs (UID 1001)
- Network: Disabled
- Filesystem: Read-only (except /tmp)
- Postinstall: --ignore-scripts flag

**Resource Limits**:
- Memory: 256m default (configurable)
- CPU: 0.5 cores default (configurable)
- Timeout: 30 seconds default (configurable)

### E2E Security Testing

Atom includes 36 comprehensive E2E tests validating all security constraints:

**Test Categories**:
- Container escape prevention (4 tests)
- Resource exhaustion protection (4 tests)
- Network isolation (2 tests)
- Filesystem isolation (3 tests)
- Malicious pattern detection (8 tests)
- Vulnerability scanning (3 tests)
- Governance blocking (4 tests)
- Typosquatting & dependency confusion (8 tests)

**Running Tests**:
```bash
# All security tests
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/test_e2e_supply_chain.py -v

# Specific category
pytest backend/tests/test_e2e_supply_chain.py::TestTyposquatting -v
```

---

## API Reference

### Marketplace Endpoints

#### Search Skills
```bash
GET /marketplace/skills?query={query}&category={category}&sort_by={sort}&page={page}&page_size={size}
```

**Parameters**:
- `query`: Search string (optional)
- `category`: Filter by category (optional)
- `skill_type`: prompt_only, python_code, nodejs_code (optional)
- `sort_by`: relevance, created, name, rating (default: relevance)
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 20, max: 100)

#### Get Skill Details
```bash
GET /marketplace/skills/{skill_id}
```

**Response**: Full skill metadata with ratings and reviews

#### Rate a Skill
```bash
POST /marketplace/skills/{skill_id}/rate
Content-Type: application/json

{
  "user_id": "my-agent",
  "rating": 5,  // 1-5 stars
  "comment": "Excellent skill!"
}
```

#### Install Skill
```bash
POST /marketplace/skills/{skill_id}/install
Content-Type: application/json

{
  "agent_id": "my-agent",
  "auto_install_deps": true
}
```

#### Get Categories
```bash
GET /marketplace/categories
```

**Response**: List of categories with skill counts

### Composition Endpoints

#### Execute Workflow
```bash
POST /composition/execute
Content-Type: application/json

{
  "workflow_id": "my-workflow",
  "agent_id": "my-agent",
  "steps": [
    {
      "step_id": "fetch",
      "skill_id": "http_get",
      "inputs": {"url": "api.example.com"},
      "dependencies": []
    },
    {
      "step_id": "process",
      "skill_id": "json_parse",
      "inputs": {},
      "dependencies": ["fetch"]
    }
  ]
}
```

#### Validate Workflow
```bash
POST /composition/validate
Content-Type: application/json

{
  "steps": [...]
}
```

**Response**:
```json
{
  "valid": true,
  "node_count": 2,
  "edge_count": 1,
  "execution_order": ["fetch", "process"]
}
```

#### Get Execution Status
```bash
GET /composition/status/{execution_id}
```

### Auto-Install Endpoints

#### Install Dependencies
```bash
POST /auto-install/install
Content-Type: application/json

{
  "skill_id": "data-analysis",
  "packages": ["pandas==2.0.0", "numpy>=1.24.0"],
  "package_type": "python",  // or "npm"
  "agent_id": "my-agent"
}
```

#### Batch Install
```bash
POST /auto-install/batch
Content-Type: application/json

{
  "installations": [
    {
      "skill_id": "skill1",
      "packages": ["pandas==2.0.0"],
      "package_type": "python"
    },
    {
      "skill_id": "skill2",
      "packages": ["lodash@4.17.21"],
      "package_type": "npm"
    }
  ],
  "agent_id": "my-agent"
}
```

#### Check Installation Status
```bash
GET /auto-install/status/{skill_id}
```

---

## Troubleshooting

### Skill Installation Fails

**Problem**: Package installation fails with "conflict detected"

**Solution**:
1. Check dependency versions in skill metadata:
   ```bash
   curl http://localhost:8000/marketplace/skills/{skill_id}
   ```
2. Resolve conflicts manually or contact skill author
3. Use `auto_install_deps=false` to skip auto-installation:
   ```bash
   curl -X POST "http://localhost:8000/marketplace/skills/{skill_id}/install" \
     -H "Content-Type: application/json" \
     -d '{"agent_id": "my-agent", "auto_install_deps": false}'
   ```

### Hot-Reload Not Working

**Problem**: Skill changes don't appear after hot-reload

**Solution**:
1. Verify watchdog is installed:
   ```bash
   pip install watchdog
   ```
2. Check file permissions on skill directory:
   ```bash
   ls -la /path/to/skills/
   ```
3. Ensure `enable_monitoring=True` in SkillDynamicLoader:
   ```python
   loader = SkillDynamicLoader(
       skills_dir="/path/to/skills",
       enable_monitoring=True
   )
   ```

### Workflow Validation Fails

**Problem**: Workflow marked as "invalid" or "cyclic"

**Solution**:
1. Review dependency graph for cycles:
   ```bash
   curl -X POST "http://localhost:8000/composition/validate" \
     -H "Content-Type: application/json" \
     -d '{"steps": [...]}'
   ```
2. Ensure all dependencies reference existing steps
3. Break cycles by introducing intermediate steps:
   ```python
   # BAD: A -> B -> A (cycle)
   steps = [
       SkillStep("A", "skill1", {}, ["B"]),
       SkillStep("B", "skill2", {}, ["A"])
   ]

   # GOOD: A -> C -> B (no cycle)
   steps = [
       SkillStep("A", "skill1", {}, []),
       SkillStep("C", "skill3", {}, ["A"]),
       SkillStep("B", "skill2", {}, ["C"])
   ]
   ```

### Security Scan Blocks Installation

**Problem**: Package blocked due to security scan

**Solution**:
1. Review scan results:
   ```bash
   curl http://localhost:8000/auto-install/status/{skill_id}
   ```
2. Check for known vulnerabilities:
   ```bash
   pip-audit --requirement <(echo "pandas==2.0.0")
   npm audit
   ```
3. If safe to proceed, manually approve package via governance:
   ```python
   # Add package to approved list for SUPERVISED+ agents
   from core.package_governance_service import PackageGovernanceService

   gov = PackageGovernanceService(db)
   gov.set_package_status(
       package_name="pandas",
       maturity_required="SUPERVISED",
       approved=True,
       reason="Reviewed and approved for data processing"
   )
   ```

### Performance Degradation

**Problem**: Operations getting slower over time

**Solution**:
1. Check for memory leaks:
   ```bash
   docker stats  # Check container memory usage
   ```
2. Clear module cache:
   ```python
   from core.skill_dynamic_loader import get_global_loader
   loader = get_global_loader()
   loader.clear_cache()
   ```
3. Review Docker image storage:
   ```bash
   docker images  # Check for old skill images
   docker system prune -a  # Cleanup unused images
   ```
4. Check database query performance:
   ```bash
   # Add indexes if needed
   CREATE INDEX idx_skill_category ON skill_executions((input_params->>'skill_metadata'->>'category'));
   ```

---

## Related Documentation

### Core Documentation
- [Community Skills](./COMMUNITY_SKILLS.md) - Phase 14 foundation for skill infrastructure
- [Python Packages](./PYTHON_PACKAGES.md) - Python package support with dependency isolation
- [npm Packages](./NPM_PACKAGE_SUPPORT.md) - npm package support with postinstall protection
- [Package Governance](./PACKAGE_GOVERNANCE.md) - Maturity-based package access control
- [Package Security](./PACKAGE_SECURITY.md) - Comprehensive security testing documentation

### Advanced Guides
- [Skill Marketplace Guide](./SKILL_MARKETPLACE_GUIDE.md) - Detailed marketplace usage
- [Skill Composition Patterns](./SKILL_COMPOSITION_PATTERNS.md) - Workflow design patterns
- [Performance Tuning](./PERFORMANCE_TUNING.md) - Optimization and monitoring guide
- [Supply Chain Security](./SUPPLY_CHAIN_SECURITY.md) - E2E security testing (Plan 60-06)

### API Documentation
- [API Reference](../backend/docs/API_DOCUMENTATION.md) - Complete REST API documentation
- [Marketplace API](../backend/docs/API_DOCUMENTATION.md#marketplace) - Marketplace endpoints
- [Composition API](../backend/docs/API_DOCUMENTATION.md#composition) - Workflow endpoints
- [Auto-Install API](../backend/docs/API_DOCUMENTATION.md#auto-install) - Package installation endpoints

### Testing
- [Security Testing](../backend/docs/PACKAGE_SECURITY.md) - 34 tests covering all threat vectors
- [Performance Benchmarks](../backend/tests/test_performance_benchmarks.py) - Regression testing
- [E2E Supply Chain Tests](../backend/tests/test_e2e_supply_chain.py) - Real-world attack simulation

---

## Summary

**Phase 60 Status**: ✅ COMPLETE (February 19, 2026)

**Plans Implemented**:
- Plan 60-01: Skill Marketplace (PostgreSQL-based with Atom SaaS architecture)
- Plan 60-02: Dynamic Skill Loading (importlib + watchdog hot-reload)
- Plan 60-03: Skill Composition Engine (DAG workflows with NetworkX)
- Plan 60-04: Auto-Installation (Python + npm with conflict detection)
- Plan 60-06: Supply Chain Security (E2E testing with 36 tests)

**Key Features**:
- ✅ Local PostgreSQL marketplace with search, ratings, categories
- ✅ Runtime skill loading with <1s hot-reload
- ✅ DAG workflow engine with automatic rollback
- ✅ Auto-installation with conflict detection
- ✅ Comprehensive supply chain security (E2E tested)
- ✅ Performance benchmarks with regression detection
- ✅ 100% audit trail coverage

**Next Steps**:
1. Browse marketplace to discover community skills
2. Compose workflows using skill composition patterns
3. Monitor performance with benchmarking tools
4. Review security scan results before installation

---

**Last Updated**: February 19, 2026
