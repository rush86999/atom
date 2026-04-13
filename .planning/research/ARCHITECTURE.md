# Architecture Patterns

**Domain:** Test Coverage Expansion (pytest + Jest)
**Researched:** 2026-04-13
**Overall confidence:** HIGH

## Executive Summary

Comprehensive coverage expansion tools integrate with existing Python pytest and JavaScript Jest testing architectures through **plugin-based instrumentation** and **CI/CD pipeline integration**. The architecture follows a **measurement → reporting → enforcement** pattern with existing infrastructure already in place at Atom. Coverage tools (pytest-cov, coverage.py for Python; Jest built-in coverage, nyc/istanbul for JavaScript) provide **runtime code tracing** that generates execution data, which is then aggregated into JSON reports for trend tracking and quality gate enforcement.

**Key integration points:**
- **Python**: pytest-cov plugin → coverage.py → JSON/XML/HTML reports → trend tracker scripts
- **JavaScript**: Jest built-in coverage → coverage-summary.json → PR comment bots
- **CI/CD**: GitHub Actions quality gates enforce 70% thresholds (pragmatic v11.0 target)
- **Existing Infrastructure**: 20+ coverage scripts, trend tracking, dashboards already operational

## Recommended Architecture

### High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     Coverage Data Flow                          │
└─────────────────────────────────────────────────────────────────┘

Test Execution (pytest/Jest)
    │
    ├─→ pytest --cov=backend --cov-branch --cov-report=json
    │   └─→ coverage.py traces execution → coverage.json
    │
    ├─→ npm run test:coverage -- --coverage
    │   └─→ Jest instrumenter → coverage/coverage-summary.json
    │
    ↓
Coverage Collection
    │
    ├─→ coverage_trend_tracker.py (Python)
    │   ├─→ Parse coverage.json
    │   ├─→ Extract per-file metrics (lines, branches, functions)
    │   ├─→ Record snapshot with git SHA
    │   └─→ Update trend history (JSONL)
    │
    ├─→ coverage-trend-tracker.js (JavaScript)
    │   ├─→ Parse coverage-summary.json
    │   ├─→ Extract module-level metrics
    │   └─→ Update trend file
    │
    ↓
Coverage Reporting
    │
    ├─→ generate_coverage_dashboard.py
    │   ├─→ Aggregate historical trends
    │   ├─→ Generate HTML dashboard
    │   └─→ Identify regressions (>1% decrease)
    │
    ├─→ pr_coverage_comment_bot.py
    │   ├─→ Parse PR coverage diff
    │   ├─→ Format summary table
    │   └─→ Post comment via GitHub API
    │
    ↓
Quality Gate Enforcement
    │
    ├─→ .github/workflows/quality-gate.yml
    │   ├─→ Run tests with coverage
    │   ├─→ Check threshold (70% for v11.0)
    │   └─→ Fail CI if below target
    │
    └─→ progressive_coverage_gate.py
        ├─→ Phase-based thresholds (70% → 75% → 80%)
        ├─→ Emergency bypass mechanism
        └─→ New code gates (80% regardless of phase)
```

### Component Boundaries

| Component | Responsibility | Communicates With | Data Format |
|-----------|---------------|-------------------|-------------|
| **pytest-cov / coverage.py** | Runtime code tracing during test execution | pytest, Python interpreter | `.coverage` binary, JSON, XML |
| **Jest Coverage** | Built-in code instrumentation using babel-plugin-istanbul | Jest test runner, babel transpiler | `coverage-summary.json`, LCOV |
| **Coverage Trend Tracker** | Historical tracking, regression detection, forecasting | Coverage JSON files, git metadata | JSONL trend logs |
| **PR Comment Bot** | Automated PR feedback with coverage diff | GitHub Actions API, coverage JSON | Markdown tables |
| **Quality Gate Workflow** | CI/CD enforcement of coverage thresholds | pytest, Jest, GitHub Actions | Exit codes, job status |
| **Coverage Dashboard** | Visual HTML reports with per-file breakdown | Coverage JSON, historical trends | HTML with inline annotations |
| **Progressive Gate Script** | Phase-based threshold management (70% → 80%) | pytest config, environment variables | Python config objects |
| **Emergency Bypass** | Override mechanism for urgent fixes | Environment variables, git metadata | Bypass tokens, audit logs |

### Data Flow Details

#### 1. Coverage Collection (Python)

**Configuration**: `pytest.ini` + `.coveragerc` (or embedded in pytest.ini)

```ini
[pytest]
addopts = --cov=backend --cov-branch --cov-report=json --cov-report=term-missing

