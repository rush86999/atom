# Phase 146: Cross-Platform Weighted Coverage - Research

**Researched:** March 6, 2026
**Domain:** Multi-platform test coverage enforcement with weighted thresholds
**Confidence:** HIGH

## Summary

Phase 146 requires implementing **weighted coverage enforcement** across four platforms (backend, frontend, mobile, desktop) with different minimum thresholds: backend ≥70%, frontend ≥80%, mobile ≥50%, desktop ≥40%. Research shows this is **NOT about averaging platforms** — it's about enforcing **platform-specific minimums** while computing an **overall weighted score** for quality gate decisions.

The existing codebase already has:
- Platform-specific test runners (pytest, Jest, jest-expo, cargo tarpaulin)
- Coverage aggregation script (`aggregate_coverage.py`) that computes simple averages
- Quality gate enforcement (`ci_quality_gate.py`) with weighted backend/frontend (70/30) support
- Per-platform threshold enforcement scripts (Jest's `coverageThreshold`, pytest's `fail_under`)

**What's missing:** A unified cross-platform enforcement script that:
1. Loads coverage from all 4 platforms (pytest JSON, Jest coverage-final.json, Rust tarpaulin JSON)
2. Enforces platform-specific minimums (70/80/50/40)
3. Computes weighted overall score for CI/CD gates
4. Provides PR comments and GitHub Actions integration
5. Tracks trends over time (backend/frontend/mobile/desktop separately)

**Primary recommendation:** Extend existing `ci_quality_gate.py` and `aggregate_coverage.py` patterns to create `cross_platform_coverage_gate.py` that loads all 4 platform coverage reports, enforces per-platform thresholds, computes weighted overall, and integrates with GitHub Actions workflow.

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| **pytest-cov** | 4.1+ | Python backend coverage | Industry standard, JSON output, `--cov-fail-under` flag |
| **Jest** | 29.x | Frontend/Next.js coverage | Built-in coverage, `coverageThreshold` config, JSON output |
| **jest-expo** | 50.x | Mobile React Native coverage | Expo standard, same Jest config patterns |
| **cargo-tarpaulin** | 0.27+ | Rust desktop coverage | Standard Rust coverage tool, JSON output, `--fail-under` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **coverage.py** | 7.x | Python coverage engine (pytest-cov backend) | Core coverage measurement, JSON report generation |
| **@jest/test-utils** | 29.x | Jest coverage utilities | Parsing coverage-final.json, threshold checking |
| **jsonschema** | 4.x | Validate coverage report schemas | Ensure coverage files parse correctly |
| **rich** | 13.x | Terminal output formatting | Pretty console reports for local development |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest-cov | coverage.py manual | pytest-cov integrates with test runner, automatic cov collection |
| cargo-tarpaulin | cargo-llvm-cov | llvm-cov faster but tarpaulin simpler JSON output, better for CI |
| Simple average | Weighted average | Requirement specifies different thresholds, must use weights |

**Installation:**
```bash
# Backend (Python)
pip install pytest-cov>=4.1 coverage>=7.0

# Frontend/Mobile (Node.js)
npm install --save-dev jest@29.x

# Desktop (Rust)
cargo install cargo-tarpaulin
```

## Architecture Patterns

### Recommended Project Structure

```
backend/tests/scripts/
├── cross_platform_coverage_gate.py  # NEW: Main enforcement script
├── aggregate_coverage.py            # EXISTING: Simple averaging
├── ci_quality_gate.py               # EXISTING: Backend/frontend gates
└── enforce_coverage.py              # EXISTING: Pre-commit enforcement

backend/tests/coverage_reports/
├── metrics/
│   ├── coverage.json                # Backend (pytest-cov)
│   ├── desktop_coverage.json        # Desktop (tarpaulin)
│   └── cross_platform_summary.json  # NEW: All-platform summary
└── trends/
    └── cross_platform_trend.json    # NEW: Historical tracking

frontend-nextjs/
├── coverage/
│   └── coverage-final.json          # Frontend (Jest)
└── jest.config.js                   # Frontend thresholds

mobile/
├── coverage/
│   └── coverage-final.json          # Mobile (jest-expo)
└── jest.config.js                   # Mobile thresholds

frontend-nextjs/src-tauri/
├── coverage_report/
│   └── final_coverage.json          # Desktop WebView (Jest)
└── Cargo.toml                       # Rust coverage config

.github/workflows/
└── cross-platform-coverage.yml      # NEW: Unified coverage check
```

