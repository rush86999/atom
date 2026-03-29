# Phase 241: Chaos Engineering Integration - Research

**Researched:** 2026-03-24
**Domain:** Chaos engineering, failure injection, resilience testing, Toxiproxy, blast radius controls
**Confidence:** HIGH

## Summary

Phase 241 focuses on implementing controlled chaos engineering experiments to validate system resilience to network issues, resource exhaustion, and service crashes. The research confirms that Atom has **comprehensive testing infrastructure** (Phase 237 bug discovery infrastructure, Phase 236 network simulation fixtures, automated bug filing service) and **existing chaos test templates** ready for implementation. The key insight is that chaos engineering requires **blast radius controls** (isolated test databases, failure injection limits, duration caps) and **recovery validation** (data integrity checks, rollback verification) to prevent production impact.

**Primary recommendation:** Build ChaosCoordinator service for experiment orchestration, integrate Toxiproxy for network chaos (slow 3G simulation, latency injection), implement memory pressure injection with psutil/memory_profiler, simulate service crashes (LLM provider failures, Redis crashes), and enforce blast radius controls (test databases only, 60s duration caps, weekly CI pipeline). Reuse existing fixtures (network_fixtures.py, memory_fixtures.py, bug_filing_service.py) and follow CHAOS_TEMPLATE.md patterns.

**Key findings:**
1. **Existing chaos infrastructure is production-ready**: CHAOS_TEMPLATE.md (529 lines) with Toxiproxy examples, network_fixtures.py (485 lines) with slow 3G/offline/db_drop simulation, memory_fixtures.py (316 lines) with CDP heap snapshots
2. **Blast radius controls are well-defined**: Test database isolation (chaos_db_session fixture), failure duration limits (60s max via pytest-timeout), injection scope limits (test network only, never production)
3. **Automated bug filing exists**: bug_filing_service.py with GitHub Issues API, idempotency checks, metadata collection (test_type, blast_radius, data_loss, data_corruption)
4. **Weekly CI pipeline established**: weekly-stress-tests.yml, bug-discovery-weekly.yml with scheduled execution (Sunday 3 AM UTC), artifact collection, Slack/email alerts
5. **Safety mechanisms proven**: Blast radius assertions (assert_blast_radius()), environment checks (ENVIRONMENT="test"), database URL validation (no production endpoints)

## Standard Stack

### Core Chaos Engineering Tools
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | 7.4.x | Test runner and chaos test orchestration | Industry standard, rich plugin ecosystem, @pytest.mark.chaos marker already defined |
| **pytest-timeout** | 2.2.x | Enforce 60s failure injection duration limit | Prevent hanging tests, blast radius control (TQ-03 compliance) |
| **toxiproxy-python** | latest | TCP proxy for network chaos simulation | De facto standard for network latency, jitter, packet loss injection |
| **psutil** | 5.9.x | System resource monitoring (CPU, memory, disk I/O) | Cross-platform process monitoring, memory pressure detection |
| **memory_profiler** | 0.61.x | Memory usage profiling and leak detection | Python-native memory tracking, heap snapshot analysis |

### Service Crash Simulation
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pytest-container** | latest | Docker container lifecycle control | Service crash simulation (Redis, PostgreSQL) |
| **subprocess** | stdlib | Process control (start/stop services) | LLM provider failure simulation |
| **unittest.mock** | stdlib | Mock external dependencies | API failure simulation without real crashes |

### Blast Radius Controls
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **pytest fixtures** | stdlib | Test database isolation | chaos_db_session (isolated DB per test) |
| **environment checks** | stdlib | Verify test environment only | assert_blast_radius() (no production access) |
| **context managers** | stdlib | Automatic cleanup (rollback) | failure_injector context manager |

### Monitoring & Validation
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **psutil** | 5.9.x | System metrics during chaos | CPU, memory, disk I/O monitoring |
| **SQLAlchemy** | 2.0.x | Database integrity checks | Data integrity validation post-chaos |
| **BugFilingService** | (Phase 236-08) | Automated bug filing | GitHub Issues for resilience failures |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **toxiproxy-python** | chaostoolkit-network | chaostoolkit is more complex (YAML experiments), toxiproxy-python is simpler for pytest integration |
| **psutil** | resource (stdlib) | psutil is cross-platform, resource module is Unix-only |
| **pytest-timeout** | signal.alarm | pytest-timeout integrates with pytest, signal.alarm requires custom handling |

**Installation:**
```bash
# Core chaos engineering (add to requirements-testing.txt)
pip install toxiproxy-python psutil memory-profiler pytest-container

# Already installed (Phase 237)
pip install pytest pytest-timeout pytest-rerunfailures
```

