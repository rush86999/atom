# Phase 245: Feedback Loops & ROI Tracking - Research

**Researched:** 2026-03-25
**Domain:** Automated regression test generation, bug discovery ROI metrics, bug fix verification, dashboard effectiveness tracking
**Confidence:** HIGH

## Summary

Phase 245 focuses on closing the bug discovery feedback loop with (1) **automated regression test generation** that converts bug findings into permanent pytest tests, (2) **enhanced bug discovery dashboard** with weekly reports showing bugs found, fixed, and regression rate, (3) **automated bug fix verification** that re-runs tests after fixes and closes GitHub issues, and (4) **ROI tracking** demonstrating time saved, bugs prevented, and cost effectiveness. The research confirms that Atom has **comprehensive infrastructure** from Phases 237-244: BugFilingService with automated GitHub issue filing, DiscoveryCoordinator orchestrating all discovery methods, DashboardGenerator with weekly HTML/JSON reports, BugReport model with normalized data, and AIEnhancedBugDiscovery with InvariantGenerator for test generation patterns. The key gaps are **no regression test automation** (bugs don't auto-generate tests), **no fix verification workflow** (issues stay open manually), **no ROI metrics collection** (cost/benefit not tracked), and **no regression rate calculation** (don't know if bugs are reintroduced).

**Primary recommendation:** Build FeedbackLoopService with four capabilities: (1) **RegressionTestGenerator** converts BugReports to pytest test files with reproducible test cases (e.g., fuzzing crash → `test_regression_fuzzing_crash_001()`), (2) **BugFixVerifier** monitors GitHub Issues for "fix" labels, re-runs failed tests, and auto-closes verified issues with comments, (3) **ROITracker** collects metrics (bugs found, time to discovery, time to fix, manual QA cost vs automation cost) and generates ROI reports showing hours saved and cost avoidance, (4) **Enhanced Dashboard** extends DashboardGenerator with regression rate tracking (compare bug signatures across weeks), fix verification status, and ROI summary cards. Reuse existing infrastructure (BugFilingService, DiscoveryCoordinator, DashboardGenerator, BugReport, InvariantGenerator patterns) and integrate with weekly bug-discovery-weekly.yml CI pipeline.

**Key findings:**
1. **Bug filing is fully automated**: BugFilingService (503 lines) files GitHub Issues with rich metadata (screenshots, logs, stack traces, severity labels), idempotency (no duplicate issues), artifact attachment
2. **Weekly dashboard reports exist**: DashboardGenerator (263 lines) generates HTML/JSON reports with bugs found, unique bugs, filed bugs, regression rate (placeholder), severity distribution, top bugs table
3. **AI test generation patterns established**: InvariantGenerator (Phase 244) uses LLM to analyze code and generate property test invariants with testable code; pattern can be adapted for regression test generation
4. **BugReport model is comprehensive**: Pydantic model with discovery_method, test_name, error_message, error_signature (SHA256), severity, metadata, stack_trace, screenshot_path, reproduction_steps - all needed for test generation
5. **DiscoveryCoordinator orchestrates everything**: Phase 242 delivered unified orchestration (667 lines) running fuzzing, chaos, property, browser discovery with aggregation, deduplication, filing, reporting
6. **GitHub Actions workflow exists**: bug-discovery-weekly.yml runs weekly (Sunday 2 AM UTC), 180-minute timeout, uploads reports as artifacts, calls DiscoveryCoordinator.run_full_discovery()

## Standard Stack

### Core Test Generation & Verification
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest** | 7.4.x | Regression test generation and execution | Industry standard, existing infrastructure, 495+ E2E tests, rich fixtures |
| **pytest-bdd** | 6.1+ | BDD-style test generation from bug reports | Given/When/Then structure from bug repro steps; readable regression tests |
| **Jinja2** | 3.1.x | Test file template rendering | Generate pytest test files from BugReport templates; already used in DashboardGenerator |
| **Pydantic** | 2.0.x | BugReport validation for test generation | Type-safe bug-to-test conversion, error handling, schema validation |

### GitHub Integration & Fix Verification
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **PyGithub** | 2.1+ | GitHub API for issue monitoring | Poll for "fix" label changes, auto-close issues, add verification comments |
| **requests** | Latest | GitHub REST API calls | Already used in BugFilingService; consistent HTTP client |
| **webhooks** | (stdlib) | GitHub webhook event handling | Listen for issue.label/issue.close events for real-time verification |

### ROI Metrics & Analytics
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **sqlite3** | (stdlib) | Metrics storage and trend analysis | Store bug discovery metrics, fix times, cost calculations locally |
| **pandas** | 2.0+ | ROI calculation and reporting | Time series analysis, cost aggregation, trend visualization |
| **matplotlib/plotly** | Latest | ROI dashboard charts | Generate ROI trend charts, cost comparison graphs |

### Test Generation Templates
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **string.Template** | (stdlib) | Simple test file templating | Built-in, sufficient for pytest file generation |
| **dataclasses** | (stdlib) | Regression test metadata | Type-safe test configuration (name, bug_id, repro_steps) |
| **pathlib** | (stdlib) | Test file path management | Cross-platform path handling for `tests/regression/` directory |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **RegressionTestGenerator (custom)** | Great Expectations, Airflow checks | Custom generator integrates with BugReport model, pytest fixtures, no external dependencies |
| **SQLite for metrics** | PostgreSQL, MongoDB | SQLite is file-based, no setup required, sufficient for weekly bug metrics |
| **PyGithub for verification** | GitHub CLI (gh) | PyGithub provides Pythonic API, better integration with existing BugFilingService |
| **Jinja2 for templates** | Mako, Django templates | Jinja2 is already dependency (DashboardGenerator), lightweight, industry-standard |
| **pytest-bdd for structure** | Robot Framework, Behave | pytest-bdd integrates with existing pytest infrastructure, fixtures, markers |

**Installation:**
```bash
# Core test generation (already installed)
pip install pytest pydantic

# GitHub integration (new)
pip install PyGithub

# ROI analytics (optional - can use pandas if already installed)
pip install pandas matplotlib

# Test generation templates (stdlib - no install needed)
# string.Template, dataclasses, pathlib are all built-in
```

## Architecture Patterns

### Recommended Project Structure

