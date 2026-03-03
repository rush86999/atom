# Requirements: Atom Backend Coverage v5.1

**Defined:** 2026-03-01
**Core Value:** Critical system paths are thoroughly tested and validated before production deployment
**Milestone:** v5.1 Backend Coverage Expansion

## v5.1 Requirements

Requirements for backend coverage expansion milestone. Each maps to roadmap phases.

### Phase 101 Fixes

- [x] **FIX-01**: Canvas test mock configuration resolved — 66 tests unblocked, coverage measurement functional (Phase 101, re-verified Phase 111)
- [x] **FIX-02**: Module import failures fixed — Coverage.py can measure all 6 target backend services (Phase 101, re-verified Phase 111)

### Core Backend Services

- [x] **CORE-01**: Agent governance service achieves 60%+ coverage — GovernanceCache, AgentGovernanceService, AgentContextResolver tested (Phase 112, 2026-03-01)
  - agent_governance_service.py: 82.08%
  - agent_context_resolver.py: 96.58%
  - governance_cache.py: 62.05%
  - 46+ governance tests passing
- [ ] **CORE-02**: Episodic memory services achieve 60%+ coverage — EpisodeSegmentationService, EpisodeRetrievalService, EpisodeLifecycleService tested
- [ ] **CORE-03**: LLM services achieve 60%+ coverage — BYOK handler, cognitive tier system, canvas summaries tested
- [ ] **CORE-04**: Agent execution services achieve 60%+ coverage — AtomAgentEndpoints, agent workflows tested
- [ ] **CORE-05**: Student training services achieve 60%+ coverage — TriggerInterceptor, StudentTrainingService, SupervisionService tested
- [ ] **CORE-06**: Graduation framework achieves 60%+ coverage — AgentGraduationService with constitutional compliance validated

### API Routes & Tools

- [ ] **API-01**: Canvas API routes achieve 60%+ coverage — Canvas presentations, form submissions, state management tested
- [ ] **API-02**: Browser automation achieves 60%+ coverage — Playwright CDP integration, web scraping, form filling tested
- [ ] **API-03**: Device capabilities achieve 60%+ coverage — Camera, screen recording, location, notifications tested
- [ ] **API-04**: Health & monitoring routes achieve 60%+ coverage — Health checks, Prometheus metrics, structured logging tested
- [ ] **API-05**: Admin routes achieve 60%+ coverage — Business facts, citations, world model tested

### Property-Based Testing

- [x] **PROP-01**: Governance invariants tested — Maturity routing, permission checks, cache consistency validated with Hypothesis (Phase 123, 2026-03-02)
  - 59 property tests passing
  - 8,900+ Hypothesis-generated examples
  - 3 coverage gaps closed (async, cache correctness, edge cases)
  - Invariants: maturity routing, permission consistency, cache <1ms P99
- [ ] **PROP-02**: Episode invariants tested — Segmentation logic, retrieval ranking, lifecycle transitions validated
- [ ] **PROP-03**: Financial invariants tested — Decimal precision, double-entry validation, audit immutability validated
- [ ] **PROP-04**: LLM invariants tested — Token counting, cost calculation, tier escalation validated

## v5.2+ Requirements

Deferred to future milestones. Tracked but not in current roadmap.

### Frontend Coverage Expansion
- **FRNT-01**: React component testing — Complete frontend 80% coverage target
- **FRNT-02**: State management testing — Hooks, context providers, reducers
- **FRNT-03**: API client testing — MSW integration, error handling

### Mobile & Desktop Testing
- **MOBL-01**: React Native testing — Device features, offline sync, cross-platform
- **DSKT-01**: Tauri testing — Rust backend, integration tests

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Frontend coverage expansion | Backend-first milestone (21.67% → 80%) |
| Mobile/desktop coverage | Backend-first milestone |
| New feature development | This milestone focuses on testing existing features |
| E2E/load/chaos testing | Infrastructure deferred to v6.0+ |
| Phase 102-110 re-execution | v5.0 phases complete, v5.1 focuses on new expansion |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FIX-01 | Phase 111 | Complete |
| FIX-02 | Phase 111 | Complete |
| CORE-01 | Phase 112 | Complete |
| CORE-02 | Phase 113 | Pending |
| CORE-03 | Phase 114 | Pending |
| CORE-04 | Phase 115 | Pending |
| CORE-05 | Phase 116 | Pending |
| CORE-06 | Phase 117 | Pending |
| API-01 | Phase 118 | Pending |
| API-02 | Phase 119 | Pending |
| API-03 | Phase 120 | Pending |
| API-04 | Phase 121 | Pending |
| API-05 | Phase 122 | Pending |
| PROP-01 | Phase 123 | Complete |
| PROP-02 | Phase 124 | Pending |
| PROP-03 | Phase 125 | Pending |
| PROP-04 | Phase 126 | Pending |

**Coverage:**
- v5.1 requirements: 16 total
- Mapped to phases: 16 (100%)
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-01*
*Last updated: 2026-03-01 after roadmap creation*