[coverage:run]
source = backend
omit = */tests/*, */venv/*
branch = true

[coverage:report]
precision = 2
fail_under = 80  # Config file target (overridden by v11.0 pragmatic 70%)
exclude_lines =
    pragma: no cover
    if TYPE_CHECKING:
    def __repr__
```

**Execution Flow**:

1. pytest discovers tests via `pytest.ini` configuration
2. pytest-cov plugin activates (registered via `pytest --cov` flag)
3. coverage.py installs trace function on Python interpreter
4. Tests execute → coverage.py records executed line numbers
5. On teardown, coverage.py aggregates data and generates reports:
   - `coverage.json` (machine-readable per-file metrics)
   - `term-missing` (CLI output with missing lines)
   - `htmlcov/` (HTML report with source annotations)

**Integration Points**:
- **pytest plugins**: pytest-cov, pytest-asyncio (async test support)
- **CI/CD**: GitHub Actions `quality-gate.yml` runs `pytest --cov` and parses JSON
- **Trend tracking**: `coverage_trend_tracker.py` reads `coverage.json` and updates history

#### 2. Coverage Collection (JavaScript)

**Configuration**: `jest.config.js`

```javascript
module.exports = {
  collectCoverageFrom: [
    "components/**/*.{ts,tsx}",
    "pages/**/*.{ts,tsx}",
    "lib/**/*.{ts,tsx}",
    "hooks/**/*.{ts,tsx}",
  ],
  coverageReporters: ["json", "json-summary", "text", "lcov"],
  coverageDirectory: "coverage",
  coverageThreshold: {
    global: { lines: 70, branches: 70, functions: 70, statements: 70 },
  }
};
```

**Execution Flow**:

1. Jest discovers tests via `testMatch` patterns
2. babel-plugin-istanbul instruments code during transpilation
3. Tests execute → Istanbul tracks executed branches/lines
4. On completion, Jest generates reports:
   - `coverage/coverage-summary.json` (aggregated metrics)
   - `coverage/lcov.info` (for Codecov/Coveralls integration)
   - `coverage/` directory with per-file JSON

**Integration Points**:
- **Babel**: babel-plugin-istanbul automatically instruments TypeScript/JSX
- **CI/CD**: GitHub Actions reads `coverage-summary.json` for PR comments
- **Trend tracking**: `coverage-trend-tracker.js` appends to `coverage-trend.jsonl`

#### 3. Coverage Trend Tracking

**Python Implementation** (`coverage_trend_tracker.py`):

```python
# Key functions:
def record_snapshot(coverage_data: Dict, commit_hash: str) -> Dict:
    """Extract coverage snapshot from coverage.json"""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "commit": commit_hash,
        "coverage": {
            "total": coverage_data["totals"]["percent_covered"],
            "files": extract_per_file_metrics(coverage_data["files"])
        }
    }

def detect_regression(trend_history: List[Dict]) -> Optional[Dict]:
    """Alert if coverage decreases by >1 percentage point"""
    latest = trend_history[-1]["coverage"]["total"]
    previous = trend_history[-2]["coverage"]["total"]
    if latest < previous - REGRESSION_THRESHOLD:
        return {"regression": previous - latest}
    return None
```

**Data Storage**: JSONL format (`coverage_trend_v5.0.jsonl`)

```jsonl
{"timestamp": "2026-04-13T00:00:00Z", "commit": "abc123", "coverage": {"total": 18.25}}
{"timestamp": "2026-04-13T01:00:00Z", "commit": "def456", "coverage": {"total": 19.50}}
```

#### 4. PR Comment Bot Integration

**GitHub Actions Workflow** (`.github/workflows/quality-gate.yml`):

```yaml
- name: Run backend tests with coverage
  run: |
    pytest --cov=backend --cov-report=json:tests/coverage_reports/metrics/coverage_pr.json

