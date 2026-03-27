---
phase: 241-chaos-engineering-integration
plan: 07
subsystem: chaos-engineering
tags: [chaos-engineering, ci-cd, documentation, pytest-markers, weekly-pipeline]

# Dependency graph
requires:
  - phase: 241-chaos-engineering-integration
    plan: 06
    provides: Blast radius control validation tests and recovery validation tests
provides:
  - Weekly CI pipeline for chaos engineering tests (CHAOS-08)
  - Comprehensive chaos testing README documentation
  - pytest.ini chaos marker configuration
affects: [chaos-engineering, ci-cd-pipeline, testing-infrastructure]

# Tech tracking
tech-stack:
  added:
    - ".github/workflows/chaos-engineering-weekly.yml (125 lines)"
  patterns:
    - "Weekly CI pipeline with Sunday 2 AM UTC schedule"
    - "Toxiproxy Docker container for network chaos simulation"
    - "Environment validation (test only, no production access)"
    - "Separate test runs for each chaos category (network, database, memory, service)"
    - "Bug filing integration on failure"
    - "pytest.ini chaos marker with descriptive text"
    - "Comprehensive README documentation (311 lines, 29 sections)"

key-files:
  created:
    - .github/workflows/chaos-engineering-weekly.yml (125 lines)
    - backend/tests/chaos/README.md (311 lines)
  modified:
    - backend/pytest.ini (1 line changed)

key-decisions:
  - "Weekly CI pipeline scheduled Sunday 2 AM UTC (minimal traffic)"
  - "Toxiproxy Docker container for network chaos (ghcr.io/shopify/toxiproxy:2.5.0)"
  - "90-minute job timeout, 120-second per-test timeout"
  - "Environment verification (ENVIRONMENT=test, DATABASE_URL validation)"
  - "Separate test runs for each chaos category (better error reporting)"
  - "pytest.ini chaos marker: 'Chaos engineering tests (failure injection, isolated environment, slow, weekly only)'"
  - "README covers all aspects: purpose, safety, requirements, running tests, fixtures, CI/CD, troubleshooting, writing new tests"

patterns-established:
  - "Pattern: Weekly chaos engineering pipeline with scheduled execution"
  - "Pattern: Toxiproxy Docker container for network latency simulation"
  - "Pattern: Environment validation before chaos injection (no production access)"
  - "Pattern: Separate test category runs (network, database, memory, service)"
  - "Pattern: Comprehensive README documentation (311 lines, 29 sections)"
  - "Pattern: pytest.ini marker with descriptive text for clarity"

# Metrics
duration: ~3 minutes
completed: 2026-03-25
---

# Phase 241: Chaos Engineering Integration - Plan 07 Summary

**Weekly CI pipeline and comprehensive documentation for chaos engineering tests with isolated execution and proper scheduling**

## Performance

- **Duration:** ~3 minutes
- **Started:** 2026-03-25T03:42:08Z
- **Completed:** 2026-03-25T03:45:08Z
- **Tasks:** 3
- **Files created:** 2
- **Files modified:** 1
- **Total lines:** 437 lines (125 + 311 + 1 changed)

## Accomplishments

- **Weekly CI pipeline created** for chaos engineering tests (125 lines)
- **pytest.ini updated** with enhanced chaos marker description
- **Comprehensive README documentation** created (311 lines, 29 sections)
- **Environment validation** implemented (test only, no production access)
- **Toxiproxy integration** for network chaos simulation
- **Separate test category runs** (network, database, memory, service)
- **Bug filing integration** on test failures
- **Troubleshooting guide** included in README

## Task Commits

Each task was committed atomically:

1. **Task 1: Weekly CI pipeline for chaos engineering** - `f31ef9a67` (feat)
2. **Task 2: Update pytest.ini with chaos marker** - `11badaf99` (feat)
3. **Task 3: Comprehensive chaos testing README** - `55aacdc4d` (docs)

**Plan metadata:** 3 tasks, 3 commits, ~3 minutes execution time

## Files Created

### Created (2 files, 436 lines)

**`.github/workflows/chaos-engineering-weekly.yml`** (125 lines)

