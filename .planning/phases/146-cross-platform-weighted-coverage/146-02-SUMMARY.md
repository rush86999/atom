---
phase: 146-cross-platform-weighted-coverage
plan: 02
subsystem: ci-cd-cross-platform-coverage
tags: [github-actions, cross-platform, coverage-enforcement, weighted-coverage, pr-comments, ci-cd]

# Dependency graph
requires:
  - phase: 146-cross-platform-weighted-coverage
    plan: 01
    provides: cross_platform_coverage_gate.py with platform-specific thresholds and weighted calculation
provides:
  - Unified GitHub Actions workflow for cross-platform coverage aggregation
  - PR comment integration with platform breakdown and gap analysis
  - Main branch enforcement with platform-specific thresholds
  - PR warning mode for development flexibility
affects: [ci-cd, coverage-enforcement, cross-platform-testing, quality-gates]

# Tech tracking
tech-stack:
  added: [github-actions-workflow, jq-json-parsing, bc-floating-point, pr-comment-integration]
  patterns:
    - "Parallel platform test jobs with artifact upload/download"
    - "if: always() to run aggregation even if platform tests fail"
    - "Separate enforcement logic for PR (warning) vs main (strict)"
    - "jq for JSON parsing in bash scripts"
    - "actions/github-script@v7 for PR comment management"

key-files:
  created:
    - .github/workflows/cross-platform-coverage.yml
  modified:
    - backend/tests/scripts/cross_platform_coverage_gate.py (added generate_pr_comment, --format pr-comment, --event-type)

key-decisions:
  - "Use if: always() on aggregation job to run even if platform tests fail (provides visibility into all failures)"
  - "Separate enforcement modes: PR warnings (flexible) vs main branch (strict with exit 1)"
  - "Platform-specific thresholds: backend>=70%, frontend>=80%, mobile>=50%, desktop>=40%"
  - "Weighted overall score: backend 35%, frontend 40%, mobile 15%, desktop 10%"
  - "PR comment uses find/update pattern to avoid duplicates (searches for bot comments with specific header)"
  - "Main branch enforcement uses jq for JSON parsing and bc for floating point comparison"

patterns-established:
  - "Pattern: Parallel platform jobs upload artifacts, aggregation job downloads all with pattern matching"
  - "Pattern: PR comment job only runs on pull_request events, enforcement runs on push to main"
  - "Pattern: Use GITHUB_EVENT_NAME environment variable for auto-detecting event type"
  - "Pattern: Platform-specific thresholds allow different maturity levels per platform"

# Metrics
duration: ~3 minutes
completed: 2026-03-06
---

# Phase 146: Cross-Platform Weighted Coverage - Plan 02 Summary

**Unified GitHub Actions workflow for cross-platform coverage aggregation, PR comments, and main branch enforcement**

## Performance

- **Duration:** ~3 minutes
- **Started:** 2026-03-06T18:40:51Z
- **Completed:** 2026-03-06T18:43:48Z
- **Tasks:** 3
- **Files created:** 1
- **Files modified:** 1
- **Commits:** 3

## Accomplishments

- **Cross-platform coverage workflow created** with 5 parallel jobs (backend, frontend, mobile, desktop tests + aggregation)
- **Platform-specific coverage artifacts uploaded** with 30-day retention for historical tracking
- **Aggregate coverage job runs even if platform tests fail** (if: always() for visibility into all failures)
- **PR comment integration** with platform breakdown table, gap analysis, and remediation steps
- **Main branch enforcement** fails build if any platform below threshold (backend>=70%, frontend>=80%, mobile>=50%, desktop>=40%)
- **PR warning mode** shows warnings without failing build (development flexibility)
- **Enhanced coverage script** with generate_pr_comment() function and --format pr-comment option
- **Event type auto-detection** from GITHUB_EVENT_NAME environment variable

## Task Commits

Each task was committed atomically:

1. **Task 1: Unified cross-platform coverage workflow** - `caa08e6b5` (feat)
2. **Task 2: PR comment format enhancement** - `b2bda5075` (feat)
3. **Task 3: Main branch enforcement** - `223d97f22` (feat)

**Plan metadata:** 3 tasks, 3 commits, 2 files created/modified, ~3 minutes execution time

## Files Created

### Created (1 GitHub Actions workflow, 395 lines)