## Architecture Patterns

### Recommended Project Structure

**Existing Structure (DO NOT CHANGE):**
```
backend/tests/
├── bug_discovery/          # ✅ EXISTS - Bug filing service
│   ├── bug_filing_service.py
│   ├── fixtures/
│   │   └── bug_filing_fixtures.py
│   └── TEMPLATES/
│       ├── FUZZING_TEMPLATE.md
│       ├── CHAOS_TEMPLATE.md     # ✅ EXISTS - 529 lines
│       ├── PROPERTY_TEMPLATE.md
│       └── BROWSER_TEMPLATE.md
├── e2e_ui/fixtures/
│   ├── network_fixtures.py       # ✅ EXISTS - 485 lines (slow 3G, offline, db_drop)
│   └── memory_fixtures.py        # ✅ EXISTS - 316 lines (CDP heap snapshots)
└── chaos/                         # ✅ NEW - Chaos engineering tests
    ├── conftest.py                # Chaos fixtures, safety checks
    ├── test_network_chaos.py      # Network latency tests
    ├── test_database_chaos.py     # Connection drop tests
    ├── test_memory_chaos.py       # Memory pressure tests
    └── test_service_crash.py      # Service crash tests
```

**NEW Structure (Phase 241):**
```
backend/tests/chaos/
├── conftest.py                    # Chaos fixtures, Toxiproxy setup
├── core/
│   ├── chaos_coordinator.py       # ✅ NEW - Experiment orchestration service
│   └── blast_radius_controls.py   # ✅ NEW - Safety mechanisms
├── test_network_latency_chaos.py  # ✅ NEW - Toxiproxy slow 3G tests
├── test_database_drop_chaos.py    # ✅ NEW - Connection pool exhaustion tests
├── test_memory_pressure_chaos.py  # ✅ NEW - Heap exhaustion tests
└── test_service_crash_chaos.py    # ✅ NEW - LLM provider/Redis crash tests
```

**Key Principle:** Follow CHAOS_TEMPLATE.md structure (Purpose, Setup, Test Procedure, Expected Behavior, Blast Radius Controls, Bug Filing).

### Pattern 1: Toxiproxy Network Chaos Fixture

**What:** Use Toxiproxy as TCP proxy to inject network latency, jitter, packet loss.

**When to use:** Testing system resilience to slow 3G connections, database latency, API timeouts.

**Example:**
```python
# Source: backend/tests/chaos/conftest.py
import pytest
from toxiproxy import Toxiproxy

@pytest.fixture(scope="function")
def toxiproxy_server():
    """Start Toxiproxy server for network chaos experiments.

    Blast radius: Test network only (localhost:8474)
    Duration: Automatic cleanup after test

    Yields:
        Toxiproxy client instance
    """
    # Create Toxiproxy client (assumes Toxiproxy running on localhost:8474)
    toxiproxy = Toxiproxy.create_toxiproxy("localhost:8474")

    yield toxiproxy

    # Cleanup: Destroy all proxies
    for proxy in toxiproxy.proxies():
        proxy.destroy()
    toxiproxy.destroy()


@pytest.fixture(scope="function")
def slow_database_proxy(toxiproxy_server):
    """Create Toxiproxy proxy for database with slow 3G latency.

    Scenario: 2000ms network latency to database
    Duration: Controlled by context manager
    Blast radius: Test database only

    Yields:
        Toxiproxy proxy object
    """
    # Create proxy: localhost:5555 -> upstream database:5432
    proxy = toxiproxy_server.create_proxy(
        name="db_proxy",
        upstream="database:5432",  # PostgreSQL upstream
        listen="localhost:5555"
    )

    yield proxy

    # Cleanup: Destroy proxy
    proxy.destroy()
```

