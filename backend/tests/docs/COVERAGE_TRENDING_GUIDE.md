# Coverage Trending Guide

**Last Updated:** March 7, 2026
**Purpose:** Track coverage changes over time, detect regressions, visualize trends
**Data Retention:** 30-day rolling history, 90-day regression log

---

## Overview

The Coverage Trending Infrastructure provides automated tracking of test coverage across all platforms (Backend, Frontend, Mobile, Desktop) with weighted overall coverage calculation. This system enables:

- **Historical Tracking:** Per-commit coverage data with platform breakdown
- **Regression Detection:** Automatic identification of coverage drops >1% threshold
- **Visual Dashboard:** Self-contained HTML dashboard with matplotlib charts
- **CI/CD Integration:** Automated trending on every push/PR to main/develop
- **External Analysis:** Export trending data to CSV/JSON/Excel formats

### Components

| Component | Purpose | Location |
|-----------|---------|----------|
| **Trend Analyzer** | Detect regressions, validate data integrity | `backend/tests/scripts/coverage_trend_analyzer.py` |
| **Dashboard Generator** | Create HTML visualization with matplotlib charts | `backend/tests/scripts/generate_coverage_dashboard.py` |
| **CI/CD Workflow** | Automated trending on every build | `.github/workflows/coverage-trending.yml` |
| **Export Utility** | Export data for external analysis | `backend/tests/scripts/coverage_trend_export.py` |

### Platform Coverage Weights

| Platform | Weight | Rationale |
|----------|--------|-----------|
| Backend | 40% | Core business logic, API contracts, data layer |
| Frontend | 30% | User interface, client-side validation |
| Mobile | 20% | React Native app, device integration |
| Desktop | 10% | Tauri desktop app, platform-specific features |

**Overall Coverage Formula:**
```
overall = (backend * 0.40) + (frontend * 0.30) + (mobile * 0.20) + (desktop * 0.10)
```

### Data Retention Policy

- **Trending History:** 30-day rolling window (auto-pruned via `--prune` flag)
- **Regression Log:** 90-day retention (persistent log for audit trails)
- **CI/CD Artifacts:** 30-day retention (GitHub Actions default)
- **Dashboard HTML:** Self-contained, no external dependencies, permanent storage

---

## Quick Start

### Local Development Setup

**1. Install Dependencies**

```bash
# Core dependencies (required)
pip install matplotlib pandas jsonschema

# Optional: Excel export support
pip install openpyxl
```

**2. Run Trend Analyzer**

```bash
# Basic regression detection
cd backend
python tests/scripts/coverage_trend_analyzer.py \
  --trending-file tests/coverage_reports/metrics/cross_platform_trend.json

# Custom regression threshold
python tests/scripts/coverage_trend_analyzer.py \
  --regression-threshold 2.0 \
  --format markdown

# JSON output for CI/CD integration
python tests/scripts/coverage_trend_analyzer.py \
  --format json \
  --output tests/coverage_reports/metrics/coverage_regressions.json
```

**3. Generate Dashboard**

```bash
# Generate 30-day trend dashboard
python tests/scripts/generate_coverage_dashboard.py \
  --trending-file tests/coverage_reports/metrics/cross_platform_trend.json \
  --output tests/coverage_reports/dashboards/coverage_trend_30d.html \
  --days 30

# Custom dimensions (larger charts)
python tests/scripts/generate_coverage_dashboard.py \
  --trending-file tests/coverage_reports/metrics/cross_platform_trend.json \
  --output tests/coverage_reports/dashboards/coverage_trend_30d.html \
  --days 30 \
  --width 1600 \
  --height 900
```

**4. Export Historical Data**

```bash
# Export last 30 days to CSV
python tests/scripts/coverage_trend_export.py \
  --format csv \
  --days 30 \
  --output coverage_export.csv

# Export all history to JSON
python tests/scripts/coverage_trend_export.py \
  --format json \
  --days 0 \
  --output coverage_export_all.json

# Export to Excel (requires openpyxl)
python tests/scripts/coverage_trend_export.py \
  --format excel \
  --days 90 \
  --output coverage_export_quarterly.xlsx
```

