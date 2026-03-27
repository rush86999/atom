# Chaos Engineering Test: [Failure Scenario]

## Purpose

Validate system resilience to [failure type: network latency, database drop, memory pressure, service crash]

**What this test validates:**
- System behavior during failure: [graceful degradation, error handling, retry logic]
- Recovery behavior: [automatic recovery, data integrity, rollback]
- No data loss or corruption during failure

**Target:**
- Service: `[service_name]`
- Component: `[component_name]`
- Dependency: `[database, API, external service]`

## Dependencies

**Required Libraries:**
```bash
# Network chaos (Toxiproxy)
pip install toxiproxy-python

# Memory pressure
pip install memory-profiler

# Service chaos
pip install pytest-container
```

**Target Service:**
- `backend/core/[service].py` - [description of target]
- `backend/api/[routes].py` - [description of target API]

**Blast Radius:**
- **Test database only:** `[database_name]` (NEVER production)
- **Isolated test environment:** Docker compose test network
- **Failure duration limit:** 60 seconds maximum

## Setup

**1. Create isolated test database:**
```python
@pytest.fixture(scope="function")
def chaos_db_session():
    """
    Isolated database for chaos testing.

    IMPORTANT: This must be a separate database from other tests
    to prevent interference with concurrent test runs.
    """
    # Create test database
    db_url = "sqlite:///./test_chaos.db"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    # Cleanup: Drop database after test
    session.close()
    os.remove("./test_chaos.db")
```

**2. Configure failure injection limits:**
```python
# Chaos test configuration
CHAOS_CONFIG = {
    "network_latency": {
        "max_latency_ms": 5000,  # Maximum 5 seconds
        "duration_seconds": 30,   # Maximum 30 seconds
    },
    "database_drop": {
        "duration_seconds": 10,   # Maximum 10 seconds
        "retry_interval_seconds": 1,
    },
    "memory_pressure": {
        "max_mb": 1024,           # Maximum 1GB
        "duration_seconds": 30,
    }
}
```

**3. Set monitoring/alerting:**
```python
import psutil
import time

def monitor_system_during_test(duration_seconds=60):
    """
    Monitor system resources during chaos test.

    Returns:
        Dict with CPU, memory, disk usage metrics
    """
    metrics = {
        "cpu_percent": [],
        "memory_mb": [],
        "disk_io": [],
    }

    start_time = time.time()
    while time.time() - start_time < duration_seconds:
        metrics["cpu_percent"].append(psutil.cpu_percent())
        metrics["memory_mb"].append(psutil.virtual_memory().used / (1024 * 1024))
        metrics["disk_io"].append(psutil.disk_io_counters())
        time.sleep(1)

    return metrics
```

## Test Procedure

**Step 1: Baseline measurement**
```python
@pytest.mark.chaos
def test_[scenario]_chaos(chaos_db_session):
    """
    Test system resilience to [failure scenario].

    Scenario: [description of failure]
    Duration: [seconds]
    Blast radius: test database only
    """
    # 1. Measure baseline operation
    baseline_metrics = measure_system_health()
    print(f"Baseline: {baseline_metrics}")

    # Create test data before injecting failure
    test_agent = create_test_agent(chaos_db_session, name="chaos_test")
    chaos_db_session.commit()
```

**Step 2: Inject failure**
```python
    # 2. Inject failure
    with failure_injector("[failure_type]", duration=30):
        # System should degrade gracefully
        result = execute_operation(test_agent.id)

        # Monitor system behavior during failure
        failure_metrics = measure_system_health()
        print(f"During failure: {failure_metrics}")

        # Assert graceful degradation (not crash)
        assert result.status in ["completed", "failed", "timeout"], \
            f"Unexpected status: {result.status}"

        # Assert no crash (HTTP 500)
        if hasattr(result, "http_status"):
            assert result.http_status != 500, "Server crashed during failure"
```

**Step 3: Monitor and rollback**
```python
    # 3. Rollback: Remove failure injection
    # (handled by failure_injector context manager)

    # 4. Verify system recovers to baseline
    recovery_metrics = measure_system_health()
    print(f"Recovery: {recovery_metrics}")

    # Assert recovery within acceptable bounds
    assert abs(recovery_metrics["cpu_percent"] - baseline_metrics["cpu_percent"]) < 20, \
        "CPU usage did not recover to baseline"

    # 5. Verify data integrity
    recovered_agent = chaos_db_session.query(AgentRegistry).filter_by(id=test_agent.id).first()
    assert recovered_agent is not None, "Agent was lost during failure"
    assert recovered_agent.name == "chaos_test", "Agent data corrupted"
```

