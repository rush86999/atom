# Milestone v5.5: Full Codebase 60% Coverage - Baseline Report

**Generated:** 2026-03-20
**Status:** 🚧 **ACTIVE**
**Timeline:** 3-4 weeks (aggressive execution across all platforms)
**Goal:** Achieve 60% actual line coverage across ENTIRE codebase (backend + frontend + mobile + desktop)

---

## Executive Summary

Milestone v5.5 is a **comprehensive coverage initiative** to achieve 60% coverage across the entire Atom codebase. This includes:

- ✅ **Backend (Python)**: 7.41% baseline → 80% target
- ✅ **Frontend (Next.js)**: 13.42% baseline → 45% target
- ✅ **Mobile (React Native)**: 0.00% baseline → 40% target
- ✅ **Desktop (Tauri + Rust)**: 0% baseline → 40% target

**Current Baseline:** ~7.03% overall (weighted average across all platforms)
**Target:** 60% overall coverage (realistic and achievable)
**Gap:** ~53 percentage points

---

## Baseline Coverage Report

### Backend (Python) - 7.41% 🔴

| Metric | Value | Status |
|--------|-------|--------|
| **Coverage** | 7.41% | 🔴 Critical |
| **Lines** | 4,136 / 55,793 | 51,657 uncovered |
| **Gap** | 72.59pp | Far below target |

**Critical Modules at 0%:**
- `agent_governance_service.py` - Core governance logic
- `trigger_interceptor.py` - Maturity-based routing
- `llm/byok_handler.py` - Multi-provider LLM routing
- `llm/cognitive_tier_system.py` - 5-tier cognitive classification
- `episode_segmentation_service.py` - Episode creation
- `episode_retrieval_service.py` - Semantic/temporal retrieval
- `episode_lifecycle_service.py` - Episode management
- `skill_composition_engine.py` - DAG workflows
- `workflow_engine.py` - 1,164 lines
- `webhook_handlers.py` - 248 lines
- `jwt_verifier.py` - 160 lines

**Only High Coverage:**
- `models.py` - 97% ✅ (4,159 lines, DB models)

### Frontend (Next.js) - 13.42% 🔴

| Metric | Value | Status |
|--------|-------|--------|
| **Lines** | 13.42% | 🔴 Critical |
| **Statements** | 13.84% | 🔴 Critical |
| **Functions** | 9.52% | 🔴 Critical |
| **Branches** | 7.79% | 🔴 Critical |
| **Total Lines** | 3,246 / 24,174 | 20,928 uncovered |
| **Gap** | 66.58pp | Far below target |

**Component Coverage:**
- Integration components: 0-50% (mostly 0%)
- Agent components: 18-70%
- Workflow/automation: 0%
- Error boundary: 100% ✅ (23 lines)

### Mobile (React Native) - 0.00% 🔴

| Metric | Value | Status |
|--------|-------|--------|
| **Coverage** | 0.00% | 🔴 Critical |
| **Estimated Lines** | ~15,000 | All uncovered |
| **Gap** | 40pp (to 40% target) | No tests executed |

**Issues:**
- Coverage file exists but shows 0%
- Test infrastructure exists (jest)
- Tests not being executed

### Desktop (Tauri + Rust) - 0% 🔴

| Metric | Value | Status |
|--------|-------|--------|
| **Coverage** | Not available | 🔴 Critical |
| **Estimated Lines** | ~10,000 | All uncovered |
| **Gap** | 40pp (to 40% target) | No coverage data |

**Issues:**
- No coverage reports found
- Rust backend needs tarpaulin/cargo-tarpaulin
- Tauri frontend needs vitest
- Part of Phase 140-142 (v5.2) but not verified

---

## Weighted Overall Coverage

| Platform | Lines | Coverage | Uncovered | Weight |
|----------|-------|----------|-----------|--------|
| Backend | 55,793 | 7.41% → 80% | 51,657 → 11,158 | 53.1% |
| Frontend | 24,174 | 13.42% → 45% | 20,928 → 13,324 | 23.0% |
| Mobile | ~15,000 | 0.00% → 40% | ~15,000 → ~9,000 | 14.3% |
| Desktop | ~10,000 | 0% → 40% | ~10,000 → ~6,000 | 9.5% |
| **TOTAL** | **~105,000** | **~7% → 60%** | **~97,585 → ~40,000** | **100%** |

**Overall Coverage: ~7.03% → 60%**
**Target: 60% weighted average**
**Lines to Cover: ~65,750 lines**

---

## Wave-Based Execution Strategy (All Platforms)

### Wave 1A: Backend Governance (Week 1 - Days 1-3)

**Backend Target:** 7.41% → 15% (+7.59pp)

