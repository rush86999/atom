# Roadmap: Atom Test Coverage Initiative

## Overview

Comprehensive cross-platform testing initiative to achieve 80% code coverage across all platforms (backend Python, frontend React/Next.js, mobile React Native, desktop Tauri/Rust). Starting from v5.2's baseline (backend: 26.15%, frontend: 65.85%, mobile: infrastructure foundation, desktop: 65-70%), this milestone focuses on filling coverage gaps with targeted test development, fixing failing tests, and enforcing quality gates to prevent regression.

## Milestones

- ✅ **v3.2 Bug Finding & Coverage Expansion** - Phases 81-90 (shipped 2026-02-26)
- ✅ **v3.3 Finance Testing & Bug Fixes** - Phases 91-110 (shipped 2026-02-25)
- ✅ **v4.0 Platform Integration & Property Testing** - Phases 111-122 (shipped 2026-02-27)
- ✅ **v5.0 Coverage Expansion** - Phases 123-152 (shipped 2026-03-01)
- ✅ **v5.2 Complete Codebase Coverage** - Phases 153-152 (shipped 2026-03-08)
- 🚧 **v5.3 Coverage Expansion to 80% Targets** - Phases 153-157 (in progress)

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

### 🚧 v5.3 Coverage Expansion to 80% Targets (In Progress)

**Milestone Goal:** Achieve actual 80% test coverage across all platforms with enforcement gates and quality metrics

#### Phase 153: Coverage Gates & Progressive Rollout
**Goal**: PR-level coverage enforcement with progressive thresholds (70% → 75% → 80%)
**Depends on**: Phase 152 (Quality Infrastructure Documentation)
**Requirements**: ENFORCE-01, ENFORCE-02
**Success Criteria** (what must be TRUE):
  1. Pull requests that decrease coverage are blocked from merging by diff-cover (backend) and jest-coverage-report-action (frontend)
  2. Coverage threshold enforcement operates at 70% minimum (Phase 1), 75% (Phase 2), 80% (Phase 3) without blocking development
  3. New code files enforce strict 80% coverage threshold regardless of phase
  4. Desktop cargo-tarpaulin enforces fail-under threshold, Mobile jest-expo threshold raised to 80%
**Plans**: 4 plans

**Wave Structure:**
- Wave 1: Plans 01-03 (Backend, Frontend/Mobile, Desktop - parallel platform enforcement)
- Wave 2: Plan 04 (Emergency bypass documentation - depends on Wave 1)

**Plan Breakdown:**
- [x] 153-01-PLAN.md — Backend progressive coverage gate with diff-cover and new code enforcement
- [ ] 153-02-PLAN.md — Frontend/Mobile Jest progressive thresholds with COVERAGE_PHASE support
- [ ] 153-03-PLAN.md — Desktop tarpaulin progressive thresholds with ubuntu-latest runner
- [ ] 153-04-PLAN.md — Emergency bypass documentation and tracking implementation

#### Phase 154: Coverage Trends & Quality Metrics
**Goal**: Coverage trend monitoring and test quality metrics alongside coverage
**Depends on**: Phase 153
**Requirements**: ENFORCE-03, ENFORCE-04
**Success Criteria** (what must be TRUE):
  1. Coverage trend analysis identifies decreases >1% (warning) and >5% (critical) with PR comments showing trend indicators (↑↓→)
  2. Historical coverage data maintained for 30-day rolling window with trend visualization
  3. Assert-to-test ratio monitored to prevent coverage gaming with low-quality tests
  4. Flaky test detection identifies unreliable tests requiring quarantine with tracked execution times
  5. Code complexity metrics (cyclomatic complexity) tracked alongside coverage
**Plans**: 4 plans

**Wave Structure:**
- Wave 1: Plans 01-03 (PR trend comments, assert ratio, complexity/execution time - parallel quality metrics)
- Wave 2: Plan 04 (Comprehensive quality report consolidation - depends on Wave 1)

**Plan Breakdown:**
- [x] 154-01-PLAN.md — PR trend comment generation with coverage indicators (↑↓→)
- [ ] 154-02-PLAN.md — Assert-to-test ratio tracking via AST parsing
- [ ] 154-03-PLAN.md — Code complexity and execution time tracking
- [ ] 154-04-PLAN.md — Comprehensive quality metrics report consolidation

