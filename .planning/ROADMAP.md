# Roadmap: Atom Test Coverage Initiative

## Overview

Comprehensive cross-platform testing initiative to achieve 80% code coverage across all platforms (backend Python, frontend React/Next.js, mobile React Native, desktop Tauri/Rust). Starting from v5.2's baseline (backend: 26.15%, frontend: 65.85%, mobile: infrastructure foundation, desktop: 65-70%), this milestone focuses on filling coverage gaps with targeted test development, fixing failing tests, and enforcing quality gates to prevent regression.

## Milestones

- ✅ **v3.2 Bug Finding & Coverage Expansion** - Phases 81-90 (shipped 2026-02-26)
- ✅ **v3.3 Finance Testing & Bug Fixes** - Phases 91-110 (shipped 2026-02-25)
- ✅ **v4.0 Platform Integration & Property Testing** - Phases 111-122 (shipped 2026-02-27)
- ✅ **v5.0 Coverage Expansion** - Phases 123-152 (shipped 2026-03-01)
- ✅ **v5.2 Complete Codebase Coverage** - Phases 153-152 (shipped 2026-03-08)
- 🚧 **v5.3 Coverage Expansion to 80% Targets** - Phases 153-158 (in progress)

## Phases

<details>
<summary>✅ v5.2 Complete Codebase Coverage (Phases 127-152) - SHIPPED 2026-03-08</summary>

### Phase 127: Backend Gap Closure
**Goal**: Backend coverage expansion methodology and integration tests
**Plans**: 12 plans

### Phase 128: API Contract Testing
**Goal**: Schemathesis validation and OpenAPI spec automation
**Plans**: 8 plans

### Phase 129: Critical Error Paths
**Goal**: Database failures, timeouts, rate limiting tests
**Plans**: 5 plans

### Phase 130: Frontend Module Coverage
**Goal**: Per-module thresholds and CI/CD enforcement
**Plans**: 6 plans

### Phase 131: Frontend Custom Hooks
**Goal**: @testing-library/react-hooks isolation
**Plans**: 6 plans

### Phase 132: Frontend Accessibility
**Goal**: jest-axe, WCAG 2.1 AA compliance
**Plans**: 5 plans

### Phase 133: Frontend API Integration
**Goal**: MSW error handling and retry logic
**Plans**: 5 plans

### Phase 134: Mobile Coverage Foundation
**Goal**: Infrastructure, 250+ tests, CI/CD
**Plans**: 7 plans

### Phase 135: Mobile Device Features
**Goal**: Camera, location, notifications, offline sync
**Plans**: 7 plans

### Phase 136: Mobile Navigation
**Goal**: React Navigation screens and deep links
**Plans**: 6 plans

### Phase 137: Mobile State Management
**Goal**: Context providers and AsyncStorage/MMKV
**Plans**: 6 plans

### Phase 138: Mobile Platform-Specific
**Goal**: iOS vs Android differences
**Plans**: 5 plans

### Phase 139: Desktop Coverage Baseline
**Goal**: Tarpaulin configured and baseline measured
**Plans**: 3 plans

### Phase 140: Desktop Coverage Expansion
**Goal**: 35% estimated coverage, 83 tests
**Plans**: 6 plans

### Phase 141: Desktop Rust Backend
**Goal**: Core logic and IPC handlers, 65-70% coverage
**Plans**: 7 plans

### Phase 142: Cross-Platform Shared Utilities
**Goal**: SYMLINK strategy and TypeScript utilities
**Plans**: 5 plans

### Phase 143: Cross-Platform API Types
**Goal**: openapi-typescript from OpenAPI spec
**Plans**: 4 plans

### Phase 144: Cross-Platform Weighted Coverage
**Goal**: Platform minimums (70/80/50/40%)
**Plans**: 4 plans

### Phase 145: Cross-Platform Property Testing
**Goal**: FastCheck shared across platforms
**Plans**: 4 plans

### Phase 146: Cross-Platform E2E Orchestration
**Goal**: Playwright + Detox + Tauri unified
**Plans**: 3 plans

### Phase 147: Quality Infrastructure Parallel
**Goal**: <15 min feedback, 4-platform jobs
**Plans**: 4 plans

### Phase 148: Quality Infrastructure Trending
**Goal**: Per-platform coverage trends
**Plans**: 4 plans

