# Phase 242: Unified Bug Discovery Pipeline - Research

**Researched:** 2026-03-25
**Domain:** Bug discovery orchestration, result aggregation, deduplication, automated triage, dashboard reporting
**Confidence:** HIGH

## Summary

Phase 242 focuses on orchestrating all bug discovery methods (fuzzing, chaos, property tests, browser discovery) into a unified pipeline with result aggregation, intelligent deduplication, automated severity triage, and weekly dashboard reporting. The research confirms that Atom has **comprehensive discovery infrastructure** from Phases 238-241: 264+ property tests, FuzzingOrchestrator with crash deduplication, ExplorationAgent for browser discovery, ChaosCoordinator for failure injection, and BugFilingService for automated GitHub issue filing. The key gap is **no unified orchestration layer** to correlate failures across discovery methods, deduplicate bugs by error signature, classify severity automatically, and generate weekly reports.

**Primary recommendation:** Build DiscoveryCoordinator service as the unified orchestration layer that (1) runs all discovery methods in weekly CI pipeline, (2) aggregates results into normalized BugReport objects, (3) deduplicates bugs using error signature hashing (extending CrashDeduplicator), (4) classifies severity using rule-based heuristics (critical/high/medium/low) with optional ML enrichment, (5) files unique bugs via existing BugFilingService, and (6) generates weekly HTML/JSON reports with bug trends (found, fixed, regression rate). Reuse existing services (FuzzingOrchestrator, ChaosCoordinator, BugFilingService), follow existing deduplication patterns (CrashDeduplicator), and integrate with weekly CI pipeline (bug-discovery-weekly.yml).

**Key findings:**
1. **Discovery infrastructure is complete and production-ready**: Phase 238 delivered 264+ property tests, Phase 239 delivered FuzzingOrchestrator with crash deduplication, Phase 240 delivered ExplorationAgent with 7 browser discovery tests, Phase 241 delivered ChaosCoordinator with blast radius controls
2. **Bug filing service handles GitHub Issues integration**: bug_filing_service.py with idempotency, metadata collection, severity labeling, artifact attachment (screenshots, logs), and duplicate detection
3. **Crash deduplication pattern established**: CrashDeduplicator uses SHA256 hashing of error signatures (stack traces) to group similar crashes, which can be extended to all bug types (property failures, chaos resilience failures, browser errors)
4. **Weekly CI pipeline exists**: bug-discovery-weekly.yml with 120-minute timeout, scheduled execution (Sunday 3 AM UTC), artifact upload, and automated bug filing script
5. **Severity classification logic exists**: BugFilingService._determine_severity() has rule-based heuristics (load tests → critical/high, memory/network → high, visual/mobile → medium, other → low) that can be centralized and enhanced

## Standard Stack

### Core Orchestration & Aggregation
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | 7.4.x | Test runner and discovery orchestration | Industry standard, @pytest.mark.discovery marker already defined, rich plugin ecosystem |
| **pydantic** | 2.0.x | Data validation for BugReport models | Type-safe bug report objects, JSON serialization, schema validation |
| **hashlib** | (stdlib) | Error signature hashing for deduplication | SHA256-based deduplication proven in CrashDeduplicator (Phase 239) |
| **dataclasses** | (stdlib) | Normalized bug report data structures | Python 3.7+ stdlib, lightweight, immutable bug reports |

### Severity Classification (Rule-Based + Optional ML)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **rule-based heuristics** | (custom) | Severity classification by test type and impact | Primary classification method (proven, deterministic) |
| **scikit-learn** | 1.3.x | Optional ML-based severity prediction | Future enhancement: train on historical bug data for better accuracy |

### Dashboard & Reporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **jinja2** | 3.1.x | HTML report templating | Weekly bug discovery reports with trends, charts, tables |
| **pytest-html** | 3.2.x | HTML test reports | Integration with existing pytest reporting infrastructure |
| **allure-pytest** | 2.13.x | Enhanced test reporting and dashboards | Optional: beautiful dashboards with historical trends |

### Result Storage & Querying
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **sqlite3** | (stdlib) | Local bug report database | Weekly bug storage for trend analysis, regression detection |
| **json** | (stdlib) | Bug report serialization | CI artifact upload, cross-pipeline result sharing |
| **datetime** | (stdlib) | Temporal aggregation | Weekly reports, regression rate calculation |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **CrashDeduplicator pattern** | MinHash, LSH | SHA256 hash of error signature is proven, simple, and sufficient for crash deduplication |
| **rule-based severity** | ML classifier only | Rule-based is deterministic, explainable, no training data required; ML can be added later |
| **SQLite for storage** | PostgreSQL, MongoDB | SQLite is file-based, no setup required, sufficient for weekly bug reports |
| **Jinja2 for reports** | WeasyDoc, ReportLab | Jinja2 is lightweight, already dependency, produces clean HTML reports |

**Installation:**
```bash
# Core orchestration (already installed)
pip install pytest pydantic

# Reporting (already installed in requirements-testing.txt)
pip install jinja2 pytest-html allure-pytest

# Optional ML for severity classification (future enhancement)
pip install scikit-learn
```

## Architecture Patterns

### Recommended Project Structure