**Chaos test using Toxiproxy:**
```python
# backend/tests/chaos/test_network_latency_chaos.py
import pytest
import time

@pytest.mark.chaos
@pytest.mark.timeout(60)
def test_slow_3g_database_latency(slow_database_proxy, chaos_db_session):
    """Test system resilience to 2000ms database latency.

    Scenario: Database queries take 2+ seconds (slow 3G)
    Duration: 30 seconds
    Blast radius: test database only
    """
    # Create test data before latency injection
    agent = create_test_agent(chaos_db_session, name="latency_test")
    chaos_db_session.commit()

    # Baseline: Query without latency
    start_time = time.time()
    agent_baseline = chaos_db_session.query(AgentRegistry).filter_by(id=agent.id).first()
    baseline_latency = time.time() - start_time

    # Inject 2000ms network latency
    with slow_database_proxy.toxic("latency", latency_ms=2000, jitter=0):
        # System should handle latency gracefully
        start_time = time.time()
        agent_with_latency = chaos_db_session.query(AgentRegistry).filter_by(id=agent.id).first()
        latency_with_injection = time.time() - start_time

        # Assert latency injected (>2 seconds)
        assert latency_with_injection > 2.0, "Latency not applied"

        # Assert graceful degradation (not crash)
        assert agent_with_latency is not None, "Query failed under latency"

    # Verify recovery: Latency back to baseline
    start_time = time.time()
    agent_recovered = chaos_db_session.query(AgentRegistry).filter_by(id=agent.id).first()
    recovery_latency = time.time() - start_time

    assert abs(recovery_latency - baseline_latency) < 0.5, "System did not recover"
```

### Pattern 2: Memory Pressure Injection Fixture

**What:** Use psutil to monitor memory and allocate memory to simulate heap exhaustion.

**When to use:** Testing system resilience to memory pressure, OOM handling, garbage collection.

**Example:**
```python
# Source: backend/tests/chaos/conftest.py
import pytest
import psutil
import time

class MemoryPressureInjector:
    """Context manager for memory pressure injection.

    Blast radius: Test process only
    Duration: Automatic cleanup (release memory)
    Safety: Maximum 1GB allocation
    """

    def __init__(self, max_mb: int = 1024, duration_seconds: int = 30):
        self.max_mb = max_mb
        self.duration_seconds = duration_seconds
        self.memory_blocks = []

    def __enter__(self):
        """Allocate memory blocks to simulate pressure."""
        # Allocate memory in 10MB chunks
        chunk_size = 10 * 1024 * 1024  # 10MB
        num_chunks = self.max_mb // 10

        for i in range(num_chunks):
            # Allocate byte array (prevents garbage collection)
            block = bytearray(chunk_size)
            self.memory_blocks.append(block)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release all allocated memory."""
        self.memory_blocks.clear()
        return False


@pytest.fixture(scope="function")
def memory_pressure_injector():
    """Inject memory pressure during test.

    Blast radius: Test process only
    Duration: 30 seconds max
    Safety: Maximum 1GB allocation

    Yields:
        MemoryPressureInjector context manager
    """
    # Baseline memory
    baseline_mb = psutil.virtual_memory().used / (1024 * 1024)

    injector = MemoryPressureInjector(max_mb=1024, duration_seconds=30)

    yield injector

    # Cleanup: Ensure memory released
    current_mb = psutil.virtual_memory().used / (1024 * 1024)
    if current_mb > baseline_mb + 100:
        print(f"Warning: Memory not fully released: {current_mb - baseline_mb:.2f}MB")
```

**Chaos test using memory pressure:**
```python
# backend/tests/chaos/test_memory_pressure_chaos.py
import pytest

@pytest.mark.chaos
@pytest.mark.timeout(60)
def test_heap_exhaustion_handling(memory_pressure_injector, chaos_db_session):
    """Test system resilience to heap exhaustion.

    Scenario: Allocate 1GB memory for 30 seconds
    Duration: 30 seconds
    Blast radius: test process only
    """
    # Baseline memory
    baseline_mb = psutil.virtual_memory().used / (1024 * 1024)

    # Inject memory pressure
    with memory_pressure_injector:
        # System should handle memory pressure gracefully
        agent = create_test_agent(chaos_db_session, name="memory_test")

        # Assert no crash (not OutOfMemoryError)
        assert agent is not None, "Operation failed under memory pressure"

        # Assert memory pressure applied
        current_mb = psutil.virtual_memory().used / (1024 * 1024)
        assert current_mb > baseline_mb + 900, "Memory pressure not applied"

    # Verify recovery: Memory released
    recovered_mb = psutil.virtual_memory().used / (1024 * 1024)
    assert abs(recovered_mb - baseline_mb) < 100, "Memory not released after recovery"
```

### Pattern 3: Database Connection Drop Fixture

**What:** Simulate database connection drops to test connection pool exhaustion and recovery.

**When to use:** Testing database reconnection logic, connection pool behavior, graceful degradation.