Weekly CI pipeline for chaos engineering tests:
- Schedule: Sunday 2 AM UTC (weekly chaos tests)
- workflow_dispatch: Allow manual trigger for ad-hoc chaos testing
- Dependencies: pytest, pytest-timeout, psutil, toxiproxy-python (optional)
- Toxiproxy: Docker container ghcr.io/shopify/toxiproxy:2.5.0
- Environment verification: ENVIRONMENT=test, DATABASE_URL validation
- Test execution: Separate runs for each chaos category (network, database, memory, service)
- Bug filing integration on failure
- 90-minute job timeout, 120-second per-test timeout
- Artifact collection and notifications

**Key Features:**
- Scheduled execution (Sunday 2 AM UTC - minimal traffic)
- Manual trigger support (workflow_dispatch)
- Toxiproxy Docker container setup and cleanup
- Environment validation (test only, no production access)
- Separate test runs for each chaos category:
  - Network latency chaos tests
  - Database drop chaos tests
  - Memory pressure chaos tests
  - Service crash chaos tests
  - Blast radius control tests
  - Recovery validation tests
- Comprehensive test run (all chaos tests)
- Test results upload (30-day retention)
- Bug filing on failure
- Toxiproxy cleanup (always())
- Failure notification with CI URL

**`backend/tests/chaos/README.md`** (311 lines, 29 sections)

Comprehensive chaos testing documentation:
- Purpose: Document chaos engineering goals and safety
- Safety: Blast radius controls (test databases only, isolated network, 60s limit, environment validation)
- Requirements: Core (pytest, psutil) and optional (toxiproxy-python, memory-profiler)
- Toxiproxy setup: Docker, macOS Homebrew, verification curl command
- Running tests: All chaos, specific categories, skip chaos (-m "not chaos")
- Test structure: Directory tree with descriptions
- Fixtures: ChaosCoordinator, blast radius, network, database, memory, service crash
- CI/CD pipeline: Weekly schedule (Sunday 2 AM UTC), steps, manual trigger
- Troubleshooting: Toxiproxy, missing deps, blast radius, timeout, Redis
- Writing new tests: Template reference, key requirements, example

**Documentation Sections (29 total):**
1. Purpose
2. Safety
3. Requirements (Core Dependencies)
4. Requirements (Optional Dependencies)
5. Toxiproxy Setup
6. Running Tests (All Chaos Tests)
7. Running Tests (Specific Chaos Categories)
8. Running Tests (Blast Radius and Recovery Tests)
9. Running Tests (Skip Chaos Tests)
10. Test Structure
11. Fixtures (ChaosCoordinator)
12. Fixtures (Blast Radius Controls)
13. Fixtures (Network Chaos Fixtures)
14. Fixtures (Database Chaos Fixtures)
15. Fixtures (Memory Chaos Fixtures)
16. Fixtures (Service Crash Fixtures)
17. CI/CD Pipeline (Weekly Execution)
18. Troubleshooting (Toxiproxy Not Available)
19. Troubleshooting (Tests Skipped Due to Missing Dependencies)
20. Troubleshooting (Blast Radius Check Failed)
21. Troubleshooting (Test Timeout)
22. Troubleshooting (Redis Not Available)
23. Writing New Chaos Tests
24. See Also

### Modified (1 file, 1 line changed)

**`backend/pytest.ini`** (1 line changed)

Updated chaos marker description:
- Old: `chaos: Chaos engineering tests`
- New: `chaos: Chaos engineering tests (failure injection, isolated environment, slow, weekly only)`

**Benefits:**
- More descriptive marker text
- Clarifies that chaos tests should run in isolated environment
- Indicates slow-running nature and weekly execution schedule
- Helps developers understand when to use chaos marker

## CHAOS-08 Requirements Compliance

### CHAOS-08: Isolated Environment Execution

**Requirement:** Chaos experiments run in isolated environment (weekly, never on shared dev)

**Implementation:**
- ✅ Weekly CI pipeline scheduled Sunday 2 AM UTC (minimal traffic)
- ✅ Environment verification step (ENVIRONMENT=test required)
- ✅ Database URL validation (no production endpoints)
- ✅ Hostname validation (no production hosts)
- ✅ Toxiproxy Docker container for network chaos (isolated network)
- ✅ Test databases only (never production)
- ✅ pytest.ini marker: "isolated environment, slow, weekly only"