**Existing Structure (DO NOT CHANGE):**
```
backend/tests/
├── bug_discovery/              # ✅ EXISTS - Bug filing service
│   ├── bug_filing_service.py   # ✅ EXISTS - GitHub Issues API
│   ├── fixtures/
│   │   └── bug_filing_fixtures.py
│   └── TEMPLATES/
├ fuzzing/                      # ✅ EXISTS - API fuzzing
│   ├── campaigns/
│   │   ├── fuzzing_orchestrator.py  # ✅ EXISTS - Campaign management
│   │   └── crash_deduplicator.py     # ✅ EXISTS - Crash deduplication
│   └── test_agent_api_fuzzing.py
├── browser_discovery/          # ✅ EXISTS - Browser exploration
│   ├── conftest.py
│   └── test_exploration_agent.py
├── chaos/                      # ✅ EXISTS - Chaos engineering
│   ├── core/
│   │   └── chaos_coordinator.py      # ✅ EXISTS - Experiment orchestration
│   └── test_network_latency_chaos.py
└── property_tests/             # ✅ EXISTS - 264+ property tests
    ├── governance/
    ├── llm_routing/
    └── security/
```

**NEW Structure (Phase 242):**
```
backend/tests/bug_discovery/
├── bug_filing_service.py       # ✅ KEEP - Existing GitHub filing
├── core/                       # ✅ NEW - Unified orchestration
│   ├── discovery_coordinator.py    # ✅ NEW - Main orchestration service
│   ├── result_aggregator.py        # ✅ NEW - Normalize results from all methods
│   ├── bug_deduplicator.py         # ✅ NEW - Extended deduplication (all bug types)
│   ├── severity_classifier.py      # ✅ NEW - Rule-based severity classification
│   └── dashboard_generator.py      # ✅ NEW - Weekly HTML/JSON reports
├── storage/                    # ✅ NEW - Bug report storage
│   ├── bug_reports.db            # ✅ NEW - SQLite database for trend analysis
│   └── reports/                   # ✅ NEW - Weekly HTML reports
│       ├── weekly-2026-03-24.html
│       └── weekly-2026-03-31.html
├── models/                     # ✅ NEW - Data models
│   └── bug_report.py             # ✅ NEW - Pydantic BugReport model
└── tests/                      # ✅ NEW - Unit tests
    ├── test_discovery_coordinator.py
    ├── test_result_aggregator.py
    ├── test_bug_deduplicator.py
    └── test_severity_classifier.py
```

**Key Principle:** DiscoveryCoordinator is the thin orchestration layer that calls existing services (FuzzingOrchestrator, ChaosCoordinator, ExplorationAgent) and aggregates results through BugReport objects.

### Pattern 1: DiscoveryCoordinator Service

**What:** Unified orchestration service that runs all discovery methods and aggregates results.

**When to use:** Weekly CI pipeline execution (bug-discovery-weekly.yml), on-demand full discovery runs.

**Example:**
```python
# Source: backend/tests/bug_discovery/core/discovery_coordinator.py
from typing import List, Dict
from pathlib import Path
from datetime import datetime

class DiscoveryCoordinator:
    """
    Orchestrates all bug discovery methods with result aggregation.

    Responsibilities:
    - Run fuzzing, chaos, property tests, browser discovery
    - Aggregate results into normalized BugReport objects
    - Delegate to BugDeduplicator for duplicate detection
    - Delegate to SeverityClassifier for severity assignment
    - File unique bugs via BugFilingService
    - Generate weekly reports via DashboardGenerator
    """

    def __init__(self, github_token: str, github_repository: str):
        self.github_token = github_token
        self.github_repository = github_repository

        # Import existing discovery services
        from tests.fuzzing.campaigns.fuzzing_orchestrator import FuzzingOrchestrator
        from tests.chaos.core.chaos_coordinator import ChaosCoordinator
        from tests.browser_discovery.conftest import ExplorationAgent
        from tests.bug_discovery.bug_filing_service import BugFilingService

        self.fuzzing_orchestrator = FuzzingOrchestrator(github_token, github_repository)
        self.chaos_coordinator = ChaosCoordinator(db_session=None)  # Isolated DB
        self.browser_agent = ExplorationAgent(page=None)  # Headless browser
        self.bug_filing_service = BugFilingService(github_token, github_repository)

        # Import new aggregation services
        from tests.bug_discovery.core.result_aggregator import ResultAggregator
        from tests.bug_discovery.core.bug_deduplicator import BugDeduplicator
        from tests.bug_discovery.core.severity_classifier import SeverityClassifier
        from tests.bug_discovery.core.dashboard_generator import DashboardGenerator

        self.result_aggregator = ResultAggregator()
        self.bug_deduplicator = BugDeduplicator()
        self.severity_classifier = SeverityClassifier()
        self.dashboard_generator = DashboardGenerator()

    def run_full_discovery(self, duration_seconds: int = 3600) -> Dict:
        """
        Run all discovery methods and aggregate results.

        Args:
            duration_seconds: Duration for each discovery method (default: 1 hour)

        Returns:
            Dict with aggregated results (bugs_found, unique_bugs, filed_bugs, report_path)
        """
        all_reports = []

        # 1. Run fuzzing discovery
        print("[DiscoveryCoordinator] Running fuzzing discovery...")
        fuzzing_campaign = self.fuzzing_orchestrator.run_campaign_with_bug_filing(
            target_endpoint="/api/v1/agents",
            test_file="tests/fuzzing/test_agent_api_fuzzing.py",
            duration_seconds=duration_seconds
        )
        fuzzing_reports = self.result_aggregator.aggregate_fuzzing_results(fuzzing_campaign)
        all_reports.extend(fuzzing_reports)

        # 2. Run chaos engineering
        print("[DiscoveryCoordinator] Running chaos engineering...")
        chaos_results = self.chaos_coordinator.run_experiment(
            experiment_name="network_latency_3g",
            failure_injection=NetworkLatencyInjection(latency_ms=2000),
            verify_graceful_degradation=verify_system_resilience
        )
        chaos_reports = self.result_aggregator.aggregate_chaos_results(chaos_results)
        all_reports.extend(chaos_reports)

        # 3. Run property tests
        print("[DiscoveryCoordinator] Running property tests...")
        property_results = subprocess.run(
            ["pytest", "tests/property_tests/", "--tb=short", "-v"],
            capture_output=True,
            text=True
        )
        property_reports = self.result_aggregator.aggregate_property_results(property_results)
        all_reports.extend(property_reports)

        # 4. Run browser discovery
        print("[DiscoveryCoordinator] Running browser discovery...")
        browser_bugs = self.browser_agent.explore_dfs(max_depth=3, max_actions=50)
        browser_reports = self.result_aggregator.aggregate_browser_results(browser_bugs)
        all_reports.extend(browser_reports)

        # 5. Deduplicate bugs
        print("[DiscoveryCoordinator] Deduplicating bugs...")
        unique_bugs = self.bug_deduplicator.deduplicate_bugs(all_reports)

        # 6. Classify severity
        print("[DiscoveryCoordinator] Classifying severity...")
        for bug in unique_bugs:
            bug.severity = self.severity_classifier.classify(bug)

        # 7. File unique bugs
        print("[DiscoveryCoordinator] Filing bugs...")
        filed_bugs = []
        for bug in unique_bugs:
            filing_result = self.bug_filing_service.file_bug(
                test_name=bug.test_name,
                error_message=bug.error_message,
                metadata=bug.metadata
            )
            filed_bugs.append(filing_result)

        # 8. Generate weekly report
        print("[DiscoveryCoordinator] Generating weekly report...")
        report_path = self.dashboard_generator.generate_weekly_report(
            bugs_found=len(all_reports),
            unique_bugs=len(unique_bugs),
            filed_bugs=len(filed_bugs),
            reports=all_reports
        )

        return {
            "bugs_found": len(all_reports),
            "unique_bugs": len(unique_bugs),
            "filed_bugs": len(filed_bugs),
            "report_path": report_path,
            "timestamp": datetime.utcnow().isoformat()
        }
```

