# Cross-Platform CI Workflows - Phase 099

**Purpose:** Document all CI workflows for cross-platform testing (web, mobile, desktop).

**Updated:** 2026-02-27

## Overview

Atom uses 4 separate CI workflows to test all platforms independently, then aggregates coverage:

1. **Web Tests** - Jest + Playwright E2E (backend + frontend)
2. **Mobile Tests** - Jest + Expo (React Native)
3. **Desktop Tests** - Cargo test + tarpaulin (Tauri integration tests)
4. **Unified Tests** - Aggregates coverage from all 3 platforms

## Workflow Matrix

| Platform | Test Framework | Unit Tests | Integration Tests | E2E Tests | Property Tests | Workflow File |
|----------|---------------|-----------|-------------------|-----------|----------------|---------------|
| Web | Jest, Playwright | 821 (Frontend) | 200+ (Backend) | 61 (Playwright) | 28 (FastCheck) | `.github/workflows/unified-tests.yml` |
| Mobile | Jest (expo) | 82 (Expo) | 44 (Integration) | **BLOCKED** (Detox) | 13 (FastCheck) | `.github/workflows/mobile-tests.yml` |
| Desktop | Cargo test | 12 (Rust) | 54 (Tauri IPC) | **BLOCKED** (tauri-driver) | 35 (Rust proptest) | `.github/workflows/desktop-tests.yml` |

## 1. Web Tests Workflow

**File:** `.github/workflows/unified-tests.yml`

**Purpose:** Test web platform (backend + frontend) with Jest and Playwright.

**Triggers:**
- Push to `main` or `develop`
- Pull request to `main` or `develop`
- Manual workflow dispatch

**Jobs:**

### Job 1: Backend Tests
```yaml
backend-tests:
  runs-on: ubuntu-latest
  timeout-minutes: 15
  steps:
    - Checkout code
    - Setup Python 3.11
    - Install dependencies (pip install)
    - Run pytest with coverage
    - Upload coverage artifact (backend-coverage)
```

**Tests Run:**
- 500+ backend unit tests
- 200+ backend integration tests
- 361 Hypothesis property tests

**Coverage:** `backend/tests/coverage/coverage.json` (pytest-json-report format)

### Job 2: Frontend Tests
```yaml
frontend-tests:
  runs-on: ubuntu-latest
  timeout-minutes: 15
  steps:
    - Checkout code
    - Setup Node.js 20
    - Install dependencies (npm ci)
    - Run Jest with coverage
    - Upload coverage artifact (frontend-coverage)
```

**Tests Run:**
- 821 Jest unit tests (Frontend)
- 147 integration tests
- 28 FastCheck property tests

**Coverage:** `frontend-nextjs/coverage/coverage-final.json` (Jest format)

### Job 3: E2E Tests (Playwright)
```yaml
e2e-tests:
  runs-on: ubuntu-latest
  timeout-minutes: 30
  steps:
    - Checkout code
    - Setup Python 3.11
    - Install dependencies
    - Start backend server (background)
    - Run Playwright E2E tests
    - Upload test artifacts
```

**Tests Run:**
- 61 Playwright E2E tests
- Cross-platform workflow tests (test_shared_workflows.py)
- Feature parity tests (test_feature_parity.py)

**Artifacts:** Screenshots, videos, traces (retention 7 days)

**Test Files:**
- `backend/tests/e2e_ui/tests/cross-platform/test_shared_workflows.py`
- `backend/tests/e2e_ui/tests/cross-platform/test_feature_parity.py`

### Job 4: Coverage Aggregation
```yaml
coverage-aggregation:
  runs-on: ubuntu-latest
  needs: [backend-tests, frontend-tests]
  steps:
    - Checkout code
    - Download backend coverage artifact
    - Download frontend coverage artifact
    - Run aggregate_coverage.py script
    - Upload aggregated coverage report
```

**Output:** `backend/tests/coverage_reports/unified/coverage.json` (all platforms)

## 2. Mobile Tests Workflow

**File:** `.github/workflows/mobile-tests.yml`

**Purpose:** Test mobile platform (React Native) with Jest and Expo.

**Triggers:**
- Push to `main` or `develop`
- Pull request to `main` or `develop`
- Manual workflow dispatch

**Jobs:**

### Job 1: Mobile Tests
```yaml
mobile-tests:
  runs-on: macos-latest  # Required for iOS compatibility
  timeout-minutes: 15
  steps:
    - Checkout code
    - Setup Node.js 20
    - Install dependencies (npm ci)
    - Run Jest with expo (maxWorkers=2)
    - Upload coverage artifact (mobile-coverage)
```

