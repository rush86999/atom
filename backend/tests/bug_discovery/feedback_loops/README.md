# Feedback Loops Services

Complete feedback loop automation for bug discovery with regression test generation, fix verification, and ROI tracking.

## Overview

The feedback loops package provides three services that close the bug discovery lifecycle:

1. **RegressionTestGenerator**: Convert BugReports to reproducible pytest test files
2. **BugFixVerifier**: Monitor GitHub Issues, re-run tests, auto-close verified fixes
3. **ROITracker**: Track ROI metrics and demonstrate business value

## RegressionTestGenerator

Converts discovered bugs into permanent regression tests.

### Usage

```python
from tests.bug_discovery.feedback_loops import RegressionTestGenerator

generator = RegressionTestGenerator()

# Generate test from single bug
test_path = generator.generate_test_from_bug(bug_report)
print(f"Generated: {test_path}")

# Generate tests from bug list
test_paths = generator.generate_tests_from_bug_list(bug_reports)
print(f"Generated {len(test_paths)} tests")

# Archive test for verified fix
archived_path = generator.archive_test(test_path, reason="verified")
```

### Templates

RegressionTestGenerator uses Jinja2 templates for each discovery method:

- `pytest_regression_template.py.j2`: Base template
- `fuzzing_regression_template.py.j2`: Fuzzing-specific tests
- `chaos_regression_template.py.j2`: Chaos engineering tests
- `property_regression_template.py.j2`: Property-based tests
- `browser_regression_template.py.j2`: Browser discovery tests

### Archival Strategy

Tests are moved to `archived/` subdirectory when:
- Bug fix is verified (2 consecutive test passes)
- GitHub issue is closed

Retention policy:
- Critical severity: Indefinite
- High severity: 1 year
- Medium/Low severity: 90 days

## BugFixVerifier

Automatically verifies bug fixes by re-running regression tests.

### Usage

```python
from tests.bug_discovery.feedback_loops import BugFixVerifier

verifier = BugFixVerifier(
    github_token=os.getenv("GITHUB_TOKEN"),
    github_repository=os.getenv("GITHUB_REPOSITORY")
)

# Verify all fixes labeled in last 24 hours
results = verifier.verify_fixes(label="fix", hours_ago=24)

for result in results:
    if result["issue_closed"]:
        print(f"Issue #{result['issue_number']}: CLOSED ✅")
    elif result["test_passed"]:
        print(f"Issue #{result['issue_number']}: PENDING ({result['consecutive_passes']}/2 passes)")
    else:
        print(f"Issue #{result['issue_number']}: FAILED ❌")
```

### Verification Workflow

1. Poll GitHub Issues for "fix" label
2. Extract bug_id from issue title/body
3. Find associated regression test file
4. Re-run test via subprocess pytest
5. If passes: Increment consecutive pass counter
6. If 2 consecutive passes: Add success comment, close issue
7. If fails: Reset counter, add failure comment

### Consecutive Passes

Requires 2 consecutive test passes before closing to prevent flaky test false positives.

State tracked in `.verification_state.json`:
```json
{
  "issue_123": {
    "bug_id": "abc123de",
    "consecutive_passes": 1,
    "last_passed": "2026-03-25T10:00:00Z"
  }
}
```

## ROITracker

Tracks ROI metrics for bug discovery automation.

### Usage

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

# Record bug fixes
tracker.record_fixes(
    bug_ids=["abc123", "def456"],
    issue_numbers=[123, 124],
    filed_dates=["2026-03-20T10:00:00Z", "2026-03-21T14:00:00Z"],
    fix_duration_hours=8.0
)

# Generate ROI report
roi_report = tracker.generate_roi_report(weeks=4)

print(f"Hours Saved: {roi_report['hours_saved']:.0f}h")
print(f"Cost Saved: ${roi_report['cost_saved']:,.0f}")
print(f"Bugs Prevented: {roi_report['bugs_prevented']}")
print(f"ROI: {roi_report['roi_ratio']:.1f}x")

# Save weekly summary
tracker.save_weekly_summary(roi_report)

# Get weekly trends for charts
trends = tracker.get_weekly_trends(weeks=12)
for week in trends:
    print(f"{week['week_start']}: {week['bugs_found']} bugs")
```

### Cost Assumptions

Default cost assumptions (configurable via `__init__`):

| Assumption | Default | Description |
|------------|---------|-------------|
| `manual_qa_hourly_rate` | $75/hour | Cost of manual QA labor |
| `developer_hourly_rate` | $100/hour | Cost of developer time |
| `bug_production_cost` | $10,000 | Average cost of production bug |
| `manual_qa_hours_per_bug` | 2 hours | Hours to manually find/report bug |

### ROI Calculation

```
Manual QA Cost = bugs_found × 2 hours × $75 = $150 × bugs_found
Automation Cost = (duration_seconds / 3600) × $100
Cost Saved = Manual QA Cost - Automation Cost
Bugs Prevented = bugs_found × 10% × $10,000
Total Savings = Cost Saved + Bugs Prevented
ROI Ratio = Total Savings / Automation Cost
```

### Database Schema

```sql
-- Discovery runs
CREATE TABLE discovery_runs (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    bugs_found INTEGER,
    unique_bugs INTEGER,
    filed_bugs INTEGER,
    duration_seconds REAL,
    by_method TEXT,              -- JSON
    by_severity TEXT,            -- JSON
    automation_cost REAL
);

