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

## See Also

- [Testing Documentation Index](TESTING_INDEX.md) - Central hub for all testing documentation
- [Testing Onboarding Guide](testing/onboarding.md) - 15-minute quick start for all platforms
- [Property Testing Patterns](testing/property-testing.md) - Shared property test infrastructure
- [E2E Testing Guide](testing/e2e-guide.md) - Cross-platform E2E orchestration
# Cross-Platform Property Testing Guide

## Overview

Atom is a multi-platform AI automation platform with four distinct codebases: **Backend** (Python/FastAPI), **Frontend** (React/Next.js), **Mobile** (React Native), and **Desktop** (Tauri/Rust). This guide explains the cross-platform property-based testing framework that validates critical invariants across all platforms.

**What is Property-Based Testing?**
Property-based testing (PBT) is a testing approach where you specify *invariants* (properties that must always be true) and the testing framework generates hundreds of random inputs to verify those properties. Unlike example-based testing (specific inputs), PBT finds edge cases you wouldn't think to test.

**Why Cross-Platform Property Testing?**
- **Unified invariants**: Canvas state, agent maturity, and data serialization behave identically across platforms
- **Bug discovery**: Random generation finds edge cases that traditional tests miss
- **Regression prevention**: Properties catch breaking changes across refactors
- **Confidence**: 100+ test cases per property provide stronger guarantees than manual examples

**Frameworks:**
- **FastCheck 4.5.3**: Property-based testing for TypeScript/React Native (frontend, mobile)
- **proptest 1.0**: Property-based testing for Rust (desktop)

**Success Metrics:**
- **12 shared properties** across 3 invariant modules (canvas, agent maturity, serialization)
- **3 platforms** running property tests (frontend Next.js, mobile React Native, desktop Rust)
- **Unified reporting** with platform breakdown and historical trend tracking

**Phase:** 147 - Cross-Platform Property Testing (Complete)
**Status:** Operational in CI/CD

## Quick Start

### Local Execution

Run property tests on all platforms:

```bash
# 1. Frontend (Next.js)
cd frontend-nextjs
npm test -- tests/property/shared-invariants.test.ts

# 2. Mobile (React Native)
cd mobile
npm test -- shared-invariants

# 3. Desktop (Rust/Tauri)
cd frontend-nextjs/src-tauri
cargo test property_tests

# 4. Aggregate results (optional)
python3 backend/tests/scripts/aggregate_property_tests.py \
  --frontend coverage/jest-frontend-property-results.json \
  --mobile coverage/jest-mobile-property-results.json \
  --desktop coverage/proptest-results.json \
  --format text
```

### CI/CD Execution

Property tests run automatically on push/PR to main branch. See `.github/workflows/cross-platform-property-tests.yml` for workflow configuration.

```bash
# Manual trigger (requires GitHub CLI)
gh workflow run cross-platform-property-tests.yml

# View results
gh run list --workflow=cross-platform-property-tests.yml
gh run view [run-id]
```

### Expected Output

```
✓ canvas state machine properties (9 tests)
✓ agent maturity properties (10 tests)
✓ serialization roundtrip properties (13 tests)

Test Suites: 1 passed, 1 total
Tests:       32 passed, 32 total
```

## Architecture

### Components

The cross-platform property testing system consists of three core components:

1. **Shared Property Tests** (`frontend-nextjs/shared/property-tests/`)
   - Common invariants defined once, shared across platforms
   - 3 modules: canvas-invariants.ts, agent-maturity-invariants.ts, serialization-invariants.ts
   - FastCheck arbitraries for random generation (fc.integer(), fc.string(), etc.)

2. **Platform Test Runners**
   - **Frontend**: `frontend-nextjs/tests/property/shared-invariants.test.ts` (imports from @atom/property-tests)
   - **Mobile**: `mobile/src/__tests__/property/shared-invariants.test.ts` (imports via SYMLINK)
   - **Desktop**: `frontend-nextjs/src-tauri/tests/state_machine_proptest.rs` (correspondence documented in README)

3. **Aggregation Infrastructure** (Phase 147-03)
   - `backend/tests/scripts/aggregate_property_tests.py`: Combines FastCheck + proptest results
   - `.github/workflows/cross-platform-property-tests.yml`: 4 CI/CD jobs (3 parallel + 1 aggregate)
   - `backend/tests/coverage_reports/metrics/property_test_results.json`: Historical tracking

### SYMLINK Strategy (Phase 144)

Mobile app shares property tests via SYMLINK to avoid duplication:

```bash
mobile/src/shared/property-tests → ../../frontend-nextjs/shared/property-tests
```

Benefits:
- **Single source of truth**: Properties defined once in frontend
- **No duplication**: Changes automatically apply to mobile
- **Consistent testing**: Both platforms run identical invariants