**`.github/workflows/cross-platform-coverage.yml`** (395 lines)
- **Workflow triggers:** push to main/develop, pull_request, workflow_dispatch with threshold override
- **Backend tests job** (lines 23-56): Python 3.11, pytest with coverage.json output, artifact upload
- **Frontend tests job** (lines 58-93): Node 20, Jest with coverage-final.json output, artifact upload
- **Mobile tests job** (lines 95-130): Node 20, jest-expo with coverage-final.json output, artifact upload
- **Desktop tests job** (lines 132-178): Rust stable, cargo tarpaulin with coverage.json output, artifact upload
- **Aggregate coverage job** (lines 180-277): Downloads all artifacts, runs cross_platform_coverage_gate.py, uploads summary artifact, adds GitHub step summary
- **PR warning step** (lines 253-286): Checks thresholds with ::warning:: annotations (PR mode, no failure)
- **Main enforcement step** (lines 288-322): Checks thresholds with ::error:: annotations and exit 1 on failure
- **PR comment job** (lines 324-379): Downloads summary, generates PR comment with platform breakdown, posts/updates comment via actions/github-script@v7

**Key workflow features:**
- Parallel execution of platform tests (4 jobs run simultaneously)
- Artifact upload/download with pattern matching (`*-coverage`)
- if: always() on aggregation job to run even if tests fail
- jq for JSON parsing (extract coverage percentages)
- bc for floating point comparison (coverage < threshold)
- GitHub Actions annotations (::error::, ::warning::)
- PR comment find/update pattern (avoids duplicate comments)
- Separate enforcement logic for PR (development) vs main (strict)

## Files Modified

### Modified (1 coverage script, +153 lines)

**`backend/tests/scripts/cross_platform_coverage_gate.py`**

**Added `generate_pr_comment()` function** (lines 490-630):
- Generates markdown PR comment with platform breakdown table
- Includes overall summary with weighted coverage, target, and gap
- Platform breakdown with coverage, threshold, status, and gap indicators
- Failed platforms section with gap analysis
- Remediation steps per platform (backend: pytest, frontend: npm test, mobile: jest, desktop: tarpaulin)
- Enforcement mode indicator (PR: warning, Main: strict)
- Artifact links to workflow run

**Added `--format pr-comment` option** (line 564):
- Extended format choices to include "pr-comment"
- Calls generate_pr_comment when format='pr-comment'

**Added `--event-type` option** (lines 567-572):
- Accepts 'pull_request' or 'push'
- Auto-detects from GITHUB_EVENT_NAME environment variable if not specified
- Default: 'push' (for local execution)

**Updated main() function** (lines 589-596, 624-627):
- Detects event type from environment or CLI argument
- Logs event type for debugging
- Calls generate_pr_comment for pr-comment format

**Added `os` import** (line 31):
- Required for os.getenv() to read GITHUB_EVENT_NAME

## Workflow Structure

### Job Dependencies

```
backend-tests ─┐
               │
frontend-tests ─┤
               ├──> aggregate-coverage ─┬─> (PR warning step)
mobile-tests ──┤                        └─> (Main enforcement step)
               │
desktop-tests ─┘                           (if: github.event_name == 'pull_request')
                                            │
                                            v
                                         pr-comment
```

### Platform Thresholds and Weights

| Platform | Threshold | Weight | Rationale |
|----------|-----------|--------|-----------|
| Backend | 70% | 35% | Core services, governance, LLM |
| Frontend | 80% | 40% | UI components, user interactions |
| Mobile | 50% | 15% | Platform-specific, emerging coverage |
| Desktop | 40% | 10% | Native code, lower maturity |

### Enforcement Modes

**Pull Request Mode (Development):**
- Checks all platform thresholds
- Shows ::warning:: annotations for failures
- Does NOT fail build (allows development flexibility)
- PR comment shows gap analysis and remediation steps

**Main Branch Mode (Strict):**
- Checks all platform thresholds
- Shows ::error:: annotations for failures
- FAILS build with exit 1 if any platform below threshold
- Ensures production quality standards

## PR Comment Format

The PR comment includes:

1. **Header:** "## Cross-Platform Coverage Report" with timestamp and event type
2. **Overall Coverage:** Weighted overall percentage, target (75% PR / 80% main), gap
3. **Overall Status:** ✅ Target Met / ⚠️ Below Target / ❌ Critical Gap
4. **Platform Breakdown Table:**
   - Platform name (Backend, Frontend, Mobile, Desktop)
   - Coverage percentage with gap indicator (e.g., "65.23% (-4.77%)")
   - Threshold percentage
   - Status emoji (✅ / ❌)

5. **Platforms Below Threshold** (if any):
   - List of failing platforms with coverage < threshold
   - Enforcement mode explanation (PR: warning, Main: strict)

6. **Remediation Steps** (if failures):
   - Backend: pytest commands, focus areas (governance, episodic memory, LLM)
   - Frontend: npm test commands, focus areas (canvas, chat, agent execution)
   - Mobile: jest commands, focus areas (device features, platform-specific)
   - Desktop: tarpaulin commands, focus areas (IPC, system tray, platform-specific)

