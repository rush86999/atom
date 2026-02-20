# End-to-End Testing Suite for Atom

Comprehensive E2E tests validating Atom's critical workflows with real service integration (PostgreSQL, Redis, LLM providers).

## Overview

This directory contains end-to-end tests that validate complete user journeys with **real services** (not mocked). E2E tests catch integration issues between components and ensure the system works as users expect.

**Testing Philosophy:**
- **Real Service Integration**: PostgreSQL, Redis, Docker, LLM providers (not mocked)
- **Complete User Journeys**: Test workflows end-to-end, not individual components
- **Production Confidence**: Validate actual behavior, not mocked responses
- **Performance Validation**: Ensure workflows complete within time thresholds
- **Coverage Targets**: 60-70% for MCP service (vs 26.56% with mocks)

### Why E2E Testing Matters

Unit tests validate individual components in isolation. Integration tests validate component interactions. **E2E tests validate complete user journeys** from start to finish, catching integration issues that unit/integration tests miss.

**Example**: Unit test might verify `AgentGovernanceService.can_perform_action()` returns `True`. E2E test verifies that an agent can actually execute a workflow end-to-end, including database writes, audit trails, and canvas presentations.

### Test Categories

| Category | File | Purpose | Tests |
|----------|------|---------|-------|
| **MCP Tools** | `test_mcp_tools_e2e.py` | MCP tool integration with real PostgreSQL | 66 |
| **Database** | `test_database_integration_e2e.py` | PostgreSQL, SQLite, migrations, pooling | 31 |
| **LLM Providers** | `test_llm_providers_e2e.py` | OpenAI, Anthropic, DeepSeek, BYOK | 36 |
| **Critical Workflows** | `test_critical_workflows_e2e.py` | Complete user journey validation | 20 |
| **Governance** | `test_scenario_01_governance.py` | Agent governance & routing | 8 |
| **Streaming** | `test_scenario_02_streaming.py` | Multi-provider LLM streaming | 6 |
| **Canvas** | `test_scenario_03_canvas.py` | Canvas presentations with governance | 5 |
| **Guidance** | `test_scenario_04_guidance.py` | Real-time agent guidance | 7 |
| **Browser** | `test_scenario_05_browser.py` | Browser automation with Playwright | 6 |
| **Episodes** | `test_scenario_06_episodes.py` | Episodic memory & retrieval | 8 |
| **Graduation** | `test_scenario_07_graduation.py` | Agent graduation framework | 7 |
| **Training** | `test_scenario_08_training.py` | Student agent training | 8 |
| **Device** | `test_scenario_09_device.py` | Device capabilities & permissions | 9 |
| **Deeplinks** | `test_scenario_10_deeplinks_feedback.py` | Deep linking & feedback | 8 |

## Setup Instructions

### Prerequisites

```bash
# 1. Install Python dependencies
cd /Users/rushiparikh/projects/atom/backend
pip install -e .

# 2. Install Docker (required for PostgreSQL and Redis)
# Download from: https://www.docker.com/products/docker-desktop

# 3. Install Playwright for browser automation tests (optional)
playwright install chromium
```

### Environment Configuration

```bash
# Required for E2E testing with real services
export E2E_TESTING=true

# Database configuration (default: PostgreSQL on port 5433)
export DATABASE_URL="postgresql://atom:atom@localhost:5433/atom_e2e"
# Or for Personal Edition testing:
# export DATABASE_URL="sqlite:///./atom_e2e.db"

# Redis configuration (default: localhost:6380)
export REDIS_URL="redis://localhost:6380"

# LLM Provider API Keys (optional - tests skip if not set)
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export DEEPSEEK_API_KEY="sk-..."
export GEMINI_API_KEY="..."

# Feature flags (automatically set by conftest.py)
export STREAMING_GOVERNANCE_ENABLED=true
export CANVAS_GOVERNANCE_ENABLED=true
export BROWSER_AUTOMATION_ENABLED=true
export EPISODIC_MEMORY_ENABLED=true
```

### Docker Service Setup

```bash
# Start PostgreSQL and Redis for E2E testing
cd /Users/rushiparikh/projects/atom
docker-compose -f docker-compose-e2e.yml up -d

# Verify services are running
docker ps

# Stop services when done
docker-compose -f docker-compose-e2e.yml down
```