-- Bug fixes
CREATE TABLE bug_fixes (
    id INTEGER PRIMARY KEY,
    bug_id TEXT,
    issue_number INTEGER,
    filed_at TEXT,
    fixed_at TEXT,
    fix_duration_hours REAL,
    severity TEXT,
    discovery_method TEXT
);

-- ROI summary (aggregated weekly)
CREATE TABLE roi_summary (
    id INTEGER PRIMARY KEY,
    week_start TEXT UNIQUE,
    bugs_found INTEGER,
    bugs_fixed INTEGER,
    hours_saved REAL,
    cost_saved REAL,
    automation_cost REAL,
    roi REAL,
    bugs_prevented INTEGER,
    cost_avoidance REAL,
    total_savings REAL,
    created_at TEXT
);
```

## Integration Example

Complete feedback loop integration:

```python
from tests.bug_discovery.core import DiscoveryCoordinator
from tests.bug_discovery.feedback_loops import BugFixVerifier, ROITracker
import os

# 1. Run discovery with feedback loops
coordinator = DiscoveryCoordinator(
    github_token=os.getenv("GITHUB_TOKEN"),
    github_repository=os.getenv("GITHUB_REPOSITORY"),
    enable_regression_tests=True,
    enable_roi_tracking=True
)

result = coordinator.run_full_discovery(duration_seconds=3600)

print(f"Bugs found: {result['bugs_found']}")
print(f"Regression tests: {len(result['regression_tests'])}")
print(f"ROI: {result['roi_data']['roi_ratio']:.1f}x")

# 2. Later, verify fixes
verifier = BugFixVerifier(
    github_token=os.getenv("GITHUB_TOKEN"),
    github_repository=os.getenv("GITHUB_REPOSITORY")
)

verification_results = verifier.verify_fixes()

# 3. Generate ROI report
roi_report = coordinator.get_roi_report(weeks=4)
weekly_trends = coordinator.get_weekly_trends(weeks=12)
```

## Testing

Unit tests for all feedback loop services:

```bash
# RegressionTestGenerator tests
pytest backend/tests/bug_discovery/feedback_loops/tests/test_regression_test_generator.py -v

# BugFixVerifier tests
pytest backend/tests/bug_discovery/feedback_loops/tests/test_bug_fix_verifier.py -v

# ROITracker tests
pytest backend/tests/bug_discovery/feedback_loops/tests/test_roi_tracker.py -v

# Dashboard enhancement tests
pytest backend/tests/bug_discovery/feedback_loops/tests/test_dashboard_enhancements.py -v
```

## Configuration

### Environment Variables

```bash
# GitHub Integration (BugFixVerifier)
GITHUB_TOKEN=ghp_xxx
GITHUB_REPOSITORY=owner/repo

# Cost Assumptions (ROITracker)
MANUAL_QA_HOURLY_RATE=75
DEVELOPER_HOURLY_RATE=100
BUG_PRODUCTION_COST=10000
MANUAL_QA_HOURS_PER_BUG=2
```

### File Locations

```bash
# Templates
backend/tests/bug_discovery/templates/*.j2

# Regression tests
backend/tests/bug_discovery/storage/regression_tests/test_regression_*.py
backend/tests/bug_discovery/storage/regression_tests/archived/

# Metrics database
backend/tests/bug_discovery/storage/metrics.db

# Verification state
backend/tests/bug_discovery/storage/regression_tests/.verification_state.json
```

## Best Practices

1. **Review generated tests**: Auto-generated tests are minimal - review and enhance
2. **Archive verified fixes**: Keep regression tests directory clean by archiving
3. **Validate ROI assumptions**: Review cost assumptions with finance team quarterly
4. **Monitor false positives**: Track false positive rate, adjust verification threshold if >5%

## Troubleshooting

### Regression test generation fails

```bash
# Check templates directory
ls backend/tests/bug_discovery/templates/

# Verify BugReport has error_signature
python -c "from tests.bug_discovery.models import BugReport; b = BugReport(...); print(b.error_signature)"
```

### Bug fix verification not running

```bash
# Check GitHub token has repo scope
gh auth status

# Verify "fix" label exists
gh label list
```

### ROI metrics seem inflated

```bash
# Review cost assumptions
python -c "from tests.bug_discovery.feedback_loops import ROITracker; t = ROITracker(); print(t.manual_qa_hourly_rate)"

# Adjust based on actual project costs
tracker = ROITracker(manual_qa_hourly_rate=50, developer_hourly_rate=80)
```