**Tests Run:**
- 82 Expo unit tests (Mobile)
- 44 integration tests
- 13 FastCheck property tests

**Coverage:** `mobile/coverage/coverage-final.json` (jest-expo format)

**Note:** E2E tests **BLOCKED** by Detox expo-dev-client requirement (deferred to post-v4.0).

## 3. Desktop Tests Workflow

**File:** `.github/workflows/desktop-tests.yml`

**Purpose:** Test desktop platform (Tauri) with Cargo test and tarpaulin.

**Triggers:**
- Push to `main` or `develop`
- Pull request to `main` or `develop`
- Manual workflow dispatch

**Jobs:**

### Job 1: Desktop Tests
```yaml
test:
  runs-on: ubuntu-latest  # x86_64 for tarpaulin compatibility
  timeout-minutes: 15
  steps:
    - Checkout code
    - Install Rust toolchain (stable)
    - Cache cargo registry, index, and build
    - Install tarpaulin (cargo install)
    - Run cargo test --verbose
    - Generate coverage with tarpaulin
    - Upload coverage artifact (desktop-coverage)
```

**Tests Run:**
- 12 Rust unit tests
- 54 Tauri integration tests (IPC commands)
- 35 Rust property tests (proptest)

**Coverage:** `frontend-nextjs/src-tauri/coverage/coverage.json` (tarpaulin JSON format)

**Note:** E2E tests **BLOCKED** by tauri-driver unavailability (deferred to post-v4.0).

**Test Files:**
- `frontend-nextjs/src-tauri/tests/commands_test.rs` (1,058 lines)
- `frontend-nextjs/src-tauri/tests/websocket_test.rs` (582 lines)
- `frontend-nextjs/src-tauri/tests/device_capabilities_test.rs` (709 lines)
- `frontend-nextjs/src-tauri/tests/canvas_integration_test.rs` (358 lines)
- `frontend-nextjs/src-tauri/tests/file_dialog_integration_test.rs` (343 lines)
- `frontend-nextjs/src-tauri/tests/cross_platform_validation_test.rs` (481 lines)
- `frontend-nextjs/src-tauri/tests/window_state_proptest.rs` (527 lines)
- `frontend-nextjs/src-tauri/tests/file_operations_proptest.rs` (604 lines)
- `frontend-nextjs/src-tauri/tests/ipc_serialization_proptest.rs` (608 lines)
- Plus 12 more test files (8,083 total lines)

## 4. Unified Coverage Aggregation

**File:** `backend/tests/scripts/coverage_reports/unified/aggregate_coverage.py`

**Purpose:** Aggregate coverage from all 3 platforms into a single report.

**Triggers:** After all platform-specific workflows complete successfully.

**Input:**
- `backend-coverage` artifact (pytest-json-report format)
- `frontend-coverage` artifact (Jest format)
- `mobile-coverage` artifact (jest-expo format, optional)
- `desktop-coverage` artifact (tarpaulin format, optional)

**Output:**
- `backend/tests/coverage_reports/unified/coverage.json` (aggregated coverage)
- PR comment with coverage breakdown table (on failure)

**Coverage Formula:**
```
overall_coverage = (covered_backend + covered_frontend + covered_mobile + covered_desktop) /
                   (total_backend + total_frontend + total_mobile + total_desktop)
```

**Graceful Degradation:**
- Mobile coverage optional (ARM Macs, CI environments) - continue on error
- Desktop coverage optional (tarpaulin x86_64 only) - continue on error

## Workflow Timing

| Workflow | Duration | Timeout | Parallel Jobs |
|----------|----------|---------|---------------|
| Web Tests | ~10 min | 15-30 min | 3 (backend, frontend, E2E) |
| Mobile Tests | ~5 min | 15 min | 1 (iOS compatible) |
| Desktop Tests | ~8 min | 15 min | 1 (x86_64 only) |
| **Total** | **~23 min** | - | **5 parallel jobs** |

## Quality Gates

### Pass Rate Threshold
- **Target:** 98% pass rate across all platforms
- **Current:** 100% (1,048/1,048 frontend tests passing)

### Coverage Threshold
- **Target:** 80% overall coverage (weighted average)
- **Current:** 20.81% (Phase 098-06)
  - Backend: 21.67%
  - Frontend: 3.45%
  - Mobile: 16.16%
  - Desktop: TBD (requires x86_64)

**Note:** Coverage below target is acceptable for Phase 095 (test infrastructure focused). Coverage expansion will happen in subsequent phases.