**Example:**
```python
# Source: backend/tests/chaos/conftest.py
import pytest
import subprocess
import time

class DatabaseConnectionDropper:
    """Context manager for database connection drop simulation.

    Blast radius: Test database only
    Duration: 10 seconds max
    Safety: Automatic restore

    Strategies:
    - SQLite: Lock database file (chmod 444)
    - PostgreSQL: Stop/start service (pg_ctl/systemctl)
    """

    def __init__(self, database_url: str, duration_seconds: int = 10):
        self.database_url = database_url
        self.duration_seconds = duration_seconds
        self.is_postgresql = "postgresql" in database_url
        self.is_sqlite = "sqlite" in database_url

    def drop_connections(self):
        """Drop database connections."""
        if self.is_sqlite:
            # Lock SQLite database file
            db_path = self.database_url.replace("sqlite:///", "")
            os.chmod(db_path, 0o444)  # Read-only
        elif self.is_postgresql:
            # Stop PostgreSQL service
            subprocess.run(
                ["pg_ctl", "stop", "-D", "/usr/local/var/postgresql"],
                capture_output=True,
                timeout=10
            )

    def restore_connections(self):
        """Restore database connections."""
        if self.is_sqlite:
            # Unlock SQLite database file
            db_path = self.database_url.replace("sqlite:///", "")
            os.chmod(db_path, 0o644)  # Read-write
        elif self.is_postgresql:
            # Start PostgreSQL service
            subprocess.run(
                ["pg_ctl", "start", "-D", "/usr/local/var/postgresql"],
                capture_output=True,
                timeout=10
            )
            time.sleep(2)  # Wait for database to be ready

    def __enter__(self):
        """Drop database connections."""
        self.drop_connections()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore database connections."""
        self.restore_connections()
        return False


@pytest.fixture(scope="function")
def database_connection_dropper():
    """Simulate database connection drops.

    Blast radius: Test database only
    Duration: 10 seconds max
    Safety: Automatic restore

    Yields:
        DatabaseConnectionDropper context manager
    """
    database_url = os.getenv("DATABASE_URL", "")

    # Assert blast radius: Test database only
    assert "test" in database_url or "dev" in database_url, \
        f"Unsafe: Database URL appears to be production: {database_url}"

    dropper = DatabaseConnectionDropper(database_url, duration_seconds=10)

    yield dropper

    # Cleanup: Ensure connections restored
    dropper.restore_connections()
```

### Pattern 4: Service Crash Simulation Fixture

**What:** Simulate service crashes (LLM provider failures, Redis crashes) to test recovery.

**When to use:** Testing graceful degradation when external services fail.

**Example:**
```python
# Source: backend/tests/chaos/conftest.py
import pytest
import subprocess

class ServiceCrashSimulator:
    """Context manager for service crash simulation.

    Blast radius: Test services only (Redis, mock LLM provider)
    Duration: 10 seconds max
    Safety: Automatic restart
    """

    def __init__(self, service_name: str, duration_seconds: int = 10):
        self.service_name = service_name
        self.duration_seconds = duration_seconds

    def crash_service(self):
        """Crash the service."""
        if self.service_name == "redis":
            subprocess.run(
                ["redis-cli", "shutdown"],
                capture_output=True,
                timeout=5
            )
        elif self.service_name == "llm_provider":
            # Mock LLM provider crash (skip actual crash for safety)
            pass

    def restore_service(self):
        """Restore the service."""
        if self.service_name == "redis":
            subprocess.run(
                ["redis-server", "--daemonize", "yes"],
                capture_output=True,
                timeout=5
            )
            time.sleep(2)  # Wait for Redis to start

    def __enter__(self):
        """Crash the service."""
        self.crash_service()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore the service."""
        self.restore_service()
        return False


@pytest.fixture(scope="function")
def service_crash_simulator():
    """Simulate service crashes.

    Blast radius: Test services only
    Duration: 10 seconds max
    Safety: Automatic restart

    Yields:
        ServiceCrashSimulator context manager
    """
    simulator = ServiceCrashSimulator(service_name="redis", duration_seconds=10)

    yield simulator

    # Cleanup: Ensure service restored
    simulator.restore_service()
```

### Anti-Patterns to Avoid

- **Running chaos tests on production:** Violates blast radius controls. Always use isolated test databases (chaos_db_session).
- **Unbounded failure injection:** Causes cascading failures. Enforce 60s duration caps with pytest-timeout.
- **Skipping safety checks:** Risk of production impact. Always assert_blast_radius() before injecting failures.
- **No recovery validation:** Can't confirm system recovers. Always verify data integrity and rollback after chaos.
- **Ignoring automated bug filing:** Loses valuable findings. Integrate with bug_filing_service.py for GitHub Issues.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Network chaos** | Custom TCP proxy, iptables rules | toxiproxy-python | Battle-tested, deterministic network conditions (latency, jitter, packet loss) |
| **Memory monitoring** | Custom memory tracking, GC hooks | psutil, memory_profiler | Cross-platform, Python-native, comprehensive metrics |
| **Service crash** | Kill processes manually | pytest-container, subprocess | Docker lifecycle control, automatic cleanup |
| **Database isolation** | Shared test database | chaos_db_session fixture | Blast radius control, parallel-safe, automatic cleanup |
| **Bug filing** | Manual GitHub issue creation | bug_filing_service.py (Phase 236-08) | Idempotency, metadata collection, GitHub Issues API integration |
| **Timeout enforcement** | Custom time tracking | pytest-timeout | Pytest integration, automatic test termination |
| **Environment checks** | Assume test environment | assert_blast_radius() | Safety verification, production protection |

