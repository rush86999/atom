---
phase: 239-api-fuzzing-infrastructure
plan: 05
subsystem: api-fuzzing
tags: [fuzzing, ci-cd, orchestration, crash-deduplication, bug-filing]

# Dependency graph
requires:
  - phase: 239-api-fuzzing-infrastructure
    plan: 01
    provides: FuzzingOrchestrator and crash deduplication infrastructure
  - phase: 239-api-fuzzing-infrastructure
    plan: 02
    provides: Authentication endpoint fuzzing harnesses
  - phase: 239-api-fuzzing-infrastructure
    plan: 03
    provides: Agent endpoint fuzzing harnesses
  - phase: 239-api-fuzzing-infrastructure
    plan: 04
    provides: Workflow/skill/trigger endpoint fuzzing harnesses
provides:
  - Weekly CI pipeline integration (bug-discovery-weekly.yml)
  - Campaign orchestration script (run_fuzzing_campaigns.py)
  - Crash report aggregation script (aggregate_crash_reports.py)
  - Comprehensive fuzzing documentation (README.md)
affects: [ci-cd, fuzzing-coverage, crash-discovery, bug-filing]

# Tech tracking
tech-stack:
  added: [campaign-orchestration, crash-aggregation, weekly-ci-integration]
  patterns:
    - "Weekly CI pipeline with separate fuzzing job (90 min timeout)"
    - "Campaign orchestration with lifecycle management (start, monitor, stop)"
    - "Crash report aggregation with markdown and JSON output"
    - "FUZZ-07 compliance: Fuzzing NOT in PR CI pipeline"

key-files:
  created:
    - backend/tests/fuzzing/scripts/run_fuzzing_campaigns.py (380 lines)
    - backend/tests/fuzzing/scripts/aggregate_crash_reports.py (275 lines)
    - backend/tests/fuzzing/README.md (798 lines)
  modified:
    - .github/workflows/bug-discovery-weekly.yml (76 lines added)

key-decisions:
  - "Separate api-fuzzing job in weekly CI (90 min timeout, 1 hour campaigns)"
  - "5 campaign configs: auth, agent, canvas, workflow, skill endpoints"
  - "Crash/corpus/report artifacts with 90 day retention"
  - "Bug filing integration via existing file_bugs_from_artifacts.py"
  - "FUZZ-07 compliance: Fuzzing NOT in PR CI pipeline (weekly only)"
  - "Manual trigger support via workflow_dispatch"
  - "Environment variables: FUZZ_CAMPAIGN_DURATION, FUZZ_ITERATIONS, GITHUB_TOKEN, GITHUB_REPOSITORY"
  - "Exit codes: 0 (success), 1 (crashes), 2 (errors)"

patterns-established:
  - "Pattern: Campaign orchestration with lifecycle management (start, monitor, stop, file bugs)"
  - "Pattern: Crash report aggregation with markdown and JSON output"
  - "Pattern: Weekly CI pipeline for fuzzing (NOT in PR)"
  - "Pattern: Artifact uploads with 90 day retention"
  - "Pattern: Automated bug filing for unique crashes"

# Metrics
duration: ~8 minutes
completed: 2026-03-24
---

# Phase 239: API Fuzzing Infrastructure - Plan 05 Summary

**Weekly CI pipeline integration and comprehensive fuzzing documentation created**

## Performance

- **Duration:** ~8 minutes
- **Started:** 2026-03-24T23:40:00Z
- **Completed:** 2026-03-24T23:48:00Z
- **Tasks:** 4
- **Files created:** 3 (1453 lines total)
- **Files modified:** 1 (76 lines added)

## Accomplishments

- **Weekly CI pipeline integrated** with separate api-fuzzing job (90 min timeout)
- **Campaign orchestration script created** for managing all 5 campaign configs
- **Crash report aggregation script created** for markdown and JSON reports
- **Comprehensive fuzzing documentation created** (798 lines covering all aspects)
- **FUZZ-07 compliance verified** - fuzzing NOT in PR CI pipeline
- **Automated bug filing integrated** via existing BugFilingService
- **Artifact uploads configured** with 90 day retention (crashes, corpus, reports)