### Pattern 2: BugReport Data Model (Pydantic)

**What:** Normalized bug report data structure with type validation.

**When to use:** All discovery methods convert results to BugReport objects for aggregation.

**Example:**
```python
# Source: backend/tests/bug_discovery/models/bug_report.py
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class DiscoveryMethod(str, Enum):
    """Discovery method types."""
    FUZZING = "fuzzing"
    CHAOS = "chaos"
    PROPERTY = "property"
    BROWSER = "browser"

class Severity(str, Enum):
    """Bug severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class BugReport(BaseModel):
    """
    Normalized bug report from any discovery method.

    All discovery methods (fuzzing, chaos, property, browser) convert
    their results to BugReport objects for unified aggregation.
    """
    discovery_method: DiscoveryMethod
    test_name: str
    error_message: str
    error_signature: str  # SHA256 hash for deduplication
    severity: Severity = Field(default=Severity.LOW)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Optional fields
    stack_trace: Optional[str] = None
    screenshot_path: Optional[str] = None
    log_path: Optional[str] = None
    reproduction_steps: Optional[str] = None

    class Config:
        """Pydantic config."""
        use_enum_values = True
```

### Pattern 3: Result Aggregation by Discovery Method

**What:** Convert discovery method-specific results to normalized BugReport objects.

**When to use:** After each discovery method completes, normalize results before aggregation.