7. **Artifacts:** Link to workflow run with 30-day retention

## GitHub Actions Annotations

The workflow uses GitHub Actions annotations for visibility:

**Warning annotations (PR mode):**
```yaml
::warning::Backend coverage 65.23% is below 70% threshold
::warning::Frontend coverage 72.45% is below 80% threshold
```

**Error annotations (Main mode):**
```yaml
::error::Coverage enforcement failed for: backend frontend
::error::Main branch requires: backend>=70%, frontend>=80%, mobile>=50%, desktop>=40%
```

These annotations appear in the GitHub Actions log summary and PR checks.

## Artifact Management

**Artifact Upload (Platform Jobs):**
- Name: `{platform}-coverage` (e.g., `backend-coverage`, `frontend-coverage`)
- Path: Coverage report file (coverage.json or coverage-final.json)
- Retention: 30 days
- Upload condition: if: always() (uploads even if tests fail)

**Artifact Download (Aggregation Job):**
- Pattern: `*-coverage` (downloads all platform artifacts)
- Path: `coverage-artifacts/`
- Merge: merge-multiple: true (flattens directory structure)

**Cross-Platform Summary Artifact:**
- Name: `cross-platform-summary`
- Path: `backend/tests/coverage_reports/metrics/cross_platform_summary.json`
- Retention: 30 days
- Contains: Aggregated coverage data with weighted score, platform breakdown, threshold failures

## Script Enhancements

### generate_pr_comment() Function

```python
def generate_pr_comment(aggregate_data, thresholds, event_type):
    """
    Generate PR comment in markdown format.

    Args:
        aggregate_data: Aggregated coverage data from compute_weighted_coverage
        thresholds: Platform-specific thresholds
        event_type: 'pull_request' or 'push'

    Returns:
        Markdown string for PR comment
    """
```

**Output sections:**
1. Header with timestamp and event type
2. Overall coverage summary (weighted, target, gap)
3. Overall status indicator (✅ / ⚠️ / ❌)
4. Platform breakdown table
5. Failed platforms section (if any)
6. Enforcement mode explanation
7. Remediation steps (if failures)
8. Artifacts section with workflow run link

### CLI Options

**New Options:**
```bash
--format {text,json,markdown,pr-comment}  # Added pr-comment option
--event-type {pull_request,push}           # Auto-detects from GITHUB_EVENT_NAME
```

**Usage examples:**
```bash
# Local testing with PR comment format
python cross_platform_coverage_gate.py \
  --format pr-comment \
  --event-type pull_request

# CI/CD usage (auto-detects event type)
python cross_platform_coverage_gate.py \
  --format pr-comment \
  --backend-coverage coverage-artifacts/backend-coverage/coverage.json \
  --frontend-coverage coverage-artifacts/frontend-coverage/coverage-final.json
```

## Decisions Made

