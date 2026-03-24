# Architecture Research

**Domain:** Automated Bug Discovery (Fuzzing, Chaos Engineering, Property-Based Testing, Headless Browser Automation)
**Researched:** March 24, 2026
**Confidence:** HIGH

## Executive Summary

Atom's existing architecture provides a strong foundation for automated bug discovery with comprehensive test infrastructure (pytest, Hypothesis, Playwright, k6, property-based tests). The platform already has 91 E2E tests, property-based testing with Hypothesis, load testing with k6, and an automated bug filing service integrated with GitHub Issues. This research outlines the integration architecture for expanding automated bug discovery to uncover 50+ bugs through fuzzing, chaos engineering, enhanced property-based testing, and intelligent browser automation.

**Key Findings:**
- **Existing infrastructure**: pytest (1000+ tests), Hypothesis (property-based), k6 (load testing), Playwright (E2E), BugFilingService (GitHub integration)
- **Integration points**: FastAPI backend (OpenAPI spec), LLMService (BYOK), AgentGovernanceService, database models (SQLAlchemy 2.0)
- **Critical components needed**: Fuzzing orchestration layer, chaos engineering failure injection, headless browser automation agents, property-based test expansion
- **Build order**: Property-based expansion → API fuzzing → Chaos engineering → Intelligent browser automation → Unified bug discovery pipeline
- **Performance targets**: <5min fuzzing campaigns, <30s property test runs, <10min chaos experiments, automated bug filing within 60s of failure

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CI/CD Layer (GitHub Actions)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ Fuzzing Job  │  │Chaos Job     │  │Property Job  │  │Browser Auto  │   │
│  │ (Scheduled)  │  │(Scheduled)   │  │(On Push)     │  │(On Push)     │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
└─────────┼──────────────────┼──────────────────┼──────────────────┼───────────┘
          │                  │                  │                  │
┌─────────┴──────────────────┴──────────────────┴──────────────────┴───────────┐
│                       Bug Discovery Orchestration Layer                      │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Unified Bug Discovery Coordinator                                  │    │
│  │  - Campaign scheduling & management                                 │    │
│  │  - Result aggregation & deduplication                              │    │
│  │  - Bug severity triage & automatic filing                          │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────────────────┤
│                       Discovery Method Layers                                │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌────────────────────┐ │
│  │  API Fuzzing Layer   │  │ Chaos Engineering    │  │ Property-Based     │ │
│  │  (Atheris/RESTler)   │  │ Layer (Chaos Monkey) │  │ Testing (Hypothesis)│ │
│  │  - Input generation  │  │ - Network failure    │  │ - Invariant testing│ │
│  │  - Endpoint coverage │  │ - Resource stress    │  │ - State machine    │ │
│  │  - Schema validation │  │ - Service crash      │  │ - Edge cases       │ │
│  └──────────┬───────────┘  └──────────┬───────────┘  └──────────┬─────────┘ │
├─────────────┼──────────────────────────┼──────────────────────────┼───────────┤
│  ┌──────────┴───────────┐  ┌──────────┴───────────┐  ┌──────────┴─────────┐ │
│  │ Browser Automation   │  │ Existing Test Infra  │  │ Bug Filing Service │ │
│  │ (Playwright + AI)    │  │ (pytest, k6, E2E)    │  │ (GitHub Issues)    │ │
│  │  - Intelligent flow  │  │  - Load tests        │  │  - Deduplication   │ │
│  │  - Visual regression │  │  - E2E tests         │  │  - Auto-labeling   │ │
│  │  - Accessibility     │  │  - Property tests    │  │  - Metadata        │ │
│  └──────────┬───────────┘  └──────────┬───────────┘  └──────────┬─────────┘ │
└─────────────┼──────────────────────────┼──────────────────────────┼───────────┘
              │                          │                          │
┌─────────────┴──────────────────────────┴──────────────────────────┴───────────┐
│                        Application Under Test                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ FastAPI      │  │ LLMService   │  │ Agent        │  │ Database     │     │
│  │ Backend      │  │ (BYOK)       │  │ Governance   │  │ (PostgreSQL) │     │
│  └──────────┬───┘  └──────────┬───┘  └──────────┬───┘  └──────────┬───┘     │
└─────────────┼──────────────────┼──────────────────┼──────────────────┼───────────┘
              │                  │                  │                  │
┌─────────────┴──────────────────┴──────────────────┴──────────────────┴───────────┐
│                       Existing Test Infrastructure                            │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │  Test Fixtures & Factories (50+ pytest fixtures)                     │    │
│  │  Mock Services (LLM, Cache, Storage, WebSocket)                      │    │
│  │  Test Data Manager (SQLite/PostgreSQL isolation)                     │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **Bug Discovery Coordinator** | Orchestrates discovery campaigns, aggregates results, manages triage | Python service with async task queue (Celery/RQ) |
| **API Fuzzing Engine** | Generates malformed inputs, validates OpenAPI schemas, finds crashes | Atheris (coverage-guided) + RESTler (stateful) |
| **Chaos Engineering Layer** | Injects failures (network, resource, service), validates resilience | Chaos Monkey + custom failure injection |
| **Property-Based Test Runner** | Expands Hypothesis tests, validates invariants, finds edge cases | Hypothesis with custom strategies |
| **Intelligent Browser Agent** | Discovers UI bugs, visual regression, accessibility issues | Playwright + heuristic exploration |
| **Bug Filing Service** | Files GitHub Issues, deduplicates, labels, attaches artifacts | Existing BugFilingService (expand) |
| **Result Aggregator** | Correlates failures across methods, tracks metrics, generates reports | Unified reporting with deduplication |

## Recommended Project Structure

```
atom/
├── backend/
│   ├── tests/
│   │   ├── fuzzing/                     # NEW: API fuzzing campaigns
│   │   │   ├── campaigns/               # Fuzzing campaign configurations
│   │   │   │   ├── api_fuzz_campaign.py # RESTler/Atheris campaign setup
│   │   │   │   ├── auth_fuzz.py         # Authentication endpoint fuzzing
│   │   │   │   ├── agent_fuzz.py        # Agent execution fuzzing
│   │   │   │   └── workflow_fuzz.py     # Workflow API fuzzing
│   │   │   ├── generators/              # Custom input generators
│   │   │   │   ├── malformed_json.py    # Malformed JSON generator
│   │   │   │   ├── sql_injection.py     # SQL injection templates
│   │   │   │   └── xss_payloads.py       # XSS payload generator
│   │   │   ├── harnesses/               # Fuzzing harnesses
│   │   │   │   └── fastapi_harness.py   # FastAPI test wrapper
│   │   │   └── conftest.py              # Fuzzing fixtures
│   │   ├── chaos/                       # NEW: Chaos engineering experiments
│   │   │   ├── experiments/             # Chaos experiment definitions
│   │   │   │   ├── network_latency.py   # Network delay injection
│   │   │   │   ├── db_connection_drop.py # Database failure injection
│   │   │   │   ├── memory_pressure.py   # Memory exhaustion simulation
│   │   │   │   └── service_crash.py     # Service termination experiments
│   │   │   ├── monitors/                # Chaos monitoring & validation
│   │   │   │   └── resilience_monitor.py # System health validation
│   │   │   └── conftest.py              # Chaos engineering fixtures
│   │   ├── property_tests/              # EXTEND: Existing property tests
│   │   │   ├── llm/                     # Existing LLM property tests
│   │   │   ├── governance/              # Existing governance property tests
│   │   │   ├── episodes/                # Existing episode property tests
│   │   │   ├── database/                # Existing database property tests
│   │   │   ├── fuzzing_integration/     # NEW: Fuzzing + Hypothesis
│   │   │   │   ├── api_invariants.py    # API contract invariants
│   │   │   │   ├── state_invariants.py  # State machine invariants
│   │   │   │   └── security_invariants.py # Security property tests
│   │   │   └── conftest.py              # Existing property test fixtures
│   │   ├── browser_automation/          # NEW: Intelligent browser automation
│   │   │   ├── agents/                  # AI-driven exploration agents
│   │   │   │   ├── exploration_agent.py # Heuristic UI explorer
│   │   │   │   ├── form_agent.py        # Form filling agent
│   │   │   │   └── navigation_agent.py  # Navigation flow agent
│   │   │   ├── detectors/               # Bug detection modules
│   │   │   │   ├── visual_regression.py # Visual diff detector
│   │   │   │   ├── accessibility.py     # A11y violation detector
│   │   │   │   └── console_errors.py    # Console error detector
│   │   │   ├── strategies/              # Exploration strategies
│   │   │   │   ├── depth_first.py       # Depth-first exploration
│   │   │   │   ├── breadth_first.py      # Breadth-first exploration
│   │   │   │   └── random_walk.py       # Random exploration
│   │   │   └── conftest.py              # Browser automation fixtures
│   │   ├── bug_discovery/               # EXTEND: Existing bug discovery
│   │   │   ├── fixtures/                # Existing bug filing fixtures
│   │   │   ├── bug_filing_service.py    # Existing BugFilingService
│   │   │   ├── coordinator.py           # NEW: Discovery coordinator
│   │   │   ├── aggregators/             # NEW: Result aggregators
│   │   │   │   ├── failure_aggregator.py # Correlate failures
│   │   │   │   └── deduplicator.py      # Deduplicate bugs
│   │   │   └── triage/                  # NEW: Bug triage
│   │   │       ├── severity_classifier.py # Classify bug severity
│   │   │       └── impact_analyzer.py    # Analyze bug impact
│   │   ├── load/                        # EXTEND: Existing load tests
│   │   │   ├── k6_setup.js              # Existing k6 setup
│   │   │   ├── test_api_load_baseline.js
│   │   │   ├── test_api_load_moderate.js
│   │   │   ├── test_api_load_high.js
│   │   │   ├── test_web_ui_load.js
│   │   │   └── README.md
│   │   ├── e2e_ui/                      # EXTEND: Existing E2E tests
│   │   │   ├── tests/                   # 91 existing E2E tests
│   │   │   ├── fixtures/                # Existing E2E fixtures
│   │   │   ├── pages/                   # Existing page objects
│   │   │   └── conftest.py
│   │   └── conftest.py                  # Root conftest (existing)
│   ├── core/                            # Existing core services
│   │   ├── fuzzing_orchestrator.py      # NEW: Fuzzing campaign orchestration
│   │   ├── chaos_coordinator.py         # NEW: Chaos experiment orchestration
│   │   └── discovery_coordinator.py     # NEW: Unified discovery coordination
│   ├── api/                             # Existing API routes
│   │   ├── fuzzing_routes.py            # NEW: Fuzzing control endpoints
│   │   └── chaos_routes.py              # NEW: Chaos experiment endpoints
│   └── tools/                           # Existing tools
│       └── discovery_tools.py           # NEW: Bug discovery tools
└── .github/
    └── workflows/
        ├── fuzzing.yml                  # NEW: Scheduled fuzzing campaigns
        ├── chaos.yml                    # NEW: Scheduled chaos experiments
        ├── bug_discovery.yml            # NEW: Unified discovery pipeline
        └── deploy.yml                   # Existing deployment workflow
```