Verification:
```bash
ls -la mobile/src/shared/property-tests
# lrwxr-xr-x  1 user  staff  64 Mar  6 18:55 property-tests -> ../../frontend-nextjs/shared/property-tests
```

### Rust Correspondence (Desktop)

Desktop Rust tests don't use SYMLINK (different language). Instead, correspondence is documented in `frontend-nextjs/src-tauri/tests/property_tests/README.md`:

```
TypeScript Property                | Rust Property
-----------------------------------|-----------------------------------
canvasStateMachineProperty         | test_canvas_state_machine_invariants
maturityMonotonicProgression       | test_agent_maturity_monotonic
jsonRoundtripPreservesData         | proptest_json_roundtrip
```

Rust tests use proptest macros with equivalent invariants, adapted to Rust type system.

### Aggregation Flow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Frontend      │     │    Mobile       │     │    Desktop      │
│  (FastCheck)    │     │  (FastCheck)    │     │  (proptest)     │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                      │                        │
         │ Jest JSON            │ Jest JSON              │ cargo test
         │ output               │ output                 │ output (formatter)
         │                      │                        │
         └──────────────────────┴────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │  Aggregation Script   │
                    │ (aggregate_property_) │
                    │   tests.py            │
                    └───────────┬───────────┘
                                │
                    ┌───────────┴───────────┐
                    │   PR Comment          │
                    │   Platform Breakdown  │
                    │   Historical Trends   │
                    └───────────────────────┘
```

## Property Library

### Canvas State Invariants (9 properties)

**Module**: `shared/property-tests/canvas-invariants.ts`

Canvas presentation state machine properties:

| Property | Description | Arbitrary | Test Cases |
|----------|-------------|-----------|------------|
| `canvasStateMachineProperty` | All transitions respect state machine rules | fc.boolean(), fc.string() | 100+ |
| `canvasNoDirectPresentingToIdle` | Cannot skip from PRESENTING to IDLE | fc.array(fc.string()) | 100+ |
| `canvasErrorRecoveryToIdle` | ERROR state recovers to IDLE | fc.string() | 100+ |
| `canvasTerminalStatesLeadToIdle` | CLOSED/COMPLETED lead to IDLE | fc.string() | 100+ |
| `canvasIdleToPresenting` | IDLE transitions to PRESENTING | fc.string() | 100+ |
| `canvasPresentingTransitions` | PRESENTING state transitions valid | fc.string(), fc.boolean() | 100+ |
| `canvasErrorStateRecoverability` | ERROR state is recoverable | fc.string() | 100+ |
| `canvasNoTerminalStateLoops` | Terminal states don't loop | fc.string() | 100+ |
| `canvasStateSequenceValidity` | State sequences are valid | fc.array(fc.string()) | 100+ |

**Example:**
```typescript
export const canvasNoDirectPresentingToIdle = fc.property(
  fc.array(fc.string()), // Canvas actions
  (actions) => {
    const stateMachine = new CanvasStateMachine();
    let currentState = CanvasState.IDLE;

    for (const action of actions) {
      const previousState = currentState;
      currentState = stateMachine.transition(currentState, action);

      // Invariant: Cannot transition directly from PRESENTING to IDLE
      if (previousState === CanvasState.PRESENTING && currentState === CanvasState.IDLE) {
        throw new Error('Invalid transition: PRESENTING → IDLE');
      }
    }

    return true;
  }
);
```

### Agent Maturity Invariants (10 properties)

**Module**: `shared/property-tests/agent-maturity-invariants.ts`

Agent maturity level state machine properties:

| Property | Description | Arbitrary | Test Cases |
|----------|-------------|-----------|------------|
| `maturityMonotonicProgression` | Maturity only increases (STUDENT → INTERN → SUPERVISED → AUTONOMOUS) | fc.array(fc.string()) | 100+ |
| `autonomousIsTerminal` | AUTONOMOUS is terminal state | fc.string() | 100+ |
| `studentCannotSkipToAutonomous` | STUDENT cannot skip to AUTONOMOUS | fc.array(fc.string()) | 100+ |
| `maturityTransitionsAreForward` | All transitions move forward | fc.string(), fc.string() | 100+ |
| `maturityOrderConsistency` | Order is preserved across transitions | fc.array(fc.string()) | 100+ |
| `maturityGraduationPath` | Graduation follows defined path | fc.array(fc.string()) | 100+ |
| `maturityNoBackwardTransitions` | No backward transitions allowed | fc.string(), fc.string() | 100+ |
| `maturityLevelUniqueness` | Each maturity level is unique | fc.constantFrom() | 4 |
| `maturityTerminalStateUniqueness` | Only AUTONOMOUS is terminal | fc.string() | 100+ |

**Example:**
```typescript
export const maturityMonotonicProgression = fc.property(
  fc.array(fc.string()), // Maturity transitions
  (transitions) => {
    const stateMachine = new AgentMaturityStateMachine();
    let currentLevel = MaturityLevel.STUDENT;
    const levels = [MaturityLevel.STUDENT, MaturityLevel.INTERN, MaturityLevel.SUPERVISED, MaturityLevel.AUTONOMOUS];

    for (const transition of transitions) {
      const previousLevel = currentLevel;
      currentLevel = stateMachine.transition(currentLevel, transition);

      // Invariant: Maturity only increases (ordinal value)
      if (levels.indexOf(currentLevel) < levels.indexOf(previousLevel)) {
        throw new Error('Maturity cannot decrease');
      }
    }

    return true;
  }
);
```

### Serialization Invariants (13 properties)

**Module**: `shared/property-tests/serialization-invariants.ts`

JSON serialization roundtrip properties:

| Property | Description | Arbitrary | Test Cases |
|----------|-------------|-----------|------------|
| `jsonRoundtripPreservesData` | JSON stringify/parse preserves data | fc.anything() | 100+ |
| `agentDataRoundtrip` | Agent data serializes correctly | fc.agentData() | 100+ |
| `canvasDataRoundtrip` | Canvas data serializes correctly | fc.canvasData() | 100+ |
| `arrayOrderPreserved` | Array order preserved | fc.array(fc.integer()) | 100+ |
| `nullAndUndefinedHandling` | null/undefined handled correctly | fc.option(fc.string()) | 100+ |
| `dateSerialization` | Date serialization preserves timestamp | fc.date() | 100+ |
| `nestedObjectSerialization` | Nested objects preserved | fc.dictionary() | 100+ |
| `specialCharactersInStrings` | Special characters preserved | fc.string() | 100+ |
| `numberPrecisionPreservation` | Number precision preserved | fc.float() | 100+ |
| `booleanSerialization` | Boolean values preserved | fc.boolean() | 100+ |
| `emptyValuesHandling` | Empty arrays/objects preserved | fc.oneof() | 100+ |

**Example:**
```typescript
export const jsonRoundtripPreservesData = fc.property(
  fc.anything(), // Arbitrary JSON-compatible data
  (data) => {
    const serialized = JSON.stringify(data);
    const deserialized = JSON.parse(serialized);

    // Invariant: Roundtrip preserves data
    assertDeepEqual(data, deserialized);
    return true;
  }
);