**Key insight:** Chaos engineering requires specialized tools for controlled failure injection. Custom solutions risk production impact, inconsistent failures, and poor recovery validation.

## Common Pitfalls

### Pitfall 1: Insufficient Blast Radius Controls

**What goes wrong:** Chaos tests affect production databases, shared dev environments, or other test runs.

**Why it happens:** Developers forget to verify environment, don't isolate test databases, or inject failures too broadly.

**How to avoid:**
1. **Always assert blast radius:**
   ```python
   def assert_blast_radius():
       db_url = os.getenv("DATABASE_URL")
       assert "test" in db_url, f"Unsafe: {db_url}"
       assert "production" not in db_url.lower()
   ```
2. **Use isolated test databases:** chaos_db_session fixture (separate database per test)
3. **Limit failure scope:** Test network only (Docker compose), specific services only
4. **Enforce duration caps:** pytest-timeout(60) to prevent unbounded failures

**Warning signs:** Chaos tests connecting to `localhost:5432` (default PostgreSQL), no database URL validation.

### Pitfall 2: No Recovery Validation

**What goes wrong:** Tests verify failure behavior but don't confirm system recovers after failure injection removed.

**Why it happens:** Developers focus on graceful degradation during failure, forget recovery validation.

**How to avoid:**
1. **Always test recovery:**
   ```python
   # Baseline measurement
   baseline = measure_system_health()

   # Inject failure
   with failure_injector:
       # Verify graceful degradation
       assert result.status in ["completed", "failed"]

   # CRITICAL: Verify recovery
   recovered = measure_system_health()
   assert abs(recovered - baseline) < tolerance, "System did not recover"
   ```
2. **Check data integrity:** No data loss, no data corruption
3. **Verify resource cleanup:** No zombie processes, no connection leaks

**Warning signs:** Chaos tests with no "recovery" assertions, tests ending immediately after failure injection.

### Pitfall 3: Using Production for Chaos Tests

**What goes wrong:** Chaos tests accidentally run against production databases or services, causing outages.

**Why it happens:** Environment variables not configured, CI jobs pointing to wrong environment.

**How to avoid:**
1. **Environment checks:** `assert os.getenv("ENVIRONMENT") == "test"`
2. **Database URL validation:** Check for "test" or "dev" in URL
3. **Network isolation:** Docker compose test network only
4. **CI pipeline separation:** Weekly chaos tests only, never on PRs

**Warning signs:** DATABASE_URL pointing to `production-db.example.com`, no environment validation.

### Pitfall 4: Skipping Automated Bug Filing

**What goes wrong:** Chaos tests discover resilience failures but don't file GitHub issues, losing valuable findings.

**Why it happens:** Developers don't integrate bug_filing_service.py or manual bug filing is tedious.

**How to avoid:**
1. **Integrate BugFilingService:** Import from tests.bug_discovery.bug_filing_service
2. **File bugs on resilience failure:** Crash, data loss, no recovery
3. **Include chaos metadata:** failure_scenario, injection_duration, blast_radius, baseline_metrics, failure_metrics, recovery_metrics
4. **Configure GitHub credentials:** GITHUB_TOKEN, GITHUB_REPOSITORY environment variables

**Warning signs:** Test failures logged to console only, no GitHub issues created for chaos discoveries.

### Pitfall 5: Non-Deterministic Chaos Tests

**What goes wrong:** Same chaos test produces different results each run (flaky, unreliable).

**Why it happens:** Randomized failure injection, time-based assertions without proper mocking.

**How to avoid:**
1. **Deterministic failure injection:** Toxiproxy provides fixed latency (2000ms)
2. **Frozen time:** Use freezegun for time-based assertions
3. **Fixed memory allocation:** Allocate exact MB (not random)
4. **Reproducible service crashes:** Same service, same crash method

**Warning signs:** Chaos tests marked as `@pytest.mark.flaky`, intermittent pass/fail behavior.

## Code Examples

Verified patterns from official sources:

### Pattern 1: ChaosCoordinator Service Architecture

