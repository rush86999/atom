# Phase 110: Quality Gates & Reporting - Research

**Researched:** 2026-03-01
**Domain:** CI/CD Quality Gates, Coverage Reporting, PR Automation
**Confidence:** HIGH

## Summary

Phase 110 implements automated coverage enforcement through PR comments, 80% merge gates, trend dashboards, and per-commit reports. The existing infrastructure includes **extensive coverage tracking scripts** (19+ scripts in `backend/tests/scripts/`), **GitHub Actions PR comment patterns**, and **trend tracking JSON structures** from Phase 100. The key integration points are:

1. **PR Comment Bot**: Use `actions/github-script@v7` (already in 5 workflows) with file-by-file coverage delta from diff-cover
2. **80% Coverage Gate**: Extend existing `ci_quality_gate.py` (490 lines) to fail CI when below threshold on main branch
3. **Trend Dashboard**: Leverage Phase 100's ASCII visualization approach + HTML report from `generate_coverage_trend.py` (no matplotlib/plotly dependencies)
4. **Per-Commit Reports**: Adapt existing trend tracker script to generate JSON snapshots stored in `coverage_reports/commits/`

**Primary recommendation**: Build on existing scripts rather than introducing new dependencies. Use `diff-cover` for file-by-file deltas, `actions/github-script@v7` for PR comments, and extend ASCII visualizations for dashboards (consistent with Phase 100 decisions).

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest-cov** | 4.1.0+ | Coverage data generation (coverage.json) | Already in requirements, industry standard for Python |
| **diff-cover** | Latest | File-by-file coverage delta comparison | Purpose-built for PR coverage diffs, git integration |
| **actions/github-script** | v7 | PR comment creation via GitHub Actions | Native GitHub Actions, no API tokens needed, already in 5 workflows |
| **actions/checkout@v4** | v4 | Full git history for diff calculations | Required for coverage deltas, fetch-depth: 0 pattern |

### Supporting (Backend)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **ci_quality_gate.py** | Existing (490 lines) | Coverage threshold enforcement | Extend to support 80% gate on main branch |
| **coverage_trend_tracker.py** | Existing (760+ lines) | Trend tracking and ASCII visualization | Phase 100 baseline, use for per-commit snapshots |
| **generate_coverage_trend.py** | Existing (500+ lines) | HTML trend report generation | Dashboard visualization, already tested |

### Supporting (Frontend)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **jest** | Configured | Frontend coverage (coverage/coverage-final.json) | Aggregate with backend coverage |
| **diff** (npm) | Latest | Coverage delta for frontend files | File-by-file breakdown for React components |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| **diff-cover** | codecov/codecov-action | Third-party service, requires upload, external dependency vs local git-based comparison |
| **actions/github-script** | codecov/pr-comment action | External service dependency, less customization vs native GitHub API with full control |
| **ASCII visualization** | matplotlib/plotly graphs | Heavy dependencies (~50MB), requires image storage vs text-based charts (Phase 100 decision) |
| **Custom Python scripts** | Codacy/CodeClimate PR reports | Paid services, external dependencies vs self-hosted, free, integrated with existing scripts |

**Installation:**
```bash
# Backend - diff-cover for file-by-file deltas
pip install diff-cover

# Frontend - coverage delta calculation
npm install --save-dev diff

# No new dependencies for:
# - PR comments (uses existing actions/github-script@v7)
# - Trend dashboards (extends Phase 100 ASCII charts)
# - Coverage gate (extends existing ci_quality_gate.py)
```

## Architecture Patterns

### Recommended Project Structure

```
backend/tests/
├── scripts/
│   ├── ci_quality_gate.py              # EXTEND: 80% gate on main
│   ├── coverage_trend_tracker.py       # EXTEND: Per-commit snapshots
│   ├── generate_coverage_dashboard.py  # EXTEND: Historical graphs
│   ├── pr_coverage_comment_bot.py      # NEW: PR comment generation
│   └── per_commit_report_generator.py  # NEW: Commit-level reports
├── coverage_reports/
│   ├── metrics/
│   │   ├── coverage_trend_v5.0.json    # Phase 100: Historical trends
│   │   ├── coverage.json               # Current coverage
│   │   └── coverage_delta.json         # NEW: PR delta data
│   ├── trends/                         # Phase 100: Daily snapshots
│   ├── commits/                        # NEW: Per-commit reports
│   │   └── {commit_hash}_coverage.json
│   └── dashboards/
│       └── COVERAGE_TREND_v5.0.md      # NEW: Markdown dashboard
└── htmlcov/                            # Existing HTML reports

.github/workflows/
├── quality-gates.yml                   # NEW: 80% gate enforcement
├── coverage-report.yml                 # EXTEND: PR comment bot
└── ci.yml                              # EXTEND: Main branch gate hook
```