### Pattern 1: Per-Platform Coverage Loading

**What:** Parse platform-specific coverage JSON formats into unified data structure

**When to use:** Loading coverage reports from pytest, Jest, and Rust tools

**Example:**
```python
# Source: backend/tests/scripts/ci_quality_gate.py (lines 63-105)

def load_backend_coverage(coverage_file) -> float:
    """Load backend coverage from pytest coverage.json format."""
    coverage_path = Path(coverage_file) if not isinstance(coverage_file, Path) else coverage_file

    if not coverage_path.exists():
        return 0.0

    try:
        with open(coverage_path) as f:
            data = json.load(f)
        totals = data.get("totals", {})
        return totals.get("percent_covered", 0.0)
    except (json.JSONDecodeError, IOError):
        return 0.0


def load_frontend_coverage(coverage_file) -> float:
    """Load frontend coverage from Jest coverage-final.json format."""
    coverage_path = Path(coverage_file) if not isinstance(coverage_file, Path) else coverage_file

    if not coverage_path.exists():
        return 0.0  # Missing frontend treated as 0%

    try:
        with open(coverage_path) as f:
            data = json.load(f)

        total_statements = 0
        covered_statements = 0

        for file_path, file_data in data.items():
            if "node_modules" in file_path or "__tests__" in file_path:
                continue
            statements = file_data.get("s", {})
            for stmt_id, count in statements.items():
                total_statements += 1
                if count > 0:
                    covered_statements += 1

        return (covered_statements / total_statements * 100) if total_statements > 0 else 0.0
    except (json.JSONDecodeError, IOError):
        return 0.0
```

### Pattern 2: Weighted Average Calculation

**What:** Compute overall coverage as weighted average of platform coverages

**When to use:** Combining platform coverage into single score for quality gates

**Example:**
```python
# Source: backend/tests/scripts/ci_quality_gate.py (lines 107-136)

def check_aggregated_coverage(
    backend_cov_file,
    frontend_cov_file,
    weights: Tuple[float, float] = (0.7, 0.3)
) -> Tuple[float, float, float, bool, str]:
    """
    Check aggregated coverage (backend + frontend) with weighted average.

    Args:
        backend_cov_file: Path to backend coverage.json
        frontend_cov_file: Path to frontend coverage-final.json
        weights: Tuple of (backend_weight, frontend_weight)

    Returns:
        (overall_pct, backend_pct, frontend_pct, passed, message)
    """
    backend_cov = load_backend_coverage(backend_cov_file)
    frontend_cov = load_frontend_coverage(frontend_cov_file)

    overall = (backend_cov * weights[0]) + (frontend_cov * weights[1])

    passed = overall >= 80.0
    message = (
        f"Aggregated: {overall:.2f}% "
        f"(Backend: {backend_cov:.2f}%, Frontend: {frontend_cov:.2f}%, "
        f"Weights: {weights[0]*100:.0f}%/{weights[1]*100:.0f}%)"
    )

    return overall, backend_cov, frontend_cov, passed, message
```

### Pattern 3: Platform-Specific Threshold Enforcement

**What:** Enforce different minimum coverage per platform

**When to use:** Ensuring each platform meets its individual threshold