// Custom arbitrary for agent data
const fcAgentData = fc.record({
  id: fc.uuid(),
  name: fc.string(),
  maturityLevel: fc.constantFrom('STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'),
  capabilities: fc.array(fc.string()),
  createdAt: fc.date(),
});
```

### Total Property Count

- **Canvas invariants**: 9 properties
- **Agent maturity invariants**: 10 properties
- **Serialization invariants**: 13 properties
- **Total**: 32 shared properties

Each property runs 100+ random test cases, generating **3,200+ test cases** per platform.

## Platform-Specific Guides

### Frontend (Next.js)

**Test Runner**: Jest with ts-jest
**Property Framework**: FastCheck 4.5.3
**Test Location**: `frontend-nextjs/tests/property/shared-invariants.test.ts`

**Configuration** (`frontend-nextjs/jest.config.js`):
```javascript
module.exports = {
  testMatch: [
    // Shared property tests (Phase 147)
    "<rootDir>/shared/property-tests/**/*.ts",
    // Standard test files
    "<rootDir>/tests/**/*.test.(ts|tsx|js)",
    // ... more patterns
  ],
  moduleNameMapper: {
    "^@atom/property-tests(.*)$": "<rootDir>/shared/property-tests$1",
  },
};
```

**Running Tests**:
```bash
# Run all property tests
cd frontend-nextjs
npm test -- tests/property/shared-invariants.test.ts

# Run with verbose output
npm test -- tests/property/shared-invariants.test.ts --verbose

# Run specific property
npm test -- tests/property/shared-invariants.test.ts -t "canvas state machine"
```

**Import Pattern**:
```typescript
import fc from 'fast-check';
import { describe, it, expect } from '@jest/globals';
import {
  canvasStateMachineProperty,
  maturityMonotonicProgression,
  jsonRoundtripPreservesData,
} from '@atom/property-tests';

describe('Canvas State Invariants', () => {
  it('should respect state machine transitions', () => {
    fc.assert(canvasStateMachineProperty);
  });
});
```

### Mobile (React Native)

**Test Runner**: Jest with jest-expo
**Property Framework**: FastCheck 4.5.3 (via SYMLINK)
**Test Location**: `mobile/src/__tests__/property/shared-invariants.test.ts`

**SYMLINK Setup** (Phase 144):
```bash
# Create SYMLINK (already done)
cd mobile/src/shared
ln -s ../../frontend-nextjs/shared/property-tests property-tests
```

**Verification**:
```bash
# Check SYMLINK exists
ls -la mobile/src/shared/property-tests