### Phase 149: Quality Infrastructure Reliability
**Goal**: Flaky test detection, retries, quarantine
**Plans**: 4 plans

### Phase 150: Quality Infrastructure Documentation
**Goal**: Testing guides and onboarding
**Plans**: 5 plans

</details>

<details>
<summary>✅ v5.3 Coverage Expansion to 80% Targets (Phases 153-158) — SHIPPED 2026-03-09</summary>

**See:** [.planning/milestones/v5.3-ROADMAP.md](.planning/milestones/v5.3-ROADMAP.md) for full details

- [x] Phase 153: Coverage Gates & Progressive Rollout (4/4 plans) — completed 2026-03-08
- [x] Phase 154: Coverage Trends & Quality Metrics (4/4 plans) — completed 2026-03-08
- [x] Phase 155: Quick Wins (5/5 plans) — completed 2026-03-08
- [x] Phase 156: Core Services Coverage (12/12 plans) — completed 2026-03-08
- [x] Phase 157: Edge Cases & Integration Testing (4/4 plans) — completed 2026-03-09
- [x] Phase 158: Coverage Gap Closure (5/5 plans) — completed 2026-03-09

</details>

### 🚧 Phase 159: Backend 80% Coverage (In Progress)

**Goal:** Achieve 80% backend test coverage by completing LLM service, episodic memory, and governance/canvas coverage
**Depends on**: Phase 158
**Success Criteria** (what must be TRUE):
  1. Backend overall coverage reaches 80%+ target (up from 74.55%)
  2. LLM service coverage increases from 43% to 80%+
  3. Episodic memory coverage increases from 21.3% to 80%+
  4. Governance and canvas coverage increases to 80%+
  5. Backend quality gates pass at 80% threshold
**Plans**: 4 plans

**Wave Structure:**
- Wave 1: Plan 01 (LLM service gap closure - highest impact)
- Wave 2: Plan 02 (Backend services gap closure - governance, episodic, canvas)
- Wave 3: Plan 03 (Final verification and 80% target status)

**Plan Breakdown:**
- [ ] 159-01-PLAN.md — LLM service gap closure (43% → target 80%, 75 tests)
- [ ] 159-02-PLAN.md — Backend services gap closure (governance, episodic, canvas, 85 tests)
- [ ] 159-03-PLAN.md — Backend 80% verification and quality gate compliance

**Wave Structure:**
- Wave 1: Plan 01 (Desktop compilation fixes - blocks all desktop work)
- Wave 2: Plans 02-04 (Mobile, Frontend, Backend - parallel platform coverage expansion)
- Wave 3: Plan 05 (Final verification and summary - depends on Waves 1-2)

**Plan Breakdown:**
- [ ] 158-01-PLAN.md — Desktop compilation fixes (unblocks Tarpaulin + 23 accessibility tests)
- [ ] 158-02-PLAN.md — Mobile test suite execution (navigation, screens, state management)
- [ ] 158-03-PLAN.md — Frontend component testing blitz (Dashboard, Calendar, CommunicationHub, integrations)
- [ ] 158-04-PLAN.md — Backend LLM service HTTP-level mocking (36.5% → 80% coverage)
- [ ] 158-05-PLAN.md — Final verification and cross-platform summary
## Progress

**Execution Order:**
Phases execute in numeric order: 153 → 154 → 155 → 156 → 157

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 153. Coverage Gates & Progressive Rollout | v5.3 | 4/4 | Complete | 2026-03-08 |
| 154. Coverage Trends & Quality Metrics | v5.3 | 4/4 | Complete | 2026-03-08 |
| 155. Quick Wins | v5.3 | 5/5 | Complete | 2026-03-08 |
| 156. Core Services Coverage | v5.3 | 12/12 | Complete | 2026-03-08 |
| 157. Edge Cases & Integration Testing | v5.3 | 4/4 | Complete | 2026-03-09 |
| 158. Coverage Gap Closure | v5.3 | 5/5 | Complete | 2026-03-09 |
| 159. Backend 80% Coverage | v5.3 | 3/3 | Complete | 2026-03-09 |
| 160. Backend 80% Target (Blockers) | v5.3 | 2/2 | Complete (Not Achieved) | 2026-03-10 |