**Existing Structure (DO NOT CHANGE):**
```
backend/tests/
├── bug_discovery/              # ✅ EXISTS - Bug filing & coordination
│   ├── bug_filing_service.py   # ✅ EXISTS - GitHub Issues API (503 lines)
│   ├── core/                   # ✅ EXISTS - Discovery orchestration (Phase 242)
│   │   ├── discovery_coordinator.py  # ✅ EXISTS - Unified orchestration (667 lines)
│   │   ├── result_aggregator.py      # ✅ EXISTS - Result normalization
│   │   ├── bug_deduplicator.py       # ✅ EXISTS - SHA256 deduplication
│   │   ├── severity_classifier.py    # ✅ EXISTS - Rule-based severity
│   │   └── dashboard_generator.py    # ✅ EXISTS - Weekly reports (263 lines)
│   ├── models/                 # ✅ EXISTS - Data models
│   │   └── bug_report.py       # ✅ EXISTS - Pydantic BugReport model
│   └── storage/                # ✅ EXISTS - Reports & database
│       ├── reports/            # ✅ EXISTS - Weekly HTML/JSON reports
│       └── bug_reports.db      # ✅ EXISTS - SQLite for bug data
├── fuzzing/                    # ✅ EXISTS - API fuzzing (Phase 239)
├── chaos/                      # ✅ EXISTS - Chaos engineering (Phase 241)
├── property_tests/             # ✅ EXISTS - 264+ property tests (Phase 238)
└── browser_discovery/          # ✅ EXISTS - Browser discovery (Phase 240)
```

**NEW Structure (Phase 245):**
```
backend/tests/bug_discovery/
├── feedback_loops/             # ✅ NEW - Feedback loop automation
│   ├── __init__.py
│   ├── regression_test_generator.py    # ✅ NEW - Generate pytest files from bugs
│   ├── bug_fix_verifier.py              # ✅ NEW - Verify fixes & close issues
│   ├── roi_tracker.py                   # ✅ NEW - ROI metrics & cost analysis
│   └── tests/                            # ✅ NEW - Unit tests
│       ├── test_regression_test_generator.py
│       ├── test_bug_fix_verifier.py
│       └──test_roi_tracker.py
├── core/                       # ✅ KEEP (Phase 242)
│   └── dashboard_generator.py  # ✅ ENHANCE - Add ROI metrics, regression rate
├── storage/                    # ✅ ENHANCE
│   ├── bug_reports.db          # ✅ KEEP - SQLite for bug data
│   ├── metrics.db              # ✅ NEW - SQLite for ROI metrics
│   └── regression_tests/       # ✅ NEW - Generated regression tests
│       ├── test_regression_fuzzing_001.py
│       ├── test_regression_chaos_002.py
│       └── test_regression_property_003.py
└── templates/                  # ✅ NEW - Test file templates
    ├── pytest_regression_template.py.j2
    ├── fuzzing_regression_template.py.j2
    └── property_regression_template.py.j2
```

**Key Principle:** Feedback loops are built ON TOP of existing bug discovery infrastructure, not a replacement. RegressionTestGenerator converts BugReports → pytest files, BugFixVerifier monitors GitHub → re-runs tests → closes issues, ROITracker aggregates metrics → generates cost/benefit reports.

### Pattern 1: RegressionTestGenerator (FEEDBACK-01)

**What:** Convert BugReports to reproducible pytest test files.

**When to use:** After DiscoveryCoordinator completes full discovery run, for each unique bug filed.

**Example:**
```python
# Source: backend/tests/bug_discovery/feedback_loops/regression_test_generator.py
from pathlib import Path
from typing import List, Dict, Any
from jinja2 import Template
from tests.bug_discovery.models.bug_report import BugReport, DiscoveryMethod

class RegressionTestGenerator:
    """
    Generate regression tests from BugReport objects.

    Converts bug findings into permanent pytest test files with:
    - Reproducible test cases (minimal reproduction from bug metadata)
    - Test fixtures (db_session, authenticated_page, browser)
    - Markers (@pytest.mark.regression, @pytest.mark.slow)
    - Docstrings (bug description, reproduction steps, expected behavior)

    Example:
        generator = RegressionTestGenerator()
        test_path = generator.generate_test_from_bug(
            bug=bug_report,
            output_dir="tests/bug_discovery/storage/regression_tests/"
        )
        print(f"Generated regression test: {test_path}")
    """

    def __init__(self, templates_dir: str = None):
        """
        Initialize RegressionTestGenerator.

        Args:
            templates_dir: Directory for Jinja2 templates (default: bug_discovery/templates/)
        """
        if templates_dir is None:
            backend_dir = Path(__file__).parent.parent.parent.parent
            templates_dir = backend_dir / "tests" / "bug_discovery" / "templates"

        self.templates_dir = Path(templates_dir)
        self.templates_dir.mkdir(parents=True, exist_ok=True)

    def generate_test_from_bug(
        self,
        bug: BugReport,
        output_dir: str = None,
        bug_id: str = None
    ) -> str:
        """
        Generate pytest test file from BugReport.

        Args:
            bug: BugReport object from discovery
            output_dir: Output directory for test file (default: tests/bug_discovery/storage/regression_tests/)
            bug_id: Bug identifier (default: auto-generated from signature)

        Returns:
            Path to generated test file
        """
        if output_dir is None:
            backend_dir = Path(__file__).parent.parent.parent.parent
            output_dir = backend_dir / "tests" / "bug_discovery" / "storage" / "regression_tests"

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate test file name
        if bug_id is None:
            bug_id = bug.error_signature[:8]  # First 8 chars of SHA256

        test_filename = f"test_regression_{bug.discovery_method}_{bug_id}.py"
        test_path = output_dir / test_filename

        # Select template based on discovery method
        template = self._get_template_for_method(bug.discovery_method)

        # Render test content
        test_content = template.render(
            bug_id=bug_id,
            bug=bug,
            test_name=f"test_regression_{bug.discovery_method}_{bug_id}",
            discovery_method=bug.discovery_method,
            reproduction_steps=bug.reproduction_steps or self._infer_reproduction_steps(bug),
            expected_behavior=f"No error - {bug.error_message} should not occur",
            metadata=bug.metadata
        )

        # Write test file
        with open(test_path, "w") as f:
            f.write(test_content)

        return str(test_path)

    def _get_template_for_method(self, discovery_method: DiscoveryMethod) -> Template:
        """Get Jinja2 template for discovery method."""
        template_map = {
            DiscoveryMethod.FUZZING: "fuzzing_regression_template.py.j2",
            DiscoveryMethod.CHAOS: "chaos_regression_template.py.j2",
            DiscoveryMethod.PROPERTY: "property_regression_template.py.j2",
            DiscoveryMethod.BROWSER: "browser_regression_template.py.j2",
        }

        template_name = template_map.get(discovery_method, "pytest_regression_template.py.j2")
        template_path = self.templates_dir / template_name

        with open(template_path) as f:
            return Template(f.read())

    def _infer_reproduction_steps(self, bug: BugReport) -> str:
        """
        Infer reproduction steps from bug metadata.

        Args:
            bug: BugReport object

        Returns:
            Reproduction steps as string
        """
        steps = []

        # Add test run command
        if bug.test_name:
            steps.append(f"1. Run test: pytest {bug.test_name}")

        # Add discovery method context
        if bug.discovery_method == DiscoveryMethod.FUZZING:
            steps.append(f"2. Fuzz endpoint with input from crash file")
            if bug.metadata.get("crash_file"):
                steps.append(f"3. Crash file: {bug.metadata['crash_file']}")
        elif bug.discovery_method == DiscoveryMethod.CHAOS:
            steps.append(f"2. Inject failure: {bug.metadata.get('experiment_name', 'unknown')}")
            steps.append(f"3. Verify graceful degradation")
        elif bug.discovery_method == DiscoveryMethod.PROPERTY:
            steps.append(f"2. Run property test with Hypothesis")
            steps.append(f"3. Invariant violation detected")
        elif bug.discovery_method == DiscoveryMethod.BROWSER:
            steps.append(f"2. Navigate to: {bug.metadata.get('url', 'unknown')}")
            steps.append(f"3. Browser error detected")

        return "\n".join(steps)

    def generate_tests_from_bug_list(
        self,
        bugs: List[BugReport],
        output_dir: str = None
    ) -> List[str]:
        """
        Generate regression tests from list of BugReports.

        Args:
            bugs: List of BugReport objects
            output_dir: Output directory for test files

        Returns:
            List of generated test file paths
        """
        test_paths = []

        for bug in bugs:
            try:
                test_path = self.generate_test_from_bug(bug, output_dir)
                test_paths.append(test_path)
                print(f"[RegressionTestGenerator] Generated: {test_path}")
            except Exception as e:
                print(f"[RegressionTestGenerator] Failed to generate test for {bug.test_name}: {e}")

        return test_paths
```