# Verify it points to correct location
readlink mobile/src/shared/property-tests
# Output: ../../frontend-nextjs/shared/property-tests
```

**Configuration** (`mobile/jest.config.js`):
```javascript
module.exports = {
  testMatch: [
    // Shared property tests (Phase 147)
    "<rootDir>/src/shared/property-tests/**/*.ts",
    // Standard test files
    "<rootDir>/src/**/__tests__/**/*.test.(ts|tsx)",
    // ... more patterns
  ],
  moduleNameMapper: {
    "^@atom/property-tests(.*)$": "<rootDir>/src/shared/property-tests$1",
  },
};
```

**Running Tests**:
```bash
# Run all property tests
cd mobile
npm test -- shared-invariants

# Run with verbose output
npm test -- shared-invariants --verbose
```

**Import Pattern** (same as frontend):
```typescript
import fc from 'fast-check';
import { canvasStateMachineProperty } from '@atom/property-tests';
// ... same test code
```

### Desktop (Tauri-Rust)

**Test Runner**: cargo test
**Property Framework**: proptest 1.0
**Test Location**: `frontend-nextjs/src-tauri/tests/state_machine_proptest.rs`

**Correspondence Documentation** (`README.md`):
```markdown
# Property Tests Correspondence

This document maps TypeScript properties to Rust proptests.

## Canvas State Properties

| TypeScript Property | Rust Property | Notes |
|---------------------|---------------|-------|
| canvasStateMachineProperty | test_canvas_state_machine_invariants | Equivalent state machine rules |
| canvasNoDirectPresentingToIdle | test_no_direct_presenting_to_idle | Same invariant |

## Agent Maturity Properties

| TypeScript Property | Rust Property | Notes |
|---------------------|---------------|-------|
| maturityMonotonicProgression | test_agent_maturity_monotonic | Ordinal comparison |
| autonomousIsTerminal | test_autonomous_is_terminal | Terminal state check |
```

**Configuration** (`Cargo.toml`):
```toml
[dev-dependencies]
proptest = "1.0"
serde_json = "1.0"
```

**Running Tests**:
```bash
# Run all property tests
cd frontend-nextjs/src-tauri
cargo test property_tests

# Run specific property
cargo test test_canvas_state_machine_invariants

# Run with output
cargo test property_tests -- --nocapture
```

**Example (Rust proptest)**:
```rust
use proptest::prelude::*;

proptest! {
  #[test]
  fn test_canvas_state_machine_invariants(
    actions in prop::collection::vec(".*", 0..10)
  ) {
    let mut state_machine = CanvasStateMachine::new();
    let mut current_state = CanvasState::Idle;

    for action in actions {
      let previous_state = current_state;
      current_state = state_machine.transition(current_state, &action);

      // Invariant: Cannot transition directly from Presenting to Idle
      if previous_state == CanvasState::Presenting && current_state == CanvasState::Idle {
        panic!("Invalid transition: Presenting → Idle");
      }
    }
  }
}
```

## CI/CD Integration

### Workflow Overview

**File**: `.github/workflows/cross-platform-property-tests.yml`

**Jobs** (4 jobs: 3 parallel + 1 sequential):

#### Job 1: Frontend Property Tests
```yaml
frontend-property-tests:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-node@v3
      with:
        node-version: '20'
        cache: 'npm'
        cache-dependency-path: frontend-nextjs/package-lock.json
    - name: Install dependencies
      run: cd frontend-nextjs && npm ci
    - name: Run property tests
      run: |
        cd frontend-nextjs
        npm test -- tests/property/shared-invariants.test.ts --ci --json \
          --outputFile=coverage/jest-frontend-property-results.json
    - name: Upload results
      uses: actions/upload-artifact@v3
      with:
        name: jest-frontend-property-results
        path: frontend-nextjs/coverage/jest-frontend-property-results.json
        retention-days: 7
```

#### Job 2: Mobile Property Tests
```yaml
mobile-property-tests:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-node@v3
      with:
        node-version: '20'
        cache: 'npm'
        cache-dependency-path: mobile/package-lock.json
    - name: Install dependencies
      run: cd mobile && npm ci
    - name: Run property tests
      run: |
        cd mobile
        npm test -- shared-invariants --ci --json \
          --outputFile=coverage/jest-mobile-property-results.json
    - name: Upload results
      uses: actions/upload-artifact@v3
      with:
        name: jest-mobile-property-results
        path: mobile/coverage/jest-mobile-property-results.json
        retention-days: 7