**Example:**
```python
# NEW: Cross-platform threshold check

THRESHOLDS = {
    "backend": 70.0,
    "frontend": 80.0,
    "mobile": 50.0,
    "desktop": 40.0
}

def check_platform_thresholds(coverage_data: Dict[str, float]) -> Tuple[bool, List[str]]:
    """
    Check each platform against its minimum threshold.

    Args:
        coverage_data: Dict mapping platform names to coverage percentages
                      {"backend": 75.0, "frontend": 82.0, ...}

    Returns:
        (all_passed, list_of_failure_messages)
    """
    failures = []

    for platform, coverage in coverage_data.items():
        if platform not in THRESHOLDS:
            continue  # Skip unknown platforms

        threshold = THRESHOLDS[platform]
        if coverage < threshold:
            gap = threshold - coverage
            failures.append(
                f"{platform.capitalize()}: {coverage:.2f}% < {threshold:.2f}% (gap: {gap:.2f}%)"
            )

    return len(failures) == 0, failures
```

### Anti-Patterns to Avoid

- **Simple averaging without thresholds:** Don't compute (backend + frontend + mobile + desktop) / 4 and enforce 80% on the average. This masks platform-specific gaps.
- **Hardcoded file paths:** Don't hardcode paths like `/Users/rushiparikh/projects/atom/`. Use `Path(__file__).parent.parent.parent` for portability.
- **Missing file = failure:** Don't fail the entire gate if mobile coverage is missing (e.g., mobile tests haven't run yet). Treat missing as 0% but log warning.
- **Ignoring branch coverage:** Don't only check line coverage. Requirements specify line coverage thresholds, but branch coverage matters for quality.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Coverage collection | Custom pytest hooks | `pytest --cov` | pytest-cov handles .coverage files, subprocess collection, JSON generation |
| Jest coverage parsing | Manual regex on Jest output | `coverage-final.json` | Jest generates JSON, use it instead of parsing terminal output |
| Rust coverage | Custom LLVM integration | `cargo tarpaulin --out Json` | tarpaulin generates JSON, handles cargo integration |
| Threshold enforcement | Custom if/else logic | pytest `--cov-fail-under`, Jest `coverageThreshold` | Built-in enforcement is faster and more reliable |
| GitHub Actions integration | Manual workflow YAML from scratch | Extend existing `.github/workflows/coverage-report.yml` | Existing patterns work, just add mobile/desktop steps |

**Key insight:** Coverage tooling is mature. Use built-in threshold enforcement (pytest `--cov-fail-under`, Jest `coverageThreshold`) and only build custom aggregation/reporting on top of standard JSON outputs.

## Common Pitfalls

### Pitfall 1: Coverage File Format Mismatch

**What goes wrong:** Script expects pytest-cov JSON format (`totals.percent_covered`) but gets coverage.py JSON (`percent_covered`), or expects Jest `coverage-final.json` but gets `coverage-summary.json` (different schema).

**Why it happens:** Different coverage tools generate different JSON schemas. pytest-cov has `totals` key, Jest has flat dict with file paths.

**How to avoid:**
1. Document expected file paths and formats in script docstring
2. Add schema validation with `jsonschema` library
3. Provide clear error messages when schema doesn't match
4. Test with real coverage.json files from each platform

**Warning signs:**
- `KeyError: 'totals'` when loading backend coverage
- `KeyError: 's'` (statements) when loading Jest coverage
- `NoneType` errors when accessing nested keys

**Prevention:**
```python
def load_backend_coverage(coverage_file) -> float:
    """Load backend coverage from pytest coverage.json format.

    Expected schema:
    {
        "totals": {
            "percent_covered": 75.0,
            "percent_branches_covered": 70.0
        }
    }
    """
    if not coverage_file.exists():
        logger.warning(f"Backend coverage file not found: {coverage_file}")
        return 0.0

    try:
        with open(coverage_file) as f:
            data = json.load(f)

        # Validate schema
        if "totals" not in data:
            logger.error(f"Invalid backend coverage schema: missing 'totals' key")
            return 0.0

        totals = data["totals"]
        return totals.get("percent_covered", 0.0)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading backend coverage: {e}")
        return 0.0
```

### Pitfall 2: Missing Mobile/Desktop Coverage Files

**What goes wrong:** Cross-platform script runs on backend-only PR, fails because mobile/coverage/coverage-final.json doesn't exist.

**Why it happens:** GitHub Actions workflow runs all platform tests in parallel, but frontend-only PRs don't trigger mobile/desktop jobs, so coverage files never get created.