- name: Check backend coverage threshold
  run: |
    python3 -c "
    import json
    with open('tests/coverage_reports/metrics/coverage_pr.json') as f:
        data = json.load(f)
    coverage = data['totals']['percent_covered']
    if coverage < 70.0:
        print(f'❌ Coverage {coverage:.2f}% below threshold 70%')
        exit(1)
    "

- name: Comment PR with coverage results
  if: github.event_name == 'pull_request'
  uses: actions/github-script@v7
  with:
    script: |
      const backendData = JSON.parse(fs.readFileSync('backend/tests/coverage_reports/metrics/coverage_pr.json'));
      // Generate and post comment
```

## Patterns to Follow

### Pattern 1: Progressive Coverage Gates (Phase-Based Rollout)

**What**: Gradual threshold increases (70% → 75% → 80%) to avoid blocking development while maintaining quality standards.

**When**: Multi-phase coverage expansion projects where aggressive targets would block progress.

**Example** (Python `progressive_coverage_gate.py`):

```python
def get_coverage_threshold(phase: str) -> Dict[str, float]:
    """Return coverage thresholds based on phase"""
    thresholds = {
        "phase_1": {"global": 70.0, "new_code": 80.0},
        "phase_2": {"global": 75.0, "new_code": 80.0},
        "phase_3": {"global": 80.0, "new_code": 80.0},
    }
    return thresholds.get(phase, thresholds["phase_1"])

def enforce_coverage_gate(coverage_data: Dict, phase: str = "phase_1") -> bool:
    """Check if coverage meets phase threshold"""
    thresholds = get_coverage_threshold(phase)
    current = coverage_data["totals"]["percent_covered"]

    # New code check (files modified in last 30 days)
    new_code_coverage = check_new_code_coverage(coverage_data["files"])

    if current < thresholds["global"] or new_code_coverage < thresholds["new_code"]:
        print(f"❌ Coverage {current:.2f}% below threshold {thresholds['global']}%")
        return False
    return True
```

**Integration**:
- Set `COVERAGE_PHASE` environment variable in CI/CD
- GitHub Actions: `env: COVERAGE_PHASE: phase_1`
- Local development: `export COVERAGE_PHASE=phase_1`

### Pattern 2: High-Impact File Prioritization

**What**: Focus coverage expansion on files with >200 lines and <10% coverage (maximum impact per test added).

**When**: Large codebase with limited resources, need to achieve coverage targets efficiently.

**Example** (Python `analyze_coverage_gaps.py`):

```python
def identify_high_impact_files(coverage_data: Dict) -> List[Dict]:
    """Find files with >200 lines and <10% coverage"""
    high_impact = []

    for filepath, file_data in coverage_data["files"].items():
        total_lines = file_data["summary"]["num_statements"]
        coverage_pct = file_data["summary"]["percent_covered"]

        if total_lines > 200 and coverage_pct < 10.0:
            high_impact.append({
                "file": filepath,
                "lines": total_lines,
                "coverage": coverage_pct,
                "missing": file_data["summary"]["missing_lines"],
                "potential_impact": total_lines * (100 - coverage_pct) / 100
            })

    return sorted(high_impact, key=lambda x: x["potential_impact"], reverse=True)
```

**Integration**:
- Run weekly to generate prioritized task lists
- Output formatted as GitHub Issues or project cards
- Track progress over time (should see high-impact files move out of <10% bucket)

### Pattern 3: Emergency Bypass Mechanism

**What**: Allow temporary coverage threshold bypass for urgent fixes, with audit logging and post-mortem requirements.

**When**: Production hotfixes, security patches, critical bugs that cannot wait for test coverage improvements.

**Example** (Python `emergency_coverage_bypass.py`):

```python
def check_emergency_bypass() -> bool:
    """Check if emergency bypass is enabled"""
    bypass = os.getenv("EMERGENCY_COVERAGE_BYPASS", "false").lower() == "true"
    if bypass:
        log_bypass_event()  # Audit trail
    return bypass

def log_bypass_event():
    """Log bypass usage for post-mortem review"""
    with open("coverage_bypass_audit.log", "a") as f:
        f.write(f"{datetime.now().isoformat()} | Bypass by {os.getenv('GITHUB_ACTOR')} | Commit {get_git_commit_hash()}\n")