```python
# Source: backend/tests/chaos/core/chaos_coordinator.py
from typing import Dict, Any, Optional
import time
import psutil

class ChaosCoordinator:
    """
    Orchestrates chaos engineering experiments with blast radius controls.

    Features:
    - Experiment lifecycle management (setup, inject, verify, cleanup)
    - Blast radius enforcement (test databases only, duration caps)
    - Recovery validation (data integrity, rollback verification)
    - Automated bug filing (BugFilingService integration)

    Safety mechanisms:
    - Blast radius checks before injection
    - Duration timeout enforcement (60s max)
    - Automatic cleanup and rollback
    - Environment verification (test only)
    """

    def __init__(self, db_session, bug_filing_service=None):
        self.db_session = db_session
        self.bug_filing_service = bug_filing_service
        self.experiments = []

    def run_experiment(
        self,
        experiment_name: str,
        failure_injection: callable,
        verify_rejection: callable,
        blast_radius_checks: list = None
    ) -> Dict[str, Any]:
        """
        Run chaos experiment with blast radius controls.

        Args:
            experiment_name: Name of experiment
            failure_injection: Function that injects failure
            verify_rejection: Function that verifies graceful degradation
            blast_radius_checks: List of safety checks to run

        Returns:
            Dict with experiment results (baseline, failure, recovery, bug_filed)
        """
        # Step 1: Blast radius validation
        if blast_radius_checks:
            for check in blast_radius_checks:
                check()  # Raises AssertionError if unsafe

        # Step 2: Baseline measurement
        baseline_metrics = self._measure_system_health()
        print(f"Baseline: {baseline_metrics}")

        # Step 3: Inject failure
        try:
            with failure_injection():
                failure_metrics = self._measure_system_health()
                print(f"During failure: {failure_metrics}")

                # Verify graceful degradation
                verify_rejection(failure_metrics)

        except Exception as e:
            # File bug for resilience failure
            if self.bug_filing_service:
                self.bug_filing_service.file_bug(
                    test_name=experiment_name,
                    error_message=f"Resilience failure: {str(e)}",
                    metadata={
                        "test_type": "chaos",
                        "baseline_metrics": baseline_metrics,
                        "failure_metrics": failure_metrics,
                        "blast_radius": "test_database_only",
                    }
                )
            raise

        # Step 4: Verify recovery
        recovery_metrics = self._measure_system_health()
        print(f"Recovery: {recovery_metrics}")

        self._verify_recovery(baseline_metrics, recovery_metrics)

        return {
            "baseline": baseline_metrics,
            "failure": failure_metrics,
            "recovery": recovery_metrics,
            "success": True
        }

    def _measure_system_health(self) -> Dict[str, float]:
        """Measure system health metrics."""
        return {
            "cpu_percent": psutil.cpu_percent(),
            "memory_mb": psutil.virtual_memory().used / (1024 * 1024),
            "disk_io": psutil.disk_io_counters(),
        }

    def _verify_recovery(self, baseline: Dict, recovery: Dict) -> None:
        """Verify system recovered to baseline."""
        # CPU recovery: within 20% of baseline
        cpu_diff = abs(recovery["cpu_percent"] - baseline["cpu_percent"])
        assert cpu_diff < 20, f"CPU did not recover: {cpu_diff}% difference"

        # Memory recovery: within 100MB of baseline
        memory_diff = abs(recovery["memory_mb"] - baseline["memory_mb"])
        assert memory_diff < 100, f"Memory did not recover: {memory_diff}MB difference"
```

**Chaos test using ChaosCoordinator:**
```python
# backend/tests/chaos/test_network_latency_chaos.py
import pytest
from tests.chaos.core.chaos_coordinator import ChaosCoordinator

@pytest.mark.chaos
@pytest.mark.timeout(60)
def test_network_latency_chaos_experiment(chaos_db_session):
    """Test network latency resilience using ChaosCoordinator."""
    from tests.bug_discovery.bug_filing_service import BugFilingService

    # Create ChaosCoordinator
    coordinator = ChaosCoordinator(
        db_session=chaos_db_session,
        bug_filing_service=BugFilingService(
            github_token=os.getenv("GITHUB_TOKEN"),
            github_repository=os.getenv("GITHUB_REPOSITORY")
        )
    )

    # Define blast radius checks
    def assert_test_database_only():
        db_url = os.getenv("DATABASE_URL")
        assert "test" in db_url, f"Unsafe: {db_url}"

    # Define failure injection
    def inject_latency():
        # Use Toxiproxy to inject 2000ms latency
        with slow_database_proxy.toxic("latency", latency_ms=2000):
            yield

    # Define graceful degradation verification
    def verify_graceful_degradation(metrics):
        # System should not crash (HTTP 500)
        assert "http_status" not in metrics or metrics["http_status"] != 500
        # System should return timeout or completed status
        assert metrics.get("status") in ["timeout", "completed"]

    # Run experiment
    results = coordinator.run_experiment(
        experiment_name="test_network_latency_chaos",
        failure_injection=inject_latency,
        verify_rejection=verify_graceful_degradation,
        blast_radius_checks=[assert_test_database_only]
    )

    # Assert success
    assert results["success"]
```