**Jinja2 Template (pytest_regression_template.py.j2):**
```python
# Source: backend/tests/bug_discovery/templates/pytest_regression_template.py.j2
"""
Regression test for bug {{ bug_id }}

Bug Report:
- Discovery Method: {{ discovery_method }}
- Test: {{ bug.test_name }}
- Error: {{ bug.error_message }}

Generated: {{ bug.timestamp.isoformat() }}
"""

import pytest
from tests.e2e_ui.fixtures.auth_fixtures import authenticated_page
from tests.e2e_ui.fixtures.database_fixtures import db_session


@pytest.mark.regression
@pytest.mark.slow
def test_regression_{{ bug_id }}(db_session):
    """
    Regression test for bug {{ bug_id }}

    {% if reproduction_steps %}
    Reproduction Steps:
    {{ reproduction_steps }}
    {% endif %}

    Expected Behavior:
    {{ expected_behavior }}

    Actual Behavior (from bug report):
    {{ bug.error_message }}
    """
    # TODO: Implement test logic from bug metadata
    # This is a placeholder - implementation depends on bug type

    {% if bug.discovery_method == "fuzzing" %}
    # Fuzzing regression: Test with crash input
    crash_input = {{ bug.metadata.get("crash_input", "None") }}
    with pytest.raises(Exception):
        # Call function with crash input
        pass

    {% elif bug.discovery_method == "chaos" %}
    # Chaos regression: Test resilience under failure
    # Inject failure and verify graceful degradation
    assert True  # Placeholder

    {% elif bug.discovery_method == "property" %}
    # Property regression: Test invariant
    # This invariant should always hold
    assert True  # Placeholder

    {% elif bug.discovery_method == "browser" %}
    # Browser regression: Test UI doesn't crash
    # Navigate to URL and verify no errors
    assert True  # Placeholder
    {% endif %}
```

### Pattern 2: BugFixVerifier (FEEDBACK-03, SUCCESS-03)

**What:** Monitor GitHub Issues for "fix" labels, re-run regression tests, auto-close verified issues.

**When to use:** Continuous workflow or scheduled job (every 6 hours) to check for fix labels.