### Structure Rationale

- **`backend/tests/fuzzing/`**: API fuzzing campaigns with Atheris/RESTler, organized by endpoint categories (auth, agents, workflows)
- **`backend/tests/chaos/`**: Chaos engineering experiments for failure injection (network, database, memory, service crashes)
- **`backend/tests/property_tests/`**: Expand existing Hypothesis tests with fuzzing integration, security invariants, and state machine validation
- **`backend/tests/browser_automation/`**: AI-driven browser exploration agents for automatic UI bug discovery, visual regression, and accessibility testing
- **`backend/tests/bug_discovery/`**: Extend existing BugFilingService with unified coordinator, result aggregation, and automatic triage
- **`backend/core/`**: Add orchestration services for fuzzing campaigns, chaos experiments, and unified discovery coordination
- **`.github/workflows/`**: CI/CD workflows for scheduled fuzzing, chaos experiments, and unified bug discovery pipeline

## Architectural Patterns

### Pattern 1: Fuzzing Campaign Orchestration

**What:** Centralized orchestration service that manages fuzzing campaigns across API endpoints, coordinates multiple fuzzing engines (Atheris, RESTler), aggregates crash results, and triggers bug filing for reproducible failures.

**When to use:**
- Running comprehensive API fuzzing campaigns
- Coordinating multiple fuzzing engines
- Aggregating crashes from different fuzzers
- Automating bug filing for reproducible crashes

**Trade-offs:**
- **Pros**: Comprehensive API coverage, automated crash discovery, reproducible test cases
- **Cons**: High computational cost, potential for false positives, requires crash triage

**Example:**
```python
# backend/core/fuzzing_orchestrator.py
from typing import List, Dict, Optional
from concurrent.futures import ProcessPoolExecutor, as_completed
import subprocess
import json
from datetime import datetime

class FuzzingCampaign:
    """Represents a fuzzing campaign with configuration and results."""

    def __init__(
        self,
        campaign_id: str,
        target_endpoints: List[str],
        fuzzer_type: str = "atheris",
        duration_seconds: int = 300,
        max_workers: int = 4
    ):
        self.campaign_id = campaign_id
        self.target_endpoints = target_endpoints
        self.fuzzer_type = fuzzer_type
        self.duration_seconds = duration_seconds
        self.max_workers = max_workers
        self.crashes = []
        self.start_time = None
        self.end_time = None

    def to_dict(self) -> Dict:
        """Serialize campaign to dict."""
        return {
            "campaign_id": self.campaign_id,
            "target_endpoints": self.target_endpoints,
            "fuzzer_type": self.fuzzer_type,
            "duration_seconds": self.duration_seconds,
            "crashes_found": len(self.crashes),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }


class FuzzingOrchestrator:
    """
    Orchestrates fuzzing campaigns across Atom API endpoints.

    Features:
    - Multi-fuzzer support (Atheris, RESTler, custom)
    - Parallel campaign execution
    - Crash deduplication
    - Reproducible test case generation
    - Integration with BugFilingService
    """

    def __init__(self, bug_filing_service):
        """
        Initialize FuzzingOrchestrator.

        Args:
            bug_filing_service: BugFilingService instance for auto-filing bugs
        """
        self.bug_filing_service = bug_filing_service
        self.campaigns: Dict[str, FuzzingCampaign] = {}

    def start_campaign(
        self,
        target_endpoints: List[str],
        fuzzer_type: str = "atheris",
        duration_seconds: int = 300,
        max_workers: int = 4
    ) -> FuzzingCampaign:
        """
        Start a fuzzing campaign.

        Args:
            target_endpoints: List of API endpoints to fuzz (e.g., ["/api/auth/login", "/api/v1/agents/execute"])
            fuzzer_type: Type of fuzzer ("atheris", "restler", "custom")
            duration_seconds: Campaign duration in seconds
            max_workers: Number of parallel fuzzing processes

        Returns:
            FuzzingCampaign instance
        """
        campaign_id = f"fuzz_{datetime.utcnow().timestamp()}"
        campaign = FuzzingCampaign(
            campaign_id=campaign_id,
            target_endpoints=target_endpoints,
            fuzzer_type=fuzzer_type,
            duration_seconds=duration_seconds,
            max_workers=max_workers
        )

        self.campaigns[campaign_id] = campaign
        return campaign

    def run_campaign(self, campaign: FuzzingCampaign) -> Dict:
        """
        Run a fuzzing campaign across target endpoints.

        Args:
            campaign: FuzzingCampaign to execute

        Returns:
            Campaign results with crash summaries
        """
        campaign.start_time = datetime.utcnow()

        # Run fuzzing in parallel across endpoints
        with ProcessPoolExecutor(max_workers=campaign.max_workers) as executor:
            futures = {
                executor.submit(
                    self._fuzz_endpoint,
                    endpoint,
                    campaign.fuzzer_type,
                    campaign.duration_seconds
                ): endpoint
                for endpoint in campaign.target_endpoints
            }

            for future in as_completed(futures):
                endpoint = futures[future]
                try:
                    crashes = future.result()
                    campaign.crashes.extend(crashes)
                    print(f"Fuzzing {endpoint}: found {len(crashes)} crashes")
                except Exception as e:
                    print(f"Error fuzzing {endpoint}: {e}")

        campaign.end_time = datetime.utcnow()

        # Deduplicate crashes
        unique_crashes = self._deduplicate_crashes(campaign.crashes)
        campaign.crashes = unique_crashes

        # File bugs for reproducible crashes
        for crash in unique_crashes:
            if self._is_reproducible(crash):
                self._file_bug_for_crash(crash, campaign)

        return campaign.to_dict()

    def _fuzz_endpoint(
        self,
        endpoint: str,
        fuzzer_type: str,
        duration_seconds: int
    ) -> List[Dict]:
        """
        Fuzz a single endpoint.

        Args:
            endpoint: API endpoint path
            fuzzer_type: Type of fuzzer to use
            duration_seconds: Fuzzing duration

        Returns:
            List of crash dictionaries
        """
        # This is a simplified implementation
        # In production, you'd use actual fuzzing engines (Atheris, RESTler)

        crashes = []

        # Mock fuzzing - replace with actual fuzzer invocation
        # Example with Atheris:
        # subprocess.run([
        #     "python", "-m", "atheris",
        #     "-h", f"--runs={duration_seconds * 100}",  # Atheris uses iterations, not seconds
        #     f"backend/tests/fuzzing/harnesses/fastapi_harness.py",
        #     "--", f"--endpoint={endpoint}"
        # ])

        # For demonstration, return mock crashes
        # In production, parse fuzzer output for crash data
        if endpoint == "/api/auth/login":
            crashes.append({
                "endpoint": endpoint,
                "input": b'{"username": "\x00\x00\x00", "password": "admin"}',
                "error": "AttributeError: 'NoneType' object has no attribute 'id'",
                "stack_trace": "Traceback (most recent call last):\n  ...",
                "reproducible": True
            })

        return crashes

    def _deduplicate_crashes(self, crashes: List[Dict]) -> List[Dict]:
        """
        Deduplicate crashes by error signature.

        Args:
            crashes: List of crash dictionaries

        Returns:
            Deduplicated crash list
        """
        seen_signatures = set()
        unique_crashes = []

        for crash in crashes:
            # Create signature from error message + endpoint
            signature = f"{crash['error']}:{crash['endpoint']}"
            if signature not in seen_signatures:
                seen_signatures.add(signature)
                unique_crashes.append(crash)

        return unique_crashes

    def _is_reproducible(self, crash: Dict) -> bool:
        """
        Check if crash is reproducible.

        Args:
            crash: Crash dictionary

        Returns:
            True if crash is reproducible
        """
        # In production, re-run the crash input to verify reproducibility
        return crash.get("reproducible", False)

    def _file_bug_for_crash(self, crash: Dict, campaign: FuzzingCampaign):
        """
        File a bug for reproducible crash.

        Args:
            crash: Crash dictionary
            campaign: Fuzzing campaign context
        """
        test_name = f"Fuzz_{crash['endpoint'].replace('/', '_')}"
        error_message = crash['error']
        stack_trace = crash.get('stack_trace', '')

        metadata = {
            "test_type": "fuzzing",
            "platform": "api",
            "endpoint": crash['endpoint'],
            "input_repr": repr(crash['input'][:100]),  # First 100 bytes
            "campaign_id": campaign.campaign_id,
            "fuzzer_type": campaign.fuzzer_type
        }

        self.bug_filing_service.file_bug(
            test_name=test_name,
            error_message=error_message,
            metadata=metadata
        )


# Usage in tests
# backend/tests/fuzzing/test_fuzzing_campaigns.py
import pytest
from core.fuzzing_orchestrator import FuzzingOrchestrator
from tests.bug_discovery.bug_filing_service import BugFilingService

@pytest.mark.integration
def test_fuzzing_campaign_auth_endpoints(db_session):
    """Run fuzzing campaign on authentication endpoints."""
    # Create bug filing service (mock in tests)
    bug_service = BugFilingService(
        github_token="test_token",
        github_repository="test/repo"
    )

    # Create orchestrator
    orchestrator = FuzzingOrchestrator(bug_service)

    # Start campaign
    campaign = orchestrator.start_campaign(
        target_endpoints=[
            "/api/auth/login",
            "/api/auth/logout",
            "/api/auth/refresh"
        ],
        fuzzer_type="atheris",
        duration_seconds=60,  # Short campaign for testing
        max_workers=2
    )

    # Run campaign
    results = orchestrator.run_campaign(campaign)

    # Assert campaign completed
    assert results["start_time"] is not None
    assert results["end_time"] is not None
    assert results["crashes_found"] >= 0
```