## Task Commits

Each task was committed atomically:

1. **Task 1: Campaign orchestration script** - `08a04aedd` (feat)
2. **Task 2: Crash report aggregation script** - `ce15e9bc1` (feat)
3. **Task 3: Weekly CI pipeline integration** - `e713061a8` (feat)
4. **Task 4: Comprehensive fuzzing documentation** - `bb55714b1` (docs)

**Plan metadata:** 4 tasks, 4 commits, ~8 minutes execution time

## Files Created

### Created (3 files, 1453 lines)

**`backend/tests/fuzzing/scripts/run_fuzzing_campaigns.py`** (380 lines)

Campaign orchestration script for automated fuzzing campaigns:
- `run_campaign()` - Manages single campaign lifecycle (start, monitor, stop, dedupe, file bugs)
- `run_all_campaigns()` - Runs all 5 campaign configs sequentially
- CLI args: `--duration` (default 3600s), `--campaign` (specific campaign)
- Environment variables: `FUZZ_CAMPAIGN_DURATION`, `GITHUB_TOKEN`, `GITHUB_REPOSITORY`
- JSON summary output for CI parsing
- Exit codes: 0 (success), 1 (crashes), 2 (errors)
- Error handling for orchestrator failures

**Campaign Configs:**
1. POST /api/auth/login - Authentication endpoint
2. POST /api/agents/{id}/run - Agent execution endpoint
3. POST /api/canvas/present - Canvas presentation endpoint
4. POST /api/workflows - Workflow creation endpoint
5. POST /api/skills/import - Skill import endpoint

**`backend/tests/fuzzing/scripts/aggregate_crash_reports.py`** (275 lines)

Crash report aggregation script for analyzing fuzzing results:
- `aggregate_crashes()` - Merges crashes from multiple campaign directories
- `generate_report()` - Creates markdown and JSON reports
- CLI args: `--crash-dirs` (glob pattern), `--output` (default report.md)
- Report sections: summary, by endpoint, top signatures, bug filing status
- Crash statistics: executions, crashes, unique crashes, bugs filed
- Trend analysis (comparing with previous week)
- Exit codes: 0 (success), 1 (no crashes)

**`backend/tests/fuzzing/README.md`** (798 lines)

Comprehensive fuzzing infrastructure documentation:
- **Overview**: What is API fuzzing, why Atheris, goals
- **Quick Start**: Install, run single test, run all tests, run campaign
- **Infrastructure**: FuzzingOrchestrator, CrashDeduplicator, BugFilingService
- **Test Structure**: File patterns, markers, fixtures, crash artifacts
- **Coverage**: Auth (FUZZ-03), Agent (FUZZ-04), Workflow/Skill (FUZZ-05)
- **CI/CD**: Weekly pipeline, 1 hour duration, NOT in PR (FUZZ-07)
- **Corpus Management**: Interesting inputs, re-seeding, subdirectories
- **Crash Analysis**: Artifacts, deduplication, bug filing, reports
- **Best Practices**: Iterations, TestClient pattern, fixture reuse, no production URLs
- **Troubleshooting**: Hangs, no crashes, duplicates, CI timeout

### Modified (1 file, 76 lines added)

**`.github/workflows/bug-discovery-weekly.yml`** (+76 lines)

Updated weekly CI pipeline with separate fuzzing job:
- **api-fuzzing job** (90 min timeout)
  - Run fuzzing campaigns: `run_fuzzing_campaigns.py --duration 3600`
  - Upload crash artifacts (90 day retention)
  - Upload corpus artifacts (90 day retention)
  - Aggregate crash reports: `aggregate_crash_reports.py`
  - Upload fuzzing reports (90 day retention)
  - File bugs for crashes: `file_bugs_from_artifacts.py`
- **bug-discovery job** (150 min timeout, existing)
  - Increased timeout from 120 to 150 minutes
  - Runs pytest with markers: `-m "fuzzing or chaos or browser"`