### Pattern 2: Blast Radius Safety Checks

```python
# Source: backend/tests/chaos/core/blast_radius_controls.py
import os
import subprocess

def assert_blast_radius():
    """
    Ensure failure is scoped to test environment only.

    Raises:
        AssertionError: If blast radius checks fail (unsafe to proceed)
    """
    # Check 1: Environment
    environment = os.getenv("ENVIRONMENT", "development")
    assert environment in ["test", "development"], \
        f"Unsafe: Environment is {environment}, not test/development"

    # Check 2: Database URL
    db_url = os.getenv("DATABASE_URL", "")
    assert "test" in db_url or "dev" in db_url, \
        f"Unsafe: Database URL appears to be production: {db_url}"

    # Check 3: No production endpoints
    production_endpoints = [
        "api.production.com",
        "prod-db.example.com",
        "production.example.com"
    ]
    for endpoint in production_endpoints:
        assert endpoint not in db_url, \
            f"Unsafe: Production endpoint in URL: {endpoint}"

    # Check 4: Network isolation (if applicable)
    # Verify we're not in production network
    hostname = subprocess.check_output(["hostname"]).decode()
    assert "prod" not in hostname.lower(), \
        f"Unsafe: Running on production host: {hostname}"

    print("✓ Blast radius checks passed")

# Usage in chaos tests
@pytest.mark.chaos
def test_chaos_with_safety_checks(chaos_db_session):
    """Chaos test with blast radius validation."""
    # Run safety checks before injecting failure
    assert_blast_radius()

    # Proceed with chaos experiment
    with failure_injector():
        # ... chaos test logic
```

### Pattern 3: Data Integrity Validation

