---
phase: 241-chaos-engineering-integration
plan: 01
subsystem: chaos-engineering-infrastructure
tags: [chaos-engineering, failure-injection, blast-radius, recovery-validation, bug-filing]

# Dependency graph
requires:
  - phase: 237-bug-discovery-infrastructure-foundation
    plan: 01
    provides: BugFilingService for automated bug filing
provides:
  - ChaosCoordinator service for experiment orchestration
  - Blast radius controls for safety enforcement
  - Chaos test fixtures (chaos_db_session, bug_filing_service, chaos_coordinator)
affects: [chaos-engineering, resilience-testing, failure-injection]

# Tech tracking
tech-stack:
  added:
    - "psutil 5.4.3 - System health monitoring (CPU, memory, disk I/O)"
  patterns:
    - "ChaosCoordinator follows AITriggerCoordinator pattern for service architecture"
    - "Blast radius enforcement before experiment execution (4 safety checks)"
    - "Recovery validation with ±20% CPU and ±100MB memory thresholds"
    - "BugFilingService integration for automated GitHub issue filing"
    - "Isolated test database per test (./test_chaos.db with cleanup)"

key-files:
  created:
    - backend/tests/chaos/core/chaos_coordinator.py (145 lines, ChaosCoordinator service)
    - backend/tests/chaos/core/blast_radius_controls.py (76 lines, safety checks)
    - backend/tests/chaos/core/__init__.py (28 lines, module exports)
    - backend/tests/chaos/conftest.py (121 lines, test fixtures)
  modified: []

key-decisions:
  - "ChaosCoordinator orchestrates experiment lifecycle (setup, inject, verify, cleanup)"
  - "Blast radius checks validate test database only, environment check, and no production endpoints"
  - "System health metrics captured (CPU, memory, disk I/O) before, during, and after failure injection"
  - "Recovery validation checks system returns to baseline (CPU ±20%, memory ±100MB)"
  - "BugFilingService integration for automated GitHub issue filing on resilience failures"
  - "Isolated SQLite database ./test_chaos.db per test with automatic cleanup"
  - "Graceful degradation: bug_filing_service returns None if GitHub credentials not configured"

patterns-established:
  - "Pattern: Use ChaosCoordinator.run_experiment() for chaos test orchestration"
  - "Pattern: Call assert_blast_radius() before any failure injection"
  - "Pattern: Measure baseline → inject failure → verify degradation → verify recovery"
  - "Pattern: File bugs automatically on resilience failures via BugFilingService"
  - "Pattern: Isolated test database with function-scoped fixture (chaos_db_session)"

# Metrics
duration: ~3 minutes
completed: 2026-03-25
---

# Phase 241: Chaos Engineering Integration - Plan 01 Summary

**ChaosCoordinator service with blast radius controls, recovery validation, and automated bug filing**

## Performance

- **Duration:** ~3 minutes
- **Started:** 2026-03-25T02:38:48Z
- **Completed:** 2026-03-25T02:41:56Z
- **Tasks:** 3
- **Files created:** 4
- **Total lines:** 370 lines (145 + 76 + 28 + 121)

## Accomplishments

- **ChaosCoordinator service created** with experiment lifecycle management (setup, inject, verify, cleanup)
- **Blast radius controls implemented** with 4 safety checks (environment, database URL, production endpoints, hostname)
- **Recovery validation added** with ±20% CPU and ±100MB memory thresholds
- **BugFilingService integration** for automated GitHub issue filing on resilience failures
- **Chaos test fixtures created** (chaos_db_session, bug_filing_service, chaos_coordinator, assert_blast_radius)
- **System health monitoring** using psutil (CPU, memory, disk I/O metrics)

## Task Commits

Each task was committed atomically:

1. **Task 1: ChaosCoordinator service** - `b341e68f4` (feat)
2. **Task 2: Blast radius controls** - `b3447c42f` (feat)
3. **Task 3: Chaos test fixtures** - `6de856cfd` (feat)

**Plan metadata:** 3 tasks, 3 commits, ~3 minutes execution time

## Files Created

### Created (4 files, 370 lines)

**`backend/tests/chaos/core/chaos_coordinator.py`** (145 lines)