### CI/CD Setup

**Workflow Triggers:**
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop` branches
- Manual dispatch via GitHub Actions UI

**Artifacts Available:**
- `coverage-trend-dashboard` (HTML) - 30-day retention
- `coverage-trending-data` (JSON files) - 30-day retention

**Job Summaries:**
- Automatic posting to GitHub Actions UI
- Trend report with +/- indicators per platform
- Regression alerts with severity levels (warning/critical)

**No Configuration Required:**
- Uses existing coverage files from `unified-tests-parallel.yml`
- Downloads artifacts automatically from 4 platform jobs
- Generates dashboard and uploads artifacts
- Posts trend report as job summary

---

## Script Reference

### coverage_trend_analyzer.py

**Purpose:** Detect significant coverage regressions and validate historical data integrity.

**Usage:**
```bash
python coverage_trend_analyzer.py [options]
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--trending-file PATH` | string | `tests/coverage_reports/metrics/cross_platform_trend.json` | Path to trending data file |
| `--regression-threshold FLOAT` | float | `1.0` | Regression threshold in percentage points |
| `--output PATH` | string | `tests/coverage_reports/metrics/coverage_regressions.json` | Path to regression output file |
| `--periods INT` | int | `7` | Number of periods to compare for trend |
| `--format FORMAT` | string | `text` | Output format: `text`, `json`, `markdown` |

**Exit Codes:**
- `0` - Success (no critical regressions)
- `1` - Critical regressions detected (threshold >5%)

**Examples:**

```bash
# Text output (human-readable)
python coverage_trend_analyzer.py --format text

# JSON output (CI/CD integration)
python coverage_trend_analyzer.py --format json --output regressions.json

# Markdown output (PR comments)
python coverage_trend_analyzer.py --format markdown --regression-threshold 2.0

# Custom trending file
python coverage_trend_analyzer.py --trending-file /path/to/custom_trend.json
```

**Output Format (Text):**
```
Coverage Trend Analysis
========================

Current Coverage: 72.3% (overall)
Historical Average (7 periods): 71.8%
Trend: +0.5% (improving)

Platform Breakdown:
- Backend: 85.2% (+1.2%)
- Frontend: 68.4% (-0.8%)
- Mobile: 52.1% (+0.3%)
- Desktop: 78.9% (+0.5%)

Regressions Detected: 2
⚠️ WARNING: Frontend coverage dropped 0.8% (threshold: 1.0%)
⚠️ WARNING: Mobile coverage dropped 1.5% (threshold: 1.0%)
```

**Output Format (JSON):**
```json
{
  "current_coverage": 72.3,
  "historical_average": 71.8,
  "trend_delta": 0.5,
  "platforms": {
    "backend": {"current": 85.2, "delta": 1.2},
    "frontend": {"current": 68.4, "delta": -0.8},
    "mobile": {"current": 52.1, "delta": -1.5},
    "desktop": {"current": 78.9, "delta": 0.5}
  },
  "regressions": [
    {
      "platform": "mobile",
      "current_coverage": 52.1,
      "previous_coverage": 53.6,
      "delta": -1.5,
      "severity": "warning",
      "detected_at": "2026-03-07T19:30:00Z"
    }
  ]
}
```

---

### generate_coverage_dashboard.py

**Purpose:** Generate self-contained HTML dashboard with matplotlib charts for coverage visualization.

**Usage:**
```bash
python generate_coverage_dashboard.py [options]
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--trending-file PATH` | string | `tests/coverage_reports/metrics/cross_platform_trend.json` | Path to trending data file |
| `--output PATH` | string | `coverage_trend_30d.html` | Path to output HTML file |
| `--days INT` | int | `30` | Number of days to include in dashboard |
| `--width INT` | int | `1200` | Chart width in pixels |
| `--height INT` | int | `600` | Chart height in pixels |

**Output:**
- Self-contained HTML file with embedded CSS/JavaScript
- Matplotlib charts encoded as base64 images
- No external dependencies (works offline)
- Responsive design for desktop/tablet/mobile viewing

**Examples:**

```bash
# Generate 30-day dashboard (default)
python generate_coverage_dashboard.py

