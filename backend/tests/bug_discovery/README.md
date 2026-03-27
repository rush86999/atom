# Bug Discovery & Feedback Loops

Automated bug discovery through fuzzing, chaos engineering, property-based testing, and browser discovery with complete feedback loop integration.

## Overview

Atom's bug discovery system automatically finds bugs through multiple discovery methods and closes the feedback loop with:

1. **Automated Discovery**: Fuzzing, chaos, property tests, browser exploration
2. **Unified Pipeline**: DiscoveryCoordinator orchestrates all methods
3. **Automated Filing**: BugFilingService creates GitHub Issues
4. **Regression Tests**: RegressionTestGenerator converts bugs to pytest tests
5. **Fix Verification**: BugFixVerifier re-runs tests and auto-closes issues
6. **ROI Tracking**: ROITracker demonstrates value of automation

## Quick Start

### Run Full Discovery

```python
from tests.bug_discovery.core import run_discovery
import os

result = run_discovery(
    github_token=os.getenv("GITHUB_TOKEN"),
    github_repository=os.getenv("GITHUB_REPOSITORY"),
    duration_seconds=3600  # 1 hour
)

print(f"Bugs found: {result['bugs_found']}")
print(f"Unique bugs: {result['unique_bugs']}")
print(f"ROI: {result['roi_data']['roi_ratio']:.1f}x")
```

### Generate Regression Tests

```python
from tests.bug_discovery.feedback_loops import RegressionTestGenerator
from tests.bug_discovery.models.bug_report import BugReport, DiscoveryMethod, Severity
from datetime import datetime

generator = RegressionTestGenerator()

# Generate test from bug report
bug = BugReport(
    discovery_method=DiscoveryMethod.FUZZING,
    test_name="test_api_fuzzing",
    error_message="SQL injection in agent_id",
    error_signature="abc123def4567890",
    severity=Severity.CRITICAL
)

test_path = generator.generate_test_from_bug(bug)
print(f"Generated: {test_path}")
```

### Verify Bug Fixes

```python
from tests.bug_discovery.feedback_loops import BugFixVerifier
import os

verifier = BugFixVerifier(
    github_token=os.getenv("GITHUB_TOKEN"),
    github_repository=os.getenv("GITHUB_REPOSITORY")
)

results = verifier.verify_fixes(label="fix", hours_ago=24)

for r in results:
    if r["test_passed"]:
        print(f"Issue #{r['issue_number']}: VERIFIED ✅")
    else:
        print(f"Issue #{r['issue_number']}: FAILED ❌")
```

### Track ROI

```python
from tests.bug_discovery.feedback_loops import ROITracker

tracker = ROITracker()

# Record discovery run
tracker.record_discovery_run(
    bugs_found=42,
    unique_bugs=35,
    filed_bugs=30,
    duration_seconds=3600,
    by_method={"fuzzing": 20, "chaos": 10, "property": 8, "browser": 4},
    by_severity={"critical": 2, "high": 10, "medium": 15, "low": 15}
)

# Generate ROI report
roi_report = tracker.generate_roi_report(weeks=4)
print(f"Hours Saved: {roi_report['hours_saved']:.0f}h")
print(f"Cost Saved: ${roi_report['cost_saved']:,.0f}")
print(f"ROI: {roi_report['roi_ratio']:.1f}x")
```

## Architecture

### Discovery Pipeline

```
DiscoveryCoordinator
    ↓
1. Fuzzing Discovery (FuzzingOrchestrator)
    → BugReport objects
    ↓
2. Chaos Discovery (ChaosCoordinator)
    → BugReport objects
    ↓
3. Property Discovery (pytest)
    → BugReport objects
    ↓
4. Browser Discovery (Playwright)
    → BugReport objects
    ↓
5. Aggregation (ResultAggregator)
    → Normalized BugReport list
    ↓
6. Deduplication (BugDeduplicator)
    → Unique BugReport list
    ↓
7. Severity Classification (SeverityClassifier)
    → BugReport with severity
    ↓
8. Bug Filing (BugFilingService)
    → GitHub Issues
    ↓
9. Regression Tests (RegressionTestGenerator)
    → pytest test files
    ↓
10. ROI Tracking (ROITracker)
    → Metrics database
    ↓
11. Report Generation (DashboardGenerator)
    → HTML/JSON reports
```

### Feedback Loops

```
Discovered Bug
    ↓
RegressionTestGenerator → test_regression_{method}_{bug_id}.py
    ↓
Developer fixes bug, labels issue "fix"
    ↓
BugFixVerifier detects label, re-runs test
    ↓
Test passes 2x consecutively? → Close issue ✅
Test fails? → Add failure comment, keep open ❌
```

### ROI Calculation