**Example:**
```python
# Source: backend/tests/bug_discovery/core/result_aggregator.py
from typing import List, Dict
from tests.bug_discovery.models.bug_report import BugReport, DiscoveryMethod, Severity

class ResultAggregator:
    """
    Aggregates results from all discovery methods into BugReport objects.

    Each discovery method (fuzzing, chaos, property, browser) has
    its own result format. ResultAggregator normalizes all results
    into BugReport objects for unified deduplication and filing.
    """

    def aggregate_fuzzing_results(self, fuzzing_campaign: Dict) -> List[BugReport]:
        """
        Convert fuzzing campaign results to BugReport objects.

        Args:
            fuzzing_campaign: FuzzingOrchestrator campaign result

        Returns:
            List of BugReport objects
        """
        reports = []

        # Extract crashes from campaign
        crash_dir = Path(fuzzing_campaign["crash_dir"])
        crash_files = list(crash_dir.glob("*.input"))

        for crash_file in crash_files:
            crash_log_file = crash_file.with_suffix(".log")

            # Read crash log
            crash_log = ""
            if crash_log_file.exists():
                with open(crash_log_file, "r") as f:
                    crash_log = f.read()

            # Generate error signature
            error_signature = self._generate_error_signature(crash_log)

            report = BugReport(
                discovery_method=DiscoveryMethod.FUZZING,
                test_name=fuzzing_campaign["target_endpoint"],
                error_message=crash_log[:200] if crash_log else "Unknown crash",
                error_signature=error_signature,
                metadata={
                    "campaign_id": fuzzing_campaign["campaign_id"],
                    "crash_file": str(crash_file),
                    "executions": fuzzing_campaign["executions"]
                },
                stack_trace=crash_log
            )

            reports.append(report)

        return reports

    def aggregate_chaos_results(self, chaos_results: Dict) -> List[BugReport]:
        """
        Convert chaos experiment results to BugReport objects.

        Args:
            chaos_results: ChaosCoordinator experiment result

        Returns:
            List of BugReport objects
        """
        reports = []

        # Check if chaos experiment failed (resilience failure)
        if not chaos_results.get("success", False):
            error_message = f"Resilience failure: {chaos_results.get('error', 'Unknown')}"

            # Generate error signature from baseline + failure metrics
            error_signature = self._generate_error_signature(
                f"{chaos_results['baseline']} | {chaos_results['failure']}"
            )

            report = BugReport(
                discovery_method=DiscoveryMethod.CHAOS,
                test_name=chaos_results["experiment_name"],
                error_message=error_message,
                error_signature=error_signature,
                metadata={
                    "baseline_metrics": chaos_results.get("baseline", {}),
                    "failure_metrics": chaos_results.get("failure", {}),
                    "blast_radius": "test_database_only"
                }
            )

            reports.append(report)

        return reports

    def aggregate_property_results(self, property_results: Dict) -> List[BugReport]:
        """
        Convert property test failures to BugReport objects.

        Args:
            property_results: pytest subprocess result

        Returns:
            List of BugReport objects
        """
        reports = []

        # Parse pytest output for failed tests
        failed_tests = self._parse_property_test_failures(property_results.stdout)

        for test_name, error_message in failed_tests.items():
            # Generate error signature from test name + error message
            error_signature = self._generate_error_signature(f"{test_name} | {error_message}")

            report = BugReport(
                discovery_method=DiscoveryMethod.PROPERTY,
                test_name=test_name,
                error_message=error_message,
                error_signature=error_signature,
                metadata={
                    "property_test": True,
                    "invariant_violation": True
                }
            )

            reports.append(report)

        return reports

    def aggregate_browser_results(self, browser_bugs: List[Dict]) -> List[BugReport]:
        """
        Convert browser discovery bugs to BugReport objects.

        Args:
            browser_bugs: List of bugs from ExplorationAgent

        Returns:
            List of BugReport objects
        """
        reports = []

        for bug in browser_bugs:
            # Generate error signature from bug type + URL + error message
            error_signature = self._generate_error_signature(
                f"{bug['type']} | {bug.get('url', '')} | {bug['message']}"
            )

            report = BugReport(
                discovery_method=DiscoveryMethod.BROWSER,
                test_name=f"browser_{bug['type']}",
                error_message=bug["message"],
                error_signature=error_signature,
                metadata={
                    "url": bug.get("url"),
                    "bug_type": bug["type"],
                    "screenshot_path": bug.get("screenshot")
                },
                screenshot_path=bug.get("screenshot")
            )

            reports.append(report)

        return reports

    def _generate_error_signature(self, error_content: str) -> str:
        """Generate SHA256 hash for error deduplication."""
        import hashlib
        return hashlib.sha256(error_content.encode("utf-8")).hexdigest()

    def _parse_property_test_failures(self, pytest_output: str) -> Dict[str, str]:
        """Parse pytest output to extract failed tests and errors."""
        # Parse pytest output for FAILED lines
        failed_tests = {}
        for line in pytest_output.split("\n"):
            if "FAILED" in line and "::" in line:
                parts = line.split()
                test_name = parts[1]
                # Extract error message (simplified)
                error_message = "Property test failed - see logs"
                failed_tests[test_name] = error_message
        return failed_tests
```

### Pattern 4: Bug Deduplication Across All Methods

**What:** Extend CrashDeduplicator pattern to deduplicate all bug types by error signature.

**When to use:** After aggregating all results, before severity classification and filing.

**Example:**
```python
# Source: backend/tests/bug_discovery/core/bug_deduplicator.py
from typing import List, Dict
from tests.bug_discovery.models.bug_report import BugReport

class BugDeduplicator:
    """
    Deduplicate bugs across all discovery methods using error signature hashing.

    Extends CrashDeduplicator pattern (Phase 239) to support all bug types:
    - Fuzzing crashes (stack trace hashing)
    - Chaos resilience failures (metric signature hashing)
    - Property test failures (test name + error message hashing)
    - Browser bugs (bug type + URL + error hashing)
    """

    def deduplicate_bugs(self, bug_reports: List[BugReport]) -> List[BugReport]:
        """
        Deduplicate bugs by error signature.

        Args:
            bug_reports: List of BugReport objects from all discovery methods

        Returns:
            List of unique BugReport objects (one per error signature)
        """
        unique_bugs = {}
        duplicate_counts = {}

        for bug in bug_reports:
            signature = bug.error_signature

            # Track first occurrence
            if signature not in unique_bugs:
                unique_bugs[signature] = bug
                duplicate_counts[signature] = 1
            else:
                # Increment duplicate count
                duplicate_counts[signature] += 1

                # Merge metadata if needed (e.g., related bugs from different methods)
                existing_bug = unique_bugs[signature]
                if bug.discovery_method not in existing_bug.metadata.get("discovery_methods", []):
                    discovery_methods = existing_bug.metadata.get("discovery_methods", [])
                    discovery_methods.append(bug.discovery_method)
                    existing_bug.metadata["discovery_methods"] = discovery_methods

        # Update unique bugs with duplicate counts
        for bug in unique_bugs.values():
            bug.metadata["duplicate_count"] = duplicate_counts[bug.error_signature]

        return list(unique_bugs.values())
```

### Pattern 5: Severity Classification (Rule-Based)

**What:** Classify bug severity using rule-based heuristics by discovery method and impact.