**Verification:**
```bash
# Environment verification in CI
export ENVIRONMENT=test
export DATABASE_URL=sqlite:///./test_chaos.db

# Verify no production access
if echo "$DATABASE_URL" | grep -i "production"; then
  echo "ERROR: Production database detected!"
  exit 1
fi
```

### Success Criteria

**Requirement:** Chaos experiments run in isolated environment (weekly, never on shared dev)

- ✅ **Weekly CI pipeline:** Sunday 2 AM UTC schedule (minimal traffic)
- ✅ **Environment validation:** ENVIRONMENT=test required
- ✅ **Database URL validation:** No production endpoints
- ✅ **Hostname validation:** No production hosts
- ✅ **Isolated test network:** Toxiproxy Docker container
- ✅ **Test databases only:** Never production

**Requirement:** Weekly CI pipeline scheduled Sunday 2 AM UTC for chaos tests only

- ✅ **Schedule:** `cron: '0 2 * * 0'` (Sunday 2 AM UTC)
- ✅ **Manual trigger:** workflow_dispatch supported
- ✅ **Separate pipeline:** chaos-engineering-weekly.yml (not shared with other tests)
- ✅ **Chaos tests only:** `pytest tests/chaos/ -v -m chaos`

**Requirement:** pytest.ini updated with @pytest.mark.chaos marker configuration

- ✅ **Marker exists:** `chaos: Chaos engineering tests (failure injection, isolated environment, slow, weekly only)`
- ✅ **Descriptive text:** Explains isolation, slowness, weekly schedule
- ✅ **Verified:** `grep "chaos:" backend/pytest.ini` returns marker

**Requirement:** Comprehensive README documentation (chaos tests, fixtures, CI pipeline, troubleshooting)

- ✅ **311 lines:** Comprehensive documentation
- ✅ **29 sections:** All aspects covered
- ✅ **Purpose:** Document chaos engineering goals and safety
- ✅ **Safety:** Blast radius controls (test databases only, isolated network, 60s limit)
- ✅ **Requirements:** Core and optional dependencies
- ✅ **Toxiproxy setup:** Docker, macOS Homebrew, verification
- ✅ **Running tests:** All chaos, specific categories, skip chaos
- ✅ **Test structure:** Directory tree with descriptions
- ✅ **Fixtures:** ChaosCoordinator, blast radius, network, database, memory, service
- ✅ **CI/CD pipeline:** Weekly schedule, steps, manual trigger
- ✅ **Troubleshooting:** Toxiproxy, missing deps, blast radius, timeout, Redis
- ✅ **Writing new tests:** Template reference, key requirements, example

**Requirement:** Chaos tests excluded from fast PR tests via marker (-m 'not chaos')

- ✅ **pytest.ini marker:** chaos marker configured
- ✅ **Fast PR tests:** `pytest tests/ -v -m "not chaos"`
- ✅ **Weekly pipeline:** `pytest tests/chaos/ -v -m chaos`
- ✅ **Separate pipelines:** Fast PR tests (<10 min) vs weekly chaos tests (~90 min)

## CI/CD Pipeline Architecture

### Weekly Chaos Engineering Pipeline

**File:** `.github/workflows/chaos-engineering-weekly.yml`

**Schedule:**
- Primary: Sunday 2 AM UTC (Saturday night in US, minimal traffic)
- Manual: `gh workflow run chaos-engineering-weekly.yml`

**Job Steps:**
1. Checkout code (actions/checkout@v4)
2. Set up Python 3.11 (actions/setup-python@v5)
3. Install dependencies (pytest, pytest-timeout, psutil)
4. Install chaos testing dependencies (toxiproxy-python, memory-profiler)
5. Start Toxiproxy (Docker container ghcr.io/shopify/toxiproxy:2.5.0)
6. Verify test environment (ENVIRONMENT=test, DATABASE_URL validation)
7. Run network latency chaos tests (pytest tests/chaos/test_network_latency_chaos.py -v -m chaos --timeout=120)
8. Run database drop chaos tests (pytest tests/chaos/test_database_drop_chaos.py -v -m chaos --timeout=120)
9. Run memory pressure chaos tests (pytest tests/chaos/test_memory_pressure_chaos.py -v -m chaos --timeout=120)
10. Run service crash chaos tests (pytest tests/chaos/test_service_crash_chaos.py -v -m chaos --timeout=120)
11. Run blast radius control tests (pytest tests/chaos/test_blast_radius_controls.py -v -m chaos --timeout=120)
12. Run recovery validation tests (pytest tests/chaos/test_recovery_validation.py -v -m chaos --timeout=120)
13. Run all chaos tests comprehensive (pytest tests/chaos/ -v -m chaos --timeout=120 --junitxml=chaos-test-results.xml)
14. Upload test results (chaos-test-results.xml, 30-day retention)
15. File bugs for failures (BugFilingService integration)
16. Cleanup Toxiproxy (docker stop toxiproxy, docker rm toxiproxy)
17. Notify on failure (CI URL printed)