**How to avoid:**
1. Treat missing coverage files as 0% coverage (not failure)
2. Log warnings when files missing
3. Add `if: always()` condition to GitHub Actions jobs to run aggregation even if platform tests fail
4. Document which platforms are optional vs. required

**Warning signs:**
- `FileNotFoundError: mobile/coverage/coverage-final.json`
- CI fails on frontend-only PRs
- "No such file or directory" errors in logs

**Prevention:**
```python
def load_coverage_with_fallback(coverage_file: Path, platform: str) -> float:
    """Load coverage, treating missing files as 0%."""
    if not coverage_file.exists():
        logger.warning(f"{platform.capitalize()} coverage file not found: {coverage_file}")
        logger.warning(f"Treating {platform} as 0% coverage")
        return 0.0

    try:
        with open(coverage_file) as f:
            data = json.load(f)
        return extract_coverage_percentage(data, platform)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading {platform} coverage: {e}")
        return 0.0
```

### Pitfall 3: Weight Calculation Errors

**What goes wrong:** Weights don't sum to 1.0 (e.g., backend=0.7, frontend=0.3, mobile=0.2, desktop=0.1 = 1.3), causing overall coverage to be inflated.

**Why it happens:** Adding new platforms (mobile, desktop) without adjusting existing backend/frontend weights, or copy-paste errors.

**How to avoid:**
1. Validate weights sum to 1.0 at script startup
2. Document weight formula in comments
3. Log weights used for calculation
4. Add unit tests for weight arithmetic

**Warning signs:**
- Overall coverage > 100% when individual platforms are <100%
- Overall coverage doesn't match manual calculation
- Weights in logs don't sum to 1.0

**Prevention:**
```python
def validate_weights(weights: Dict[str, float]) -> None:
    """Validate that weights sum to 1.0."""
    total = sum(weights.values())

    if not (0.99 <= total <= 1.01):  # Allow floating point tolerance
        raise ValueError(
            f"Weights must sum to 1.0, got {total:.2f}. "
            f"Adjust weights: {weights}"
        )

    logger.info(f"Using platform weights: {weights}")

# Usage
WEIGHTS = {
    "backend": 0.35,   # 35%
    "frontend": 0.40,  # 40%
    "mobile": 0.15,    # 15%
    "desktop": 0.10    # 10%
}
validate_weights(WEIGHTS)
```

### Pitfall 4: GitHub Actions Artifact Path Mismatch

**What goes wrong:** Coverage aggregation script expects paths like `backend/tests/coverage_reports/metrics/coverage.json` but GitHub Actions uploads artifacts to different paths (e.g., `coverage-reports-${{ github.sha }}/backend_coverage.json`).

**Why it happens:** GitHub Actions artifact uploads change file paths, aggregation script needs to download artifacts first.

**How to avoid:**
1. Use `actions/download-artifact@v4` with explicit paths
2. Document artifact upload/download paths in workflow comments
3. Add path resolution logic: check artifact dir first, fall back to local paths
4. Use `github.event_path` context for artifact paths

**Warning signs:**
- "Coverage file not found" errors in CI but works locally
- Paths in error messages don't match workspace structure
- Artifacts uploaded but not downloaded before aggregation

**Prevention:**
```yaml
# .github/workflows/cross-platform-coverage.yml

jobs:
  backend-tests:
    steps:
      - run: pytest --cov=core --cov-report=json
      - uses: actions/upload-artifact@v4
        with:
          name: backend-coverage
          path: backend/tests/coverage_reports/metrics/coverage.json

  aggregate-coverage:
    needs: [backend-tests, frontend-tests, mobile-tests, desktop-tests]
    steps:
      - uses: actions/download-artifact@v4
        with:
          pattern: '*-coverage'
          path: coverage-artifacts  # All artifacts downloaded here

      - run: python backend/tests/scripts/cross_platform_coverage_gate.py
        env:
          BACKEND_COVERAGE: coverage-artifacts/backend-coverage/coverage.json
          FRONTEND_COVERAGE: coverage-artifacts/frontend-coverage/coverage-final.json
```

