# Unified Bug Discovery Pipeline

Automated bug discovery pipeline that orchestrates all discovery methods (fuzzing, chaos engineering, property tests, browser discovery) with result aggregation, deduplication, severity classification, automated bug filing, and weekly reporting.

## Overview

The Unified Bug Discovery Pipeline (Phase 242) ties together all bug discovery methods from previous phases into a single orchestration layer:

- **Fuzzing** (Phase 239): Atheris-based API fuzzing with crash deduplication
- **Chaos Engineering** (Phase 241): Controlled failure injection with blast radius controls
- **Property Tests** (Phase 238): Hypothesis-based invariant testing
- **Browser Discovery** (Phase 240): Headless browser exploration with console/accessibility detection

## Architecture

```
DiscoveryCoordinator (orchestrates all methods)
    -> ResultAggregator (normalizes to BugReport objects)
    -> BugDeduplicator (SHA256 error signature deduplication)
    -> SeverityClassifier (rule-based severity assignment)
    -> BugFilingService (GitHub Issues API)
    -> DashboardGenerator (weekly HTML/JSON reports)
```

## Usage

### Running Full Discovery

```python
from tests.bug_discovery.core import run_discovery
import os

result = run_discovery(
    github_token=os.getenv("GITHUB_TOKEN"),
    github_repository=os.getenv("GITHUB_REPOSITORY"),
    duration_seconds=3600
)

print(f"Bugs found: {result['bugs_found']}")
print(f"Unique bugs: {result['unique_bugs']}")
```

### Using DiscoveryCoordinator Directly

```python
from tests.bug_discovery.core import DiscoveryCoordinator

coordinator = DiscoveryCoordinator(
    github_token="your_token",
    github_repository="owner/repo"
)

result = coordinator.run_full_discovery(
    duration_seconds=3600,
    fuzzing_endpoints=["/api/v1/auth/login", "/api/v1/agents"],
    chaos_experiments=["network_latency_3g", "database_drop"],
    run_property_tests=True,
    run_browser_discovery=True
)
```

## Testing

```bash
# Unit tests
pytest backend/tests/bug_discovery/tests/ -v

# Integration tests
pytest backend/tests/bug_discovery/tests/test_discovery_coordinator.py -v

# Discovery pipeline tests
pytest backend/tests/bug_discovery/tests/ -v -m discovery
```

## Reports

Weekly reports: `backend/tests/bug_discovery/storage/reports/`
- `weekly-YYYY-MM-DD.html`: Human-readable HTML
- `weekly-YYYY-MM-DD.json`: Machine-readable JSON

## Troubleshooting

- **Discovery methods skipped**: Check dependencies (Atheris, Playwright, Toxiproxy)
- **Bug filing failures**: Verify GITHUB_TOKEN has `repo` scope
- **High memory usage**: Reduce duration_seconds or disable methods
- **Reports not generated**: Check storage/reports/ directory permissions

## Related Documentation

- Phase 238: Property-Based Testing Expansion
- Phase 239: API Fuzzing Infrastructure
- Phase 240: Headless Browser Bug Discovery
- Phase 241: Chaos Engineering Integration
- Research: `.planning/phases/242-unified-bug-discovery-pipeline/242-RESEARCH.md`