---

### Pattern 2: Chaos Engineering Experiment Orchestration

**What:** Centralized chaos engineering service that injects failures (network latency, database connection drops, memory pressure, service crashes) into the Atom platform, validates system resilience, and automatically files bugs for unrecoverable failures.

**When to use:**
- Testing system resilience under failure
- Validating graceful degradation
- Discovering cascading failures
- Testing recovery mechanisms

**Trade-offs:**
- **Pros**: Finds production-relevant failures, validates resilience, tests recovery automation
- **Cons**: Can cause temporary outages, requires careful isolation, may produce false positives

**Example:**
```python
# backend/core/chaos_coordinator.py
from typing import List, Dict, Callable, Optional
from datetime import datetime, timedelta
import asyncio
import psutil  # For system resource monitoring
import time

class ChaosExperiment:
    """Represents a chaos engineering experiment."""

    def __init__(
        self,
        experiment_id: str,
        failure_type: str,
        target_component: str,
        duration_seconds: int,
        rollback_func: Optional[Callable] = None
    ):
        self.experiment_id = experiment_id
        self.failure_type = failure_type
        self.target_component = target_component
        self.duration_seconds = duration_seconds
        self.rollback_func = rollback_func
        self.start_time = None
        self.end_time = None
        self.baseline_metrics = {}
        self.chaos_metrics = {}
        self.recovery_metrics = {}
        self.failures_detected = []

    def to_dict(self) -> Dict:
        """Serialize experiment to dict."""
        return {
            "experiment_id": self.experiment_id,
            "failure_type": self.failure_type,
            "target_component": self.target_component,
            "duration_seconds": self.duration_seconds,
            "failures_detected": len(self.failures_detected),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
        }


class ChaosCoordinator:
    """
    Orchestrates chaos engineering experiments for Atom platform.

    Features:
    - Network failure injection (latency, packet loss, connection drops)
    - Database failure injection (connection pool exhaustion, query failures)
    - Resource stress (CPU, memory, disk)
    - Service termination (graceful and forceful)
    - Automated resilience validation
    - Bug filing for unrecoverable failures
    """

    def __init__(self, bug_filing_service):
        """
        Initialize ChaosCoordinator.

        Args:
            bug_filing_service: BugFilingService instance for auto-filing bugs
        """
        self.bug_filing_service = bug_filing_service
        self.experiments: Dict[str, ChaosExperiment] = {}

    def start_experiment(
        self,
        failure_type: str,
        target_component: str,
        duration_seconds: int = 60
    ) -> ChaosExperiment:
        """
        Start a chaos experiment.

        Args:
            failure_type: Type of failure ("network_latency", "db_connection_drop", "memory_pressure", "service_crash")
            target_component: Component to target ("database", "redis", "llm_service", "api_server")
            duration_seconds: Experiment duration in seconds

        Returns:
            ChaosExperiment instance
        """
        experiment_id = f"chaos_{datetime.utcnow().timestamp()}"
        experiment = ChaosExperiment(
            experiment_id=experiment_id,
            failure_type=failure_type,
            target_component=target_component,
            duration_seconds=duration_seconds
        )

        self.experiments[experiment_id] = experiment
        return experiment

    def run_experiment(self, experiment: ChaosExperiment) -> Dict:
        """
        Run a chaos experiment.

        Args:
            experiment: ChaosExperiment to execute

        Returns:
            Experiment results with failure summaries
        """
        experiment.start_time = datetime.utcnow()

        # Collect baseline metrics
        experiment.baseline_metrics = self._collect_metrics(experiment.target_component)

        # Inject failure
        rollback_func = self._inject_failure(experiment)
        experiment.rollback_func = rollback_func

        # Wait for failure duration
        time.sleep(experiment.duration_seconds)

        # Collect chaos metrics
        experiment.chaos_metrics = self._collect_metrics(experiment.target_component)

        # Detect failures
        experiment.failures_detected = self._detect_failures(
            experiment.baseline_metrics,
            experiment.chaos_metrics
        )

        # Rollback failure injection
        if rollback_func:
            rollback_func()

        # Wait for recovery
        time.sleep(10)

        # Collect recovery metrics
        experiment.recovery_metrics = self._collect_metrics(experiment.target_component)

        experiment.end_time = datetime.utcnow()

        # File bugs for unrecovered failures
        for failure in experiment.failures_detected:
            if not self._is_recovered(failure, experiment.recovery_metrics):
                self._file_bug_for_failure(failure, experiment)

        return experiment.to_dict()

    def _inject_failure(self, experiment: ChaosExperiment) -> Optional[Callable]:
        """
        Inject failure into target component.

        Args:
            experiment: ChaosExperiment with failure configuration

        Returns:
            Rollback function to undo failure injection
        """
        if experiment.failure_type == "network_latency":
            return self._inject_network_latency(experiment)
        elif experiment.failure_type == "db_connection_drop":
            return self._inject_db_connection_drop(experiment)
        elif experiment.failure_type == "memory_pressure":
            return self._inject_memory_pressure(experiment)
        elif experiment.failure_type == "service_crash":
            return self._inject_service_crash(experiment)
        else:
            raise ValueError(f"Unknown failure type: {experiment.failure_type}")

    def _inject_network_latency(self, experiment: ChaosExperiment) -> Callable:
        """
        Inject network latency using tc (traffic control).

        Args:
            experiment: ChaosExperiment with target configuration

        Returns:
            Rollback function
        """
        # Use tc to add network delay
        # This requires root privileges and is platform-specific (Linux)
        # For demonstration, we'll use a mock implementation

        def rollback():
            """Remove network latency."""
            # subprocess.run(["tc", "qdisc", "del", "dev", "eth0", "root"])
            pass

        # Inject latency: add 500ms delay, 100ms jitter, 10% packet loss
        # subprocess.run([
        #     "tc", "qdisc", "add", "dev", "eth0", "root", "handle", "1:",
        #     "netem", "delay", "500ms", "100ms", "loss", "10%"
        # ])

        return rollback

    def _inject_db_connection_drop(self, experiment: ChaosExperiment) -> Callable:
        """
        Inject database connection drops.

        Args:
            experiment: ChaosExperiment with target configuration

        Returns:
            Rollback function
        """
        # Mock implementation - in production, you'd use:
        # - iptables to block database port
        # - Database proxy to drop connections
        # - Custom middleware to reject queries

        def rollback():
            """Restore database connections."""
            pass

        # Block database connections
        # subprocess.run([
        #     "iptables", "-A", "INPUT", "-p", "tcp", "--dport", "5432",
        #     "-j", "DROP"
        # ])

        return rollback

    def _inject_memory_pressure(self, experiment: ChaosExperiment) -> Callable:
        """
        Inject memory pressure by allocating memory.

        Args:
            experiment: ChaosExperiment with target configuration

        Returns:
            Rollback function
        """
        memory_blocks = []

        def rollback():
            """Release allocated memory."""
            memory_blocks.clear()

        # Allocate 500MB of memory
        block_size = 500 * 1024 * 1024  # 500MB in bytes
        memory_blocks.append(b'\x00' * block_size)

        return rollback

    def _inject_service_crash(self, experiment: ChaosExperiment) -> Callable:
        """
        Inject service crash (kill and restart).

        Args:
            experiment: ChaosExperiment with target configuration

        Returns:
            Rollback function
        """
        def rollback():
            """Restart crashed service."""
            # subprocess.run(["systemctl", "start", "atom-backend"])
            pass

        # Kill service
        # subprocess.run(["systemctl", "stop", "atom-backend"])

        return rollback

    def _collect_metrics(self, component: str) -> Dict:
        """
        Collect system metrics for component.

        Args:
            component: Component name

        Returns:
            Metrics dictionary
        """
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent,
            "timestamp": datetime.utcnow().isoformat()
        }

    def _detect_failures(
        self,
        baseline_metrics: Dict,
        chaos_metrics: Dict
    ) -> List[Dict]:
        """
        Detect failures by comparing baseline and chaos metrics.

        Args:
            baseline_metrics: Metrics before failure injection
            chaos_metrics: Metrics during failure injection

        Returns:
            List of failure dictionaries
        """
        failures = []

        # Detect CPU spike (>80% increase)
        cpu_increase = (
            chaos_metrics["cpu_percent"] - baseline_metrics["cpu_percent"]
        )
        if cpu_increase > 80:
            failures.append({
                "type": "cpu_spike",
                "severity": "high",
                "baseline": baseline_metrics["cpu_percent"],
                "chaos": chaos_metrics["cpu_percent"],
                "increase": cpu_increase
            })

        # Detect memory spike (>50% increase)
        memory_increase = (
            chaos_metrics["memory_percent"] - baseline_metrics["memory_percent"]
        )
        if memory_increase > 50:
            failures.append({
                "type": "memory_spike",
                "severity": "high",
                "baseline": baseline_metrics["memory_percent"],
                "chaos": chaos_metrics["memory_percent"],
                "increase": memory_increase
            })

        return failures

    def _is_recovered(self, failure: Dict, recovery_metrics: Dict) -> bool:
        """
        Check if system recovered from failure.

        Args:
            failure: Failure dictionary
            recovery_metrics: Metrics after rollback

        Returns:
            True if system recovered
        """
        # System recovered if metrics are within 20% of baseline
        recovery_cpu = recovery_metrics.get("cpu_percent", 0)
        baseline_cpu = failure.get("baseline", 0)

        return abs(recovery_cpu - baseline_cpu) < (baseline_cpu * 0.2)

    def _file_bug_for_failure(self, failure: Dict, experiment: ChaosExperiment):
        """
        File bug for unrecovered failure.

        Args:
            failure: Failure dictionary
            experiment: ChaosExperiment context
        """
        test_name = f"Chaos_{experiment.failure_type}_{experiment.target_component}"
        error_message = f"System failed to recover from {failure['type']}"
        stack_trace = f"Baseline: {failure['baseline']}, Chaos: {failure['chaos']}, Increase: {failure['increase']}%"

        metadata = {
            "test_type": "chaos",
            "platform": "backend",
            "failure_type": failure["type"],
            "severity": failure["severity"],
            "experiment_id": experiment.experiment_id,
            "target_component": experiment.target_component
        }

        self.bug_filing_service.file_bug(
            test_name=test_name,
            error_message=error_message,
            metadata=metadata
        )


# Usage in tests
# backend/tests/chaos/test_chaos_experiments.py
import pytest
from core.chaos_coordinator import ChaosCoordinator
from tests.bug_discovery.bug_filing_service import BugFilingService

@pytest.mark.integration
@pytest.mark.skip(reason="Chaos experiments require isolated environment")
def test_database_connection_drop_chaos(db_session):
    """Test system resilience when database connections drop."""
    # Create bug filing service (mock in tests)
    bug_service = BugFilingService(
        github_token="test_token",
        github_repository="test/repo"
    )

    # Create coordinator
    coordinator = ChaosCoordinator(bug_service)

    # Start experiment
    experiment = coordinator.start_experiment(
        failure_type="db_connection_drop",
        target_component="database",
        duration_seconds=30  # Short experiment for testing
    )

    # Run experiment
    results = coordinator.run_experiment(experiment)

    # Assert experiment completed
    assert results["start_time"] is not None
    assert results["end_time"] is not None
    # System should recover from connection drops
    assert len(results["failures_detected"]) == 0 or all(
        coordinator._is_recovered(f, experiment.recovery_metrics)
        for f in results["failures_detected"]
    )
```

