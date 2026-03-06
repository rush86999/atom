# Cross-Platform Coverage Guide

## Overview

Atom is a multi-platform AI automation platform with four distinct codebases: **Backend** (Python/FastAPI), **Frontend** (React/Next.js), **Mobile** (React Native), and **Desktop** (Tauri/Rust). This guide explains the cross-platform coverage enforcement system that ensures balanced quality across all platforms.

**The Problem:** Simple averaging masks platform-specific gaps. If backend is 90%, frontend is 85%, mobile is 30%, and desktop is 20%, the average is 56.25% — but mobile and desktop are critically under-tested.

**The Solution:** Enforce **platform-specific minimum thresholds** (backend ≥70%, frontend ≥80%, mobile ≥50%, desktop ≥40%) while computing a **weighted overall score** for quality gate decisions.

**Benefits:**
- **Prevents hiding:** Low-coverage platforms cannot hide behind high-coverage platforms
- **Balanced quality:** Each platform meets its minimum threshold based on business impact
- **Weighted overall:** Single score for CI/CD gates reflects platform importance
- **Trend tracking:** Monitor coverage regression separately per platform

**Phase:** 146 - Cross-Platform Weighted Coverage (Complete)
**Status:** Operational in CI/CD

## Quick Start

### Local Execution

Run all platform tests and generate cross-platform coverage report:

```bash
# 1. Run backend tests (Python)
cd backend
pytest --cov=core --cov=api --cov=tools --cov-report=json:tests/coverage_reports/metrics/coverage.json
cd ..

# 2. Run frontend tests (Next.js)
cd frontend-nextjs
npm test -- --coverage --watchAll=false
cd ..

# 3. Run mobile tests (React Native)
cd mobile
npm test -- --coverage
cd ..

# 4. Run desktop tests (Rust/Tauri)
cd frontend-nextjs/src-tauri
cargo tarpaulin --out Json --output-dir coverage
cd ../..

# 5. Generate cross-platform report
python backend/tests/scripts/cross_platform_coverage_gate.py \
  --backend-coverage backend/tests/coverage_reports/metrics/coverage.json \
  --frontend-coverage frontend-nextjs/coverage/coverage-final.json \
  --mobile-coverage mobile/coverage/coverage-final.json \
  --desktop-coverage frontend-nextjs/src-tauri/coverage/coverage.json \
  --format text

# 6. Check results
cat backend/tests/coverage_reports/metrics/cross_platform_summary.json
```

### CI/CD Execution

Coverage runs automatically on push/PR to main/develop branches. See `.github/workflows/cross-platform-coverage.yml` for workflow configuration.

```bash
# Manual trigger (requires GitHub CLI)
gh workflow run cross-platform-coverage.yml

# View results
gh run list --workflow=cross-platform-coverage.yml
gh run view [run-id]
```

### Expected Output

```
Cross-Platform Coverage Report
===============================

Backend: 75.00% (threshold: 70.00%) ✓
Frontend: 82.50% (threshold: 80.00%) ✓
Mobile: 55.00% (threshold: 50.00%) ✓
Desktop: 45.00% (threshold: 40.00%) ✓

Weighted Overall: 72.38% (backend: 35%, frontend: 40%, mobile: 15%, desktop: 10%)

All platforms passed minimum thresholds ✓
```

## Architecture

### Components

The cross-platform coverage system consists of three core components:

1. **cross_platform_coverage_gate.py** - Main enforcement script
   - Loads coverage from all 4 platforms (pytest, Jest, jest-expo, tarpaulin)
   - Enforces platform-specific thresholds (70/80/50/40)
   - Computes weighted overall score (35/40/15/10 distribution)
   - Generates reports (text, JSON, markdown, PR comment)
   - Exits with status code for CI/CD (0=pass, 1=fail, 2=error)

2. **update_cross_platform_trending.py** - Trend tracking script
   - Loads historical trend data from `cross_platform_trend.json`
   - Computes trend deltas (current vs. previous, 7-period average)
   - Stores new entries with commit SHA, branch, timestamp
   - Generates trend indicators (↑↓→)
   - Retains 30 days of historical data

3. **cross-platform-coverage.yml** - GitHub Actions workflow
   - Runs platform tests in parallel (4 jobs)
   - Uploads coverage artifacts (30-day retention)
   - Downloads all artifacts in aggregate job
   - Runs enforcement script with trend tracking
   - Posts PR comments with platform breakdown and trends
   - Enforces thresholds on main branch (warnings on PRs)