# Generate 90-day dashboard
python generate_coverage_dashboard.py --days 90 --output coverage_trend_90d.html

# High-resolution dashboard (4K displays)
python generate_coverage_dashboard.py --width 2560 --height 1440

# Custom trending file
python generate_coverage_dashboard.py --trending-file /path/to/custom_trend.json
```

**Dashboard Sections:**

1. **Overall Coverage Trend** - Line chart showing weighted overall coverage over time
2. **Platform Breakdown** - Stacked area chart with per-platform coverage
3. **Regression Events** - Scatter plot highlighting regression points
4. **Summary Statistics** - Table with min/max/avg/current coverage per platform
5. **Commit History** - Timeline of coverage changes with commit SHAs

---

### coverage_trend_export.py

**Purpose:** Export trending data for external analysis (Excel, BI tools, custom scripts).

**Usage:**
```bash
python coverage_trend_export.py [options]
```

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--trending-file PATH` | string | `tests/coverage_reports/metrics/cross_platform_trend.json` | Path to trending data file |
| `--output PATH` | string | `coverage_export.csv` | Path to output file |
| `--format FORMAT` | string | `csv` | Export format: `csv`, `json`, `excel` |
| `--days INT` | int | `30` | Number of days to export (0 for all history) |

**Export Formats:**

**CSV Format:**
```csv
timestamp,overall_coverage,backend,frontend,mobile,desktop,commit_sha,branch
2026-03-07T19:30:00Z,72.3,85.2,68.4,52.1,78.9,abc123,main
2026-03-06T14:15:00Z,71.8,84.0,69.2,51.8,78.4,def456,develop
...
```

**JSON Format:**
```json
{
  "export_time": "2026-03-07T19:30:00Z",
  "total_entries": 30,
  "filtered_entries": 30,
  "date_range": {
    "start": "2026-02-06T00:00:00Z",
    "end": "2026-03-07T19:30:00Z"
  },
  "history": [
    {
      "timestamp": "2026-03-07T19:30:00Z",
      "overall_coverage": 72.3,
      "platforms": {
        "backend": 85.2,
        "frontend": 68.4,
        "mobile": 52.1,
        "desktop": 78.9
      },
      "commit_sha": "abc123",
      "branch": "main"
    }
  ]
}
```

**Excel Format:**
- **Sheet 1: Summary** - Overall stats, platform breakdown, min/max/avg/current
- **Sheet 2: History** - Time series data with all columns
- Formatted with headers, column widths, number formats
- Requires `openpyxl` dependency (`pip install openpyxl`)

**Examples:**

```bash
# Export last 30 days to CSV
python coverage_trend_export.py --format csv --days 30

# Export all history to JSON
python coverage_trend_export.py --format json --days 0

# Export last 90 days to Excel
python coverage_trend_export.py --format excel --days 90 --output quarterly_report.xlsx

# Custom output path
python coverage_trend_export.py --output /tmp/coverage_data.csv
```

---

## CI/CD Integration

### Workflow: coverage-trending.yml

**Location:** `.github/workflows/coverage-trending.yml`

**Triggers:**
- `push` to `main` or `develop` branches
- `pull_request` to `main` or `develop` branches
- `workflow_dispatch` (manual trigger via GitHub Actions UI)

**Dependencies:**
- `unified-tests-parallel.yml` (test-platform job)
- Waits for all 4 platform tests to complete (backend, frontend, mobile, desktop)

**Workflow Steps:**