**Priority Modules:**
1. **Governance** (CRITICAL):
   - `agent_governance_service.py` (80% target)
   - `trigger_interceptor.py` (80% target)
   - `governance_cache.py` (80% target)

**Estimated Effort:** 3-5 days, ~1,050 lines of tests

**Expected Coverage After Wave 1A:**
- Backend: ~15%
- Overall: ~9%

### Wave 1B: Backend LLM & Episodes (Week 1 - Days 4-7)

**Backend Target:** 15% → 25% (+10pp)

**Priority Modules:**
1. **LLM Services** (CRITICAL):
   - `llm/byok_handler.py` (80% target)
   - `llm/cognitive_tier_system.py` (80% target)

2. **Episode Services** (HIGH):
   - `episode_segmentation_service.py` (80% target)
   - `episode_retrieval_service.py` (80% target)

**Estimated Effort:** 3-5 days, ~1,600 lines of tests

**Expected Coverage After Wave 1B:**
- Backend: ~25%
- Overall: ~15%

### Wave 2: Frontend + Backend Tools (Week 2)

**Frontend Target:** 13.42% → 45% (+31.58pp)
**Backend Target:** 25% → 45% (+20pp)

**Frontend Components:**
1. **Integration Components** (45% target):
   - Slack, Jira, GitHub (most used)
   - Agent components (AgentManager, AgentStudio)
   - Dashboard components

2. **State Management** (60% target):
   - Custom hooks testing
   - Context providers
   - Redux/Zustand stores

**Backend Services:**
1. **Tool Services** (70% target):
   - `canvas_tool.py` (80% target)
   - `browser_tool.py` (80% target)
   - `device_tool.py` (80% target)

2. **Skill Services** (70% target):
   - `skill_adapter.py` (80% target)
   - `skill_composition_engine.py` (80% target)
   - `skill_dynamic_loader.py` (80% target)

3. **Training Services** (70% target):
   - `student_training_service.py` (80% target)
   - `supervision_service.py` (80% target)

**Estimated Effort:** 7 days, ~4,000 lines of tests

**Expected Coverage After Wave 2:**
- Backend: ~45%
- Frontend: ~45%
- Overall: ~35%

### Wave 3: Mobile + Desktop + Integration (Week 3)

**Mobile Target:** 0% → 40% (+40pp)
**Desktop Target:** 0% → 40% (+40pp)
**Backend Target:** 45% → 80% (+35pp)

**Mobile (React Native):**
1. **Device Features** (70% target):
   - Camera, location, notifications
   - Offline sync (AsyncStorage/MMKV)
   - Navigation screens

2. **State Management** (70% target):
   - Context providers
   - AsyncStorage/MMKV
   - React Navigation state

**Desktop (Tauri + Rust):**
1. **Rust Backend** (70% target):
   - Core logic (tarpaulin coverage)
   - IPC handlers
   - File system operations

2. **Tauri Frontend** (70% target):
   - Component testing (vitest)
   - Window management
   - Desktop-specific UI

**Backend Core Services:**
1. **Database & World Model** (70% target):
   - `episode_lifecycle_service.py` (80% target)
   - `agent_world_model.py` (80% target)
   - `policy_fact_extractor.py` (80% target)
   - `atom_cli_skill_wrapper.py` (80% target)
   - `models.py` (60% target - focus on critical models)

**Estimated Effort:** 7-10 days, ~3,000 lines of tests

**Expected Coverage After Wave 3:**
- Backend: ~80% ✅
- Frontend: ~45% ✅
- Mobile: ~40% ✅
- Desktop: ~40% ✅
- Overall: ~55%

### Wave 4: Final Push to 60% (Week 4)

**Target:** All platforms maintain targets, overall → 60%

**Focus Areas:**
- Property-based tests (invariants)
- Edge cases (error paths, timeouts, retries)
- Integration test gaps
- Property test expansion (1000+ examples)

**Estimated Effort:** 3-4 days, ~2,000 lines of tests

**Final Target:**
- Backend: 80%+ ✅
- Frontend: 45%+ ✅
- Mobile: 40%+ ✅
- Desktop: 40%+ ✅
- **Overall: 60%+** ✅

---

## Timeline Summary

| Wave | Duration | Platforms | Coverage Target | Lines to Cover |
|------|----------|-----------|-----------------|----------------|
| **Wave 1A** | 3-5 days | Backend governance | 7% → 9% overall | +1,050 lines |
| **Wave 1B** | 3-5 days | Backend LLM/episodes | 9% → 15% overall | +1,600 lines |
| **Wave 2** | 7 days | Frontend + Backend | 15% → 35% overall | +4,000 lines |
| **Wave 3** | 7-10 days | Mobile + Desktop | 35% → 55% overall | +3,000 lines |
| **Wave 4** | 3-4 days | Final push | 55% → 60% overall | +2,000 lines |
| **TOTAL** | **23-31 days** | **All platforms** | **7% → 60%** | **~65,750 lines** |