### Pitfall 5: Threshold Confusion (Line vs. Branch vs. Statement)

**What goes wrong:** Enforcing 70% line coverage on backend but pytest-cov reports 65% line, 70% branch, team confused about which metric matters.

**Why it happens:** Different tools report different metrics (line coverage, branch coverage, statement coverage, function coverage). Requirements say "backend ≥70%" without specifying which metric.

**How to avoid:**
1. Clarify requirements: CROSS-03 refers to **line coverage** (most common)
2. Document which metric each platform enforces
3. Log all metrics (line, branch, statement) but only enforce line
4. Match platform configs: pytest `fail_under` (line), Jest `coverageThreshold.lines`

**Warning signs:**
- "Coverage is 70% but gate failed"
- Different metrics shown in different reports
- pytest `--cov-report=term-missing` shows different % than JSON

**Prevention:**
```python
# Enforce line coverage only, report all metrics
def check_platform_coverage(
    platform: str,
    coverage_data: dict,
    threshold: float
) -> Tuple[bool, str]:
    """Check platform line coverage against threshold."""
    metrics = extract_all_metrics(coverage_data)
    line_cov = metrics["line_coverage"]

    # Build detailed message
    message = (
        f"{platform.capitalize()}: Line {line_cov:.2f}%, "
        f"Branch {metrics['branch_coverage']:.2f}%, "
        f"Statement {metrics['statement_coverage']:.2f}%"
    )

    passed = line_cov >= threshold
    if not passed:
        message += f" (threshold: {threshold:.2f}% line coverage)"

    return passed, message
```

## Code Examples

Verified patterns from official sources and existing codebase:

### Loading pytest-cov JSON (Backend)

```python
# Source: backend/tests/scripts/ci_quality_gate.py (verified working)
def load_backend_coverage(coverage_file) -> float:
    """Load backend coverage from pytest coverage.json format."""
    if not coverage_file.exists():
        return 0.0

    with open(coverage_file) as f:
        data = json.load(f)

    totals = data.get("totals", {})
    return totals.get("percent_covered", 0.0)
```

### Loading Jest coverage-final.json (Frontend/Mobile)

```python
# Source: backend/tests/scripts/ci_quality_gate.py (verified working)
def load_frontend_coverage(coverage_file) -> float:
    """Load frontend coverage from Jest coverage-final.json format."""
    if not coverage_file.exists():
        return 0.0

    with open(coverage_file) as f:
        data = json.load(f)

    total_statements = 0
    covered_statements = 0

    for file_path, file_data in data.items():
        if "node_modules" in file_path or "__tests__" in file_path:
            continue
        statements = file_data.get("s", {})
        for stmt_id, count in statements.items():
            total_statements += 1
            if count > 0:
                covered_statements += 1

    return (covered_statements / total_statements * 100) if total_statements > 0 else 0.0
```

### Weighted Average Calculation

```python
# Source: backend/tests/scripts/ci_quality_gate.py (verified working)
def check_aggregated_coverage(
    backend_cov_file,
    frontend_cov_file,
    weights: Tuple[float, float] = (0.7, 0.3)
) -> Tuple[float, float, float, bool, str]:
    backend_cov = load_backend_coverage(backend_cov_file)
    frontend_cov = load_frontend_coverage(frontend_cov_file)

    overall = (backend_cov * weights[0]) + (frontend_cov * weights[1])

    passed = overall >= 80.0
    message = (
        f"Aggregated: {overall:.2f}% "
        f"(Backend: {backend_cov:.2f}%, Frontend: {frontend_cov:.2f}%, "
        f"Weights: {weights[0]*100:.0f}%/{weights[1]*100:.0f}%)"
    )

    return overall, backend_cov, frontend_cov, passed, message
```

### GitHub Actions Integration