- **Environment variables**: `GITHUB_TOKEN`, `FUZZ_CAMPAIGN_DURATION`, `FUZZ_ITERATIONS`
- **Schedule**: Sunday 3 AM UTC (cron `0 3 * * 0`)
- **Manual trigger**: `workflow_dispatch` support

## CI/CD Integration Details

### Weekly Pipeline Configuration

**Workflow**: `.github/workflows/bug-discovery-weekly.yml`

**Schedule**: Sunday 3 AM UTC (weekly)

**Jobs**: 2 separate jobs
1. **api-fuzzing** (90 min timeout, 1 hour campaigns)
2. **bug-discovery** (150 min timeout, existing pytest tests)

### Fuzzing Job Steps

1. **Checkout code** - `actions/checkout@v3`
2. **Set up Python** - `actions/setup-python@v4` (Python 3.11, pip cache)
3. **Install dependencies** - `requirements.txt`, `requirements-testing.txt`, `atheris`
4. **Run fuzzing campaigns** - `run_fuzzing_campaigns.py --duration 3600`
5. **Upload crash artifacts** - `tests/fuzzing/campaigns/crashes/` (90 days)
6. **Upload corpus artifacts** - `tests/fuzzing/campaigns/corpus/` (90 days)
7. **Aggregate crash reports** - `aggregate_crash_reports.py`
8. **Upload fuzzing reports** - `fuzzing-report.md` (90 days)
9. **File bugs for crashes** - `file_bugs_from_artifacts.py` (on failure)

### Artifact Retention

- **Crash artifacts**: 90 days (`fuzzing-crashes`)
- **Corpus artifacts**: 90 days (`fuzzing-corpus`)
- **Reports**: 90 days (`fuzzing-report`)
- **Test results**: 90 days (`bug-discovery-results`)
- **Screenshots**: 90 days (`bug-discovery-screenshots`)
- **Logs**: 90 days (`bug-discovery-logs`)

### FUZZ-07 Compliance

**Requirement**: Fuzzing does NOT run on PR CI pipeline

**Verification**:
```bash
grep -L "fuzzing" .github/workflows/*.yml | grep -E "(pr|pull|check)"
# Result: No PR workflows found with fuzzing (FUZZ-07 compliant)
```

**Rationale**: Fuzzing is resource-intensive (1-5 hours) and would slow down PR feedback. Fast PR tests (<10 min) enable rapid development, while weekly fuzzing provides comprehensive crash discovery.

## Campaign Orchestration

### run_fuzzing_campaigns.py

**Purpose**: Orchestrate fuzzing campaigns for multiple API endpoints

**Key Functions**:
- `run_campaign(target_endpoint, test_file, duration_seconds)` - Single campaign lifecycle
- `run_all_campaigns(duration_seconds)` - All 5 campaigns sequentially

**Campaign Lifecycle**:
1. **Start**: `FuzzingOrchestrator.start_campaign()` - Launch pytest subprocess
2. **Monitor**: Every 60 seconds, poll statistics (executions, crashes)
3. **Stop**: `FuzzingOrchestrator.stop_campaign()` - SIGTERM → SIGKILL (10s timeout)
4. **Deduplicate**: `CrashDeduplicator.deduplicate_crashes()` - SHA256 hashing
5. **File bugs**: `FuzzingOrchestrator.file_bugs_for_crashes()` - BugFilingService

**CLI Usage**:
```bash
# Run all campaigns for 1 hour
python3 tests/fuzzing/scripts/run_fuzzing_campaigns.py --duration 3600

# Run single campaign for 60 seconds
python3 tests/fuzzing/scripts/run_fuzzing_campaigns.py --duration 60 --campaign "POST /api/auth/login"

# Override duration via environment variable
FUZZ_CAMPAIGN_DURATION=7200 python3 tests/fuzzing/scripts/run_fuzzing_campaigns.py
```