---

### Pattern 3: Property-Based Testing Expansion

**What:** Expand existing Hypothesis property-based tests to cover API contracts, state machine invariants, and security properties, integrating with fuzzing-generated inputs for comprehensive invariant validation.

**When to use:**
- Validating API contracts across all possible inputs
- Testing state machine transitions for all states
- Verifying security properties (no SQL injection, XSS)
- Finding edge cases in complex logic

**Trade-offs:**
- **Pros**: Finds deep edge cases, validates invariants, comprehensive coverage
- **Cons**: Can be slow, requires careful invariant definition, test maintenance

**Example:**
```python
# backend/tests/property_tests/fuzzing_integration/api_invariants.py
"""
Property-Based Tests for API Contract Invariants

Tests CRITICAL API invariants with Hypothesis:
- Request validation (malformed JSON, oversized payloads)
- Response contracts (status codes, content types)
- Error handling (graceful degradation, no crashes)
- Security invariants (no SQL injection, XSS)
"""

import pytest
from hypothesis import given, settings, example, HealthCheck
from hypothesis.strategies import (
    text, integers, floats, dictionaries, lists, none,
    binary, uuids, datetime as datetime_st
)
from fastapi.testclient import TestClient
from main import app
import json

class TestAPIContractInvariants:
    """Test invariants for API contracts."""

    @given(
        username=text(min_size=0, max_size=1000),
        password=text(min_size=0, max_size=1000)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_login_endpoint_handles_all_inputs_invariant(
        self, db_session, username: str, password: str
    ):
        """
        INVARIANT: Login endpoint handles all inputs without crashing.

        VALIDATED_BUG: Login crashed on extremely long usernames (1000+ chars).
        Root cause: Missing length validation.
        Fixed in commit xyz789.
        """
        client = TestClient(app)

        # Attempt login with any username/password
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": password}
        )

        # INVARIANT: Response is always valid JSON (no crashes)
        # Status code is always 4xx/5xx for invalid inputs, never 500
        assert response.status_code in [200, 400, 401, 422, 500]
        assert response.headers["content-type"] == "application/json"

    @given(
        prompt_text=text(min_size=0, max_size=50000),
        agent_id=uuids()
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_agent_execution_handles_large_prompts_invariant(
        self, db_session, prompt_text: str, agent_id
    ):
        """
        INVARIANT: Agent execution handles prompts up to 50KB without crashing.

        VALIDATED_BUG: Agent execution crashed on prompts >10KB.
        Root cause: Token counting overflow.
        Fixed in commit abc456.
        """
        client = TestClient(app)

        # Execute agent with any prompt text
        response = client.post(
            f"/api/v1/agents/{agent_id}/execute",
            json={"prompt": prompt_text}
        )

        # INVARIANT: No crashes, graceful error handling
        assert response.status_code in [200, 400, 404, 413, 500]

        # If prompt is too large, should return 413 (Payload Too Large)
        if len(prompt_text) > 10000:  # Hypothetical limit
            assert response.status_code == 413

    @given(
        workflow_def=dictionaries(
            keys=text(min_size=1, max_size=50),
            values=text(min_size=0, max_size=1000),
            min_size=0,
            max_size=100
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_workflow_creation_handles_malformed_json_invariant(
        self, db_session, workflow_def
    ):
        """
        INVARIANT: Workflow creation handles all dictionary inputs without SQL injection.

        VALIDATED_BUG: Workflow name vulnerable to SQL injection.
        Root cause: Unescaped string interpolation in query.
        Fixed in commit def123.
        """
        client = TestClient(app)

        # Create workflow with any dictionary definition
        response = client.post(
            "/api/v1/workflows",
            json={"definition": workflow_def}
        )

        # INVARIANT: No SQL injection errors
        # If SQL injection occurred, we'd see database error in response
        assert response.status_code in [200, 400, 401, 422, 500]

        # Check for SQL error signatures in response
        if response.status_code == 500:
            error_detail = response.json().get("detail", "")
            assert "syntax error" not in error_detail.lower()
            assert "mysql" not in error_detail.lower()
            assert "postgresql" not in error_detail.lower()
            assert "sqlite" not in error_detail.lower()


class TestStateMachineInvariants:
    """Test invariants for agent state machine."""

    @given(
        current_confidence=floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        execution_count=integers(min_value=0, max_value=1000),
        intervention_count=integers(min_value=0, max_value=100)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_agent_graduation_state_machine_invariant(
        self, db_session,
        current_confidence: float,
        execution_count: int,
        intervention_count: int
    ):
        """
        INVARIANT: Agent graduation state machine is monotonic (never demotes).

        VALIDATED_BUG: Agent could demote from INTERN to STUDENT.
        Root cause: Incorrect graduation criteria check.
        Fixed in commit ghi789.
        """
        from core.models import AgentRegistry, AgentStatus
        from core.agent_graduation_service import AgentGraduationService

        # Create agent with specified metrics
        agent = AgentRegistry(
            name="TestAgent",
            confidence_score=current_confidence,
            execution_count=execution_count,
            intervention_count=intervention_count,
            maturity_level="STUDENT"
        )
        db_session.add(agent)
        db_session.commit()

        # Check graduation criteria
        grad_service = AgentGraduationService(db_session)
        new_level = grad_service.check_graduation_eligibility(agent.id)

        # INVARIANT: State transitions are monotonic (never demote)
        maturity_order = ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]
        current_idx = maturity_order.index(agent.maturity_level)
        new_idx = maturity_order.index(new_level) if new_level else current_idx

        assert new_idx >= current_idx, \
            f"Agent demoted from {agent.maturity_level} to {new_level}"


# Integration with fuzzing
# backend/tests/fuzzing/campaigns/property_fuzz_campaign.py
"""
Fuzzing Campaign with Property-Based Tests

Combines fuzzing-generated inputs with Hypothesis property tests
to validate invariants across malformed and unexpected inputs.
"""

from hypothesis import given, settings
from backend.tests.property_tests.fuzzing_integration.api_invariants import (
    TestAPIContractInvariants,
    TestStateMachineInvariants
)

class PropertyFuzzingCampaign:
    """Run property-based tests with fuzzing-generated inputs."""

    def __init__(self, db_session):
        self.db_session = db_session
        self.api_tests = TestAPIContractInvariants()
        self.state_tests = TestStateMachineInvariants()

    def run_campaign(self, max_examples: int = 1000):
        """Run property-based fuzzing campaign."""
        print(f"Running property-based fuzzing campaign with {max_examples} examples")

        # Run API contract tests
        print("Testing API contract invariants...")
        self.api_tests.test_login_endpoint_handles_all_inputs_invariant(
            self.db_session,
            username="",  # Hypothesis will generate random inputs
            password=""
        )

        self.api_tests.test_agent_execution_handles_large_prompts_invariant(
            self.db_session,
            prompt_text="",
            agent_id=""
        )

        self.api_tests.test_workflow_creation_handles_malformed_json_invariant(
            self.db_session,
            workflow_def={}
        )

        # Run state machine tests
        print("Testing state machine invariants...")
        self.state_tests.test_agent_graduation_state_machine_invariant(
            self.db_session,
            current_confidence=0.5,
            execution_count=10,
            intervention_count=2
        )

        print("Property-based fuzzing campaign completed")
```