**Example: Network latency chaos**
```python
from toxiproxy import Toxiproxy

@pytest.mark.chaos
def test_network_latency_chaos(chaos_db_session):
    """
    Test system resilience to network latency.

    Scenario: 2000ms network latency to database
    Duration: 30 seconds
    Blast radius: test database only
    """
    # Setup Toxiproxy
    toxiproxy = Toxiproxy.create_toxiproxy("localhost:8474")
    proxy = toxiproxy.create_proxy(
        name="db_proxy",
        upstream="database:5432",
        listen="localhost:5555"
    )

    try:
        # Baseline
        baseline_time = measure_query_time()

        # Inject network latency
        with proxy.toxic("latency", latency_ms=2000, jitter=0):
            # System should handle latency gracefully
            start_time = time.time()
            result = execute_database_query()
            latency = time.time() - start_time

            # Assert timeout or graceful degradation
            assert latency > 2, "Latency not applied"
            assert result.status in ["timeout", "completed"], \
                f"Unexpected status: {result.status}"

        # Verify recovery
        recovery_time = measure_query_time()
        assert abs(recovery_time - baseline_time) < 0.5, "System did not recover"

    finally:
        # Cleanup: Remove proxy
        toxiproxy.destroy()
```

**Example: Database connection drop chaos**
```python
@pytest.mark.chaos
def test_database_drop_chaos(chaos_db_session):
    """
    Test system resilience to database connection drops.

    Scenario: Database connection drops for 10 seconds
    Duration: 10 seconds
    Blast radius: test database only
    """
    # Create test data before drop
    agent = create_test_agent(chaos_db_session, name="drop_test")
    agent_id = agent.id
    chaos_db_session.commit()

    # Baseline: Agent exists
    assert agent_id is not None

    # Inject database drop
    with database_connection_drop(duration=10):
        # System should handle connection error gracefully
        with pytest.raises((DatabaseError, OperationalError)):
            # Query should fail gracefully (not crash)
            chaos_db_session.query(AgentRegistry).filter_by(id=agent_id).first()

        # Retry logic should kick in
        result = retry_database_query(agent_id, max_retries=5)
        assert result.status in ["retry_exhausted", "timeout"], \
            f"Unexpected status: {result.status}"

    # Verify recovery: Connection restored
    recovered_agent = chaos_db_session.query(AgentRegistry).filter_by(id=agent_id).first()
    assert recovered_agent is not None, "Agent lost after database recovery"
    assert recovered_agent.name == "drop_test", "Data corrupted after recovery"
```

**Example: Memory pressure chaos**
```python
@pytest.mark.chaos
def test_memory_pressure_chaos(chaos_db_session):
    """
    Test system resilience to memory pressure.

    Scenario: Allocate 500MB memory for 30 seconds
    Duration: 30 seconds
    Blast radius: test process only
    """
    # Baseline memory
    baseline_mb = psutil.virtual_memory().used / (1024 * 1024)

    # Inject memory pressure
    memory_allocator = allocate_memory(mb=500, duration=30)

    try:
        # System should handle memory pressure gracefully
        result = execute_memory_intensive_operation()

        # Assert no crash (not OutOfMemoryError)
        assert result is not None, "Operation failed under memory pressure"

        # Assert performance degradation (not crash)
        current_mb = psutil.virtual_memory().used / (1024 * 1024)
        assert current_mb > baseline_mb + 400, "Memory pressure not applied"

    finally:
        # Cleanup: Release memory
        memory_allocator.release()
```

## Expected Behavior

**During failure:**
- System degrades gracefully (no crashes)
- Error handling works (appropriate error messages)
- Retry logic activates (if applicable)
- No data loss or corruption
- No cascading failures (other services unaffected)

**After recovery:**
- System returns to baseline performance
- Data integrity maintained (no lost/corrupted data)
- No zombie processes or resource leaks
- All connections restored

**Blast radius:**
- Failure scoped to test database only
- No impact on other test runs
- No impact on production systems
- Isolated test network (Docker compose)

## Blast Radius Controls

**Isolation mechanisms:**

1. **Test database:**
   - Database: `./test_chaos.db` (separate from main test database)
   - Scope: Function-level fixture (fresh database per test)
   - Verification: Query database name before injecting failure

2. **Failure duration limit:**
   - Maximum: 60 seconds (enforced by pytest timeout)
   - Monitoring: Log start/end timestamps
   - Auto-rollback: Context manager ensures cleanup

3. **Injection scope:**
   - Network: Test network only (Docker compose network)
   - Database: Test database only (NEVER production)
   - Services: Test containers only (NEVER production)

4. **Resource limits:**
   - Memory: Maximum 1GB allocation
   - CPU: Maximum 80% usage
   - Duration: Maximum 60 seconds

**Verification commands:**
```bash
# Verify test database (NEVER production)
echo $DATABASE_URL  # Should be sqlite:///./test_chaos.db

# Verify failure duration
grep "duration_seconds" backend/tests/bug_discovery/test_*_chaos.py  # Should be <= 60

# Verify isolation
docker ps  # Should show test containers only
```

## Bug Filing