**Services:**
- **PostgreSQL 16**: `localhost:5433` (user: `atom`, pass: `atom`, db: `atom_e2e`)
- **Valkey 8** (Redis-compatible): `localhost:6380`

## Test Execution Guide

### Running All E2E Tests

```bash
# Run all E2E tests with real services
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/e2e/ -v

# Run with timeout enforcement (10 minutes total)
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/e2e/ -v --timeout=600

# Run with coverage (MCP service target: 60-70%)
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/e2e/ -v --cov=integrations/mcp_service --cov-report=term-missing
```

### Running Specific Test Suites

```bash
# MCP Tool E2E Tests (PostgreSQL integration)
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/e2e/test_mcp_tools_e2e.py -v

# Database Integration E2E Tests (PostgreSQL, SQLite, migrations)
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/e2e/test_database_integration_e2e.py -v

# LLM Provider E2E Tests (requires API keys)
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/e2e/test_llm_providers_e2e.py -v

# Critical Workflow E2E Tests (complete user journeys)
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/e2e/test_critical_workflows_e2e.py -v
```

### Running with Coverage

```bash
# Generate HTML coverage report
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/e2e/ -v \
  --cov=integrations/mcp_service \
  --cov=core \
  --cov-report=html \
  --cov-report=term-missing

# View coverage report
open htmlcov/index.html

# Check coverage for specific module
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/e2e/ -v \
  --cov=integrations/mcp_service.mcp_service \
  --cov-report=term-missing
```

### Debugging Failed Tests

```bash
# Run with verbose output
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/e2e/test_critical_workflows_e2e.py -v -s

# Drop into debugger on failure
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/e2e/test_critical_workflows_e2e.py -v -s --pdb

# Run last failed tests
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/e2e/ -v --lf

# Run until first failure
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/e2e/ -v -x
```

## Test Organization

### E2E Test Files

#### 1. MCP Tool E2E Tests (`test_mcp_tools_e2e.py`)
**Purpose**: Validate MCP tool integration with real PostgreSQL operations

**Test Coverage**:
- CRM tools (Salesforce, HubSpot, Pipedrive): 5 tests
- Task management (Asana, Trello, Jira): 6 tests
- Ticketing systems (Zendesk, Freshdesk): 4 tests
- Knowledge base (Notion, Confluence): 6 tests
- Canvas presentations: 5 tests
- Finance tools (QuickBooks, Xero): 3 tests
- WhatsApp integration: 3 tests
- Shopify integration: 4 tests
- Error handling (404, 500, timeout): 8 tests
- Concurrency (parallel operations): 4 tests
- Performance (bulk operations): 4 tests
- Data validation (SQL injection, XSS): 10 tests

**Key Fixtures**:
- `e2e_docker_compose`: Start/stop Docker services
- `e2e_postgres_db`: PostgreSQL database connection
- `mcp_service`: MCP service instance with DB
- `crm_data_factory`: Create test CRM records

#### 2. Database Integration E2E Tests (`test_database_integration_e2e.py`)
**Purpose**: Validate database operations across PostgreSQL and SQLite

**Test Coverage**:
- PostgreSQL CRUD operations: 4 tests
- PostgreSQL transactions: 3 tests
- PostgreSQL foreign keys: 3 tests
- SQLite Personal Edition: 2 tests
- SQLite WAL mode: 1 test
- Connection pooling: 3 tests
- Alembic migrations: 4 tests
- Backup/restore: 3 tests
- Performance benchmarks: 3 tests

**Key Fixtures**:
- `e2e_postgres_db`: PostgreSQL database
- `e2e_sqlite_db`: SQLite in-memory database
- `migration_runner`: Run Alembic migrations
- `database_backup`: Backup/restore utilities

#### 3. LLM Provider E2E Tests (`test_llm_providers_e2e.py`)
**Purpose**: Validate multi-provider LLM integration with real API calls

**Test Coverage**:
- OpenAI integration: 6 tests
- Anthropic integration: 6 tests
- DeepSeek integration: 5 tests
- BYOK handler: 7 tests
- Context management: 3 tests
- Cross-provider comparison: 2 tests
- Error handling: 3 tests
- Performance benchmarks: 2 tests

**Key Fixtures**:
- `llm_api_keys`: Detect available API keys
- `openai_client`: OpenAI client (skips if no key)
- `anthropic_client`: Anthropic client (skips if no key)
- `byok_handler`: BYOK handler with multiple providers