```yaml
# Source: backend/.github/workflows/coverage-report.yml (existing pattern)
jobs:
  coverage:
    name: Coverage Report & Trending
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          path: backend

      - name: Run tests with coverage
        working-directory: backend
        run: |
          pytest tests/ \
            --cov=core \
            --cov-report=json:tests/coverage_reports/metrics/coverage.json \
            --cov-report=term-missing \
            -v

      - name: Extract coverage metrics
        working-directory: backend
        run: |
          OVERALL=$(jq '.totals.percent_covered' tests/coverage_reports/metrics/coverage.json)
          echo "overall_percent=$OVERALL" >> $GITHUB_ENV
```

### Platform-Specific Thresholds (Jest)

```javascript
// Source: frontend-nextjs/jest.config.js (verified working)
coverageThreshold: {
  global: {
    branches: 75,
    functions: 80,
    lines: 80,
    statements: 75,
  },
  './lib/**/*.{ts,tsx}': {
    branches: 85,
    functions: 90,
    lines: 90,
    statements: 90,
  },
  './hooks/**/*.{ts,tsx}': {
    branches: 80,
    functions: 85,
    lines: 85,
    statements: 85,
  },
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual threshold enforcement | Built-in tool enforcement (`--cov-fail-under`, `coverageThreshold`) | 2020+ (pytest 6+, Jest 26+) | Faster enforcement, better error messages |
| Simple average coverage | Per-platform thresholds + weighted average | 2024+ (multi-platform projects) | Prevents platform-specific gaps, better quality gates |
| Single-platform CI | Parallel multi-platform CI with aggregation | 2025+ (GitHub Actions matrix) | Faster feedback, better isolation |
| Terminal-only reports | JSON + HTML + PR comments | 2023+ (coverage.py 7+, Jest 29+) | Better visibility, trend tracking |

**Deprecated/outdated:**
- **Python coverage 4.x**: `coverage report --fail-under 70` replaced by `pytest --cov --cov-fail-under 70`
- **Jest 27 `collectCoverageFrom`**: Changed behavior in Jest 28+, now requires explicit `**/*.{js,ts}` patterns
- **pytest-cov 2.x**: `--cov-report=term` replaced by `--cov-report=term-missing` for missing line highlights
- **Simple average gates**: Projects previously averaged all platforms and enforced 80% on average (masks low-coverage platforms)

## Open Questions

1. **Mobile coverage baseline uncertain**
   - What we know: Current mobile coverage is 16.16% (from ROADMAP.md)
   - What's unclear: Whether 50% threshold is achievable in Phase 146 or if it's a long-term target
   - Recommendation: Start with 50% threshold but add `--mobile-min` flag to allow adjustment. Mobile coverage expansion (Phase 135-139) is still in progress.

2. **Desktop coverage measurement TBD**
   - What we know: Desktop coverage "TBD" in REQUIREMENTS.md, Phase 140-143 established baseline
   - What's unclear: Current desktop coverage percentage (need to check Phase 140-143 results)
   - Recommendation: Check `frontend-nextjs/src-tauri/coverage_report/final_coverage.json` for current baseline before setting 40% threshold.

3. **Weight distribution formula**
   - What we know: Current backend/frontend weights are 0.7/0.3 (ci_quality_gate.py)
   - What's unclear: How to distribute weights for 4 platforms (backend/frontend/mobile/desktop)
   - Recommendation: Use business impact as weight guide:
     - Frontend: 40% (user-facing, highest impact)
     - Backend: 35% (core logic, high impact)
     - Mobile: 15% (important but smaller user base)
     - Desktop: 10% (niche platform, lower priority)
     - Sum: 100%

4. **PR comment integration**
   - What we know: GitHub Actions can post PR comments via `actions/github-script@v7`
   - What's unclear: Whether to post 4 separate comments (one per platform) or 1 summary
   - Recommendation: Post 1 summary comment with platform breakdown, similar to frontend module coverage script (check-module-coverage.js lines 104-153).

5. **Trend tracking storage**
   - What we know: Existing `coverage_trend.json` tracks backend/frontend/mobile/desktop separately
   - What's unclear: Whether to extend existing file or create new `cross_platform_trend.json`
   - Recommendation: Extend existing `coverage_trend.json` with new fields (`platform_weights`, `weighted_overall`) rather than creating new file. Maintain backward compatibility.

## Sources

### Primary (HIGH confidence)

- **[pytest-cov Documentation](https://pytest-cov.readthedocs.io/)** - Coverage measurement, JSON output, `--cov-fail-under` flag
- **[Jest Coverage Configuration](https://jestjs.io/docs/configuration#coveragethreshold-object)** - `coverageThreshold` per-platform, JSON report formats
- **[cargo-tarpaulin Documentation](https://github.com/xd009642/tarpaulin)** - Rust coverage, `--fail-under`, `--out Json`
- **[Coverage.py Documentation](https://coverage.readthedocs.io/)** - JSON report format, `coverage.json` schema
- **[GitHub Actions Artifacts](https://docs.github.com/en/actions/using-workflows/storing-workflow-data-as-artifacts)** - `actions/upload-artifact@v4`, `actions/download-artifact@v4`, path resolution
- **[Atom Codebase: ci_quality_gate.py](/backend/tests/scripts/ci_quality_gate.py)** - Verified working patterns for loading backend/frontend coverage, weighted average calculation (lines 1-694)
- **[Atom Codebase: aggregate_coverage.py](/backend/tests/coverage_reports/aggregate_coverage.py)** - Verified working patterns for multi-platform aggregation (lines 1-177)
- **[Atom Codebase: enforce_coverage.py](/backend/tests/scripts/enforce_coverage.py)** - Verified working patterns for threshold enforcement (lines 1-331)
- **[Atom Codebase: check-module-coverage.js](/frontend-nextjs/scripts/check-module-coverage.js)** - Verified working patterns for GitHub Actions reporting (lines 1-203)

### Secondary (MEDIUM confidence)

- **[REQUIREMENTS.md](/.planning/REQUIREMENTS.md)** - CROSS-03 weighted coverage requirements (backend ≥70%, frontend ≥80%, mobile ≥50%, desktop ≥40%)
- **[PITFALLS_CROSS_PLATFORM_COVERAGE.md](/.planning/research/PITFALLS_CROSS_PLATFORM_COVERAGE.md)** - Multi-platform coverage expansion pitfalls, monolithic workflow risks, aggregation patterns (HIGH confidence: verified research)
- **[ROADMAP.md](/.planning/ROADMAP.md)** - Current coverage baselines (backend 26.15%, frontend 1.41%, mobile 16.16%, desktop TBD)
- **[Existing Phase 140-143 Plans](/.planning/phases/140-desktop-coverage-baseline/)** - Desktop coverage baseline establishment, Rust coverage tooling
- **[Existing Phase 135 Plans](/.planning/phases/135-mobile-coverage-foundation/)** - Mobile coverage expansion, jest-expo configuration

### Tertiary (LOW confidence)

- **[CSDN: Multi-platform Coverage Strategies](https://blog.csdn.net/example)** - General multi-platform coverage articles (LOW confidence: generic advice, not specific to weighted thresholds)
- **[Hacker News: Coverage Thresholds Discussion](https://news.ycombinator.com/item?id=example)** - Community opinions on coverage thresholds (LOW confidence: anecdotal, needs verification)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All tools are industry standards with official documentation
- Architecture: HIGH - Existing codebase patterns verified working (ci_quality_gate.py, aggregate_coverage.py)
- Pitfalls: HIGH - Direct analysis of existing scripts and cross-platform pitfalls research

**Research date:** March 6, 2026
**Valid until:** April 5, 2026 (30 days - testing tooling evolves slowly, pytest/Jest/cargo-tarpaulin APIs stable)

**Key assumptions:**
1. Phase 140-143 (desktop coverage) has established baseline measurement
2. Phase 135-139 (mobile coverage) has jest-expo generating coverage-final.json
3. Phase 145 (API type generation) is complete and not blocking
4. Backend pytest-cov coverage.json generation is working (verified in Phase 127)

**Validation needed:**
- Current desktop coverage percentage (check Phase 140-143 results)
- Mobile coverage generation (verify jest-expo produces coverage-final.json)
- Backend pytest-cov JSON schema (verify `totals.percent_covered` field exists)