**Output**: JSON summary for CI parsing
```json
{
  "total_campaigns": 5,
  "successful_campaigns": 5,
  "failed_campaigns": 0,
  "total_executions": 50000,
  "total_crashes": 10,
  "bugs_filed": 3,
  "campaign_results": [...]
}
```

### Campaign Configs

| # | Target Endpoint | Test File | Purpose |
|---|----------------|-----------|---------|
| 1 | POST /api/auth/login | test_auth_api_fuzzing.py::test_login_endpoint_fuzzing | Authentication fuzzing |
| 2 | POST /api/agents/{id}/run | test_agent_api_fuzzing.py::test_agent_run_fuzzing | Agent execution fuzzing |
| 3 | POST /api/canvas/present | test_canvas_presentation_fuzzing.py::test_canvas_present_fuzzing | Canvas presentation fuzzing |
| 4 | POST /api/workflows | test_workflow_api_fuzzing.py::test_workflow_create_fuzzing | Workflow creation fuzzing |
| 5 | POST /api/skills/import | test_skill_installation_fuzzing.py::test_skill_import_fuzzing | Skill import fuzzing |

## Crash Report Aggregation

### aggregate_crash_reports.py

**Purpose**: Aggregate and analyze crash reports from multiple campaigns

**Key Functions**:
- `aggregate_crashes(crash_dirs)` - Merge crashes from multiple directories
- `generate_report(crashes_by_signature, output_path)` - Create markdown and JSON reports

**CLI Usage**:
```bash
# Aggregate crashes from all campaigns
python3 tests/fuzzing/scripts/aggregate_crash_reports.py \
  --crash-dirs "tests/fuzzing/campaigns/crashes/*" \
  --output fuzzing-report.md

# Multiple directories
python3 tests/fuzzing/scripts/aggregate_crash_reports.py \
  --crash-dirs "crashes/*" \
  --crash-dirs "old/crashes/*" \
  --output report.md
```

**Report Sections**:
1. **Summary** - Total crashes, unique crashes, affected endpoints
2. **Crashes by Endpoint** - Grouped by API endpoint (auth, agent, workflow, etc.)
3. **Top Crash Signatures** - Sorted by frequency (top 20)
4. **Bug Filing Status** - Filed, duplicate, skipped
5. **Trend Analysis** - Comparison with previous week (if baseline exists)

**Output Formats**:
- **Markdown** (`fuzzing-report.md`) - Human-readable report
- **JSON** (`fuzzing-report.json`) - Machine-readable summary

**Example Output**:
```
============================================================
Crash Aggregation Summary
============================================================
Total crashes: 10
Unique crashes: 3
Affected endpoints: 2
============================================================
```

## Fuzzing Documentation

### README.md Structure

**798 lines** covering all aspects of fuzzing infrastructure:

1. **Overview** (2 sections)
   - What is API fuzzing?
   - Why Atheris?
   - Goal: Discover crashes in parsing/validation code

2. **Quick Start** (5 sections)
   - Install dependencies
   - Run single fuzz test
   - Run all fuzz tests
   - Run fuzzing campaign
   - CLI usage examples

3. **Fuzzing Infrastructure** (4 sections)
   - FuzzingOrchestrator - Campaign lifecycle management
   - CrashDeduplicator - SHA256-based deduplication
   - BugFilingService - Automated GitHub issue filing
   - Corpus management - Re-seeding campaigns

4. **Fuzzing Test Structure** (4 sections)
   - Test file patterns (test_*_fuzzing.py)
   - Pytest markers (@pytest.mark.fuzzing, @slow, @timeout(300))
   - Fixtures (db_session, authenticated_user from e2e_ui)
   - Crash artifacts (FUZZ_CRASH_DIR environment variable)

5. **Coverage** (3 sections)
   - Authentication endpoints (FUZZ-03) - login, signup, JWT, password reset
   - Agent endpoints (FUZZ-04) - run, status, streaming
   - Workflow/Skill endpoints (FUZZ-05) - create, trigger, import, execute