```

#### Job 3: Desktop Property Tests
```yaml
desktop-property-tests:
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v3
    - uses: actions-rs/toolchain@v1
      with:
        toolchain: stable
        cache: true
    - name: Run property tests
      run: |
        cd frontend-nextjs/src-tauri
        cargo test property_tests 2>&1 | tee proptest-output.txt
    - name: Format results
      run: |
        python3 tests/proptest_formatter.py \
          --input proptest-output.txt \
          --output proptest-results.json
    - name: Upload results
      uses: actions/upload-artifact@v3
      with:
        name: proptest-results
        path: frontend-nextjs/src-tauri/coverage/proptest-results.json
        retention-days: 7
```

#### Job 4: Aggregate Results
```yaml
aggregate-results:
  needs: [frontend-property-tests, mobile-property-tests, desktop-property-tests]
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v3
    - name: Download all artifacts
      uses: actions/download-artifact@v3
      with:
        path: artifacts
    - name: Run aggregation script
      run: |
        python3 backend/tests/scripts/aggregate_property_tests.py \
          --frontend artifacts/jest-frontend-property-results/jest-frontend-property-results.json \
          --mobile artifacts/jest-mobile-property-results/jest-mobile-property-results.json \
          --desktop artifacts/proptest-results/proptest-results.json \
          --output property_test_results.json \
          --format json
    - name: Upload aggregated results
      uses: actions/upload-artifact@v3
      with:
        name: property-test-results
        path: property_test_results.json
        retention-days: 30
    - name: Update historical tracking
      run: |
        # Merge with backend/tests/coverage_reports/metrics/property_test_results.json
        # Keep last 30 runs for trend analysis
    - name: Post PR comment
      uses: actions/github-script@v6
      if: github.event_name == 'pull_request'
      with:
        script: |
          const fs = require('fs');
          const results = JSON.parse(fs.readFileSync('property_test_results.json', 'utf8'));
          const markdown = generatePRComment(results);
          github.rest.issues.createComment({
            issue_number: context.issue.number,
            owner: context.repo.owner,
            repo: context.repo.repo,
            body: markdown
          });
```

### PR Comment Format

```markdown
## 🧪 Property Test Results

**Platform Breakdown:**

| Platform | Total | Passed | Failed | Pass Rate |
|----------|-------|--------|--------|-----------|
| Frontend | 32 | 32 | 0 | 100% ✅ |
| Mobile | 32 | 32 | 0 | 100% ✅ |
| Desktop | 27 | 27 | 0 | 100% ✅ |
| **Total** | **91** | **91** | **0** | **100%** |

**Trends:** Frontend ↑ 2% | Mobile → | Desktop ↓ 1%

**Details:**
- All canvas state invariants passed (9/9)
- All agent maturity invariants passed (10/10)
- All serialization invariants passed (13/13)
```

### Historical Tracking

**File**: `backend/tests/coverage_reports/metrics/property_test_results.json`

```json
{
  "total": 91,
  "passed": 91,
  "failed": 0,
  "pass_rate": 100.0,
  "platforms": {
    "frontend": {"total": 32, "passed": 32, "failed": 0},
    "mobile": {"total": 32, "passed": 32, "failed": 0},
    "desktop": {"total": 27, "passed": 27, "failed": 0}
  },
  "timestamp": "2026-03-06T10:30:00Z",
  "history": [
    {"timestamp": "2026-03-05T10:00:00Z", "pass_rate": 98.9},
    {"timestamp": "2026-03-04T10:00:00Z", "pass_rate": 97.8},
    // ... last 30 runs
  ]
}
```

Trend indicators (↑↓→) calculated from last 3 runs in history array.

## Property Testing Patterns

### State Machine Invariants

**Pattern**: Test all valid state transitions and reject invalid ones.

**Example (Canvas State)**:
```typescript
// Valid: IDLE → PRESENTING → CLOSED → IDLE
// Invalid: IDLE → CLOSED (missing PRESENTING)

export const canvasStateMachineProperty = fc.property(
  fc.array(fc.string()), // Random action sequence
  (actions) => {
    const stateMachine = new CanvasStateMachine();
    let currentState = CanvasState.IDLE;

    for (const action of actions) {
      const previousState = currentState;
      currentState = stateMachine.transition(currentState, action);

      // Check all transition rules
      assertValidTransition(previousState, currentState, action);
    }

    return true;
  }
);
```

**What to test**:
- ✅ All defined transitions work correctly
- ✅ Invalid transitions are rejected
- ✅ Terminal states cannot transition further
- ✅ Recovery paths exist from error states

### Serialization Roundtrips

**Pattern**: Data must survive serialization/deserialization unchanged.

**Example (JSON)**:
```typescript
export const jsonRoundtripPreservesData = fc.property(
  fc.anything(), // Random JSON-compatible data
  (data) => {
    const serialized = JSON.stringify(data);
    const deserialized = JSON.parse(serialized);

    // Deep equality check
    assertDeepEqual(data, deserialized);
    return true;
  }
);
```

**What to test**:
- ✅ All data types serialize correctly (strings, numbers, booleans, null, arrays, objects)
- ✅ Nested structures preserve hierarchy
- ✅ Special characters don't break serialization
- ✅ Dates preserve timestamps (or ISO string format)
- ✅ Precision is maintained (floating-point numbers)

### Monotonic Progression

**Pattern**: Values only increase (or decrease) along a sequence.

**Example (Agent Maturity)**:
```typescript
const MATURITY_LEVELS = ['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'];