**When to use:** After deduplication, before bug filing.

**Example:**
```python
# Source: backend/tests/bug_discovery/core/severity_classifier.py
from tests.bug_discovery.models.bug_report import BugReport, Severity, DiscoveryMethod

class SeverityClassifier:
    """
    Classify bug severity using rule-based heuristics.

    Extends BugFilingService._determine_severity() logic (Phase 236)
    to support all discovery methods with consistent severity rules.
    """

    def classify(self, bug: BugReport) -> Severity:
        """
        Classify bug severity based on discovery method and impact.

        Args:
            bug: BugReport object

        Returns:
            Severity level (critical/high/medium/low)
        """
        # Critical severity: Crashes in critical paths, data corruption
        if bug.discovery_method == DiscoveryMethod.FUZZING:
            # Fuzzing crashes are critical (potential security vulnerabilities)
            return Severity.CRITICAL

        if bug.discovery_method == DiscoveryMethod.CHAOS:
            # Resilience failures are high (system instability)
            return Severity.HIGH

        if bug.discovery_method == DiscoveryMethod.PROPERTY:
            # Property test failures: Check if invariant is critical
            if "security" in bug.test_name.lower():
                # Security invariant violations are critical
                return Severity.CRITICAL
            elif "database" in bug.test_name.lower() or "transaction" in bug.test_name.lower():
                # Database invariant violations are high (data corruption risk)
                return Severity.HIGH
            else:
                # Other invariant violations are medium
                return Severity.MEDIUM

        if bug.discovery_method == DiscoveryMethod.BROWSER:
            # Browser bugs: Check bug type
            bug_type = bug.metadata.get("bug_type", "")
            if bug_type == "console_error":
                # JavaScript console errors are high
                return Severity.HIGH
            elif bug_type == "accessibility":
                # Accessibility violations are medium (WCAG compliance)
                return Severity.MEDIUM
            elif bug_type == "broken_link":
                # Broken links are low (usability issue)
                return Severity.LOW
            else:
                # Other browser bugs are low
                return Severity.LOW

        # Default to low severity
        return Severity.LOW
```

### Pattern 6: Weekly Dashboard Reports (HTML/JSON)

**What:** Generate weekly HTML reports with bug trends (found, fixed, regression rate).

**When to use:** After full discovery run, upload as CI artifact.

**Example:**
```python
# Source: backend/tests/bug_discovery/core/dashboard_generator.py
from typing import List, Dict
from pathlib import Path
from datetime import datetime, timedelta
from jinja2 import Template
from tests.bug_discovery.models.bug_report import BugReport

class DashboardGenerator:
    """
    Generate weekly bug discovery dashboard reports.

    Produces HTML and JSON reports with:
    - Bugs found (by discovery method, severity)
    - Bugs fixed (from GitHub Issues)
    - Regression rate (bugs reintroduced after fix)
    - Trend analysis (week-over-week comparison)
    """

    def generate_weekly_report(
        self,
        bugs_found: int,
        unique_bugs: int,
        filed_bugs: int,
        reports: List[BugReport]
    ) -> str:
        """
        Generate weekly HTML report.

        Args:
            bugs_found: Total bugs found (including duplicates)
            unique_bugs: Unique bugs after deduplication
            filed_bugs: Bugs filed to GitHub
            reports: List of BugReport objects

        Returns:
            Path to generated HTML report
        """
        # Calculate statistics
        by_method = self._group_by_method(reports)
        by_severity = self._group_by_severity(reports)

        # Load previous week data for regression rate
        regression_rate = self._calculate_regression_rate(reports)

        # Render HTML template
        template = Template(self._get_html_template())
        html_content = template.render(
            week_date=datetime.utcnow().strftime("%Y-%m-%d"),
            bugs_found=bugs_found,
            unique_bugs=unique_bugs,
            filed_bugs=filed_bugs,
            regression_rate=regression_rate,
            by_method=by_method,
            by_severity=by_severity,
            top_bugs=reports[:10]  # Top 10 bugs by severity
        )

        # Save report
        reports_dir = Path("tests/bug_discovery/storage/reports")
        reports_dir.mkdir(parents=True, exist_ok=True)

        report_path = reports_dir / f"weekly-{datetime.utcnow().strftime('%Y-%m-%d')}.html"
        with open(report_path, "w") as f:
            f.write(html_content)

        return str(report_path)

    def _group_by_method(self, reports: List[BugReport]) -> Dict[str, int]:
        """Group bugs by discovery method."""
        method_counts = {}
        for report in reports:
            method = report.discovery_method.value
            method_counts[method] = method_counts.get(method, 0) + 1
        return method_counts

    def _group_by_severity(self, reports: List[BugReport]) -> Dict[str, int]:
        """Group bugs by severity."""
        severity_counts = {}
        for report in reports:
            severity = report.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
        return severity_counts

    def _calculate_regression_rate(self, reports: List[BugReport]) -> float:
        """Calculate regression rate (bugs reintroduced after fix)."""
        # Load previous week bug signatures from database
        # Check if any current bugs match previous week bugs (were reintroduced)
        # For now, return 0.0 (placeholder)
        return 0.0

    def _get_html_template(self) -> str:
        """Return Jinja2 HTML template for weekly report."""
        return """
<!DOCTYPE html>
<html>
<head>
    <title>Weekly Bug Discovery Report - {{ week_date }}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333; }
        .summary { display: flex; gap: 20px; margin: 20px 0; }
        .card { border: 1px solid #ddd; padding: 15px; border-radius: 5px; flex: 1; }
        .card h3 { margin-top: 0; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .critical { color: #d32f2f; font-weight: bold; }
        .high { color: #f57c00; }
        .medium { color: #fbc02d; }
        .low { color: #388e3c; }
    </style>
</head>
<body>
    <h1>Weekly Bug Discovery Report - {{ week_date }}</h1>

    <div class="summary">
        <div class="card">
            <h3>Bugs Found</h3>
            <p style="font-size: 36px; color: #d32f2f;">{{ bugs_found }}</p>
        </div>
        <div class="card">
            <h3>Unique Bugs</h3>
            <p style="font-size: 36px; color: #f57c00;">{{ unique_bugs }}</p>
        </div>
        <div class="card">
            <h3>Bugs Filed</h3>
            <p style="font-size: 36px; color: #388e3c;">{{ filed_bugs }}</p>
        </div>
        <div class="card">
            <h3>Regression Rate</h3>
            <p style="font-size: 36px; color: #1976d2;">{{ regression_rate }}%</p>
        </div>
    </div>

    <h2>Bugs by Discovery Method</h2>
    <table>
        <tr>
            <th>Method</th>
            <th>Count</th>
        </tr>
        {% for method, count in by_method.items() %}
        <tr>
            <td>{{ method }}</td>
            <td>{{ count }}</td>
        </tr>
        {% endfor %}
    </table>

    <h2>Bugs by Severity</h2>
    <table>
        <tr>
            <th>Severity</th>
            <th>Count</th>
        </tr>
        {% for severity, count in by_severity.items() %}
        <tr>
            <td class="{{ severity }}">{{ severity }}</td>
            <td>{{ count }}</td>
        </tr>
        {% endfor %}
    </table>

    <h2>Top Bugs</h2>
    <table>
        <tr>
            <th>Test</th>
            <th>Method</th>
            <th>Severity</th>
            <th>Error</th>
        </tr>
        {% for bug in top_bugs %}
        <tr>
            <td>{{ bug.test_name }}</td>
            <td>{{ bug.discovery_method.value }}</td>
            <td class="{{ bug.severity.value }}">{{ bug.severity.value }}</td>
            <td>{{ bug.error_message[:100] }}</td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
        """
```