**Note**: Tests gracefully skip when API keys not configured (CI-friendly)

#### 4. Critical Workflow E2E Tests (`test_critical_workflows_e2e.py`)
**Purpose**: Validate complete user journeys end-to-end

**Test Coverage**:
- **Agent Execution Workflow** (3 tests):
  - Complete agent lifecycle (creation, execution, monitoring, results)
  - Failure scenarios with error handling
  - Multi-agent coordination

- **Skill Loading Workflow** (3 tests):
  - Skill import, security scanning, storage, execution
  - Package dependency detection
  - Invalid SKILL.md handling

- **Package Installation Workflow** (3 tests):
  - Governance approval, vulnerability scanning, installation
  - Dependency resolution
  - Graceful failure handling

- **Multi-Provider LLM Workflow** (3 tests):
  - Provider failure and fallback
  - Cost optimization
  - Budget enforcement

- **Canvas Presentation Workflow** (3 tests):
  - Canvas creation, LLM content generation, presentation
  - LLM-generated content on canvas
  - Feedback loop and linkage

- **End-to-End Smoke Tests** (5 tests):
  - Complete agent-to-canvas journey
  - Skill-to-package integration
  - Performance threshold validation
  - Data integrity checks
  - Error recovery and audit trail validation

**Key Fixtures**:
- `agent_workflow`: Agent execution workflow setup
- `skill_workflow`: Skill loading workflow setup
- `package_workflow`: Package installation workflow setup
- `llm_workflow`: Multi-provider LLM workflow setup
- `canvas_workflow`: Canvas presentation workflow setup
- `composite_workflow`: All workflows combined
- `workflow_performance_thresholds`: Performance validation

### Fixture Modules

#### `conftest.py` - Root E2E Configuration
- Docker Compose lifecycle management
- PostgreSQL and Redis fixtures
- LLM API key detection
- Test data factories
- Performance monitoring

#### `fixtures/workflow_fixtures.py` - Workflow-Specific Fixtures
- Agent workflow fixture
- Skill workflow fixture
- Package workflow fixture
- LLM workflow fixture
- Canvas workflow fixture
- Composite workflow fixture
- Performance threshold fixture
- Audit trail helper

#### `fixtures/database_fixtures.py` - Database Fixtures
- PostgreSQL engine fixture
- SQLite engine fixture
- Migration runner fixture
- Backup/restore fixture
- Connection pool fixture

#### `fixtures/llm_fixtures.py` - LLM Provider Fixtures
- API key detection
- OpenAI client fixture
- Anthropic client fixture
- BYOK handler fixture
- Mock response fixture

#### `fixtures/test_data_factory.py` - Test Data Generation
- CRM data factory
- Task data factory
- Ticket data factory
- Knowledge base factory
- Canvas data factory
- Finance data factory

## CI/CD Integration

### GitHub Actions Configuration

```yaml
name: E2E Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]
  schedule:
    # Run daily at 2 AM UTC
    - cron: '0 2 * * *'

jobs:
  e2e-tests:
    runs-on: ubuntu-latest
    timeout-minutes: 15

    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_USER: atom
          POSTGRES_PASSWORD: atom
          POSTGRES_DB: atom_e2e
        ports:
          - 5433:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

      redis:
        image: valkey/valkey:8
        ports:
          - 6380:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd backend
          pip install -e .
          pip install pytest pytest-timeout pytest-cov

      - name: Run E2E tests
        env:
          E2E_TESTING: true
          DATABASE_URL: postgresql://atom:atom@localhost:5433/atom_e2e
          REDIS_URL: redis://localhost:6380
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          PYTHONPATH=./backend pytest backend/tests/e2e/ -v \
            --timeout=600 \
            --cov=integrations/mcp_service \
            --cov-report=xml \
            --cov-report=term-missing

      - name: Check coverage threshold
        run: |
          coverage=$(coverage report | grep integrations/mcp_service | awk '{print $4}' | sed 's/%//')
          if (( $(echo "$coverage < 60" | bc -l) )); then
            echo "Coverage $coverage% below 60% threshold"
            exit 1
          fi
          echo "Coverage $coverage% meets threshold"

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
          flags: e2e
          name: e2e-coverage

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: e2e-test-results
          path: |
            backend/htmlcov/
            backend/.coverage*
```

### Parallel Execution