### Data Flow

```
┌─────────────────┐
│ Platform Tests  │
│ (pytest/Jest/   │
│  jest-expo/     │
│  tarpaulin)     │
└────────┬────────┘
         │ Generate coverage reports
         ▼
┌─────────────────┐
│ Coverage Files  │
│ (coverage.json, │
│  coverage-      │
│  final.json,    │
│  tarpaulin.json)│
└────────┬────────┘
         │ CI uploads artifacts
         ▼
┌─────────────────┐
│ GitHub Actions  │
│ Artifacts       │
│ (30-day retain) │
└────────┬────────┘
         │ Aggregate job downloads all
         ▼
┌─────────────────────────────────────┐
│ cross_platform_coverage_gate.py     │
│ - Load all coverage files           │
│ - Parse platform-specific formats   │
│ - Enforce thresholds                │
│ - Compute weighted overall          │
│ - Generate report (text/JSON/MD)    │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│ PR Comment / GitHub Step Summary    │
│ - Platform breakdown table          │
│ - Threshold pass/fail status        │
│ - Trend indicators (↑↓→)            │
│ - Gap analysis and remediation      │
└─────────────────────────────────────┘
```

### Platform-Specific Formats

Each platform generates coverage in a different JSON format:

**Backend (pytest coverage.json):**
```json
{
  "totals": {
    "percent_covered": 75.0,
    "covered_lines": 1500,
    "num_statements": 2000
  }
}
```

**Frontend/Mobile (Jest coverage-final.json):**
```json
{
  "src/file.ts": {
    "s": {"1": 10, "2": 5},
    "b": {"1": [10, 5]},
    "f": {"1": 10},
    "l": {"1": 10}
  }
}
```
- `s`: Statement coverage (hit count per statement)
- `b`: Branch coverage (hit count per branch)
- `f`: Function coverage (hit count per function)
- `l`: Line coverage (hit count per line)

**Desktop (tarpaulin coverage.json):**
```json
{
  "files": {
    "src/main.rs": {
      "stats": {
        "covered": 50,
        "coverable": 100,
        "percent": 50.0
      }
    }
  }
}
```

The enforcement script handles all three formats automatically.

## Platform Thresholds

### Minimum Thresholds

| Platform | Threshold | Rationale |
|----------|-----------|-----------|
| **Backend** | ≥70% | Mature codebase, complex async logic, database interactions, external service integrations. Lower target due to large codebase size (500+ files) and integration testing challenges. |
| **Frontend** | ≥80% | User-facing code, UI criticality, high testability with React Testing Library. Rapid iteration requires strong test coverage to prevent regressions. |
| **Mobile** | ≥50% | React Native, newer codebase, platform-specific challenges (device permissions, native modules). Moderate target due to testing infrastructure limitations (simulators, hardware mocks). |
| **Desktop** | ≥40% | Tauri/Rust, niche platform, hardware-dependent features (file dialogs, system tray). Lowest target due to platform-specific code and GUI testing complexity. |

### Threshold Rationale

**Backend (70%):**
- Python codebase is large (500+ files in core/, api/, tools/)
- Integration tests require database, external services
- Async/await patterns harder to test comprehensively
- Historical baseline: 26.15% (Phase 127), significant gap to close
- Target: 70% is achievable with focused integration testing

**Frontend (80%):**
- React/Next.js highly testable with React Testing Library
- Component tests are fast and reliable
- User-facing bugs have high business impact
- Historical baseline: 4.87% (Phase 130), massive gap
- Target: 80% aligns with industry standards for UI code

**Mobile (50%):**
- React Native testing infrastructure still maturing (Phase 135-139)
- Device-specific features require platform mocking (Camera, Location, Notifications)
- Simulators/emulators slower than web tests
- Historical baseline: 16.16% (Phase 135)
- Target: 50% balances quality with development velocity

**Desktop (40%):**
- Tauri/Rust coverage measurement complex (tarpaulin linking issues on macOS)
- System integration tests require GUI context or manual QA
- Niche platform (Windows/macOS/Linux) with smaller user base
- Historical baseline: <5% (Phase 140), 35% estimated (Phase 141)
- Target: 40% ensures critical paths tested without blocking development

### Customization

Override default thresholds via command-line:

```bash
# Raise all thresholds by 5%
python cross_platform_coverage_gate.py \
  --thresholds backend=75,frontend=85,mobile=55,desktop=45 \
  --format text

# Lower mobile threshold temporarily
python cross_platform_coverage_gate.py \
  --thresholds mobile=40 \
  --format json
```

**Note:** Custom thresholds should be justified in commit messages and reviewed regularly.

## Weight Distribution

### Formula

The weighted overall coverage is computed as:

```
overall = (backend × 0.35) + (frontend × 0.40) + (mobile × 0.15) + (desktop × 0.10)
```

### Weight Rationale

Weights reflect **business impact** and **user base size**:

| Platform | Weight | Business Impact | Justification |
|----------|--------|-----------------|---------------|
| **Frontend** | 40% | Highest | User-facing UI, direct impact on UX, every user interacts with frontend. Bugs are immediately visible. |
| **Backend** | 35% | High | Core logic, data integrity, LLM integrations, governance. Issues affect all users but may be less visible. |
| **Mobile** | 15% | Medium | Important platform but smaller user base. Mobile-specific bugs don't affect web/desktop users. |
| **Desktop** | 10% | Lower | Niche platform, supplementary experience. Desktop-specific bugs affect small subset of users. |

**Total:** 100% (must sum to 1.0)

### Weight Validation

The enforcement script validates weights at startup:

```python
def validate_weights(weights: Dict[str, float]) -> None:
    """Validate that weights sum to 1.0."""
    total = sum(weights.values())

    if not (0.99 <= total <= 1.01):  # Floating point tolerance
        raise ValueError(
            f"Weights must sum to 1.0, got {total:.2f}. "
            f"Adjust weights: {weights}"
        )
```

If weights don't sum to 1.0, the script exits with error code 2.

### Customization

Override default weights via command-line:

```bash
# Emphasize backend quality (50% backend, 30% frontend, 12% mobile, 8% desktop)
python cross_platform_coverage_gate.py \
  --weights backend=0.50,frontend=0.30,mobile=0.12,desktop=0.08 \
  --format text

# Equal weights for all platforms (25% each)
python cross_platform_coverage_gate.py \
  --weights backend=0.25,frontend=0.25,mobile=0.25,desktop=0.25 \
  --format json
```

**Warning:** Custom weights should be used sparingly and documented in PR descriptions.

## Coverage File Formats

### Backend (pytest coverage.json)

**Location:** `backend/tests/coverage_reports/metrics/coverage.json`

**Format:**
```json
{
  "totals": {
    "percent_covered": 75.0,
    "covered_lines": 1500,
    "num_statements": 2000,
    "percent_branches_covered": 70.0,
    "percent_branches_covered": 70.0
  },
  "files": {
    "core/agent_governance_service.py": {
      "summary": {
        "percent_covered": 80.0,
        "covered_lines": 80,
        "num_statements": 100
      }
    }
  }
}
```

**Generation:**
```bash
pytest --cov=core --cov=api --cov=tools \
  --cov-report=json:tests/coverage_reports/metrics/coverage.json \
  --cov-report=term-missing
```

**Schema:** The script reads `totals.percent_covered` for overall coverage.

### Frontend/Mobile (Jest coverage-final.json)

**Location:**
- Frontend: `frontend-nextjs/coverage/coverage-final.json`
- Mobile: `mobile/coverage/coverage-final.json`

**Format:**
```json
{
  "src/components/Button.tsx": {
    "s": {"1": 10, "2": 5, "3": 0},
    "b": {"1": [10, 5]},
    "f": {"1": 10},
    "l": {"1": 10, "2": 5, "3": 0}
  },
  "src/hooks/useCanvasState.ts": {
    "s": {"1": 15, "2": 10},
    "b": {"1": [15, 10], "2": [10, 5]},
    "f": {"1": 15},
    "l": {"1": 15, "2": 10}
  }
}
```

**Generation:**
```bash
# Frontend
npm test -- --coverage --watchAll=false

# Mobile
npm test -- --coverage
```

**Schema:** The script aggregates statement coverage (`s` key) across all files, filtering out `node_modules` and `__tests__`.

**Computation:**
```python
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

coverage_pct = (covered_statements / total_statements * 100) if total_statements > 0 else 0.0
```

### Desktop (tarpaulin coverage.json)

**Location:** `frontend-nextjs/src-tauri/coverage/coverage.json`