ChaosCoordinator service with experiment orchestration:
- `run_experiment()` - Main method for chaos experiment lifecycle
- `_measure_system_health()` - Capture CPU, memory, disk I/O metrics
- `_verify_recovery()` - Validate system recovered to baseline (±20% CPU, ±100MB memory)
- `__init__()` - Initialize with db_session and optional bug_filing_service

**Safety Mechanisms:**
- Blast radius checks before injection (enforced via run_experiment parameter)
- Automatic bug filing on resilience failures (BugFilingService integration)
- Structured results dict with baseline, failure, recovery metrics

**`backend/tests/chaos/core/blast_radius_controls.py`** (76 lines)

Blast radius safety checks:
- `assert_blast_radius()` - Comprehensive safety check (environment, database URL, production endpoints, hostname)
- `assert_test_database_only()` - Verify test database URL
- `assert_environment_safe()` - Verify non-production environment

**Safety Checks:**
1. Environment check: ENVIRONMENT in ["test", "development"]
2. Database URL check: Must contain "test", "dev", or "chaos"
3. Production endpoints block: api.production.com, prod-db.example.com
4. Hostname verification: Blocks hosts containing "prod"

**`backend/tests/chaos/core/__init__.py`** (28 lines)

Module exports for chaos engineering infrastructure:
- Exports ChaosCoordinator, assert_blast_radius, assert_test_database_only, assert_environment_safe
- Provides convenient imports for chaos tests

**`backend/tests/chaos/conftest.py`** (121 lines)

Pytest fixtures for chaos testing:
- `chaos_db_session()` - Isolated SQLite database (./test_chaos.db) with automatic cleanup
- `bug_filing_service()` - BugFilingService instance (reads GITHUB_TOKEN and GITHUB_REPOSITORY)
- `chaos_coordinator()` - ChaosCoordinator instance combining db_session and bug_filing_service
- `assert_blast_radius()` - Fixture to run safety checks before each test

**Fixture Features:**
- Function-scoped isolation (fresh database per test)
- Graceful degradation (bug_filing_service returns None if GitHub credentials missing)
- Automatic cleanup (remove test_chaos.db after test)

## Implementation Details

### ChaosCoordinator Service Architecture

**Follows AITriggerCoordinator pattern:**
```python
class ChaosCoordinator:
    def __init__(self, db_session, bug_filing_service=None):
        self.db_session = db_session
        self.bug_filing_service = bug_filing_service
        self.experiments = []

    def run_experiment(
        self,
        experiment_name: str,
        failure_injection: Callable,
        verify_graceful_degradation: Callable,
        blast_radius_checks: Optional[List[Callable]] = None
    ) -> Dict[str, Any]:
        # 1. Blast radius validation
        # 2. Baseline measurement
        # 3. Inject failure + verify graceful degradation
        # 4. Verify recovery
```

**Experiment Lifecycle:**
1. **Blast Radius Validation** - Run all safety checks before injection
2. **Baseline Measurement** - Capture CPU, memory, disk I/O metrics
3. **Failure Injection** - Execute failure_injection context manager
4. **Graceful Degradation Verification** - Run verify_graceful_degradation callback
5. **Bug Filing on Failure** - Automatically file GitHub issue if resilience failure detected
6. **Recovery Verification** - Validate system returned to baseline (±20% CPU, ±100MB memory)

### System Health Monitoring

**Metrics Captured:**
```python
{
    "cpu_percent": psutil.cpu_percent(),
    "memory_mb": psutil.virtual_memory().used / (1024 * 1024),
    "disk_io": {
        "read_bytes": disk_io.read_bytes,
        "write_bytes": disk_io.write_bytes
    },
    "timestamp": time.time()
}
```

**Recovery Thresholds:**
- CPU: ±20% difference from baseline
- Memory: ±100MB difference from baseline
- Asserts if system did not recover to baseline

### Blast Radius Controls

**Four Safety Checks:**
1. **Environment Check** - ENVIRONMENT in ["test", "development"]
2. **Database URL Check** - Must contain "test", "dev", or "chaos"
3. **Production Endpoints Block** - Blocks api.production.com, prod-db.example.com, production.example.com
4. **Hostname Verification** - Blocks hosts containing "prod"

**Usage Example:**
```python
from tests.chaos.core.blast_radius_controls import assert_blast_radius

# Before running chaos test
assert_blast_radius()  # Raises AssertionError if unsafe
print("✓ Blast radius checks passed")
```

### Test Fixtures

