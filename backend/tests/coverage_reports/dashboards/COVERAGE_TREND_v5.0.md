# Coverage Trend Dashboard v5.0

**Generated:** 2026-03-01 12:48:03 UTC
**Purpose:** Track progress toward 80% coverage goal with historical trends

## Executive Summary

| Metric | Value |
|--------|-------|
| **Current Coverage** | **21.67%** |
| **Baseline** | 21.67% |
| **Target** | 80.00% |
| **Remaining** | 58.33% |
| **Progress** | 27.1% |
| **Total Snapshots** | 5 |
| **Date Range** | 2026-02-27 to 2026-02-27 |

### Visual Progress Bar

[█████░░░░░░░░░░░░░░░] 27.1%

### Coverage Statistics

- **Lines Covered:** 18,552 / 69,417
- **Branch Coverage:** 1.14%
- **Covered Branches:** 194 / 17,080

---

## Overall Coverage Trend

```
Coverage Trend (last 5 snapshots)
======================================================================
 80.0% |     | <-- 80% TARGET
 76.1% |     | <-- 80% TARGET
 72.2% |     |
 68.3% |     |
 64.4% |     |
 60.6% |     |
 56.7% |     |
 52.8% |     |
 48.9% |     |
 45.0% |     |
 41.1% |     |
 37.2% |     |
 33.3% |     |
 29.4% |     |
 25.6% |B***C|
 21.7% |B***C|
       +-----+
Legend: B = Baseline, C = Current, * = Historical snapshot
```

### Trend Analysis

- **Total Change:** 0.00% (stable at 21.67%)
- **Trend:** Stable →
- **Average Change:** +0.000% per snapshot

---

## Module Breakdown

### Core Module (24.28%)

- **Current:** 24.28%
- **Average:** 24.28%
- **Range:** 24.28% - 24.28%
- **Snapshots:** 5

Progress to 80%: [██████░░░░░░░░░░░░░░] 30.3% (55.72% remaining)

```
 24.3% |     |
 24.8% |     |
 24.3% |     |
       +-----+
```

**Trend:** Stable → (+0.00% from baseline)

---

### Api Module (36.38%)

- **Current:** 36.38%
- **Average:** 36.38%
- **Range:** 36.38% - 36.38%
- **Snapshots:** 5

Progress to 80%: [█████████░░░░░░░░░░░] 45.5% (43.62% remaining)

```
 36.4% |     |
 36.9% |     |
 36.4% |     |
       +-----+
```

**Trend:** Stable → (+0.00% from baseline)

---

### Tools Module (12.93%)

- **Current:** 12.93%
- **Average:** 12.93%
- **Range:** 12.93% - 12.93%
- **Snapshots:** 5

Progress to 80%: [███░░░░░░░░░░░░░░░░░] 16.2% (67.07% remaining)

```
 12.9% |     |
 13.4% |     |
 12.9% |     |
       +-----+
```

**Trend:** Stable → (+0.00% from baseline)

---

## Detailed Analysis

### Coverage Momentum (Last 5 Snapshots)

- **Average Change:** +0.000% per snapshot
- **Momentum:** 🟡 Neutral

### Module Performance Comparison

| Module | Current | Baseline | Change | Target | Gap |
|--------|---------|----------|--------|--------|-----|
| Core | 24.28% | 24.28% | +0.00% | 80.00% | 55.72% |
| Api | 36.38% | 36.38% | +0.00% | 80.00% | 43.62% |
| Tools | 12.93% | 12.93% | +0.00% | 80.00% | 67.07% |

### Recommendations

- ⚠️ **Critical Gap:** More than 50% below target. Focus on high-impact files first.

---

## Forecast to 80%

**Cannot forecast**

---

## Detailed Snapshot History

Showing 5 most recent snapshots (oldest to newest):

| # | Date | Coverage | Lines | Branch | Delta | Commit | Message |
|---|------|----------|-------|--------|-------|--------|---------|
| 1 | 2026-02-27 16:25 | 21.67% | 18,552/69,417 | 1.1% | +0.00% | `09ae09bb` | feat(100-04): Create coverage trend trac |
| 2 | 2026-02-27 16:26 | 21.67% | 18,552/69,417 | 1.1% | +0.00% | `d9cab6e4` | feat(100-04): Initialize trend tracking  |
| 3 | 2026-02-27 16:26 | 21.67% | 18,552/69,417 | 1.1% | +0.00% | `d9cab6e4` | feat(100-04): Initialize trend tracking  |
| 4 | 2026-02-27 16:26 | 21.67% | 18,552/69,417 | 1.1% | +0.00% | `d9cab6e4` | feat(100-04): Initialize trend tracking  |
| 5 | 2026-02-27 16:26 | 21.67% | 18,552/69,417 | 1.1% | +0.00% | `5361c707` | feat(100-04): Add trend analysis command |