**Example:**
```python
# Source: backend/tests/bug_discovery/feedback_loops/bug_fix_verifier.py
from typing import List, Dict, Any
from datetime import datetime, timedelta
from github import Github
from tests.bug_discovery.models.bug_report import BugReport
import subprocess
import sys

class BugFixVerifier:
    """
    Verify bug fixes by re-running regression tests and auto-closing GitHub issues.

    Workflow:
    1. Poll GitHub Issues for "fix" label
    2. Re-run associated regression test
    3. If test passes: Add verification comment, close issue
    4. If test fails: Add failure comment, keep issue open

    Example:
        verifier = BugFixVerifier(github_token, github_repository)
        verified_issues = verifier.verify_fixes()
        print(f"Verified {len(verified_issues)} bug fixes")
    """

    def __init__(self, github_token: str, github_repository: str):
        """
        Initialize BugFixVerifier.

        Args:
            github_token: GitHub Personal Access Token
            github_repository: Repository in format "owner/repo"
        """
        self.github_token = github_token
        self.github_repository = github_repository
        self.github = Github(github_token)
        self.repo = self.github.get_repo(github_repository)

    def verify_fixes(
        self,
        label: str = "fix",
        hours_ago: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Verify bug fixes for issues with "fix" label.

        Args:
            label: Label to search for (default: "fix")
            hours_ago: Only verify issues labeled in last N hours (default: 24)

        Returns:
            List of verification results (issue_number, test_passed, issue_closed)
        """
        # Search for issues with "fix" label
        issues = self.repo.get_issues(labels=[label], state="open")

        verification_results = []

        for issue in issues:
            # Check if issue was labeled recently
            if not self._was_labeled_recently(issue, label, hours_ago):
                continue

            print(f"[BugFixVerifier] Verifying fix for issue #{issue.number}: {issue.title}")

            # Extract bug_id from issue title or body
            bug_id = self._extract_bug_id(issue)

            if not bug_id:
                print(f"[BugFixVerifier] Warning: Could not extract bug_id from issue #{issue.number}")
                continue

            # Re-run regression test
            test_result = self._run_regression_test(bug_id)

            if test_result["passed"]:
                # Test passed - close issue
                self._close_issue_with_comment(
                    issue=issue,
                    bug_id=bug_id,
                    test_result=test_result
                )
                verification_results.append({
                    "issue_number": issue.number,
                    "test_passed": True,
                    "issue_closed": True,
                    "bug_id": bug_id
                })
            else:
                # Test failed - add comment
                self._add_failure_comment(
                    issue=issue,
                    bug_id=bug_id,
                    test_result=test_result
                )
                verification_results.append({
                    "issue_number": issue.number,
                    "test_passed": False,
                    "issue_closed": False,
                    "bug_id": bug_id
                })

        return verification_results

    def _was_labeled_recently(self, issue, label: str, hours_ago: int) -> bool:
        """Check if issue was labeled with specified label recently."""
        # Get issue timeline events
        events = list(issue.get_events())

        for event in events:
            if event.event == "labeled" and event.label.name == label:
                # Check if labeled within hours_ago
                time_since_label = datetime.utcnow() - event.created_at
                if time_since_label <= timedelta(hours=hours_ago):
                    return True

        return False

    def _extract_bug_id(self, issue) -> str:
        """
        Extract bug_id from GitHub issue.

        Searches issue title and body for bug_id pattern (e.g., "Bug ID: abc123def").
        """
        import re

        # Pattern: [Bug] abc123def: Test Name
        title_pattern = r'\[Bug\] ([a-f0-9]+):'

        # Search title
        title_match = re.search(title_pattern, issue.title)
        if title_match:
            return title_match.group(1)

        # Search body
        body_match = re.search(r'bug_id[:\s]+([a-f0-9]+)', issue.body, re.IGNORECASE)
        if body_match:
            return body_match.group(1)

        return None

    def _run_regression_test(self, bug_id: str) -> Dict[str, Any]:
        """
        Run regression test for bug_id.

        Args:
            bug_id: Bug identifier (first 8 chars of error_signature)

        Returns:
            Dict with passed (bool), output (str), duration_seconds (float)
        """
        import time

        # Find test file
        backend_dir = Path(__file__).parent.parent.parent.parent
        regression_tests_dir = backend_dir / "tests" / "bug_discovery" / "storage" / "regression_tests"

        test_files = list(regression_tests_dir.glob(f"*_{bug_id}.py"))

        if not test_files:
            return {
                "passed": False,
                "output": f"Regression test file not found for bug_id: {bug_id}",
                "duration_seconds": 0.0
            }

        test_file = test_files[0]

        # Run test
        start_time = time.time()

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", str(test_file), "-v"],
                capture_output=True,
                text=True,
                cwd=backend_dir,
                timeout=300  # 5 minute timeout
            )

            duration = time.time() - start_time

            return {
                "passed": result.returncode == 0,
                "output": result.stdout + result.stderr,
                "duration_seconds": duration
            }

        except subprocess.TimeoutExpired:
            return {
                "passed": False,
                "output": f"Test timed out after 5 minutes",
                "duration_seconds": 300.0
            }

    def _close_issue_with_comment(
        self,
        issue,
        bug_id: str,
        test_result: Dict[str, Any]
    ):
        """Close issue with verification comment."""
        comment_body = f"""## Bug Fix Verified ✅

Regression test for this bug has passed:
- Bug ID: {bug_id}
- Test Duration: {test_result['duration_seconds']:.2f} seconds
- Verified At: {datetime.utcnow().isoformat()}Z

Closing issue automatically.
"""

        issue.create_comment(comment_body)
        issue.edit(state="closed")
        print(f"[BugFixVerifier] Closed issue #{issue.number} - fix verified")

    def _add_failure_comment(
        self,
        issue,
        bug_id: str,
        test_result: Dict[str, Any]
    ):
        """Add failure comment to issue."""
        comment_body = f"""## Bug Fix Verification Failed ❌

Regression test for this bug is still failing:
- Bug ID: {bug_id}
- Test Duration: {test_result['duration_seconds']:.2f} seconds
- Verified At: {datetime.utcnow().isoformat()}Z

Test Output:
```
{test_result['output'][:1000]}
```

Please review the fix and re-label with "fix" when ready.
"""

        issue.create_comment(comment_body)
        print(f"[BugFixVerifier] Added failure comment to issue #{issue.number}")
```

### Pattern 3: ROITracker (FEEDBACK-04, FEEDBACK-05, SUCCESS-01)

**What:** Track ROI metrics for bug discovery (time saved, bugs prevented, cost effectiveness).

**When to use:** After each weekly bug discovery run, aggregate metrics and generate ROI report.