#### Phase 155: Quick Wins (Leaf Components & Infrastructure)
**Depends on**: Phase 154
**Requirements**: QUICK-01, QUICK-02, QUICK-03, QUICK-04
**Success Criteria** (what must be TRUE):
  1. Backend DTOs, utilities, and helpers achieve 80%+ coverage with low-complexity tests
  2. Frontend UI components (Button, Input, Display components) achieve 80%+ coverage
  3. Desktop helper functions and platform-specific utilities achieve 80%+ coverage
  4. Mobile device mock factories and test utilities achieve 80%+ coverage
  5. Route registration, middleware configuration, provider setup, and context wiring tested across platforms
  6. Data transfer objects and serializers (Pydantic models, TypeScript interfaces, Rust structs) validated
  7. Simple state management (read-only services, useState hooks, AsyncStorage/MMKV) tested
**Plans**: 5 plans

**Wave Structure:**
- Wave 1: Plans 01-03B (Backend DTOs, Backend utilities, Frontend UI components, Mobile components - parallel quick wins)
- Wave 2: Plan 04 (Configuration and wiring - depends on Wave 1)

**Plan Breakdown:**
- [x] 155-01-PLAN.md — Backend DTO testing (response models, validators, API schemas)
- [x] 155-02-PLAN.md — Backend utility testing (formatters, validators)
- [x] 155-03A-PLAN.md — Frontend UI component testing (Button, Input, Badge)
- [x] 155-03B-PLAN.md — Mobile component testing and test infrastructure (Button, Card, mocks)
- [x] 155-04-PLAN.md — Configuration and wiring testing (route registration, provider setup)

#### Phase 156: Core Services Coverage (High Impact)
**Goal**: Expand coverage to 80% for critical services (governance, LLM, episodic memory, canvas, HTTP client)
**Depends on**: Phase 155
**Requirements**: CORE-01, CORE-02, CORE-03, CORE-04, CORE-05
**Success Criteria** (what must be TRUE):
  1. Agent governance coverage expanded to 80% (maturity routing, permission checking, lifecycle management, cache validation)
  2. LLM service coverage expanded to 80% (BYOK handler, token counting, rate limiting, streaming)
  3. Episodic memory coverage expanded to 80% (segmentation, retrieval algorithms, lifecycle management, canvas/feedback integration)
  4. Canvas presentation coverage expanded to 80% (state management, chart rendering, form validation, interactive components)
  5. API client coverage expanded to 80% (HTTP methods, error handling, retry logic, WebSocket)
**Plans**: 4 plans

**Wave Structure:**
- Wave 1: Plans 01-04 (Governance, LLM, Episodes, Canvas/HTTP - parallel service testing)

**Plan Breakdown:**
- [x] 156-01-PLAN.md — Agent governance coverage (maturity routing, permissions, lifecycle, cache)
- [x] 156-02-PLAN.md — LLM service coverage (BYOK handler, token counting, rate limiting, streaming)
- [x] 156-03-PLAN.md — Episodic memory coverage (segmentation, retrieval, lifecycle, canvas/feedback integration)
- [x] 156-04-PLAN.md — Canvas presentation and HTTP client coverage (state management, charts, forms, connection pooling, retry logic)

#### Phase 157: Edge Cases & Integration Testing
**Goal**: Complex error paths, routing, accessibility, concurrent operations, and cross-service workflows
**Depends on**: Phase 156
**Requirements**: EDGE-01, EDGE-02, EDGE-03, EDGE-04, EDGE-05
**Success Criteria** (what must be TRUE):
  1. Error boundaries tested across platforms (React error boundaries, exception middleware, Tauri error propagation, network error handling)
  2. Routing and navigation validated (React Router, React Navigation screens, Tauri window management, API route registration)
  3. Accessibility compliance tested to WCAG 2.1 AA (keyboard navigation, screen reader compatibility, ARIA attributes)
  4. Concurrent operations and race conditions tested (database transactions, concurrent agent operations, state updates, IPC parallelization)
  5. Integration tests cover cross-service workflows (agent execution E2E, canvas presentation workflows, offline sync scenarios, multi-platform E2E)
**Plans**: 4 plans

## Progress

**Execution Order:**
Phases execute in numeric order: 153 → 154 → 155 → 156 → 157

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 153. Coverage Gates & Progressive Rollout | v5.3 | 0/4 | Not started | - |
| 154. Coverage Trends & Quality Metrics | v5.3 | 0/TBD | Not started | - |
| 155. Quick Wins | v5.3 | 0/TBD | Not started | - |
| 156. Core Services Coverage | v5.3 | 0/TBD | Not started | - |
| 157. Edge Cases & Integration Testing | v5.3 | 0/TBD | Not started | - |
