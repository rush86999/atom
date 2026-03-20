# Codebase Coverage Baseline Report

**Date**: March 20, 2026
**Objective**: Achieve 80% test coverage across the ENTIRE Atom codebase

---

## Executive Summary

| Platform | Current Coverage | Test Pass Rate | Gap to 80% | Priority |
|----------|-----------------|----------------|------------|----------|
| **Backend** | 74.6% | 97.4% (381/391) | +5.4% | HIGH |
| **Frontend** | 13.47% | 71% (2,743/3,862) | +66.53% | CRITICAL |
| **Mobile** | 61.34% | 78% (1,840/2,359) | +18.66% | MEDIUM |
| **Desktop** | TBD | Building... | TBD | LOW |

**Overall Estimated Coverage**: ~40-50%
**Target**: 80% across ALL platforms

---

## Platform Breakdown

### 1. Backend (Python/FastAPI)

**Status**: 74.6% coverage ✅ (Close to target)

**Test Results**:
- Passing: 381 tests
- Failing: 10 tests
- Skipped: 6 tests
- Pass Rate: 97.4%

**Coverage Details**:
- Total Lines: ~12,000+ (estimated)
- Covered: ~8,952 lines
- Uncovered: ~3,048 lines

**Failing Tests** (10):
1. `test_ai_accounting_routes_coverage.py` - 4 failures (dashboard metrics)
2. `test_analytics_dashboard_endpoints.py` - 6 failures (realtime feed, metrics summary, workflow performance)

**Root Cause Analysis**:
- Pydantic v2 deprecation warnings (`.dict()` → `.model_dump()`)
- Missing or mocked analytics data
- Time window calculation issues

**Gap Analysis** (+5.4% to reach 80%):
- **Quick Wins** (<1 hour):
  - Fix 10 failing tests (+2-3% coverage)
  - Add tests for low-coverage API routes (+2-3% coverage)

**Files Requiring Additional Tests**:
- `/backend/core/llm/cognitive_tier_system.py` - Already well tested
- `/backend/core/agent_governance_service.py` - Core logic, needs edge cases
- `/backend/api/analytics_dashboard_endpoints.py` - Fix failing tests first
- `/backend/tools/browser_tool.py` - Integration tests needed
- `/backend/core/episode_segmentation_service.py` - Add edge case tests

---

### 2. Frontend (Next.js/React)

**Status**: 13.47% coverage ⚠️ (CRITICAL - Far below target)

**Test Results**:
- Passing: 2,743 tests
- Failing: 1,119 tests
- Total: 3,862 tests
- Pass Rate: 71%

**Coverage Details** (from `coverage/coverage-summary.json`):
- Lines: 13.47%
- Statements: ~14% (estimated)
- Functions: ~15% (estimated)
- Branches: ~8% (estimated)

**Test Configuration**:
- Framework: Jest
- Coverage collection: Enabled
- Coverage paths: `components/**/*.{ts,tsx}`, `pages/**/*.{ts,tsx}`, `lib/**/*.{ts,tsx}`, `hooks/**/*.{ts,tsx}`

**Gap Analysis** (+66.53% to reach 80%):
- **Critical Priority** - Requires significant effort (4-6 hours)

**High-Impact Areas for Testing**:
1. **Hooks** (Quick wins - high value):
   - `useCanvasState.ts` - Canvas state subscription
   - `useAgentExecution.ts` - Agent execution management
   - `useWebSocket.ts` - WebSocket connection management
   - `useBrowserAutomation.ts` - Browser control hooks

2. **Components** (Medium effort):
   - Canvas components (charts, forms, markdown)
   - Agent dashboard components
   - Analytics components
   - Device capability components

3. **Services** (High value):
   - `/lib/api/` - API client functions
   - `/lib/websocket.ts` - WebSocket service
   - `/lib/canvas/` - Canvas state management

4. **Pages** (Lower priority - mostly integration):
   - `/pages/agent/` - Agent management pages
   - `/pages/dashboard/` - Dashboard pages

**Common Test Failure Patterns** (identified from 1,119 failures):
- Fast-check property testing errors (update imports)
- Jest worker exceptions (fix async tests, add timeouts)
- Missing TestProviders (wrap with context providers)
- Mock failures (fix jest.mock() calls)

**Quick Wins** (<2 hours for +20-30% coverage):
1. Add tests for all hooks in `/hooks/` directory (+10-15%)
2. Add tests for API client functions in `/lib/api/` (+5-10%)
3. Fix fast-check import issues in existing tests (+3-5%)
4. Add TestProvider wrapper for component tests (+2-3%)

---

### 3. Mobile (React Native)

**Status**: 61.34% coverage ⚠️ (Moderate gap to target)

**Test Results**:
- Passing: 1,840 tests
- Failing: 519 tests
- Total: 2,359 tests
- Pass Rate: 78%