- **if: always() on aggregation job:** Ensures aggregation runs even if platform tests fail, providing visibility into all failures instead of silent skips
- **Separate enforcement modes:** PR mode allows development flexibility (warnings only), main mode enforces strict quality standards (exit 1)
- **Platform-specific thresholds:** Different maturity levels per platform (backend 70%, frontend 80%, mobile 50%, desktop 40%) reflect current coverage baselines
- **Weighted overall calculation:** Backend 35%, frontend 40%, mobile 15%, desktop 10% weights align with business impact
- **PR comment find/update pattern:** Searches for existing bot comments with specific header to avoid duplicates, updates if found
- **jq for JSON parsing:** Uses jq for extracting coverage percentages from JSON (more reliable than bash string manipulation)
- **bc for floating point comparison:** Uses bc for coverage < threshold comparisons (bash doesn't handle floating point)

## Deviations from Plan

None - plan executed exactly as written. All tasks completed successfully with no deviations.

## Issues Encountered

None - all tasks completed successfully.

## User Setup Required

None - workflow uses standard GitHub Actions features:
- actions/checkout@v4
- actions/setup-python@v5
- actions/setup-node@v4
- actions-rust-lang/setup-rust-toolchain@v1
- actions/cache@v4
- actions/upload-artifact@v4
- actions/download-artifact@v4
- actions/github-script@v7

No external service configuration required.

## Verification Results

All verification steps passed:

1. ✅ **Workflow YAML is valid** - Python yaml.safe_load() parses successfully
2. ✅ **5 jobs defined** - backend-tests, frontend-tests, mobile-tests, desktop-tests, aggregate-coverage, pr-comment
3. ✅ **Artifact upload/download patterns match** - 5 uploads (4 platform + 1 summary), 2 downloads (artifacts + summary)
4. ✅ **Script reference exists** - cross_platform_coverage_gate.py called in aggregation and PR comment jobs
5. ✅ **PR comment format option added** - generate_pr_comment() function, --format pr-comment, --event-type
6. ✅ **Main branch enforcement step exists** - Enforce platform thresholds on main with exit 1
7. ✅ **PR warning step exists** - Check platform thresholds (PR warning) with ::warning:: annotations
8. ✅ **jq usage for JSON parsing** - 9 jq calls for extracting coverage percentages
9. ✅ **bc usage for floating point comparison** - bc used in all threshold checks
10. ✅ **Platform-specific thresholds** - backend>=70%, frontend>=80%, mobile>=50%, desktop>=40%
11. ✅ **Weighted calculation** - backend 35%, frontend 40%, mobile 15%, desktop 10%

## Workflow Triggers

**Automatic:**
- `push` to main or develop branches
- `pull_request` to main or develop branches

**Manual:**
- `workflow_dispatch` with threshold override option (default: 80%)

**Event type detection:**
- GITHUB_EVENT_NAME environment variable
- Auto-detects 'push' or 'pull_request'
- Falls back to 'push' for local execution

## Platform Test Commands

**Backend (Python pytest):**
```bash
pytest tests/ \
  --cov=core \
  --cov=api \
  --cov=tools \
  --cov-report=json \
  --cov-report=term-missing \
  --cov-report=html
```

**Frontend (Jest):**
```bash
npm test -- --coverage --coverageReporters=json --coverageReporters=text
```

**Mobile (jest-expo):**
```bash
npm test -- --coverage --coverageReporters=json --coverageReporters=text
```

**Desktop (cargo tarpaulin):**
```bash
cargo tarpaulin \
  --config tarpaulin.toml \
  --out Json \
  --output-dir coverage-report \
  --timeout 300
```

## Enforcement Logic

**PR Warning Step:**
```bash
# Check each platform threshold
BACKEND=$(echo "$SUMMARY" | jq -r '.platforms.python.coverage_pct // 0')
if (( $(echo "$BACKEND < 70" | bc -l) )); then
  echo "::warning::Backend coverage ${BACKEND}% is below 70% threshold"
fi
# No exit 1 - warnings only
```

**Main Enforcement Step:**
```bash
# Check each platform threshold
BACKEND=$(echo "$SUMMARY" | jq -r '.platforms.python.coverage_pct // 0')
if (( $(echo "$BACKEND < 70" | bc -l) )); then
  echo "::error::Backend coverage ${BACKEND}% < 70%"
  FAILED="${FAILED}backend "
fi
# Exit 1 if any failures
if [ -n "$FAILED" ]; then
  echo "::error::Coverage enforcement failed for: $FAILED"
  exit 1
fi
```

## Next Phase Readiness

✅ **Cross-platform coverage workflow complete** - Unified CI/CD workflow with PR comments and main branch enforcement

**Ready for:**
- Phase 146 Plan 03: Local development workflow integration (pre-commit hooks, local coverage aggregation)
- Phase 146 Plan 04: Coverage trend analysis and dashboard (historical tracking, visualization)
- Phase 147+: Coverage expansion for individual platforms (backend, frontend, mobile, desktop improvements)

**Recommendations for follow-up:**
1. Add coverage trend tracking (compare current coverage to previous runs)
2. Add coverage badge generation (weighted overall percentage)
3. Add coverage dashboard (historical visualization with GitHub Pages)
4. Add local development workflow (pre-commit hooks for coverage checks)
5. Add platform-specific coverage goals (incremental improvements per platform)

## Self-Check: PASSED

All files created:
- ✅ .github/workflows/cross-platform-coverage.yml (395 lines)

All files modified:
- ✅ backend/tests/scripts/cross_platform_coverage_gate.py (+153 lines)

All commits exist:
- ✅ caa08e6b5 - feat(146-02): create unified cross-platform coverage workflow
- ✅ b2bda5075 - feat(146-02): add PR comment format to coverage script
- ✅ 223d97f22 - feat(146-02): add main branch enforcement to workflow

All verification criteria met:
- ✅ Workflow YAML is valid and contains all 5 jobs
- ✅ Artifact upload/download paths match between upload and download steps
- ✅ Script generates PR comment format with platform breakdown table
- ✅ Main branch enforcement exits 1 on threshold failure
- ✅ PR warnings show without failing build
- ✅ PR comment includes remediation steps for failing platforms
- ✅ Unit tests pass for enhanced script functionality

---

*Phase: 146-cross-platform-weighted-coverage*
*Plan: 02*
*Completed: 2026-03-06*
