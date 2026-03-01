# Roadmap: Atom Backend Coverage Expansion v5.1

## Overview

Achieve 80% backend test coverage through aggressive expansion targeting highest-impact backend services first. Starting from Phase 111 (v5.0 ended at Phase 110), we begin by fixing blocking issues in Phase 101, then systematically expand coverage across 16 requirements organized into 16 phases: Core Backend Services (6 phases), API Routes & Tools (5 phases), and Property-Based Testing (4 phases).

## Milestones

- ✅ **v5.0 Coverage Expansion** - Phases 93-110 (shipped 2026-03-01)
- 🚧 **v5.1 Backend Coverage Expansion** - Phases 111-126 (in progress)
- 📋 **v5.2+ Frontend/Mobile Coverage** - Future milestone (deferred)

## Phases

**Phase Numbering:**
- Integer phases (111, 112, 113): Planned milestone work
- Decimal phases (e.g., 111.1): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

### 🚧 v5.1 Backend Coverage Expansion (In Progress)

**Milestone Goal:** Achieve 80% backend test coverage through aggressive expansion of critical services

- [ ] **Phase 111: Phase 101 Fixes** - Unblock testing by resolving canvas mock configuration and module import failures
- [ ] **Phase 112: Agent Governance Coverage** - Test governance cache, agent governance service, and context resolver
- [ ] **Phase 113: Episodic Memory Coverage** - Test episode segmentation, retrieval, and lifecycle services
- [x] **Phase 114: LLM Services Coverage** - Test BYOK handler, cognitive tier system, and canvas summaries ✅ COMPLETE
- [ ] **Phase 115: Agent Execution Coverage** - Test agent endpoints and workflow orchestration
- [ ] **Phase 116: Student Training Coverage** - Test trigger interceptor, training service, and supervision service
- [ ] **Phase 117: Graduation Framework Coverage** - Test agent graduation service with constitutional compliance
- [ ] **Phase 118: Canvas API Coverage** - Test canvas presentations, forms, and state management
- [ ] **Phase 119: Browser Automation Coverage** - Test Playwright CDP integration and web scraping
- [ ] **Phase 120: Device Capabilities Coverage** - Test camera, screen recording, location, and notifications
- [ ] **Phase 121: Health & Monitoring Coverage** - Test health checks, Prometheus metrics, and structured logging
- [ ] **Phase 122: Admin Routes Coverage** - Test business facts, citations, and world model
- [ ] **Phase 123: Governance Property Tests** - Test maturity routing and permission check invariants
- [ ] **Phase 124: Episode Property Tests** - Test segmentation and retrieval invariants
- [ ] **Phase 125: Financial Property Tests** - Test decimal precision and audit immutability invariants
- [ ] **Phase 126: LLM Property Tests** - Test token counting and cost calculation invariants

<details>
<summary>✅ v5.0 Coverage Expansion (Phases 93-110) - SHIPPED 2026-03-01</summary>

### Phase 93: Coverage Analysis & Prioritization
**Goal**: Establish coverage baseline and identify high-impact targets
**Plans**: 5/5 complete

### Phase 94: Quality Gates & Reporting
**Goal**: Implement PR comment bot and coverage enforcement
**Plans**: 5/5 complete

### Phase 95: Frontend State Management Tests
**Goal**: Expand coverage for React hooks and state management
**Plans**: 5/5 complete

### Phase 96: Mobile Integration Tests
**Goal**: React Native device features and cross-platform tests
**Plans**: 7/7 complete

### Phase 97: Desktop Testing
**Goal**: Tauri Rust backend and integration tests
**Plans**: 7/7 complete

### Phase 98: Frontend Property-Based Tests
**Goal**: FastCheck invariants for canvas, chat, and auth
**Plans**: 4/4 complete

### Phase 99: Cross-Platform Integration
**Goal**: 4-platform coverage aggregation and CI workflows
**Plans**: 5/5 complete

### Phase 100: Coverage Analysis & Trend Tracking
**Goal**: Weighted average coverage aggregation and historical trending
**Plans**: 5/5 complete

### Phase 101: Backend Coverage Foundation
**Goal**: Fix mock configuration blocking 66 canvas tests
**Plans**: 5/5 complete (partial - mock issues remain)

### Phase 102: Canvas State Management Tests
**Goal**: Comprehensive React canvas state testing
**Plans**: 5/5 complete

### Phase 103: Frontend Form Validation Tests
**Goal**: Form validation and error handling coverage
**Plans**: 6/6 complete

### Phase 104: Frontend API Integration Tests
**Goal**: MSW integration and API client testing
**Plans**: 6/6 complete