**Format:**
```json
{
  "files": {
    "src/main.rs": {
      "stats": {
        "covered": 50,
        "coverable": 100,
        "percent": 50.0
      }
    },
    "src/commands.rs": {
      "stats": {
        "covered": 30,
        "coverable": 50,
        "percent": 60.0
      }
    }
  }
}
```

**Generation:**
```bash
cargo tarpaulin --out Json --output-dir coverage
```

**Schema:** The script computes weighted average across all files:

```python
total_coverable = 0
total_covered = 0

for file_path, file_data in data["files"].items():
    stats = file_data["stats"]
    total_coverable += stats["coverable"]
    total_covered += stats["covered"]

coverage_pct = (total_covered / total_coverable * 100) if total_coverable > 0 else 0.0
```

### Missing Files

If a coverage file is missing, the script treats that platform as 0% coverage and logs a warning:

```
WARNING: Frontend coverage file not found: frontend-nextjs/coverage/coverage-final.json
WARNING: Treating frontend as 0% coverage
```

This allows partial coverage reports (e.g., backend-only PRs) without failing the entire gate.

## CLI Reference

### Script: cross_platform_coverage_gate.py

**Location:** `backend/tests/scripts/cross_platform_coverage_gate.py`

**Usage:**
```bash
python cross_platform_coverage_gate.py [options]
```

**Arguments:**

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--backend-coverage` | Path | Auto-detected | Path to pytest coverage.json |
| `--frontend-coverage` | Path | Auto-detected | Path to Jest coverage-final.json (frontend) |
| `--mobile-coverage` | Path | Auto-detected | Path to jest-expo coverage-final.json (mobile) |
| `--desktop-coverage` | Path | Auto-detected | Path to tarpaulin coverage.json |
| `--weights` | CSV | 0.35,0.40,0.15,0.10 | Override default weights (backend=X,frontend=Y,...) |
| `--thresholds` | CSV | 70,80,50,40 | Override default thresholds (backend=X,frontend=Y,...) |
| `--format` | text\|json\|markdown\|pr-comment | text | Output format |
| `--output-json` | Path | cross_platform_summary.json | Save JSON output to file |
| `--strict` | Flag | False | Exit 1 if any platform below threshold |

**Auto-detected Paths:**

If not specified, the script uses these default paths (relative to script location):

- Backend: `../../../tests/coverage_reports/metrics/coverage.json`
- Frontend: `../../../../frontend-nextjs/coverage/coverage-final.json`
- Mobile: `../../../../mobile/coverage/coverage-final.json`
- Desktop: `../../../../frontend-nextjs/src-tauri/coverage/coverage.json`

**Exit Codes:**

| Code | Meaning |
|------|---------|
| 0 | Success (all platforms passed thresholds) |
| 1 | Threshold failure (at least one platform below minimum) |
| 2 | Execution error (missing file, parse error, weight validation failed) |

### Examples

**Basic usage (text output):**
```bash
python cross_platform_coverage_gate.py --format text
```

**JSON output for CI/CD:**
```bash
python cross_platform_coverage_gate.py --format json --output-json cross_platform_summary.json
```

**Strict mode (fail build on threshold violations):**
```bash
python cross_platform_coverage_gate.py --strict --format text
```

**Custom thresholds and weights:**
```bash
python cross_platform_coverage_gate.py \
  --thresholds backend=75,frontend=85,mobile=55,desktop=45 \
  --weights backend=0.40,frontend=0.35,mobile=0.15,desktop=0.10 \
  --format markdown
```

**PR comment format:**
```bash
python cross_platform_coverage_gate.py --format pr-comment > pr_comment.md
```

## Troubleshooting

### Missing Coverage Files

**Symptom:**
```
WARNING: Frontend coverage file not found: frontend-nextjs/coverage/coverage-final.json
WARNING: Treating frontend as 0% coverage
Frontend: 0.00% < 80.00% (gap: 80.00%)
```

**Cause:** Platform tests didn't run or failed, so coverage file wasn't generated.

**Solution:**
1. Check platform-specific job logs in GitHub Actions
2. Verify tests are passing: `npm test -- --coverage` (frontend/mobile)
3. Ensure coverage report generation is enabled in test config
4. Check file paths in CI/CD workflow (artifact upload/download)

**Example fix:**
```yaml
# .github/workflows/cross-platform-coverage.yml