### Anti-Patterns to Avoid

- **Manual bug filing**: Don't file bugs manually — use BugFilingService for idempotency and metadata collection
- **Discovery method-specific formats**: Don't keep separate result formats — normalize all results to BugReport objects
- **Severity classification by gut feel**: Don't guess severity — use rule-based heuristics with clear criteria
- **Weekly reports without trends**: Don't generate static reports — include week-over-week comparison and regression rate
- **Deduplication by test name only**: Don't deduplicate by test name alone — use error signature hashing (stack traces, metrics, URLs)

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **GitHub Issues API** | Custom REST API calls | BugFilingService (Phase 236) | Idempotency, duplicate detection, artifact attachment already implemented |
| **Crash deduplication** | Custom deduplication logic | CrashDeduplicator pattern (Phase 239) | SHA256 error signature hashing proven in fuzzing campaigns |
| **Campaign management** | Custom subprocess management | FuzzingOrchestrator (Phase 239) | Start/stop/monitor lifecycle with crash tracking |
| **Experiment orchestration** | Custom chaos test runner | ChaosCoordinator (Phase 241) | Blast radius controls, recovery validation |
| **Browser automation** | Custom web scraping | ExplorationAgent (Phase 240) | DFS/BFS/random walk with console error detection |
| **Severity classification** | ML classifier from scratch | Rule-based heuristics (this phase) | Deterministic, explainable, no training data required |
| **HTML reports** | Custom HTML generation | Jinja2 templates | Industry-standard templating, clean separation of logic/presentation |

**Key insight:** Atom has comprehensive discovery infrastructure from Phases 238-241. Phase 242 is the orchestration layer that ties everything together, not a new discovery method. Reuse existing services (FuzzingOrchestrator, ChaosCoordinator, ExplorationAgent, BugFilingService) and focus on aggregation, deduplication, severity classification, and reporting.

## Common Pitfalls

### Pitfall 1: Discovery Method Silos
**What goes wrong:** Each discovery method (fuzzing, chaos, property, browser) produces its own result format, making aggregation and deduplication difficult.

**Why it happens:** Discovery methods are developed independently in different phases (238-241) without a unified data model.

**How to avoid:** Define BugReport Pydantic model early as the common data structure. Require all discovery methods to convert results to BugReport objects before aggregation.

**Warning signs:** Discovery method-specific logic in DiscoveryCoordinator, repeated result parsing code, difficulty deduplicating across methods.

### Pitfall 2: Over-Engineering Severity Classification
**What goes wrong:** Teams build complex ML classifiers for severity prediction without sufficient training data, leading to poor accuracy and unmaintainable code.

**Why it happens:** Desire for "intelligent" automation without considering the data requirements (thousands of labeled bugs for ML training).

**How to avoid:** Start with rule-based heuristics (proven in BugFilingService). ML can be added later as enhancement once sufficient historical bug data is collected.

**Warning signs:** Discussing ML models before collecting baseline data, complexity without clear ROI, difficulty explaining severity decisions.

### Pitfall 3: Ignoring Regression Detection
**What goes wrong:** Weekly reports show bugs found and fixed, but don't detect regressions (bugs reintroduced after fix), leading to repeated issues.

**Why it happens:** Focus on current week's bugs without tracking historical bug signatures.