1. **Download Artifacts** - Downloads coverage artifacts from all 4 platform jobs
2. **Run Cross-Platform Coverage Gate** - Computes weighted overall coverage
3. **Update Trending Data** - Appends new entry with commit SHA and branch tracking
4. **Detect Regressions** - Analyzes trends for significant drops (>1% threshold)
5. **Generate Dashboard** - Creates 30-day trend HTML dashboard
6. **Upload Artifacts** - Uploads dashboard and trending data (30-day retention)
7. **Post Job Summary** - Creates GitHub Actions job summary with trend report
8. **Post Regression Alerts** - Comments on PR with regression details
9. **Fail Build** - Exits with error if critical regressions detected (>5% threshold)

**Artifacts:**

| Artifact | Contents | Retention |
|----------|----------|-----------|
| `coverage-trend-dashboard` | HTML dashboard (30-day trend) | 30 days |
| `coverage-trending-data` | `cross_platform_trend.json`, `coverage_regressions.json` | 30 days |

**Job Summaries:**
- Automatic posting to GitHub Actions UI
- Includes overall coverage trend, platform breakdown, regression events
- Accessible via "Summary" button in workflow run page

**PR Comments:**
- Automatic posting on pull_request events
- Includes coverage trend with +/- indicators per platform
- Links to dashboard artifact for detailed visualization
- Regression alerts with severity levels