- name: Run frontend tests
  run: npm test -- --coverage --watchAll=false
  # ^^ Must generate coverage/coverage-final.json

- name: Upload frontend coverage
  uses: actions/upload-artifact@v4
  with:
    name: frontend-coverage
    path: frontend-nextjs/coverage/coverage-final.json
```

### Threshold Failures

**Symptom:**
```
Backend: 65.00% < 70.00% (gap: 5.00%)
Frontend: 82.50% >= 80.00% ✓
Mobile: 45.00% < 50.00% (gap: 5.00%)
Desktop: 42.00% >= 40.00% ✓

✗ Threshold failures detected
```

**Cause:** Coverage below minimum threshold for one or more platforms.

**Solution:**
1. **Add tests** for uncovered code paths
2. **Review PR comment** for specific file-level gaps (if available)
3. **Use coverage reports** to identify high-impact files:
   ```bash
   # Backend
   pytest --cov=core --cov-report=term-missing

   # Frontend
   npm test -- --coverage --coverageReporters="text"

   # Mobile
   npm test -- --coverage --coverageReporters="text"

   # Desktop
   cargo tarpaulin --out Html
   open tarpaulin-report.html
   ```
4. **Focus on high-impact files** first (governance, episodic memory, LLM services)
5. **Consider lowering threshold temporarily** if gap is large (document rationale in commit)

### Weight Validation Errors

**Symptom:**
```
ERROR: Weights must sum to 1.0, got 1.30. Adjust weights: {'backend': 0.7, 'frontend': 0.3, 'mobile': 0.2, 'desktop': 0.1}
```

**Cause:** Custom weights don't sum to 1.0 (floating point tolerance: 0.99-1.01).

**Solution:**
1. **Adjust weights** to sum to 1.0:
   ```bash
   # Wrong (sums to 1.3)
   --weights backend=0.7,frontend=0.3,mobile=0.2,desktop=0.1

   # Correct (sums to 1.0)
   --weights backend=0.35,frontend=0.40,mobile=0.15,desktop=0.10
   ```
2. **Use calculator** to verify sum:
   ```python
   weights = {"backend": 0.35, "frontend": 0.40, "mobile": 0.15, "desktop": 0.10}
   print(sum(weights.values()))  # Should print 1.0
   ```
3. **Document rationale** if deviating from default weights

### JSON Parse Errors

**Symptom:**
```
ERROR: Invalid backend coverage schema: missing 'totals' key
ERROR: Error loading backend coverage: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)
```

**Cause:** Coverage file corrupted, wrong format, or truncated.

**Solution:**
1. **Re-run platform tests** to regenerate coverage:
   ```bash
   # Backend
   cd backend
   pytest --cov=core --cov-report=json:tests/coverage_reports/metrics/coverage.json

   # Frontend
   cd frontend-nextjs
   npm test -- --coverage --watchAll=false

   # Mobile
   cd mobile
   npm test -- --coverage

   # Desktop
   cd frontend-nextjs/src-tauri
   cargo tarpaulin --out Json --output-dir coverage
   ```
2. **Verify file format** matches expected schema (see Coverage File Formats section)
3. **Check file size** (should be >100 bytes, not 0 bytes):
   ```bash
   ls -la backend/tests/coverage_reports/metrics/coverage.json
   ```
4. **Review test logs** for errors during coverage generation

### CI/CD Integration Issues

**Symptom:**
```
ERROR: Backend coverage file not found: coverage-artifacts/backend-coverage/coverage.json
```

**Cause:** Artifact upload failed or artifact names don't match download patterns.

**Solution:**
1. **Verify artifact upload** in platform-specific jobs:
   ```yaml
   - name: Upload backend coverage
     uses: actions/upload-artifact@v4
     with:
       name: backend-coverage  # Must match download pattern
       path: backend/tests/coverage_reports/metrics/coverage.json
   ```
2. **Verify artifact download** in aggregate job:
   ```yaml
   - name: Download all coverage artifacts
     uses: actions/download-artifact@v4
     with:
       pattern: '*-coverage'  # Must match upload names
       path: coverage-artifacts
   ```
3. **Check artifact retention** (should be 30 days):
   ```yaml
   - uses: actions/upload-artifact@v4
     with:
       retention-days: 30
   ```
4. **Use `if: always()`** to ensure aggregate job runs even if platform tests fail:
   ```yaml
   aggregate-coverage:
     needs: [backend-tests, frontend-tests, mobile-tests, desktop-tests]
     if: always()  # Run even if some platform tests fail
   ```

### Platform-Specific Issues

**Backend (pytest):**
- **Issue:** Coverage includes test files
- **Fix:** Add `--cov-context=test` or exclude tests in `.coveragerc`:
  ```ini
  [run]
  omit = tests/*
  ```

**Frontend (Jest):**
- **Issue:** Coverage includes node_modules
- **Fix:** Update `jest.config.js`:
  ```javascript
  collectCoverageFrom: [
    'src/**/*.{ts,tsx}',
    '!src/**/*.d.ts',
    '!src/**/*.stories.tsx',
    '!node_modules/**'
  ]
  ```

**Mobile (jest-expo):**
- **Issue:** Coverage includes expo modules
- **Fix:** Use `--collectCoverageFrom` flag:
  ```bash
  npm test -- --coverage --collectCoverageFrom="src/**/*.{ts,tsx}"
  ```

**Desktop (tarpaulin):**
- **Issue:** Linking errors on macOS x86_64
- **Fix:** Use CI/CD workflow (ubuntu-latest runner) for accurate coverage:
  ```bash
  gh workflow run desktop-coverage.yml
  ```

## CI/CD Integration

### Workflow: cross-platform-coverage.yml

**Location:** `.github/workflows/cross-platform-coverage.yml`

**Triggers:**
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop`
- Manual trigger via `workflow_dispatch`

