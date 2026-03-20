# Milestone v5.5: Full Codebase 60% Coverage - Realistic Target

**Created:** 2026-03-20
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

## Why 60% Instead of 80%?

### Mathematical Reality

The original goal of 80% coverage across the ENTIRE codebase was mathematically impossible with the planned targets:

```
Original Plan:
Backend:  50,000 lines × 80% = 40,000 lines
Frontend: 35,000 lines × 45% = 15,750 lines
Mobile:   15,000 lines × 40% =  6,000 lines
Desktop:  10,000 lines × 40% =  4,000 lines
Total:   110,000 lines

Weighted coverage = (40,000 + 15,750 + 6,000 + 4,000) / 110,000
               = 59.77%

Required for 80%: 88,000 lines
Planned: 65,750 lines
Shortfall: 22,250 lines (20.23%)
```

### Revised Goal: 60% Overall Coverage

The 60% target is **realistic and achievable** with the current wave structure:

```
Revised Plan (matches current wave targets):
Backend:  50,000 lines × 80% = 40,000 lines (80% target maintained)
Frontend: 35,000 lines × 45% = 15,750 lines (45% target maintained)
Mobile:   15,000 lines × 40% =  6,000 lines (40% target maintained)
Desktop:  10,000 lines × 40% =  4,000 lines (40% target maintained)
Total:   110,000 lines

Weighted coverage = (40,000 + 15,750 + 6,000 + 4,000) / 110,000
               = 59.77% ≈ 60%

Achievable: Yes ✅
Wave changes: None (current waves already target this)
```

### Alternative: 80% Would Require Massive Expansion

To achieve actual 80% overall coverage, we would need:
- Frontend: 35,000 lines × 80% = 28,000 lines (+12,250 lines, +78%)
- Mobile: 15,000 lines × 70% = 10,500 lines (+4,500 lines, +75%)
- Desktop: 10,000 lines × 70% = 7,000 lines (+3,000 lines, +75%)
- Additional cost: 2-3 more waves, +20,000 lines of tests

This is not feasible for Phase 212.

---

## Wave-Based Execution Strategy

### Wave 1A: Backend Governance (Week 1)

**Backend Target:** 7.41% → 15% (+7.59pp)

**Modules:**
- `agent_governance_service.py` (80% target)
- `trigger_interceptor.py` (80% target)
- `governance_cache.py` (80% target)

**Estimated Effort:** 3-5 days (3 modules, ~1,050 lines of tests)

### Wave 1B: Backend LLM & Episodes (Week 1)

**Backend Target:** 15% → 25% (+10pp)

**Modules:**
- `llm/byok_handler.py` (80% target)
- `llm/cognitive_tier_system.py` (80% target)
- `episode_segmentation_service.py` (80% target)
- `episode_retrieval_service.py` (80% target)

**Estimated Effort:** 3-5 days (4 modules, ~1,600 lines of tests)

### Wave 2: Core Services (Week 2)

**Frontend Target:** 13.42% → 45% (+31.58pp)
**Backend Target:** 25% → 45% (+20pp)

**Frontend Components:**
- Integration components (Slack, Jira, GitHub, AgentManager)
- State management hooks (useAgentState, useCanvasState)

**Backend Services:**
- Tools (canvas, browser, device)
- Skills (adapter, composition, loader)
- Training (student training, supervision)

**Estimated Effort:** 7 days (8 modules, ~4,000 lines of tests)

### Wave 3: Database & Platform (Week 3)

**Mobile Target:** 0% → 40% (+40pp)
**Desktop Target:** 0% → 40% (+40pp)
**Backend Target:** 45% → 80% (+35pp)

**Backend:**
- Core services (lifecycle, world model, policy, CLI, models)
- API contracts, E2E integration

**Mobile:**
- Device features (Camera, Location, Notifications)
- Storage and navigation

**Desktop:**
- Rust backend (core logic, IPC handlers)
- Tauri frontend (window management)

**Estimated Effort:** 7-10 days (5 backend + 8 platform tests, ~3,000 lines)

### Wave 4: Property Tests & Edge Cases (Week 4)

**Target:** Final push to 60% overall

**Property Tests:**
- Governance invariants (maturity routing, permission checks)
- LLM invariants (cognitive tier classification, cache awareness)
- Episode invariants (segmentation, retrieval, lifecycle)
- Financial invariants (decimal precision, double-entry validation)
- Security invariants (JWT validation, auth checks)

**Edge Cases:**
- Timeouts, retries, errors, empty inputs, concurrent access
- Integration gaps (WebSocket, LanceDB, Redis, S3/R2)

**Estimated Effort:** 3-4 days (100+ property tests, ~2,000 lines)

---

## Success Criteria

### Milestone Complete When:

1. ✅ **Backend**: 80%+ coverage (40,000+ / 50,000 lines)
2. ✅ **Frontend**: 45%+ coverage (15,750+ / 35,000 lines)
3. ✅ **Mobile**: 40%+ coverage (6,000+ / 15,000 lines)
4. ✅ **Desktop**: 40%+ coverage (4,000+ / 10,000 lines)
5. ✅ **Overall**: 60%+ weighted average (65,750+ / 110,000 lines)
6. ✅ **All critical paths tested** (governance, security, data integrity)
7. ✅ **Property tests passing** (100+ Hypothesis tests, 1000+ examples)
8. ✅ **CI workflows re-enabled** (all tests passing, no failures)

---

## Estimated Timeline

| Wave | Duration | Coverage Target | Modules |
|------|----------|-----------------|---------|
| **Wave 1A** | 3-5 days | 7% → 15% overall | 3 governance |
| **Wave 1B** | 3-5 days | 15% → 25% overall | 4 LLM/episodes |
| **Wave 2** | 7 days | 25% → 35% overall | Frontend + tools |
| **Wave 3** | 7-10 days | 35% → 55% overall | Backend + platforms |
| **Wave 4** | 3-4 days | 55% → 60% overall | Property + edge cases |
| **Total** | **23-31 days** | **7% → 60%** | **20+ modules** |

**Aggressive Timeline:** 23 days (parallel execution, no blockers)
**Realistic Timeline:** 27 days (some blockers, rework)
**Conservative Timeline:** 31 days (external dependencies, complex fixes)

---

## Commands Reference

```bash
# Backend coverage
cd backend
PYTHONPATH=/Users/rushiparikh/projects/atom/backend pytest tests/ \
  --cov=core --cov=api --cov=tools --cov-report=html --cov-report=term

# Frontend coverage
cd frontend-nextjs
npm test -- --coverage --watchAll=false

# Mobile coverage
cd mobile
npm test -- --coverage

# Desktop Rust coverage
cd desktop-app/src-tauri
cargo tarpaulin --out Html

# Desktop Tauri frontend coverage
cd desktop-app
npm test -- --coverage
```

---

*Milestone v5.5 revised 2026-03-20. Target: 60% full codebase coverage in 23-31 days.*