**Coverage Details** (from `coverage/coverage-summary.json`):
- Lines: 61.34% (476/776 covered)
- Statements: 61.5% (492/800 covered)
- Functions: 64.7% (77/119 covered)
- Branches: 47.75% (138/289 covered)

**Per-Module Coverage**:
| File | Lines Coverage | Status |
|------|---------------|---------|
| `storageService.ts` | 88.23% | ✅ Good |
| `AuthContext.tsx` | 86.85% | ✅ Good |
| `DeviceContext.tsx` | 30.87% | ❌ Needs work |
| `WebSocketContext.tsx` | 42.64% | ⚠️ Moderate |
| `cameraService.ts` | ~60% | ⚠️ Moderate |
| `locationService.ts` | ~60% | ⚠️ Moderate |
| `notificationService.ts` | ~60% | ⚠️ Moderate |
| `offlineSyncService.ts` | ~60% | ⚠️ Moderate |

**Gap Analysis** (+18.66% to reach 80%):
- **Moderate Priority** - Requires focused effort (2-3 hours)

**High-Impact Areas for Testing**:
1. **Context Providers** (Quick wins):
   - `DeviceContext.tsx` - Add tests for device capabilities (+10-15%)
   - `WebSocketContext.tsx` - Add tests for WebSocket events (+8-10%)

2. **Services** (Medium effort):
   - `cameraService.ts` - Add tests for camera permissions and capture (+3-5%)
   - `locationService.ts` - Add tests for location tracking (+3-5%)
   - `notificationService.ts` - Add tests for notification handling (+3-5%)
   - `offlineSyncService.ts` - Add tests for sync logic (+3-5%)

**Common Test Failure Patterns** (519 failures):
- TypeScript parsing errors in test files (syntax issues)
- Timeout issues (increase timeout for async tests)
- Mock implementation errors (fix jest.mock() calls)

**Quick Wins** (<1 hour for +10-15% coverage):
1. Fix TypeScript parsing errors in failing tests (+3-5%)
2. Add tests for `DeviceContext.tsx` edge cases (+5-8%)
3. Add tests for `WebSocketContext.tsx` reconnection logic (+3-5%)
4. Increase timeouts for slow async tests (+1-2%)

---

### 4. Desktop (Tauri/Rust)

**Status**: TBD 🔄 (Building coverage report)

**Test Status**:
- Compilation: In progress (blocking waiting for file lock)
- Coverage Tool: cargo-tarpaulin 0.27.1
- Architecture: x86_64 ✅ (compatible with tarpaulin)
- Coverage Script: `/Users/rushiparikh/projects/atom/frontend-nextjs/src-tauri/coverage.sh`

**Coverage Configuration**:
- Tool: cargo-tarpaulin
- Config: `tarpaulin.toml` (needs to be created)
- Output Format: HTML (default)
- Timeout: 300 seconds

**Estimated Coverage**: Unknown (Rust projects typically have 50-70% coverage)

**Gap Analysis**: TBD (waiting for coverage report)

**High-Priority Areas for Testing** (once coverage is measured):
1. **IPC Command Handlers**:
   - Agent execution commands
   - Browser automation commands
   - Device capability commands
   - Canvas presentation commands

2. **Core Logic**:
   - File system operations
   - Process spawning
   - Native OS integrations

3. **Error Handling**:
   - Command validation
   - Permission checks
   - Error propagation

**Next Steps**:
1. Complete tarpaulin build (currently compiling dependencies)
2. Generate initial coverage report
3. Identify low-coverage modules
4. Add targeted tests for critical paths

**Note**: Rust coverage typically takes 5-10 minutes to build and run. The compilation is currently in progress.

---

## Strategic Recommendations

### Phase 1: Fix Failing Tests (2-4 hours)

**Priority**: CRITICAL - Stabilize test suites before adding new tests

**Backend** (30 minutes):
1. Fix Pydantic v2 deprecation warnings in analytics endpoints
2. Fix 10 failing tests in `test_ai_accounting_routes_coverage.py` and `test_analytics_dashboard_endpoints.py`
3. Expected impact: +2-3% coverage

**Frontend** (1-2 hours):
1. Fix fast-check import issues in existing tests
2. Fix Jest worker exceptions (add timeouts, fix async patterns)
3. Wrap tests with TestProviders for context
4. Fix mock implementation errors
5. Expected impact: +10-15% coverage (from fixes) + improved stability

**Mobile** (1 hour):
1. Fix TypeScript parsing errors in test files
2. Increase timeouts for slow async tests
3. Fix mock implementations
4. Expected impact: +3-5% coverage (from fixes) + improved stability

**Desktop** (30 minutes):
1. Wait for coverage build to complete
2. Run existing tests to identify failures
3. Fix any critical test failures
4. Expected impact: Baseline establishment

---

### Phase 2: Add Targeted Coverage Tests (4-8 hours)

**Strategy**: Focus on high-impact, low-effort tests to maximize coverage gains