**Jobs:**

1. **backend-tests** - Run pytest with coverage
   - Generates `coverage.json`
   - Uploads `backend-coverage` artifact

2. **frontend-tests** - Run Jest with coverage
   - Generates `coverage-final.json`
   - Uploads `frontend-coverage` artifact

3. **mobile-tests** - Run jest-expo with coverage
   - Generates `coverage-final.json`
   - Uploads `mobile-coverage` artifact

4. **desktop-tests** - Run cargo tarpaulin
   - Generates `coverage.json`
   - Uploads `desktop-coverage` artifact

5. **aggregate-coverage** - Download all artifacts and run enforcement
   - Downloads all `*-coverage` artifacts
   - Runs `cross_platform_coverage_gate.py`
   - Runs `update_cross_platform_trending.py`
   - Posts PR comment with platform breakdown
   - Fails build if any platform below threshold (main branch only)
   - Uploads `cross_platform_summary.json` artifact

### Artifact Retention

All coverage artifacts are retained for 30 days:

```yaml
- uses: actions/upload-artifact@v4
  with:
    retention-days: 30
```

This allows historical trend tracking and manual inspection.

### PR Comments

The aggregate job posts a PR comment with:

- **Platform breakdown table** with coverage percentages
- **Threshold pass/fail status** (✓ or ✗)
- **Trend indicators** (↑↓→) showing change from previous commit
- **Weighted overall score** with weight distribution
- **Gap analysis** (how much each platform is above/below threshold)
- **Remediation steps** (which files to test)

**Example PR Comment:**

```markdown
## Cross-Platform Coverage Report

| Platform | Coverage | Threshold | Status | Trend |
|----------|----------|-----------|--------|-------|
| Backend | 75.00% | 70.00% | ✓ | ↑ 2.5% |
| Frontend | 82.50% | 80.00% | ✓ | → 0.0% |
| Mobile | 55.00% | 50.00% | ✓ | ↑ 5.0% |
| Desktop | 45.00% | 40.00% | ✓ | ↓ 1.5% |

**Weighted Overall:** 72.38% (backend: 35%, frontend: 40%, mobile: 15%, desktop: 10%)

All platforms passed minimum thresholds ✓

### Gap Analysis

- Backend: +5.00% above threshold ✓
- Frontend: +2.50% above threshold ✓
- Mobile: +5.00% above threshold ✓
- Desktop: +5.00% above threshold ✓

### Trend Analysis

- Backend: ↑ 2.5% (72.5% → 75.0%)
- Frontend: → 0.0% (82.5% → 82.5%)
- Mobile: ↑ 5.0% (50.0% → 55.0%)
- Desktop: ↓ 1.5% (46.5% → 45.0%)

### Remediation

No immediate action required. All platforms meet minimum thresholds.

<details>
<summary>Historical Trends (Last 7 Commits)</summary>

| Commit | Backend | Frontend | Mobile | Desktop | Overall |
|-------|---------|----------|--------|---------|---------|
| abc123 | 75.0% | 82.5% | 55.0% | 45.0% | 72.4% |
| def456 | 72.5% | 82.5% | 50.0% | 46.5% | 70.6% |
| ...
</details>
```