## Artifacts

### Coverage Artifacts (retention 7 days)
- `backend-coverage` - pytest coverage JSON
- `frontend-coverage` - Jest coverage JSON
- `mobile-coverage` - jest-expo coverage JSON (optional)
- `desktop-coverage` - tarpaulin coverage JSON (optional)

### Test Artifacts (retention 7 days)
- `e2e-web-artifacts` - Playwright screenshots, videos, traces
- `e2e-mobile-artifacts` - Detox artifacts (when unblocked)
- `e2e-desktop-artifacts` - WebDriverIO artifacts (when unblocked)

## Blocked E2E Tests

### Mobile E2E (Detox)
- **Status:** BLOCKED by expo-dev-client requirement
- **Impact:** Cannot run Detox E2E tests in CI
- **Workaround:** Use 194 Jest tests (100% pass rate, 16.16% coverage)
- **Timeline:** Defer to post-v4.0

### Desktop E2E (WebDriverIO)
- **Status:** BLOCKED by tauri-driver unavailability
- **Impact:** Cannot run WebDriverIO E2E tests in CI
- **Workaround:** Use 54 Tauri integration tests (IPC commands)
- **Timeline:** Defer to post-v4.0

## Cross-Platform Test Contracts

**See:** `backend/tests/e2e_ui/tests/cross-platform/CONTRACT.md`

**Contracts Defined:**
1. AUTH-001: Authentication Workflow
2. AGENT-001: Agent Execution Workflow
3. CANVAS-001: Canvas Presentation Workflow
4. SKILL-001: Skill Execution Workflow
5. DATA-001: Data Persistence Workflow
6. DEVICE-001: Device Capabilities Workflow
7. FEATURE-PARITY-001: Agent Chat Features
8. WINDOW-001: Window Management Workflow

**Contract Mapping:**
- Web: `test_shared_workflows.py` + `test_feature_parity.py` (Playwright)
- Mobile: Deferred (Detox BLOCKED)
- Desktop: `commands_test.rs` + `canvas_integration_test.rs` + `device_capabilities_test.rs` (Tauri IPC)

## Running Workflows Locally

### Web Tests
```bash
# Backend tests
cd backend
pytest tests/ -v

# Frontend tests
cd frontend-nextjs
npm test

# E2E tests (Playwright)
cd backend
pytest tests/e2e_ui/ -v
```

### Mobile Tests
```bash
cd mobile
npm test
```

### Desktop Tests
```bash
cd frontend-nextjs/src-tauri
cargo test

# With coverage
./coverage.sh
```

## CI/CD Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        GitHub Push/PR                           │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     ▼
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
┌───────────────┐        ┌───────────────┐
│ Web Tests     │        │ Mobile Tests  │
│ (3 parallel)  │        │ (macOS only)  │
└───────┬───────┘        └───────┬───────┘
        │                        │
        └────────────┬───────────┘
                     │
                     ▼
        ┌────────────┴────────────┐
        │                         │
        ▼                         ▼
┌───────────────┐        ┌───────────────┐
│ Desktop Tests │        │ Unified       │
│ (x86_64 only) │        │ Coverage      │
└───────────────┘        └───────────────┘
```

## Recommendations

### For Phase 099
1. ✅ **Use existing CI workflows** - All 3 platforms have operational CI
2. ✅ **Focus on cross-platform contracts** - Document what tests map across platforms
3. ✅ **Skip E2E for mobile/desktop** - Blocked by Detox and tauri-driver

### Post-v4.0
1. **Revisit Detox E2E** - Check if expo-dev-client requirement can be resolved
2. **Revisit tauri-driver** - Check if official WebDriver support is released
3. **Add E2E workflows** - Create `.github/workflows/e2e-mobile.yml` and `e2e-desktop.yml`

## See Also

- `backend/tests/e2e_ui/tests/cross-platform/CONTRACT.md` - Cross-platform test contracts
- `frontend-nextjs/wdio/README.md` - WebDriverIO setup (BLOCKED - tauri-driver unavailable)
- `.planning/phases/099-cross-platform-integration/TAURI_INTEGRATION_TESTS.md` - Desktop test catalog
- `backend/tests/scripts/coverage_reports/unified/aggregate_coverage.py` - Coverage aggregation script

---

*Last updated: 2026-02-27*
*Phase: 099-cross-platform-integration*
*Status: All 3 platforms have operational CI (web, mobile, desktop)*
*E2E: Web ✅ (61 tests), Mobile ⏸️ (BLOCKED), Desktop ⏸️ (BLOCKED)*