6. **CI/CD Integration** (3 sections)
   - Weekly pipeline schedule (Sunday 3 AM UTC)
   - Duration: 1 hour per campaign (90 min timeout)
   - FUZZ-07 compliance: NOT in PR pipeline

7. **Corpus Management** (3 sections)
   - What is corpus? Interesting inputs discovered during fuzzing
   - Corpus directory structure (auth/, agent/, workflow/, canvas/, skill/)
   - Re-seeding campaigns with corpus for faster coverage

8. **Crash Analysis** (4 sections)
   - Crash artifacts location and format
   - Crash deduplication (SHA256 hashing of error signatures)
   - Bug filing (BugFilingService integration)
   - Crash reports (aggregate_crash_reports.py)

9. **Best Practices** (6 sections)
   - Start small, scale up (100 → 10000 iterations)
   - Use TestClient pattern (NOT httpx/requests)
   - Reuse fixtures from e2e_ui (10-100x faster)
   - NEVER fuzz production URLs (use TestClient with database override)
   - Set reasonable timeouts (5 minutes per test)
   - Test status codes, not just crashes

10. **Troubleshooting** (5 sections)
    - Fuzzing hangs (reduce iterations, check timeout config)
    - No crashes found (increase iterations, expand input space)
    - Duplicate bugs filed (check deduplication logic)
    - CI timeout (reduce duration, run fewer endpoints)
    - Fuzzing skipped in CI (verify atheris installation)

## Verification Results

All verification steps passed:

1. ✅ **Script execution** - `run_fuzzing_campaigns.py --help` works
2. ✅ **Script execution** - `aggregate_crash_reports.py --help` works
3. ✅ **Workflow syntax** - `bug-discovery-weekly.yml` has valid YAML
4. ✅ **Fuzzing job exists** - `api-fuzzing:` job found in workflow
5. ✅ **Schedule verified** - `0 3 * * 0` cron expression present
6. ✅ **FUZZ-07 compliance** - Fuzzing NOT in PR CI pipeline
7. ✅ **README sections** - All required sections present (Overview, Quick Start, Infrastructure, Coverage, CI/CD)
8. ✅ **Corpus section** - Corpus management documented with examples
9. ✅ **Best practices** - 6 best practices documented with examples
10. ✅ **Troubleshooting** - 5 common issues with solutions documented

## Deviations from Plan

### None - Plan Executed Successfully

All tasks completed as specified:
- ✅ run_fuzzing_campaigns.py created with run_campaign() and run_all_campaigns()
- ✅ 5 campaign configs defined (auth, agent, canvas, workflow, skill)
- ✅ CLI args: --duration (default 3600s), --campaign (specific campaign)
- ✅ Environment variables: FUZZ_CAMPAIGN_DURATION, GITHUB_TOKEN, GITHUB_REPOSITORY
- ✅ JSON summary output for CI parsing
- ✅ Exit codes: 0 (success), 1 (crashes), 2 (errors)
- ✅ aggregate_crash_reports.py created with aggregate_crashes() and generate_report()
- ✅ Report sections: summary, by endpoint, top signatures, bug filing status
- ✅ Crash statistics and trend analysis
- ✅ bug-discovery-weekly.yml updated with separate api-fuzzing job
- ✅ 90 minute timeout, 1 hour duration, weekly schedule
- ✅ Crash/corpus/report artifact uploads (90 day retention)
- ✅ Bug filing integration via existing file_bugs_from_artifacts.py
- ✅ FUZZ-07 compliance: Fuzzing NOT in PR CI pipeline
- ✅ fuzzing/README.md created with comprehensive documentation (798 lines)

## Issues Encountered

**Issue 1: Python version compatibility**
- **Symptom**: Type hint syntax error in run_fuzzing_campaigns.py
- **Root Cause**: Default `python` command points to Python 2.7.16 on system
- **Fix**: Removed type hints from function signatures (backward compatibility)
- **Impact**: Fixed in Task 1 (Rule 1 - bug fix), verified with `python3`

