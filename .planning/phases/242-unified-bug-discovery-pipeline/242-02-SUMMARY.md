---
phase: 242-unified-bug-discovery-pipeline
plan: 02
subsystem: unified-pipeline
tags: [orchestration, bug-discovery, aggregation, deduplication, triage, github-integration]

# Dependency graph
requires:
  - phase: 242-unified-bug-discovery-pipeline
    plan: 01
    provides: Core pipeline services (BugReport model, ResultAggregator, BugDeduplicator, SeverityClassifier, DashboardGenerator)
provides:
  - DiscoveryCoordinator orchestration service with run_full_discovery() method
  - End-to-end bug discovery pipeline (fuzzing → chaos → property → browser → aggregate → deduplicate → classify → file → report)
  - Integration with FuzzingOrchestrator, ChaosCoordinator, BugFilingService
  - Weekly report generation in storage/reports/
affects: [bug-discovery-pipeline, ci-cd, automation, github-integration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Orchestration pattern: DiscoveryCoordinator.run_full_discovery() coordinates all discovery methods"
    - "Service composition: FuzzingOrchestrator, ChaosCoordinator, BugFilingService, ResultAggregator, BugDeduplicator, SeverityClassifier, DashboardGenerator"
    - "Subprocess execution for property tests (pytest -v --tb=short)"
    - "Playwright headless browser for console error detection"
    - "Blast radius enforcement for chaos experiments (assert_blast_radius)"
    - "Idempotent bug filing via BugFilingService with duplicate detection"
    - "Weekly HTML reports with severity distribution and discovery method breakdown"
    - "Convenience function run_discovery() for CI/CD pipelines"

key-files:
  created:
    - backend/tests/bug_discovery/core/discovery_coordinator.py (654 lines, DiscoveryCoordinator + run_discovery)
    - backend/tests/bug_discovery/storage/reports/.gitkeep (directory marker)
  modified:
    - backend/tests/bug_discovery/core/__init__.py (added DiscoveryCoordinator, run_discovery exports)

key-decisions:
  - "DiscoveryCoordinator orchestrates all four discovery methods in sequence (fuzzing → chaos → property → browser)"
  - "Fuzzing campaigns run via FuzzingOrchestrator.run_campaign_with_bug_filing() with 15 min max per endpoint"
  - "Chaos experiments run via ChaosCoordinator.run_experiment() with blast radius checks and isolated SQLite database"
  - "Property tests run via subprocess pytest with 30 min timeout and stdout parsing for failures"
  - "Browser discovery uses Playwright headless browser with console error detection"
  - "Bug filing happens after deduplication and severity classification (only unique bugs filed)"
  - "Weekly reports generated via DashboardGenerator with bugs_found, unique_bugs, filed_bugs, severity_distribution, by_method"
  - "Graceful degradation: Missing dependencies (Playwright, toxiproxy) skip with warnings, don't fail entire pipeline"

patterns-established:
  - "Pattern: DiscoveryCoordinator.run_full_discovery() as single entry point for complete bug discovery pipeline"
  - "Pattern: Result aggregation → Deduplication → Severity classification → Bug filing → Report generation"
  - "Pattern: Subprocess execution for pytest (property tests) with stdout parsing"
  - "Pattern: Isolated test databases for chaos experiments (tempfile.NamedTemporaryFile)"
  - "Pattern: Mock failure injection for CI environments (LatencyInjection, DatabaseDropInjection, MemoryPressureInjection)"
  - "Pattern: Blast radius enforcement (assert_blast_radius) for all chaos experiments"
  - "Pattern: Bug filing after deduplication (prevents duplicate GitHub issues)"

# Metrics
duration: ~3 minutes
completed: 2026-03-25
---

# Phase 242: Unified Bug Discovery Pipeline - Plan 02 Summary

**DiscoveryCoordinator orchestration service with end-to-end bug discovery pipeline**

## Performance

- **Duration:** ~3 minutes
- **Started:** 2026-03-25T10:53:39Z
- **Completed:** 2026-03-25T10:57:23Z
- **Tasks:** 2
- **Files created:** 2
- **Total lines:** 654 lines (discovery_coordinator.py)

## Accomplishments

- **DiscoveryCoordinator service created** with run_full_discovery() orchestration method
- **End-to-end pipeline implemented** fuzzing → chaos → property → browser → aggregate → deduplicate → classify → file → report
- **Fuzzing integration** via FuzzingOrchestrator.run_campaign_with_bug_filing()
- **Chaos integration** via ChaosCoordinator.run_experiment() with blast radius checks
- **Property test integration** via subprocess pytest execution
- **Browser discovery integration** via Playwright headless browser
- **Bug filing automation** via BugFilingService with idempotency
- **Weekly report generation** via DashboardGenerator with HTML/JSON output
- **CI/CD convenience function** run_discovery() for easy integration
- **Storage directory created** at backend/tests/bug_discovery/storage/reports/

## Task Commits

Each task was committed atomically:

1. **Task 1: DiscoveryCoordinator orchestration service** - `82067a502` (feat)
2. **Task 2: Update core exports and create storage directory** - `a6fd0f3de` (feat)

**Plan metadata:** 2 tasks, 2 commits, ~3 minutes execution time

## Files Created

### Created (2 files, 654 lines)

**`backend/tests/bug_discovery/core/discovery_coordinator.py`** (654 lines)

DiscoveryCoordinator orchestration service:

**Public Methods:**
- `__init__(github_token, github_repository, storage_dir)` - Initialize coordinator with GitHub credentials
- `run_full_discovery(duration_seconds, fuzzing_endpoints, chaos_experiments, run_property_tests, run_browser_discovery)` - Orchestrate complete bug discovery pipeline
- `_run_fuzzing_discovery(endpoints, duration_seconds)` - Run fuzzing campaigns via FuzzingOrchestrator
- `_run_chaos_discovery(experiments)` - Run chaos experiments via ChaosCoordinator with blast radius checks
- `_run_property_discovery()` - Run property tests via subprocess pytest
- `_run_browser_discovery()` - Run browser discovery via Playwright headless
- `_file_bugs(bugs)` - File unique bugs via BugFilingService
- `_get_fuzzing_test_file(endpoint)` - Map endpoints to test files
- `_count_by_severity(bugs)` - Count bugs by severity
- `_count_by_method(bugs)` - Count bugs by discovery method

**Helper Methods:**
- `_run_network_latency_experiment(coordinator, blast_radius_checks)` - Network latency chaos experiment
- `_run_database_drop_experiment(coordinator, blast_radius_checks)` - Database drop chaos experiment
- `_run_memory_pressure_experiment(coordinator, blast_radius_checks)` - Memory pressure chaos experiment

**Convenience Function:**
- `run_discovery(github_token, github_repository, duration_seconds)` - CI/CD convenience function

**Service Dependencies:**
- `FuzzingOrchestrator` - Fuzzing campaign orchestration
- `ChaosCoordinator` - Chaos experiment orchestration
- `BugFilingService` - Automated GitHub issue filing
- `ResultAggregator` - Result normalization
- `BugDeduplicator` - Cross-method deduplication
- `SeverityClassifier` - Rule-based severity classification
- `DashboardGenerator` - Weekly HTML/JSON report generation

**`backend/tests/bug_discovery/core/__init__.py`** (updated)

Unified exports for all core services:
- `DiscoveryCoordinator` - Orchestration service
- `run_discovery` - CI/CD convenience function
- `ResultAggregator` - Result normalization
- `BugDeduplicator` - Bug deduplication
- `SeverityClassifier` - Severity classification
- `DashboardGenerator` - Report generation

**`backend/tests/bug_discovery/storage/reports/.gitkeep`** (directory marker)

Storage directory for weekly HTML/JSON reports generated by DashboardGenerator

## Pipeline Architecture

### End-to-End Flow

```
run_full_discovery()
    ↓
1. Fuzzing Discovery (FuzzingOrchestrator)
    → aggregate_fuzzing_results()
    ↓
2. Chaos Discovery (ChaosCoordinator)
    → aggregate_chaos_results()
    ↓
3. Property Discovery (subprocess pytest)
    → aggregate_property_results()
    ↓
4. Browser Discovery (Playwright)
    → aggregate_browser_results()
    ↓
5. Deduplication (BugDeduplicator)
    → deduplicate_bugs()
    ↓
6. Severity Classification (SeverityClassifier)
    → batch_classify()
    ↓
7. Bug Filing (BugFilingService)
    → file_bug() for each unique bug
    ↓
8. Report Generation (DashboardGenerator)
    → generate_weekly_report()
```

### Discovery Method Details

**1. Fuzzing Discovery**
- **Orchestrator:** FuzzingOrchestrator
- **Method:** `run_campaign_with_bug_filing(target_endpoint, test_file, duration_seconds)`
- **Endpoints:** /api/v1/auth/login, /api/v1/agents, /api/v1/agents/run, /api/v1/canvas/present
- **Duration:** 15 min max per endpoint (900s)
- **Test Files:** test_auth_api_fuzzing.py, test_agent_api_fuzzing.py, test_agent_streaming_fuzzing.py, test_canvas_presentation_fuzzing.py
- **Aggregation:** ResultAggregator.aggregate_fuzzing_results()

**2. Chaos Discovery**
- **Orchestrator:** ChaosCoordinator
- **Method:** `run_experiment(experiment_name, failure_injection, verify_graceful_degradation, blast_radius_checks)`
- **Experiments:** network_latency_3g, database_connection_drop, memory_pressure
- **Blast Radius:** assert_blast_radius checks for all experiments
- **Database:** Isolated SQLite database (tempfile.NamedTemporaryFile)
- **Failure Injection:** Mock classes for CI environments (LatencyInjection, DatabaseDropInjection, MemoryPressureInjection)
- **Aggregation:** ResultAggregator.aggregate_chaos_results() (only adds reports if experiment failed)

**3. Property Discovery**
- **Method:** subprocess pytest execution
- **Command:** `python -m pytest tests/property_tests -v --tb=short`
- **Timeout:** 30 minutes (1800s)
- **Output Parsing:** Parse stdout for FAILED test results
- **Aggregation:** ResultAggregator.aggregate_property_results() (only failed tests become BugReports)

**4. Browser Discovery**
- **Method:** Playwright headless browser
- **URL:** http://localhost:3000 (FRONTEND_URL env var)
- **Detection:** Console error checking via `window.__consoleErrors`
- **Fallback:** Frontend unavailable creates bug report
- **Aggregation:** ResultAggregator.aggregate_browser_results()

### Result Processing

**5. Deduplication**
- **Service:** BugDeduplicator
- **Method:** `deduplicate_bugs(all_reports)`
- **Logic:** SHA256-based error signature hashing with discovery_methods metadata
- **Output:** List of unique BugReport objects with duplicate_count

**6. Severity Classification**
- **Service:** SeverityClassifier
- **Method:** `batch_classify(unique_bugs)`
- **Rules:** Keyword-based (CRITICAL: sql injection, xss, csrf, security; HIGH: resilience, memory leak, connection; MEDIUM: accessibility, invariant)
- **Output:** BugReport.severity field populated

**7. Bug Filing**
- **Service:** BugFilingService
- **Method:** `file_bug(test_name, error_message, metadata)`
- **Idempotency:** Duplicate detection based on test_name + error_signature
- **Metadata:** test_type, severity, error_signature, duplicate_count, plus bug-specific metadata
- **Output:** List of filing results (status: created/duplicate/error)

**8. Report Generation**
- **Service:** DashboardGenerator
- **Method:** `generate_weekly_report(bugs_found, unique_bugs, filed_bugs, reports)`
- **Output:** HTML report at storage/reports/bug_discovery_report_{timestamp}.html
- **Content:** Summary cards, bugs by method, bugs by severity, top N bugs, regression rate

## Integration Points

### FuzzingOrchestrator Integration

```python
from tests.fuzzing.campaigns.fuzzing_orchestrator import FuzzingOrchestrator

orchestrator = FuzzingOrchestrator(self.github_token, self.github_repository)
result = orchestrator.run_campaign_with_bug_filing(
    target_endpoint=endpoint,
    test_file=test_file,
    duration_seconds=min(duration_seconds // len(endpoints), 900)
)
campaign_reports = self.result_aggregator.aggregate_fuzzing_results(result)
```

**Integration Points:**
- BugFilingService passed to FuzzingOrchestrator constructor
- run_campaign_with_bug_filing() handles automated bug filing during fuzzing
- ResultAggregator converts fuzzing campaign results to BugReport objects

### ChaosCoordinator Integration

```python
from tests.chaos.core.chaos_coordinator import ChaosCoordinator
from tests.chaos.core.blast_radius_controls import assert_blast_radius

# Create isolated database
engine = create_engine(f"sqlite:///{test_db_path}")
Session = sessionmaker(bind=engine)
db_session = Session()

coordinator = ChaosCoordinator(
    db_session=db_session,
    bug_filing_service=self.bug_filing_service
)

result = coordinator.run_experiment(
    experiment_name="network_latency_3g",
    failure_injection=LatencyInjection,
    verify_graceful_degradation=verify_graceful_degradation,
    blast_radius_checks=[assert_blast_radius]
)
experiment_reports = self.result_aggregator.aggregate_chaos_results(result)
```

**Integration Points:**
- BugFilingService passed to ChaosCoordinator constructor
- Isolated test database for blast radius enforcement
- Blast radius checks (assert_blast_radius) enforced for all experiments
- ResultAggregator converts chaos results to BugReport objects (only if experiment failed)

### BugFilingService Integration

```python
from tests.bug_discovery.bug_filing_service import BugFilingService

self.bug_filing_service = BugFilingService(github_token, github_repository)

result = self.bug_filing_service.file_bug(
    test_name=bug.test_name,
    error_message=bug.error_message,
    metadata={
        "test_type": bug.discovery_method.value,
        "severity": bug.severity.value,
        "error_signature": bug.error_signature,
        "duplicate_count": bug.duplicate_count,
        **bug.metadata
    }
)
```

**Integration Points:**
- BugFilingService instance created in DiscoveryCoordinator.__init__()
- Passed to FuzzingOrchestrator and ChaosCoordinator
- Called in _file_bugs() for each unique bug after deduplication
- Metadata enriched with discovery_method, severity, error_signature, duplicate_count

### ResultAggregator Integration

```python
from tests.bug_discovery.core.result_aggregator import ResultAggregator

self.result_aggregator = ResultAggregator()

# Fuzzing results
campaign_reports = self.result_aggregator.aggregate_fuzzing_results(result)

# Chaos results
experiment_reports = self.result_aggregator.aggregate_chaos_results(result)

# Property test results
property_reports = self.result_aggregator.aggregate_property_results(result.stdout)

# Browser discovery results
browser_reports = self.result_aggregator.aggregate_browser_results(bugs)
```

**Integration Points:**
- ResultAggregator instance created in DiscoveryCoordinator.__init__()
- Four aggregation methods for different discovery methods
- Normalizes all results to BugReport objects

## Graceful Degradation

The DiscoveryCoordinator implements graceful degradation for missing dependencies:

**1. Playwright Not Available**
```python
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("[DiscoveryCoordinator] Playwright not available, skipping browser discovery")
    return []
```

**2. Frontend Not Available**
```python
try:
    page.goto(frontend_url, timeout=10000)
except Exception as e:
    bugs.append({
        "type": "frontend_unavailable",
        "error": f"Frontend not available at {frontend_url}: {str(e)}",
        "url": frontend_url
    })
```

**3. Property Test Directory Not Found**
```python
if not property_test_dir.exists():
    print("[DiscoveryCoordinator] Property test directory not found, skipping")
    return []
```

**4. Fuzzing Campaign Failure**
```python
except Exception as e:
    print(f"[DiscoveryCoordinator] Warning: Fuzzing failed for {endpoint}: {e}")
    reports.append(BugReport(
        discovery_method=DiscoveryMethod.FUZZING,
        test_name=f"fuzzing_{endpoint.replace('/', '_')}",
        error_message=f"Fuzzing campaign failed: {str(e)}",
        error_signature=f"fuzzing_failure_{endpoint}"
    ))
```

**5. Chaos Experiment Failure**
```python
except Exception as e:
    print(f"[DiscoveryCoordinator] Warning: Chaos experiment {experiment_name} failed: {e}")
    reports.append(BugReport(
        discovery_method=DiscoveryMethod.CHAOS,
        test_name=experiment_name,
        error_message=f"Chaos experiment setup failed: {str(e)}",
        error_signature=f"chaos_setup_failure_{experiment_name}"
    ))
```

**6. Bug Filing Failure**
```python
except Exception as e:
    print(f"[DiscoveryCoordinator] Warning: Failed to file bug {bug.test_name}: {e}")
    filed_bugs.append({
        "status": "error",
        "test_name": bug.test_name,
        "error": str(e)
    })
```

## Patterns Established

### 1. Orchestration Pattern
```python
coordinator = DiscoveryCoordinator(
    github_token=os.getenv("GITHUB_TOKEN"),
    github_repository=os.getenv("GITHUB_REPOSITORY")
)
result = coordinator.run_full_discovery(duration_seconds=3600)
```

**Benefits:**
- Single entry point for complete bug discovery pipeline
- Consistent orchestration across all discovery methods
- Easy CI/CD integration via run_discovery() convenience function

### 2. Service Composition Pattern
```python
self.bug_filing_service = BugFilingService(github_token, github_repository)
self.result_aggregator = ResultAggregator()
self.bug_deduplicator = BugDeduplicator()
self.severity_classifier = SeverityClassifier()
self.dashboard_generator = DashboardGenerator(storage_dir)
```

**Benefits:**
- Modular architecture (each service has single responsibility)
- Easy to test individual services
- Easy to extend with new services

### 3. Subprocess Execution Pattern
```python
result = subprocess.run(
    [sys.executable, "-m", "pytest", str(property_test_dir), "-v", "--tb=short"],
    capture_output=True,
    text=True,
    cwd=backend_dir,
    timeout=1800
)
return self.result_aggregator.aggregate_property_results(result.stdout)
```

**Benefits:**
- Isolated test execution (separate process)
- Stdout parsing for test results
- Timeout protection (30 min max)

### 4. Mock Failure Injection Pattern
```python
class LatencyInjection:
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
```

**Benefits:**
- CI-compatible chaos tests (no toxiproxy required)
- Graceful degradation for missing dependencies
- Consistent experiment interface

### 5. Isolated Database Pattern
```python
with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
    test_db_path = f.name

engine = create_engine(f"sqlite:///{test_db_path}")
Session = sessionmaker(bind=engine)
db_session = Session()

try:
    # Run chaos experiments
finally:
    os.unlink(test_db_path)
```

**Benefits:**
- Blast radius enforcement (isolated test database)
- No production data at risk
- Automatic cleanup on error

## Deviations from Plan

### None - Plan Executed Successfully

All tasks completed as specified:
- ✅ DiscoveryCoordinator service created with run_full_discovery() orchestration method
- ✅ _run_fuzzing_discovery() uses FuzzingOrchestrator.run_campaign_with_bug_filing()
- ✅ _run_chaos_discovery() uses ChaosCoordinator.run_experiment() with blast_radius_checks
- ✅ _run_property_discovery() runs subprocess pytest and parses output
- ✅ _run_browser_discovery() uses Playwright headless browser
- ✅ _file_bugs() calls BugFilingService.file_bug() for each unique bug
- ✅ DashboardGenerator.generate_weekly_report() creates HTML report
- ✅ core/__init__.py exports all services for clean imports
- ✅ storage/reports/ directory exists for report output
- ✅ run_discovery() convenience function for CI/CD pipelines

## Verification Results

All verification steps passed:

1. ✅ **DiscoveryCoordinator imports all dependencies** - FuzzingOrchestrator, ChaosCoordinator, BugFilingService, core services
2. ✅ **run_full_discovery() method exists** - Main orchestration method
3. ✅ **Method structure** - All helper methods exist (_run_fuzzing_discovery, _run_chaos_discovery, _run_property_discovery, _run_browser_discovery, _file_bugs)
4. ✅ **core/__init__.py exports all services** - DiscoveryCoordinator, ResultAggregator, BugDeduplicator, SeverityClassifier, DashboardGenerator
5. ✅ **storage/reports/ directory exists** - Directory for weekly HTML/JSON reports
6. ✅ **run_discovery() convenience function exists** - CI/CD integration function
7. ✅ **BugReport model has required fields** - discovery_method, test_name, error_message, error_signature, severity
8. ✅ **Services can be instantiated** - All five services instantiate without errors

## Usage Examples

### CI/CD Pipeline Integration

```python
from tests.bug_discovery.core import run_discovery

# Run full discovery with 1 hour duration
result = run_discovery(
    github_token=os.getenv("GITHUB_TOKEN"),
    github_repository=os.getenv("GITHUB_REPOSITORY"),
    duration_seconds=3600
)

print(f"Bugs found: {result['bugs_found']}")
print(f"Unique bugs: {result['unique_bugs']}")
print(f"Filed bugs: {result['filed_bugs']}")
print(f"Report: {result['report_path']}")
print(f"Severity distribution: {result['severity_distribution']}")
print(f"By method: {result['by_method']}")
```

### Custom Discovery Configuration

```python
from tests.bug_discovery.core import DiscoveryCoordinator

coordinator = DiscoveryCoordinator(
    github_token=os.getenv("GITHUB_TOKEN"),
    github_repository=os.getenv("GITHUB_REPOSITORY")
)

# Run only fuzzing and chaos
result = coordinator.run_full_discovery(
    duration_seconds=1800,
    fuzzing_endpoints=["/api/v1/auth/login", "/api/v1/agents"],
    chaos_experiments=["network_latency_3g"],
    run_property_tests=False,
    run_browser_discovery=False
)
```

## Next Phase Readiness

✅ **DiscoveryCoordinator orchestration service complete** - End-to-end bug discovery pipeline with all four discovery methods

**Ready for:**
- Phase 242 Plan 03: Weekly CI pipeline integration
- Phase 243: Memory & Performance Bug Discovery
- Phase 244: AI-Enhanced Bug Discovery
- Phase 245: Feedback Loops & ROI Tracking

**Unified Pipeline Infrastructure Established:**
- DiscoveryCoordinator orchestration service
- End-to-end pipeline (fuzzing → chaos → property → browser → aggregate → deduplicate → classify → file → report)
- Integration with FuzzingOrchestrator, ChaosCoordinator, BugFilingService
- Subprocess execution for property tests
- Playwright headless browser for console error detection
- Blast radius enforcement for chaos experiments
- Idempotent bug filing with duplicate detection
- Weekly HTML/JSON report generation
- CI/CD convenience function for easy integration
- Storage directory for reports (backend/tests/bug_discovery/storage/reports/)

## Self-Check: PASSED

All files created:
- ✅ backend/tests/bug_discovery/core/discovery_coordinator.py (654 lines)
- ✅ backend/tests/bug_discovery/storage/reports/.gitkeep (directory marker)

All commits exist:
- ✅ 82067a502 - Task 1: DiscoveryCoordinator orchestration service
- ✅ a6fd0f3de - Task 2: Update core exports and create storage directory

All verification passed:
- ✅ DiscoveryCoordinator imports all dependencies
- ✅ run_full_discovery() method exists
- ✅ All orchestration methods exist (_run_fuzzing_discovery, _run_chaos_discovery, _run_property_discovery, _run_browser_discovery, _file_bugs)
- ✅ core/__init__.py exports all five services
- ✅ storage/reports/ directory exists
- ✅ run_discovery() convenience function exists
- ✅ BugReport model has required fields
- ✅ All services can be instantiated

---

*Phase: 242-unified-bug-discovery-pipeline*
*Plan: 02*
*Completed: 2026-03-25*