---

## Metadata

| Property | Value |
|----------|-------|
| **Version** | 5.0 |
| **Target Coverage** | 80.0% |
| **Max History Entries** | 30 |
| **Total Snapshots** | 5 |
| **Created At** | 2026-02-27T16:25:48.934438Z |
| **Last Updated** | 2026-02-27T16:26:34.922639Z |

---

## How to Interpret This Dashboard

### Understanding the Charts

**Overall Coverage Trend:**
- Shows coverage over time with the last 30 snapshots
- `B` marks the baseline (first measurement)
- `C` marks the current (latest measurement)
- `*` marks historical snapshots
- `80% TARGET` line shows the goal

**Module Breakdown:**
- Core: `backend/core/` - Business logic, governance, LLM integration
- API: `backend/api/` - REST endpoints, routes, handlers
- Tools: `backend/tools/` - Browser automation, device capabilities

### Reading the Progress Bar

The visual progress bar shows completion toward 80%:
- `█` (filled blocks) = progress made
- `░` (empty blocks) = remaining work
- Total width = 20 characters (5% per character)

Example: `[█████░░░░░░░░░░░░░░░]` = 25% progress

### Forecast Scenarios

- **Optimistic:** 130% of recent velocity (best case)
- **Realistic:** 100% of recent velocity (expected case)
- **Pessimistic:** 70% of recent velocity (worst case)

Forecasts assume:
- Consistent test writing pace
- Linear coverage growth
- No major refactoring that reduces coverage

### Using This Data

**For Developers:**
- Focus on modules with largest gap to 80%
- Prioritize files with 0% coverage for quick wins
- Track impact of test additions in snapshot history
- Verify coverage increases after writing tests

**For Project Managers:**
- Monitor velocity to estimate completion timeline
- Use forecast scenarios for risk planning
- Check trend direction (should be increasing)
- Allocate resources based on module gaps

**For QA Teams:**
- Identify under-tested modules (low coverage %)
- Track regression (sudden decreases in trend)
- Validate test coverage after feature releases
- Prioritize testing efforts by module risk

### Updating This Dashboard

This dashboard is automatically updated:
- After each CI/CD pipeline run
- When tests are executed locally with coverage tracking
- Via manual update: `python tests/scripts/coverage_trend_tracker.py --commit <hash>`

### Quick Reference

**Good Coverage Trend:**
- Increasing by 0.5-2% per snapshot
- All modules showing upward momentum
- Forecast timeline within 3-6 months

**Warning Signs:**
- Flat or decreasing trend (no progress)
- One module stagnant while others improve
- Large gaps between snapshots (infrequent testing)

---

## Technical Notes

### Data Collection Method

- **Tool:** pytest with pytest-cov plugin
- **Source:** `backend/tests/coverage_reports/metrics/coverage.json`
- **Frequency:** Per commit, max 30 entries retained
- **Format:** JSON with timestamps, git hashes, and commit messages

### Coverage Calculation

- **Statement Coverage:** Percentage of executed lines vs total lines
- **Branch Coverage:** Percentage of executed branches vs total branches
- **Module Breakdown:** Aggregated from file-level data
- **Threshold:** 80% target for all modules

### Data Files

- `coverage_trend_v5.0.json`: Main trend tracking file
- `trends/YYYY-MM-DD_coverage_trend.json`: Daily snapshots
- `coverage.json`: Latest coverage report
- `coverage_baseline.json`: Initial baseline from Phase 100

### Visualization

- **Format:** ASCII art (terminal-friendly, no dependencies)
- **Width:** Configurable (default: 70 characters)
- **Height:** Auto-scaled based on data range
- **Rendering:** Monospace font required for proper alignment

### Limitations

- Tracks backend Python code only (not frontend/mobile/desktop)
- Requires git repository for commit metadata
- Limited to last 30 snapshots (older data archived)
- Forecast assumes linear progression (may vary)

---

## Dashboard Changelog

### v5.0 (2026-03-01)
- Initial trend dashboard creation
- ASCII visualization for terminal display
- Per-module breakdown (core, api, tools)
- Forecast scenarios (optimistic, realistic, pessimistic)
- Detailed snapshot history with commit messages
- Coverage momentum and velocity tracking
- Module performance comparison
- Comprehensive user guide and technical notes

### Planned Enhancements
- [ ] Integration with frontend/mobile coverage data
- [ ] Automated PR comment generation
- [ ] Email alerts on regression detection
- [ ] Historical trend comparison by phase
- [ ] Coverage heatmaps by file/directory

---

*For questions or issues, see: `backend/tests/scripts/generate_coverage_dashboard.py`*
*Coverage data source: `backend/tests/coverage_reports/metrics/coverage_trend_v5.0.json`*