**Example:**
```python
# Source: backend/tests/bug_discovery/feedback_loops/roi_tracker.py
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime, timedelta
import sqlite3
import json

class ROITracker:
    """
    Track ROI metrics for bug discovery automation.

    Metrics collected:
    - Bugs found (by method, severity)
    - Time to discovery (automation vs manual QA)
    - Time to fix (from filed to closed)
    - Cost avoidance (bugs prevented from production)
    - Manual QA cost vs automation cost

    Example:
        tracker = ROITracker()
        tracker.record_discovery_run(bugs_found=42, duration_seconds=3600)
        tracker.record_fixes(fixed_bugs=15, avg_fix_time_hours=8)
        roi_report = tracker.generate_roi_report()
    """

    def __init__(self, db_path: str = None):
        """
        Initialize ROITracker.

        Args:
            db_path: Path to SQLite database (default: tests/bug_discovery/storage/metrics.db)
        """
        if db_path is None:
            backend_dir = Path(__file__).parent.parent.parent.parent
            db_path = backend_dir / "tests" / "bug_discovery" / "storage" / "metrics.db"

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database schema
        self._init_db()

        # Cost assumptions (configurable)
        self.manual_qa_hourly_rate = 75  # $/hour for manual QA
        self.developer_hourly_rate = 100  # $/hour for developer
        self.bug_production_cost = 10000  # Average cost of production bug

    def _init_db(self):
        """Initialize SQLite database with metrics schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Discovery runs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS discovery_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                bugs_found INTEGER NOT NULL,
                unique_bugs INTEGER NOT NULL,
                filed_bugs INTEGER NOT NULL,
                duration_seconds REAL NOT NULL,
                by_method TEXT NOT NULL,
                by_severity TEXT NOT NULL,
                automation_cost REAL NOT NULL
            )
        """)

        # Bug fixes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bug_fixes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bug_id TEXT NOT NULL,
                issue_number INTEGER NOT NULL,
                filed_at TEXT NOT NULL,
                fixed_at TEXT NOT NULL,
                fix_duration_hours REAL NOT NULL,
                severity TEXT NOT NULL
            )
        """)

        # ROI summary table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS roi_summary (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week_start TEXT NOT NULL UNIQUE,
                bugs_found INTEGER NOT NULL,
                bugs_fixed INTEGER NOT NULL,
                hours_saved REAL NOT NULL,
                cost_saved REAL NOT NULL,
                automation_cost REAL NOT NULL,
                roi REAL NOT NULL
            )
        """)

        conn.commit()
        conn.close()

    def record_discovery_run(
        self,
        bugs_found: int,
        unique_bugs: int,
        filed_bugs: int,
        duration_seconds: float,
        by_method: Dict[str, int],
        by_severity: Dict[str, int]
    ):
        """
        Record bug discovery run metrics.

        Args:
            bugs_found: Total bugs found (including duplicates)
            unique_bugs: Unique bugs after deduplication
            filed_bugs: Bugs filed to GitHub
            duration_seconds: Discovery run duration
            by_method: Bugs by discovery method (e.g., {"fuzzing": 10, "chaos": 5})
            by_severity: Bugs by severity (e.g., {"critical": 2, "high": 8})
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Calculate automation cost (developer time)
        automation_cost = (duration_seconds / 3600) * self.developer_hourly_rate

        cursor.execute("""
            INSERT INTO discovery_runs (
                timestamp, bugs_found, unique_bugs, filed_bugs,
                duration_seconds, by_method, by_severity, automation_cost
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.utcnow().isoformat(),
            bugs_found,
            unique_bugs,
            filed_bugs,
            duration_seconds,
            json.dumps(by_method),
            json.dumps(by_severity),
            automation_cost
        ))

        conn.commit()
        conn.close()

    def record_fixes(
        self,
        bug_ids: List[str],
        issue_numbers: List[int],
        filed_dates: List[str],
        fix_duration_hours: float
    ):
        """
        Record bug fix metrics.

        Args:
            bug_ids: List of bug IDs
            issue_numbers: List of GitHub issue numbers
            filed_dates: List of filed dates (ISO format)
            fix_duration_hours: Average time to fix (hours)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for bug_id, issue_number, filed_date in zip(bug_ids, issue_numbers, filed_dates):
            # Calculate severity-based fix cost
            # TODO: Fetch severity from BugReport database
            severity = "unknown"

            cursor.execute("""
                INSERT INTO bug_fixes (
                    bug_id, issue_number, filed_at, fixed_at, fix_duration_hours, severity
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                bug_id,
                issue_number,
                filed_date,
                datetime.utcnow().isoformat(),
                fix_duration_hours,
                severity
            ))

        conn.commit()
        conn.close()

    def generate_roi_report(self, weeks: int = 4) -> Dict[str, Any]:
        """
        Generate ROI report for last N weeks.

        Args:
            weeks: Number of weeks to include in report (default: 4)

        Returns:
            Dict with ROI metrics (bugs_found, bugs_fixed, hours_saved, cost_saved, roi_ratio)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Calculate week start date
        week_start = (datetime.utcnow() - timedelta(weeks=weeks)).isoformat()

        # Aggregate discovery metrics
        cursor.execute("""
            SELECT
                SUM(bugs_found) as total_bugs_found,
                SUM(unique_bugs) as total_unique_bugs,
                SUM(filed_bugs) as total_filed_bugs,
                SUM(duration_seconds) as total_duration_seconds,
                SUM(automation_cost) as total_automation_cost
            FROM discovery_runs
            WHERE timestamp >= ?
        """, (week_start,))

        discovery_row = cursor.fetchone()

        # Aggregate fix metrics
        cursor.execute("""
            SELECT
                COUNT(*) as total_fixed_bugs,
                AVG(fix_duration_hours) as avg_fix_duration_hours
            FROM bug_fixes
            WHERE fixed_at >= ?
        """, (week_start,))

        fix_row = cursor.fetchone()

        conn.close()

        # Calculate ROI metrics
        total_bugs_found = discovery_row[0] or 0
        total_unique_bugs = discovery_row[1] or 0
        total_filed_bugs = discovery_row[2] or 0
        total_duration_seconds = discovery_row[3] or 0
        total_automation_cost = discovery_row[4] or 0
        total_fixed_bugs = fix_row[0] or 0
        avg_fix_duration_hours = fix_row[1] or 0

        # Calculate time saved (manual QA vs automation)
        # Assumption: Manual QA takes 2 hours per bug
        manual_qa_hours = total_bugs_found * 2
        automation_hours = total_duration_seconds / 3600
        hours_saved = manual_qa_hours - automation_hours

        # Calculate cost saved
        manual_qa_cost = manual_qa_hours * self.manual_qa_hourly_rate
        cost_saved = manual_qa_cost - total_automation_cost

        # Calculate bugs prevented from production (cost avoidance)
        # Assumption: 10% of bugs found would have reached production
        bugs_prevented = int(total_bugs_found * 0.1)
        cost_avoidance = bugs_prevented * self.bug_production_cost

        # Total savings
        total_savings = cost_saved + cost_avoidance

        # ROI ratio (savings / cost)
        roi_ratio = total_savings / total_automation_cost if total_automation_cost > 0 else 0

        return {
            "period_weeks": weeks,
            "period_start": week_start,
            "bugs_found": total_bugs_found,
            "unique_bugs": total_unique_bugs,
            "filed_bugs": total_filed_bugs,
            "bugs_fixed": total_fixed_bugs,
            "manual_qa_hours": manual_qa_hours,
            "automation_hours": automation_hours,
            "hours_saved": hours_saved,
            "manual_qa_cost": manual_qa_cost,
            "automation_cost": total_automation_cost,
            "cost_saved": cost_saved,
            "bugs_prevented": bugs_prevented,
            "cost_avoidance": cost_avoidance,
            "total_savings": total_savings,
            "roi_ratio": roi_ratio,
            "avg_fix_duration_hours": avg_fix_duration_hours
        }
```

