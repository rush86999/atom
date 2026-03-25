# Chaos Engineering Tests

Controlled failure injection tests for system resilience validation.

## Purpose

Chaos engineering tests validate system resilience to:
- Network latency (slow 3G simulation with Toxiproxy)
- Database connection drops (connection pool exhaustion)
- Memory pressure (heap exhaustion handling)
- Service crashes (LLM provider failures, Redis crashes)

## Safety

**Blast Radius Controls:**
- ✅ Test databases only (never production)
- ✅ Isolated test network (localhost only)
- ✅ 60-second failure duration limit
- ✅ Environment validation (ENVIRONMENT=test required)
- ✅ Database URL validation (no production endpoints)
- ✅ Hostname validation (no production hosts)

## Requirements

### Core Dependencies

```bash
pip install pytest pytest-timeout psutil
```

### Optional Dependencies

```bash
# Network chaos (Toxiproxy)
pip install toxiproxy-python

# Memory profiling
pip install memory-profiler
```

### Toxiproxy Setup

Toxiproxy is used for network latency simulation (slow 3G).

**Docker (recommended for CI):**
```bash
docker run -d --name toxiproxy -p 8474:8474 ghcr.io/shopify/toxiproxy:2.5.0
```

**macOS (Homebrew):**
```bash
brew tap shopify/shopify
brew install toxiproxy
toxiproxy-server -port 8474
```

**Verify Toxiproxy:**
```bash
curl http://localhost:8474/proxies
```

## Running Tests

### Run All Chaos Tests

```bash
cd backend
pytest tests/chaos/ -v -m chaos
```

### Run Specific Chaos Categories

```bash
# Network latency chaos
pytest tests/chaos/test_network_latency_chaos.py -v -m chaos

# Database drop chaos
pytest tests/chaos/test_database_drop_chaos.py -v -m chaos

# Memory pressure chaos
pytest tests/chaos/test_memory_pressure_chaos.py -v -m chaos

# Service crash chaos
pytest tests/chaos/test_service_crash_chaos.py -v -m chaos
```

### Run Blast Radius and Recovery Tests

```bash
# Blast radius control validation
pytest tests/chaos/test_blast_radius_controls.py -v -m chaos

# Recovery validation
pytest tests/chaos/test_recovery_validation.py -v -m chaos
```

### Skip Chaos Tests (Fast PR Tests)

```bash
# Skip chaos tests in fast CI
pytest tests/ -v -m "not chaos"
```

## Test Structure

```
tests/chaos/
├── core/
│   ├── chaos_coordinator.py       # Experiment orchestration service
│   ├── blast_radius_controls.py   # Safety mechanisms
│   └── __init__.py
├── fixtures/
│   ├── network_chaos_fixtures.py  # Toxiproxy network latency
│   ├── database_chaos_fixtures.py # Database connection drop
│   ├── memory_chaos_fixtures.py   # Memory pressure injection
│   └── service_crash_fixtures.py  # LLM/Redis crash simulation
├── test_network_latency_chaos.py
├── test_database_drop_chaos.py
├── test_memory_pressure_chaos.py
├── test_service_crash_chaos.py
├── test_blast_radius_controls.py
├── test_recovery_validation.py
├── conftest.py                     # Chaos fixtures
└── README.md                       # This file
```

## Fixtures

### ChaosCoordinator

Orchestrates chaos experiments with blast radius controls and recovery validation.

```python
from tests.chaos.core.chaos_coordinator import ChaosCoordinator

def test_example(chaos_coordinator):
    results = chaos_coordinator.run_experiment(
        experiment_name="test_example",
        failure_injection=inject_failure,
        verify_graceful_degradation=verify_graceful,
        blast_radius_checks=[assert_blast_radius]
    )
```

### Blast Radius Controls

Safety checks to prevent production impact.

```python
from tests.chaos.core.blast_radius_controls import assert_blast_radius

# Always run before chaos injection
assert_blast_radius()  # Raises AssertionError if unsafe
```

### Network Chaos Fixtures

```python
def test_slow_3g(slow_database_proxy):
    with slow_database_proxy.toxic("latency", latency_ms=2000):
        # Database queries have 2 second latency
        agent = db_session.query(Agent).first()
```