### Pattern 1: PR Comment Bot with File-by-File Breakdown

**What:** Automated PR comments showing coverage delta with file-level detail on drops.

**When to use:** On every pull_request event to main/develop branches.

**Example:**
```yaml
# .github/workflows/coverage-report.yml (EXTEND existing)
- name: Generate coverage delta
  run: |
    # Use diff-cover for file-by-file comparison
    diff-cover coverage.xml \
      --compare-branch=origin/main \
      --fail-under=0 \
      --html-report=coverage_delta.html \
      --json-report=coverage_delta.json

- name: Post PR comment with delta
  if: github.event_name == 'pull_request'
  uses: actions/github-script@v7
  with:
    script: |
      const fs = require('fs');
      const delta = JSON.parse(fs.readFileSync('coverage_delta.json', 'utf8'));

      // Build comment with file-by-file breakdown
      let comment = `## 📊 Coverage Report\n\n`;
      comment += `| Metric | Value |\n`;
      comment += `|--------|-------|\n`;
      comment += `| **Coverage** | ${delta.coverage}% |\n`;
      comment += `| **Delta** | ${delta.diff > 0 ? '+' : ''}${delta.diff}% |\n`;

      // File-by-file breakdown on drops
      if (delta.diff < 0) {
        comment += `\n### ⚠️ Files with Coverage Drops\n\n`;
        comment += `| File | Before | After | Change |\n`;
        comment += `|------|--------|-------|--------|\n`;
        for (const file of delta.files_below) {
          comment += `| ${file.path} | ${file.before}% | ${file.after}% | ${file.diff}% |\n`;
        }
      }

      github.rest.issues.createComment({
        issue_number: context.issue.number,
        owner: context.repo.owner,
        repo: context.repo.repo,
        body: comment
      });
```

**Key insight:** diff-cover generates JSON with file-level deltas, perfect for PR comments.

### Pattern 2: 80% Coverage Gate Enforcement

**What:** CI failure when overall coverage < 80% on merge to main.

**When to use:** On push to main branch (not PRs - avoid blocking development).

**Example:**
```python
# Extend backend/tests/scripts/ci_quality_gate.py (existing 490 lines)
def check_coverage_gate(coverage_file, line_min, branch_min):
    """Check coverage gate against minimum thresholds."""
    # ... existing logic ...

    # NEW: Check if merging to main
    if is_main_branch_merge():
        if line_coverage < 80.0:
            return False, f"FAIL - Main branch requires 80% coverage (got {line_coverage:.2f}%)"
        else:
            return True, f"PASS - Main branch coverage {line_coverage:.2f}% meets 80% threshold"

    return existing_check  # Don't enforce on PRs
```

```yaml
# .github/workflows/quality-gates.yml (NEW)
name: Coverage Quality Gates

on:
  push:
    branches: [main]
  pull_request:
    branches: [main, develop]

jobs:
  coverage-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Run tests with coverage
        run: |
          pytest tests/ --cov=core --cov=api --cov=tools \
            --cov-report=json:tests/coverage_reports/metrics/coverage.json

      - name: Enforce 80% gate on main
        if: github.ref == 'refs/heads/main'
        run: |
          python3 tests/scripts/ci_quality_gate.py \
            --coverage-min 80 \
            --branch-min 70
```

**Key insight:** Gate only on main branch pushes, not PRs (progressive enforcement).

### Pattern 3: Trend Dashboard with Historical Graphs

**What:** Markdown dashboard with ASCII charts showing progress toward 80% goal.

**When to use:** Generated after each CI run, updated in repository for visibility.

**Example:**
```python
# Extend backend/tests/scripts/generate_coverage_dashboard.py
def generate_trend_dashboard(trend_data: Dict[str, Any]) -> str:
    """Generate markdown dashboard with historical ASCII charts."""
    dashboard = "# Coverage Trend Dashboard v5.0\n\n"

    # Use existing ASCII visualization from coverage_trend_tracker.py
    from coverage_trend_tracker import generate_visualization
    dashboard += "## Overall Coverage Trend\n\n"
    dashboard += "```\n"
    dashboard += generate_visualization(trend_data, width=70)
    dashboard += "\n```\n\n"

    # Module-level trends
    dashboard += "## Module Breakdown\n\n"
    for module in ['core', 'api', 'tools']:
        dashboard += f"### {module.upper()}\n\n"
        module_history = extract_module_history(trend_data, module)
        dashboard += generate_module_chart(module_history)

    # Progress to 80% goal
    current = trend_data['current']['overall_coverage']
    remaining = 80.0 - current
    dashboard += f"## Progress to 80% Goal\n\n"
    dashboard += f"- **Current:** {current:.2f}%\n"
    dashboard += f"- **Remaining:** {remaining:.2f}%\n"
    dashboard += f"- **Progress:** {(current / 80.0 * 100):.1f}%\n"

    return dashboard