### Enforcement Modes

**Pull Requests (Warnings Only):**
```yaml
- name: Enforce coverage thresholds
  if: github.event_name == 'pull_request'
  run: |
    python cross_platform_coverage_gate.py --format text
    # Exit code ignored, warnings only
```

**Main Branch (Strict Enforcement):**
```yaml
- name: Enforce coverage thresholds
  if: github.ref == 'refs/heads/main'
  run: |
    python cross_platform_coverage_gate.py --strict --format text
    # Exit code 1 causes build failure
```

This allows development flexibility on PRs while ensuring main branch quality.

## Trend Tracking

### Script: update_cross_platform_trending.py

**Location:** `backend/tests/scripts/update_cross_platform_trending.py`

**Purpose:** Track historical coverage trends over time with regression detection.

**Usage:**
```bash
# Update trends (automatic in CI/CD)
python update_cross_platform_trending.py \
  --coverage-json cross_platform_summary.json \
  --trend-json cross_platform_trend.json

# View trend summary
python update_cross_platform_trending.py \
  --trend-json cross_platform_trend.json \
  --summary
```

**Storage:** `backend/tests/coverage_reports/metrics/cross_platform_trend.json`

**Retention:** 30 days of historical data

**Metrics Tracked:**
- Per-platform coverage over time (backend, frontend, mobile, desktop)
- Weighted overall score over time
- Trend deltas (current vs. previous, 7-period average)
- Commit SHA and branch for traceability
- Timestamp for each entry

### Trend Indicators

The system computes trend indicators based on change magnitude:

| Indicator | Condition | Meaning |
|-----------|-----------|---------|
| **↑** | Change > +1.0% | Significant increase |
| **↓** | Change < -1.0% | Significant decrease |
| **→** | -1.0% ≤ Change ≤ +1.0% | Stable |

**Example:**
```
Backend: 75.0% ↑ 2.5% (previous: 72.5%, 7-period avg: 73.2%)
```

### Multi-Period Comparison

Trend tracking supports two comparison modes:

1. **1-period delta** (current vs. previous commit)
   - Fast feedback on recent changes
   - Sensitive to short-term fluctuations

2. **7-period delta** (current vs. 7-commit average)
   - Smooths out noise
   - Detects sustained trends
   - Better for long-term analysis

### Regression Detection

The system flags regressions when:

- Coverage decreases by >1% (↓ indicator)
- 7-period average is decreasing (sustained regression)
- Platform falls below threshold (threshold breach)

**Example regression warning:**
```
⚠️ REGRESSION DETECTED: Desktop coverage decreased 3.0% (46.5% → 43.5%)
Previous: 46.5%, 7-period avg: 45.2%, Current: 43.5%
```

### Manual Trend Analysis

View historical trends outside of CI/CD:

```bash
# Load trend data
python -c "
import json
with open('backend/tests/coverage_reports/metrics/cross_platform_trend.json') as f:
    trends = json.load(f)

for entry in trends[-10:]:  # Last 10 entries
    print(f\"{entry['timestamp']}: Backend {entry['backend']:.1f}%\")
"

# Compute average coverage over last N commits
python -c "
import json
with open('backend/tests/coverage_reports/metrics/cross_platform_trend.json') as f:
    trends = json.load(f)

last_7 = trends[-7:]
avg_backend = sum(t['backend'] for t in last_7) / len(last_7)
print(f'Average backend coverage (last 7): {avg_backend:.1f}%')
"
```

## Best Practices

### 1. Run Locally Before Pushing

Catch coverage gaps early by running the gate script locally:

```bash
# Run all platform tests
cd backend && pytest --cov=core --cov-report=json && cd ..
cd frontend-nextjs && npm test -- --coverage && cd ..
cd mobile && npm test -- --coverage && cd ..
cd frontend-nextjs/src-tauri && cargo tarpaulin --out Json && cd ../..

# Generate cross-platform report
python backend/tests/scripts/cross_platform_coverage_gate.py --format text
```

This prevents CI failures and provides faster feedback.

### 2. Focus on High-Impact Files First