### Pattern 4: Enhanced DashboardGenerator (FEEDBACK-02)

**What:** Extend DashboardGenerator with ROI metrics, regression rate tracking, fix verification status.

**When to use:** Weekly report generation after DiscoveryCoordinator completes full discovery run.

**Example (extends existing DashboardGenerator):**
```python
# Source: backend/tests/bug_discovery/core/dashboard_generator.py (ENHANCED)

# Add ROI metrics section to HTML template
def _render_html_template_with_roi(self, roi_data: Dict[str, Any]) -> str:
    """Render HTML template with ROI metrics section."""
    return f"""<!DOCTYPE html>
<html>
<head>
    <title>Weekly Bug Discovery Report - {week_date}</title>
    <style>
        /* ... existing styles ... */
        .roi-card {{ border: 2px solid #4caf50; background: #e8f5e9; }}
        .roi-positive {{ color: #4caf50; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Weekly Bug Discovery Report - {week_date}</h1>

        <!-- Existing summary cards -->
        <div class="summary">
            <div class="card critical">
                <h3>Bugs Found</h3>
                <div class="value">{bugs_found}</div>
            </div>
            <!-- ... existing cards ... -->
        </div>

        <!-- NEW: ROI Metrics Section -->
        <h2>ROI Metrics (Last 4 Weeks)</h2>
        <div class="summary">
            <div class="card roi-card">
                <h3>Hours Saved</h3>
                <div class="value roi-positive">{roi_data['hours_saved']:.1f}h</div>
                <p>Manual QA: {roi_data['manual_qa_hours']:.1f}h → Automation: {roi_data['automation_hours']:.1f}h</p>
            </div>
            <div class="card roi-card">
                <h3>Cost Saved</h3>
                <div class="value roi-positive">${roi_data['cost_saved']:,.0f}</div>
                <p>Manual QA: ${roi_data['manual_qa_cost']:,.0f} → Automation: ${roi_data['automation_cost']:,.0f}</p>
            </div>
            <div class="card roi-card">
                <h3>Bugs Prevented</h3>
                <div class="value roi-positive">{roi_data['bugs_prevented']}</div>
                <p>Cost Avoidance: ${roi_data['cost_avoidance']:,.0f}</p>
            </div>
            <div class="card roi-card">
                <h3>ROI Ratio</h3>
                <div class="value roi-positive">{roi_data['roi_ratio']:.1f}x</div>
                <p>Every $1 spent saves ${roi_data['total_savings'] / roi_data['automation_cost']:.2f}</p>
            </div>
        </div>

        <!-- NEW: Fix Verification Status -->
        <h2>Bug Fix Verification</h2>
        <table>
            <tr><th>Week</th><th>Fixed</th><th>Verified</th><th>Pending</th><th>Regression Rate</th></tr>
            {self._render_fix_verification_rows()}
        </table>

        <!-- Existing sections: Bugs by Method, Bugs by Severity, Top Bugs -->
        <!-- ... -->
    </div>
</body>
</html>"""
```

### Anti-Patterns to Avoid

- **Manual regression test creation**: Don't manually write regression tests from bug reports — use RegressionTestGenerator to auto-generate pytest files
- **Manual issue closing**: Don't manually close fixed issues — use BugFixVerifier to re-run tests and auto-close verified issues
- **Ignoring cost tracking**: Don't skip ROI metrics — collect time/cost data for every discovery run to demonstrate value
- **Regression without verification**: Don't file bugs without closing the loop — generate tests, verify fixes, close issues
- **Static dashboard without trends**: Don't show only current week — include week-over-week trends, regression rate, ROI metrics

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **GitHub API integration** | Custom REST API calls | PyGithub library | Handle rate limiting, authentication, webhooks automatically |
| **Test file templating** | String concatenation | Jinja2 templates | Clean separation of logic/presentation, reusability, maintainability |
| **Metrics storage** | JSON files | SQLite database | Structured queries, historical aggregation, trend analysis |
| **ROI calculations** | Custom spreadsheets | pandas (optional) | Time series analysis, cost aggregation, trend visualization |
| **Regression test patterns** | Custom test frameworks | pytest + fixtures | Existing infrastructure, 495+ E2E tests, CI integration |
| **Issue monitoring** | Polling loops | GitHub webhooks | Real-time event handling, no polling overhead |

**Key insight:** Feedback loops leverage existing bug discovery infrastructure (BugFilingService, DiscoveryCoordinator, DashboardGenerator, BugReport). RegressionTestGenerator converts bugs → tests, BugFixVerifier monitors GitHub → verifies fixes, ROITracker aggregates metrics → demonstrates value. Don't rebuild GitHub integration or test infrastructure.

## Common Pitfalls

### Pitfall 1: Ignoring Regression Test Maintainability

**What goes wrong:** Generated regression tests are brittle, hard to maintain, and become stale over time.

**Why it happens:** Tests are generated as monolithic scripts without clear structure, missing fixtures, or incomplete reproduction steps.

**How to avoid:**
1. Use pytest fixtures for setup/teardown (db_session, authenticated_page, browser)
2. Include docstrings with bug description, reproduction steps, expected behavior
3. Mark tests with @pytest.mark.regression for easy filtering
4. Add bug_id in test name for traceability (test_regression_fuzzing_abc123)
5. Include bug metadata (issue URL, filed date) in test file header

**Warning signs:** Generated tests have TODO placeholders, missing assertions, or no clear reproduction steps.

### Pitfall 2: Over-Automating Issue Closing

**What goes wrong:** Issues auto-close without proper verification, leading to false positives and developer distrust.

**Why it happens:** BugFixVerifier closes issues based on label without re-running test, or test passes but doesn't actually verify the fix.

**How to avoid:**
1. Always re-run regression test before closing issue
2. Add verification comment with test output and duration
3. Require "fix" label (not just any label) for verification
4. Keep issue open if test fails, add failure comment with next steps
5. Track verification metrics (false positive rate, re-open rate)