**Timeout Configuration:**
- Job timeout: 90 minutes
- Per-test timeout: 120 seconds

**Artifacts:**
- chaos-test-results.xml (30-day retention)

**Bug Filing:**
- Automatic GitHub issue creation on failure
- BugFilingService integration from Phase 236

## Patterns Established

### 1. Weekly Chaos Engineering Pipeline Pattern

```yaml
on:
  schedule:
    - cron: '0 2 * * 0'  # Sunday 2 AM UTC
  workflow_dispatch:  # Allow manual trigger
```

**Benefits:**
- Scheduled execution during minimal traffic
- Manual trigger for ad-hoc chaos testing
- Separate from fast PR tests
- Isolated test environment

### 2. Toxiproxy Docker Container Pattern

```bash
docker run -d --name toxiproxy -p 8474:8474 ghcr.io/shopify/toxiproxy:2.5.0
```

**Benefits:**
- Network latency simulation (slow 3G)
- Isolated test network
- Automated setup and cleanup
- Consistent chaos injection

### 3. Environment Validation Pattern

```bash
export ENVIRONMENT=test
export DATABASE_URL=sqlite:///./test_chaos.db

# Verify no production access
if echo "$DATABASE_URL" | grep -i "production"; then
  echo "ERROR: Production database detected!"
  exit 1
fi
```

**Benefits:**
- Prevents production access
- Enforces test environment only
- Database URL validation
- Blast radius enforcement

### 4. Separate Test Category Runs Pattern

```bash
pytest tests/chaos/test_network_latency_chaos.py -v -m chaos --timeout=120
pytest tests/chaos/test_database_drop_chaos.py -v -m chaos --timeout=120
pytest tests/chaos/test_memory_pressure_chaos.py -v -m chaos --timeout=120
pytest tests/chaos/test_service_crash_chaos.py -v -m chaos --timeout=120
```

**Benefits:**
- Better error reporting (separate test runs)
- Faster failure identification
- Per-category timeout configuration
- Easier debugging

### 5. Comprehensive README Documentation Pattern

**README Structure (29 sections):**
1. Purpose
2. Safety
3. Requirements (Core Dependencies)
4. Requirements (Optional Dependencies)
5. Toxiproxy Setup
6. Running Tests (All Chaos Tests)
7. Running Tests (Specific Chaos Categories)
8. Running Tests (Blast Radius and Recovery Tests)
9. Running Tests (Skip Chaos Tests)
10. Test Structure
11. Fixtures (ChaosCoordinator)
12. Fixtures (Blast Radius Controls)
13. Fixtures (Network Chaos Fixtures)
14. Fixtures (Database Chaos Fixtures)
15. Fixtures (Memory Chaos Fixtures)
16. Fixtures (Service Crash Fixtures)
17. CI/CD Pipeline (Weekly Execution)
18. Troubleshooting (Toxiproxy Not Available)
19. Troubleshooting (Tests Skipped Due to Missing Dependencies)
20. Troubleshooting (Blast Radius Check Failed)
21. Troubleshooting (Test Timeout)
22. Troubleshooting (Redis Not Available)
23. Writing New Chaos Tests
24. See Also

**Benefits:**
- Complete documentation for developers
- Troubleshooting guide for common issues
- Toxiproxy setup instructions (Docker, macOS Homebrew)
- Running tests examples (all, specific categories, skip)
- Test structure and fixtures documentation
- CI/CD pipeline description
- Writing new tests guide

## Deviations from Plan

### None - Plan Executed Successfully