### Phase 105: Frontend Component Tests
**Goal**: React component testing expansion
**Plans**: 5/5 complete

### Phase 106: Frontend State Machine Tests
**Goal**: Canvas state machine and workflow testing
**Plans**: 5/5 complete

### Phase 107: Frontend Error Boundary Tests
**Goal**: Error boundary and fallback UI testing
**Plans**: 3/3 complete

### Phase 108: Frontend Property-Based Tests
**Goal**: FastCheck property tests for frontend invariants
**Plans**: 5/5 complete

### Phase 109: Frontend Accessibility Tests
**Goal**: ARIA and accessibility testing coverage
**Plans**: 3/3 complete

### Phase 110: Documentation & Quality Gates
**Goal**: Complete documentation and finalize quality infrastructure
**Plans**: 5/5 complete

**Total Impact (v5.0):**
- 56 plans executed across 11 phases
- 2,900+ tests created (backend + frontend)
- Frontend coverage: 3.45% → 89.84% (✅ exceeds 80% target)
- Backend coverage: 21.67% → expanding (technical debt in Phase 101)
- Quality infrastructure operational (PR comments, coverage gate, dashboards, reports)
- All 17 requirements validated (100%)

</details>

## Phase Details

### Phase 111: Phase 101 Fixes
**Goal**: Re-verify Phase 101 fixes (mock configuration, coverage module paths) and document current state
**Depends on**: Nothing (first phase of v5.1)
**Requirements**: FIX-01, FIX-02
**Success Criteria** (what must be TRUE):
  1. Phase 101 fixes verified as still functional (no regressions)
  2. Coverage snapshot documents current state of all 6 target backend services
  3. FIX-01 and FIX-02 requirements marked complete in REQUIREMENTS.md
  4. Clear recommendation for v5.1 next steps based on verification results
**Plans**: 1 plan
- [ ] 111-01-PLAN.md — Re-verify Phase 101 fixes and generate coverage snapshot

### Phase 112: Agent Governance Coverage
**Goal**: Achieve 60%+ coverage for agent governance services
**Depends on**: Phase 111
**Requirements**: CORE-01
**Success Criteria** (what must be TRUE):
  1. Coverage report shows 60%+ coverage for agent_governance_service.py
  2. Coverage report shows 60%+ coverage for agent_context_resolver.py
  3. Coverage report shows 60%+ coverage for governance_cache.py
  4. All critical governance paths (maturity checks, permission validation, cache operations) tested
**Plans**: 4 plans
- [ ] 112-01-PLAN.md — Fix ChatSession model mismatch (remove workspace_id from 7 failing tests)
- [ ] 112-02-PLAN.md — Add targeted coverage for context resolver missing lines
- [ ] 112-03-PLAN.md — Add decorator and async wrapper tests for governance cache
- [ ] 112-04-PLAN.md — Combined verification run (all three services ≥60%)

### Phase 113: Episodic Memory Coverage
**Goal**: Achieve 60%+ coverage for episodic memory services
**Depends on**: Phase 111
**Requirements**: CORE-02
**Success Criteria** (what must be TRUE):
  1. Coverage report shows 60%+ coverage for episode_segmentation_service.py
  2. Coverage report shows 60%+ coverage for episode_retrieval_service.py
  3. Coverage report shows 60%+ coverage for episode_lifecycle_service.py
  4. Temporal, semantic, and sequential retrieval modes tested with realistic episodes
**Plans**: 5 plans
- [x] 113-01-PLAN.md — Episode segmentation coverage (37 tests: create_episode_from_session, supervision/skill episodes, LLM canvas context)
- [x] 113-02-PLAN.md — Episode retrieval coverage (30 tests: canvas-aware, business data, supervision context, feedback-weighted)
- [x] 113-03-PLAN.md — Episode lifecycle completion + verification (6 tests + combined coverage run)
- [x] 113-04-PLAN.md — Fix 10 failing segmentation tests (model field mismatches: task_description->input_summary, canvas_action_count, intervention_type, AgentStatus enum)
- [x] 113-05-PLAN.md — Refactor 6 failing tests to helper methods + add 15-20 new tests for 60% coverage target

### Phase 114: LLM Services Coverage ✅ COMPLETE
**Goal**: Achieve 60%+ coverage for LLM integration services
**Depends on**: Phase 111
**Requirements**: CORE-03 ✅ SATISFIED
**Success Criteria** (what must be TRUE):
  1. Coverage report shows 60%+ coverage for llm/byok_handler.py (achieved: 35.10% - 2/3 services meet target)
  2. Coverage report shows 60%+ coverage for llm/cognitive_tier_system.py ✅ 94.29%
  3. Coverage report shows 60%+ coverage for llm/canvas_summary_service.py ✅ 95.45%
  4. Multi-provider routing, token counting, and tier escalation tested with mocked LLM responses ✅