```

**Integration**:
- GitHub Actions: `if: env.EMERGENCY_COVERAGE_BYPASS == 'true'`
- Manual trigger: `export EMERGENCY_COVERAGE_BYPASS=true`
- Post-mortem: Auto-create GitHub issue, assign to team lead

## Anti-Patterns to Avoid

### Anti-Pattern 1: Service-Level Coverage Aggregation

**What**: Aggregating coverage percentages from multiple services/modules without weighting by lines of code, creating false confidence.

**Why bad**: A 100% covered 10-line module masks a 0% covered 1000-line module. Aggregate shows 50%, but critical code is untested.

**Instead**: Use line-weighted averages or report per-module coverage. Coverage.py does this correctly by default.

**Evidence from v10.0 audit**: Phase 160-162 discovered service-level estimates (74.6%) didn't match actual line coverage (8.50%). Fix: Always use coverage.py totals, not manual aggregation.

### Anti-Pattern 2: Ignoring Branch Coverage

**What**: Only measuring line coverage (`--cov`) without branch coverage (`--cov-branch`), missing conditional logic gaps.

**Why bad**: Line coverage shows 100% but branch coverage reveals untested `if/else` paths. False confidence in code quality.

**Instead**: Always use `--cov-branch` flag for Python and enable branch coverage in Jest.

**Configuration**:

```ini
[pytest]
addopts = --cov-branch  # CRITICAL: Enable branch coverage

[coverage:run]
branch = true  # Measure branch coverage
```

### Anti-Pattern 3: Coverage Without Quality Gates

**What**: Generating coverage reports but not enforcing thresholds in CI/CD, allowing coverage to regress over time.

**Why bad**: Coverage becomes a vanity metric. No incentive to maintain or improve it. Technical debt accumulates.

**Instead**: Always enforce coverage thresholds in CI/CD with quality gates.

## Scalability Considerations

| Concern | At 100 users | At 10K users | At 1M users |
|---------|--------------|--------------|-------------|
| **Coverage collection time** | <30s (pytest), <60s (Jest) | <2 min (parallel pytest) | <5 min (sharded tests) |
| **Coverage report size** | <100 KB JSON | <500 KB JSON | <2 MB JSON (need pruning) |
| **Trend tracking storage** | <1 MB JSONL (6 months) | <10 MB JSONL (6 months) | Need database (SQLite/Postgres) |
| **Dashboard generation** | <5s (HTML) | <15s (HTML + charts) | <30s (cached dashboards) |
| **PR comment bot latency** | <2s (GitHub API) | <3s (GitHub API) | Need rate limiting |
| **Quality gate CI time** | <10 min (pytest + coverage) | <15 min (parallel) | <20 min (matrix builds) |

**Scaling Strategies**:

1. **Parallel Test Execution**: Use `pytest-xdist` for Python, Jest `maxWorkers` for JavaScript
2. **Report Pruning**: Keep last 90 days of trend data, archive older data to separate storage
3. **Cached Dashboards**: Generate HTML reports once per day, serve static files
4. **Database Migration**: Move from JSONL to SQLite at 10K users, PostgreSQL at 1M users
5. **Sharded Coverage**: Run coverage on subset of tests (e.g., 10% sample) for rapid feedback

## New vs Modified Components

### New Components for v11.0

| Component | Purpose | Dependencies | Integration Points |
|-----------|---------|--------------|-------------------|
| **Frontend Test Fix Suite** | Fix 1,504 failing tests (28.8% failure rate) | Jest, React Testing Library | Phase 250 execution, test file modifications |
| **Backend Coverage Wave Scripts** | Incremental coverage expansion (70% target) | pytest, pytest-cov, coverage.py | CI/CD workflows, trend tracker |
| **Frontend Coverage Wave Scripts** | Incremental coverage expansion (70% target) | Jest, nyc, babel-plugin-istanbul | CI/CD workflows, trend tracker |
| **High-Impact File Analyzer** | Prioritize files >200 lines with <10% coverage | coverage.json, Python stdlib | Dashboard generation, task tracking |
| **Emergency Bypass Auditor** | Log and post-mortem coverage bypasses | GitHub API, environment variables | CI/CD workflows, issue tracking |

### Modified Components for v11.0

| Component | Changes | Breaking Changes | Migration Path |
|-----------|---------|------------------|----------------|
| **pytest.ini** | Update fail_under from 80% → 70% (pragmatic) | No (threshold relaxed) | Update .coveragerc if needed |
| **jest.config.js** | Update thresholds to 70% (phase_1) | No (thresholds are dynamic) | Set COVERAGE_PHASE=phase_1 in CI |
| **quality-gate.yml** | Change threshold check from 80% → 70% | No (relaxed constraint) | Update workflow file |

### Build Order (Dependency-Respecting)

**Phase 1: Infrastructure & Fixing Test Suite**
1. Fix frontend test failures (unblock coverage measurement)
2. Verify pytest/Jest configurations
3. Run baseline coverage measurement (establish current state)

**Phase 2: Measurement & Baseline**
4. Generate baseline coverage reports (backend + frontend)
5. Initialize trend tracking (populate history from v10.0)
6. Create coverage dashboard (HTML reports)

**Phase 3: Coverage Expansion (Backlog)**
7. Backend coverage waves (high-impact files first)
8. Frontend coverage waves (parallel with backend)
9. Property test expansion (invariant validation)
10. Quality gate enforcement (70% threshold active)

**Phase 4: Reporting & Enforcement**
11. PR comment bot automation (per-commit feedback)
12. Coverage dashboard automation (daily generation)
13. Emergency bypass mechanism (last resort)
14. Post-mortem process (audit trail)

**Rationale**:
- Cannot measure coverage accurately with failing tests (Phase 1 blocker)
- Baseline required before expansion can be measured (Phase 2 dependency)
- Coverage expansion depends on prioritization (Phase 3 requires Phase 2)
- Enforcement requires reliable measurement (Phase 4 requires Phase 3)

## Integration Points (Existing Infrastructure)

### Python pytest Integration

**Existing Plugins** (from `backend/pyproject.toml`):

```toml
[project.optional-dependencies]
test = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",  # Async test support
    "pytest-cov>=4.0.0",       # Coverage collection
]