All tasks completed as specified:
- ✅ Weekly CI pipeline created (125 lines)
- ✅ pytest.ini updated with enhanced chaos marker
- ✅ Comprehensive README created (311 lines, 29 sections)
- ✅ Environment validation (test only, no production access)
- ✅ Toxiproxy integration (Docker container)
- ✅ Separate test category runs (network, database, memory, service)
- ✅ Bug filing integration on failure
- ✅ Troubleshooting guide included

## Verification Results

All verification steps passed:

1. ✅ **Weekly CI pipeline** - .github/workflows/chaos-engineering-weekly.yml (125 lines)
2. ✅ **Schedule configured** - Sunday 2 AM UTC (cron: '0 2 * * 0')
3. ✅ **Manual trigger** - workflow_dispatch supported
4. ✅ **Toxiproxy integration** - Docker container ghcr.io/shopify/toxiproxy:2.5.0
5. ✅ **Environment validation** - ENVIRONMENT=test, DATABASE_URL validation
6. ✅ **Separate test runs** - Network, database, memory, service categories
7. ✅ **Bug filing integration** - BugFilingService on failure
8. ✅ **pytest.ini marker** - chaos marker with descriptive text
9. ✅ **README comprehensive** - 311 lines, 29 sections
10. ✅ **YAML syntax valid** - Python yaml.safe_load() passed
11. ✅ **pytest.ini marker verified** - grep returns marker
12. ✅ **README exists** - wc -l returns 311 lines
13. ✅ **README sections** - 29 sections (grep -c "^##" returns 29)

## Test Execution

### Manual Trigger (Ad-Hoc Chaos Testing)

```bash
# Trigger chaos engineering workflow manually
gh workflow run chaos-engineering-weekly.yml

# View workflow run
gh run list --workflow=chaos-engineering-weekly.yml

# View workflow logs
gh run view [run-id]
```

### Local Chaos Testing

```bash
# Run all chaos tests
cd backend
pytest tests/chaos/ -v -m chaos

# Run specific chaos category
pytest tests/chaos/test_network_latency_chaos.py -v -m chaos

# Skip chaos tests (fast PR tests)
pytest tests/ -v -m "not chaos"
```

### Toxiproxy Setup (Local Development)

```bash
# Docker (recommended)
docker run -d --name toxiproxy -p 8474:8474 ghcr.io/shopify/toxiproxy:2.5.0

# Verify Toxiproxy
curl http://localhost:8474/proxies

# Cleanup
docker stop toxiproxy
docker rm toxiproxy
```

## Next Phase Readiness

✅ **Chaos engineering weekly CI pipeline and documentation complete** - CHAOS-08 requirement satisfied

**Ready for:**
- Phase 242: Unified Bug Discovery Pipeline
- Phase 243: Memory & Performance Bug Discovery
- Phase 244: AI-Enhanced Bug Discovery
- Phase 245: Feedback Loops & ROI Tracking

**Chaos Engineering Infrastructure Established:**
- Weekly CI pipeline (Sunday 2 AM UTC)
- Toxiproxy integration for network chaos
- Environment validation (test only, no production access)
- Separate test category runs (network, database, memory, service)
- Comprehensive README documentation (311 lines, 29 sections)
- pytest.ini chaos marker with descriptive text
- Bug filing integration on failure
- Troubleshooting guide

## Self-Check: PASSED

All files created:
- ✅ .github/workflows/chaos-engineering-weekly.yml (125 lines)
- ✅ backend/tests/chaos/README.md (311 lines)

All files modified:
- ✅ backend/pytest.ini (1 line changed)

All commits exist:
- ✅ f31ef9a67 - Task 1: Weekly CI pipeline for chaos engineering
- ✅ 11badaf99 - Task 2: Update pytest.ini with chaos marker
- ✅ 55aacdc4d - Task 3: Comprehensive chaos testing README

All verification passed:
- ✅ Weekly CI pipeline created (125 lines)
- ✅ Schedule configured (Sunday 2 AM UTC)
- ✅ Toxiproxy integration (Docker container)
- ✅ Environment validation (test only, no production access)
- ✅ Separate test category runs (network, database, memory, service)
- ✅ Bug filing integration on failure
- ✅ pytest.ini marker updated (enhanced description)
- ✅ README comprehensive (311 lines, 29 sections)
- ✅ YAML syntax valid
- ✅ All success criteria met (CHAOS-08)

---

*Phase: 241-chaos-engineering-integration*
*Plan: 07*
*Completed: 2026-03-25*