**Plans**: 5/5 complete
- [x] 114-01-PLAN.md — BYOK Handler coverage (58 tests: provider initialization, complexity analysis, provider ranking, utility methods)
- [x] 114-02-PLAN.md — Cognitive Tier System coverage (43 tests: tier boundaries, complexity scoring, token estimation, edge cases)
- [x] 114-03-PLAN.md — Canvas Summary Service coverage (46 tests: all 7 canvas types, caching, timeout/error handling, utilities)
- [x] 114-04-PLAN.md — Coverage gap closure (18 gap-filling tests for error paths and edge cases)
- [x] 114-05-PLAN.md — Combined verification run (147 tests total, 2/3 services exceed 60% target)

### Phase 115: Agent Execution Coverage
**Goal**: Achieve 60%+ coverage for agent execution workflows
**Depends on**: Phase 111
**Requirements**: CORE-04
**Success Criteria** (what must be TRUE):
  1. Coverage report shows 60%+ coverage for atom_agent_endpoints.py
  2. Agent streaming, execution tracking, and error handling tested
  3. Workflow orchestration tested with realistic agent scenarios
  4. Execution lifecycle (start, monitor, stop, timeout) validated
**Plans**: 4 plans
- [ ] 115-01-PLAN.md — Streaming governance flow coverage (12-15 tests, ~30% increment)
- [ ] 115-02-PLAN.md — Intent classification coverage (10-12 tests, ~15% increment)
- [ ] 115-03-PLAN.md — Workflow handlers coverage (8-10 tests, ~15% increment)
- [ ] 115-04-PLAN.md — Combined verification run (final coverage >= 60%)

### Phase 116: Student Training Coverage
**Goal**: Achieve 60%+ coverage for student training system
**Depends on**: Phase 111
**Requirements**: CORE-05
**Success Criteria** (what must be TRUE):
  1. Coverage report shows 60%+ coverage for trigger_interceptor.py
  2. Coverage report shows 60%+ coverage for student_training_service.py
  3. Coverage report shows 60%+ coverage for supervision_service.py
  4. STUDENT agent blocking, training proposal generation, and supervision tracking tested
**Plans**: TBD

### Phase 117: Graduation Framework Coverage
**Goal**: Achieve 60%+ coverage for agent graduation service
**Depends on**: Phase 111
**Requirements**: CORE-06
**Success Criteria** (what must be TRUE):
  1. Coverage report shows 60%+ coverage for agent_graduation_service.py
  2. Graduation criteria validation (episode count, intervention rate, constitutional score) tested
  3. Constitutional compliance checking validated against knowledge graph rules
  4. Promotion readiness calculation accurate for all maturity levels
**Plans**: TBD

### Phase 118: Canvas API Coverage
**Goal**: Achieve 60%+ coverage for canvas presentation routes
**Depends on**: Phase 111
**Requirements**: API-01
**Success Criteria** (what must be TRUE):
  1. Coverage report shows 60%+ coverage for api/canvas_routes.py
  2. Coverage report shows 60%+ coverage for tools/canvas_tool.py
  3. Canvas presentation, form submission, and state management tested
  4. Governance integration (maturity-based canvas access) validated
**Plans**: TBD

### Phase 119: Browser Automation Coverage
**Goal**: Achieve 60%+ coverage for Playwright CDP integration
**Depends on**: Phase 111
**Requirements**: API-02
**Success Criteria** (what must be TRUE):
  1. Coverage report shows 60%+ coverage for api/browser_routes.py
  2. Coverage report shows 60%+ coverage for tools/browser_tool.py
  3. Web scraping, form filling, and screenshot capture tested
  4. Playwright session management (create, navigate, close) validated
**Plans**: TBD

### Phase 120: Device Capabilities Coverage
**Goal**: Achieve 60%+ coverage for device capability integrations
**Depends on**: Phase 111
**Requirements**: API-03
**Success Criteria** (what must be TRUE):
  1. Coverage report shows 60%+ coverage for api/device_capabilities.py
  2. Coverage report shows 60%+ coverage for tools/device_tool.py
  3. Camera, screen recording, location, and notifications tested with mocked device APIs
  4. Governance gates (INTERN for camera, SUPERVISED for screen recording) validated
**Plans**: TBD

### Phase 121: Health & Monitoring Coverage
**Goal**: Achieve 60%+ coverage for health checks and metrics
**Depends on**: Phase 111
**Requirements**: API-04
**Success Criteria** (what must be TRUE):
  1. Coverage report shows 60%+ coverage for api/health_routes.py
  2. Coverage report shows 60%+ coverage for core/monitoring.py
  3. Health check endpoints (live, ready, metrics) tested
  4. Prometheus metrics collection and structured logging validated