**Automatic bug filing on resilience failure:**
```python
from tests.bug_discovery.bug_filing_service import BugFilingService

def file_bug_from_resilience_failure(test_name, failure_details):
    """
    File bug for chaos engineering resilience failure.

    Args:
        test_name: Name of chaos test
        failure_details: Dict with failure metadata
    """
    BugFilingService.file_bug(
        test_name=f"test_{test_name}_chaos",
        error_message=f"Resilience failure: {failure_details['failure_type']}",
        metadata={
            "test_type": "chaos",
            "failure_scenario": failure_details["scenario"],
            "injection_duration": failure_details["duration"],
            "blast_radius": "test_database_only",
            "baseline_metrics": failure_details["baseline"],
            "failure_metrics": failure_details["during_failure"],
            "recovery_metrics": failure_details["after_recovery"],
            "data_loss": failure_details.get("data_loss", False),
            "data_corruption": failure_details.get("data_corruption", False),
        },
        expected_behavior=f"System should degrade gracefully during {failure_details['scenario']}",
        actual_behavior=f"System crashed or failed to recover: {failure_details['error']}"
    )
```

**Manual bug filing (if not automatic):**
```bash
# Bug title: [Bug] Resilience failure: [Failure Scenario] Chaos

# Bug body:
## Bug Description

Chaos engineering test discovered resilience failure in [service_name].

## Failure Scenario

- Type: [network latency / database drop / memory pressure]
- Duration: [seconds]
- Blast radius: test database only

## Steps to Reproduce

1. Run chaos test: `pytest backend/tests/bug_discovery/test_[scenario]_chaos.py -v`
2. Inject failure: [specific failure injection steps]
3. Observe system behavior: [description of failure]

## Actual Behavior

- System crashed with error: [error message]
- Data loss: [yes/no]
- Data corruption: [yes/no]
- Cascading failures: [description]

## Expected Behavior

- System should degrade gracefully (return error, not crash)
- No data loss or corruption
- System should recover after failure injection removed

## Metrics

**Baseline:**
- CPU: [percent]
- Memory: [MB]
- Response time: [ms]

**During failure:**
- CPU: [percent]
- Memory: [MB]
- Response time: [ms]

**After recovery:**
- CPU: [percent]
- Memory: [MB]
- Response time: [ms]

## Blast Radius Verification

- Test database: [database_name]
- Test network: [docker network]
- Duration limit: [seconds]
- Production impact: NONE (verified)
```

## TQ Compliance

**TQ-01 (Test Independence):**
- Isolated test database per test (`chaos_db_session` fixture)
- No shared state between chaos tests
- Each test is self-contained with setup/teardown

**TQ-02 (Pass Rate):**
- Chaos tests are deterministic (same failure = same behavior)
- Same failure injection produces same system response
- 98%+ pass rate expected (failures = real bugs)

**TQ-03 (Performance):**
- Failure injection capped at 60s (enforced by pytest timeout)
- Most chaos tests complete in 30-45s
- Use `@pytest.mark.timeout(60)` to enforce limit

**TQ-04 (Determinism):**
- Same failure injection produces same results
- Toxiproxy provides deterministic network conditions
- Memory allocation is deterministic (fixed MB)

**TQ-05 (Coverage Quality):**
- Tests resilience behavior (observable system behavior)
- Not implementation details (internal error handling)
- Validates graceful degradation (user-facing)

## pytest.ini Marker

Add to `backend/pytest.ini`:
```ini
[pytest]
markers =
    chaos: Chaos engineering tests (failure injection, isolated environment, slow)
```

Run only chaos tests:
```bash
pytest backend/tests/bug_discovery/ -v -m chaos
```

Skip chaos tests in fast CI:
```bash
pytest backend/tests/ -v -m "not chaos"
```

## Safety Checks

**Before running chaos tests:**
```bash
# Verify environment
echo $ENVIRONMENT  # Should be "test" or "development"

# Verify database
echo $DATABASE_URL  # Should be test database

# Verify no production access
ping production.example.com  # Should FAIL (no access)
```

**During chaos tests:**
```python
# Assert blast radius
def assert_blast_radius():
    """Ensure failure is scoped to test environment only."""
    db_url = os.getenv("DATABASE_URL")
    assert "test" in db_url or "dev" in db_url, \
        f"Unsafe: Database URL appears to be production: {db_url}"

    # Assert no production endpoints
    production_endpoints = ["api.production.com", "prod-db.example.com"]
    for endpoint in production_endpoints:
        assert endpoint not in db_url, \
            f"Unsafe: Production endpoint in URL: {endpoint}"
```

**After chaos tests:**
```bash
# Verify cleanup
ls -la ./test_chaos.db  # Should be removed
docker ps  # Should show no running toxiproxy containers
```

## See Also

- [Chaos Engineering Principles](https://principlesofchaos.org)
- [Toxiproxy Python Documentation](https://github.com/ihucos/toxiproxy-python)
- `backend/docs/TEST_QUALITY_STANDARDS.md` - TQ-01 through TQ-05
- `backend/tests/bug_discovery/TEMPLATES/README.md` - Template usage guide