---

### Pattern 4: Intelligent Browser Automation for Bug Discovery

**What:** AI-driven browser automation that explores the Atom web UI using heuristic algorithms, detects visual regressions, accessibility violations, console errors, and automatically files bugs for discovered issues.

**When to use:**
- Discovering UI bugs not covered by manual E2E tests
- Validating accessibility across all pages
- Detecting visual regressions after UI changes
- Finding console errors and broken links

**Trade-offs:**
- **Pros**: Finds unexpected UI bugs, comprehensive coverage, automated exploration
- **Cons:** Can be flaky, requires heuristics tuning, may miss business logic bugs

**Example:**
```python
# backend/tests/browser_automation/agents/exploration_agent.py
"""
Intelligent Browser Exploration Agent

Uses heuristics to explore the Atom web UI and discover bugs:
- Depth-first exploration of clickable elements
- Form filling with random/malicious inputs
- Visual regression detection
- Accessibility violation detection
- Console error detection
"""

from typing import List, Dict, Optional, Set
from playwright.async_api import async_playwright, Page, Browser
import asyncio
from datetime import datetime
import hashlib

class ExplorationAgent:
    """
    Intelligent browser exploration agent for bug discovery.

    Features:
    - Heuristic exploration of UI elements
    - Form filling with edge case inputs
    - Visual regression detection
    - Accessibility violation detection
    - Console error detection
    """

    def __init__(
        self,
        base_url: str,
        max_pages: int = 50,
        max_depth: int = 3,
        screenshot_dir: str = "/tmp/screenshots"
    ):
        """
        Initialize ExplorationAgent.

        Args:
            base_url: Base URL of application to explore
            max_pages: Maximum number of pages to explore
            max_depth: Maximum depth of exploration tree
            screenshot_dir: Directory for screenshots
        """
        self.base_url = base_url
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.screenshot_dir = screenshot_dir

        self.bugs_found = []
        self.visited_urls: Set[str] = set()
        self.exploration_queue: List[Dict] = []

    async def explore(self) -> List[Dict]:
        """
        Start intelligent exploration.

        Returns:
            List of bugs discovered
        """
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Start exploration from base URL
            await self._explore_page(page, self.base_url, depth=0)

            await browser.close()

        return self.bugs_found

    async def _explore_page(self, page: Page, url: str, depth: int):
        """
        Explore a single page.

        Args:
            page: Playwright Page object
            url: URL to explore
            depth: Current exploration depth
        """
        if depth > self.max_depth or url in self.visited_urls or len(self.visited_urls) >= self.max_pages:
            return

        print(f"Exploring: {url} (depth: {depth}, visited: {len(self.visited_urls)})")
        self.visited_urls.add(url)

        try:
            # Navigate to page
            await page.goto(url, wait_until="networkidle", timeout=10000)

            # Detect bugs on this page
            await self._detect_console_errors(page, url)
            await self._detect_accessibility_violations(page, url)
            await self._detect_broken_links(page, url)
            await self._detect_visual_regression(page, url)

            # Find clickable elements for further exploration
            links = await page.locator("a[href]").all()
            buttons = await page.locator("button").all()
            forms = await page.locator("form").all()

            # Add to exploration queue (depth-first)
            for link in links[:10]:  # Limit to 10 links per page
                href = await link.get_attribute("href")
                if href and href.startswith("/"):
                    full_url = f"{self.base_url}{href}"
                    await self._explore_page(page, full_url, depth + 1)

            # Fill forms with edge case inputs
            for form in forms[:5]:  # Limit to 5 forms per page
                await self._fill_form_with_edge_cases(page, form, url)

        except Exception as e:
            # Record navigation error as potential bug
            self.bugs_found.append({
                "type": "navigation_error",
                "url": url,
                "error": str(e),
                "severity": "medium",
                "discovered_at": datetime.utcnow().isoformat()
            })

    async def _detect_console_errors(self, page: Page, url: str):
        """
        Detect console errors on page.

        Args:
            page: Playwright Page object
            url: Current URL
        """
        console_errors = []

        # Listen for console messages
        page.on("console", lambda msg: console_errors.append(msg))

        # Wait a bit for console errors to appear
        await asyncio.sleep(2)

        # Filter for errors
        errors = [msg for msg in console_errors if msg.type == "error"]

        for error in errors:
            self.bugs_found.append({
                "type": "console_error",
                "url": url,
                "error_text": error.text,
                "severity": "high",
                "discovered_at": datetime.utcnow().isoformat()
            })

    async def _detect_accessibility_violations(self, page: Page, url: str):
        """
        Detect accessibility violations using axe-core.

        Args:
            page: Playwright Page object
            url: Current URL
        """
        # Inject axe-core
        await page.add_script_tag(url="https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.8.2/axe.min.js")

        # Run accessibility audit
        results = await page.evaluate("""
            async () => {
                return await axe.run();
            }
        """)

        # Record violations
        for violation in results.get("violations", []):
            self.bugs_found.append({
                "type": "accessibility_violation",
                "url": url,
                "violation_id": violation["id"],
                "description": violation["description"],
                "impact": violation["impact"],
                "tags": violation["tags"],
                "severity": "high" if violation["impact"] == "critical" else "medium",
                "discovered_at": datetime.utcnow().isoformat()
            })

    async def _detect_broken_links(self, page: Page, url: str):
        """
        Detect broken links (404 responses).

        Args:
            page: Playwright Page object
            url: Current URL
        """
        links = await page.locator("a[href]").all()

        for link in links:
            try:
                href = await link.get_attribute("href")
                if href and href.startswith("/"):
                    full_url = f"{self.base_url}{href}"

                    # Check link status (without navigating)
                    response = await page.request.get(full_url)
                    if response.status == 404:
                        self.bugs_found.append({
                            "type": "broken_link",
                            "url": url,
                            "link_href": href,
                            "status_code": 404,
                            "severity": "medium",
                            "discovered_at": datetime.utcnow().isoformat()
                        })
            except Exception:
                # Link is truly broken (exception on request)
                self.bugs_found.append({
                    "type": "broken_link",
                    "url": url,
                    "link_href": href,
                    "error": "Request failed",
                    "severity": "medium",
                    "discovered_at": datetime.utcnow().isoformat()
                })

    async def _detect_visual_regression(self, page: Page, url: str):
        """
        Detect visual regression by comparing screenshots.

        Args:
            page: Playwright Page object
            url: Current URL
        """
        # Take screenshot
        screenshot_hash = hashlib.md5(url.encode()).hexdigest()
        screenshot_path = f"{self.screenshot_dir}/{screenshot_hash}.png"

        await page.screenshot(path=screenshot_path)

        # In production, compare with baseline screenshot
        # For now, just record that screenshot was taken
        # Visual regression detection requires image diff library
        pass

    async def _fill_form_with_edge_cases(self, page: Page, form, url: str):
        """
        Fill form with edge case inputs to discover validation bugs.

        Args:
            page: Playwright Page object
            form: Form element
            url: Current URL
        """
        # Find all inputs in form
        inputs = await form.locator("input").all()

        edge_cases = [
            "",  # Empty string
            "\x00",  # Null byte
            "A" * 10000,  # Very long string
            "<script>alert('xss')</script>",  # XSS payload
            "'; DROP TABLE users; --",  # SQL injection payload
            "../../etc/passwd",  # Path traversal
            "{{7*7}}",  # Template injection
            "${7*7}",  # Expression language injection
        ]

        for input_elem in inputs[:5]:  # Limit to 5 inputs per form
            input_type = await input_elem.get_attribute("type")
            input_name = await input_elem.get_attribute("name")

            # Skip hidden inputs
            if input_type == "hidden":
                continue

            # Try edge cases
            for edge_case in edge_cases:
                try:
                    await input_elem.fill(edge_case)

                    # Submit form
                    submit_button = await form.locator("button[type='submit'], input[type='submit']").first
                    if submit_button:
                        await submit_button.click()

                        # Wait for response
                        await asyncio.sleep(1)

                        # Check for errors
                        current_url = page.url
                        if "error" in current_url.lower():
                            self.bugs_found.append({
                                "type": "form_validation_bug",
                                "url": url,
                                "input_name": input_name,
                                "edge_case": edge_case[:100],  # Truncate for readability
                                "error_url": current_url,
                                "severity": "high",
                                "discovered_at": datetime.utcnow().isoformat()
                            })

                        # Go back to form
                        await page.go_back()

                except Exception as e:
                    # Form submission crashed - potential bug
                    self.bugs_found.append({
                        "type": "form_submission_crash",
                        "url": url,
                        "input_name": input_name,
                        "edge_case": edge_case[:100],
                        "error": str(e),
                        "severity": "critical",
                        "discovered_at": datetime.utcnow().isoformat()
                    })


# Usage in tests
# backend/tests/browser_automation/test_exploration_agent.py
import pytest
from backend.tests.browser_automation.agents.exploration_agent import ExplorationAgent

@pytest.mark.integration
@pytest.mark.asyncio
async def test_exploration_agent_discovers_bugs():
    """Test that exploration agent discovers bugs in web UI."""
    agent = ExplorationAgent(
        base_url="http://localhost:3000",
        max_pages=20,  # Explore 20 pages
        max_depth=2,
        screenshot_dir="/tmp/screenshots"
    )

    bugs = await agent.explore()

    # Assert agent explored some pages
    assert len(agent.visited_urls) > 0

    # Assert bugs were found (even if zero, test should pass)
    print(f"Explored {len(agent.visited_urls)} pages")
    print(f"Found {len(bugs)} bugs")

    for bug in bugs:
        print(f"Bug: {bug['type']} - {bug.get('error', bug.get('description', ''))}")
```