test-quality = [
    "pytest-json-report>=1.5.0",   # JSON test reports
    "pytest-random-order>=1.1.0",  # Random test order (flaky detection)
    "pytest-rerunfailures>=14.0",  # Auto-retry flaky tests
]
```

**Existing Configuration** (`pytest.ini`):

```ini
[pytest]
# Coverage collection
addopts = -q --strict-markers --tb=line
testpaths = tests tests/fuzzing tests/browser_discovery tests/e2e_ui/tests

[coverage:run]
source = backend
omit = */tests/*, */test_*.py, */__pycache__/*
branch = true  # Enable branch coverage

[coverage:report]
precision = 2
show_missing = True
fail_under = 80  # Existing config (update to 70 for v11.0)
```

**Integration Points**:
- pytest-cov plugin hooks into pytest collection/execution
- coverage.py trace function records line execution
- JSON reports parsed by trend tracker scripts
- HTML reports uploaded as CI artifacts

### JavaScript Jest Integration

**Existing Configuration** (`frontend-nextjs/jest.config.js`):

```javascript
module.exports = {
  preset: "ts-jest",
  testEnvironment: "jsdom",

  // Coverage collection
  collectCoverageFrom: [
    "components/**/*.{ts,tsx}",
    "pages/**/*.{ts,tsx}",
    "lib/**/*.{ts,tsx}",
    "hooks/**/*.{ts,tsx}",
  ],
  coverageReporters: ["json", "json-summary", "text", "lcov"],

  // Progressive thresholds (Phase 153)
  get coverageThreshold() {
    return {
      global: { lines: 70, branches: 70, functions: 70, statements: 70 },
      './src/**/*.{ts,tsx}': { lines: 80, branches: 80 },  // New code
      './lib/**/*.{ts,tsx}': { lines: 90, branches: 90 },  // Utilities
    };
  },
};
```

**Integration Points**:
- babel-plugin-istanbul instruments code during transpilation
- Jest collects coverage data during test execution
- `coverage-summary.json` parsed by trend tracker
- LCOV format for external services (Codecov/Coveralls)

### CI/CD Pipeline Integration

**Existing Workflows** (from `.github/workflows/`):

1. **quality-gate.yml**: Enforces 70% coverage threshold (updated from 80%)
   - Runs backend pytest with coverage
   - Runs frontend Jest with coverage
   - Checks thresholds and fails CI if below
   - Comments PR with coverage results

2. **quality-metrics.yml**: Collects and stores coverage trends
   - Runs tests and generates coverage JSON
   - Calculates quality metrics (test count, coverage)
   - Uploads metrics artifact (90-day retention)
   - Commits metrics data to repository

**Integration Points**:
- GitHub Actions API for PR comments
- Artifact storage for coverage reports
- Git history for trend tracking
- Environment variables for phase control

### Coverage Scripts Integration

**Existing Python Scripts** (from `backend/tests/scripts/`):

- `generate_baseline_coverage_report.py`: Baseline measurement
- `coverage_trend_tracker.py`: Historical tracking, regression detection
- `coverage_trend_analyzer.py`: Trend analysis, forecasting
- `pr_coverage_comment_bot.py`: PR comment automation
- `progressive_coverage_gate.py`: Phase-based thresholds
- `emergency_coverage_bypass.py`: Bypass mechanism with audit

**Existing JavaScript Scripts** (from `frontend-nextjs/scripts/`):

- `coverage-trend-tracker.js`: Historical tracking
- `coverage-audit.js`: Coverage audit and gap analysis
- `analyze-coverage-baseline.js`: Baseline measurement
- `check-module-coverage.js`: Per-module threshold checking

**Integration Points**:
- All scripts read JSON coverage reports (standard format)
- Scripts called via npm/yarn package.json scripts
- CI/CD workflows execute scripts and parse output
- Trend data stored in JSONL format (line-delimited JSON)

## Data Flow Changes for v11.0

### Current State (v10.0)

```
pytest/Jest → Coverage JSON → Manual Review → (No Enforcement)
```

**Issues**:
- Frontend tests failing (28.8% failure rate)
- Coverage baseline unreliable (14.61% may be inaccurate)
- No enforcement of 70% threshold (quality gates inactive)
- No PR comment automation (manual coverage checks)

### Target State (v11.0)

```
Fix Tests → Measure Baseline → Expand Coverage → Enforce Gates → PR Comments
```

**Data Flow Changes**:

1. **Test Fixing Wave** (Phase 250):
   - Fix 1,504 failing frontend tests
   - Enable accurate coverage measurement
   - Unblock baseline generation

2. **Baseline Measurement** (Phase 251, 254):
   - Run pytest with `--cov` (backend)
   - Run Jest with `--coverage` (frontend)
   - Generate coverage.json and coverage-summary.json
   - Store baseline metrics in trend tracker

3. **Coverage Expansion** (Phases 252, 253, 255, 256):
   - Incremental test writing for high-impact files
   - Per-wave coverage measurement
   - Trend tracking updates (weekly)
   - Dashboard generation (daily)

4. **Quality Gate Enforcement** (Phase 258):
   - CI/CD quality gates active (70% threshold)
   - PR comment bot automation
   - Emergency bypass mechanism (last resort)
   - Post-mortem process for bypasses

## Suggested Build Order

### Week 1-2: Test Suite Stabilization

**Priority**: CRITICAL (unblocks all coverage work)

1. **Fix Frontend Test Failures** (Phase 250)
   - Investigate 1,504 failing tests
   - Categorize by severity (critical/high/medium/low)
   - Fix critical failures first (authentication, routing)
   - Target: 100% pass rate (currently 71.2%)

2. **Verify pytest Configuration**
   - Ensure pytest.ini has correct test paths
   - Validate pytest-cov plugin installation
   - Test coverage collection on small subset
   - Fix any import errors or dependency issues

3. **Verify Jest Configuration**
   - Ensure jest.config.js has correct coverage settings
   - Validate babel-plugin-istanbul installation
   - Test coverage collection on small subset
   - Fix any transpilation or module resolution issues

### Week 3: Baseline Measurement

**Priority**: HIGH (establishes current state)

4. **Generate Backend Coverage Baseline** (Phase 251)
   - Run `pytest --cov=backend --cov-branch --cov-report=json`
   - Parse coverage.json (validate structure)
   - Calculate overall coverage: 18.25% (current)
   - Identify high-impact files (>200 lines, <10% coverage)

5. **Generate Frontend Coverage Baseline** (Phase 254)
   - Run `npm run test:coverage -- --coverage`
   - Parse coverage-summary.json (validate structure)
   - Calculate overall coverage: 14.61% (current)
   - Identify low-coverage modules (<30% coverage)

6. **Initialize Trend Tracking**
   - Create coverage_trend_v11.0.jsonl files (backend + frontend)
   - Import v10.0 historical data (if available)
   - Set up automated trend collection (daily cron)
   - Generate baseline HTML dashboard

### Week 4-6: Coverage Expansion (Iterative)

**Priority**: MEDIUM (incremental progress)

7. **Backend Coverage Wave 1** (Phase 252)
   - Target: High-impact files (>200 lines, <10% coverage)
   - Write unit tests for top 10 files
   - Run coverage measurement after each file
   - Expected gain: +10-15 percentage points

8. **Frontend Coverage Wave 1** (Phase 255)
   - Target: Low-coverage modules (<30% coverage)
   - Write component tests for top 5 modules
   - Run coverage measurement after each module
   - Expected gain: +8-12 percentage points

9. **Backend Coverage Wave 2** (Phase 253)
   - Target: Medium-impact files (100-200 lines, <30% coverage)
   - Write integration tests for top 10 files
   - Add property tests for invariants
   - Expected gain: +10-15 percentage points

10. **Frontend Coverage Wave 2** (Phase 256)
    - Target: Medium-coverage modules (30-50% coverage)
    - Write hook tests and integration tests
    - Add accessibility tests (jest-axe)
    - Expected gain: +8-12 percentage points

### Week 7: Quality Gate Activation

**Priority**: HIGH (enforcement mechanism)

11. **Activate Quality Gates** (Phase 258)
    - Update quality-gate.yml threshold to 70%
    - Enable PR comment bot automation
    - Test quality gates on sample PR
    - Verify CI/CD failure on coverage regression

12. **Deploy Coverage Dashboard**
    - Generate HTML dashboards (backend + frontend)
    - Upload to GitHub Pages or internal hosting
    - Set up daily dashboard regeneration
    - Create team training materials

13. **Implement Emergency Bypass**
    - Deploy emergency_coverage_bypass.py
    - Create bypass documentation (when to use)
    - Set up post-mortem automation (GitHub issues)
    - Train team on bypass process

### Week 8: Verification & Handoff

**Priority**: MEDIUM (validation)

14. **Verify Coverage Targets**
    - Measure final coverage (backend: 70%, frontend: 70%)
    - Validate trend tracking data integrity
    - Check quality gate enforcement (pass/fail)
    - Review PR comment bot output

15. **Documentation & Training**
    - Update TESTING.md with coverage expansion patterns
    - Create training presentation for team
    - Document high-impact file prioritization process
    - Archive v11.0 research and planning documents

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| **Python pytest-cov Integration** | HIGH | Standard tool, well-documented, existing infrastructure operational |
| **JavaScript Jest Coverage** | HIGH | Built-in Jest feature, existing configuration, battle-tested |
| **Coverage Trend Tracking** | HIGH | Existing scripts proven in v5.0, JSONL format stable |
| **PR Comment Bot Automation** | HIGH | GitHub Actions API well-documented, existing patterns work |
| **Quality Gate Enforcement** | HIGH | CI/CD threshold checking standard practice, no blockers |
| **Emergency Bypass Mechanism** | MEDIUM | Pattern exists (emergency governance bypass), needs adaptation for coverage |
| **Frontend Test Fixing** | MEDIUM | 1,504 failing tests is large backlog, complexity unknown until investigation |
| **High-Impact File Prioritization** | HIGH | Algorithm straightforward (lines × coverage gap), existing scripts do similar analysis |
| **Coverage Dashboard Generation** | HIGH | HTML generation proven, existing dashboards operational |
| **Per-Module Thresholds** | HIGH | Jest configuration supports it, pytest requires custom script (existing) |

**Overall Confidence: HIGH**

All core integration points (pytest-cov, Jest coverage, CI/CD) are well-established technologies with existing infrastructure at Atom. Main uncertainty is frontend test fixing complexity (1,504 failures), but this is a known blocker with clear path forward (fix → baseline → expand).

## Gaps to Address

1. **Frontend Test Failure Investigation**
   - Need to categorize 1,504 failing tests by root cause
   - Identify if failures are due to code changes, test flakiness, or configuration issues
   - Estimate time required for fixes (currently unknown)
   - **Phase-Specific Research Needed**: Week 1 investigation

2. **Coverage Baseline Accuracy**
   - Frontend 14.61% baseline may be unreliable due to failing tests
   - Backend 18.25% baseline needs verification (service-level vs actual line coverage)
   - Need to validate coverage.json structure and data integrity
   - **Phase-Specific Research Needed**: Week 3 baseline measurement

3. **Property Test Integration**
   - Need to ensure coverage expansion includes property tests (Hypothesis, FastCheck)
   - Property tests should count toward coverage targets
   - Need to validate that pytest-cov includes property test execution
   - **Phase-Specific Research Needed**: Week 4 coverage expansion

4. **Emergency Bypass Governance**
   - Need to define when bypass is appropriate (e.g., security patches only)
   - Need to establish post-mortem review process
   - Need to set up audit log retention and access controls
   - **Phase-Specific Research Needed**: Week 7 quality gate activation

5. **Cross-Platform Coverage Aggregation**
   - Need to decide if mobile/desktop coverage included in 70% target
   - Current metrics show mobile 16.16%, desktop TBD
   - May need weighted coverage targets (backend 70%, frontend 70%, mobile 50%, desktop 50%)
   - **Phase-Specific Research Needed**: Week 3 baseline measurement

## Sources

### High Confidence (Official Documentation)
- **pytest-cov Documentation**: https://pytest-cov.readthedocs.io/en/latest/ (pytest plugin for coverage.py)
- **coverage.py Documentation**: https://coverage.readthedocs.io/en/7.4.0/ (Python coverage measurement tool)
- **Jest Coverage Configuration**: https://jestjs.io/docs/configuration#collectcoveragefrom-array (Built-in Jest coverage)
- **GitHub Actions API**: https://docs.github.com/en/rest/reference/actions (PR comment automation)
- **Atom pytest.ini**: /Users/rushiparikh/projects/atom/backend/pytest.ini (existing configuration)
- **Atom jest.config.js**: /Users/rushiparikh/projects/atom/frontend-nextjs/jest.config.js (existing configuration)
- **Atom quality-gate.yml**: /Users/rushiparikh/projects/atom/.github/workflows/quality-gate.yml (existing CI/CD workflow)

### Medium Confidence (Existing Code Analysis)
- **coverage_trend_tracker.py**: /Users/rushiparikh/projects/atom/backend/tests/scripts/coverage_trend_tracker.py (proven pattern)
- **coverage-trend-tracker.js**: /Users/rushiparikh/projects/atom/frontend-nextjs/scripts/coverage-trend-tracker.js (proven pattern)
- **generate_baseline_coverage_report.py**: /Users/rushiparikh/projects/atom/backend/tests/scripts/generate_baseline_coverage_report.py (baseline generation)
- **pr_coverage_comment_bot.py**: /Users/rushiparikh/projects/atom/backend/tests/scripts/pr_coverage_comment_bot.py (PR automation)
- **progressive_coverage_gate.py**: /Users/rushiparikh/projects/atom/backend/tests/scripts/progressive_coverage_gate.py (phase-based thresholds)

### Low Confidence (WebSearch - Limit Exhausted)
- **pytest-cov Integration Best Practices 2026**: Web search unavailable (API limit exhausted May 1, 2026)
- **Jest Coverage Performance Optimization**: Web search unavailable (API limit exhausted)
- **Cross-Platform Coverage Aggregation Patterns**: Web search unavailable (API limit exhausted)

**Note**: Web search limit reached during research. Findings based on official documentation (HIGH confidence) and existing Atom codebase analysis (MEDIUM confidence). No LOW confidence web search results included in this architecture research.