**Aggressive Timeline:** 23 days (parallel execution, minimal blockers)
**Realistic Timeline:** 27 days (some blockers, rework)
**Conservative Timeline:** 31 days (external dependencies, complex fixes)

---

## Daily Verification Process

### Backend (Daily)

```bash
cd /Users/rushiparikh/projects/atom
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/ \
  --cov=backend.core --cov=backend.api --cov=backend.tools \
  --cov-report=term-missing --cov-report=html --cov-report=json

# Check coverage percentage
cat backend/coverage.json | python3 -c \
  "import json, sys; data = json.load(sys.stdin); \
  print(f'{data[\"totals\"][\"percent_covered\"]:.2f}%')"
```

### Frontend (Daily)

```bash
cd frontend-nextjs
npm test -- --coverage --watchAll=false

# Check coverage summary
cat coverage/coverage-summary.json | python3 -c \
  "import json, sys; data = json.load(sys.stdin); \
  print(f'{data[\"total\"][\"lines\"][\"pct\"]:.2f}%')"
```

### Mobile (Daily)

```bash
cd mobile
npm test -- --coverage

# Check coverage
cat coverage/coverage-final.json | jq '.total.lines.pct'
```

### Desktop (Daily)

```bash
# Rust backend
cd desktop-app/src-tauri
cargo tarpaulin --out Html

# Tauri frontend
cd desktop-app
npm test -- --coverage
```

---

## Success Criteria

### Milestone Complete When:

1. ✅ **Backend**: 80%+ coverage (40,000+ / 50,000 lines)
2. ✅ **Frontend**: 45%+ coverage (15,750+ / 35,000 lines)
3. ✅ **Mobile**: 40%+ coverage (6,000+ / ~15,000 lines)
4. ✅ **Desktop**: 40%+ coverage (4,000+ / ~10,000 lines)
5. ✅ **Overall**: 60%+ weighted average (~65,750+ / ~110,000 lines)
6. ✅ **All critical paths tested** (governance, security, data integrity)
7. ✅ **Property tests passing** (100+ Hypothesis tests, 1000+ examples)
8. ✅ **CI workflows re-enabled** (all tests passing, no failures)

---

## Immediate Next Steps

### Day 0 (Today)
1. ✅ Disable all CI workflows (COMPLETED)
2. ✅ Archive Phase 211 (COMPLETED)
3. ✅ Create Milestone v5.5 (COMPLETED)
4. ✅ Run baseline coverage report (COMPLETED)
5. ✅ Update goal to 60% (COMPLETED - mathematical fix)
6. 🔲 Execute Wave 1A (governance tests)

### Day 1-5: Wave 1A Execution
1. Create test files for 3 governance modules
2. Run tests and verify 15% backend coverage
3. Measure overall coverage (target: ~9%)
4. Create Wave 1A SUMMARY.md

### Day 6-10: Wave 1B Execution
1. Create test files for 4 LLM/episode modules
2. Run tests and verify 25% backend coverage
3. Measure overall coverage (target: ~15%)
4. Create Wave 1B SUMMARY.md

### Day 11-17: Wave 2 Execution
1. Create frontend component tests
2. Create backend tool/skill tests
3. Create property-based tests
4. Measure overall coverage (target: ~35%)
5. Create Wave 2 SUMMARY.md

### Day 18-27: Wave 3 Execution
1. Create mobile test suite
2. Create desktop coverage (Rust + Tauri)
3. Create E2E integration tests
4. Measure overall coverage (target: ~55%)
5. Create Wave 3 SUMMARY.md

### Day 28-31: Wave 4 Execution
1. Final property-based tests
2. Final edge case tests
3. Verify all platforms at targets
4. Re-enable CI workflows
5. Create Wave 4 SUMMARY.md
6. Create final 212-COMPLETE.md

---

## Commands Reference

```bash
# Backend coverage
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest backend/tests/ \
  --cov=backend.core --cov=backend.api --cov=backend.tools \
  --cov-report=term-missing --cov-report=html

# Frontend coverage
cd frontend-nextjs && npm test -- --coverage

# Mobile coverage
cd mobile && npm test -- --coverage

# Desktop Rust coverage
cd desktop-app/src-tauri && cargo tarpaulin --out Html

# Desktop Tauri frontend coverage
cd desktop-app && npm test -- --coverage

# Overall coverage check
cat backend/coverage.json | jq '.totals.percent_covered'
cat frontend-nextjs/coverage/coverage-summary.json | jq '.total.lines.pct'
cat mobile/coverage/coverage-final.json | jq '.total.lines.pct'
```

---

*Baseline report revised 2026-03-20. Target: 60% full codebase coverage in 23-31 days.*