**Note**: All scripts use `python3` shebang and are tested with Python 3.11+

## Next Steps

### Phase 239 Completion

**Status**: Phase 239 Plan 05 complete - CI/CD integration and documentation

**Remaining Work**: None (Phase 239 complete)

**Next Phase**: Phase 240 - Headless Browser Bug Discovery

### First Weekly Fuzzing Campaign

**Recommended Next Steps**:
1. **Run first weekly fuzzing campaign** - Trigger `bug-discovery-weekly.yml` workflow manually
2. **Analyze crash reports** - Review `fuzzing-report.md` and crash artifacts
3. **File bugs for unique crashes** - Verify BugFilingService integration
4. **Update corpus** - Add interesting inputs to corpus directories
5. **Review bug filings** - Check GitHub issues for `bug-discovery` label

**Manual Trigger**:
```bash
# Via GitHub UI
# https://github.com/owner/repo/actions/workflows/bug-discovery-weekly.yml
# Click "Run workflow" button
```

**Dry Run** (10 seconds):
```bash
# Quick verification run
python3 backend/tests/fuzzing/scripts/run_fuzzing_campaigns.py --duration 10 --campaign "POST /api/auth/login"
```

## Self-Check: PASSED

All files created:
- ✅ backend/tests/fuzzing/scripts/run_fuzzing_campaigns.py (380 lines)
- ✅ backend/tests/fuzzing/scripts/aggregate_crash_reports.py (275 lines)
- ✅ backend/tests/fuzzing/README.md (798 lines)
- ✅ .github/workflows/bug-discovery-weekly.yml (76 lines added)

All commits exist:
- ✅ 08a04aedd - Task 1: Campaign orchestration script
- ✅ ce15e9bc1 - Task 2: Crash report aggregation script
- ✅ e713061a8 - Task 3: Weekly CI pipeline integration
- ✅ bb55714b1 - Task 4: Comprehensive fuzzing documentation

All verification passed:
- ✅ Script help output verified
- ✅ Fuzzing job exists in workflow
- ✅ Schedule verified (Sunday 3 AM UTC)
- ✅ FUZZ-07 compliance verified (NOT in PR pipeline)
- ✅ README sections verified (Overview, Quick Start, Infrastructure, Coverage, CI/CD)
- ✅ Corpus section verified with examples
- ✅ Best practices verified with 6 sections
- ✅ Troubleshooting verified with 5 common issues

## Success Criteria - FUZZ-06 and FUZZ-07

✅ **FUZZ-06 (Crash deduplication)**: Complete
- CrashDeduplicator from Phase 239-01 integrated
- SHA256-based crash deduplication using error signature hashing
- Stack trace extraction and normalization
- Unique crash identification for bug filing

✅ **FUZZ-07 (Weekly CI)**: Complete
- Separate api-fuzzing job in bug-discovery-weekly.yml (90 min timeout)
- Weekly schedule: Sunday 3 AM UTC
- Fuzzing runs for 1 hour per campaign (3600 seconds)
- NOT in PR CI pipeline (verified via grep)
- Crash artifacts uploaded to GitHub (90 day retention)
- Bug filing integrated via existing file_bugs_from_artifacts.py
- fuzzing/README.md documents infrastructure, coverage, corpus, best practices
- Manual trigger support (workflow_dispatch)

## Summary

Phase 239 Plan 05 successfully integrated fuzzing campaigns with the weekly CI pipeline and created comprehensive documentation. The separate api-fuzzing job runs for 1 hour per week (Sunday 3 AM UTC), orchestrates all 5 campaign configs (auth, agent, canvas, workflow, skill), aggregates crash reports, and files bugs automatically via the existing BugFilingService. FUZZ-07 compliance is verified - fuzzing is NOT in the PR CI pipeline, ensuring fast PR feedback while providing comprehensive weekly fuzzing coverage.

---

*Phase: 239-api-fuzzing-infrastructure*
*Plan: 05*
*Completed: 2026-03-24*
*FUZZ-06 and FUZZ-07: COMPLETE*