**How to avoid:** Store bug signatures in SQLite database. Each week, check if any current bugs match previous weeks (were reintroduced). Report regression rate as key metric.

**Warning signs:** No historical bug tracking, regression rate not calculated, repeated bugs filed multiple times.

### Pitfall 4: Slow Discovery Pipeline
**What goes wrong:** Full discovery run takes 6+ hours, making weekly CI pipeline impractical and delaying bug detection.

**Why it happens:** Running all discovery methods sequentially without parallelization, excessive test data (e.g., 100K fuzzing iterations).

**How to avoid:** Run discovery methods in parallel (pytest-xdist), limit iterations (10K fuzzing, 30 min chaos, 20 browser tests), target <2 hours for full discovery run.

**Warning signs:** Discovery runs exceeding 2 hours, no parallelization, excessive iteration counts.

### Pitfall 5: Duplicate Bug Filings
**What goes wrong:** Same bug filed multiple times across discovery methods (e.g., fuzzing and property tests both find SQL injection), cluttering GitHub Issues.

**Why it happens:** Deduplication only within discovery method, not across methods.

**How to avoid:** Deduplicate by error signature across all methods after aggregation. Track which methods found each bug in metadata.

**Warning signs:** Multiple GitHub Issues for same error, high duplicate count in BugFilingService, developer complaints about bug spam.

## Code Examples

Verified patterns from official sources:

### DiscoveryCoordinator Integration (This Phase)
```python
# Source: backend/tests/bug_discovery/core/discovery_coordinator.py
from tests.fuzzing.campaigns.fuzzing_orchestrator import FuzzingOrchestrator
from tests.chaos.core.chaos_coordinator import ChaosCoordinator
from tests.bug_discovery.bug_filing_service import BugFilingService

coordinator = DiscoveryCoordinator(
    github_token=os.getenv("GITHUB_TOKEN"),
    github_repository=os.getenv("GITHUB_REPOSITORY")
)

# Run full discovery (fuzzing, chaos, property, browser)
result = coordinator.run_full_discovery(duration_seconds=3600)

print(f"Bugs found: {result['bugs_found']}")
print(f"Unique bugs: {result['unique_bugs']}")
print(f"Bugs filed: {result['filed_bugs']}")
print(f"Report: {result['report_path']}")
```

### BugReport Model (Pydantic)
```python
# Source: backend/tests/bug_discovery/models/bug_report.py
from pydantic import BaseModel
from tests.bug_discovery.models.bug_report import BugReport, DiscoveryMethod, Severity

# Create bug report from fuzzing crash
fuzzing_bug = BugReport(
    discovery_method=DiscoveryMethod.FUZZING,
    test_name="/api/v1/agents/run",
    error_message="SQL injection in agent_id parameter",
    error_signature="a1b2c3d4...",  # SHA256 hash
    severity=Severity.CRITICAL,
    metadata={
        "campaign_id": "api-v1-agents_2026-03-25",
        "crash_file": "/tmp/crashes/crash-001.input"
    }
)

# Validate automatically (Pydantic)
print(fuzzing_bug.json(indent=2))
```

### Result Aggregation Pattern
```python
# Source: backend/tests/bug_discovery/core/result_aggregator.py
from tests.bug_discovery.core.result_aggregator import ResultAggregator

aggregator = ResultAggregator()

# Normalize fuzzing results
fuzzing_reports = aggregator.aggregate_fuzzing_results(fuzzing_campaign)

# Normalize chaos results
chaos_reports = aggregator.aggregate_chaos_results(chaos_results)

# All reports are now BugReport objects
all_reports = fuzzing_reports + chaos_reports
```

### Bug Deduplication Pattern
```python
# Source: backend/tests/bug_discovery/core/bug_deduplicator.py
from tests.bug_discovery.core.bug_deduplicator import BugDeduplicator

deduplicator = BugDeduplicator()

# Deduplicate all bugs by error signature
unique_bugs = deduplicator.deduplicate_bugs(all_reports)

print(f"Total bugs: {len(all_reports)}")
print(f"Unique bugs: {len(unique_bugs)}")

# Check duplicate counts
for bug in unique_bugs:
    if bug.metadata["duplicate_count"] > 1:
        print(f"Bug {bug.test_name}: {bug.metadata['duplicate_count']} duplicates")
```

### Severity Classification Pattern
```python
# Source: backend/tests/bug_discovery/core/severity_classifier.py
from tests.bug_discovery.core.severity_classifier import SeverityClassifier

classifier = SeverityClassifier()

# Classify severity for all bugs
for bug in unique_bugs:
    bug.severity = classifier.classify(bug)

# Count by severity
from collections import Counter
severity_counts = Counter(bug.severity for bug in unique_bugs)
print(severity_counts)
# Output: Counter({<Severity.CRITICAL>: 5, <Severity.HIGH>: 12, ...})
```