```
Manual QA Cost:
  = bugs_found × manual_qa_hours_per_bug × manual_qa_hourly_rate
  = 50 × 2 × $75 = $7,500

Automation Cost:
  = duration_seconds / 3600 × developer_hourly_rate
  = 3600 / 3600 × $100 = $100

Cost Saved:
  = Manual QA Cost - Automation Cost
  = $7,500 - $100 = $7,400

Bugs Prevented:
  = bugs_found × 10% × bug_production_cost
  = 50 × 0.1 × $10,000 = $50,000

Total Savings:
  = Cost Saved + Bugs Prevented
  = $7,400 + $50,000 = $57,400

ROI Ratio:
  = Total Savings / Automation Cost
  = $57,400 / $100 = 574x
```

## Directory Structure

```
backend/tests/bug_discovery/
├── bug_filing_service.py          # GitHub Issues automation
├── feedback_loops/                # Feedback loop services
│   ├── __init__.py
│   ├── regression_test_generator.py
│   ├── bug_fix_verifier.py
│   ├── roi_tracker.py
│   ├── tests/
│   │   ├── test_regression_test_generator.py
│   │   ├── test_bug_fix_verifier.py
│   │   ├── test_roi_tracker.py
│   │   └── test_dashboard_enhancements.py
│   └── README.md                  # Feedback loops documentation
├── core/                          # Core orchestration
│   ├── __init__.py
│   ├── discovery_coordinator.py   # Main orchestrator
│   ├── result_aggregator.py
│   ├── bug_deduplicator.py
│   ├── severity_classifier.py
│   └── dashboard_generator.py     # Report generation
├── models/
│   ├── __init__.py
│   └── bug_report.py              # Unified bug model
├── storage/                       # Data storage
│   ├── reports/                   # Weekly HTML/JSON reports
│   ├── regression_tests/          # Generated regression tests
│   │   ├── archived/              # Verified fixes (archived)
│   │   └── .gitkeep
│   ├── metrics.db                 # ROI metrics database
│   └── bug_reports.db             # Bug database
├── fuzzing/                       # Fuzzing tests
├── chaos/                         # Chaos engineering tests
├── property_tests/                # Property-based tests
├── browser_discovery/             # Browser discovery tests
└── README.md                      # This file
```

## Discovery Methods

### Fuzzing (FUZZING)

Coverage-guided fuzzing for FastAPI endpoints using Atheris.

**What it finds:** SQL injection, XSS, CSRF, buffer overflows, parsing errors

**Example:**
```python
from tests.fuzzing.campaigns.fuzzing_orchestrator import FuzzingOrchestrator

orchestrator = FuzzingOrchestrator(github_token, github_repository)
result = orchestrator.run_campaign_with_bug_filing(
    target_endpoint="/api/v1/agents",
    test_file="tests/fuzzing/test_agent_api_fuzzing.py",
    duration_seconds=900
)
```

### Chaos Engineering (CHAOS)

Controlled failure injection testing resilience.

**What it finds:** Connection timeouts, memory exhaustion, cascading failures

**Example:**
```python
from tests.chaos.core.chaos_coordinator import ChaosCoordinator

coordinator = ChaosCoordinator(db_session=test_db, bug_filing_service=filing_service)
result = coordinator.run_experiment(
    experiment_name="network_latency_3g",
    failure_injection=LatencyInjection,
    verify_graceful_degradation=lambda: True,
    blast_radius_checks=[assert_blast_radius]
)
```

### Property-Based Testing (PROPERTY)

Hypothesis-based invariant testing.

**What it finds:** State machine violations, contract violations, edge cases

**Example:**
```bash
pytest tests/property_tests/ -v
```

### Browser Discovery (BROWSER)

Headless browser automation for UI bug detection.

**What it finds:** Console errors, accessibility violations, broken links

**Example:**
```python
from tests.browser_discovery.conftest import authenticated_page

page.goto("http://localhost:3000/dashboard")
errors = page.evaluate("() => window.__consoleErrors || []")
assert len(errors) == 0
```

## Configuration

### Environment Variables

```bash
# GitHub Integration
GITHUB_TOKEN=ghp_xxx                    # GitHub Personal Access Token
GITHUB_REPOSITORY=owner/repo             # Repository for issue filing

# Discovery Configuration
DISCOVERY_DURATION_SECONDS=3600          # Duration per discovery method
ENABLE_REGRESSION_TESTS=true            # Generate regression tests
ENABLE_ROI_TRACKING=true                # Track ROI metrics

# ROI Cost Assumptions (optional, uses defaults if not set)
MANUAL_QA_HOURLY_RATE=75                # Cost per hour for manual QA
DEVELOPER_HOURLY_RATE=100               # Cost per hour for developer
BUG_PRODUCTION_COST=10000               # Average cost of production bug
MANUAL_QA_HOURS_PER_BUG=2               # Hours to manually find a bug
```