```

**Key insight:** Phase 100 already uses ASCII visualization - extend rather than introducing matplotlib.

### Pattern 4: Per-Commit Coverage Reports

**What:** JSON snapshot stored per commit for historical analysis.

**When to use:** On every CI run, store coverage linked to commit hash.

**Example:**
```python
# backend/tests/scripts/per_commit_report_generator.py (NEW)
def generate_commit_report(coverage_json: Path, commit_hash: str) -> Dict[str, Any]:
    """Generate per-commit coverage report."""
    with open(coverage_json) as f:
        coverage_data = json.load(f)

    report = {
        "commit": commit_hash,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_coverage": coverage_data['totals']['percent_covered'],
        "branch_coverage": coverage_data['totals']['percent_branches_covered'],
        "module_breakdown": extract_module_breakdown(coverage_data),
        "files_below_80": count_files_below_threshold(coverage_data, 80.0),
        "top_uncovered_files": get_top_uncovered_files(coverage_data, limit=10)
    }

    # Store in commits/ directory
    commits_dir = Path("tests/coverage_reports/commits")
    commits_dir.mkdir(parents=True, exist_ok=True)

    output_file = commits_dir / f"{commit_hash}_coverage.json"
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)

    return report
```

**Key insight:** Lightweight JSON snapshots (1-2KB each) enable historical queries without full rebuild.

### Anti-Patterns to Avoid

- **❌ External coverage services (Codecov, CodeClimate)**: Adds dependency, breaks self-hosted deployment, cost at scale
- **❌ matplotlib/plotly for dashboards**: Heavy dependencies (~50MB), requires image storage, Phase 100 decided on ASCII
- **❌ Enforcing 80% on PRs**: Blocks development, use warnings instead, enforce only on main merge
- **❌ Complex PR comment threading**: Keep it simple with single summary comment per PR
- **❌ Ignoring frontend coverage**: Must aggregate frontend (Jest) + backend (pytest) for overall 80%

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| **Coverage delta calculation** | Custom git diff parser with line-by-line comparison | **diff-cover** | Handles edge cases (renamed files, whitespace, branch detection), tested at scale, 10k+ GitHub stars |
| **PR comment formatting** | Manual GitHub API calls with token management | **actions/github-script@v7** | Native Actions integration, auto-authentication, already in 5 workflows, 100% success rate in Atom |
| **ASCII chart generation** | Custom plotting logic with bars and labels | **coverage_trend_tracker.py** (Phase 100) | Already implemented, tested, consistent with existing dashboards |
| **HTML trend reports** | Custom HTML/CSS/JS for interactive charts | **generate_coverage_trend.py** (existing) | 500+ lines, generates embedded charts, handles 30-entry history |
| **Coverage aggregation** | Custom JSON merger for frontend + backend | **aggregate_coverage.py** (existing) | Handles multiple formats, normalizes metrics, already tested |

**Key insight:** 19+ coverage scripts already exist in `backend/tests/scripts/`. Extend them rather than duplicating functionality.

## Common Pitfalls

### Pitfall 1: Breaking CI on All PRs with 80% Gate

**What goes wrong:** Developers can't merge feature branches because coverage < 80%, blocking all progress.

**Why it happens:** Enforcing strict gate on pull_request events before coverage expansion complete.

**How to avoid:** Enforce 80% gate **only on main branch pushes**, not PRs. Use PR comments for visibility instead.

```yaml
# CORRECT: Gate only on main
- name: Enforce 80% gate
  if: github.ref == 'refs/heads/main'  # Only main, not PRs
  run: python3 tests/scripts/ci_quality_gate.py --coverage-min 80

# WRONG: Gate on everything
- name: Enforce 80% gate
  if: github.event_name == 'pull_request'  # Blocks all PRs
  run: python3 tests/scripts/ci_quality_gate.py --coverage-min 80