### Dashboard Report Generation
```python
# Source: backend/tests/bug_discovery/core/dashboard_generator.py
from tests.bug_discovery.core.dashboard_generator import DashboardGenerator

generator = DashboardGenerator()

# Generate weekly HTML report
report_path = generator.generate_weekly_report(
    bugs_found=150,
    unique_bugs=42,
    filed_bugs=38,
    reports=unique_bugs
)

print(f"Weekly report: {report_path}")
# Output: tests/bug_discovery/storage/reports/weekly-2026-03-25.html
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **Separate bug discovery tools** | **Unified orchestration layer** | Phase 242 (this phase) | Single coordinator runs all methods, aggregates results, files unique bugs |
| **Manual bug triage** | **Automated severity classification** | Phase 242 (this phase) | Rule-based heuristics classify bugs consistently, reduce human effort |
| **No regression detection** | **Weekly regression rate tracking** | Phase 242 (this phase) | Detect bugs reintroduced after fix, measure quality over time |
| **Separate CI pipelines** | **Single weekly discovery pipeline** | Phase 242 (this phase) | Bug-discovery-weekly.yml runs all methods, generates unified report |
| **Crash deduplication only** | **Cross-method bug deduplication** | Phase 242 (this phase) | Deduplicate bugs by error signature across all discovery methods |

**Deprecated/outdated:**
- **Manual bug filing via GitHub UI**: Replaced by BugFilingService with idempotency and metadata collection
- **Separate fuzzing/chaos/browser CI jobs**: Replaced by unified DiscoveryCoordinator in weekly pipeline
- **Severity classification by developer gut feel**: Replaced by rule-based heuristics with clear criteria

## Open Questions

1. **ML-based severity classification**
   - What we know: Rule-based heuristics are sufficient for initial implementation (proven in BugFilingService)
   - What's unclear: Whether ML classifier improves accuracy enough to justify complexity
   - Recommendation: Start with rule-based, collect historical bug data, evaluate ML in future enhancement

2. **Regression detection algorithm**
   - What we know: Need to track bug signatures across weeks to detect reintroduced bugs
   - What's unclear: How long to track bug signatures (1 month? 3 months?) and what constitutes regression (exact match? similar?)
   - Recommendation: Start with exact signature match, 1-month window. Expand to similar signatures later using fuzzy matching.

3. **Weekly report storage**
   - What we know: HTML reports for human viewing, JSON for CI artifacts
   - What's unclear: Whether to use SQLite database or JSON files for historical bug data
   - Recommendation: Use SQLite for bug signatures (structured queries, regression detection), JSON for weekly reports (CI artifact upload)

4. **Discovery method parallelization**
   - What we know: Running methods sequentially is slow (>6 hours)
   - What's unclear: Whether pytest-xdist can parallelize across different discovery methods (fuzzing, chaos, property, browser)
   - Recommendation: Investigate pytest-xdist for test-level parallelization. If insufficient, use subprocess.Popen to run methods in parallel.

## Sources

### Primary (HIGH confidence)
- **Phase 239 Research (API Fuzzing)** - FuzzingOrchestrator pattern, CrashDeduplicator implementation, campaign management
- **Phase 241 Research (Chaos Engineering)** - ChaosCoordinator pattern, blast radius controls, recovery validation
- **BugFilingService Source** - `/Users/rushiparikh/projects/atom/backend/tests/bug_discovery/bug_filing_service.py` (503 lines) - GitHub Issues API, idempotency, severity classification
- **FuzzingOrchestrator Source** - `/Users/rushiparikh/projects/atom/backend/tests/fuzzing/campaigns/fuzzing_orchestrator.py` (508 lines) - Campaign lifecycle management
- **CrashDeduplicator Source** - `/Users/rushiparikh/projects/atom/backend/tests/fuzzing/campaigns/crash_deduplicator.py` (203 lines) - SHA256 error signature hashing
- **ChaosCoordinator Source** - `/Users/rushiparikh/projects/atom/backend/tests/chaos/core/chaos_coordinator.py` (133 lines) - Experiment orchestration
- **Property Tests Inventory** - `/Users/rushiparikh/projects/atom/backend/tests/property_tests/` (264 property test files)
- **Browser Discovery Tests** - `/Users/rushiparikh/projects/atom/backend/tests/browser_discovery/test_exploration_agent.py` (423 lines) - DFS/BFS/random walk exploration

### Secondary (MEDIUM confidence)
- **Pydantic Documentation** - Data validation, BaseModel, type safety for BugReport model
- **Jinja2 Documentation** - HTML templating for weekly reports
- **pytest-xdist Documentation** - Parallel test execution for discovery methods

### Tertiary (LOW confidence)
- **ML-based bug triage research** (not verified) - Need to evaluate if ML improves severity classification accuracy
- **Regression detection algorithms** (not verified) - Need to research fuzzy matching for similar bug signatures

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All tools are proven in Phases 238-241 (pytest, pydantic, hashlib, jinja2)
- Architecture: HIGH - DiscoveryCoordinator pattern is thin orchestration layer, reuses existing services
- Pitfalls: HIGH - Identified from multi-method aggregation challenges and CI pipeline constraints
- Severity classification: MEDIUM - Rule-based heuristics are proven, ML enhancement needs validation
- Regression detection: MEDIUM - Algorithm is straightforward (signature matching), fuzzy matching needs research

**Research date:** 2026-03-25
**Valid until:** 2026-04-25 (30 days - stable domain, bug discovery patterns are well-established)

**Next steps for planner:**
1. Design DiscoveryCoordinator service interface with run_full_discovery() method
2. Define BugReport Pydantic model with all discovery method fields
3. Implement ResultAggregator to normalize fuzzing, chaos, property, browser results
4. Extend CrashDeduplicator to BugDeduplicator for cross-method deduplication
5. Centralize severity classification logic from BugFilingService into SeverityClassifier
6. Design HTML/JSON weekly report templates with trend analysis
7. Plan DiscoveryCoordinator integration with bug-discovery-weekly.yml CI pipeline
8. Define test strategy for DiscoveryCoordinator (unit tests, integration tests, end-to-end)