### Database Chaos Fixtures

```python
def test_database_drop(database_connection_dropper):
    with database_connection_dropper():
        # Database unavailable, queries fail
        pass
    # Connection restored
```

### Memory Chaos Fixtures

```python
def test_memory_pressure(memory_pressure_injector):
    with memory_pressure_injector(max_mb=512):
        # System under 512MB memory pressure
        result = perform_operation()
```

### Service Crash Fixtures

```python
def test_llm_crash(llm_provider_crash_simulator):
    with llm_provider_crash_simulator():
        # LLM calls will fail
        response = llm_service.chat("Hello")
```

## CI/CD Pipeline

### Weekly Execution

Chaos tests run weekly (Sunday 2 AM UTC) via GitHub Actions:

**Workflow:** `.github/workflows/chaos-engineering-weekly.yml`

**Steps:**
1. Checkout code
2. Set up Python 3.11
3. Install dependencies (pytest, psutil, toxiproxy-python)
4. Start Toxiproxy (Docker)
5. Verify test environment (ENVIRONMENT=test, no production access)
6. Run all chaos tests (120s timeout per test)
7. Upload test results
8. File bugs for failures
9. Cleanup Toxiproxy

**Manual Trigger:**
```bash
gh workflow run chaos-engineering-weekly.yml
```

## Troubleshooting

### Toxiproxy Not Available

**Error:** `toxiproxy-python not installed`

**Solution:**
```bash
pip install toxiproxy-python
docker run -d --name toxiproxy -p 8474:8474 ghcr.io/shopify/toxiproxy:2.5.0
```

### Tests Skipped Due to Missing Dependencies

**Error:** `psutil not installed` or `memory-profiler not installed`

**Solution:**
```bash
pip install psutil memory-profiler
```

### Blast Radius Check Failed

**Error:** `Unsafe: Database URL appears to be production`

**Solution:**
```bash
export DATABASE_URL=sqlite:///./test_chaos.db
export ENVIRONMENT=test
```

### Test Timeout

**Error:** `Timeout >60s`

**Solution:** Chaos tests have 60s duration limit. If test legitimately needs more time, adjust in pytest.ini or use `@pytest.mark.timeout(120)`.

### Redis Not Available

**Error:** `Redis connection refused`

**Solution:** Redis tests use mock if Redis not available. To use actual Redis:
```bash
docker run -d --name redis -p 6379:6379 redis:alpine
```

## Writing New Chaos Tests

Follow the template in `backend/tests/bug_discovery/TEMPLATES/CHAOS_TEMPLATE.md`.

**Key Requirements:**
1. Use `@pytest.mark.chaos` marker
2. Use `@pytest.mark.timeout(60)` for duration cap
3. Use `ChaosCoordinator` for orchestration
4. Include blast radius checks (`assert_blast_radius()`)
5. Verify graceful degradation (no crash)
6. Verify recovery (return to baseline)
7. Verify data integrity (no data loss/corruption)

**Example:**
```python
@pytest.mark.chaos
@pytest.mark.timeout(60)
def test_new_chaos_scenario(chaos_coordinator, chaos_db_session):
    """Test system resilience to [failure scenario]."""

    # Create test data
    agent = AgentRegistry(id="test-agent", name="test", maturity_level="STUDENT")
    chaos_db_session.add(agent)
    chaos_db_session.commit()

    # Define failure injection
    def inject_failure():
        return failure_context_manager

    # Define graceful degradation check
    def verify_graceful(metrics):
        assert metrics["cpu_percent"] < 100, "System crashed"

    # Run experiment
    results = chaos_coordinator.run_experiment(
        experiment_name="test_new_chaos_scenario",
        failure_injection=inject_failure,
        verify_graceful_degradation=verify_graceful,
        blast_radius_checks=[assert_blast_radius]
    )

    assert results["success"]
```

## See Also

- [CHAOS_TEMPLATE.md](../bug_discovery/TEMPLATES/CHAOS_TEMPLATE.md) - Chaos test template
- [BugFilingService](../bug_discovery/bug_filing_service.py) - Automated bug filing
- [AITriggerCoordinator](../../core/ai_trigger_coordinator.py) - Service orchestration pattern