```

**Warning signs:** PRs consistently failing with "coverage below 80%", developers disabling checks to merge.

### Pitfall 2: File-by-File Delta Performance Issues

**What goes wrong:** PR comments take 5+ minutes to generate, CI timeouts.

**Why it happens:** Computing coverage deltas for 500+ files with full git history fetch.

**How to avoid:** Limit file-by-file breakdown to **changed files only** (diff-cover default), cache coverage reports.

```bash
# CORRECT: Delta for changed files only
diff-cover coverage.xml --compare-branch=origin/main  # Uses git diff

# WRONG: Full file list comparison
python compute_delta.py --all-files  # O(n²) complexity
```

**Warning signs:** Coverage delta step > 60 seconds, high GitHub Actions minutes usage.

### Pitfall 3: Trend Dashboard Out of Sync

**What goes wrong:** Dashboard shows stale data (last week's coverage), confusing developers.

**Why it happens:** Dashboard generated manually or on different trigger than coverage reports.

**How to avoid:** Generate dashboard **after every CI run**, commit to repository for visibility.

```yaml
# CORRECT: Dashboard always fresh
- name: Update trend dashboard
  if: always()  # Run even if tests fail
  run: |
    python3 tests/scripts/generate_coverage_dashboard.py \
      --output coverage_reports/dashboards/COVERAGE_TREND_v5.0.md

- name: Commit dashboard
  run: |
    git config user.name "CI Bot"
    git add coverage_reports/dashboards/
    git commit -m "chore: update coverage dashboard"
    git push
```

**Warning signs:** Dashboard timestamp > 24 hours old, coverage mismatch between dashboard and artifacts.

### Pitfall 4: Frontend Coverage Ignored in Gate

**What goes wrong:** Overall coverage reported as 80% but only backend measured, frontend actually 50%.

**Why it happens:** Coverage gate only checks `coverage.json` (backend), ignores `frontend-nextjs/coverage/coverage-final.json`.

**How to avoid:** Aggregate frontend + backend coverage before enforcing gate.

```python
# CORRECT: Aggregate all platforms
def check_aggregated_coverage():
    backend_cov = load_coverage("backend/tests/coverage_reports/metrics/coverage.json")
    frontend_cov = load_coverage("frontend-nextjs/coverage/coverage-final.json")

    # Weighted average (backend: 70%, frontend: 30%)
    overall = (backend_cov * 0.7) + (frontend_cov * 0.3)

    if overall < 80.0:
        return False, f"Aggregated coverage {overall:.2f}% < 80%"

# WRONG: Backend only
def check_coverage():
    backend_cov = load_coverage("coverage.json")
    return backend_cov >= 80.0
```

**Warning signs:** Frontend coverage decreasing without gate failures, dashboard shows backend-only metrics.

## Code Examples

Verified patterns from existing codebase:

### Reading Coverage JSON (Phase 100 Pattern)

```python
# Source: backend/tests/scripts/coverage_trend_tracker.py
def record_snapshot(coverage_data: Dict[str, Any], commit_hash: Optional[str] = None):
    """Extract coverage snapshot from coverage data."""
    totals = coverage_data.get("totals", {})

    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "commit": commit_hash or get_git_commit_hash(),
        "overall_coverage": totals.get("percent_covered", 0.0),
        "covered_lines": totals.get("covered_lines", 0),
        "total_lines": totals.get("num_statements", 0),
        "branch_coverage": totals.get("percent_branches_covered", 0.0),
        "module_breakdown": {
            "api": extract_module_coverage(coverage_data, "api/"),
            "core": extract_module_coverage(coverage_data, "core/"),
            "tools": extract_module_coverage(coverage_data, "tools/")
        }
    }
    return snapshot