### Pytest Configuration

```ini
# pytest.ini

[pytest]
markers =
    regression: Marks tests as regression tests
    fuzzing: Marks tests as fuzzing tests
    chaos: Marks tests as chaos engineering tests
    property: Marks tests as property-based tests
    browser: Marks tests as browser discovery tests
    slow: Marks tests as slow (run in weekly pipeline only)
```

## CI/CD Integration

### Weekly Bug Discovery Pipeline

Runs every Sunday at 2 AM UTC:

```yaml
# .github/workflows/bug-discovery-weekly.yml
on:
  schedule:
    - cron: '0 2 * * 0'  # Sunday 2 AM UTC

jobs:
  bug-discovery:
    steps:
      - uses: actions/checkout@v4
      - run: |
          python -c "
          from tests.bug_discovery.core import run_discovery
          run_discovery(
              github_token=os.getenv('GITHUB_TOKEN'),
              github_repository=os.getenv('GITHUB_REPOSITORY'),
              duration_seconds=3600
          )
          "
```

### Bug Fix Verification Pipeline

Runs every 6 hours to verify fixes:

```yaml
# .github/workflows/bug-fix-verification.yml
on:
  schedule:
    - cron: '0 */6 * * *'  # Every 6 hours

jobs:
  verify-fixes:
    steps:
      - run: |
          python -c "
          from tests.bug_discovery.feedback_loops import BugFixVerifier
          verifier = BugFixVerifier(...)
          verifier.verify_fixes()
          "
```

## Best Practices

### Writing Regression Tests

Generated regression tests should be reviewed and enhanced:

```python
# Auto-generated (minimal)
def test_regression_fuzzing_abc123de(api_client):
    # TODO: Implement test logic
    assert True  # Placeholder

# Enhanced (manual review)
def test_regression_fuzzing_abc123de(api_client):
    """Regression test for SQL injection in agent_id parameter."""
    # Test with malicious input
    response = api_client.post("/api/v1/agents", json={
        "agent_id": "1 OR 1=1--"
    })

    # Should reject malicious input
    assert response.status_code in [400, 422]

    # Test with valid input
    response = api_client.post("/api/v1/agents", json={
        "agent_id": "valid-uuid"
    })

    # Should accept valid input
    assert response.status_code == 200
```

### Archival Strategy

Regression tests are archived when:

1. Bug fix is verified (test passes 2x consecutively)
2. GitHub issue is closed
3. Test moved to `regression_tests/archived/`

Restoration:

If a bug recurs (same error_signature detected):
1. Test moved back from `archived/`
2. Re-run to confirm bug exists
3. Re-open GitHub issue if confirmed

## Metrics & Effectiveness

### Key Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| Bugs found per hour | Discovery throughput | > 10/hour |
| Unique bug rate | Deduplication effectiveness | > 70% |
| False positive rate | Bugs not confirmed | < 5% |
| Fix verification rate | Bugs with verified fixes | > 80% |
| ROI ratio | Cost savings vs automation cost | > 10x |

### Weekly Report Sections

1. **Bug Discovery Summary**: Bugs found, unique, filed
2. **ROI Metrics**: Hours saved, cost saved, bugs prevented, ROI ratio
3. **Fix Verification**: Fixed, verified, pending counts
4. **By Method**: Breakdown by discovery method
5. **By Severity**: Breakdown by severity
6. **Top Bugs**: Highest priority bugs

## Troubleshooting

### Regression Test Generation Fails

```bash
# Check templates exist
ls backend/tests/bug_discovery/templates/*.j2

# Verify BugReport has required fields
python -c "from tests.bug_discovery.models import BugReport; print(BugReport.__fields__)"
```

### Bug Fix Verification Not Running

```bash
# Check GitHub token has repo scope
# Check workflow is enabled in GitHub Actions
# Verify "fix" label exists in repository
```

### ROI Metrics Not Appearing

```bash
# Check metrics.db exists
ls backend/tests/bug_discovery/storage/metrics.db

# Verify ROI tracking enabled
python -c "from tests.bug_discovery.core import DiscoveryCoordinator; c = DiscoveryCoordinator(...); print(c.enable_roi_tracking)"
```

## Further Reading

- [Bug Discovery Infrastructure](./docs/BUG_DISCOVERY_INFRASTRUCTURE.md)
- [Feedback Loops Documentation](./feedback_loops/README.md)
- [Property-Based Testing](./property_tests/README.md)
- [Chaos Engineering](./chaos/README.md)
- [Fuzzing Guide](./fuzzing/README.md)

## Contributing

When adding new discovery methods:

1. Create BugReport objects with required fields
2. Add method to DiscoveryMethod enum
3. Implement aggregation in ResultAggregator
4. Update DashboardGenerator templates
5. Add regression test template