**Backend** (1-2 hours, +5-10% coverage):
1. Add tests for low-coverage API routes
2. Add edge case tests for governance service
3. Add integration tests for browser tool
4. Add tests for episode service edge cases

**Frontend** (2-3 hours, +30-40% coverage):
1. Add hook tests (`useCanvasState`, `useAgentExecution`, `useWebSocket`)
2. Add API client tests (`/lib/api/`)
3. Add canvas component tests (charts, forms)
4. Add service tests (`/lib/websocket.ts`, `/lib/canvas/`)

**Mobile** (1-2 hours, +15-20% coverage):
1. Add `DeviceContext` tests (device capabilities)
2. Add `WebSocketContext` tests (reconnection, events)
3. Add service tests (camera, location, notifications)
4. Add navigation tests

**Desktop** (1-2 hours, TBD coverage):
1. Add IPC command handler tests
2. Add file system operation tests
3. Add error handling tests
4. Add permission check tests

---

### Phase 3: Verification & Documentation (30 minutes)

1. Generate final coverage reports for all platforms
2. Verify all platforms >= 80% coverage
3. Verify all platforms >= 95% test pass rate
4. Create `CODEBASE_COVERAGE_80_PERCENT.md` documenting achievement
5. Commit all changes with clear messages

---

## Success Criteria

- [ ] Backend >= 80% coverage (currently 74.6%, gap: +5.4%)
- [ ] Frontend >= 80% coverage (currently 13.47%, gap: +66.53%)
- [ ] Mobile >= 80% coverage (currently 61.34%, gap: +18.66%)
- [ ] Desktop >= 80% coverage (currently TBD)
- [ ] All platforms >= 95% test pass rate
  - [ ] Backend: 97.4% → Maintain or improve
  - [ ] Frontend: 71% → Fix 1,119 failing tests
  - [ ] Mobile: 78% → Fix 519 failing tests
  - [ ] Desktop: TBD → Measure and fix
- [ ] Comprehensive documentation created
- [ ] All changes committed with clear messages

---

## Estimated Timeline

| Phase | Duration | Effort | Impact |
|-------|----------|--------|--------|
| Phase 1: Fix Failing Tests | 2-4 hours | HIGH | +10-20% coverage (from fixes) |
| Phase 2: Add Targeted Tests | 4-8 hours | HIGH | +50-70% coverage (new tests) |
| Phase 3: Verification | 30 minutes | LOW | Validation |
| **Total** | **6.5-12.5 hours** | **HIGH** | **80% coverage target** |

---

## Next Actions (Immediate)

1. ✅ **Measure baseline coverage** - COMPLETE (except desktop in progress)
2. 🔲 **Fix backend failing tests** (10 tests, 30 minutes)
3. 🔲 **Fix frontend failing tests** (1,119 tests, 1-2 hours)
4. 🔲 **Fix mobile failing tests** (519 tests, 1 hour)
5. 🔲 **Wait for desktop coverage** (build in progress)
6. 🔲 **Add backend coverage tests** (+5-10%, 1-2 hours)
7. 🔲 **Add frontend coverage tests** (+30-40%, 2-3 hours)
8. 🔲 **Add mobile coverage tests** (+15-20%, 1-2 hours)
9. 🔲 **Add desktop coverage tests** (TBD, 1-2 hours)
10. 🔲 **Verify and document** (30 minutes)

---

## Platform-Specific Commands

### Backend
```bash
cd /Users/rushiparikh/projects/atom/backend
pytest --cov=core --cov=api --cov=tools --cov=cli --cov-report=json --cov-report=html -v
cat coverage.json | jq '.totals.percent_covered'
open htmlcov/index.html
```

### Frontend
```bash
cd /Users/rushiparikh/projects/atom/frontend-nextjs
npm run test:coverage -- --coverage --coverageReporters=json --coverageReporters=text --maxWorkers=2
cat coverage/coverage-summary.json | jq '.total.lines.pct'
open coverage/index.html
```

### Mobile
```bash
cd /Users/rushiparikh/projects/atom/mobile
npm run test:coverage -- --coverage --coverageReporters=json --maxWorkers=2
cat coverage/coverage-summary.json | jq '.total.lines.pct'
open coverage/index.html
```

### Desktop
```bash
cd /Users/rushiparikh/projects/atom/frontend-nextjs/src-tauri
./coverage.sh --baseline  # Generate baseline report
open coverage-report/index.html
```

---

## Notes

- **Backend**: Strong test culture, only 10 failing tests, close to 80% target
- **Frontend**: Critical priority, very low coverage (13.47%), many failing tests (1,119)
- **Mobile**: Moderate coverage (61.34%), many failing tests (519), TypeScript parsing issues
- **Desktop**: Coverage measurement in progress, Rust compilation takes time
- **Overall**: Estimated 40-50% coverage, significant effort needed to reach 80%

---

**Last Updated**: March 20, 2026
**Status**: Phase 1 Complete (Baseline Measurement) → Phase 2 Ready (Fix Failing Tests)