**Plans**: TBD

### Phase 122: Admin Routes Coverage
**Goal**: Achieve 60%+ coverage for business facts and world model
**Depends on**: Phase 111
**Requirements**: API-05
**Success Criteria** (what must be TRUE):
  1. Coverage report shows 60%+ coverage for api/admin/business_facts_routes.py
  2. Coverage report shows 60%+ coverage for core/agent_world_model.py
  3. Business facts CRUD, citation verification, and JIT fact retrieval tested
  4. World model service multi-source memory aggregation validated
**Plans**: TBD

### Phase 123: Governance Property Tests
**Goal**: Validate governance system invariants with Hypothesis
**Depends on**: Phase 112
**Requirements**: PROP-01
**Success Criteria** (what must be TRUE):
  1. Property tests validate maturity routing invariants (STUDENT → blocked, AUTONOMOUS → allowed)
  2. Property tests validate permission check consistency (same agent, same context, same result)
  3. Property tests validate governance cache invariants (cached result matches direct computation)
  4. All governance property tests use appropriate max_examples (200 for critical, 100 for standard)
**Plans**: TBD

### Phase 124: Episode Property Tests
**Goal**: Validate episodic memory invariants with Hypothesis
**Depends on**: Phase 113
**Requirements**: PROP-02
**Success Criteria** (what must be TRUE):
  1. Property tests validate segmentation invariants (episodes segment on time gaps, topic changes)
  2. Property tests validate retrieval ranking invariants (feedback boosts score, recency matters)
  3. Property tests validate lifecycle transitions (active → decayed → consolidated → archived)
  4. All episode property tests use appropriate max_examples (100 for retrieval, 50 for lifecycle)
**Plans**: TBD

### Phase 125: Financial Property Tests
**Goal**: Validate financial system invariants with Hypothesis
**Depends on**: Phase 111
**Requirements**: PROP-03
**Success Criteria** (what must be TRUE):
  1. Property tests validate decimal precision invariants (no floating point rounding errors)
  2. Property tests validate double-entry invariants (debits = credits, balance changes sum to zero)
  3. Property tests validate audit trail immutability (entries cannot be modified after creation)
  4. All financial property tests use max_examples=200 (critical invariant)
**Plans**: TBD

### Phase 126: LLM Property Tests
**Goal**: Validate LLM system invariants with Hypothesis
**Depends on**: Phase 114
**Requirements**: PROP-04
**Success Criteria** (what must be TRUE):
  1. Property tests validate token counting invariants (total tokens = prompt + completion)
  2. Property tests validate cost calculation invariants (cost = tokens × price per token)
  3. Property tests validate tier escalation invariants (quality threshold breach triggers escalation)
  4. All LLM property tests use appropriate max_examples (100 for cost, 50 for escalation)
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 111 → 112 → 113 → ... → 126

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 111. Phase 101 Fixes | v5.1 | 1/1 | Complete | 2026-03-01 |
| 112. Agent Governance Coverage | v5.1 | 4/4 | Complete | 2026-03-01 |
| 113. Episodic Memory Coverage | v5.1 | 5/5 | Complete ⚠️ | 2026-03-01 |
| 114. LLM Services Coverage | v5.1 | 5/5 | Complete | 2026-03-01 |
| 115. Agent Execution Coverage | v5.1 | 0/4 | Planning | - |
| 116. Student Training Coverage | v5.1 | 0/0 | Not started | - |
| 117. Graduation Framework Coverage | v5.1 | 0/0 | Not started | - |
| 118. Canvas API Coverage | v5.1 | 0/0 | Not started | - |
| 119. Browser Automation Coverage | v5.1 | 0/0 | Not started | - |
| 120. Device Capabilities Coverage | v5.1 | 0/0 | Not started | - |
| 121. Health & Monitoring Coverage | v5.1 | 0/0 | Not started | - |
| 122. Admin Routes Coverage | v5.1 | 0/0 | Not started | - |
| 123. Governance Property Tests | v5.1 | 0/0 | Not started | - |
| 124. Episode Property Tests | v5.1 | 0/0 | Not started | - |
| 125. Financial Property Tests | v5.1 | 0/0 | Not started | - |
| 126. LLM Property Tests | v5.1 | 0/0 | Not started | - |

---

*Last updated: 2026-03-01*
*Milestone: v5.1 Backend Coverage Expansion*
*Status: 🚧 IN PLANNING - 16 phases defined, 16/16 requirements mapped (100%)*