Prioritize testing efforts using the **coverage gap × business impact** formula:

```
Priority = (100% - current_coverage) × business_impact_weight

Business Impact Weights:
- CRITICAL: 3x (governance, episodic memory, LLM services)
- HIGH: 2x (API endpoints, core services)
- MEDIUM: 1x (UI components, utilities)
- LOW: 0.5x (minor features, config)
```

**Example:**
- `agent_governance_service.py`: (100% - 26%) × 3x = 222 priority
- `Button.tsx`: (100% - 90%) × 1x = 10 priority

Test `agent_governance_service.py` first.

### 3. Use Platform-Specific Test Strategies

Different platforms require different testing approaches:

**Backend (Python):**
- Unit tests for service layer logic
- Integration tests for database operations
- Property tests for algorithmic correctness
- Contract tests for API endpoints

**Frontend (React):**
- Component tests for UI logic
- Integration tests for data fetching
- Accessibility tests for WCAG compliance
- E2E tests for user workflows

**Mobile (React Native):**
- Platform-specific tests (iOS vs Android)
- Device capability tests (Camera, Location, Notifications)
- Navigation tests for screen transitions
- Mock tests for native modules

**Desktop (Rust):**
- Unit tests for command logic
- Platform-specific tests (Windows/macOS/Linux)
- IPC tests for Tauri commands
- System integration tests for file dialogs, tray

### 4. Monitor Trends to Detect Regressions Early

Review trend indicators in PR comments:

- **↑ (Increase)**: Coverage improving, good direction
- **→ (Stable)**: Coverage stable, acceptable
- **↓ (Decrease)**: Coverage regressing, investigate immediately

**Example regression response:**
```bash
# Revert commit that caused regression
git revert abc123

# Add tests for deleted code
git checkout abc123~1  # Before regression
# Write tests for uncovered code
git checkout main  # Back to main
# Re-apply tests with proper coverage
```

### 5. Adjust Thresholds Incrementally

Start with achievable targets and increase gradually:

```
Phase 146: 70/80/50/40 (current targets)
Phase 147: 75/85/55/45 (+5% each)
Phase 148: 80/90/60/50 (+5% each)
```

This maintains morale while improving quality.

### 6. Document Rationale for Custom Weights/Thresholds

If deviating from defaults, document why:

```bash
git commit -m "
feat: temporarily lower mobile threshold to 40%

Rationale: Mobile test infrastructure migration in progress
(jest-expo to vitest). Expected completion: Phase 147.
Temporary threshold prevents blocking frontend/backend progress.
"
```

This provides context for future reviewers.

## Related Documentation

- **FRONTEND_COVERAGE.md** - Frontend-specific coverage strategies and patterns
- **DESKTOP_COVERAGE.md** - Desktop Tauri coverage patterns and platform-specific tests
- **ROADMAP.md** - Phase 146 completion status and handoff to Phase 147
- **146-RESEARCH.md** - Technical research and rationale for weighted coverage system
- **cross_platform_coverage_gate.py** - Main enforcement script implementation
- **update_cross_platform_trending.py** - Trend tracking script implementation
- **cross-platform-coverage.yml** - GitHub Actions workflow configuration

## Quick Reference

**File Locations:**
- Enforcement script: `backend/tests/scripts/cross_platform_coverage_gate.py`
- Trend tracking: `backend/tests/scripts/update_cross_platform_trending.py`
- Trend storage: `backend/tests/coverage_reports/metrics/cross_platform_trend.json`
- CI/CD workflow: `.github/workflows/cross-platform-coverage.yml`

**Default Thresholds:**
- Backend: ≥70%
- Frontend: ≥80%
- Mobile: ≥50%
- Desktop: ≥40%

**Default Weights:**
- Backend: 35%
- Frontend: 40%
- Mobile: 15%
- Desktop: 10%

**Exit Codes:**
- 0: Success
- 1: Threshold failure
- 2: Execution error

**Support:**
- Issues: `backend/tests/scripts/cross_platform_coverage_gate.py`
- Documentation: `docs/CROSS_PLATFORM_COVERAGE.md`
- Phase 146 Plans: `.planning/phases/146-cross-platform-weighted-coverage/`

---

**Phase:** 146 - Cross-Platform Weighted Coverage
**Status:** Complete (2026-03-06)
**Next:** Phase 147 - Cross-Platform Property Testing