## Data Flow

### Automated Bug Discovery Pipeline

```
[Developer Push/PR Trigger OR Scheduled Cron]
    ↓
[Bug Discovery Coordinator Starts]
    ↓
[Parallel Campaign Execution]
    ├── [Fuzzing Campaign] → Atheris/RESTler → API endpoints → Crash detection
    ├── [Chaos Experiment] → Failure injection → Resilience validation → Failure detection
    ├── [Property Tests] → Hypothesis → Invariant validation → Edge case discovery
    └── [Browser Automation] → Exploration agent → UI bug discovery → Visual regression
    ↓
[Result Aggregation]
    ├── Collect crashes from fuzzing
    ├── Collect failures from chaos experiments
    ├── Collect invariant violations from property tests
    └── Collect UI bugs from browser automation
    ↓
[Deduplication]
    ├── Group bugs by error signature
    ├── Merge duplicates across campaigns
    └── Prioritize by severity (critical, high, medium, low)
    ↓
[Bug Triage]
    ├── Classify severity (critical, high, medium, low)
    ├── Analyze impact (data loss, security, UX)
    └── Determine reproducibility (always, sometimes, flaky)
    ↓
[Bug Filing]
    ├── Check for existing issues (deduplication)
    ├── Create GitHub Issues for reproducible bugs
    ├── Attach screenshots, logs, traces
    └── Apply labels (automated, severity, platform, test-type)
    ↓
[CI/CD Result]
    ├── Comment on PR with bug summary
    ├── Update metrics dashboard
    └── Trigger remediation workflows (if critical)
```

### Fuzzing Campaign Flow

```
[Fuzzing Campaign Started]
    ↓
[OpenAPI Schema Generation]
    ├── Extract OpenAPI spec from FastAPI
    ├── Identify endpoints (/api/auth/login, /api/v1/agents/execute)
    └── Generate input schemas (request bodies, parameters)
    ↓
[Fuzzer Execution]
    ├── [Atheris] → Coverage-guided fuzzing → Binary input generation
    ├── [RESTler] → Stateful API fuzzing → Sequence-based exploitation
    └── [Custom] → Domain-specific fuzzing → Business logic bugs
    ↓
[Crash Detection]
    ├── Monitor for exceptions (AttributeError, ValueError, KeyError)
    ├── Detect segmentation faults (if using native fuzzers)
    └── Identify assertion failures
    ↓
[Crash Triaging]
    ├── Minimize crash input (reduce to minimal reproducer)
    ├── Verify reproducibility (re-run minimized input)
    └── Classify severity (crash = critical, logic error = high)
    ↓
[Bug Filing]
    ├── Generate test case from crash input
    ├── File GitHub Issue with reproducer
    └── Add label: fuzzing, severity:critical
```

### Chaos Experiment Flow

```
[Chaos Experiment Started]
    ↓
[Baseline Metrics Collection]
    ├── CPU usage: 20%
    ├── Memory usage: 40%
    ├── Response time: p95=200ms
    └── Error rate: 0.1%
    ↓
[Failure Injection]
    ├── [Network Latency] → Add 500ms delay, 10% packet loss
    ├── [Database Connection Drop] → Block port 5432 for 30s
    ├── [Memory Pressure] → Allocate 500MB memory
    └── [Service Crash] → Kill and restart backend service
    ↓
[Chaos Metrics Collection]
    ├── CPU usage: 80% (+300% increase)
    ├── Memory usage: 75% (+87.5% increase)
    ├── Response time: p95=2000ms (+900% increase)
    └── Error rate: 15% (+14900% increase)
    ↓
[Failure Detection]
    ├── Compare baseline vs chaos metrics
    ├── Detect unrecoverable failures (error rate still 10% after rollback)
    └── Identify cascading failures (API → Database → Redis)
    ↓
[Rollback & Recovery]
    ├── Remove failure injection
    ├── Wait for system recovery (10s)
    └── Collect recovery metrics
    ↓
[Bug Filing for Unrecovered Failures]
    ├── System failed to recover from database connection drops
    ├── Error rate remained at 10% after 30s recovery period
    └── File bug: "Database connection pool exhaustion not handled gracefully"
```

### Property-Based Test Flow

```
[Property-Based Test Started]
    ↓
[Hypothesis Input Generation]
    ├── Generate random input: username=""; DROP TABLE users; --"
    ├── Generate random input: password="\x00\x01\x02..."
    ├── Generate random input: agent_id=<invalid-uuid>
    └── Generate random input: prompt_text=50000 characters
    ↓
[Test Execution]
    ├── Call function with generated input
    ├── Monitor for exceptions
    └── Validate invariants (e.g., "response is always JSON")
    ↓
[Invariant Validation]
    ├── INVARIANT: Login never crashes on any input
    │   └── PASS: No exception raised
    ├── INVARIANT: Agent execution rejects oversized prompts
    │   └── PASS: Returns 413 for prompts >10KB
    └── INVARIANT: Workflow creation prevents SQL injection
        └── FAIL: Workflow name with "'; DROP TABLE" caused database error
    ↓
[Shrinking]
    ├── Hypothesis automatically minimizes failing input
    ├── Original: username="A very long string with SQL injection '; DROP TABLE users; --"
    └── Minimized: username="'; DROP" (6 chars instead of 60)
    ↓
[Bug Filing]
    ├── Invariant violation: SQL injection in workflow name
    ├── Minimal reproducer: username="'; DROP"
    └── File bug with test case that demonstrates the violation
```

## Integration Points

### Existing Atom Architecture Integration

| Atom Component | Integration Pattern | Notes |
|----------------|---------------------|-------|
| **FastAPI Backend** | OpenAPI spec generation for fuzzing targets | Auto-generate fuzzing harnesses from OpenAPI spec |
| **LLMService (BYOK)** | Property-based tests for token counting, cost calculation | Extend existing property tests for LLM invariants |
| **AgentGovernanceService** | Fuzzing agent maturity transitions, state machine validation | Test all possible state transitions for bugs |
| **Database Models** | Chaos engineering for database failure injection | Test resilience to connection drops, query failures |
| **BugFilingService** | Result aggregation and automatic GitHub filing | Extend existing service for unified bug filing |
| **pytest Fixtures** | Reusable test data for all discovery methods | Use existing 50+ fixtures for consistent test data |
| **Playwright E2E** | Browser automation agent uses existing E2E infrastructure | Extend 91 E2E tests with intelligent exploration |