```bash
# Run E2E tests in parallel (faster on CI)
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/e2e/ -v -n auto

# Run specific suites in parallel
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest \
  backend/tests/e2e/test_mcp_tools_e2e.py \
  backend/tests/e2e/test_database_integration_e2e.py \
  -v -n auto
```

## Performance Benchmarks

### Expected Execution Times

| Test Suite | Tests | Target | Notes |
|------------|-------|--------|-------|
| MCP Tools E2E | 66 | 2-3 min | PostgreSQL operations |
| Database Integration | 31 | 1-2 min | PostgreSQL + SQLite |
| LLM Providers | 36 | 2-4 min | API calls (if keys set) |
| Critical Workflows | 20 | 1-2 min | Workflow validation |
| Scenarios (01-10) | 64 | 3-5 min | Feature scenarios |
| **TOTAL** | **217+** | **<10 min** | **Full suite target** |

### Performance Targets

| Workflow | Target | Validation |
|----------|--------|------------|
| Agent creation | <1s | `test_workflow_performance_within_thresholds` |
| Agent execution | <10s | `test_agent_execution_workflow` |
| Skill import | <5s | `test_skill_loading_workflow` |
| Package install | <60s | `test_python_package_installation` |
| LLM streaming | <5s | `test_multi_provider_fallback` |
| Canvas presentation | <2s | `test_canvas_presentation_workflow` |
| **Total workflow** | **<2 min** | `test_complete_agent_to_canvas_workflow` |

### Timeout Enforcement

```bash
# Set 10-minute timeout for entire suite
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/e2e/ -v --timeout=600

# Set per-test timeout
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/e2e/ -v --timeout=30
```

## Coverage Targets

### Current Baseline (Phase 62)

| Module | Coverage | Target | Gap |
|--------|----------|--------|-----|
| MCP Service | 26.56% | 60-70% | **-33% to -43%** |
| Core Services | 24.4% | 50-60% | -26% to -36% |
| API Routes | 38.2% | 70-80% | -32% to -42% |

### E2E Test Contribution

E2E tests with real services should improve MCP service coverage from **26.56% to 60-70%**:

**Why E2E Improves Coverage**:
- Unit tests mock external dependencies (database, APIs)
- E2E tests use real PostgreSQL, Redis, LLM providers
- Real service integration covers actual code paths
- No mocking = actual code execution = better coverage

**Validation**:
```bash
# Run E2E tests with coverage
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/e2e/ -v \
  --cov=integrations/mcp_service \
  --cov-report=term-missing

# Check MCP service coverage
# Target: 60-70% (vs 26.56% baseline)
```

## Troubleshooting

### Docker Issues

**Issue**: Docker services not starting
```bash
# Check Docker is running
docker ps

# Restart Docker Desktop (macOS/Windows)
# Or restart Docker daemon (Linux)
sudo systemctl restart docker

# Re-create services
docker-compose -f docker-compose-e2e.yml down
docker-compose -f docker-compose-e2e.yml up -d
```

**Issue**: PostgreSQL connection refused
```bash
# Check PostgreSQL is running
docker ps | grep postgres

# Check PostgreSQL logs
docker-compose -f docker-compose-e2e.yml logs postgres

# Verify connection
psql -h localhost -p 5433 -U atom -d atom_e2e
```

**Issue**: Redis connection refused
```bash
# Check Redis is running
docker ps | grep redis

# Check Redis logs
docker-compose -f docker-compose-e2e.yml logs redis

# Verify connection
redis-cli -p 6380 ping
```

### Database Issues

**Issue**: "Database is locked" (SQLite)
```bash
# Remove stale database files
rm -f atom_e2e.db atom_e2e.db-wal atom_e2e.db-shm

# Re-run tests
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/e2e/ -v
```

**Issue**: Migration failures
```bash
# Reset database
docker-compose -f docker-compose-e2e.yml down
docker volume rm atom_postgres_data
docker-compose -f docker-compose-e2e.yml up -d

# Run migrations manually
cd backend
alembic upgrade head
```

### API Key Issues

**Issue**: "API key required" (LLM tests)
```bash
# Option 1: Set API keys
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."

# Option 2: Skip LLM tests
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/e2e/ -v -k "not llm"
```

### Test Timeout Issues

**Issue**: Tests exceed timeout
```bash
# Increase timeout
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/e2e/ -v --timeout=900

# Run tests individually
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/e2e/test_critical_workflows_e2e.py -v -s

# Run slow tests last
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/e2e/ -v -m "not slow"
```