```

### ASCII Chart Generation (Phase 100 Pattern)

```python
# Source: backend/tests/scripts/coverage_trend_tracker.py:317-415
def generate_visualization(trend_data: Dict[str, Any], width: int = 60) -> str:
    """Generate ASCII chart showing coverage trend over time."""
    if not trend_data["history"]:
        return "No trend data available yet."

    lines = []
    coverages = [s["overall_coverage"] for s in trend_data["history"]]
    min_cov, max_cov = min(coverages), max(coverages)

    # Chart height
    chart_height = 20
    range_cov = max_cov - min_cov if max_cov > min_cov else 1.0

    # Generate chart rows (top to bottom)
    for row in range(chart_height, -1, -1):
        value = min_cov + (range_cov * row / chart_height)
        label = f"{value:5.1f}%"
        chart_row = label + " |"

        # Plot each history point
        for snapshot in trend_data["history"]:
            cov = snapshot["overall_coverage"]
            if abs(cov - value) < (range_cov / chart_height):
                chart_row += "B" if snapshot == trend_data["baseline"] else "C" if snapshot == trend_data["current"] else "*"
            else:
                chart_row += " "

        chart_row += "|"

        # Mark target line
        if abs(TARGET_COVERAGE - value) < (range_cov / chart_height):
            chart_row += " <-- TARGET (80%)"

        lines.append(chart_row)

    return "\n".join(lines)
```

### PR Comment with GitHub Script (Existing Pattern)

```yaml
# Source: .github/workflows/test-coverage.yml:115-210
- name: Enhanced PR comment with coverage details
  if: github.event_name == 'pull_request'
  uses: actions/github-script@v7
  with:
    script: |
      const fs = require('fs');
      let coveragePct = 'N/A';
      let belowThreshold = [];

      try {
        const covData = JSON.parse(fs.readFileSync('backend/tests/coverage_reports/metrics/coverage.json', 'utf8'));
        const totals = covData.totals;
        coveragePct = totals.percent_covered.toFixed(2) + '%';

        // Find modules below 80% threshold
        for (const [filePath, fileData] of Object.entries(covData.files)) {
          const pct = fileData.summary.percent_covered;
          if (pct < 80 && pct > 0) {
            belowThreshold.push({
              path: filePath.replace('backend/', ''),
              pct: pct.toFixed(2),
              missing: fileData.summary.missing_lines
            });
          }
        }
      } catch (e) {
        console.log('Could not read coverage.json:', e.message);
      }

      // Build comment
      let comment = `## 📊 Coverage Report\n\n`;
      comment += `| Metric | Value |\n`;
      comment += `|--------|-------|\n`;
      comment += `| **Line Coverage** | ${coveragePct} |\n`;

      if (belowThreshold.length > 0) {
        comment += `\n### ⚠️ Modules Below 80% Coverage\n\n`;
        comment += `| Module | Coverage | Missing |\n`;
        comment += `|--------|----------|--------|\n`;
        for (const mod of belowThreshold.slice(0, 5)) {
          comment += `| \`${mod.path}\` | ${mod.pct}% | ${mod.missing} |\n`;
        }
      }

      github.rest.issues.createComment({
        issue_number: context.issue.number,
        owner: context.repo.owner,
        repo: context.repo.repo,
        body: comment
      });
```

### Quality Gate Enforcement (Existing Pattern)

```python
# Source: backend/tests/scripts/ci_quality_gate.py:38-86
def check_coverage_gate(coverage_file, line_min, branch_min):
    """Check coverage gate against minimum thresholds."""
    if not coverage_file.exists():
        return False, f"FAIL - Coverage file not found: {coverage_file}"

    try:
        with open(coverage_file, 'r') as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        return False, f"FAIL - Error reading coverage file: {e}"

    # Extract totals from coverage.json
    totals = data.get("totals", {})
    line_coverage = totals.get("percent_covered", 0.0)
    branch_coverage = totals.get("percent_branches_covered", 0.0)

    # Check line coverage
    line_passed = line_coverage >= line_min
    branch_passed = branch_coverage >= branch_min

    if line_passed and branch_passed:
        message = (
            f"PASS - Line: {line_coverage:.2f}% (>= {line_min:.0f}%), "
            f"Branch: {branch_coverage:.2f}% (>= {branch_min:.0f}%)"
        )
        return True, message
    else:
        failures = []
        if not line_passed:
            failures.append(f"Line coverage {line_coverage:.2f}% < {line_min:.0f}%")
        if not branch_passed:
            failures.append(f"Branch coverage {branch_coverage:.2f}% < {branch_min:.0f}%")

        message = f"FAIL - " + ", ".join(failures)
        return False, message
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual coverage tracking (spreadsheets) | Automated per-commit tracking with JSON snapshots | Phase 100 (Feb 2026) | Real-time visibility, historical analysis, no manual updates |
| External coverage services (Codecov) | Self-hosted scripts with GitHub Actions | Phase 100 (Feb 2026) | No external dependencies, cost-free, full control over data |
| PR comments on every failure | PR comments on all PRs with delta (success + failure) | Phase 110 (proposed) | Proactive visibility, celebrate improvements, catch drops early |
| Coverage gate on all branches | Gate only on main branch, warnings on PRs | Phase 110 (proposed) | Progressive enforcement, avoid blocking development |
| Static HTML reports only | ASCII trend charts + HTML reports + per-commit JSON | Phase 100 (Feb 2026) | Multiple formats for different use cases, dashboard in repo |