export const maturityMonotonicProgression = fc.property(
  fc.array(fc.string()), // Random maturity transitions
  (transitions) => {
    const stateMachine = new AgentMaturityStateMachine();
    let currentLevel = MaturityLevel.STUDENT;

    for (const transition of transitions) {
      const previousLevel = currentLevel;
      currentLevel = stateMachine.transition(currentLevel, transition);

      // Invariant: Maturity only increases
      const previousOrdinal = MATURITY_LEVELS.indexOf(previousLevel);
      const currentOrdinal = MATURITY_LEVELS.indexOf(currentLevel);

      if (currentOrdinal < previousOrdinal) {
        throw new Error(`Maturity decreased: ${previousLevel} → ${currentLevel}`);
      }
    }

    return true;
  }
);
```

**What to test**:
- ✅ Sequence respects ordering (A < B < C < D)
- ✅ No backward transitions allowed
- ✅ Terminal state cannot progress further
- ✅ Skipping levels is blocked (unless explicitly allowed)

### Guards and Constraints

**Pattern**: Certain state transitions are guarded by conditions.

**Example (Canvas Presenting Guard)**:
```typescript
export const canvasNoDirectPresentingToIdle = fc.property(
  fc.array(fc.string()), // Random action sequence
  (actions) => {
    const stateMachine = new CanvasStateMachine();
    let currentState = CanvasState.IDLE;

    for (const action of actions) {
      const previousState = currentState;
      currentState = stateMachine.transition(currentState, action);

      // Guard: Cannot transition directly from PRESENTING to IDLE
      // Must go through CLOSED or COMPLETED first
      if (previousState === CanvasState.PRESENTING && currentState === CanvasState.IDLE) {
        throw new Error('Guard violated: PRESENTING → IDLE (blocked)');
      }
    }

    return true;
  }
);
```

**What to test**:
- ✅ Guards prevent specific transitions
- ✅ Alternative paths exist (guard → intermediate → target)
- ✅ Guards apply consistently regardless of action sequence

## Troubleshooting

### FastCheck Seed Reproduction

**Problem**: Property test failed, but you can't reproduce it locally.

**Solution**: Use the `FASTCHECK_SEED` environment variable.

```bash
# CI/CD output shows: "Error: Property failed after 42 tests, seed: 12345"
# Reproduce locally:

FASTCHECK_SEED=12345 npm test -- tests/property/shared-invariants.test.ts
```

**In code**:
```typescript
// Set global seed (for debugging)
fc.configureGlobal({ seed: 12345 });

// Run single property
fc.assert(canvasStateMachineProperty);
```

### SYMLINK Issues

**Problem**: Mobile tests can't find `@atom/property-tests`.

**Solution**: Verify SYMLINK exists and points to correct location.

```bash
# Check SYMLINK exists
ls -la mobile/src/shared/property-tests

# Expected output:
# lrwxr-xr-x  1 user  staff  64 Mar  6 18:55 property-tests -> ../../frontend-nextjs/shared/property-tests

# If missing, recreate SYMLINK
cd mobile/src/shared
ln -s ../../frontend-nextjs/shared/property-tests property-tests

# Verify relative path
readlink mobile/src/shared/property-tests
# Output: ../../frontend-nextjs/shared/property-tests
```

**Common issues**:
- ❌ SYMLINK points to wrong directory (check relative path)
- ❌ SYMLINK is absolute instead of relative (breaks on other machines)
- ❌ Target directory doesn't exist (verify frontend-nextjs/shared/property-tests)

### Jest Not Finding Tests

**Problem**: `npm test -- shared-invariants` reports "No tests found".

**Solution**: Check `testMatch` pattern in `jest.config.js`.

```javascript
// frontend-nextjs/jest.config.js
module.exports = {
  testMatch: [
    // ✅ Correct: Matches shared property tests
    "<rootDir>/shared/property-tests/**/*.ts",

    // ❌ Wrong: Doesn't match .ts files in shared/
    // "<rootDir>/shared/**/*.test.ts",  // Requires .test.ts extension

    // ❌ Wrong: Doesn't include shared/ directory
    // "<rootDir>/tests/**/*.test.ts",  // Only tests/ directory
  ],
};
```

**Verification**:
```bash
# Check which files Jest matches
cd frontend-nextjs
npx jest --showConfig | grep testMatch