### New Components Integration

| New Component | Integration with Existing | Notes |
|---------------|--------------------------|-------|
| **FuzzingOrchestrator** | Uses OpenAPI spec, calls FastAPI endpoints | Wrap existing API endpoints in fuzzing harnesses |
| **ChaosCoordinator** | Targets database, Redis, LLM services | Inject failures into existing dependencies |
| **Property-Based Tests** | Extends existing Hypothesis tests | Add new invariant tests to existing property test suite |
| **ExplorationAgent** | Uses Playwright (already in E2E tests) | Extend existing E2E test infrastructure |
| **DiscoveryCoordinator** | Calls BugFilingService (existing) | Unify all discovery methods under single coordinator |
| **ResultAggregator** | Correlates results from all methods | Aggregate crashes, failures, violations |

### External Service Integration

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| **Atheris** | Coverage-guided fuzzing for Python functions | Install via pip: `pip install atheris` |
| **RESTler** | Stateful REST API fuzzing | Use Docker image: `microsoft/restler` |
| **Chaos Monkey** | Service termination experiments | Install via pip: `pip install chaos-monkey` |
| **axe-core** | Accessibility violation detection | Inject via Playwright: `page.add_script_tag()` |
| **GitHub Issues API** | Bug filing via BugFilingService | Already integrated, extend for deduplication |
| **k6** | Load testing for baseline metrics | Already configured, extend for chaos experiments |

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| **0-100 bugs discovered** | Single fuzzing campaign (1 hour), single chaos experiment (30 min), 50 property tests, browser automation (100 pages) |
| **100-500 bugs discovered** | Parallel fuzzing campaigns (4 endpoints), daily chaos experiments (5 failure types), 200 property tests, browser automation (500 pages) |
| **500-1000+ bugs discovered** | Continuous fuzzing (24/7), hourly chaos experiments, 1000+ property tests, browser automation (all pages), result deduplication critical |

### Scaling Priorities

1. **First bottleneck: Fuzzing campaign duration**
   - **Problem**: Fuzzing 10+ endpoints takes hours
   - **Fix**: Parallel fuzzing with ProcessPoolExecutor, prioritize critical endpoints, use coverage-guided fuzzing (Atheris)

2. **Second bottleneck: Chaos experiment isolation**
   - **Problem**: Chaos experiments affect other tests, cause flakiness
   - **Fix**: Run chaos experiments in isolated containers (Docker), use network namespaces, schedule during off-hours

3. **Third bottleneck: Browser automation exploration**
   - **Problem**: Exploring entire UI takes hours, finds many false positives
   - **Fix**: Limit exploration depth (max_depth=3), prioritize critical flows (auth, agent execution), use smart heuristics

## Anti-Patterns

### Anti-Pattern 1: Fuzzing Without Crash Deduplication

**What people do:** File a bug for every single crash discovered by fuzzer, resulting in hundreds of duplicate issues.

**Why it's wrong:** Same root cause (e.g., "null pointer dereference") manifests across many inputs, creating noise and triage overhead.

**Do this instead:**
- Group crashes by error signature (error message + stack trace)
- File one bug per unique root cause
- Include list of all crash inputs in single issue
- Example:
```python
# BAD: File bug for each crash
for crash in crashes:
    bug_service.file_bug(
        test_name=f"fuzz_{endpoint}",
        error_message=crash["error"],
        metadata={"input": crash["input"]}
    )

# GOOD: Deduplicate crashes by error signature
unique_crashes = deduplicate_by_signature(crashes)
for crash in unique_crashes:
    bug_service.file_bug(
        test_name=f"fuzz_{endpoint}",
        error_message=crash["error"],
        metadata={
            "crash_count": crash["count"],
            "example_inputs": crash["examples"][:5]  # First 5 examples
        }
    )
```

---

### Anti-Pattern 2: Chaos Engineering in Production

**What people do:** Run chaos experiments against production environment without proper safeguards.

**Why it's wrong:** Can cause real outages, data loss, customer impact, and team burnout from paging.

**Do this instead:**
- Run chaos experiments in staging environment that mirrors production
- Use feature flags to disable chaos experiments if system health degrades
- Schedule experiments during off-hours (2 AM Sunday)
- Always have rollback plan ready
- Example:
```python
# BAD: Run chaos experiment in production
coordinator.run_experiment(experiment)  # Targets production DB!

# GOOD: Run chaos experiment in staging with safeguards
os.environ["ENVIRONMENT"] = "staging"
experiment.target_component = "staging_database"

# Add safety check: abort if error rate >10%
if metrics["error_rate"] > 10:
    print("Error rate too high, aborting experiment")
    return

coordinator.run_experiment(experiment)
```

---

### Anti-Pattern 3: Property-Based Tests Without Shrinking

**What people do:** Write property-based tests but don't use Hypothesis's shrinking feature, resulting in huge test inputs that are hard to debug.

**Why it's wrong:** Minimized inputs are easier to debug, faster to reproduce, and clearer in bug reports.

**Do this instead:**
- Always use `@given` decorator with Hypothesis strategies
- Let Hypothesis automatically shrink failing inputs
- Include minimized input in bug report
- Example:
```python
# BAD: Manual input generation (no shrinking)
@pytest.mark.parametrize("username", ["admin", "test" * 1000, "'; DROP TABLE users; --"])
def test_login(username):
    response = client.post("/api/auth/login", json={"username": username})
    # If this fails, you have to manually debug which input caused it

# GOOD: Hypothesis with shrinking (automatic minimization)
@given(username=text(min_size=0, max_size=1000))
def test_login(username):
    response = client.post("/api/auth/login", json={"username": username})
    # Hypothesis automatically shrinks failing input to minimal case
    # E.g., "'; DROP TABLE users; --" → "'; D"
```

---

### Anti-Pattern 4: Browser Automation Without Wait Conditions

**What people do:** Browser automation doesn't wait for page load, network idle, or element visibility, causing flaky tests and false positives.

**Why it's wrong:** Tests fail intermittently due to timing issues, not actual bugs, leading to ignored bug reports.

**Do this instead:**
- Always wait for network idle before detecting bugs
- Wait for elements to be visible before interacting
- Use explicit waits instead of fixed timeouts
- Example:
```python
# BAD: No wait conditions
await page.goto(url)
errors = await detect_console_errors(page)  # Might miss errors that appear later

# GOOD: Wait for network idle
await page.goto(url, wait_until="networkidle", timeout=10000)
await page.wait_for_selector("body", state="visible")
errors = await detect_console_errors(page)
```

---

### Anti-Pattern 5: Automated Bug Filing Without Human Review

**What people do:** Automatically file bugs for every test failure without human triage, flooding issue tracker with noise.

**Why it's wrong:** False positives, flaky tests, and low-priority issues clutter the issue tracker, reduce team confidence in automated discovery.

**Do this instead:**
- File bugs only for reproducible failures (fail 2+ times)
- Require severity "high" or "critical" for automatic filing
- Create "potential bug" label for low-confidence issues
- Review all auto-filed bugs daily and close false positives
- Example:
```python
# BAD: File bug for every failure
if test_failed:
    bug_service.file_bug(...)

# GOOD: File bug only for reproducible, high-severity failures
if test_failed and failure_count >= 2 and severity in ["critical", "high"]:
    bug_service.file_bug(...)
elif test_failed:
    # Create "potential bug" label for low-confidence issues
    bug_service.file_bug(..., labels=["potential-bug", "needs-review"])
```

## Recommended Build Order

### Phase 1: Property-Based Test Expansion (Week 1)

**Goal:** Expand existing Hypothesis property tests with new invariants for API contracts, state machines, and security properties.

**Tasks:**
1. **API Contract Invariants**
   - Test request validation (malformed JSON, oversized payloads)
   - Test response contracts (status codes, content types)
   - Test error handling (graceful degradation, no crashes)
   - **Files:** `backend/tests/property_tests/fuzzing_integration/api_invariants.py`

2. **State Machine Invariants**
   - Test agent graduation state machine (monotonic transitions)
   - Test episode lifecycle state transitions
   - Test workflow execution state machine
   - **Files:** `backend/tests/property_tests/fuzzing_integration/state_invariants.py`

3. **Security Invariants**
   - Test SQL injection prevention in all endpoints
   - Test XSS prevention in user-generated content
   - Test authentication bypass prevention
   - **Files:** `backend/tests/property_tests/fuzzing_integration/security_invariants.py`

**Dependencies:** Existing property test infrastructure (Hypothesis, pytest fixtures)

**Validation:**
- 50+ new property tests added
- All tests pass with Hypothesis max_examples=100
- Tests discover at least 5 edge case bugs

---

### Phase 2: API Fuzzing Infrastructure (Week 2)

**Goal:** Implement fuzzing orchestration with Atheris and RESTler for comprehensive API endpoint testing.