**Warning signs:** Issues closed immediately after labeling, developers complain about false verification, high re-open rate.

### Pitfall 3: Not Tracking Actual Costs

**What goes wrong:** ROI reports use hypothetical costs instead of actual time/cost data, leading to inflated ROI claims.

**Why it happens:** Using assumed hourly rates instead of actual project costs, not tracking real time spent on fixes.

**How to avoid:**
1. Track actual discovery run duration (use DiscoveryCoordinator timestamps)
2. Track actual fix duration (from GitHub issue filed_at to closed_at)
3. Use project-specific hourly rates (not generic $100/hour)
4. Include automation overhead (maintenance, false positive investigation)
5. Validate ROI claims with finance team

**Warning signs:** ROI claims seem too good to be true (10x, 20x), no actual time data, generic cost assumptions.

### Pitfall 4: Regression Rate Not Calculated

**What goes wrong:** Dashboard shows bugs found and fixed, but not regression rate (bugs reintroduced after fix).

**Why it happens:** Not tracking bug signatures across weeks, no historical bug database, missing signature matching logic.

**How to avoid:**
1. Store bug signatures in SQLite database (BugReport.error_signature)
2. Each week, check if any current bugs match previous weeks (same signature)
3. Calculate regression rate = (reintroduced_bugs / total_bugs) * 100
4. Display regression rate prominently in dashboard
5. Alert if regression rate exceeds threshold (e.g., 5%)

**Warning signs:** Same bugs filed multiple times, dashboard has no regression metric, no historical bug tracking.

### Pitfall 5: Test Generation Without Cleanup

**What goes wrong:** Regression test directory accumulates hundreds of test files, many for fixed bugs, creating maintenance burden.

**Why it happens:** Tests generated but never deleted after fixes verified, no test archival strategy.

**How to avoid:**
1. Archive tests for verified fixes (move to tests/regression/archived/)
2. Keep tests only for unresolved bugs or critical bugs
3. Add test metadata (bug_id, issue_number, fix_status) for filtering
4. Periodic cleanup job (archive tests for issues closed > 30 days)
5. Generate test execution report (which tests are still relevant)

**Warning signs:** Regression test directory has 500+ test files, CI takes too long, developers unsure which tests matter.

## Code Examples

Verified patterns from official sources:

### RegressionTestGenerator Integration (This Phase)
```python
# Source: backend/tests/bug_discovery/feedback_loops/regression_test_generator.py
from tests.bug_discovery.feedback_loops.regression_test_generator import RegressionTestGenerator
from tests.bug_discovery.models.bug_report import BugReport

generator = RegressionTestGenerator()

# Generate test from bug report
bug = BugReport(
    discovery_method="fuzzing",
    test_name="test_agent_api_fuzzing",
    error_message="SQL injection in agent_id parameter",
    error_signature="abc123def",
    metadata={"crash_file": "/tmp/crash-001.input"}
)

test_path = generator.generate_test_from_bug(bug)
print(f"Generated test: {test_path}")
# Output: tests/bug_discovery/storage/regression_tests/test_regression_fuzzing_abc123.py

# Generate tests from bug list
bugs = [bug1, bug2, bug3]
test_paths = generator.generate_tests_from_bug_list(bugs)
print(f"Generated {len(test_paths)} regression tests")
```

### BugFixVerifier Workflow
```python
# Source: backend/tests/bug_discovery/feedback_loops/bug_fix_verifier.py
from tests.bug_discovery.feedback_loops.bug_fix_verifier import BugFixVerifier

verifier = BugFixVerifier(
    github_token=os.getenv("GITHUB_TOKEN"),
    github_repository=os.getenv("GITHUB_REPOSITORY")
)

# Verify all fixes labeled in last 24 hours
results = verifier.verify_fixes(label="fix", hours_ago=24)

for result in results:
    if result["test_passed"]:
        print(f"Issue #{result['issue_number']}: FIX VERIFIED ✅")
    else:
        print(f"Issue #{result['issue_number']}: FIX FAILED ❌")
```

### ROI Tracking
```python
# Source: backend/tests/bug_discovery/feedback_loops/roi_tracker.py
from tests.bug_discovery.feedback_loops.roi_tracker import ROITracker

tracker = ROITracker()

# Record discovery run metrics
tracker.record_discovery_run(
    bugs_found=42,
    unique_bugs=35,
    filed_bugs=30,
    duration_seconds=3600,
    by_method={"fuzzing": 20, "chaos": 10, "property": 8, "browser": 4},
    by_severity={"critical": 2, "high": 10, "medium": 15, "low": 15}
)

# Record bug fixes
tracker.record_fixes(
    bug_ids=["abc123", "def456"],
    issue_numbers=[123, 124],
    filed_dates=["2026-03-20T10:00:00Z", "2026-03-21T14:00:00Z"],
    fix_duration_hours=8.0
)

# Generate ROI report
roi_report = tracker.generate_roi_report(weeks=4)

print(f"Hours Saved: {roi_report['hours_saved']:.1f}h")
print(f"Cost Saved: ${roi_report['cost_saved']:,.0f}")
print(f"ROI Ratio: {roi_report['roi_ratio']:.1f}x")
```