# Run with --debug flag
npx jest shared-invariants --debug
```

### Proptest Failures

**Problem**: Rust proptest failed with obscure error message.

**Solution**: Run `cargo test` with `-- --nocapture` for details.

```bash
# Run proptest with output
cd frontend-nextjs/src-tauri
cargo test test_canvas_state_machine_invariants -- --nocapture

# Output shows:
# [2016-03-06T10:30:00Z INFO  proptest] # Config: proptest
# [2016-03-06T10:30:00Z INFO  proptest] # Tests: 100
# [2016-03-06T10:30:00Z INFO  proptest] # Failures: 1
# [2016-03-06T10:30:00Z INFO  proptest] # Failing input: test_canvas_state_machine_invariants
#     actions = ["present", "idle"]  # Minimal failing case
```

**Reproduce specific case**:
```rust
// Paste failing input into test
#[test]
fn test_reproduce_failure() {
    let actions = vec!["present", "idle"];
    let mut state_machine = CanvasStateMachine::new();
    // ... test logic
}
```

### Module Resolution Errors

**Problem**: `Cannot find module '@atom/property-tests'`.

**Solution**: Check `moduleNameMapper` in `jest.config.js`.

```javascript
// frontend-nextjs/jest.config.js
module.exports = {
  moduleNameMapper: {
    // ✅ Correct: Maps @atom/property-tests to shared/property-tests
    "^@atom/property-tests(.*)$": "<rootDir>/shared/property-tests$1",

    // ❌ Wrong: Missing path alias
    // (no entry for @atom/property-tests)

    // ❌ Wrong: Incorrect capture group syntax
    // "^@atom/property-tests$": "<rootDir>/shared/property-tests",  // No (.*) capture
  },
};
```

**Verification**:
```bash
# Check Jest resolves module correctly
cd frontend-nextjs
node -e "console.log(require.resolve('@atom/property-tests'))"
# Output: /Users/.../frontend-nextjs/shared/property-tests/index.ts
```

### FastCheck API Changes

**Problem**: `fc.jsonObject()` throws "is not a function".

**Solution**: FastCheck 4.5.3 doesn't have `fc.jsonObject()`. Use `fc.anything()` instead.

```typescript
// ❌ Wrong (FastCheck 3.x API)
export const jsonRoundtripPreservesData = fc.property(
  fc.jsonObject(),  // Doesn't exist in FastCheck 4.x
  (data) => { /* ... */ }
);

// ✅ Correct (FastCheck 4.x API)
export const jsonRoundtripPreservesData = fc.property(
  fc.anything(),  // Correct for 4.x
  (data) => { /* ... */ }
);
```

**Check FastCheck version**:
```bash
cd frontend-nextjs
npm list fast-check
# fast-check@4.5.3
```

## Best Practices

### Start with Shared Invariants

**Rule**: Begin with state machine and serialization properties (highest ROI).

**Why**: These catch the most bugs with the least effort.

**Priority order**:
1. **State machines** (canvas state, agent maturity) - High value, easy to write
2. **Serialization** (JSON roundtrips) - Critical for data integrity
3. **Custom business logic** (ordering, pagination) - Medium value
4. **UI behavior** (form validation) - Lower value (use E2E tests)

**Example**:
```typescript
// ✅ Good: Start with state machine invariants
export const canvasStateMachineProperty = fc.property(/* ... */);
export const maturityMonotonicProgression = fc.property(/* ... */);

// ❌ Avoid: Complex UI properties (hard to maintain)
export const formValidationProperty = fc.property(
  fc.record({
    username: fc.string(),
    email: fc.email(),
    password: fc.string(),
  }),
  (formData) => {
    // UI validation logic (better tested with E2E)
  }
);
```

### Use Property Tests for Critical Business Logic

**Rule**: Focus properties on core invariants, not edge cases.

**What to test with properties**:
- ✅ State machine transitions (canvas, agent maturity)
- ✅ Data serialization (JSON roundtrips)
- ✅ Ordering invariants (monotonic progression)
- ✅ Idempotent operations (calling twice = same result)

**What to test with example-based tests**:
- ✅ UI interactions (button clicks, form submissions)
- ✅ API integrations (third-party services)
- ✅ Error messages (user-facing text)

**Example**:
```typescript
// ✅ Good: Property test for state machine
export const canvasStateMachineProperty = fc.property(/* ... */);

// ✅ Good: Example-based test for API integration
test('canvas API returns 404 for invalid canvas ID', async () => {
  const response = await fetch(`/api/canvases/invalid-id`);
  expect(response.status).toBe(404);
});