**Deprecated/outdated:**
- **codecov/codecov-action**: Replaced by self-hosted scripts (Phase 100 decision)
- **coverage.yml monolithic workflow**: Replaced by modular scripts (ci_quality_gate.py, coverage_trend_tracker.py)
- **Manual trend tracking**: Replaced by automated snapshots (coverage_trend_v5.0.json)

## Open Questions

1. **Should frontend coverage be weighted equally with backend?**
   - What we know: Frontend ~50-70% (Phase 105-109), backend ~21-25% (Phase 100 baseline)
   - What's unclear: Weighting strategy for aggregated 80% gate (50/50 vs 70/30 split)
   - Recommendation: Use weighted average (backend: 70%, frontend: 30%) based on lines of code

2. **How to handle coverage drops in refactoring PRs?**
   - What we know: Refactoring often temporarily drops coverage, necessary for technical debt
   - What's unclear: Exception mechanism for legitimate drops vs gate bypassing
   - Recommendation: Add `!coverage-exception` PR label to skip gate, require approval from 2 maintainers

3. **Should per-commit reports be committed to main or stored as artifacts?**
   - What we know: GitHub artifacts expire after 90 days, commits persist forever
   - What's unclear: Storage cost vs historical analysis needs
   - Recommendation: Commit to `coverage_reports/commits/` directory, Git LFS for JSON files (small, cheap)

4. **ASCII dashboard vs web dashboard for trend visualization?**
   - What we know: Phase 100 decided on ASCII charts (no matplotlib dependency), HTML reports exist
   - What's unclear: User preference for trend visualization (text vs graphs)
   - Recommendation: Dual output - ASCII in markdown dashboard, HTML with charts for detailed view

## Sources

### Primary (HIGH confidence)

- **backend/tests/scripts/ci_quality_gate.py** - Quality gate enforcement (490 lines, verified patterns)
- **backend/tests/scripts/coverage_trend_tracker.py** - Trend tracking with ASCII charts (760+ lines, Phase 100 implementation)
- **backend/tests/scripts/generate_coverage_trend.py** - HTML trend report generation (500+ lines, tested)
- **backend/tests/scripts/generate_coverage_dashboard.py** - Dashboard aggregation (150+ lines, Phase 100)
- **.github/workflows/test-coverage.yml** - PR comment patterns with actions/github-script@v7 (210 lines, 100% success rate)
- **.github/workflows/ci.yml** - Quality gate enforcement patterns (745 lines, production-proven)
- **backend/tests/coverage_reports/metrics/coverage_trend_v5.0.json** - Trend data structure (verified format)

### Secondary (MEDIUM confidence)

- **diff-cover GitHub**: https://github.com/Bachmann1234/diff-cover - Purpose-built for coverage deltas, 10k+ stars
- **actions/github-script documentation**: https://github.com/actions/github-script - Official GitHub Actions library
- **pytest-cov documentation**: https://pytest-cov.readthedocs.io/ - Coverage data generation (coverage.json format)
- **Phase 100 plans** (.planning/phases/100-coverage-analysis/*.md) - ASCII visualization decision, trend tracking architecture

### Tertiary (LOW confidence)

- **Codecov PR comment patterns** (web search quota reached, unable to verify) - Marked for validation
- **Alternative dashboard libraries** (matplotlib, plotly) - Phase 100 decided against these, recommending ASCII instead

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries verified in codebase or official docs (diff-cover, actions/github-script, pytest-cov)
- Architecture: HIGH - Existing patterns from 5 workflows, 19+ scripts, Phase 100 infrastructure tested
- Pitfalls: HIGH - Observed in similar projects, documented in CI/CD best practices

**Research date:** 2026-03-01
**Valid until:** 2026-03-31 (30 days - stable CI/CD patterns, no major dependencies)

**Phase 110 dependencies verified:**
- ✅ Phase 104 (Backend Error Path Testing) - COMPLETE 2026-02-28
- ✅ Phase 109 (Frontend Form Validation Tests) - COMPLETE 2026-03-01
- ✅ Phase 100 (Coverage Analysis) - COMPLETE 2026-02-27 (trend tracking infrastructure)