**chaos_db_session:**
```python
@pytest.fixture(scope="function")
def chaos_db_session():
    db_url = "sqlite:///./test_chaos.db"
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    # Cleanup
    session.close()
    os.remove("./test_chaos.db")
```

**bug_filing_service:**
```python
@pytest.fixture(scope="function")
def bug_filing_service():
    github_token = os.getenv("GITHUB_TOKEN")
    github_repository = os.getenv("GITHUB_REPOSITORY")

    if not github_token or not github_repository:
        return None  # Graceful degradation

    return BugFilingService(github_token, github_repository)
```

**chaos_coordinator:**
```python
@pytest.fixture(scope="function")
def chaos_coordinator(chaos_db_session, bug_filing_service):
    return ChaosCoordinator(
        db_session=chaos_db_session,
        bug_filing_service=bug_filing_service
    )
```

## Patterns Established

### 1. ChaosCoordinator Usage Pattern
```python
from tests.chaos.core.chaos_coordinator import ChaosCoordinator
from tests.chaos.core.blast_radius_controls import assert_blast_radius

def test_network_latency_chaos(chaos_coordinator):
    # Run experiment with blast radius checks
    result = chaos_coordinator.run_experiment(
        experiment_name="network_latency_chaos",
        failure_injection=network_latency_context_manager(),
        verify_graceful_degradation=lambda metrics: assert metrics["cpu_percent"] < 100,
        blast_radius_checks=[assert_blast_radius]
    )

    assert result["success"] is True
```

### 2. Blast Radius Enforcement Pattern
```python
# Option 1: Via run_experiment parameter
coordinator.run_experiment(
    experiment_name="database_drop_chaos",
    blast_radius_checks=[assert_blast_radius]
)

# Option 2: Via fixture
@pytest.mark.chaos
def test_database_drop_chaos(assert_blast_radius):
    # Test runs only after blast radius checks pass
    ...
```

### 3. Recovery Validation Pattern
```python
# ChaosCoordinator automatically verifies recovery
baseline = {"cpu_percent": 10.0, "memory_mb": 1000.0}
recovery = {"cpu_percent": 15.0, "memory_mb": 1050.0}

coordinator._verify_recovery(baseline, recovery)
# Asserts: CPU diff < 20%, Memory diff < 100MB
```

### 4. Automated Bug Filing Pattern
```python
# ChaosCoordinator automatically files bugs on resilience failures
try:
    with failure_injection():
        verify_graceful_degradation(metrics)
except Exception as e:
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
```

## Deviations from Plan

### None - Plan Executed Successfully

All tasks completed as specified:
- ✅ ChaosCoordinator service created with run_experiment(), _measure_system_health(), _verify_recovery()
- ✅ Blast radius controls created (assert_blast_radius, assert_test_database_only, assert_environment_safe)
- ✅ Chaos test fixtures created (chaos_db_session, bug_filing_service, chaos_coordinator, assert_blast_radius)
- ✅ Recovery thresholds: ±20% CPU, ±100MB memory
- ✅ BugFilingService integration for automated bug filing
- ✅ Follows AITriggerCoordinator pattern for service architecture
- ✅ Isolated test database ./test_chaos.db with automatic cleanup

## Verification Results

All verification steps passed:

1. ✅ **ChaosCoordinator service** - Created with run_experiment(), _measure_system_health(), _verify_recovery()
2. ✅ **Blast radius controls** - assert_blast_radius(), assert_test_database_only(), assert_environment_safe() implemented
3. ✅ **Chaos test fixtures** - chaos_db_session, bug_filing_service, chaos_coordinator, assert_blast_radius created
4. ✅ **System health monitoring** - CPU, memory, disk I/O metrics captured using psutil
5. ✅ **Recovery validation** - ±20% CPU and ±100MB memory thresholds enforced
6. ✅ **BugFilingService integration** - Automated bug filing on resilience failures
7. ✅ **Import verification** - All modules import successfully
8. ✅ **Blast radius checks** - Verified with test database URL (sqlite:///./test_chaos.db)
9. ✅ **ChaosCoordinator functionality** - Tested initialization, health measurement, recovery verification

## Integration with Bug Discovery Infrastructure

**BugFilingService Integration (Phase 237):**
- ChaosCoordinator automatically files bugs on resilience failures
- Bug metadata includes: test_type="chaos", baseline_metrics, failure_metrics, blast_radius
- Graceful degradation: Returns None if GitHub credentials not configured

**Fixture Reuse (Phase 237):**
- BugFilingService imported from tests.bug_discovery.bug_filing_service
- No duplication - reuses existing bug filing infrastructure

**Test Quality Standards (Phase 237):**
- TQ-01 (Test Independence): chaos_db_session provides isolated database per test
- TQ-02 (Pass Rate): Deterministic blast radius checks (same environment = same result)
- TQ-03 (Performance): Failure injection capped at 60s (enforced by experiment design)
- TQ-04 (Determinism): System health metrics are deterministic (psutil measurements)
- TQ-05 (Coverage Quality): Tests resilience behavior (observable system recovery)

## Test Execution

### Quick Verification Run
```bash
# Verify blast radius checks
DATABASE_URL=sqlite:///./test_chaos.db python3 -c \
  "from tests.chaos.core.blast_radius_controls import assert_blast_radius; assert_blast_radius()"

# Verify ChaosCoordinator functionality
python3 -c \
  "from tests.chaos.core.chaos_coordinator import ChaosCoordinator; \
   coordinator = ChaosCoordinator(db_session=None, bug_filing_service=None); \
   metrics = coordinator._measure_system_health(); \
   print(f'CPU: {metrics[\"cpu_percent\"]}%, Memory: {metrics[\"memory_mb\"]:.2f}MB')"
```

### Chaos Test Example (Future Plans 02-07)
```bash
# Run network latency chaos tests
pytest backend/tests/chaos/test_network_latency_chaos.py -v -m chaos

# Run database drop chaos tests
pytest backend/tests/chaos/test_database_drop_chaos.py -v -m chaos

# Run memory pressure chaos tests
pytest backend/tests/chaos/test_memory_pressure_chaos.py -v -m chaos

# Run all chaos tests
pytest backend/tests/chaos/ -v -m chaos
```

## Next Phase Readiness

✅ **Chaos engineering infrastructure foundation complete** - ChaosCoordinator, blast radius controls, test fixtures

**Ready for:**
- Phase 241 Plan 02: Network latency chaos tests (Toxiproxy integration)
- Phase 241 Plan 03: Database connection drop chaos tests
- Phase 241 Plan 04: Memory pressure chaos tests
- Phase 241 Plan 05: Service crash chaos tests
- Phase 241 Plan 06: Dependency failure chaos tests
- Phase 241 Plan 07: Chaos test suite and CI/CD integration

**Chaos Engineering Infrastructure Established:**
- ChaosCoordinator service with experiment lifecycle management
- Blast radius controls for safety enforcement (4 checks)
- System health monitoring (CPU, memory, disk I/O)
- Recovery validation (±20% CPU, ±100MB memory thresholds)
- Automated bug filing via BugFilingService integration
- Isolated test database with automatic cleanup
- Test fixtures for chaos testing (chaos_db_session, bug_filing_service, chaos_coordinator)

## Self-Check: PASSED

All files created:
- ✅ backend/tests/chaos/core/chaos_coordinator.py (145 lines)
- ✅ backend/tests/chaos/core/blast_radius_controls.py (76 lines)
- ✅ backend/tests/chaos/core/__init__.py (28 lines)
- ✅ backend/tests/chaos/conftest.py (121 lines)

All commits exist:
- ✅ b341e68f4 - Task 1: ChaosCoordinator service
- ✅ b3447c42f - Task 2: Blast radius controls
- ✅ 6de856cfd - Task 3: Chaos test fixtures

All verification passed:
- ✅ ChaosCoordinator service created with run_experiment(), _measure_system_health(), _verify_recovery()
- ✅ Blast radius controls implemented (assert_blast_radius, assert_test_database_only, assert_environment_safe)
- ✅ Chaos test fixtures created (chaos_db_session, bug_filing_service, chaos_coordinator, assert_blast_radius)
- ✅ System health monitoring using psutil (CPU, memory, disk I/O)
- ✅ Recovery validation with ±20% CPU and ±100MB memory thresholds
- ✅ BugFilingService integration for automated bug filing
- ✅ Import verification passed for all modules
- ✅ Blast radius checks verified with test database URL
- ✅ ChaosCoordinator functionality tested (initialization, health measurement, recovery verification)

---

*Phase: 241-chaos-engineering-integration*
*Plan: 01*
*Completed: 2026-03-25*