// ❌ Avoid: Property test for API integration
export const canvasAPIProperty = fc.property(
  fc.string(),
  async (canvasId) => {
    const response = await fetch(`/api/canvases/${canvasId}`);
    // Flaky (network errors, rate limits)
  }
);
```

### Document Correspondence Between Rust and TypeScript

**Rule**: Maintain README.md documenting TypeScript → Rust property mappings.

**Why**: Rust and TypeScript are different languages; direct code sharing isn't possible.

**Example README** (`frontend-nextjs/src-tauri/tests/property_tests/README.md`):
```markdown
# Property Tests Correspondence

## Canvas State Properties

| TypeScript Property | Rust Property | Status | Notes |
|---------------------|---------------|--------|-------|
| canvasStateMachineProperty | test_canvas_state_machine_invariants | ✅ Implemented | Equivalent invariant |
| canvasNoDirectPresentingToIdle | test_no_direct_presenting_to_idle | ✅ Implemented | Same guard logic |
| canvasErrorRecoveryToIdle | test_error_recovery_to_idle | ✅ Implemented | Error state handling |

## Agent Maturity Properties

| TypeScript Property | Rust Property | Status | Notes |
|---------------------|---------------|--------|-------|
| maturityMonotonicProgression | test_agent_maturity_monotonic | ✅ Implemented | Ordinal comparison |
| autonomousIsTerminal | test_autonomous_is_terminal | ✅ Implemented | Terminal state |

## Differences

- TypeScript uses strings for state values, Rust uses enums
- FastCheck generates random inputs with fc.*, proptest uses strategy::*
- Rust tests use `proptest!` macro, TypeScript uses `fc.property()`
```

### Run Property Tests in CI for Every PR

**Rule**: Property tests should block PRs if they fail.

**CI/CD configuration**:
```yaml
# .github/workflows/cross-platform-property-tests.yml
aggregate-results:
  steps:
    - name: Fail on test failures
      run: |
        python3 backend/tests/scripts/aggregate_property_tests.py \
          --frontend results.json \
          --format json
        # Exit code 1 if any failures
        if [ $? -ne 0 ]; then
          echo "❌ Property tests failed"
          exit 1
        fi
```

**Why**: Properties catch regressions that traditional tests miss.

**Example**:
```typescript
// Developer refactors state machine, accidentally allows PRESENTING → IDLE
// Traditional test: Uses specific inputs, might not catch edge case
test('canvas transitions from IDLE to PRESENTING', () => {
  const stateMachine = new CanvasStateMachine();
  expect(stateMachine.transition(CanvasState.IDLE, 'present')).toBe(CanvasState.PRESENTING);
});

// Property test: Generates 100 random inputs, catches bug
export const canvasNoDirectPresentingToIdle = fc.property(
  fc.array(fc.string()),
  (actions) => {
    // Fails when 'present' → 'idle' sequence occurs
    // Developer sees: "Property failed after 47 tests"
  }
);
```

## References

### Framework Documentation

- **FastCheck**: https://github.com/dubzzz/fast-check
  - TypeScript/JavaScript property-based testing framework
  - 100+ arbitraries (fc.integer(), fc.string(), fc.record(), etc.)
  - Excellent shrinking algorithm (minimal failing cases)

- **proptest**: https://altsysrq.github.io/proptest-book/
  - Rust property-based testing framework
  - Inspired by Haskell's QuickCheck
  - Integrates with cargo test

### Related Documentation

- **CROSS_PLATFORM_COVERAGE.md**: Cross-platform coverage enforcement (70/80/50/40 thresholds)
- **API_TYPE_GENERATION.md**: OpenAPI type generation (Phase 145)
- **PHASE_144_SYMLINK_STRATEGY.md**: SYMLINK distribution pattern

### Example Property Tests

- **frontend-nextjs/shared/property-tests/canvas-invariants.ts**: Canvas state machine properties
- **frontend-nextjs/shared/property-tests/agent-maturity-invariants.ts**: Agent maturity properties
- **frontend-nextjs/shared/property-tests/serialization-invariants.ts**: JSON roundtrip properties
- **frontend-nextjs/src-tauri/tests/state_machine_proptest.rs**: Rust state machine proptests

### Aggregation Infrastructure

- **backend/tests/scripts/aggregate_property_tests.py**: Result aggregation script
- **frontend-nextjs/src-tauri/tests/proptest_formatter.py**: Cargo test output formatter
- **backend/tests/coverage_reports/metrics/property_test_results.json**: Historical tracking

---

**Phase**: 147 - Cross-Platform Property Testing (Complete)
**Status**: Operational in CI/CD
**Last Updated**: March 6, 2026