### Import Errors

**Issue**: "No module named 'core'"
```bash
# Set PYTHONPATH
export PYTHONPATH=/Users/rushiparikh/projects/atom/backend

# Or use inline
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/e2e/ -v
```

**Issue**: "No module named 'pytest'"
```bash
# Install pytest
cd /Users/rushiparikh/projects/atom/backend
pip install pytest pytest-timeout pytest-cov
```

## Best Practices

### Writing E2E Tests

1. **Test Complete Workflows**: Don't test individual functions - test user journeys
2. **Use Real Services**: PostgreSQL, Redis, Docker (not mocks)
3. **Validate Audit Trails**: Check database records, logs, metrics
4. **Test Failure Scenarios**: Not just happy path - error handling too
5. **Assert Performance**: Use `workflow_performance_thresholds` fixture
6. **Clean Up Test Data**: Use fixtures with proper teardown

### Example E2E Test

```python
def test_complete_user_workflow(composite_workflow):
    """Test complete workflow from user request to result."""
    agent = composite_workflow["agent"]
    canvas = composite_workflow["canvas"]

    # Step 1: Execute agent
    execution = AgentExecution(
        agent_id=agent["agent"].id,
        user_id=canvas["user_id"],
        task="Generate insights",
        status="in_progress"
    )
    agent["session"].add(execution)
    agent["session"].commit()

    # Step 2: Complete execution
    execution.status = "completed"
    execution.output_data = {"insights": ["insight1", "insight2"]}
    agent["session"].commit()

    # Step 3: Create canvas
    audit = CanvasAudit(
        canvas_id=canvas["canvas_id"],
        user_id=canvas["user_id"],
        action="present",
        canvas_data=execution.output_data
    )
    canvas["session"].add(audit)
    canvas["session"].commit()

    # Step 4: Verify workflow complete
    assert execution.status == "completed"
    assert audit.action == "present"
```

## Contributing

When adding new E2E tests:

1. **Create Test File**: `tests/e2e/test_new_feature_e2e.py`
2. **Use E2E Fixtures**: Leverage existing fixtures from `fixtures/`
3. **Test Real Services**: Use PostgreSQL, Redis, Docker (not mocks)
4. **Validate Workflows**: Test complete user journeys
5. **Add Performance Assertions**: Use `workflow_performance_thresholds`
6. **Update README**: Document new tests in this file
7. **Update conftest.py**: Add new fixtures if needed
8. **Verify Coverage**: Run with `--cov` to check coverage contribution

## Resources

### Documentation
- **Main Documentation**: `/Users/rushiparikh/projects/atom/CLAUDE.md`
- **API Documentation**: `/Users/rushiparikh/projects/atom/backend/docs/API_DOCUMENTATION.md`
- **Deployment Guide**: `/Users/rushiparikh/projects/atom/backend/docs/DEPLOYMENT_RUNBOOK.md`
- **Operations Guide**: `/Users/rushiparikh/projects/atom/backend/docs/OPERATIONS_GUIDE.md`

### Source Code
- **Core Services**: `/Users/rushiparikh/projects/atom/backend/core/`
- **API Routes**: `/Users/rushiparikh/projects/atom/backend/api/`
- **Integrations**: `/Users/rushiparikh/projects/atom/backend/integrations/`
- **Tools**: `/Users/rushiparikh/projects/atom/backend/tools/`

### Test Infrastructure
- **E2E Fixtures**: `/Users/rushiparikh/projects/atom/backend/tests/e2e/fixtures/`
- **Unit Tests**: `/Users/rushiparikh/projects/atom/backend/tests/unit/`
- **Integration Tests**: `/Users/rushiparikh/projects/atom/backend/tests/integration/`

## Support

For issues or questions about E2E testing:
1. Check test docstrings for details
2. Review fixture definitions in `tests/e2e/fixtures/`
3. Inspect service implementations in `core/`
4. Check API route implementations in `api/`
5. Review CI/CD logs for environment-specific issues
6. Check Docker logs: `docker-compose -f docker-compose-e2e.yml logs`

---

**Last Updated**: 2025-02-20
**E2E Test Count**: 217+ tests across 14 test files
**Coverage Target**: 60-70% for MCP service (vs 26.56% baseline)
**Performance Target**: <10 minutes for full suite execution