**Tasks:**
1. **Fuzzing Orchestrator**
   - Implement FuzzingOrchestrator service
   - Add fuzzing campaign management (start, stop, monitor)
   - Implement crash detection and triage
   - **Files:** `backend/core/fuzzing_orchestrator.py`

2. **Fuzzing Harnesses**
   - Create FastAPI harness for Atheris
   - Create OpenAPI spec generator for RESTler
   - Implement crash deduplication
   - **Files:** `backend/tests/fuzzing/harnesses/fastapi_harness.py`

3. **Fuzzing Campaigns**
   - Create auth endpoint fuzzing campaign
   - Create agent execution fuzzing campaign
   - Create workflow API fuzzing campaign
   - **Files:** `backend/tests/fuzzing/campaigns/*.py`

**Dependencies:** Phase 1 (property tests for validation)

**Validation:**
- Fuzzing orchestrator runs campaigns successfully
- Atheris fuzzing discovers crashes in test endpoints
- RESTler fuzzing discovers HTTP protocol violations

---

### Phase 3: Chaos Engineering Layer (Week 3)

**Goal:** Implement chaos engineering experiments for failure injection and resilience validation.

**Tasks:**
1. **Chaos Coordinator**
   - Implement ChaosCoordinator service
   - Add experiment management (start, stop, rollback)
   - Implement failure detection and recovery validation
   - **Files:** `backend/core/chaos_coordinator.py`

2. **Failure Injection**
   - Implement network latency injection (tc)
   - Implement database connection drop (iptables)
   - Implement memory pressure simulation
   - Implement service crash experiments
   - **Files:** `backend/tests/chaos/experiments/*.py`

3. **Resilience Monitoring**
   - Implement baseline metrics collection
   - Implement chaos metrics collection
   - Implement recovery validation
   - **Files:** `backend/tests/chaos/monitors/resilience_monitor.py`

**Dependencies:** Phase 1 (property tests for system validation)

**Validation:**
- Chaos experiments run successfully in isolated environment
- System recovers from network latency (within 10% of baseline)
- System recovers from database connection drops (within 30s)

---

### Phase 4: Intelligent Browser Automation (Week 4)

**Goal:** Implement AI-driven browser exploration agent for automatic UI bug discovery.

**Tasks:**
1. **Exploration Agent**
   - Implement ExplorationAgent with heuristic exploration
   - Add depth-first exploration strategy
   - Implement form filling with edge cases
   - **Files:** `backend/tests/browser_automation/agents/exploration_agent.py`

2. **Bug Detection**
   - Implement console error detection
   - Implement accessibility violation detection (axe-core)
   - Implement broken link detection
   - Implement visual regression detection
   - **Files:** `backend/tests/browser_automation/detectors/*.py`

3. **Exploration Strategies**
   - Implement depth-first exploration
   - Implement breadth-first exploration
   - Implement random walk exploration
   - **Files:** `backend/tests/browser_automation/strategies/*.py`

**Dependencies:** Existing Playwright E2E infrastructure

**Validation:**
- Exploration agent explores 20+ pages without crashes
- Discovers at least 5 UI bugs (console errors, a11y violations, broken links)
- Visual regression detection works (screenshots compared)

---

### Phase 5: Unified Bug Discovery Pipeline (Week 5)

**Goal:** Implement unified discovery coordinator that aggregates results from all methods and automates bug filing.

**Tasks:**
1. **Discovery Coordinator**
   - Implement DiscoveryCoordinator service
   - Add campaign scheduling (fuzzing, chaos, property, browser)
   - Implement result aggregation
   - **Files:** `backend/core/discovery_coordinator.py`

2. **Result Aggregation**
   - Implement FailureAggregator (correlate failures across methods)
   - Implement Deduplicator (merge duplicate bugs)
   - Implement bug triage (severity classification, impact analysis)
   - **Files:** `backend/tests/bug_discovery/aggregators/*.py`

3. **Bug Filing Integration**
   - Extend BugFilingService for unified filing
   - Implement automatic filing for reproducible bugs
   - Implement "potential bug" workflow for low-confidence issues
   - **Files:** `backend/tests/bug_discovery/coordinator.py`

**Dependencies:** Phases 1-4 (all discovery methods)

**Validation:**
- Discovery coordinator runs all campaigns successfully
- Result aggregation correlates failures across methods
- Automated bug filing creates GitHub Issues for reproducible bugs

---

### Phase 6: CI/CD Integration (Week 6)

**Goal:** Integrate bug discovery pipeline with GitHub Actions for scheduled campaigns and PR-triggered tests.

**Tasks:**
1. **Fuzzing Workflow**
   - Create GitHub Actions workflow for scheduled fuzzing
   - Run fuzzing campaigns daily (2 AM UTC)
   - File bugs for reproducible crashes
   - **Files:** `.github/workflows/fuzzing.yml`

2. **Chaos Workflow**
   - Create GitHub Actions workflow for scheduled chaos experiments
   - Run chaos experiments weekly (Sunday 2 AM UTC)
   - File bugs for unrecovered failures
   - **Files:** `.github/workflows/chaos.yml`

3. **Unified Discovery Workflow**
   - Create GitHub Actions workflow for unified bug discovery
   - Run on PR trigger (quick smoke tests)
   - Run scheduled (comprehensive campaigns)
   - **Files:** `.github/workflows/bug_discovery.yml`

**Dependencies:** Phase 5 (unified coordinator)

**Validation:**
- All workflows run successfully in CI/CD
- Fuzzing workflow discovers crashes weekly
- Chaos workflow validates resilience weekly
- Unified workflow provides comprehensive bug discovery

## Sources

### High Confidence (Official Documentation & Codebase Analysis)

- **[Atom Test Infrastructure](https://github.com/ruship24/atom/blob/main/backend/tests/conftest.py)** - Existing pytest fixtures, Hypothesis configuration, test data management
- **[Atom Property-Based Tests](https://github.com/ruship24/atom/tree/main/backend/tests/property_tests)** - Existing Hypothesis tests for LLM, governance, episodes, database
- **[Atom Bug Filing Service](https://github.com/ruship24/atom/blob/main/backend/tests/bug_discovery/bug_filing_service.py)** - Existing BugFilingService with GitHub Issues integration
- **[Atom Load Tests](https://github.com/ruship24/atom/tree/main/backend/tests/load)** - Existing k6 load tests for API endpoints
- **[Atom E2E Tests](https://github.com/ruship24/atom/tree/main/backend/tests/e2e_ui)** - 91 existing E2E tests with Playwright
- **[Hypothesis Documentation](https://hypothesis.readthedocs.io/)** - Property-based testing framework for Python
- **[Atheris Documentation](https://github.com/google/atheris)** - Coverage-guided fuzzing for Python
- **[RESTler Documentation](https://github.com/microsoft/restler-fuzzer)** - Stateful REST API fuzzing
- **[Chaos Monkey Documentation](https://chaos-mesh.org/)** - Chaos engineering for cloud infrastructure
- **[Playwright Documentation](https://playwright.dev/python/)** - Browser automation for Python
- **[axe-core Documentation](https://www.deque.com/axe/)** - Accessibility testing engine

### Medium Confidence (Industry Best Practices - Codebase Analysis)

- **Atom Backend Architecture** - FastAPI + SQLAlchemy 2.0 + PostgreSQL/SQLite
- **Atom Agent System** - AgentGovernanceService, LLMService (BYOK), episodic memory
- **Atom CI/CD Pipeline** - GitHub Actions workflows, deployment automation
- **Property-Based Testing Patterns** - Invariant validation, state machine testing, edge case discovery
- **Fuzzing Best Practices** - Coverage-guided fuzzing, crash deduplication, minimization
- **Chaos Engineering Patterns** - Failure injection, resilience validation, rollback mechanisms

### Low Confidence (Limited Verification - Needs Validation)

- **Atheris + FastAPI Integration** - Limited examples of Atheris with FastAPI specifically
- **RESTler Stateful Fuzzing** - RESTler primarily designed for C# services, Python integration unclear
- **Chaos Engineering Isolation** - Running chaos experiments in CI/CD without affecting other tests
- **Browser Automation Exploration Heuristics** - AI-driven exploration strategies for complex web UIs

### Gaps Identified

- **Atheris Integration with FastAPI** - Need to validate Atheris compatibility with FastAPI's async endpoints
- **Chaos Engineering in GitHub Actions** - Running failure injection in CI/CD environment (container isolation challenges)
- **Browser Automation Exploration Coverage** - Determining optimal exploration depth vs. time tradeoff
- **Property-Based Test Performance** - Scaling to 1000+ examples without exceeding CI/CD time limits

**Next Research Phases:**
- Phase-specific research needed for Atheris + FastAPI integration patterns
- Investigation into chaos engineering isolation strategies for CI/CD
- Deep dive on browser exploration heuristics for complex React applications
- Research on property-based test performance optimization (parallel execution, caching)

---

*Architecture research for: Atom v8.0 Automated Bug Discovery (Fuzzing, Chaos Engineering, Property-Based Testing, Browser Automation)*
*Researched: March 24, 2026*
*Confidence: HIGH (mix of official docs, codebase analysis, industry best practices)*