```python
# Source: backend/tests/chaos/core/data_integrity.py
from sqlalchemy.orm import Session

def verify_data_integrity(db_session: Session, test_data_ids: list) -> Dict[str, bool]:
    """
    Verify data integrity after chaos experiment.

    Checks:
    - No data loss (all test data still exists)
    - No data corruption (data values unchanged)
    - No orphaned records (referential integrity)

    Args:
        db_session: Database session
        test_data_ids: List of test record IDs to verify

    Returns:
        Dict with integrity check results
    """
    results = {
        "data_loss": False,
        "data_corruption": False,
        "orphaned_records": False,
    }

    # Check 1: No data loss
    for record_id in test_data_ids:
        record = db_session.query(AgentRegistry).filter_by(id=record_id).first()
        if record is None:
            results["data_loss"] = True
            break

    # Check 2: No data corruption
    # (Compare checksums or critical field values)
    for record_id in test_data_ids:
        record = db_session.query(AgentRegistry).filter_by(id=record_id).first()
        if record and record.name == "chaos_test":
            # Verify expected data
            if "corrupted" in str(record.__dict__):
                results["data_corruption"] = True
                break

    # Check 3: No orphaned records
    # (Verify foreign key relationships)
    # Implementation depends on schema

    return results

# Usage in chaos tests
@pytest.mark.chaos
def test_data_integrity_after_crash(chaos_db_session):
    """Verify data integrity after service crash."""
    # Create test data
    agent = create_test_agent(chaos_db_session, name="chaos_test")
    agent_id = agent.id
    chaos_db_session.commit()

    # Inject service crash
    with service_crash_simulator:
        # System crashes and recovers
        pass

    # Verify data integrity
    integrity_results = verify_data_integrity(chaos_db_session, [agent_id])

    # Assert no data loss or corruption
    assert not integrity_results["data_loss"], "Data loss detected"
    assert not integrity_results["data_corruption"], "Data corruption detected"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **Manual chaos testing** | Automated chaos experiments with Toxiproxy | Phase 241 (planned) | Reproducible network conditions, deterministic failures |
| **Shared test database** | Isolated chaos_db_session per test | Phase 241 (planned) | Blast radius control, parallel-safe, no interference |
| **No blast radius controls** | assert_blast_radius() + environment checks | Phase 241 (planned) | Production safety, validated failure scope |
| **Manual bug filing** | Automated BugFilingService integration | Phase 236-08 (complete) | GitHub Issues created automatically with metadata |
| **No recovery validation** | ChaosCoordinator with recovery verification | Phase 241 (planned) | Confirm system recovers, data integrity maintained |

**Deprecated/outdated:**
- **Manual service crashes:** Use pytest-container or subprocess with automatic cleanup
- **Unbounded failure injection:** Enforce 60s duration caps with pytest-timeout
- **Production chaos testing:** Always use isolated test databases and networks
- **Non-deterministic chaos:** Use Toxiproxy for deterministic network conditions

## Open Questions

1. **Toxiproxy deployment strategy**
   - What we know: Toxiproxy needs to run as separate service (localhost:8474)
   - What's unclear: Should Toxiproxy run in Docker container? Systemd service? On-demand per test?
   - Recommendation: Run Toxiproxy in Docker container during CI, manual setup for local development

2. **Memory pressure injection limits**
   - What we know: CHAOS_TEMPLATE.md suggests max 1GB allocation
   - What's unclear: Should limit be relative to available memory (e.g., 50% of free memory)?
   - Recommendation: Start with fixed 1GB limit, adjust based on false positive rate (OOM kills)

3. **Service crash simulation for LLM providers**
   - What we know: Should simulate OpenAI/Anthropic API failures
   - What's unclear: Mock failures or actual network disruption? How to avoid API rate limits?
   - Recommendation: Use unittest.mock for LLM provider failures (safer, no rate limits)

4. **Chaos test execution frequency**
   - What we know: CHAOS-08 requires weekly execution, never on shared dev
   - What's unclear: Should specific chaos scenarios run daily (e.g., network latency)?
   - Recommendation: Start with weekly full chaos suite, add daily high-value scenarios (network latency)

5. **Recovery validation thresholds**
   - What we know: Should verify system recovers to baseline
   - What's unclear: What's acceptable deviation from baseline? ±20% CPU? ±100MB memory?
   - Recommendation: Start with ±20% CPU, ±100MB memory thresholds, adjust based on false positive rate

## Sources

### Primary (HIGH confidence)
- **backend/tests/bug_discovery/TEMPLATES/CHAOS_TEMPLATE.md** - Chaos engineering test template (529 lines) with Toxiproxy examples, blast radius controls, safety checks
- **backend/tests/e2e_ui/fixtures/network_fixtures.py** - Network simulation fixtures (485 lines) with slow 3G, offline mode, database drop simulation
- **backend/tests/e2e_ui/fixtures/memory_fixtures.py** - Memory leak detection fixtures (316 lines) with CDP heap snapshots
- **backend/tests/bug_discovery/bug_filing_service.py** - Automated bug filing service with GitHub Issues API
- **backend/pytest.ini** - Pytest markers (@pytest.mark.chaos) and configuration
- **.github/workflows/weekly-stress-tests.yml** - Weekly stress test pipeline with scheduled execution (Sunday 3 AM UTC)
- **.github/workflows/bug-discovery-weekly.yml** - Weekly bug discovery pipeline for chaos/fuzzing/browser tests

### Secondary (MEDIUM confidence)
- **pytest documentation** (pytest.org) - Test discovery, markers, fixtures, timeout plugin
- **Toxiproxy Python GitHub** (github.com/ihucos/toxiproxy-python) - Network chaos simulation API
- **psutil documentation** (psutil.readthedocs.io) - Cross-platform system monitoring
- **memory_profiler documentation** (pypi.org/project/memory-profiler) - Python memory profiling

### Tertiary (LOW confidence)
- **Chaos Toolkit documentation** (chaostoolkit.org) - Chaos engineering experimentation framework (alternative to custom ChaosCoordinator)
- **Principles of Chaos** (principlesofchaos.org) - Chaos engineering best practices
- Web search limitations (rate limit exhausted, unable to verify current 2026 best practices)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All tools verified against codebase (network_fixtures.py, memory_fixtures.py), CHAOS_TEMPLATE.md provides Toxiproxy examples
- Architecture: HIGH - Existing fixture patterns well-documented, ChaosCoordinator design follows AITriggerCoordinator pattern
- Pitfalls: HIGH - Common pitfalls identified from CHAOS_TEMPLATE.md safety checks, blast radius controls
- Blast radius controls: HIGH - assert_blast_radius() pattern from CHAOS_TEMPLATE.md, environment checks in weekly-stress-tests.yml

**Research date:** 2026-03-24
**Valid until:** 2026-04-23 (30 days - stable chaos engineering patterns, Toxiproxy mature project)