**Regression Alerts:**
- **Warning:** Coverage drop >1% threshold (logged, doesn't fail build)
- **Critical:** Coverage drop >5% threshold (fails build on main branch)
- Includes platform name, current/previous coverage, delta percentage

---

## Data Schema

### cross_platform_trend.json

**Structure:**
```json
{
  "history": [
    {
      "timestamp": "2026-03-07T19:30:00Z",
      "overall_coverage": 72.3,
      "platforms": {
        "backend": 85.2,
        "frontend": 68.4,
        "mobile": 52.1,
        "desktop": 78.9
      },
      "thresholds": {
        "backend": 80.0,
        "frontend": 80.0,
        "mobile": 60.0,
        "desktop": 70.0
      },
      "commit_sha": "abc123def456",
      "branch": "main"
    }
  ],
  "latest": {
    "timestamp": "2026-03-07T19:30:00Z",
    "overall_coverage": 72.3,
    "platforms": {
      "backend": 85.2,
      "frontend": 68.4,
      "mobile": 52.1,
      "desktop": 78.9
    }
  },
  "platform_trends": {
    "backend": {
      "current": 85.2,
      "average": 84.5,
      "min": 82.1,
      "max": 86.0
    }
  },
  "computed_weights": {
    "backend": 0.4,
    "frontend": 0.3,
    "mobile": 0.2,
    "desktop": 0.1
  }
}
```

**Entry Structure:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `timestamp` | string | Yes | ISO 8601 timestamp with Z suffix (UTC) |
| `overall_coverage` | float | Yes | Weighted overall coverage percentage (0-100) |
| `platforms` | object | Yes | Per-platform coverage dict (backend, frontend, mobile, desktop) |
| `thresholds` | object | Yes | Platform thresholds at time of recording |
| `commit_sha` | string | No | Git commit SHA (optional, for CI/CD tracking) |
| `branch` | string | No | Git branch name (optional, for CI/CD tracking) |

---

### coverage_regressions.json

**Structure:**
```json
{
  "regressions": [
    {
      "platform": "mobile",
      "current_coverage": 52.1,
      "previous_coverage": 53.6,
      "delta": -1.5,
      "severity": "warning",
      "detected_at": "2026-03-07T19:30:00Z",
      "commit_sha": "abc123def456"
    }
  ],
  "metadata": {
    "regression_threshold": 1.0,
    "critical_threshold": 5.0,
    "retention_days": 90,
    "last_updated": "2026-03-07T19:30:00Z"
  }
}
```

**Regression Entry Structure:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `platform` | string | Yes | Affected platform name (backend, frontend, mobile, desktop) |
| `current_coverage` | float | Yes | Coverage after regression (percentage) |
| `previous_coverage` | float | Yes | Coverage before regression (percentage) |
| `delta` | float | Yes | Percentage change (negative for regression) |
| `severity` | string | Yes | Severity level: `warning` (>1%), `critical` (>5%) |
| `detected_at` | string | Yes | ISO 8601 timestamp when regression detected |
| `commit_sha` | string | No | Associated commit SHA (optional) |

---

## Troubleshooting

### Missing Coverage Files

**Symptoms:**
- Trend analyzer reports "No trending data found"
- Dashboard shows empty charts
- CI/CD workflow fails to download artifacts

**Solutions:**

1. **Check unified-tests-parallel.yml artifact uploads:**
   ```bash
   # Verify workflow uploaded artifacts
   gh run list --workflow=unified-tests-parallel.yml --limit 5
   gh run view <run-id> --log
   ```

2. **Verify platform test jobs completed successfully:**
   - Check GitHub Actions UI for platform job status
   - Look for "backend-coverage", "frontend-coverage", "mobile-coverage", "desktop-coverage" artifacts
   - Re-run failed jobs if needed

3. **Check artifact retention policy:**
   - GitHub Actions artifacts have 7-day default retention
   - coverage-trending.yml extends retention to 30 days
   - Artifacts >30 days old are automatically deleted

4. **Manual artifact download (debug):**
   ```bash
   # Download artifact via GitHub CLI
   gh run download <run-id> -n backend-coverage

   # Verify coverage file exists
   ls -la coverage/backend/coverage.json
   ```

---

### Dashboard Not Rendering

**Symptoms:**
- HTML file opens but shows blank page
- Charts display as broken images
- JavaScript errors in browser console

**Solutions:**

1. **Verify matplotlib installed:**
   ```bash
   pip show matplotlib
   # If not installed:
   pip install matplotlib
   ```

2. **Check HTML file size:**
   ```bash
   # HTML should be >50KB (contains base64-encoded charts)
   ls -lh coverage_trend_30d.html
   # If <10KB, charts may not have been generated
   ```

3. **Open browser console for JavaScript errors:**
   - Chrome/Edge: F12 → Console tab
   - Firefox: F12 → Console tab
   - Look for errors like "Uncaught ReferenceError" or "Failed to load resource"

4. **Regenerate dashboard with verbose output:**
   ```bash
   python generate_coverage_dashboard.py --days 30 --output test.html
   # Check console output for matplotlib errors
   ```

---

### False Positive Regressions

**Symptoms:**
- Regression alerts for normal coverage fluctuations
- Threshold too sensitive for platform with high variance
- Regression detected immediately after adding new tests

**Solutions:**

1. **Adjust regression threshold:**
   ```bash
   # Increase threshold from 1.0% to 2.0%
   python coverage_trend_analyzer.py --regression-threshold 2.0
   ```

2. **Check for flaky test coverage:**
   - Some tests have non-deterministic coverage (random data, time-based logic)
   - Exclude flaky tests from coverage measurement using `.coveragerc`
   - Stabilize tests with mocking/fixed data

3. **Verify 30-day pruning not removing valid data:**
   ```bash
   # Check trending data file size
   ls -lh cross_platform_trend.json
   # Should have 30+ entries (one per day)
   # If only 1-2 entries, pruning may be too aggressive
   ```

4. **Use moving average for smoothing:**
   - Trend analyzer uses 7-period moving average by default
   - Increase `--periods` to 14 or 30 for smoother trends
   ```bash
   python coverage_trend_analyzer.py --periods 14
   ```

---

### CI/CD Workflow Not Triggering

**Symptoms:**
- Workflow doesn't run on push/PR
- Manual dispatch option not available
- Workflow fails immediately with "Workflow not found"

**Solutions:**

1. **Check branch name:**
   - Workflow only triggers on `main` and `develop` branches
   - Feature branches (e.g., `feature/new-ui`) won't trigger trending
   - Update workflow triggers if needed:
     ```yaml
     on:
       push:
         branches: [main, develop, feature/*]
     ```

2. **Verify workflow file syntax:**
   ```bash
   # Validate YAML syntax
   yamllint .github/workflows/coverage-trending.yml
   # Or use GitHub CLI:
   gh workflow view coverage-trending.yml --yaml
   ```

3. **Check GitHub Actions permissions:**
   - Repository settings → Actions → General → Workflow permissions
   - Ensure "Read and write permissions" is enabled
   - Check "Allow GitHub Actions to create and approve pull requests"

4. **Manual workflow trigger (debug):**
   ```bash
   # Trigger workflow manually
   gh workflow run coverage-trending.yml
   # View workflow run logs
   gh run list --workflow=coverage-trending.yml --limit 1
   gh run view <run-id> --log
   ```

---

## Best Practices

### Running Trending Analysis

- **Run after every significant code change** - Catch regressions early
- **Review dashboard weekly** - Look for trend patterns (gradual decline, plateau)
- **Investigate regressions >2% immediately** - Small drops compound over time
- **Archive historical data monthly** - Download full export for long-term analysis

### Adjusting Platform Weights

- **Review quarterly** - Business priorities change (new platforms, deprecation)
- **Update in `cross_platform_coverage_gate.py`** - Modify `PLATFORM_WEIGHTS` dict
- **Document rationale** - Add comment explaining weight change
- **Communicate to team** - Update team on new overall coverage calculation

### Regression Thresholds

- **Keep at 1% for early warning** - Catches small drops before they compound
- **Use 5% for critical failures** - Fails main branch builds on significant regressions
- **Adjust per-platform if needed** - Some platforms have higher variance (mobile, desktop)
- **Document threshold changes** - Track in ROADMAP.md or project wiki

### Data Retention

- **30-day trending history** - Sufficient for short-term trend analysis
- **90-day regression log** - Audit trail for quality metrics
- **Monthly archives** - Export full history to JSON for permanent storage
- **CI/CD artifacts** - 30-day GitHub Actions retention (extendable to 90 days)

---

## Reference

### Platform-Specific Testing Guides

- **[Frontend Testing Guide](../../docs/FRONTEND_TESTING_GUIDE.md)** - Jest coverage targets and per-module thresholds
- **[Mobile Testing Guide](../../docs/MOBILE_TESTING_GUIDE.md)** - jest-expo coverage for React Native
- **[Desktop Testing Guide](../../docs/DESKTOP_TESTING_GUIDE.md)** - tarpaulin coverage for Rust/Tauri

### Related Documentation

- **PARALLEL_EXECUTION_GUIDE.md** - Test execution strategy and CI/CD workflow
- **CROSS_PLATFORM_COVERAGE.md** - Coverage thresholds and weighted calculation
- **ROADMAP.md** - Phase 150 quality infrastructure details

### Related Scripts

- **cross_platform_coverage_gate.py** - Coverage threshold enforcement
- **update_cross_platform_trending.py** - Data tracking and commit history
- **ci_status_aggregator.py** - Test results aggregation

### File Locations

| Type | Location |
|------|----------|
| **Scripts** | `backend/tests/scripts/` |
| **Data** | `backend/tests/coverage_reports/metrics/` |
| **Dashboards** | `backend/tests/coverage_reports/dashboards/` |
| **Docs** | `backend/tests/docs/` |
| **Workflows** | `.github/workflows/` |

### Quick Command Reference

```bash
# Run trend analyzer
python backend/tests/scripts/coverage_trend_analyzer.py

# Generate dashboard
python backend/tests/scripts/generate_coverage_dashboard.py --days 30

# Export data
python backend/tests/scripts/coverage_trend_export.py --format csv --days 30

# CI/CD workflow trigger
gh workflow run coverage-trending.yml

# View latest workflow run
gh run list --workflow=coverage-trending.yml --limit 1
gh run view $(gh run list --workflow=coverage-trending.yml --limit 1 --json databaseId --jq '.[0].databaseId') --log
```

---

**Last Updated:** March 7, 2026
**Maintained By:** Atom Quality Infrastructure Team
**Questions?** See ROADMAP.md Phase 150 or open GitHub issue