### Enhanced Dashboard with ROI Metrics
```python
# Source: backend/tests/bug_discovery/core/dashboard_generator.py (ENHANCED)
from tests.bug_discovery.core.dashboard_generator import DashboardGenerator
from tests.bug_discovery.feedback_loops.roi_tracker import ROITracker

generator = DashboardGenerator()
tracker = ROITracker()

# Get ROI metrics
roi_data = tracker.generate_roi_report(weeks=4)

# Generate weekly report with ROI section
report_path = generator.generate_weekly_report_with_roi(
    bugs_found=42,
    unique_bugs=35,
    filed_bugs=30,
    reports=bug_reports,
    roi_data=roi_data
)

print(f"Weekly report with ROI: {report_path}")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| **Manual bug filing** | Automated bug filing via BugFilingService | Phase 237 | GitHub Issues created automatically with rich metadata |
| **Separate discovery methods** | Unified orchestration via DiscoveryCoordinator | Phase 242 | Single coordinator runs all methods, aggregates results |
| **No regression tests** | Automated test generation from bugs | Phase 245 (this phase) | Bugs converted to permanent pytest tests automatically |
| **Manual fix verification** | Automated verification and issue closing | Phase 245 (this phase) | Re-run tests, auto-close verified issues |
| **No ROI tracking** | Comprehensive ROI metrics and reporting | Phase 245 (this phase) | Demonstrate cost savings, time saved, bug prevention value |
| **Static dashboard** | Dynamic dashboard with trends and ROI | Phase 245 (this phase) | Weekly reports show regression rate, fix status, ROI metrics |

**Deprecated/outdated:**
- **Manual regression test creation**: Replaced by RegressionTestGenerator with Jinja2 templates
- **Manual issue closing**: Replaced by BugFixVerifier with automated test re-running
- **Spreadsheet-based ROI tracking**: Replaced by ROITracker with SQLite + pandas
- **Static HTML reports**: Replaced by enhanced DashboardGenerator with ROI metrics and trends

## Open Questions

1. **Regression test archival strategy**
   - What we know: Tests for fixed bugs should be archived to avoid clutter
   - What's unclear: How long to keep archived tests (30 days? 90 days?), should we delete or move to archive/?
   - Recommendation: Move tests for verified fixes to tests/regression/archived/ after 30 days, keep critical bugs indefinitely

2. **False positive tolerance in verification**
   - What we know: BugFixVerifier should only close issues when test passes
   - What's unclear: What if test passes but bug still exists (test quality issue)? How to handle flaky tests?
   - Recommendation: Require 2 consecutive test passes before closing issue, track false positive rate, alert if >5%

3. **ROI calculation assumptions**
   - What we know: Need to track actual time and costs, not use hypothetical rates
   - What's unclear: What if actual hourly rates vary widely? How to account for automation overhead (maintenance, false positives)?
   - Recommendation: Use project-specific hourly rates from finance team, include 20% overhead factor for maintenance

4. **Regression rate threshold**
   - What we know: Should track and display regression rate (bugs reintroduced)
   - What's unclear: What regression rate is acceptable? At what threshold should we alert?
   - Recommendation: Alert if regression rate >5%, investigate if >10%, critical if >20%

5. **Integration with existing CI pipelines**
   - What we know: bug-discovery-weekly.yml runs weekly discovery
   - What's unclear: Should regression test generation run in same pipeline or separate job? Should BugFixVerifier run as separate scheduled workflow?
   - Recommendation: Add regression test generation to bug-discovery-weekly.yml, run BugFixVerifier as separate 6-hourly workflow

## Sources

### Primary (HIGH confidence)
- **BugFilingService Source** - `/Users/rushiparikh/projects/atom/backend/tests/bug_discovery/bug_filing_service.py` (503 lines) - GitHub Issues API, idempotency, metadata collection, severity classification
- **DiscoveryCoordinator Source** - `/Users/rushiparikh/projects/atom/backend/tests/bug_discovery/core/discovery_coordinator.py` (667 lines) - Unified orchestration, result aggregation, bug filing
- **DashboardGenerator Source** - `/Users/rushiparikh/projects/atom/backend/tests/bug_discovery/core/dashboard_generator.py` (263 lines) - Weekly HTML/JSON reports, Jinja2 templates
- **BugReport Model** - `/Users/rushiparikh/projects/atom/backend/tests/bug_discovery/models/bug_report.py` (81 lines) - Pydantic model with error_signature, metadata, stack_trace
- **InvariantGenerator Source** - `/Users/rushiparikh/projects/atom/backend/tests/bug_discovery/ai_enhanced/invariant_generator.py` (150+ lines) - AI test generation patterns, LLM code analysis
- **bug-discovery-weekly.yml** - `.github/workflows/bug-discovery-weekly.yml` - Weekly CI pipeline, 180-minute timeout, artifact upload
- **Phase 242 Research** - Unified bug discovery pipeline architecture, aggregation patterns, deduplication logic
- **Phase 244 Research** - AI-enhanced test generation patterns, LLM-based invariant suggestions

### Secondary (MEDIUM confidence)
- **PyGithub Documentation** - GitHub API integration, issue monitoring, label management
- **pytest Documentation** - Test fixtures, markers (@pytest.mark.regression), test discovery
- **Jinja2 Documentation** - Template rendering, test file generation from BugReport objects
- **SQLite Documentation** - Database schema, metrics storage, historical trend analysis

### Tertiary (LOW confidence)
- **Web search unavailable** - Rate limit exhausted, unable to verify 2026 best practices for regression test generation and ROI tracking
- **ROI calculation standards** - Not verified against industry benchmarks, need to validate assumptions with finance team
- **Regression test archival patterns** - No external verification, based on internal codebase patterns

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All tools proven in codebase (pytest, Pydantic, Jinja2, SQLite), PyGithub is standard for GitHub API
- Architecture: HIGH - Patterns extend existing infrastructure (BugFilingService, DiscoveryCoordinator, DashboardGenerator), clear separation of concerns
- Pitfalls: HIGH - Identified from test maintenance challenges, automation quality concerns, metric tracking best practices
- ROI tracking: MEDIUM - Cost calculation patterns are standard, but assumptions (hourly rates, production bug cost) need validation
- Regression rate calculation: MEDIUM - Algorithm is straightforward (signature matching), but archival strategy needs refinement

**Research date:** 2026-03-25
**Valid until:** 2026-04-24 (30 days - stable domain, test generation and ROI tracking are well-established practices)

**Next steps for planner:**
1. Design RegressionTestGenerator service with Jinja2 templates for each discovery method (fuzzing, chaos, property, browser)
2. Implement BugFixVerifier with PyGithub to monitor "fix" label, re-run tests, auto-close verified issues
3. Build ROITracker with SQLite database to store discovery runs, bug fixes, ROI metrics
4. Extend DashboardGenerator to include ROI metrics section, fix verification status, regression rate tracking
5. Create test file templates (pytest_regression_template.py.j2, fuzzing_regression_template.py.j2, etc.)
6. Define regression test archival strategy (move to archived/ after 30 days, keep critical bugs)
7. Integrate with bug-discovery-weekly.yml to generate regression tests after discovery run
8. Create separate GitHub Actions workflow for BugFixVerifier (6-hourly schedule)
9. Define test strategy for RegressionTestGenerator, BugFixVerifier, ROITracker (unit tests, integration tests)
10. Plan verification: 50+ bugs discovered, documented, and filed (SUCCESS-03), time saved vs manual QA (SUCCESS-01)
